import unittest
from unittest.mock import Mock
from scripts.check_connections import probe

class ConnectionProbeTests(unittest.TestCase):
    def test_missing_key_is_not_a_network_failure(self):
        call=Mock()
        self.assertEqual(probe('residents','',call)['status'],'missing_key')
        call.assert_not_called()

    def test_success_report_does_not_store_key_or_raw_data(self):
        report=probe('parks','secret-key',lambda key:{'parks':[{'private':'excluded'}]})
        self.assertEqual(report['count'],1)
        self.assertEqual(report['status'],'success')
        self.assertNotIn('secret-key',str(report))
        self.assertNotIn('excluded',str(report))

    def test_failed_is_not_zero_results(self):
        report=probe('citydata','test',Mock(side_effect=ValueError('연결 시간 초과')))
        self.assertEqual(report['status'],'failed')
        self.assertNotIn('count',report)
