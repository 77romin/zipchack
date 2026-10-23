import unittest
from boundary_data import bundled_boundaries
from neighborhood_data import load_neighborhoods
from map_view import build_map_html

class BoundaryDataTests(unittest.TestCase):
    def test_all_boundaries_match_current_legal_codes(self):
        boundaries=bundled_boundaries()
        self.assertEqual(len(boundaries),467)
        self.assertEqual(set(boundaries),{r['code'] for r in load_neighborhoods()[0]})

    def test_bicycle_overlay_and_no_fake_age_circle(self):
        html=build_map_html('key')
        self.assertIn('icon.innerHTML',html)
        self.assertIn('background:#15803d',html)
        self.assertIn('content:icon',html)
        self.assertNotIn('radius:350',html)
        self.assertNotIn('radius:500',html)

    def test_population_cache_merges_and_restores_age_keys(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from boundary_data import save_population_snapshot,population_snapshot
        with tempfile.TemporaryDirectory() as directory,patch('boundary_data.ROOT',Path(directory)):
            first={'code':'1114016200','month':'202609','ages':{20:12},'total':12}
            second={'code':'1117010100','month':'202609','ages':{30:15},'total':15}
            save_population_snapshot('202609',{'a':first})
            save_population_snapshot('202609',{'b':second})
            cached=population_snapshot('202609')
            self.assertEqual(set(cached),{first['code'],second['code']})
            self.assertEqual(cached[first['code']]['ages'][20],12)
            self.assertEqual(population_snapshot('202608'),{})
            with self.assertRaises(ValueError):save_population_snapshot('../bad',{})
