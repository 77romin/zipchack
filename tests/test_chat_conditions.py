import unittest
from unittest.mock import Mock, patch
import requests
from chat_conditions import ConversationError, extract_patch, merge_conditions, next_question, map_conditions

class ChatTests(unittest.TestCase):
    def test_partial_update_and_zero(self):
        original = {'workplace':'시청', 'deal_type':'월세', 'deposit_max':1000, 'rent_max':70, 'preferences':{'bike':5}}
        result = merge_conditions(original, {'rent_max':60, 'preferences':{'park':0}})
        self.assertEqual(result['workplace'], '시청')
        self.assertEqual(result['preferences'], {'bike':5, 'park':0})
        self.assertEqual(original['rent_max'], 70)
        self.assertEqual(merge_conditions(result, {'deposit_max':0})['deposit_max'], 0)

    def test_deletion_and_contract_change(self):
        current = {'deal_type':'월세', 'deposit_max':1000, 'rent_max':70, 'preferences':{'bike':5}}
        result = merge_conditions(current, {'deal_type':'매매', 'preferences':{'bike':None}})
        self.assertNotIn('deposit_max', result)
        self.assertNotIn('rent_max', result)
        self.assertEqual(result['preferences'], {})
        self.assertNotIn('deal_type', merge_conditions(current, {'deal_type':None}))

    def test_bad_patches_rejected(self):
        for value in [{'rent_max':True}, {'commute_minutes':-2}, {'rent_max':float('nan')},
                      {'preferences':{'park':6}}, {'invented':'x'}, {'preferred_ages':[23]},
                      {'workplace':''}, {'deal_type':['월세']}]:
            with self.subTest(value=value):
                with self.assertRaises(ConversationError):
                    merge_conditions({}, value)

    def test_questions_and_mapping(self):
        self.assertIn('직장', next_question({}))
        current = {'workplace':'시청', 'deal_type':'월세', 'deposit_max':0, 'rent_max':70,
                   'commute_mode':'대중교통', 'commute_minutes':40}
        self.assertIsNone(next_question(current))
        self.assertEqual(map_conditions(current)['deposit_max'], 0)
        self.assertEqual(map_conditions(current)['preferences']['age'], 0)
        self.assertIsNone(map_conditions({**current, 'deal_type':'전세'}))

    def test_extract_context_and_json(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices':[{'message':{'content':'{"rent_max":60}'}}]}
        with patch('chat_conditions.requests.post', return_value=response) as post:
            self.assertEqual(extract_patch('60으로', {'rent_max':70}, [], 'secret-key'), {'rent_max':60})
            self.assertIn('70', post.call_args.kwargs['json']['messages'][1]['content'])
            self.assertEqual(post.call_count, 1)

    def test_failure_hides_key(self):
        with patch('chat_conditions.requests.post', side_effect=requests.Timeout('secret-key')):
            with self.assertRaises(ConversationError) as error:
                extract_patch('시청', {}, [], 'secret-key')
        self.assertNotIn('secret-key', str(error.exception))
        with patch('chat_conditions.requests.post') as post:
            with self.assertRaises(ConversationError): extract_patch('시청', {}, [], '')
            post.assert_not_called()

    def test_malformed_response(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices':[{'message':{'content':'not JSON'}}]}
        with patch('chat_conditions.requests.post', return_value=response):
            with self.assertRaises(ConversationError): extract_patch('시청', {}, [], 'test')

    def test_chat_ui_accumulates_and_resets(self):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=20).run()
        with patch('chat_view.extract_patch', return_value={'workplace':'시청', 'deal_type':'월세', 'deposit_max':1000}):
            app.chat_input[0].set_value('시청 근처 보증금 천').run()
        self.assertEqual(app.session_state['conversation_conditions']['deposit_max'], 1000)
        self.assertIsNone(app.session_state['housing_conditions'])
        with patch('chat_view.extract_patch', return_value={'rent_max':60, 'commute_mode':'자전거', 'commute_minutes':30}):
            app.chat_input[0].set_value('월세60 자전거30분').run()
        self.assertEqual(app.session_state['housing_conditions']['workplace'], '시청')
        self.assertEqual(app.session_state['housing_conditions']['rent_max'], 60)
        self.assertEqual(len(app.exception), 0)
        with patch('chat_view.extract_patch', side_effect=ConversationError('연결 실패')):
            app.chat_input[0].set_value('월세50').run()
        self.assertEqual(app.session_state['conversation_conditions']['rent_max'], 60)
        next(button for button in app.button if button.key == 'reset_housing_chat').click().run()
        self.assertEqual(app.session_state['conversation_conditions'], {})
        self.assertIsNone(app.session_state['housing_conditions'])
