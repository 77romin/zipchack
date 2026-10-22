import tempfile,unittest
from unittest.mock import Mock,patch
from rag_index import Source
from rag_prepare import validate_queries,validate_selection,prepare,WikiSearch

class PrepareTests(unittest.TestCase):
    def test_structured_outputs_reject_invalid_ids_and_duplicates(self):
        self.assertEqual(validate_queries({'queries':['공원','공원']}),['공원'])
        for data in [{'queries':[]},{'queries':['x'*101]},{}]:
            with self.assertRaises(ValueError):validate_queries(data)
        candidates=[{'id':'1'}]
        for selected in [[{'id':'2','reason':'이유'}],[{'id':'1','reason':''}], [{'id':'1','reason':'이유'}]*2]:
            with self.assertRaises(ValueError):validate_selection({'selected':selected},candidates)

    def test_own_document_indexed_even_when_p1_fails(self):
        item={'code':'1144010200','name':'공덕동','district':'마포구','full_name':'서울특별시 마포구 공덕동'}
        own=Source(item['code'],'wikipedia:1','공덕동','짧은 본문','https://example.org','2026')
        index=Mock()
        with tempfile.TemporaryDirectory() as folder,patch('rag_prepare.collect',return_value=(own,False)),patch('rag_prepare.ask',side_effect=ValueError('실패')):
            with self.assertRaises(ValueError):prepare(item,'질문','key',folder,index)
        index.put.assert_called_once_with(own)

    def test_search_cache_does_not_repeat_http(self):
        response=Mock();response.json.return_value={'query':{'search':[{'pageid':1,'title':'공덕역','snippet':'공덕동'}]}}
        with tempfile.TemporaryDirectory() as folder,patch('rag_prepare.requests.get',return_value=response) as get,patch('rag_prepare.time.sleep'):
            wiki=WikiSearch(folder)
            self.assertEqual(wiki.search('공덕동'),wiki.search('공덕동'))
            self.assertEqual(get.call_count,1)

    def test_other_region_body_is_not_attached(self):
        with tempfile.TemporaryDirectory() as folder:
            wiki=WikiSearch(folder)
            wiki.query=Mock(return_value={'query':{'pages':{'1':{'pageid':1,'ns':0,'title':'다른 지역','extract':'다른 지역의 공원'}}}})
            self.assertIsNone(wiki.document({'id':'1'},{'name':'공덕동','district':'마포구'}))
