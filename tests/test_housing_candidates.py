import unittest
from unittest.mock import patch
from pathlib import Path
from housing_candidates import build_candidates,candidate_reply
from chat_flow import collect_turn

CONDITIONS={'workplace':'시청','deal_type':'월세','deposit_max':1000,'rent_max':70,'commute_mode':'대중교통','commute_minutes':40,
            'preferences':{'park':3,'bike':3},'preferred_ages':[20,30]}

def row(dong,deposit,rent):
    return {'category':'오피스텔','dong':dong,'deposit':deposit,'monthly_rent':rent,'deal_type':'월세',
            'contract_date':'2026-09-01','source_url':'https://www.data.go.kr/data/15126475/openapi.do',
            'name':'테스트','area':20,'area_type':'전용면적','contract_type':'신규'}

def result():
    return {'rows':[row('신당동',1000,60),row('신당동',500,70),row('충무로',900,70),row('명동',2000,80)],
            'statuses':[{'category':'오피스텔','error':None,'complete':True,'skipped':0,'total':4,'received':4}],
            'district_code':'11140','month':'202609','queried_at':'test KST'}

class HousingCandidateTests(unittest.TestCase):
    def test_budget_group_count_and_single_contract_example(self):
        data=build_candidates(result(),CONDITIONS)
        self.assertEqual(data['matched'],3)
        self.assertEqual([group['dong'] for group in data['groups']],['신당동','충무로'])
        self.assertEqual(data['groups'][0]['count'],2)
        example=data['groups'][0]['example']
        self.assertEqual((example['deposit'],example['monthly_rent']),(1000,60))
        self.assertNotEqual((example['deposit'],example['monthly_rent']),(500,60))

    def test_reply_evidence_and_unknown_criteria(self):
        reply=candidate_reply(result(),CONDITIONS)
        for expected in ['신당동','202609','test KST','공식 출처','통근시간','종합 적합도 순위','오피스텔']:
            self.assertIn(expected,reply)
        self.assertNotIn('명동',reply)

    def test_partial_failure_and_excluded_rows(self):
        data=result()
        data['statuses'] += [{'category':'아파트','error':'연결 실패','complete':False}]
        self.assertEqual(build_candidates(data,CONDITIONS)['partial'],['아파트'])
        self.assertIn('전체 결과가 아니에요',candidate_reply(data,CONDITIONS))
        data['statuses'][0]['skipped']=1
        self.assertIn('오피스텔',build_candidates(data,CONDITIONS)['partial'])

    def test_failed_does_not_mean_no_transactions(self):
        data=result()
        data['statuses']=[{'category':'아파트','error':'연결 실패','complete':False}]
        self.assertEqual(build_candidates(data,CONDITIONS)['state'],'failed')
        self.assertIn('거래가 없다는 뜻은 아니에요',candidate_reply(data,CONDITIONS))

    def test_zero_does_not_relax_conditions(self):
        conditions={**CONDITIONS,'rent_max':10}
        reply=candidate_reply(result(),conditions)
        self.assertIn('0건',reply)
        self.assertEqual(conditions['rent_max'],10)
        self.assertEqual(build_candidates(result(),conditions)['groups'],[])
        self.assertEqual(build_candidates(result(),{'deal_type':'매매'})['state'],'missing_budget')

    def test_finished_turn_uses_records_without_llm(self):
        with patch('chat_flow.extract_patch') as extract:
            updated,reply,_,stage=collect_turn('추천해줘',CONDITIONS,[],'',True,rental_result=result())
        extract.assert_not_called()
        self.assertEqual(updated,CONDITIONS)
        self.assertEqual(stage,'candidates')
        self.assertIn('신당동',reply)

    def test_top_five_and_tie_break(self):
        data=result()
        data['rows']=[row(name,1000,70) for name in ['마','라','다','나','가','바']]
        self.assertEqual(build_candidates(data,CONDITIONS)['groups'][0]['dong'],'가')
        reply=candidate_reply(data,CONDITIONS)
        self.assertEqual(reply.count('공식 출처'),5)

    def test_ui_neighborhood_and_chat_use_same_records(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
        app.session_state['conversation_conditions']=CONDITIONS
        app.session_state['rent_result']=result()
        app.run()
        select=next(s for s in app.selectbox if s.label=='거래를 살펴볼 동네')
        select.select('신당동').run()
        app.chat_input[0].set_value('추천해줘').run()
        self.assertEqual(app.session_state['chat_stage'],'candidates')
        self.assertIn('신당동',app.session_state['housing_chat'][-1]['content'])
        self.assertEqual(len(app.exception),0)
