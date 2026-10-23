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
        with patch('map_viewport._map',return_value=bounds),patch('map_viewport.bundled_boundaries',return_value=geometries),patch('map_viewport.fetch_residents',side_effect=lambda code,month,key:{'code':code,'month':month,'total':10}) as fetch,patch.dict('os.environ',{'MOIS_RESIDENT_API_KEY':'test'}):
            app=AppTest.from_string(source,default_timeout=20).run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(fetch.call_count,2)
            app.run();self.assertEqual(fetch.call_count,2)
            self.assertEqual(len(app.session_state['resident_data']),2)

    def test_zoomed_out_does_not_call_every_api(self):
        bounds={'south':37.1,'north':37.9,'west':126.1,'east':127.9}
        geometries={str(i):geometry(127.,37.52) for i in range(121)}
        with patch('map_viewport._map',return_value=bounds),patch('map_viewport.bundled_boundaries',return_value=geometries),patch('map_viewport.fetch_residents') as fetch:
            app=AppTest.from_string("from map_viewport import render_viewport\nrender_viewport('',[],None,'test','202609')").run()
            fetch.assert_not_called();self.assertTrue(any('확대' in i.value for i in app.info))
