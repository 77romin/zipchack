import unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from streamlit.testing.v1 import AppTest
from rag_index import Source
from rag_prepare import prepare


class RagControlsTests(unittest.TestCase):
    def test_top_k_reaches_actual_ui_call(self):
        app=AppTest.from_string('from rag_view import render_rag\nrender_rag()').run()
        app.number_input(key='rag_top_k').set_value(1).run()
        app.text_input(key='rag_question').set_value('질문')
        with patch('rag_view.answer_question',return_value={'answer':'근거 [1]','citations':[]}) as call:
            next(b for b in app.button if b.label=='근거로 답변받기').click().run()
        self.assertEqual(call.call_args.kwargs,{'k':1})
        self.assertFalse(app.exception)

    def test_same_question_rehydrates_index_without_ai_or_http(self):
        item={'code':'1144010200','name':'공덕동','district':'마포구','full_name':'서울특별시 마포구 공덕동'}
        own=Source(item['code'],'wikipedia:1','공덕동','본문','https://ko.wikipedia.org/','2026')
        with tempfile.TemporaryDirectory() as folder,patch('rag_prepare.collect',return_value=(own,True)) as collect,patch('rag_prepare.ask',return_value={'queries':['공덕']} ) as ask,patch('rag_prepare.WikiSearch') as wiki:
            wiki.return_value.search.return_value=[];wiki.return_value.requests=0
            first=prepare(item,'질문','key',folder,Mock(put=Mock(return_value={'chunks':1,'embedded':0,'removed':0})))
            other=Mock(put_many=Mock(return_value=[{'chunks':1,'embedded':0,'removed':0}]));second=prepare(item,'질문','key',folder,other)
            self.assertFalse(first['question_cache_hit']);self.assertTrue(second['question_cache_hit'])
            self.assertEqual(second['collection_requests'],0)
            self.assertEqual(ask.call_count,1);self.assertEqual(collect.call_count,1)
            other.put_many.assert_called_once_with([own])

    def test_safe_error_categories_and_source_type(self):
        from rag_view import safe_error,source_kind
        self.assertIn('GMS_KEY가 없습니다',safe_error(ValueError('GMS_KEY')))
        self.assertIn('색인이 없습니다',safe_error(ValueError('색인이 없습니다')))
        self.assertNotIn('secret',safe_error(ValueError('secret')))
        self.assertEqual(source_kind({'kind':'external','source_url':'https://ko.wikipedia.org/w/'}),'위키백과')

    def test_wiki_without_contact_never_sends_http(self):
        from wiki_transport import get
        with patch('wiki_transport.requests.get') as http:
            with self.assertRaises(ValueError):get('https://ko.wikipedia.org/w/api.php',headers={'User-Agent':'Zipchack/0.1 (local educational RAG project)'})
            http.assert_not_called()

    def test_abstention_is_readable_and_alternate_citation_is_validated(self):
        from rag_pipeline import validate_answer
        evidence=[{'citation':1,'metadata':{'kind':'metadata','document_id':'d','source_url':'https://example.org','title':'동네','observed_at':'2026'}}]
        self.assertIn('확인할 수 없어',validate_answer({'answer':'abstained=true','abstained':True},evidence)['answer'])
        result=validate_answer({'answer':'확인 불가 [근거번호: 1]','abstained':True},evidence)
        self.assertEqual(result['citations'][0]['numbers'],[1])
        with self.assertRaises(ValueError):validate_answer({'answer':'확인 불가 [근거번호: 9]','abstained':True},evidence)
