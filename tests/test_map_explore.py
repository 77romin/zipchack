import json,unittest
from unittest.mock import patch
from map_explore import read_boundaries,map_card
from map_view import build_map_html
from chat_query import run_chat_turn

class ExploreTests(unittest.TestCase):
    def test_partial_conditions_can_query_without_workplace_commute_or_preferences(self):
        conditions={'deal_type':'월세','deposit_max':1000,'rent_max':70,'district':'중구','deal_month':'202609','housing_types':['오피스텔']}
        result={'district_code':'11140','month':'202609','statuses':[{'category':'오피스텔','complete':True}],'rows':[]}
        with patch('chat_query.fetch_rents',return_value=result) as fetch:
            turn=run_chat_turn('추천해줘',conditions,[],'',{},False)
        fetch.assert_called_once()
        self.assertEqual(turn['stage'],'candidates')
        self.assertNotIn('workplace',turn['conditions'])

    def test_boundaries_reject_wrong_code_crs_and_open_ring(self):
        feature={'type':'Feature','properties':{'legal_code':'1114016200'},'geometry':{'type':'Polygon','coordinates':[[[127,37.5],[127.1,37.5],[127.1,37.6],[127,37.5]]]}}
        def encode():return json.dumps({'type':'FeatureCollection','features':[feature]}).encode()
        self.assertIn('1114016200',read_boundaries(encode()))
        feature['properties']['legal_code']='1114062'
        with self.assertRaises(ValueError):read_boundaries(encode())
        feature['properties']['legal_code']='1114016200';feature['geometry']['coordinates'][0][0]=[200000,450000]
        with self.assertRaises(ValueError):read_boundaries(encode())

    def test_missing_data_is_not_zero_age_and_payload_is_escaped(self):
        point={'name':'신당동','dong':'신당동','legal_code':'1114016200','latitude':37.56,'longitude':127,'month':'202609','count':1}
        card=map_card(point,None,{},None,{},'202609')
        self.assertEqual(card['age_rates'],{})
        self.assertTrue(any('미조회' in x for x in card['lines']))
        card['lines'].append('</script><script>alert(1)</script>')
        html=build_map_html('key',neighborhood=point,explore=card)
        self.assertNotIn('</script><script>alert(1)',html)
        for text in ['layer-age','layer-bike','법정동 경계','showArea','fillOpacity']:
            self.assertIn(text,html)

    def test_integrated_card_scopes_prices_and_facilities_and_zero_population(self):
        point={'legal_code':'1114016200','dong':'신당동','latitude':37.56,'longitude':127.0}
        row={'dong':'신당동','deposit':1000,'monthly_rent':60,'deal_type':'월세','contract_date':'2026-09-01','category':'오피스텔','source_url':'https://www.data.go.kr/example'}
        result={'district_code':'11140','month':'202609','queried_at':'조회일','statuses':[{'category':'오피스텔','complete':False}],'rows':[row]}
        conditions={'deal_type':'월세','deposit_max':1000,'rent_max':70}
        bikes={'stations':[{'id':'a','name':'가까운 대여소','latitude':37.5601,'longitude':127.}], 'data_month':'2026-06','source_url':'https://data.seoul.go.kr/bike'}
        parks={'parks':[{'id':'b','name':'먼 공원','latitude':37.8,'longitude':127.}], 'source_updated_at':'2026-09-23','source_url':'https://data.seoul.go.kr/park'}
        residents={'1114016200:202609':{'total':0,'month':'202609','ages':{}}}
        card=map_card(point,result,conditions,bikes,residents,'202609',parks)
        text=' '.join(card['lines'])
        for expected in ['거래 1건','보증금 1,000 / 월세 60','따릉이 대여소 1곳','주요 공원 0곳','2026-06','2026-09-23','전체 거래가 아닐','인구 0명']:
            self.assertIn(expected,text)
        self.assertEqual(card['age_rates'],{})
        self.assertEqual(len(card['sources']),3)
        elsewhere=map_card({**point,'legal_code':'1117016200'},result,conditions,bikes,{},'202609',parks)
        self.assertIn('전월세 거래 미조회',' '.join(elsewhere['lines']))
        empty=map_card(point,{**result,'rows':[]},conditions,bikes,{},'202609',parks)
        self.assertIn('현재 매물이 없다는 뜻은 아님',' '.join(empty['lines']))

    def test_region_cards_use_clicked_code_and_mark_approximate_point(self):
        from map_explore import region_cards
        regions=[{'code':'1114016200','name':'서울특별시 중구 신당동','latitude':37.56,'longitude':127.},
                 {'code':'1117010100','name':'서울특별시 용산구 후암동','latitude':37.55,'longitude':126.98}]
        residents={'1117010100:202609':{'total':100,'month':'202609','ages':{20:40,30:20,60:40}}}
        cards=region_cards(regions,None,None,{},None,None,residents,'202609')
        self.assertEqual(cards[0]['card']['age_rates'],{})
        self.assertEqual(cards[1]['card']['age_rates']['20'],40.)
        self.assertIn('동 경계 기준점(대략)',' '.join(cards[1]['card']['lines']))
