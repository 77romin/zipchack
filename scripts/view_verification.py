"""저장된 실제 실행 기록의 증빙 열람 화면. 운영 앱과 별도로 실행한다."""
from pathlib import Path
import json,sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_view import show_answer,safe_error
OUT=ROOT/'docs/검증/RAG_최종실험'
st.set_page_config(page_title='집착 검증 기록',layout='wide')
st.title('집.착 실제 실행 검증 기록')
st.caption('저장된 GMS·Chroma 실행 결과를 열람합니다. 이 화면에서 모델을 재호출하지 않습니다. 오류 안내는 격리된 입력 검증입니다.')
section=st.radio('증빙 항목',['Top-k 전후','수집·색인 반복','근거 답변','오류 안내','품질·시간 비교','UML'],horizontal=True)
raw=json.loads((OUT/'raw.json').read_text(encoding='utf-8'))
if section=='Top-k 전후':
    mode=st.radio('검색 방식',['similarity','mmr'],horizontal=True)
    columns=st.columns(2)
    for col,k in zip(columns,[1,4]):
        r=next(r for r in raw['top_k'] if r['mode']==mode and r['k']==k)
        with col:
            st.subheader(f'Top-k {k} · 외부 {r["external_count"]}개')
            st.caption('공통 질문: 공덕역 환승 교통을 설명해줘 · 메타데이터 1개 별도')
            for row in r['evidence']:
                st.write(f"[{row['citation']}] {row['metadata']['title']} · {row['metadata']['kind']}")
                st.caption(row['id']);st.write(row['text'][:300])
elif section=='수집·색인 반복':
    repeat=json.loads((OUT/'collection_repeat.json').read_text(encoding='utf-8'))
    st.subheader('같은 질문 2회 · 수집 억제')
    st.table([{'실행':i+1,'질문 캐시':r['question_cache_hit'],'수집 HTTP':r['collection_requests'],'준비 ms':round(r['prepare_ms'],1)} for i,r in enumerate(repeat)])
    chunks=json.loads((OUT/'chunk_comparison.json').read_text(encoding='utf-8'))
    st.subheader('실제 Chroma 재색인 · 설정 변경과 반복')
    st.table([{'크기':r['size'],'중복':r['overlap'],'청크':r['count'],'새 임베딩':r['result']['embedded']} for r in chunks['settings']])
    for name in ['collection_repeat.json','chunk_comparison.json']:
        with st.expander(name):st.json(json.loads((OUT/name).read_text(encoding='utf-8')))
elif section=='근거 답변':
    case=st.selectbox('질문',raw['cases'],format_func=lambda c:c['id']+' · '+c['question'])
    mode=st.radio('검색 방식',['no-rag','similarity','mmr'],horizontal=True)
    row=next(r for r in raw['runs'] if r['case']==case['id'] and r['mode']==mode)
    st.write('질문: '+case['question']);show_answer({**row['result'],'mode':mode})
elif section=='오류 안내':
    for label,error in [('API 키 없음',ValueError('GMS_KEY')),('색인 없음',ValueError('색인이 없습니다')),('외부 요청 실패',ValueError('private-value'))]:
        st.subheader(label);st.warning(safe_error(error))
    st.caption('운영 .env와 DB를 삭제하지 않고 동일 오류 표시 함수를 검증했습니다.')
elif section=='품질·시간 비교':
    st.dataframe(json.loads((OUT/'summary.json').read_text(encoding='utf-8')))
    st.image((OUT/'quality.svg').read_text(encoding='utf-8'))
    st.image((OUT/'latency.svg').read_text(encoding='utf-8'))
else:st.image((ROOT/'docs/RAG_파이프라인.svg').read_text(encoding='utf-8'))
