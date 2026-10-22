import unittest
from unittest.mock import patch
from housing_scores import score_point,compare_candidates,score_reply,preference_weights,selected_ages
from test_housing_candidates import result,CONDITIONS

POINT={'latitude':37.56,'longitude':127.01,'legal_code':'1114016200'}
PARKS={'parks':[{'latitude':37.56,'longitude':127.01}],'source_url':'https://data.seoul.go.kr','skipped':0}
BIKES={'stations':[{'latitude':37.56,'longitude':127.01}],'source_url':'https://www.data.go.kr','skipped':0}

def context():
    return {'points':{'11140:신당동':POINT,'11140:충무로':POINT},'parks':PARKS,'bikes':BIKES,'residents':{},'month':'202609'}

class HousingScoreTests(unittest.TestCase):
    def test_weighted_score_and_missing_not_zero(self):
        conditions={'preferences':{'park':5,'bike':5}}
        score=score_point(POINT,conditions,parks=None,bikes=BIKES)
        self.assertEqual(score['score'],100)
        self.assertEqual(score['coverage'],50)
        self.assertFalse(score['complete'])
        self.assertEqual(score['missing'],['공원 접근성'])

    def test_distance_rule_and_far_clamping(self):
        with patch('housing_scores.nearest_distance',side_effect=[300,1200]):
            score=score_point(POINT,{'preferences':{'park':3,'bike':1}},PARKS,BIKES)
        self.assertEqual(score['score'],65)
        self.assertTrue(score['complete'])
        with patch('housing_scores.nearest_distance',return_value=2000):
            self.assertEqual(score_point(POINT,{'preferences':{'park':3}},PARKS)['score'],0)

    def test_empty_zero_weight_and_unsupported_preferences(self):
        self.assertIsNone(score_point(POINT,{'preferences':{'park':0}},PARKS)['score'])
        score=score_point(POINT,{'preferences':{'park':3}},{'parks':[]})
        self.assertIsNone(score['score'])
        self.assertFalse(score['complete'])
        self.assertIn('주차장',score_point(POINT,{'preferences':{'parking':5}})['missing'])

    def test_explicit_age_default_and_zero_override(self):
        self.assertEqual(preference_weights({'preferred_ages':[20,30]}),{'age':3})
        self.assertEqual(preference_weights({'preferred_ages':[20,30],'preferences':{'age':0}}),{})
        self.assertEqual(selected_ages({'preferred_age_range':[20,39]}),[20,30])
        self.assertEqual(selected_ages({'preferred_age_range':[20,35]}),[])
        resident={'code':'1114016200','total':100,'ages':{20:20,30:30},'month':'202609'}
        score=score_point(POINT,{'preferred_ages':[20,30]},resident=resident)
        self.assertEqual(score['score'],50)
        self.assertIsNone(score_point(POINT,{'preferred_ages':[20]},resident={**resident,'code':'other'})['score'])

    def test_budget_recalculation_and_shared_ranks(self):
        data=compare_candidates(result(),{'deposit_max':1000,'rent_max':70,'preferences':{'park':3}},context())
        self.assertEqual([row['rank'] for row in data],[1,1])
        data=compare_candidates(result(),{'deposit_max':1000,'rent_max':60,'preferences':{'park':3}},context())
        self.assertEqual([row['dong'] for row in data],['신당동'])

    def test_incomplete_source_and_scope_do_not_rank(self):
        ctx=context(); ctx['parks']={**PARKS,'skipped':1}
        data=compare_candidates(result(),{'deposit_max':1000,'rent_max':70,'preferences':{'park':3}},ctx)
        self.assertTrue(all(row['rank'] is None for row in data))
        data=result(); data['statuses'][0]['complete']=False
        scores=compare_candidates(data,{'deposit_max':1000,'rent_max':70,'preferences':{'park':3}},context())
        self.assertTrue(all(row['rank'] is None for row in scores))

    def test_resident_month_and_unknown_location(self):
        ctx=context(); ctx['points']={'11140:신당동':POINT}
        ctx['residents']={'1114016200:202608':{'code':'1114016200','month':'202608','total':100,'ages':{20:40,30:30}}}
        data=compare_candidates(result(),CONDITIONS,ctx)
        self.assertTrue(all(row['rank'] is None for row in data))
        self.assertTrue(any('동네 대표 위치' in row['missing'] for row in data))

    def test_chat_recalculates_updated_weights(self):
        from chat_flow import collect_turn
        with patch('chat_flow.extract_patch',return_value={'preferences':{'park':5,'bike':0,'age':0}}):
            updated,reply,_,_=collect_turn('공원만 중요해',CONDITIONS,[],'test',True,rental_result=result(),lifestyle_context=context())
        self.assertEqual(updated['preferences']['bike'],0)
        self.assertIn('생활 선호 비교',reply)
        self.assertIn('100/100',reply)
        self.assertIn('실제 통근시간',reply)

    def test_score_view_and_chat_integration(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']={**CONDITIONS,'preferences':{'park':3},'preferred_ages':[]}
        app.session_state['rent_result']=result()
        app.session_state['neighborhood_locations']={'11140:신당동':POINT}
        app.session_state['park_data']=PARKS
        app.run()
        app.chat_input[0].set_value('추천해줘').run()
        self.assertIn('생활 선호 비교',app.session_state['housing_chat'][-1]['content'])
        self.assertIn('100/100',app.session_state['housing_chat'][-1]['content'])
        self.assertEqual(len(app.exception),0)
