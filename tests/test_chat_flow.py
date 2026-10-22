import unittest
from unittest.mock import patch
from chat_flow import collect_turn, is_finish_request

BASE = {'workplace':'서울 시청','deal_type':'월세','deposit_max':1000,'rent_max':70,
        'commute_mode':'대중교통','commute_minutes':40}

class ChatFlowTests(unittest.TestCase):
    def test_repeated_preference_question_regression(self):
        with patch('chat_flow.extract_patch', return_value=BASE):
            current, reply, asked, stage = collect_turn('시청 출근 월세70', {}, [], 'test')
        self.assertEqual(stage, 'preferences')
        self.assertTrue(asked)
        with patch('chat_flow.extract_patch', return_value={'preferences':{'park':3,'bike':3,'age':3}, 'preferred_ages':[20,30]}):
            current, reply, asked, stage = collect_turn('공원 따릉이 20~30대 선호', current, [], 'test', asked)
        self.assertNotIn('더 원하는 점이 있나요', reply)
        self.assertIn('20대·30대', reply)
        self.assertEqual(stage, 'waiting_for_data')
        with patch('chat_flow.extract_patch') as extract:
            final, reply, _, stage = collect_turn('없음. 알려줘', current, [], 'test', asked)
            extract.assert_not_called()
        self.assertEqual(final, current)
        self.assertEqual(final['preferences']['park'], 3)
        self.assertNotIn('더 원하는 점이 있나요', reply)
        self.assertIn('아직 조회할 수 없어요', reply)

    def test_finished_still_needs_required_information(self):
        result, reply, _, stage = collect_turn('추천해줘', {}, [], '')
        self.assertEqual(result, {})
        self.assertEqual(stage, 'collecting')
        self.assertIn('직장', reply)

    def test_finish_detection_does_not_hide_new_conditions(self):
        for message in ['없음. 알려줘', '없어요', '추천해줘', '없음, 추천해주세요']:
            self.assertTrue(is_finish_request(message))
        for message in ['', '공원은 없어도 돼', '없음. 월세는60으로', '월세 조건 지워줘']:
            self.assertFalse(is_finish_request(message))

    def test_preferences_already_present_skip_optional_question(self):
        with patch('chat_flow.extract_patch', return_value={}):
            _, reply, _, stage = collect_turn('글쎄', {**BASE,'preferences':{'park':3}}, [], 'test')
        self.assertNotEqual(stage, 'preferences')
        self.assertNotIn('더 원하는 점이 있나요', reply)

    def test_ui_finish_preserves_preferences(self):
        from pathlib import Path
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=20).run()
        with patch('chat_flow.extract_patch', return_value={**BASE, 'preferences':{'park':3,'bike':3},'preferred_ages':[20,30]}):
            app.chat_input[0].set_value('시청 출근 공원 따릉이 선호').run()
        with patch('chat_flow.extract_patch') as extract:
            app.chat_input[0].set_value('없음. 알려줘').run()
            extract.assert_not_called()
        self.assertEqual(app.session_state['chat_stage'], 'waiting_for_data')
        self.assertEqual(app.session_state['conversation_conditions']['preferred_ages'], [20,30])
        self.assertEqual(len(app.exception), 0)
        next(button for button in app.button if button.key=='reset_housing_chat').click().run()
        self.assertFalse(app.session_state['chat_optional_asked'])
