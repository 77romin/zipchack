import unittest
from unittest.mock import patch
from rent_api import service_keys, fetch_rents

class RentKeyTests(unittest.TestCase):
    def test_specific_keys_override_common(self):
        keys=service_keys({'DATA_GO_KR_SERVICE_KEY':'shared','DATA_GO_KR_APT_RENT_KEY':'apt','DATA_GO_KR_OFFI_RENT_KEY':' offi '})
        self.assertEqual(keys,{'아파트':'apt','연립다세대':'shared','단독다가구':'shared','오피스텔':'offi'})

    def test_missing_key_is_not_called(self):
        result={'rows':[],'total':0,'received':0,'skipped':0,'complete':True}
        with patch('rent_api.fetch_category',return_value=result) as fetch:
            data=fetch_rents('11140','202609',['아파트','오피스텔'],{'아파트':'apt-only'})
        fetch.assert_called_once_with('아파트','11140','202609','apt-only')
        self.assertIn('DATA_GO_KR_OFFI_RENT_KEY',data['statuses'][1]['error'])
        self.assertNotIn('apt-only',str(data))

    def test_each_service_receives_own_key(self):
        results=[{'rows':[],'total':0,'received':0,'skipped':0,'complete':True} for _ in range(2)]
        with patch('rent_api.fetch_category',side_effect=results) as fetch:
            fetch_rents('11140','202609',['아파트','오피스텔'],{'아파트':'a','오피스텔':'b'})
        self.assertEqual([call.args[3] for call in fetch.call_args_list],['a','b'])
