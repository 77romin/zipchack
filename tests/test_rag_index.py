import tempfile,unittest
from dataclasses import replace
from unittest.mock import patch,Mock
from rag_index import Source,chunks,Index,GmsEmbeddings

class RagIndexTests(unittest.TestCase):
    def setUp(self):
        self.source=Source('dong-1','doc-1','공식 자료','공원 정보입니다. '*80,'https://example.org/source','2026-09-23')

    def test_chunks_keep_source_and_no_cross_item_collision(self):
        rows=chunks(self.source,100,20)
        self.assertGreater(len(rows),1)
        self.assertTrue(all(len(row['text'])<=100 for row in rows))
        self.assertEqual(rows[0]['metadata']['source_url'],self.source.source_url)
        other=chunks(replace(self.source,item_id='dong-2'),100,20)
        self.assertFalse({r['id'] for r in rows}&{r['id'] for r in other})
        self.assertEqual(len(chunks(replace(self.source,kind='metadata'),100,20)),1)
        with self.assertRaises(ValueError): chunks(self.source,100,100)

    def test_real_chroma_idempotence_replace_and_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            embed=Mock(side_effect=lambda texts:[[1.0,0.0,0.0] for t in texts])
            index=Index(folder,embed,'unit-test-only')
            initial=index.put_many([self.source],100,20)[0]
            self.assertGreater(initial['embedded'],1)
            self.assertEqual(index.put_many([self.source],100,20)[0]['embedded'],0)
            self.assertEqual(embed.call_count,1)
            embed.side_effect=ValueError('failed')
            with self.assertRaises(ValueError):index.put(replace(self.source,text='새 본문'),100,20)
            self.assertEqual(index.collections['external'].count(),initial['chunks'])
            embed.side_effect=lambda texts:[[1.0,0.0,0.0] for t in texts]
            result=index.put(replace(self.source,text='새 본문'),100,20)
            self.assertEqual(index.collections['external'].count(),1)
            self.assertEqual(result['removed'],initial['chunks']-1)
            index.put(replace(self.source,kind='metadata'),100,20)
            self.assertEqual(index.collections['metadata'].count(),1)
            index.close()
            with self.assertRaises(ValueError):Index(folder,embed,'different-model')

    def test_embedding_failure_hides_secret(self):
        import requests
        with patch('rag_index.requests.post',side_effect=requests.Timeout('private-key')):
            with self.assertRaises(ValueError) as error:GmsEmbeddings('private-key')(['문서'])
        self.assertNotIn('private-key',str(error.exception))

    def test_transient_failure_retries_and_preserves_response_order(self):
        import requests
        response=Mock()
        response.json.return_value={'data':[{'index':1,'embedding':[0.0,1.0]},{'index':0,'embedding':[1.0,0.0]}]}
        with patch('rag_index.requests.post',side_effect=[requests.Timeout('private-key'),response]) as post, patch('time.sleep'):
            self.assertEqual(GmsEmbeddings('private-key')(['문서1','문서2']),[[1.0,0.0],[0.0,1.0]])
            self.assertEqual(post.call_count,2)
