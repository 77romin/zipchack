import unittest
from unittest.mock import patch,Mock
from pathlib import Path
import requests
from neighborhood_api import parse_neighborhood,resolve_neighborhood,NeighborhoodError
from map_view import build_map_html
from test_housing_candidates import result,CONDITIONS

def payload(**changes):
    document={'address_name':'서울 중구 신당동','address_type':'REGION','y':'37.56','x':'127.01','address':None}
    document.update(changes)
    return {'documents':[document]}

POINT={'name':'중구 신당동','address':'서울 중구 신당동','latitude':37.56,'longitude':127.01,'queried_at':'test KST'}

class NeighborhoodMapTests(unittest.TestCase):
    def test_exact_region_and_same_name_other_district(self):
        point=parse_neighborhood(payload(),'중구','신당동')
        self.assertEqual(point['latitude'],37.56)
        for data in [payload(address_name='서울 성동구 신당동'),payload(address_name='서울 중구 신당1동'),
                     payload(address_type='REGION_ADDR'),payload(y='nan'),payload(x='0')]:
            with self.assertRaises(NeighborhoodError):parse_neighborhood(data,'중구','신당동')

    def test_ambiguous_regions_are_not_guessed(self):
        data=payload()
        data['documents']+=payload(y='37.57')['documents']
        with self.assertRaises(NeighborhoodError):parse_neighborhood(data,'중구','신당동')

    def test_no_key_or_bad_query_no_request(self):
        with patch('neighborhood_api.requests.get') as get:
            for code,dong,key in [('11140','신당동',''),('99999','신당동','key'),('11140','<script>','key')]:
                with self.assertRaises(NeighborhoodError):resolve_neighborhood(code,dong,key)
            get.assert_not_called()

    def test_failure_hides_rest_key(self):
        with patch('neighborhood_api.requests.get',side_effect=requests.Timeout('secret-rest-key')):
            with self.assertRaises(NeighborhoodError) as error:resolve_neighborhood('11140','신당동','secret-rest-key')
        self.assertNotIn('secret-rest-key',str(error.exception))
        with patch('neighborhood_api.requests.get',return_value=Mock(json=lambda:payload())) as get:
            resolve_neighborhood('11140','신당동','secret-rest-key')
        self.assertEqual(get.call_args.kwargs['params']['query'],'서울특별시 중구 신당동')

    def test_map_geometry_and_labels_are_safe(self):
        data={**POINT,'name':'</script><script>bad()</script>','count':2,'month':'202609'}
        html=build_map_html('public',neighborhood=data)
        self.assertNotIn('</script><script>bad()',html)
        self.assertIn('label.textContent',html)
        self.assertIn('개별 주택 아님',html)
        self.assertIn('bounds.extend(center)',html)
        self.assertIn('map.setLevel(5)',html)
        self.assertIn('"neighborhood": null',build_map_html('public'))
        with self.assertRaises(ValueError):build_map_html('public',neighborhood={**data,'latitude':float('nan')})

    def test_ui_selection_cache_and_budget_invalidation(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']=CONDITIONS
        app.session_state['rent_result']=result()
        app.run()
        with patch('rent_view.resolve_neighborhood',return_value=POINT) as resolve:
            next(w for w in app.selectbox if w.label=='거래를 살펴볼 동네').select('신당동').run()
            resolve.assert_not_called()
            next(b for b in app.button if b.key=='show_candidate_neighborhood').click().run()
            self.assertEqual(resolve.call_count,1)
            app.run()
            next(b for b in app.button if b.key=='show_candidate_neighborhood').click().run()
            self.assertEqual(resolve.call_count,1)
        self.assertTrue(any('중구 신당동' in c.value for c in app.caption))
        next(w for w in app.selectbox if w.label=='거래를 살펴볼 동네').select('전체').run()
        self.assertFalse(any('지도: 중구 신당동' in c.value for c in app.caption))
        app.session_state['conversation_conditions']={**CONDITIONS,'rent_max':1}
        app.run()
        self.assertFalse(any(b.key=='show_candidate_neighborhood' for b in app.button))
        self.assertEqual(len(app.exception),0)

    def test_ui_failure_does_not_cache_wrong_point(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']=CONDITIONS
        app.session_state['rent_result']=result()
        app.run()
        next(w for w in app.selectbox if w.label=='거래를 살펴볼 동네').select('신당동').run()
        with patch('rent_view.resolve_neighborhood',side_effect=NeighborhoodError('위치 미확인')):
            next(b for b in app.button if b.key=='show_candidate_neighborhood').click().run()
        self.assertEqual(app.session_state['neighborhood_locations'],{})
        self.assertTrue(any('위치 미확인' in w.value for w in app.warning))
        self.assertEqual(len(app.exception),0)
