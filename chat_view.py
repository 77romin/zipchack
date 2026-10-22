"""대화 입력 화면. 누적 조건과 부족한 정보를 사용자에게 보여준다."""
import os
import streamlit as st
from chat_conditions import ConversationError, extract_patch, merge_conditions, next_question, map_conditions, DEFAULT_MODEL

def render_chat():
    st.subheader('집.착과 대화하기')
    st.caption('원하는 조건을 편하게 알려주세요. 빠진 내용은 하나씩 물어볼게요.')
    history = st.session_state.setdefault('housing_chat', [])
    current = st.session_state.setdefault('conversation_conditions', {})
    with st.container(border=True, height=500):
        if not history:
            with st.chat_message('assistant'):
                st.write('어떤 집과 동네를 찾고 있나요? 직장, 예산, 출근 방법부터 알려주세요.')
        for item in history:
            with st.chat_message(item['role']):
                st.write(item['content'])
    if current:
        with st.expander('대화에서 정리한 조건', expanded=True):
            labels = {'workplace':'직장', 'deal_type':'거래 유형', 'deposit_max':'최대 보증금(만원)',
                      'rent_max':'최대 월세(만원)', 'purchase_max':'최대 매매가(만원)',
                      'commute_minutes':'최대 편도 통근시간(분)', 'commute_mode':'통근수단',
                      'preferred_ages':'희망 주민 연령대', 'preferences':'생활 선호(0~5)'}
            st.json({labels.get(key, key):value for key,value in current.items()})
    prompt = st.chat_input('예: 시청 출근, 보증금 천에 월세 70, 지하철 40분', max_chars=2000)
    if prompt:
        try:
            with st.spinner('말씀하신 조건을 정리하고 있어요...'):
                patch = extract_patch(prompt, current, history, os.getenv('GMS_KEY', ''),
                                      os.getenv('GMS_MODEL', '').strip() or DEFAULT_MODEL)
                updated = merge_conditions(current, patch)
            question = next_question(updated)
            if not patch:
                answer = '조건을 확실히 이해하지 못했어요. 구체적으로 다시 알려주세요. '
            else:
                answer = '말씀하신 조건을 반영했어요. '
            if question:
                answer += question
            else:
                answer += '기본 조건이 모였어요. 공원·따릉이·주변 연령대 등 더 원하는 점이 있나요? '
                answer += '실거래가와 동네 근거 검색은 아직 연결 중이라 지금은 최종 추천지를 제시할 수 없어요.'
            st.session_state.conversation_conditions = updated
            mapped = map_conditions(updated)
            if mapped:
                st.session_state.housing_conditions = mapped
            elif (st.session_state.get('housing_conditions') or {}).get('source') == 'conversation':
                st.session_state.housing_conditions = None
            st.session_state.housing_chat = (history + [
                {'role':'user','content':prompt}, {'role':'assistant','content':answer}])[-40:]
            st.rerun()
        except ConversationError as error:
            st.warning(str(error))
    if st.button('대화와 대화 조건 초기화', key='reset_housing_chat'):
        st.session_state.housing_chat = []
        st.session_state.conversation_conditions = {}
        if (st.session_state.get('housing_conditions') or {}).get('source') == 'conversation':
            st.session_state.housing_conditions = None
        st.rerun()
