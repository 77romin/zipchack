import tempfile,unittest
from unittest.mock import Mock
from rag_index import Index,Source
from rag_retrieve import select,retrieve

class RetrieveTests(unittest.TestCase):
    def test_mmr_changes_diversity_and_lambda_one_matches_similarity(self):
        vectors=[[1.,0.],[.99,.01],[.6,.8]]
        similar,_=select(vectors,[1.,0.],2)
        diverse,_=select(vectors,[1.,0.],2,'mmr',.2)
        self.assertEqual(similar,[0,1]);self.assertEqual(diverse,[0,2])
        self.assertEqual(select(vectors,[1.,0.],2,'mmr',1)[0],similar)

    def test_metadata_always_included_other_item_excluded_and_no_docs(self):
        with tempfile.TemporaryDirectory() as folder:
            embed=Mock(side_effect=lambda texts:[[1.,0.] for t in texts])
            index=Index(folder,embed,'test')
            try:
                for item,kind,text in [('a','metadata','대상 동네'),('a','external','대상 설명'),('b','external','다른 동네')]:
                    index.put(Source(item,item+kind,item,text,'https://example.org','2026-10-22',kind))
                for mode in ['similarity','mmr']:
                    result=retrieve(index,'a','설명',mode,k=1,fetch_k=3)
                    self.assertEqual(len(result['evidence']),2)
                    self.assertEqual(result['evidence'][0]['metadata']['kind'],'metadata')
                    self.assertTrue(all(r['metadata']['item_id']=='a' for r in result['evidence']))
                    self.assertEqual([r['citation'] for r in result['evidence']],[1,2])
                index.put(Source('empty','meta','빈 동네','메타데이터','https://example.org','2026-10-22','metadata'))
                count=embed.call_count
                self.assertEqual(retrieve(index,'empty','설명')['external_count'],0)
                self.assertEqual(embed.call_count,count)
                with self.assertRaises(ValueError):retrieve(index,'missing','질문')
                with self.assertRaises(ValueError):retrieve(index,'a','질문',k=4,fetch_k=1)
            finally:index.close()
