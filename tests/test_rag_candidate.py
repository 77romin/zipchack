import unittest
from unittest.mock import patch
from rag_candidate import candidate_sources,target_candidate


class CandidateEvidenceTests(unittest.TestCase):
    def test_exact_scope_dates_and_missing_are_preserved(self):
        point={'legal_code':'1114016200','dong':'신당동','latitude':37.56,'longitude':127.0}
        context={'month':'202609','bikes':{'source_url':'https://data.seoul.go.kr/','source_updated_at':'2026-06-01',
            'stations':[dict(point,id='near',name='가까운 대여소'),dict(point,id='far',name='먼 대여소',latitude=37.8)]},
            'residents':{'1114016200:202609':{'code':'wrong','month':'202609','source_url':'https://data.go.kr/'}}}
        docs=list(candidate_sources(point,context))
        self.assertEqual(len(docs),1)
        self.assertIn('가까운 대여소',docs[0].text)
        self.assertNotIn('먼 대여소',docs[0].text)
        self.assertEqual(docs[0].observed_at,'2026-06-01')
        self.assertIn('실시간 재고가 아니',docs[0].text)
        self.assertEqual(list(candidate_sources(point,{})),[])

    def test_recommendation_target_replaces_unrelated_map_selection(self):
        from chat_view import process_request
        point={'legal_code':'1114016200'}
        turn={'conditions':{},'answer':'추천','result':None}
        runner=lambda *args,**kwargs:turn
        calls=[]
        with patch('chat_view.recommendation_rows',return_value=[{'point':None},{'point':point}]):
            result=process_request('질문',{},[],{},None,None,{},False,True,'mmr','different-map-code',
                'key',{},'model',{},runner,lambda *args:self.fail('지도 동네로 검색하면 안 됨'),
                lambda *args:calls.append(args) or {'answer':'근거'})
        self.assertEqual(calls[0],(point,{},'질문','mmr'))
        self.assertIn('rag_result',result[1])
        self.assertEqual(target_candidate([],point),point)
