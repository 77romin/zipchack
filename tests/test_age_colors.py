import unittest
from age_colors import age_composition

class AgeColorTests(unittest.TestCase):
    def rates(self,young,old):
        return {'20':young,'30':0,'60':old,'70':0,'80':0,'90':0,'100':0}
    def test_green_yellow_red_and_population_size_independence(self):
        self.assertEqual(age_composition(self.rates(80,0))['color'],'#16a34a')
        self.assertEqual(age_composition(self.rates(25,25))['color'],'#facc15')
        self.assertEqual(age_composition(self.rates(0,80))['color'],'#dc2626')
        self.assertEqual(age_composition(self.rates(40,20))['color'],age_composition(self.rates(20,10))['color'])
    def test_missing_and_zero_are_not_colored(self):
        self.assertIsNone(age_composition({}))
        self.assertIsNone(age_composition(self.rates(0,0)))
        rates=self.rates(20,30);rates['100']=None
        self.assertIsNone(age_composition(rates))
