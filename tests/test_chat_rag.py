import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

class ChatRagTests(unittest.TestCase):
    def test_switch_and_mode_apply_to_search_and_preserve_conditions_on_failure(self):
        source="from chat_view import render_chat\nrender_chat(neighborhood={'legal_code':'1114016200','name':'신당동'})"
        turn={'conditions':{},'answer':'조건을 확인했어요.','asked':False,'stage':'collecting','result':None,'cache':{}}
        result={'answer':'문서 근거 [1]','citations':[],'mode':'mmr'}
        with patch('chat_view.run_chat_turn',return_value=turn),patch('chat_view.answer_question',return_value=result) as search:
            app=AppTest.from_string(source).run()
            app.chat_input[0].set_value('첫 질문').run();search.assert_not_called()
            app.checkbox(key='chat_use_rag').check().run()
            app.radio(key='chat_retrieval_mode').set_value('mmr').run()
            app.chat_input[0].set_value('동네 특징은?').run()
            search.assert_called_once_with('1114016200','동네 특징은?','mmr')
            self.assertEqual(app.session_state['housing_chat'][-1]['rag_result']['mode'],'mmr')
            search.side_effect=ValueError('private-key')
            app.chat_input[0].set_value('다음 질문').run()
            self.assertEqual(len(app.exception),0)
            self.assertIn('rag_error',app.session_state['housing_chat'][-1])
            self.assertNotIn('private-key',str(app.session_state['housing_chat']))
            app.radio(key='chat_retrieval_mode').set_value('similarity').run()
            search.side_effect=None
            app.chat_input[0].set_value('유사도 질문').run()
            self.assertEqual(search.call_args.args[-1],'similarity')

    def test_prompt_survives_map_triggered_rerun(self):
        from threading import Event
        release=Event();calls=[]
        def slow(message,*args,**kwargs):
            calls.append(message);release.wait(5)
            return {'conditions':{},'answer':'처리 완료','asked':False,'stage':'collecting','result':None,'cache':{}}
        with patch('chat_view.run_chat_turn',side_effect=slow):
            app=AppTest.from_string('from chat_view import render_chat\nrender_chat()').run()
            app.chat_input[0].set_value('지도 갱신 중 입력').run()
            app.run();app.run()
            self.assertEqual(calls,['지도 갱신 중 입력'])
            release.set();app.session_state['housing_job']['future'].result(timeout=5)
            app.run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(len(app.session_state['housing_chat']),2)
            self.assertNotIn('pending_housing_prompt',app.session_state)

    def test_reset_discards_late_background_reply(self):
        from threading import Event
        release=Event()
        def slow(*args,**kwargs):
            release.wait(5)
            return {'conditions':{'rent_max':70},'answer':'이전 요청 답변','asked':False,'stage':'collecting','result':None,'cache':{}}
        with patch('chat_view.run_chat_turn',side_effect=slow):
            app=AppTest.from_string('from chat_view import render_chat\nrender_chat()').run()
            app.chat_input[0].set_value('처리 중 초기화').run()
            future=app.session_state['housing_job']['future']
            app.button(key='reset_housing_chat').click().run()
            release.set();future.result(timeout=5);app.run()
            self.assertEqual(app.session_state['housing_chat'],[])
            self.assertEqual(app.session_state['conversation_conditions'],{})
            self.assertNotIn('housing_job',app.session_state)

    def test_job_merges_data_loaded_while_request_was_running(self):
        from concurrent.futures import Future
        turn={'conditions':{},'answer':'완료','asked':False,'stage':'collecting','result':None,'cache':{}}
        future=Future();future.set_result((turn,{'role':'assistant','content':'완료'},
            {'points':{'new':{'legal_code':'new'}},'residents':{'new':{'total':1}}},{}))
        app=AppTest.from_string('from chat_view import render_chat\nrender_chat()').run()
        app.session_state['neighborhood_locations']={'loaded_during_job':{}}
        app.session_state['resident_data']={'loaded_during_job':{}}
        app.session_state['housing_job']={'future':future,'prompt':'질문','history':[]}
        app.run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(set(app.session_state['resident_data']),{'new','loaded_during_job'})
        self.assertEqual(set(app.session_state['neighborhood_locations']),{'new','loaded_during_job'})
