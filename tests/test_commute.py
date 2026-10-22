import unittest
from unittest.mock import Mock,patch
from urllib.parse import unquote
import requests
from commute import route_url,record_key,make_record,assess_record,address_origin_candidates,resolve_building,commute_reply,MODES
from test_housing_candidates import result,CONDITIONS

ORIGIN={'name':'중구 신당동','latitude':37.56,'longitude':127.01,'origin_kind':'neighborhood'}
DEST={'name':'서울시청','latitude':37.5665,'longitude':126.978}
DEPART='2026-10-23 08:30'

class CommuteTests(unittest.TestCase):
    def test_modes_url_direction_and_escaping(self):
        for mode,token in MODES.items():
            url=route_url(ORIGIN,DEST,mode)
            self.assertIn('/link/by/'+token+'/',url)
            self.assertLess(unquote(url).index('중구 신당동'),unquote(url).index('서울시청'))
        url=route_url({**ORIGIN,'name':'a/b,?x=<tag>'},DEST,'대중교통')
        self.assertIn('a%2Fb%2C%3Fx%3D%3Ctag%3E',url)
        with self.assertRaises(ValueError):route_url({**ORIGIN,'latitude':float('nan')},DEST,'도보')

    def test_no_confirmation_or_zero_is_not_verified(self):
        for minutes,confirmed in [(None,True),(0,True),(True,True),(40,False)]:
            with self.assertRaises(ValueError):make_record(ORIGIN,DEST,'대중교통',DEPART,minutes,confirmed)

    def test_limit_boundary_and_recalculation(self):
        record=make_record(ORIGIN,DEST,'대중교통',DEPART,40,True)
        self.assertEqual(record['method'],'user_reported')
        self.assertEqual(assess_record(record,ORIGIN,DEST,'대중교통',DEPART,40)['state'],'within')
        self.assertEqual(assess_record(record,ORIGIN,DEST,'대중교통',DEPART,39)['state'],'over')

    def test_endpoint_mode_time_and_origin_kind_isolation(self):
        record=make_record(ORIGIN,DEST,'대중교통',DEPART,40,True)
        for origin,destination,mode,departure in [
            ({**ORIGIN,'origin_kind':'building_address'},DEST,'대중교통',DEPART),
            (ORIGIN,{**DEST,'latitude':37.57},'대중교통',DEPART),
            (ORIGIN,DEST,'자전거',DEPART),(ORIGIN,DEST,'대중교통','2026-10-24 08:30')]:
            self.assertEqual(assess_record(record,origin,destination,mode,departure,40)['state'],'unknown')

    def test_precise_building_candidates_exclude_masked_and_detached(self):
        data=result()
        data['rows'][0].update(jibun='123-4',district_code='11140')
        data['rows'][1].update(jibun='12*',district_code='11140')
        self.assertEqual(len(address_origin_candidates(data,CONDITIONS,'신당동')),1)
        data['rows'][0]['category']='단독다가구'
        self.assertEqual(address_origin_candidates(data,CONDITIONS,'신당동'),[])

    def test_building_geocode_must_match_full_parcel(self):
        candidate={'name':'테스트','address':'서울특별시 중구 신당동 123-4','district':'중구','dong':'신당동','jibun':'123-4'}
        address={'region_1depth_name':'서울','region_2depth_name':'중구','region_3depth_name':'신당동','main_address_no':'123','sub_address_no':'4','mountain_yn':'N'}
        document={'address_type':'REGION_ADDR','address':address,'y':'37.56','x':'127.01'}
        response=Mock(); response.json.return_value={'documents':[document]}
        with patch('commute.requests.get',return_value=response):
            self.assertEqual(resolve_building(candidate,'test')['origin_kind'],'building_address')
            document['address_type']='REGION'
            with self.assertRaises(ValueError):resolve_building(candidate,'test')
        with patch('commute.requests.get',side_effect=requests.Timeout('secret-key')):
            with self.assertRaises(ValueError) as error:resolve_building(candidate,'secret-key')
            self.assertNotIn('secret-key',str(error.exception))

    def test_chat_reports_user_source_and_workplace_change(self):
        record=make_record(ORIGIN,DEST,'대중교통',DEPART,40,True)
        context={'destination':DEST,'workplace_query':CONDITIONS['workplace'],'points':{'11140:신당동':ORIGIN},
                 'records':{record_key(ORIGIN,DEST,'대중교통',DEPART):record},'departure':DEPART}
        reply=commute_reply(result(),CONDITIONS,context)
        self.assertIn('희망시간 이내',reply)
        self.assertIn('자동 검증값이 아니에요',reply)
        self.assertIn('대표점',reply)
        self.assertIn('선택해야',commute_reply(result(),{**CONDITIONS,'workplace':'강남역'},context))

    def test_ui_requires_confirm_and_keeps_modes_separate(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_string("""import streamlit as st
from commute_view import render_commute
origin={'name':'중구 신당동','latitude':37.56,'longitude':127.01,'dong':'신당동','district_code':'11140'}
destination={'name':'서울시청','latitude':37.5665,'longitude':126.978}
render_commute(origin,destination,{'workplace':'서울시청','commute_mode':'대중교통','commute_minutes':40},None,{'11140:신당동':origin})
""").run()
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=='사용자 확인 통근시간 저장').click().run()
        self.assertEqual(app.session_state['commute_records'],{})
        app.number_input[0].set_value(35)
        app.checkbox[0].check()
        next(b for b in app.button if b.label=='사용자 확인 통근시간 저장').click().run()
        self.assertEqual(len(app.session_state['commute_records']),1)
        self.assertEqual(next(iter(app.session_state['commute_records'].values()))['minutes'],35)
        next(w for w in app.selectbox if w.label=='기록할 이동수단').select('자전거').run()
        self.assertIsNone(app.number_input[0].value)
        self.assertFalse(app.checkbox[0].value)
        self.assertEqual(len(app.exception),0)
