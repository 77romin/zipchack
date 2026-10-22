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
        for text in ['layer-age','layer-bike','대표점 주변 500m','showArea','fillOpacity']:
            self.assertIn(text,html)
