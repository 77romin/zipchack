"""대화 입력 화면. 누적 조건과 부족한 정보를 사용자에게 보여준다."""
import os
import streamlit as st
from chat_conditions import ConversationError, map_conditions, DEFAULT_MODEL
from chat_query import run_chat_turn
from rent_api import service_keys
from rag_view import answer_question,answer_candidate,show_answer,safe_error
from recommendations import prepare_candidates,recommendation_rows
from rag_candidate import target_candidate

from concurrent.futures import ThreadPoolExecutor,TimeoutError
from copy import deepcopy

_JOBS=ThreadPoolExecutor(max_workers=4)


def process_request(prompt,current,history,score_context,commute_context,result,cache,asked,use_rag,mode,item_id,key,keys,model,failures,runner,rag_call,candidate_call=None,k=4):
    prepared={}
    def prepare(result,conditions,context):
        prepared.update(prepare_candidates(result,conditions,context,failures))
        return prepared
    turn=runner(prompt,current,history,key,keys,asked,model,rental_result=result,lifestyle_context=score_context,
                cache=cache,commute_context=commute_context,prepare_context=prepare)
    assistant={'role':'assistant','content':turn['answer']}
    if use_rag:
        context=prepared or score_context or {}
        rows=recommendation_rows(turn['result'],turn['conditions'],context)
        target=target_candidate(rows,None)
        if target and candidate_call:
            try:
                assistant['rag_result']=candidate_call(target,context,prompt,mode) if k==4 else candidate_call(target,context,prompt,mode,k=k)
            except Exception as error:
                assistant['rag_error']=safe_error(error)
            return turn,assistant,prepared,failures
        if not item_id:assistant['rag_error']='검색할 동네가 아직 없습니다. 지도 위치를 확인해주세요.'
        else:
            try:assistant['rag_result']=rag_call(item_id,prompt,mode) if k==4 else rag_call(item_id,prompt,mode,k=k)
            except Exception as error:assistant['rag_error']=safe_error(error)
    return turn,assistant,prepared,failures


def finish_request(job):
    try:
        turn,assistant,prepared,failures=job['future'].result()
        updated=turn['conditions']
        st.session_state.rent_query_cache=turn['cache']
        if turn['result'] is None:st.session_state.pop('rent_result',None)
        else:st.session_state.rent_result=turn['result']
        st.session_state.chat_optional_asked=turn['asked']
        st.session_state.chat_stage=turn['stage']
        st.session_state.conversation_conditions=updated
        if prepared:
            st.session_state.setdefault('neighborhood_locations',{}).update(prepared['points'])
            st.session_state.setdefault('resident_data',{}).update(prepared['residents'])
        st.session_state.recommendation_failures=failures
        mapped=map_conditions(updated)
        if mapped:st.session_state.housing_conditions=mapped
        elif (st.session_state.get('housing_conditions') or {}).get('source')=='conversation':st.session_state.housing_conditions=None
    except ConversationError as error:assistant={'role':'assistant','content':str(error)}
    except Exception:assistant={'role':'assistant','content':'처리를 완료하지 못했습니다. 기존 조건은 유지했어요. 연결 상태를 확인한 뒤 다시 입력해주세요.'}
    st.session_state.housing_chat=(job['history']+[{'role':'user','content':job['prompt']},assistant])[-40:]
    st.session_state.pop('housing_job',None);st.session_state.pop('pending_housing_prompt',None)
    st.rerun()


@st.fragment(run_every=.5)
def poll_request():
    job=st.session_state.get('housing_job')
    if job and job['future'].done():st.rerun()
    if job:st.info('조건과 동네 자료를 확인하고 있어요. 잠시만 기다려주세요.')


def render_chat(score_context=None,commute_context=None,neighborhood=None):
    st.subheader('집.착과 대화하기')
    st.caption('질문 순서와 관계없이 원하는 조건부터 말해주세요. 직장·통근시간·생활 선호는 나중에 추가해도 됩니다.')
    use_rag=st.checkbox('RAG 활용',value=False,key='chat_use_rag')
    mode=st.radio('검색 방식',['similarity','mmr'],format_func=lambda value:'유사도' if value=='similarity' else 'MMR',
                  horizontal=True,key='chat_retrieval_mode',disabled=not use_rag)
    k=st.number_input('검색 근거 수 Top-k',min_value=1,max_value=20,value=4,key='chat_top_k',disabled=not use_rag)
    if use_rag:
        st.caption('추천 후보가 있으면 확인된 최상위 후보의 근거를 자동 준비합니다. 후보가 없으면 지도 선택 동네의 저장 문서를 검색합니다.')
    history = st.session_state.setdefault('housing_chat', [])
    current = st.session_state.setdefault('conversation_conditions', {})
    active_job=st.session_state.get('housing_job')
    with st.container(border=True, height=500):
        if not history:
            with st.chat_message('assistant'):
                st.write('어떤 집과 동네를 찾고 있나요? 예산이나 관심 지역 등 아는 조건부터 편하게 알려주세요.')
        for item in history:
            with st.chat_message(item['role']):
                st.write(item['content'])
                if item.get('rag_result'):show_answer(item['rag_result'])
                if item.get('rag_error'):st.caption(item['rag_error'])
        if active_job:
            with st.chat_message('user'):st.write(active_job['prompt'])
    if current:
        with st.sidebar.expander('대화에서 정리한 조건'):
            labels = {'workplace':'직장', 'deal_type':'거래 유형', 'deposit_max':'최대 보증금(만원)',
                      'rent_max':'최대 월세(만원)', 'purchase_max':'최대 매매가(만원)',
                      'commute_minutes':'최대 편도 통근시간(분)', 'commute_mode':'통근수단',
                      'preferred_ages':'희망 주민 연령대', 'preferences':'생활 선호(0~5)',
                      'district':'실거래 조회 자치구','deal_month':'조회 계약월','housing_types':'조회 주택 유형'}
            st.json({labels.get(key, key):value for key,value in current.items()})
    job=st.session_state.get('housing_job')
    if job and job['future'].done():finish_request(job)
    prompt=st.chat_input('예: 시청 출근, 보증금 천에 월세 70, 지하철 40분',max_chars=2000,key='housing_message',disabled=bool(job))
    if prompt and not job:
        clean_history=[{'role':item['role'],'content':item['content']} for item in history]
        future=_JOBS.submit(process_request,prompt,deepcopy(current),clean_history,deepcopy(score_context),deepcopy(commute_context),
            deepcopy(st.session_state.get('rent_result')),deepcopy(st.session_state.get('rent_query_cache')),
            st.session_state.get('chat_optional_asked',False),use_rag,mode,(neighborhood or {}).get('legal_code'),
            os.getenv('GMS_KEY',''),service_keys(os.environ),os.getenv('GMS_MODEL','').strip() or DEFAULT_MODEL,
            dict(st.session_state.get('recommendation_failures',{})),run_chat_turn,answer_question,answer_candidate,k)
        job={'future':future,'prompt':prompt,'history':list(history)}
        st.session_state.housing_job=job;st.session_state.pending_housing_prompt=prompt
        # 즉시 완료되는 작업은 같은 실행에서 반영하고, 긴 API 작업은 화면과 분리한다.
        try:future.result(timeout=.1)
        except TimeoutError:pass
        except Exception:pass  # 완료 처리에서 사용자에게 안전한 안내를 남긴다.
        if future.done():finish_request(job)
        st.rerun()
    if job:poll_request()
    with st.sidebar:reset=st.button('대화와 대화 조건 초기화',key='reset_housing_chat')
    if reset:
        if job:job['future'].cancel()
        st.session_state.pop('housing_job',None);st.session_state.pop('pending_housing_prompt',None)
        st.session_state.housing_chat=[];st.session_state.conversation_conditions={}
        st.session_state.chat_optional_asked=False;st.session_state.chat_stage='collecting'
        if (st.session_state.get('housing_conditions') or {}).get('source')=='conversation':st.session_state.housing_conditions=None
        st.rerun()
