"""실거래 조회와 예산 필터. 현재 매물·적합도 순위로 표현하지 않는다."""
from datetime import datetime, timedelta, timezone
import os
import streamlit as st
from rent_api import DISTRICTS, SOURCES, RentDataError, fetch_rents, filter_budget

def render_rents(conditions):
    st.subheader('예산 안의 전월세 거래 기록')
    st.caption('과거 계약 기록입니다. 현재 매물·입주 가능 여부·통근시간을 확인한 결과가 아닙니다.')
    with st.expander('실거래 조회 범위',expanded=True):
        with st.form('rent_query_form'):
            district=st.selectbox('조회할 서울 자치구',list(DISTRICTS),index=1,key='rent_district')
            today=datetime.now(timezone(timedelta(hours=9)))
            previous=today.replace(day=1)-timedelta(days=1)
            month=st.text_input('계약월 (YYYYMM)',value=previous.strftime('%Y%m'),key='rent_month')
            categories=st.multiselect('주택 유형',list(SOURCES),default=['연립다세대','단독다가구','오피스텔'],key='rent_categories')
            submitted=st.form_submit_button('전월세 실거래 조회')
        st.caption('선택한 구·한 달만 조회하며 직장 반경이나 통근시간으로 선택된 범위가 아닙니다. 유형당 최대 5페이지를 조회합니다.')
        if not os.getenv('DATA_GO_KR_SERVICE_KEY','').strip():
            st.info('실거래 조회를 사용하려면 DATA_GO_KR_SERVICE_KEY를 설정해주세요. 아래 링크에서 필요한 주택 유형별 활용신청을 할 수 있습니다.')
            for category,(_,identifier) in SOURCES.items():
                st.link_button(category+' 전월세 API 신청',f'https://www.data.go.kr/data/{identifier}/openapi.do')
    if submitted:
        st.session_state.pop('rent_result',None)
        try:
            with st.spinner('공식 전월세 거래 기록을 불러오고 있어요...'):
                st.session_state.rent_result=fetch_rents(DISTRICTS[district],month.strip(),categories,os.getenv('DATA_GO_KR_SERVICE_KEY',''))
        except RentDataError as error:
            st.warning(str(error))
    result=st.session_state.get('rent_result')
    if not result:
        return
    name=next(name for name,code in DISTRICTS.items() if code==result['district_code'])
    st.caption(f"조회 범위: 서울 {name} · 계약월 {result['month']} · 조회 시각 {result['queried_at']}")
    successful=0
    for status in result['statuses']:
        if status['error']:
            st.warning(status['category']+': '+status['error'])
        else:
            successful+=1
            st.caption(f"{status['category']}: 응답 {status['received']:,}/{status['total']:,}건 · 형식·지역·날짜 미확인 제외 {status['skipped']:,}건")
            if not status['complete']:
                st.warning(status['category']+': 조회 상한에 도달한 일부 결과입니다. 전체 거래를 확인한 결과가 아닙니다.')
    if not successful:
        st.info('성공한 조회가 없습니다. 거래가 없다는 뜻은 아닙니다.')
        return
    filtered=filter_budget(result['rows'],conditions or {})
    if filtered is None:
        st.info('대화나 왼쪽 입력에서 전월세 예산을 먼저 지정해주세요. 매매 기록은 아직 지원하지 않습니다.')
        return
    st.metric('현재 예산에 맞는 조회 거래',f'{len(filtered):,}건')
    if not filtered:
        st.info('이번에 조회한 기록 안에는 예산에 맞는 거래가 없습니다. 조회 기간·지역을 넓힐 수 있으며 현재 매물이 없다는 뜻은 아닙니다.')
        return
    st.dataframe([{'유형':row['category'],'법정동':row['dong'],'건물명':row['name'] or '미제공',
                   '계약일':row['contract_date'],'보증금(만원)':row['deposit'],'월세(만원)':row['monthly_rent'],
                   '면적(㎡)':row['area'],'면적 기준':row['area_type'],'계약 구분':row['contract_type'] or '미제공'}
                  for row in sorted(filtered,key=lambda row:row['contract_date'],reverse=True)],hide_index=True)
    st.caption('최신 계약일 순입니다. 적합도 순위가 아닙니다. 대화에서 예산을 바꾸면 저장된 조회 기록에 즉시 다시 적용합니다. 관리비·공원·거주민 연령·통근시간은 이 필터에 포함되지 않습니다.')
