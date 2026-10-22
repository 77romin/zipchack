"""실거래 조회와 예산 필터. 현재 매물·적합도 순위로 표현하지 않는다."""
from datetime import datetime, timedelta, timezone
import os
import streamlit as st
from housing_candidates import build_candidates
from rent_api import DISTRICTS, SOURCES, RentDataError, fetch_rents, filter_budget, service_keys, KEY_NAMES

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
        configured = service_keys(os.environ)
        missing = [category for category in categories if not configured[category]]
        if missing:
            st.info('키 미설정: ' + ', '.join(missing) + '. 각 서비스의 키를 .env.example의 유형별 항목에 입력해주세요.')
            for category,(_,identifier) in SOURCES.items():
                st.link_button(category+' 전월세 API 신청',f'https://www.data.go.kr/data/{identifier}/openapi.do')
    if submitted:
        st.session_state.pop('rent_result',None)
        try:
            with st.spinner('공식 전월세 거래 기록을 불러오고 있어요...'):
                st.session_state.rent_result=fetch_rents(DISTRICTS[district],month.strip(),categories,service_keys(os.environ))
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
    candidates=build_candidates(result,conditions or {})
    st.subheader('예산 기준 탐색 후보 동네')
    st.dataframe([{'법정동':group['dong'],'예산에 맞는 거래(건)':group['count'],
                   '주택 유형별 건수':', '.join(f'{key} {value}건' for key,value in group['categories'].items()),
                   '최근 계약일':group['latest']} for group in candidates['groups']],hide_index=True)
    st.caption('예산에 맞는 조회 거래 건수 내림차순입니다. 종합 추천 순위·현재 매물 수가 아닙니다. 오른쪽 대화에서 “추천해줘”라고 하면 동일한 근거를 안내합니다.')
    dong=st.selectbox('거래를 살펴볼 동네',['전체']+[group['dong'] for group in candidates['groups']],key='candidate_dong')
    if dong!='전체':
        filtered=[row for row in filtered if row['dong']==dong]
    st.dataframe([{'유형':row['category'],'법정동':row['dong'],'건물명':row['name'] or '미제공',
                   '계약일':row['contract_date'],'보증금(만원)':row['deposit'],'월세(만원)':row['monthly_rent'],
                   '면적(㎡)':row['area'],'면적 기준':row['area_type'],'계약 구분':row['contract_type'] or '미제공'}
                  for row in sorted(filtered,key=lambda row:row['contract_date'],reverse=True)],hide_index=True)
    st.caption('최신 계약일 순입니다. 적합도 순위가 아닙니다. 대화에서 예산을 바꾸면 저장된 조회 기록에 즉시 다시 적용합니다. 관리비·공원·거주민 연령·통근시간은 이 필터에 포함되지 않습니다.')
