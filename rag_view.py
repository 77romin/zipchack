"""동네별 RAG 대화 화면. 기존 예산·통근 조건 대화와 분리한다."""
import os
from pathlib import Path
import streamlit as st
from neighborhood_data import load_neighborhoods
from rag_index import Index,GmsEmbeddings
from rag_pipeline import build_graph,run

ROOT=Path(__file__).resolve().parent


def answer_candidate(point,context,question,mode,k=4):
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
        preparation=prepare_external(index,code,question,key)
        result=run(build_graph(index,key,os.getenv('GMS_MODEL','').strip() or 'gpt-5.4-nano'),code,question,mode=mode,k=k)
        result['preparation']={'item_id':code,'documents':len(sources),'embedded':sum(r['embedded'] for r in indexed),'snapshot':identity,'external':preparation}
        return result
    finally:index.close()

def prepare_external(index,code,question,key):
    from rag_prepare import prepare
    from wiki_documents import TITLES
    if code not in TITLES:
        return {'status':'unsupported','notice':'자체 위키 문서 연결 미검증: 공식 자료만 사용합니다.'}
    item=next(row for row in load_neighborhoods()[0] if row['code']==code)
    try:
        return prepare(item,question,key,ROOT/'storage/preparation',index,os.getenv('WIKI_CONTACT',''),
                       os.getenv('GMS_MODEL','').strip() or 'gpt-5.4-nano')
    except ValueError:
        return {'status':'failed','notice':'외부 문서 확장 실패: 이미 준비된 근거만 검색합니다.'}


def answer_question(item_id,question,mode,k=4):
    if not (ROOT/'storage/rag/chroma.sqlite3').exists():
        raise ValueError('근거 색인이 없습니다. 자료 준비와 색인을 먼저 실행해주세요.')
    key=os.getenv('GMS_KEY','').strip()
    if not key:raise ValueError('GMS_KEY를 설정하고 앱을 다시 실행해주세요.')
    model=os.getenv('RAG_EMBEDDING_MODEL','').strip() or 'text-embedding-3-small'
    index=Index(ROOT/'storage/rag',GmsEmbeddings(key,model),model)
    try:
        preparation=prepare_external(index,item_id,question,key)
        result=run(build_graph(index,key,os.getenv('GMS_MODEL','').strip() or 'gpt-5.4-nano'),
                   item_id,question,mode=mode,k=k)
        result['external_preparation']=preparation
        return result
    finally:index.close()

def source_kind(source):
    if source['kind']=='metadata':return '동네 메타데이터'
    url=source.get('source_url','')
    if 'wikipedia.org/' in url:return '위키백과'
    if 'data.seoul.go.kr/' in url:return '서울시 공식 시설 자료'
    if 'data.go.kr/' in url:return '공공데이터 공식 통계/API'
    return '외부 문서'


def safe_error(error):
    text=str(error)
    if 'GMS_KEY' in text:return 'GMS_KEY가 없습니다. .env 설정 후 다시 실행해주세요.'
    if '색인이 없습니다' in text:return '근거 색인이 없습니다. 색인 준비 명령을 먼저 실행해주세요.'
    return '근거 처리를 완료하지 못했습니다. 자료·모델·네트워크 상태를 확인해주세요.'


def show_answer(result):
    if result.get('preparation'):
        p=result['preparation']
        st.caption(f"추천 근거 대상: {p['item_id']} · 준비 문서 {p['documents']}개 · 새 임베딩 {p['embedded']}개")
    preparation=result.get('external_preparation') or result.get('preparation',{}).get('external')
    if preparation:
        with st.expander('검색어·문서 선별 기록'):
            st.json(preparation)
    retrieval=result.get('retrieval',{})
    if retrieval:
        with st.expander('검색한 근거 전체 · Top-k 검증'):
            st.caption(f"외부 근거 Top-k {retrieval.get('k')} · 실제 외부 청크 {retrieval.get('external_count')} · 메타데이터 별도 포함")
            for row in retrieval.get('evidence',[]):
                st.write(f"[{row['citation']}] {row['metadata']['title']}")
                st.caption(row['id'])
            import json
            st.download_button('검색·답변 기록 JSON 저장',json.dumps(result,ensure_ascii=False,indent=2),
                               file_name='rag_evidence.json',mime='application/json',key='download-'+str(id(result)))
    st.markdown(result['answer'])
    st.caption('부동산·법률·금융 전문가의 조언을 대신하지 않습니다. 계약 전 원문과 현장을 확인하세요.')
    if result.get('abstained'):st.info('자료가 부족해 답변을 유보했습니다.')
    citations=result.get('citations',[])
    if citations:
        with st.expander('답변에 사용한 근거'):
            for source in citations:
                numbers=', '.join(str(n) for n in source['numbers'])
                kind=source_kind(source)
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
    k=st.number_input('검색 근거 수 Top-k',min_value=1,max_value=20,value=4,key='rag_top_k')
    histories=st.session_state.setdefault('rag_histories',{})
    history=histories.setdefault(item_id,[])
    st.caption('대화 기록은 동네별로 보관합니다. 자체 문서 연결이 검증된 5개 동네는 검색어 추출·후보 선별을 자동 실행하고, 같은 질문은 수집 캐시를 재사용합니다. 그 외 동네는 이미 준비된 근거만 사용합니다.')
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
                    result=answer_question(item_id,question,mode) if k==4 else answer_question(item_id,question,mode,k=k)
                histories[item_id]=(history+[{'question':question,'result':result}])[-10:]
                st.rerun()
            except Exception as error:
                st.warning(safe_error(error))
                st.caption('답변을 완료하지 못했습니다. 색인·API 키·네트워크를 확인해주세요. 기존 대화는 유지됩니다.')
    if st.button('이 동네 질문 기록 지우기',key='rag_clear'):
        histories[item_id]=[];st.rerun()
