"""동네별 RAG 대화 화면. 기존 예산·통근 조건 대화와 분리한다."""
import os
from pathlib import Path
import streamlit as st
from neighborhood_data import load_neighborhoods
from rag_index import Index,GmsEmbeddings
from rag_pipeline import build_graph,run

ROOT=Path(__file__).resolve().parent


def answer_candidate(point,context,question,mode):
    """자료 묶음별 색인으로 다른 사용자·대표점의 근거 혼입을 방지한다."""
    from hashlib import sha256
    from dataclasses import asdict
    import json
    from rag_candidate import candidate_sources
    from neighborhood_data import neighborhood_sources,wiki_sources
    code=point['legal_code']
    sources=[s for s in neighborhood_sources() if s.item_id==code]
    if not sources:raise ValueError('공식 법정동 코드가 확인되지 않았습니다.')
    sources.extend(s for s in wiki_sources() if s.item_id==code)
    sources.extend(candidate_sources(point,context))
    identity=sha256(json.dumps([asdict(s) for s in sources],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key=os.getenv('GMS_KEY','').strip()
    model=os.getenv('RAG_EMBEDDING_MODEL','').strip() or 'text-embedding-3-small'
    index=Index(ROOT/'storage/rag_candidates'/identity,GmsEmbeddings(key,model),model)
    try:
        indexed=index.put_many(sources)
        result=run(build_graph(index,key,os.getenv('GMS_MODEL','').strip() or 'gpt-5.4-nano'),code,question,mode=mode)
        result['preparation']={'item_id':code,'documents':len(sources),'embedded':sum(r['embedded'] for r in indexed),'snapshot':identity}
        return result
    finally:index.close()

def answer_question(item_id,question,mode):
    if not (ROOT/'storage/rag/chroma.sqlite3').exists():
        raise ValueError('근거 색인이 없습니다. 자료 준비와 색인을 먼저 실행해주세요.')
    key=os.getenv('GMS_KEY','').strip()
    if not key:raise ValueError('GMS_KEY를 설정하고 앱을 다시 실행해주세요.')
    model=os.getenv('RAG_EMBEDDING_MODEL','').strip() or 'text-embedding-3-small'
    index=Index(ROOT/'storage/rag',GmsEmbeddings(key,model),model)
    try:
        return run(build_graph(index,key,os.getenv('GMS_MODEL','').strip() or 'gpt-5.4-nano'),
                   item_id,question,mode=mode)
    finally:index.close()

def show_answer(result):
    if result.get('preparation'):
        p=result['preparation']
        st.caption(f"추천 근거 대상: {p['item_id']} · 준비 문서 {p['documents']}개 · 새 임베딩 {p['embedded']}개")
    st.markdown(result['answer'])
    if result.get('abstained'):st.info('자료가 부족해 답변을 유보했습니다.')
    citations=result.get('citations',[])
    if citations:
        with st.expander('답변에 사용한 근거'):
            for source in citations:
                numbers=', '.join(str(n) for n in source['numbers'])
                kind='동네 메타데이터' if source['kind']=='metadata' else '외부 문서'
                st.write(f"[{numbers}] {source['title']} · {kind}")
                st.link_button('원문 보기',source['source_url'])
                st.caption('자료 시점: '+source['observed_at'])
                if source.get('license'):st.caption(source['license'])
                if source.get('attribution'):st.caption(source['attribution'])
    else:st.caption('답변에서 인용한 문서가 없습니다.')
    st.caption('검색 방식: '+result.get('mode','similarity')+' · 문서 자료에 근거한 설명이며 현재 매물·운행·주거 적합성을 보장하지 않습니다.')

def render_rag(neighborhood=None):
    st.subheader('동네 근거에 질문하기')
    st.caption('예산·직장 조건 입력은 위 대화에서 진행합니다. 여기서는 저장된 동네 문서에 질문합니다. 각 질문은 독립적으로 처리하므로 동네·대상을 구체적으로 적어주세요.')
    try:rows,_=load_neighborhoods()
    except (ValueError,OSError):
        st.info('동네 자료를 먼저 준비해주세요.');return
    by_code={row['code']:row for row in rows}
    codes=list(by_code)
    suggested=(neighborhood or {}).get('legal_code')
    if 'rag_item' not in st.session_state and suggested in by_code:
        st.session_state.rag_item=suggested
    pending=st.session_state.pop('rag_follow_item',None)
    if pending in by_code:st.session_state.rag_item=pending
    item_id=st.selectbox('질문할 동네',codes,format_func=lambda code:by_code[code]['full_name'],key='rag_item')
    if suggested in by_code and suggested!=item_id:
        if st.button('지도에서 선택한 동네로 질문하기',key='rag_follow_map'):
            st.session_state.rag_follow_item=suggested
            st.rerun()
    mode=st.radio('근거 검색 방식',['similarity','mmr'],format_func=lambda m:'유사도' if m=='similarity' else 'MMR',horizontal=True,key='rag_mode')
    histories=st.session_state.setdefault('rag_histories',{})
    history=histories.setdefault(item_id,[])
    st.caption('대화 기록은 동네별로 이 세션에서만 보관합니다. 외부 문서가 없는 동네는 메타데이터 범위만 답할 수 있습니다. 문서 수집은 이 화면에서 자동 실행하지 않습니다.')
    for turn in history:
        with st.chat_message('user'):st.write(turn['question'])
        with st.chat_message('assistant'):show_answer(turn['result'])
    with st.form('rag_question_form',clear_on_submit=True):
        question=st.text_input('동네에 대해 궁금한 점',max_chars=2000,key='rag_question')
        submitted=st.form_submit_button('근거로 답변받기')
    if submitted:
        if not question.strip():st.warning('질문을 입력해주세요.')
        else:
            try:
                with st.spinner('동네 근거를 검색하고 답변을 작성합니다...'):
                    result=answer_question(item_id,question,mode)
                histories[item_id]=(history+[{'question':question,'result':result}])[-10:]
                st.rerun()
            except Exception:
                st.warning('답변을 완료하지 못했습니다. 색인·API 키·네트워크를 확인해주세요. 기존 대화는 유지됩니다.')
    if st.button('이 동네 질문 기록 지우기',key='rag_clear'):
        histories[item_id]=[];st.rerun()
