import unittest
from copy import deepcopy
from city_match import evaluate_place,comparison_rows,upsert_snapshot,facility_markers
from map_view import build_map_html

class CityMatchTests(unittest.TestCase):
    def setUp(self):
        self.data={'area_code':'A','area_name':'테스트','parking':[{}], 'subways':[{}],
            'ev_stations':[{'restricted':'Y'}], 'air':{'value':0}, 'commerce':{'payment_count':0},
            'age_rates':{'20대':30,'30대':20}}
    def test_zero_and_missing_not_same(self):
        prefs={'weights':{'air':5,'commerce':5}}
        self.assertEqual(evaluate_place(self.data,prefs)['score'],50)
        missing=deepcopy(self.data);missing['air']['value']=None
        r=evaluate_place(missing,prefs)
        self.assertEqual(r['coverage'],50)
        self.assertFalse(r['complete'])
    def test_no_weights(self):
        self.assertIsNone(evaluate_place(self.data,{'weights':{}})['score'])
    def test_ev_restrictions(self):
        self.assertEqual(evaluate_place(self.data,{'weights':{'ev':5}})['score'],0)
        self.data['ev_stations'][0]['restricted']=None
        self.assertIsNone(evaluate_place(self.data,{'weights':{'ev':5}})['score'])
    def test_age_is_current_population_and_unknown_groups(self):
        p={'weights':{'age':5},'age_groups':['20대','30대']}
        self.assertEqual(evaluate_place(self.data,p)['score'],50)
        p['age_groups'].append('40대')
        self.assertIsNone(evaluate_place(self.data,p)['score'])
    def test_partial_no_rank_and_upsert(self):
        b=deepcopy(self.data);b.update(area_code='B',area_name='미확인');b['air']['value']=None
        records=upsert_snapshot({},self.data);records=upsert_snapshot(records,b)
        records=upsert_snapshot(records,self.data)
        self.assertEqual(len(records),2)
        rows=comparison_rows(records,{'weights':{'air':5}})
        self.assertEqual(rows[0]['순위'],'1');self.assertEqual(rows[1]['순위'],'미확정')
    def test_map_invalid_coords_radius_and_injection(self):
        d={'subways':[{'name':'</script>','latitude':37.5665,'longitude':126.978},
            {'name':'invalid','latitude':float('nan'),'longitude':127},
            {'name':'far','latitude':37.8,'longitude':127}]}
        points=facility_markers(d,['subways'],{'latitude':37.5665,'longitude':126.978},1)
        self.assertEqual(len(points),1)
        self.assertNotIn('"name": "</script>"',build_map_html('key',facilities=points))

if __name__=='__main__':unittest.main()
