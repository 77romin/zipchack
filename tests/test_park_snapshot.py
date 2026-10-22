import unittest
import json,hashlib
from pathlib import Path
from park_data import load_parks,bundled_parks

class ParkSnapshotTests(unittest.TestCase):
    def test_wgs84_columns_do_not_use_grs80(self):
        text='공원명,X좌표(GRS80TM),Y좌표(GRS80TM),X좌표(WGS84),Y좌표(WGS84)\n테스트공원,198364,450395,126.9903773,37.5501402'
        row=load_parks(text.encode('cp949'),'official.csv')['parks'][0]
        self.assertEqual(row['longitude'],126.9903773)
        self.assertEqual(row['latitude'],37.5501402)
        with self.assertRaises(ValueError):
            load_parks('공원명,X좌표(GRS80TM),Y좌표(GRS80TM)\n공원,198364,450395'.encode(),'wrong.csv')

    def test_real_snapshot_integrity_and_provenance(self):
        folder=Path(__file__).resolve().parents[1]/'data'
        manifest=json.loads((folder/'parks_seoul.source.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256((folder/'parks_seoul.csv').read_bytes()).hexdigest(),manifest['normalized_sha256'])
        data=bundled_parks()
        self.assertEqual(len(data['parks']),manifest['row_count'])
        self.assertEqual(data['source_updated_at'],manifest['dataset_updated_at'])
        self.assertIn('API 실조회 아님',data['origin'])
        self.assertTrue(any(row['name']=='남산공원' for row in data['parks']))
