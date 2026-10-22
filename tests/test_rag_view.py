import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

SOURCE='''import streamlit as st
from rag_view import render_rag
render_rag()
'''
class RagViewTests(unittest.TestCase):
    def result(self):
        return {'answer':'공덕동은 마포구입니다. [1]','abstained':False,'mode':'mmr',
            'citations':[{'numbers':[1],'title':'공덕동','kind':'metadata','source_url':'https://example.org','observed_at':'2026'}]}

    def test_answer_history_isolated_modes_and_clear(self):
        app=AppTest.from_string(SOURCE,default_timeout=20).run()
        app.selectbox(key='rag_item').set_value('1144010200').run()
        app.radio(key='rag_mode').set_value('mmr').run()
        app.text_input(key='rag_question').set_value('어느 구인가요?')
        with patch('rag_view.answer_question',return_value=self.result()) as call:
            next(b for b in app.button if b.label=='근거로 답변받기').click().run()
            call.assert_called_once_with('1144010200','어느 구인가요?','mmr')
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.session_state['rag_histories']['1144010200']),1)
        app.selectbox(key='rag_item').set_value('1114016200').run()
        self.assertFalse(any('공덕동은 마포구' in x.value for x in app.markdown))
        app.selectbox(key='rag_item').set_value('1144010200').run()
        self.assertTrue(any('공덕동은 마포구' in x.value for x in app.markdown))
        app.button(key='rag_clear').click().run()
        self.assertEqual(app.session_state['rag_histories']['1144010200'],[])

    def test_error_hides_private_details_and_does_not_save_failed_turn(self):
        app=AppTest.from_string(SOURCE,default_timeout=20).run()
        app.text_input(key='rag_question').set_value('질문')
        with patch('rag_view.answer_question',side_effect=ValueError('private-api-key')):
            next(b for b in app.button if b.label=='근거로 답변받기').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(any('private-api-key' in x.value for x in app.warning))
        self.assertEqual(sum(map(len,app.session_state['rag_histories'].values())),0)
