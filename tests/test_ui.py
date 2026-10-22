import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class UITests(unittest.TestCase):
    def test_preferences_search_and_radius(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        app.button[0].click().run()
        self.assertTrue(any("입력해주세요" in x.value for x in app.warning))
        app.text_input[0].set_value("서울시청")
        app.slider[0].set_value(5.0)
        app.button[0].click().run()
        self.assertEqual(app.session_state["housing_conditions"]["search_radius_km"], 5.0)
        with patch("kakao_api.search_workplace", return_value=[
            {"name":"서울시청","address":"서울 중구","latitude":37.5665,"longitude":126.978}
        ]):
            with patch.dict("os.environ", {"KAKAO_REST_API_KEY":"test-only"}):
                app.button[1].click().run()
                app.selectbox[0].select_index(0).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.selectbox[0].value["name"], "서울시청")
                app.button[1].click().run()
                self.assertIsNone(app.selectbox[0].value)

if __name__ == "__main__":
    unittest.main()
