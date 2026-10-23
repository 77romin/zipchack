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
