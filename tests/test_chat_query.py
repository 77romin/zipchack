import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from pathlib import Path
from chat_query import run_chat_turn,signature,refresh_requested
from chat_conditions import validate_patch,ConversationError
from rent_api import RentDataError
from test_housing_candidates import result,CONDITIONS

FULL={**CONDITIONS,'district':'중구','deal_month':'202609','housing_types':['오피스텔']}

class ChatQueryTests(unittest.TestCase):
    def test_query_schema_and_relative_month(self):
        month=(datetime.now(timezone(timedelta(hours=9))).replace(day=1)-timedelta(days=1)).strftime('%Y%m')
        self.assertEqual(validate_patch({'deal_month':'previous_month'})['deal_month'],month)
        self.assertEqual(validate_patch({'housing_types':['오피스텔','오피스텔']})['housing_types'],['오피스텔'])
        for value in [{'district':'서울 전체'},{'deal_month':'202613'},{'housing_types':['원룸']},{'housing_types':[]}]:
            with self.assertRaises(ConversationError):validate_patch(value)

    def test_missing_scope_questions_and_no_fetch(self):
        with patch('chat_query.fetch_rents') as fetch:
            turn=run_chat_turn('추천해줘',CONDITIONS,[],'',{},True)
            self.assertEqual(turn['stage'],'query_conditions')
            self.assertIn('자치구',turn['answer'])
            with patch('chat_flow.extract_patch',return_value={'district':'중구'}):
                turn=run_chat_turn('중구',CONDITIONS,[],'test',{},True)
            self.assertIn('계약월',turn['answer'])
            fetch.assert_not_called()

    def test_same_scope_budget_change_reuses(self):
        with patch('chat_flow.extract_patch',return_value={'rent_max':60}),patch('chat_query.fetch_rents') as fetch:
            turn=run_chat_turn('월세60',FULL,[],'test',{},True,rental_result=result())
        fetch.assert_not_called()
        self.assertEqual(turn['conditions']['rent_max'],60)
        self.assertIn('다시 적용',turn['answer'])

    def test_scope_change_fetch_and_bounded_cache(self):
        cache={str(i):result() for i in range(5)}
        with patch('chat_query.fetch_rents',return_value=result()) as fetch:
            turn=run_chat_turn('추천해줘',FULL,[],'',{'오피스텔':'test'},True,cache=cache)
        fetch.assert_called_once_with('11140','202609',['오피스텔'],{'오피스텔':'test'})
        self.assertEqual(turn['stage'],'candidates')
        self.assertEqual(len(turn['cache']),5)
        self.assertIn(signature(FULL),turn['cache'])
        with patch('chat_query.fetch_rents') as fetch:
            reused=run_chat_turn('추천해줘',FULL,[],'',{},True,cache=turn['cache'])
        fetch.assert_not_called()
        self.assertIn('저장된',reused['answer'])

    def test_explicit_refresh_and_failure_preserve_conditions(self):
        self.assertTrue(refresh_requested('다시 조회해줘'))
        with patch('chat_flow.extract_patch') as extract,patch('chat_query.fetch_rents',side_effect=RentDataError('연결 실패')) as fetch:
            turn=run_chat_turn('다시 조회해줘',FULL,[],'',{},True,rental_result=result())
        extract.assert_not_called(); self.assertEqual(fetch.call_count,1)
        self.assertEqual(turn['conditions'],FULL)
        self.assertIsNone(turn['result'])
        self.assertEqual(turn['stage'],'query_failed')

    def test_partial_or_deleted_scope_never_uses_old_scope(self):
        for patch_data in [{'district':'마포구','deal_month':None},{'district':None,'deal_month':None,'housing_types':None}]:
            with patch('chat_flow.extract_patch',return_value=patch_data),patch('chat_query.fetch_rents') as fetch:
                turn=run_chat_turn('조회 조건 수정',FULL,[],'test',{},True,rental_result=result())
            fetch.assert_not_called()
            self.assertIsNone(turn['result'])
            self.assertEqual(turn['stage'],'query_conditions')
            self.assertNotIn('신당동',turn['answer'])

    def test_legacy_manual_scope_and_purchase(self):
        with patch('chat_query.fetch_rents') as fetch:
            turn=run_chat_turn('추천해줘',CONDITIONS,[],'',{},True,rental_result=result())
            self.assertIn('신당동',turn['answer'])
            turn=run_chat_turn('추천해줘',{**FULL,'deal_type':'매매','purchase_max':10000},[],'',{},True)
        fetch.assert_not_called()
        self.assertEqual(turn['stage'],'unsupported')

    def test_ui_auto_query_does_not_repeat_on_rerun(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']=CONDITIONS
        app.session_state['chat_optional_asked']=True
        with patch('chat_flow.extract_patch',return_value={'district':'중구','deal_month':'202609','housing_types':['오피스텔']}),patch('chat_query.fetch_rents',return_value=result()) as fetch:
            app.chat_input[0].set_value('중구 지난달 오피스텔').run()
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(app.session_state['chat_stage'],'candidates')
            self.assertIn('신당동',app.session_state['housing_chat'][-1]['content'])
            app.run()
            self.assertEqual(fetch.call_count,1)
        self.assertEqual(len(app.exception),0)
