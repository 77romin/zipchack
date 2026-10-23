import unittest
from unittest.mock import patch
from app_startup import missing_dependencies,check_runtime

class StartupTests(unittest.TestCase):
    def test_missing_dependencies_are_named_before_app_imports(self):
        with patch('app_startup.importlib.util.find_spec',side_effect=lambda name:None if name=='langchain_text_splitters' else object()):
            self.assertEqual(missing_dependencies(),['langchain-text-splitters'])

    def test_wrong_environment_stops_with_instruction(self):
        with patch('app_startup.missing_dependencies',return_value=['langchain-text-splitters']),patch('streamlit.error') as error,patch('streamlit.write'),patch('streamlit.caption'),patch('streamlit.code') as code,patch('streamlit.stop',side_effect=RuntimeError('stopped')):
            with self.assertRaises(RuntimeError):check_runtime()
            error.assert_called_once();self.assertIn('run.sh',code.call_args.args[0])
