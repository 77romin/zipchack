"""고정 질문·코퍼스의 no-RAG/similarity/MMR 실제 실행 기록. 정답 판정은 별도 검토한다."""
import json,sys,os
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from rag_index import Index,GmsEmbeddings
from rag_prepare import ask
from rag_pipeline import build_graph,run

CASES=[
 {'id':'Q1','item':'1111010100','question':'서울 청운동이라는 이름은 어떤 두 지명에서 유래했나요?','expected':'청풍계와 백운동에서 각각 한 글자','answerable':True,'document':'wikipedia:','terms':['청풍계','백운동']},
 {'id':'Q2','item':'1168010100','question':'역삼동이 역삼1동과 역삼2동으로 분동된 정확한 날짜는 언제인가요?','expected':'1980년 4월 1일','answerable':True,'document':'wikipedia:','terms':['1980','4월','1일']},
 {'id':'Q3','item':'1144012400','question':'연남동은 몇 년에 어느 동 일부를 분리해 마포구에 편입하면서 생겼나요?','expected':'1975년, 서대문구 연희동 일부','answerable':True,'document':'wikipedia:','terms':['1975','연희동']},
 {'id':'Q4','item':'1144010200','question':'지금 공덕동에서 보증금 천만원 월세 70만원으로 즉시 입주 가능한 정확한 호수와 집주인 연락처를 알려줘.','expected':'현재 매물·호수·연락처 자료가 없어 확인 불가','answerable':False,'terms':[]},
 {'id':'Q5','item':'1114016200','question':'신당동 충무아트센터 따릉이 대여소에 지금 남은 자전거가 정확히 몇 대인가요?','expected':'실시간 재고 자료가 없어 확인 불가','answerable':False,'terms':[]},
]

def main():
    load_dotenv(ROOT/'.env')
    key=os.getenv('GMS_KEY','');model=os.getenv('GMS_MODEL') or 'gpt-5.4-nano'
    embedding=os.getenv('RAG_EMBEDDING_MODEL') or 'text-embedding-3-small'
    folder=ROOT/'docs/검증/RAG_최종실험';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'raw.json'
    record={'model':model,'embedding_model':embedding,'cases':CASES,'runs':[],
      'method':'각 질문/모드 1회, 동일 고정 DB. RAG k=4/fetch_k=20/lambda=.5. no-RAG는 근거 없이 일반 지식 답변. 프롬프트가 달라 종합 시스템 비교이며 검색 알고리즘만의 인과 효과가 아님. 시간은 검색+생성, 수집·색인·UI 제외.'}
    index=Index(ROOT/'storage/rag',GmsEmbeddings(key,embedding),embedding)
    try:
        graph=build_graph(index,key,model)
        for case in CASES:
            for mode in ['no-rag','similarity','mmr']:
                start=perf_counter()
                try:
                    if mode=='no-rag':
                        result=ask('외부 검색 없이 자신이 알고 있는 일반 지식으로 서울 동네 질문에 답하라. 모르면 추측하지 말고 모른다고 하라. 출처 번호나 URL을 만들지 말라. JSON {"answer":"완전한 한국어 문장","abstained":false}로 출력하라. 확인할 수 없으면 abstained=true이며 answer에도 이유를 쓰라.',{'question':case['question']},key,model)
                        if not result.get('answer','').strip():raise ValueError('빈 답변')
                    else:result=run(graph,case['item'],case['question'],mode=mode,k=4)
                    record['runs'].append({'case':case['id'],'mode':mode,'wall_ms':(perf_counter()-start)*1000,'result':result})
                except ValueError:
                    record['runs'].append({'case':case['id'],'mode':mode,'error':'외부 호출 또는 출력 검증 실패'})
                path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                print(case['id'],mode,'saved',flush=True)
        # 동일 질문·고정 후보에서 외부 Top-k 증가와 MMR 목록 차이를 저장.
        from rag_retrieve import retrieve
        record['top_k']=[retrieve(index,'1144010200','공덕역 환승 교통을 설명해줘',mode,k=k) for mode in ['similarity','mmr'] for k in [1,4]]
        record['graph']={'nodes':list(graph.get_graph().nodes),'edges':[[e.source,e.target] for e in graph.get_graph().edges]}
        path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:index.close()

if __name__=='__main__':main()
