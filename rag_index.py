"""출처 있는 자료의 청킹·임베딩·별도 Chroma 컬렉션 적재. UI와 분리."""
from dataclasses import dataclass
from hashlib import sha256
import json, math
from pathlib import Path
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

@dataclass(frozen=True)
class Source:
    item_id: str
    document_id: str
    title: str
    text: str
    source_url: str
    observed_at: str
    kind: str = 'external'

def chunks(source, size=1000, overlap=200):
    if not 0 <= overlap < size:
        raise ValueError('청크 크기는 양수이고 중복 길이보다 커야 합니다.')
    if source.kind not in {'metadata','external'} or any(not isinstance(v,str) or not v.strip() for v in vars(source).values()):
        raise ValueError('항목·문서 식별자, 본문, 출처, 기준일이 필요합니다.')
    texts=[source.text] if source.kind=='metadata' else RecursiveCharacterTextSplitter(
        chunk_size=size,chunk_overlap=overlap,separators=['\n\n','\n','。','. ',' ','']).split_text(source.text)
    namespace=json.dumps([source.item_id,source.document_id,source.kind],ensure_ascii=False)
    return [{'id':sha256(f'{namespace}:{i}'.encode()).hexdigest(), 'text':text,
             'metadata':{'item_id':source.item_id,'document_id':source.document_id,'kind':source.kind,
                         'title':source.title,'source_url':source.source_url,'observed_at':source.observed_at,
                         'chunk_index':i,'chunk_size':size,'chunk_overlap':overlap,
                         'fingerprint':sha256(json.dumps([vars(source),size,overlap,text],sort_keys=True,ensure_ascii=False).encode()).hexdigest()}}
            for i,text in enumerate(texts)]

class GmsEmbeddings:
    def __init__(self,key,model='text-embedding-3-small'):
        if not key or not key.strip():
            raise ValueError('GMS_KEY를 설정해주세요.')
        self.key=key.strip()
        self.model=model

    def __call__(self,texts):
        for attempt in range(3):
            try:
                response=requests.post('https://gms.ssafy.io/gmsapi/api.openai.com/v1/embeddings',
                    headers={'Authorization':'Bearer '+self.key},json={'model':self.model,'input':texts},timeout=(5,60))
                response.raise_for_status()
                data=sorted(response.json()['data'],key=lambda row:row['index'])
                vectors=[row['embedding'] for row in data]
                if [row['index'] for row in data]!=list(range(len(texts))) or not vectors:
                    raise ValueError()
                dimension=len(vectors[0])
                if not dimension or any(len(v)!=dimension or any(type(x) not in (int,float) or not math.isfinite(x) for x in v) for v in vectors):
                    raise ValueError()
                return vectors
            except (requests.RequestException,ValueError,KeyError,TypeError):
                if attempt==2:
                    raise ValueError('임베딩 요청에 실패했습니다. GMS 권한·모델 지원·네트워크를 확인해주세요.') from None
                import time
                time.sleep(0.5*(attempt+1))

class Index:
    def __init__(self,path,embed,model):
        import chromadb
        from chromadb.config import Settings
        self.embed=embed
        self.model=model
        client=chromadb.PersistentClient(path=str(path),settings=Settings(anonymized_telemetry=False))
        self.client=client
        self.collections={kind:client.get_or_create_collection('zipchack_'+kind,
             metadata={'embedding_model':model},embedding_function=None) for kind in ('metadata','external')}
        if any(c.metadata.get('embedding_model')!=model for c in self.collections.values()):
            client.close()
            raise ValueError('저장된 임베딩 모델이 다릅니다. 별도 DB 경로를 사용해주세요.')

    def close(self):
        self.client.close()

    def put_many(self,sources,size=1000,overlap=200):
        results=[]
        for offset in range(0,len(sources),4):
            results.extend(self._put_group(sources[offset:offset+4],size,overlap))
        return results

    def _put_group(self,sources,size=1000,overlap=200):
        pending={}
        for source in sources:
            rows=chunks(source,size,overlap)
            old=self.collections[source.kind].get(ids=[r['id'] for r in rows],include=['metadatas'])
            existing=dict(zip(old['ids'],old['metadatas']))
            for row in rows:
                if existing.get(row['id'],{}).get('fingerprint')!=row['metadata']['fingerprint']:
                    pending[row['text']]=None
        texts=list(pending)
        for offset in range(0,len(texts),4):
            batch=texts[offset:offset+4]
            pending.update(zip(batch,self.embed(batch)))
        original=self.embed
        self.embed=lambda batch:[pending[text] for text in batch]
        try:
            return [self.put(source,size,overlap) for source in sources]
        finally:
            self.embed=original

    def put(self,source,size=1000,overlap=200):
        rows=chunks(source,size,overlap)
        collection=self.collections[source.kind]
        where={'$and':[{'item_id':source.item_id},{'document_id':source.document_id}]}
        previous=collection.get(where=where,include=['metadatas'])
        existing=dict(zip(previous['ids'],previous['metadatas']))
        changed=[row for row in rows if existing.get(row['id'],{}).get('fingerprint')!=row['metadata']['fingerprint']]
        # 모든 임베딩 성공 후 upsert. 실패 시 이전 문서/청크를 삭제하지 않는다.
        vectors=[]
        for offset in range(0,len(changed),32):
            vectors.extend(self.embed([row['text'] for row in changed[offset:offset+32]]))
        if changed:
            collection.upsert(ids=[r['id'] for r in changed],documents=[r['text'] for r in changed],
                              metadatas=[r['metadata'] for r in changed],embeddings=vectors)
        stale=set(existing)-{row['id'] for row in rows}
        if stale:
            collection.delete(ids=sorted(stale))
        return {'chunks':len(rows),'embedded':len(changed),'removed':len(stale)}

def park_sources():
    from park_data import bundled_parks
    data=bundled_parks()
    for row in data['parks']:
        # 공원을 특정 법정동에 임의 배정하지 않는다. 좌표 정보만으로 편의성을 단정하지 않는다.
        yield Source('seoul-parks',str(row['id']),row['name'],
            f"공원명: {row['name']}\n위도: {row['latitude']}\n경도: {row['longitude']}\n서울시 주요 공원 목록의 위치 자료입니다. 입구·도보시간·운영시간 정보는 포함하지 않습니다.",
            data['source_url'],data['source_updated_at'])
