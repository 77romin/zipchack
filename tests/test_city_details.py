import unittest
from seoul_api import parse_citydata

XML="""<SeoulRtd.citydata><RESULT><CODE>INFO-000</CODE></RESULT><CITYDATA>
<AREA_NM>테스트 장소</AREA_NM><LIVE_PPLTN_STTS><LIVE_PPLTN_STTS>
<AREA_PPLTN_MIN>100</AREA_PPLTN_MIN><MALE_PPLTN_RATE>0</MALE_PPLTN_RATE><FEMALE_PPLTN_RATE>100</FEMALE_PPLTN_RATE>
<PPLTN_RATE_20>30</PPLTN_RATE_20></LIVE_PPLTN_STTS></LIVE_PPLTN_STTS>
<PRK_STTS><PRK_STTS><PRK_NM>주차장 A</PRK_NM><PRK_CD>a</PRK_CD><LAT>37.5665</LAT><LNG>126.978</LNG>
<CPCTY>100</CPCTY><CUR_PRK_YN>Y</CUR_PRK_YN><CUR_PRK_CNT>0</CUR_PRK_CNT><RATES>0</RATES></PRK_STTS>
<PRK_STTS><PRK_NM>주차장 B</PRK_NM><PRK_CD>b</PRK_CD><CUR_PRK_YN>N</CUR_PRK_YN><CUR_PRK_CNT>999</CUR_PRK_CNT></PRK_STTS></PRK_STTS>
<SUB_STTS><SUB_STTS><SUB_STN_NM>시청</SUB_STN_NM><SUB_STN_LINE>1호선</SUB_STN_LINE><SUB_STN_X>126.978</SUB_STN_X><SUB_STN_Y>37.5665</SUB_STN_Y></SUB_STTS>
<SUB_STTS><SUB_STN_NM>시청</SUB_STN_NM><SUB_STN_LINE>1호선</SUB_STN_LINE></SUB_STTS></SUB_STTS>
<CHARGER_STTS><CHARGER_STTS><STAT_NM>충전소</STAT_NM><STAT_ID>e</STAT_ID><STAT_LIMITYN>Y</STAT_LIMITYN>
<STAT_LIMITDETAIL>입주민 전용</STAT_LIMITDETAIL><STAT_X>126.98</STAT_X><STAT_Y>37.567</STAT_Y>
<DETAIL><CHARGER_ID>01</CHARGER_ID><CHARGER_STAT>3</CHARGER_STAT><STATUPDDT>20261022090000</STATUPDDT></DETAIL></CHARGER_STTS></CHARGER_STTS>
<WEATHER_STTS><WEATHER_STTS><FCST24HOURS><FCST24HOURS><TEMP>99</TEMP></FCST24HOURS></FCST24HOURS>
<TEMP>-2</TEMP><AIR_IDX>좋음</AIR_IDX><AIR_IDX_MVL>20</AIR_IDX_MVL><AIR_IDX_MAIN>PM10</AIR_IDX_MAIN><PM10>0</PM10></WEATHER_STTS></WEATHER_STTS>
<LIVE_CMRCL_STTS><LIVE_CMRCL_STTS><AREA_CMRCL_LVL>활발</AREA_CMRCL_LVL><AREA_SH_PAYMENT_CNT>0</AREA_SH_PAYMENT_CNT>
<CMRCL_MALE_RATE>70</CMRCL_MALE_RATE><CMRCL_20_RATE>40</CMRCL_20_RATE><CMRCL_TIME>2026-10-22 09:00</CMRCL_TIME>
<LIST><ROW><RSB_MID_CTGR>카페</RSB_MID_CTGR><RSB_SH_PAYMENT_CNT>10</RSB_SH_PAYMENT_CNT></ROW></LIST>
</LIVE_CMRCL_STTS></LIVE_CMRCL_STTS></CITYDATA></SeoulRtd.citydata>"""

class CityDetailTests(unittest.TestCase):
    def setUp(self): self.data=parse_citydata(XML.encode())
    def test_gender_not_commerce_gender(self):
        self.assertEqual(self.data['gender_rates']['남성'],0)
        self.assertEqual(self.data['commerce']['gender_rates']['남성'],70)
        self.assertEqual(self.data['age_rates']['20대'],30)
        self.assertEqual(self.data['commerce']['age_rates']['20대'],40)
    def test_parking_realtime_and_zero(self):
        self.assertEqual(len(self.data['parking']),2)
        self.assertEqual(self.data['parking'][0]['available'],0)
        self.assertEqual(self.data['parking'][0]['base_fee'],0)
        self.assertIsNone(self.data['parking'][1]['available'])
    def test_facilities_not_mixed(self):
        self.assertEqual(len(self.data['subways']),1)
        self.assertEqual(self.data['subways'][0]['longitude'],126.978)
        ev=self.data['ev_stations'][0]
        self.assertEqual(ev['restriction'],'입주민 전용')
        self.assertEqual(ev['chargers'][0]['status_code'],'3')
    def test_weather_not_forecast(self):
        self.assertEqual(self.data['temperature'],-2)
        self.assertEqual(self.data['air']['value'],20)
        self.assertEqual(self.data['pm10'],0)
    def test_commerce_nested_and_missing(self):
        self.assertEqual(self.data['commerce']['payment_count'],0)
        self.assertEqual(self.data['commerce']['industries'][0]['payment_count'],10)
        self.assertIsNone(self.data['commerce']['amount_min'])
        empty=parse_citydata(b'<CITYDATA><AREA_NM>empty</AREA_NM></CITYDATA>')
        self.assertEqual(empty['parking'],[])
        self.assertIsNone(empty['gender_rates']['남성'])
        self.assertIsNone(empty['air']['value'])
    def test_invalid_percent(self):
        bad=XML.replace('<FEMALE_PPLTN_RATE>100','<FEMALE_PPLTN_RATE>101')
        self.assertIsNone(parse_citydata(bad.encode())['gender_rates']['여성'])

if __name__=='__main__': unittest.main()
