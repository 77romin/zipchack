import unittest
from unittest.mock import patch,Mock
import requests
from seoul_api import parse_citydata,fetch_citydata,SeoulDataError
from streamlit.testing.v1 import AppTest
from pathlib import Path

FIXTURE=b"""<SeoulRtd.citydata><RESULT><CODE>INFO-000</CODE></RESULT><CITYDATA>
<AREA_NM>test</AREA_NM><LIVE_PPLTN_STTS><LIVE_PPLTN_STTS>
<AREA_PPLTN_MIN>100</AREA_PPLTN_MIN><AREA_PPLTN_MAX>200</AREA_PPLTN_MAX>
<RESNT_PPLTN_RATE>0</RESNT_PPLTN_RATE><PPLTN_RATE_20>35</PPLTN_RATE_20>
<REPLACE_YN>Y</REPLACE_YN></LIVE_PPLTN_STTS></LIVE_PPLTN_STTS>
<WEATHER_STTS><WEATHER_STTS><PM10>0</PM10><PM25>-999</PM25><TEMP>-2</TEMP></WEATHER_STTS></WEATHER_STTS>
</CITYDATA></SeoulRtd.citydata>"""

class SeoulTests(unittest.TestCase):
    def test_nested_xml_zero_missing_and_replacement(self):
        data=parse_citydata(FIXTURE)
        self.assertEqual(data['resident_rate'],0)
        self.assertEqual(data['pm10'],0)
        self.assertIsNone(data['pm25'])
        self.assertIsNone(data['age_rates']['30대'])
        self.assertEqual(data['replacement'],'Y')
        self.assertEqual(data['temperature'],-2)

    def test_error_and_invalid_xml(self):
        for xml in [b'<RESULT><CODE>INFO-100</CODE></RESULT>',b'<broken',b'<root/>']:
            with self.assertRaises(SeoulDataError): parse_citydata(xml)

    def test_no_key_no_request(self):
        with patch('seoul_api.requests.get') as get:
            with self.assertRaises(SeoulDataError): fetch_citydata('area','')
            get.assert_not_called()

    def test_secrets_not_in_error(self):
        with patch('seoul_api.requests.get',side_effect=requests.Timeout('secret-key')):
            with self.assertRaises(SeoulDataError) as error: fetch_citydata('area','secret-key')
            self.assertNotIn('secret-key',str(error.exception))

    def test_success_and_time(self):
        response=Mock(content=FIXTURE)
        with patch('seoul_api.requests.get',return_value=response) as get:
            data=fetch_citydata('광화문·덕수궁','test-only')
            self.assertIn('KST',data['queried_at'])
            self.assertEqual(get.call_args.kwargs['timeout'],(5,20))

    def test_ui_missing_key_and_success(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        next(b for b in app.button if b.label=='현재 상황 조회').click().run()
        self.assertEqual(len(app.exception),0)
        with patch('seoul_api.fetch_citydata',return_value={**parse_citydata(FIXTURE),'queried_at':'test KST'}):
            next(b for b in app.button if b.label=='현재 상황 조회').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(m.label=='상주 인구 비율' and m.value=='0%' for m in app.metric))

if __name__=='__main__': unittest.main()
