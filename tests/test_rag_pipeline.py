import unittest
from unittest.mock import Mock,patch
from rag_pipeline import validate_answer,build_graph,run

class PipelineTests(unittest.TestCase):
    def evidence(self):
        return [{'citation':1,'id':'meta','text':'공덕동은 마포구의 법정동',
            'metadata':{'kind':'metadata','document_id':'legal','title':'공덕동','source_url':'https://example.org','observed_at':'2026'}}]

    def test_citations_validate_and_only_used_sources_displayed(self):
        e=self.evidence()
        result=validate_answer({'answer':'마포구입니다. [1]','abstained':False},e)
        self.assertEqual(result['citations'][0]['numbers'],[1])
        for data in [{'answer':'정답 [2]','abstained':False},{'answer':'정답','abstained':False}, {'answer':'https://made-up.org [1]','abstained':False}]:
            with self.assertRaises(ValueError):validate_answer(data,e)
        self.assertEqual(validate_answer({'answer':'제공 자료로 확인할 수 없습니다.','abstained':True},e)['citations'],[])

    def test_actual_compiled_graph_order_and_evidence_passed(self):
        retrieval={'evidence':self.evidence(),'timings':{'total_ms':2}}
        call=Mock(return_value={'answer':'마포구입니다. [1]','abstained':False})
        with patch('rag_pipeline.retrieve',return_value=retrieval) as search:
            graph=build_graph(Mock(),'key',answer_call=call)
            result=run(graph,'1144010200','어느 구?',mode='mmr')
        self.assertEqual(result['trace'],['retrieve','generate'])
        self.assertEqual(call.call_args.args[1]['evidence'][0]['text'],self.evidence()[0]['text'])
        self.assertEqual(search.call_args.args[3],'mmr')
        self.assertGreaterEqual(result['timings']['end_to_end_ms'],0)

    def test_invalid_citation_fails_graph_without_answer(self):
        with patch('rag_pipeline.retrieve',return_value={'evidence':self.evidence(),'timings':{'total_ms':1}}):
            graph=build_graph(Mock(),'key',answer_call=lambda *a:{'answer':'정답 [99]','abstained':False})
            with self.assertRaises(ValueError):run(graph,'dong','질문')
