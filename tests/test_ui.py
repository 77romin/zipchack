import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class UITests(unittest.TestCase):
    def test_preferences_search_and_radius(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        next(b for b in app.button if b.label == "조건 적용").click().run()
        self.assertTrue(any("입력해주세요" in x.value for x in app.warning))
        next(w for w in app.text_input if w.label == "직장 주소 또는 장소명").set_value("서울시청")
        app.slider[0].set_value(5.0)
        next(b for b in app.button if b.label == "조건 적용").click().run()
        self.assertEqual(app.session_state["housing_conditions"]["search_radius_km"], 5.0)
        with patch("kakao_api.search_workplace", return_value=[
            {"name":"서울시청","address":"서울 중구","latitude":37.5665,"longitude":126.978}
        ]):
            with patch.dict("os.environ", {"KAKAO_REST_API_KEY":"test-only"}):
                next(b for b in app.button if b.label == "직장 검색").click().run()
                next(w for w in app.selectbox if w.label == "검색 결과에서 직장을 선택해주세요.").select_index(0).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(next(w for w in app.selectbox if w.label == "검색 결과에서 직장을 선택해주세요.").value["name"], "서울시청")
                next(b for b in app.button if b.label == "직장 검색").click().run()
                self.assertIsNone(next(w for w in app.selectbox if w.label == "검색 결과에서 직장을 선택해주세요.").value)

if __name__ == "__main__":
    unittest.main()
