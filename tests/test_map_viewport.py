import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from map_viewport import visible_codes,validate_viewport

def geometry(x,y):
    return {'type':'Polygon','coordinates':[[[x,y],[x+.02,y],[x+.02,y+.02],[x,y+.02],[x,y]]]}

class ViewportTests(unittest.TestCase):
    def test_cross_district_and_outside_bounds(self):
        bounds={'south':37.50,'north':37.56,'west':126.98,'east':127.04}
        geometries={'1114016200':geometry(127.,37.52),'1120010100':geometry(127.02,37.53),'other':geometry(127.4,37.7)}
        self.assertEqual(visible_codes(bounds,geometries),['1114016200','1120010100'])
        with self.assertRaises(ValueError):validate_viewport({**bounds,'south':float('nan')})
        with self.assertRaises(ValueError):validate_viewport({**bounds,'east':126.8})

    def test_automatic_fetch_and_session_cache_without_district_selection(self):
        bounds={'south':37.50,'north':37.56,'west':126.98,'east':127.04}
        geometries={'1114016200':geometry(127.,37.52),'1120010100':geometry(127.02,37.53)}
        source="from map_viewport import render_viewport\nrender_viewport('',[],None,'test','202609')"
        with patch('map_viewport._viewport_component',return_value=bounds),patch('map_viewport.bundled_boundaries',return_value=geometries),patch('map_viewport.fetch_residents',side_effect=lambda code,month,key:{'code':code,'month':month,'total':10}) as fetch,patch.dict('os.environ',{'MOIS_RESIDENT_API_KEY':'test'}):
            app=AppTest.from_string(source,default_timeout=20).run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(fetch.call_count,2)
            app.run();self.assertEqual(fetch.call_count,2)
            self.assertEqual(len(app.session_state['resident_data']),2)

    def test_zoomed_out_does_not_call_every_api(self):
        bounds={'south':37.1,'north':37.9,'west':126.1,'east':127.9}
        geometries={str(i):geometry(127.,37.52) for i in range(121)}
        with patch('map_viewport._viewport_component',return_value=bounds),patch('map_viewport.bundled_boundaries',return_value=geometries),patch('map_viewport.fetch_residents') as fetch:
            app=AppTest.from_string("from map_viewport import render_viewport\nrender_viewport('',[],None,'test','202609')").run()
            fetch.assert_not_called();self.assertTrue(any('확대' in i.value for i in app.info))

    def test_retry_only_failed_and_record_safe_reason(self):
        from resident_api import ResidentLookupError
        bounds={'south':37.50,'north':37.56,'west':126.98,'east':127.04}
        geometries={'1114016200':geometry(127.,37.52),'1120010100':geometry(127.02,37.53)}
        calls=[]
        def fetch(code,month,key):
            calls.append(code)
            if code=='1120010100' and calls.count(code)==1:
                raise ResidentLookupError('connection','secret must not be rendered')
            return {'code':code,'month':month,'total':10}
        source="from map_viewport import render_viewport\nrender_viewport('',[],None,'test','202609')"
        with patch('map_viewport._viewport_component',return_value=bounds),patch('map_viewport.bundled_boundaries',return_value=geometries),patch('map_viewport.fetch_residents',side_effect=fetch),patch.dict('os.environ',{'MOIS_RESIDENT_API_KEY':'test'}):
            app=AppTest.from_string(source,default_timeout=20).run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(app.session_state['viewport_failure_reasons']['1120010100:202609'],'connection')
            self.assertNotIn('secret',str(app.table[0].value))
            app.run();self.assertEqual(len(calls),2)
            app.button(key='retry_viewport').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(calls.count('1114016200'),1)
            self.assertEqual(calls.count('1120010100'),2)
            self.assertEqual(app.session_state['viewport_failures'],{})

    def test_resident_no_data_and_connection_categories(self):
        import requests
        from resident_api import parse_residents,fetch_residents,ResidentLookupError
        with self.assertRaises(ResidentLookupError) as raised:
            parse_residents(b'<response><head><resultCode>00</resultCode><totalCount>0</totalCount></head></response>','1114016200','202609')
        self.assertEqual(raised.exception.category,'no_data')
        with patch('resident_api.requests.get',side_effect=requests.Timeout('secret')):
            with self.assertRaises(ResidentLookupError) as raised:
                fetch_residents('1114016200','202609','secret')
            self.assertEqual(raised.exception.category,'connection')
            self.assertNotIn('secret',str(raised.exception))
