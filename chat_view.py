"""대화 입력 화면. 누적 조건과 부족한 정보를 사용자에게 보여준다."""
import os
import streamlit as st
from chat_conditions import ConversationError, map_conditions, DEFAULT_MODEL
from chat_query import run_chat_turn
from rent_api import service_keys
from rag_view import answer_question,show_answer

def render_chat(score_context=None,commute_context=None,neighborhood=None):
    st.subheader('집.착과 대화하기')
    st.caption('질문 순서와 관계없이 원하는 조건부터 말해주세요. 직장·통근시간·생활 선호는 나중에 추가해도 됩니다.')
    use_rag=st.checkbox('RAG 활용',value=False,key='chat_use_rag')
    mode=st.radio('검색 방식',['similarity','mmr'],format_func=lambda value:'유사도' if value=='similarity' else 'MMR',
                  horizontal=True,key='chat_retrieval_mode',disabled=not use_rag)
    if use_rag:
        st.caption('근거 검색 동네: '+(neighborhood or {}).get('name','미선택')+' · 저장된 문서 기준')
    history = st.session_state.setdefault('housing_chat', [])
    current = st.session_state.setdefault('conversation_conditions', {})
    with st.container(border=True, height=500):
        if not history:
            with st.chat_message('assistant'):
                st.write('어떤 집과 동네를 찾고 있나요? 예산이나 관심 지역 등 아는 조건부터 편하게 알려주세요.')
        for item in history:
            with st.chat_message(item['role']):
                st.write(item['content'])
                if item.get('rag_result'):show_answer(item['rag_result'])
                if item.get('rag_error'):st.caption(item['rag_error'])
    if current:
        with st.sidebar.expander('대화에서 정리한 조건'):
            labels = {'workplace':'직장', 'deal_type':'거래 유형', 'deposit_max':'최대 보증금(만원)',
                      'rent_max':'최대 월세(만원)', 'purchase_max':'최대 매매가(만원)',
                      'commute_minutes':'최대 편도 통근시간(분)', 'commute_mode':'통근수단',
                      'preferred_ages':'희망 주민 연령대', 'preferences':'생활 선호(0~5)',
                      'district':'실거래 조회 자치구','deal_month':'조회 계약월','housing_types':'조회 주택 유형'}
            st.json({labels.get(key, key):value for key,value in current.items()})
    prompt = st.chat_input('예: 시청 출근, 보증금 천에 월세 70, 지하철 40분', max_chars=2000)
    if prompt:
        try:
            with st.spinner('말씀하신 조건을 정리하고 있어요...'):
                turn=run_chat_turn(
                    prompt,current,[{'role':item['role'],'content':item['content']} for item in history],os.getenv('GMS_KEY',''),service_keys(os.environ),
                    st.session_state.get('chat_optional_asked',False),
                    os.getenv('GMS_MODEL','').strip() or DEFAULT_MODEL,
                    rental_result=st.session_state.get('rent_result'),lifestyle_context=score_context,
                    cache=st.session_state.get('rent_query_cache'),commute_context=commute_context)
                updated,answer,asked,stage=(turn[key] for key in ['conditions','answer','asked','stage'])
            st.session_state.rent_query_cache=turn['cache']
            if turn['result'] is None:
                st.session_state.pop('rent_result',None)
            else:
                st.session_state.rent_result=turn['result']
            st.session_state.chat_optional_asked = asked
            st.session_state.chat_stage = stage
            st.session_state.conversation_conditions = updated
            mapped = map_conditions(updated)
            if mapped:
                st.session_state.housing_conditions = mapped
            elif (st.session_state.get('housing_conditions') or {}).get('source') == 'conversation':
                st.session_state.housing_conditions = None
            assistant={'role':'assistant','content':answer}
            if use_rag:
                item_id=(neighborhood or {}).get('legal_code')
                if not item_id:
                    assistant['rag_error']='검색할 동네가 아직 없습니다. 지도 위치를 확인해주세요.'
                else:
                    try:
                        with st.spinner('동네 문서에서 근거를 검색합니다...'):
                            assistant['rag_result']=answer_question(item_id,prompt,mode)
                    except Exception:
                        assistant['rag_error']='근거 답변을 완료하지 못했습니다. 입력한 조건은 저장했어요. 사이드바에서 색인·연결 상태를 확인해주세요.'
            st.session_state.housing_chat = (history + [
                {'role':'user','content':prompt}, assistant])[-40:]
            st.rerun()
        except ConversationError as error:
            st.warning(str(error))
    with st.sidebar:
        reset=st.button('대화와 대화 조건 초기화',key='reset_housing_chat')
    if reset:
        st.session_state.housing_chat = []
        st.session_state.conversation_conditions = {}
        st.session_state.chat_optional_asked = False
        st.session_state.chat_stage = 'collecting'
        if (st.session_state.get('housing_conditions') or {}).get('source') == 'conversation':
            st.session_state.housing_conditions = None
        st.rerun()
