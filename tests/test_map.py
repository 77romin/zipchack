import unittest
from map_view import build_map_html

class MapTests(unittest.TestCase):
    def test_radius_units_and_workplace(self):
        html = build_map_html("public-key", {"latitude":37.5,"longitude":127.0}, 2.5)
        self.assertIn('"radius_m": 2500', html)
        self.assertIn('"workplace": true', html)
        self.assertIn("circle.getBounds()", html)

    def test_no_workplace(self):
        self.assertIn('"workplace": false', build_map_html("key"))

    def test_invalid_geometry(self):
        for radius in [0, 11, float("nan")]:
            with self.assertRaises(ValueError):
                build_map_html("key", radius_km=radius)
        with self.assertRaises(ValueError):
            build_map_html("key", {"latitude":float("nan"),"longitude":127})

    def test_key_cannot_escape_script_src(self):
        html = build_map_html('bad-key\"><script>')
        self.assertNotIn('appkey=bad-key\"><script>', html)

if __name__ == "__main__":
    unittest.main()
