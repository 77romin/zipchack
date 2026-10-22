"""선택 동네 메타데이터 필수 포함·동일 후보 범위의 cosine/MMR 검색."""
from time import perf_counter
import math

def cosine(a,b):
    if len(a)!=len(b) or not a:
        raise ValueError('벡터 차원을 확인해주세요.')
    denominator=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/denominator if denominator else 0.0

def select(vectors,query,k,mode='similarity',weight=0.5):
    if mode not in {'similarity','mmr'} or not 0<=weight<=1 or type(k) is not int or k<1:
        raise ValueError('검색 방식·개수·MMR 계수를 확인해주세요.')
    relevance=[cosine(query,v) for v in vectors]
    remaining=list(range(len(vectors))); chosen=[]
    while remaining and len(chosen)<k:
        def score(i):
            if mode=='similarity' or not chosen:
                return relevance[i]
            return weight*relevance[i]-(1-weight)*max(cosine(vectors[i],vectors[j]) for j in chosen)
        best=max(remaining,key=lambda i:(score(i),-i))
        chosen.append(best);remaining.remove(best)
    return chosen,relevance

def retrieve(index,item_id,question,mode='similarity',k=4,fetch_k=20,weight=0.5):
    start=perf_counter()
    if not isinstance(question,str) or not question.strip() or len(question)>4000:
        raise ValueError('질문을 1~4000자로 입력해주세요.')
    if type(fetch_k) is not int or type(k) is not int or not 1<=k<=fetch_k<=200:
        raise ValueError('1 ≤ k ≤ fetch_k ≤ 200 이어야 합니다.')
    select([], [1.0], k, mode, weight)
    metadata=index.collections['metadata'].get(where={'item_id':item_id},include=['documents','metadatas'])
    if not metadata['ids']:
        raise ValueError('선택 동네 메타데이터가 없습니다. 자료를 먼저 색인해주세요.')
    def unpack(data):
        return [{'id':identity,'text':text,'metadata':meta} for identity,text,meta in zip(data['ids'],data['documents'],data['metadatas'])]
    evidence=unpack(metadata)
    # 대상 항목 자체 문서만 검색. 서울 전체 공원 목록을 임의로 동네 근거에 포함하지 않는다.
    available=index.collections['external'].get(where={'item_id':item_id},include=['metadatas'])
    timings={'embedding_ms':0.0,'vector_ms':0.0,'selection_ms':0.0}
    candidates=[];relevance=[];selected=[]
    if available['ids']:
        t=perf_counter();query=index.embed([question])[0];timings['embedding_ms']=(perf_counter()-t)*1000
        t=perf_counter()
        result=index.collections['external'].query(query_embeddings=[query],where={'item_id':item_id},
            n_results=min(fetch_k,len(available['ids'])),include=['documents','metadatas','embeddings'])
        timings['vector_ms']=(perf_counter()-t)*1000
        batch={key:result[key][0] for key in ['ids','documents','metadatas']}
        candidates=unpack(batch);vectors=result['embeddings'][0]
        # 동일 후보를 cosine으로 다시 정렬하며 DB 기본 거리와 구분한다.
        t=perf_counter();selected,relevance=select(vectors,query,k,mode,weight)
        timings['selection_ms']=(perf_counter()-t)*1000
        evidence += [{**candidates[i],'cosine':relevance[i]} for i in selected]
    unique={}
    for row in evidence:
        unique.setdefault(row['id'],row)
    evidence=[{**row,'citation':i+1} for i,row in enumerate(unique.values())]
    timings['total_ms']=(perf_counter()-start)*1000
    return {'item_id':item_id,'mode':mode,'k':k,'fetch_k':fetch_k,'weight':weight,
        'candidate_count':len(candidates),'external_count':len(selected),'evidence':evidence,
        'timings':timings,'notice':None if selected else '선택 동네의 외부 설명 문서가 아직 없습니다.'}
