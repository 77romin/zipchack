import unittest
from unittest.mock import patch
from recommendations import prepare_candidates,recommendation_rows
from chat_query import run_chat_turn

C={'district':'중구','deal_month':'202609','housing_types':['오피스텔'],'deal_type':'월세','deposit_max':1000,'rent_max':70,'preferences':{'park':3}}
P={'latitude':37.56,'longitude':127.,'legal_code':'1114016200'}
Q={'latitude':37.57,'longitude':127.,'legal_code':'1114016500'}

def result():
    def row(dong,rent):return {'dong':dong,'monthly_rent':rent,'deposit':1000,'deal_type':'월세','category':'오피스텔','contract_date':'2026-09-01','source_url':'https://www.data.go.kr/example'}
    return {'district_code':'11140','month':'202609','queried_at':'test','statuses':[{'category':'오피스텔','complete':True,'error':None,'skipped':0}],'rows':[row('신당동',60),row('황학동',70)]}

def context():
    return {'month':'202609','points':{'11140:신당동':P,'11140:황학동':Q},'residents':{},'parks':{'parks':[P],'skipped':0},'bikes':None}

class RecommendationTests(unittest.TestCase):
    def test_budget_and_weights_change_shared_pin_ranking(self):
        rows=recommendation_rows(result(),C,context())
        self.assertEqual(rows[0]['dong'],'신당동');self.assertEqual(rows[0]['label'],'1')
        self.assertEqual(len(recommendation_rows(result(),{**C,'rent_max':60},context())),1)
        ctx=context();ctx['bikes']={'stations':[Q],'skipped':0}
        changed=recommendation_rows(result(),{**C,'preferences':{'bike':5,'park':0}},ctx)
        self.assertEqual(changed[0]['dong'],'황학동')
        self.assertTrue(all(r['label']=='후보' for r in recommendation_rows(result(),{**C,'preferences':{}},ctx)))

    def test_unknown_is_not_ranked_and_source_limit_is_explicit(self):
        ctx=context();ctx['parks']['skipped']=1
        rows=recommendation_rows(result(),C,ctx)
        self.assertEqual(rows[0]['label'],'참고 1');self.assertIsNone(rows[0]['rank'])
        self.assertTrue(rows[0]['issues'])
        missing=recommendation_rows(result(),{**C,'preferences':{'age':3},'preferred_ages':[20,30]},ctx)
        self.assertTrue(all(r['label']=='후보' for r in missing))
        partial=result();partial['statuses'][0]['complete']=False
        self.assertTrue(all(r['label']=='후보' for r in recommendation_rows(partial,C,context())))
        self.assertEqual(recommendation_rows(None,C,context()),[])

    def test_automatic_location_and_age_cache(self):
        conditions={**C,'preferences':{'age':3},'preferred_ages':[20]}
        resident={'code':P['legal_code'],'month':'202609','total':100,'ages':{20:50}}
        failures={}
        with patch('recommendations.resolve_neighborhood',side_effect=[P,ValueError('private')]) as locate,patch('recommendations.fetch_residents',return_value=resident) as population:
            prepared=prepare_candidates(result(),conditions,{'points':{},'residents':{},'month':'202609'},failures)
            self.assertEqual(locate.call_count,2);population.assert_called_once()
            prepare_candidates(result(),conditions,prepared,failures)
            self.assertEqual(locate.call_count,2);self.assertEqual(population.call_count,1)
            self.assertIn('11140:신당동',prepared['points'])
            self.assertIn('point:11140:황학동',failures)

    def test_turn_prepares_after_fetch_and_reuses_after_budget_change(self):
        data=result();ctx=context()
        with patch('chat_query.fetch_rents',return_value=data) as fetch:
            prepare=unittest.mock.Mock(return_value=ctx)
            first=run_chat_turn('추천해줘',C,[],'',{},prepare_context=prepare)
            prepare.assert_called_once();fetch.assert_called_once()
            self.assertIn('지도와 함께',first['answer']);self.assertIn('신당동 · 1위',first['answer'])
        with patch('chat_flow.extract_patch',return_value={'rent_max':60}),patch('chat_query.fetch_rents') as fetch:
            second=run_chat_turn('월세60으로',C,[],'test',{},rental_result=data,prepare_context=lambda *args:ctx)
            fetch.assert_not_called();self.assertNotIn('황학동 ·',second['answer'])
