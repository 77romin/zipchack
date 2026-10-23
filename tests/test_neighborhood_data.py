import csv,hashlib,json,tempfile,unittest,zipfile
from dataclasses import asdict
from io import BytesIO
from unittest.mock import Mock,patch
from neighborhood_data import parse_codes,load_neighborhoods,neighborhood_sources,wiki_sources
from wiki_documents import parse_page,collect

class NeighborhoodDataTests(unittest.TestCase):
    def archive(self,text):
        buffer=BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('codes.txt',text.encode('cp949'))
        return buffer.getvalue()

    def test_official_parser_excludes_cancelled_and_aggregate_rows(self):
        header='법정동코드\t법정동명\t폐지여부\n'
        text=header+'1100000000\t서울특별시\t존재\n1111000000\t서울특별시 종로구\t존재\n1111010100\t서울특별시 종로구 청운동\t존재\n1111010200\t서울특별시 종로구 신교동\t폐지\n2611010100\t부산광역시 중구 영주동\t존재\n'
        rows=parse_codes(self.archive(text))
        self.assertEqual([r['code'] for r in rows],['1111010100'])
        with self.assertRaises(ValueError):parse_codes(self.archive(text+'1111010100\t서울특별시 종로구 청운동\t존재\n'))

    def payload(self,text='청운동은 서울특별시 종로구의 법정동이다.'):
        return {'query':{'pages':{'12':{'ns':0,'pageid':12,'title':'청운동','extract':text,'revisions':[{'revid':123,'timestamp':'2026-01-01T00:00:00Z'}]}}}}

    def test_short_own_document_included_and_wrong_region_rejected(self):
        item={'code':'1111010100','district':'종로구','name':'청운동'}
        source=parse_page(self.payload(),item,'청운동')
        self.assertEqual(source.item_id,item['code'])
        self.assertTrue(source.source_url.endswith('oldid=123'))
        self.assertEqual(source.license,'CC BY-SA 4.0')
        with self.assertRaises(ValueError):parse_page(self.payload('청운동은 다른 지역의 동이다.'),item,'청운동')
        payload=self.payload();payload['query']['pages']['12']['pageprops']={'disambiguation':''}
        with self.assertRaises(ValueError):parse_page(payload,item,'청운동')

    def test_cache_reuses_without_http_and_keeps_revision(self):
        item={'code':'1111010100','district':'종로구','name':'청운동'}
        response=Mock();response.json.return_value=self.payload()
        with tempfile.TemporaryDirectory() as folder,patch('wiki_documents.requests.get',return_value=response) as get:
            first,hit=collect(item,'청운동',folder,contact='test@example.org')
            second,cached=collect(item,'청운동',folder,contact='test@example.org')
            self.assertFalse(hit);self.assertTrue(cached)
            self.assertEqual(asdict(first),asdict(second));self.assertEqual(get.call_count,1)

    def test_real_snapshot_ids_and_external_links(self):
        rows,manifest=load_neighborhoods()
        self.assertGreaterEqual(len(rows),100)
        self.assertEqual(len({r['district'] for r in rows}),25)
        sources=list(neighborhood_sources())
        self.assertEqual(len(sources),len(rows))
        self.assertTrue(all(s.kind=='metadata' for s in sources))
        external=list(wiki_sources())
        self.assertEqual(len(external),5)
        self.assertTrue(all(s.revision_id and s.attribution for s in external))

    def test_failed_refresh_preserves_valid_cache(self):
        item={'code':'1111010100','district':'종로구','name':'청운동'}
        response=Mock();response.json.return_value=self.payload()
        with tempfile.TemporaryDirectory() as folder,patch('wiki_documents.requests.get',return_value=response):
            first,_=collect(item,'청운동',folder,contact='test@example.org')
            response.json.return_value=self.payload('다른 지역의 동네입니다.')
            with self.assertRaises(ValueError):collect(item,'청운동',folder,contact='test@example.org',refresh=True)
            cached,hit=collect(item,'청운동',folder,contact='test@example.org')
            self.assertTrue(hit);self.assertEqual(asdict(first),asdict(cached))
