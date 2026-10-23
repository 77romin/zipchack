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
