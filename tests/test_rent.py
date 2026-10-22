import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote
from pathlib import Path
import requests
from rent_api import parse_page, fetch_rents, fetch_category, filter_budget, validate_query, RentDataError, SOURCES

def fixture(page=1,total=1,items=None):
    if items is None:
        items='<item><sggCd>11140</sggCd><umdNm>신당동</umdNm><aptNm>테스트건물</aptNm><deposit>1,000</deposit><monthlyRent>70</monthlyRent><dealYear>2026</dealYear><dealMonth>9</dealMonth><dealDay>1</dealDay><excluUseAr>20.5</excluUseAr><totalFloorAr>25</totalFloorAr></item>'
    return f'<response><header><resultCode>000</resultCode></header><body><items>{items}</items><pageNo>{page}</pageNo><totalCount>{total}</totalCount></body></response>'.encode()

class RentTests(unittest.TestCase):
    def test_four_types_units_and_area(self):
        for category in SOURCES:
            row=parse_page(fixture(),category,'11140','202609')['rows'][0]
            self.assertEqual(row['deposit'],1000)
            self.assertEqual(row['monthly_rent'],70)
            self.assertEqual(row['area_type'],'연면적' if category=='단독다가구' else '전용면적')

    def test_missing_negative_zero_and_wrong_scope(self):
        for old,new in [('<monthlyRent>70</monthlyRent>','<monthlyRent/>'),
                        ('<deposit>1,000</deposit>','<deposit>-1</deposit>'),
                        ('<sggCd>11140</sggCd>','<sggCd>11110</sggCd>'),
                        ('<dealDay>1</dealDay>','<dealDay>32</dealDay>')]:
            result=parse_page(fixture().replace(old.encode(),new.encode()),'아파트','11140','202609')
            self.assertEqual(result['skipped'],1)
        row=parse_page(fixture().replace(b'<monthlyRent>70</monthlyRent>',b'<monthlyRent>0</monthlyRent>'),'아파트','11140','202609')['rows'][0]
        self.assertEqual(row['deal_type'],'전세')
        self.assertEqual(filter_budget([row],{'deposit_max':1000,'rent_max':70}),[])
        self.assertEqual(len(filter_budget([row],{'deal_type':'전세','deposit_max':1000})),1)

    def test_budget_boundary_change_and_duplicates(self):
        rows=parse_page(fixture(),'아파트','11140','202609')['rows']*2
        self.assertEqual(len(filter_budget(rows,{'deposit_max':1000,'rent_max':70})),2)
        self.assertEqual(filter_budget(rows,{'deposit_max':1000,'rent_max':60}),[])
        self.assertIsNone(filter_budget(rows,{'deal_type':'매매'}))

    def test_all_pages_and_encoded_key(self):
        responses=[Mock(content=fixture(1,2)),Mock(content=fixture(2,2))]
        with patch('rent_api.requests.get',side_effect=responses) as get:
            result=fetch_category('아파트','11140','202609','abc%2Bdef%3D')
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(get.call_args.kwargs['params']['serviceKey'],'abc+def=')
        self.assertEqual(get.call_args.kwargs['params']['pageNo'],2)

    def test_limit_and_page_mismatch(self):
        with patch('rent_api.requests.get',return_value=Mock(content=fixture(1,5))):
            self.assertFalse(fetch_category('아파트','11140','202609','test',max_pages=1)['complete'])
        with patch('rent_api.requests.get',return_value=Mock(content=fixture(2,5))):
            with self.assertRaises(RentDataError): fetch_category('아파트','11140','202609','test')

    def test_errors_and_no_key_do_not_leak(self):
        with patch('rent_api.requests.get',side_effect=requests.Timeout('secret-key')):
            with self.assertRaises(RentDataError) as error:
                fetch_category('아파트','11140','202609','secret-key')
        self.assertNotIn('secret-key',str(error.exception))
        with patch('rent_api.requests.get') as get:
            with self.assertRaises(RentDataError): fetch_rents('11140','202609',['아파트'],'')
            get.assert_not_called()
        for content in [b'<broken',b'<response/>',b'<OpenAPI_ServiceResponse><cmmMsgHeader><returnAuthMsg>secret-key</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>']:
            with self.assertRaises(RentDataError) as error:
                parse_page(content,'아파트','11140','202609')
            self.assertNotIn('secret-key',str(error.exception))

    def test_partial_type_failure_is_visible(self):
        success={'rows':[],'total':0,'received':0,'skipped':0,'complete':True}
        with patch('rent_api.fetch_category',side_effect=[success,RentDataError('접근 실패')]):
            result=fetch_rents('11140','202609',['아파트','오피스텔'],'test')
        self.assertIsNone(result['statuses'][0]['error'])
        self.assertEqual(result['statuses'][1]['error'],'접근 실패')

    def test_query_validation(self):
        for code,month,types in [('12345','202609',['아파트']),('11140','202613',['아파트']),('11140','209901',['아파트']),('11140','202609',[])]:
            with self.assertRaises(RentDataError): validate_query(code,month,types)

    def test_ui_budget_change_reuses_records(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']={'deal_type':'월세','deposit_max':1000,'rent_max':70}
        data={'rows':parse_page(fixture(),'아파트','11140','202609')['rows'],
              'statuses':[{'category':'아파트','total':1,'received':1,'skipped':0,'complete':True,'error':None}],
              'district_code':'11140','month':'202609','queried_at':'test KST'}
        with patch('rent_view.fetch_rents',return_value=data) as fetch:
            next(b for b in app.button if b.label=='전월세 실거래 조회').click().run()
            self.assertEqual(fetch.call_count,1)
            self.assertTrue(any(m.label=='현재 예산에 맞는 조회 거래' and m.value=='1건' for m in app.metric))
            app.session_state['conversation_conditions']={'deal_type':'월세','deposit_max':1000,'rent_max':60}
            app.run()
            self.assertEqual(fetch.call_count,1)
        self.assertTrue(any(m.label=='현재 예산에 맞는 조회 거래' and m.value=='0건' for m in app.metric))
        self.assertEqual(len(app.exception),0)
