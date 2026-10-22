import unittest
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
from seoul_api import parse_citydata
from test_city_details import XML

class CityPreferencesUITests(unittest.TestCase):
    def test_tabs_layers_and_comparison_survive_preferences(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        data={**parse_citydata(XML.encode()),'queried_at':'test KST'}
        with patch('seoul_api.fetch_citydata',return_value=data):
            next(b for b in app.button if b.label=='현재 상황 조회').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(t.label=='전기차 충전' for t in app.tabs))
        next(b for b in app.button if b.label=='이 장소를 비교 목록에 추가').click().run()
        self.assertEqual(len(app.session_state['city_comparisons']),1)
        next(s for s in app.slider if s.label=='현재 대기환경 중요도').set_value(5)
        next(b for b in app.button if b.label=='현재환경 선호 적용').click().run()
        self.assertEqual(app.session_state['city_preferences']['weights']['air'],5)
        self.assertEqual(len(app.session_state['city_comparisons']),1)
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=='비교 목록 비우기').click().run()
        self.assertEqual(app.session_state['city_comparisons'],{})

if __name__=='__main__':unittest.main()
