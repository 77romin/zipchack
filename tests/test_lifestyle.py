import unittest
from unittest.mock import Mock,patch
from io import BytesIO
from park_data import load_parks,fetch_parks
from resident_api import parse_residents,fetch_residents,preferred_share
from geo import stations_within

def resident_xml(total=220):
    ages=''.join(f'<{sex}{age}AgeNmprCnt>10</{sex}{age}AgeNmprCnt>' for sex in ['male','feml'] for age in range(0,101,10))
    return (f'<response><head><resultCode>00</resultCode><totalCount>1</totalCount></head><items><item>'
            f'<stdgCd>1114016200</stdgCd><statsYm>202609</statsYm><stdgNm>신당동</stdgNm><totNmprCnt>{total}</totNmprCnt>'
            f'{ages}</item></items></response>').encode()

class LifestyleTests(unittest.TestCase):
    def test_park_file_aliases_and_invalid_rows(self):
        content='공원명,위도,경도\n테스트공원,37.56,127.01\n오류,nan,127'
        data=load_parks(content.encode('cp949'),'official.csv')
        self.assertEqual(len(data['parks']),1)
        self.assertEqual(data['skipped'],1)
        self.assertEqual(stations_within(data['parks'],37.56,127.01,0.5)[0]['distance_m'],0)
        with self.assertRaises(ValueError):load_parks('공원명,주소\n공원,서울'.encode(),'bad.csv')

    def test_park_api_success_and_partial_response(self):
        section={'RESULT':{'CODE':'INFO-000'},'list_total_count':1,
                 'row':[{'P_PARK':'테스트공원','LATITUDE':'37.56','LONGITUDE':'127.01'}]}
        response=Mock(); response.json.return_value={'SearchParkInfoService':section}
        with patch('park_data.requests.get',return_value=response):
            self.assertEqual(len(fetch_parks('test')['parks']),1)
            section['list_total_count']=2
            with self.assertRaises(ValueError):fetch_parks('test')

    def test_park_and_population_errors_hide_key(self):
        import requests
        with patch('park_data.requests.get',side_effect=requests.Timeout('secret')):
            with self.assertRaises(ValueError) as error:fetch_parks('secret')
            self.assertNotIn('secret',str(error.exception))
        with patch('resident_api.requests.get',side_effect=requests.Timeout('secret')):
            with self.assertRaises(ValueError) as error:fetch_residents('1114016200','202609','secret')
            self.assertNotIn('secret',str(error.exception))

    def test_resident_ratio_and_deduplicated_ages(self):
        data=parse_residents(resident_xml(),'1114016200','202609')
        self.assertEqual(data['total'],220)
        self.assertEqual(preferred_share(data,[20,30,20]),18.2)
        self.assertIsNone(preferred_share(data,[]))
        self.assertIsNone(preferred_share({**data,'total':0},[20]))

    def test_resident_scope_consistency_and_missing(self):
        for content in [resident_xml(221),resident_xml().replace(b'<stdgCd>1114016200',b'<stdgCd>1111016200'),
                        resident_xml().replace(b'<totalCount>1',b'<totalCount>2'),
                        resident_xml().replace(b'<male20AgeNmprCnt>10</male20AgeNmprCnt>',b'')]:
            with self.assertRaises(ValueError):parse_residents(content,'1114016200','202609')

    def test_resident_request_is_single_legal_dong_residents_only(self):
        response=Mock(content=resident_xml())
        with patch('resident_api.requests.get',return_value=response) as get:
            fetch_residents('1114016200','202609','test')
        params=get.call_args.kwargs['params']
        self.assertEqual(params['lv'],7)
        self.assertEqual(params['regSeCd'],2)
        with patch('resident_api.requests.get') as get:
            with self.assertRaises(ValueError):fetch_residents('1114016200','202609','')
            get.assert_not_called()

    def test_lifestyle_ui_missing_and_provided_data(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_string("""import streamlit as st
from lifestyle_view import render_lifestyle
point={'name':'중구 신당동','latitude':37.56,'longitude':127.01,'legal_code':'1114016200'}
park={'parks':[{'id':'1','name':'테스트공원','latitude':37.56,'longitude':127.01}],'origin':'test','skipped':0}
render_lifestyle(point,{'preferred_ages':[20,30]},None,park)
""").run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('따릉이 위치 자료 미확인' in item.value for item in app.info))
        self.assertTrue(any(m.label=='대표점 500m 안의 공원' and m.value=='1곳' for m in app.metric))
        next(w for w in app.text_input if w.key=='resident_month').set_value('202609')
        with patch('lifestyle_view.fetch_residents',return_value=parse_residents(resident_xml(),'1114016200','202609')):
            next(b for b in app.button if b.key=='fetch_residents').click().run()
        self.assertTrue(any(m.value=='18.2%' for m in app.metric))
        self.assertEqual(len(app.exception),0)
