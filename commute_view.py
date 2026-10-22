"""외부 길찾기와 명시적인 사용자 확인 기록. 링크 열기는 검증 완료가 아니다."""
from datetime import datetime,time,timezone,timedelta
import os
import streamlit as st
from commute import MODES,route_url,record_key,make_record,assess_record,address_origin_candidates,resolve_building

def render_commute(neighborhood,destination,conditions,result,points):
    st.subheader('통근시간 확인')
    records=st.session_state.setdefault('commute_records',{})
    context={'records':records,'destination':destination,'workplace_query':(conditions or {}).get('workplace'),'points':points}
    st.caption('카카오맵 길찾기에서 총소요시간을 확인한 뒤 직접 기록합니다. 앱이 경로시간을 자동 수신·검증하지 않습니다.')
    if not neighborhood or not destination:
        st.info('후보 동네를 지도에 표시하고, 직장 검색 결과에서 도착지를 선택해주세요.')
        return context
    conditions=conditions or {}
    kind=st.radio('통근 출발지 기준',['동네 대표점','거래 주택 주소'],horizontal=True,key='commute_origin_kind')
    origin={**neighborhood,'origin_kind':'neighborhood'}
    if kind=='거래 주택 주소':
        district_code=result.get('district_code') if result else None
        dong=neighborhood.get('dong')
        candidates=address_origin_candidates(result,conditions,dong) if result and dong else []
        if not candidates:
            st.info('예산에 맞는 거래 중 정확한 지번을 확인할 수 있는 주소가 없습니다. 단독다가구·마스킹된 지번은 추정하지 않습니다.')
            return context
        candidate=st.selectbox('출발지로 확인할 거래 주소',candidates,format_func=lambda item:item['name']+' · '+item['address'],key='commute_building_candidate')
        cache=st.session_state.setdefault('commute_building_locations',{})
        if st.button('선택 주택 주소 위치 확인',key='resolve_commute_building'):
            try:
                cache[candidate['address']]=resolve_building(candidate,os.getenv('KAKAO_REST_API_KEY',''))
            except ValueError as error:
                cache.pop(candidate['address'],None); st.warning(str(error))
        origin=cache.get(candidate['address'])
        if not origin:
            st.info('선택한 주소의 위치를 먼저 확인해주세요.')
            return context
        st.caption('주소 대표 좌표입니다. 개별 호실·건물 출입구 위치나 현재 매물을 확인한 것은 아닙니다.')
    else:
        st.caption('동네 대표점 출발 경로입니다. 동네 안의 개별 주택에 같은 시간이 걸린다는 뜻은 아닙니다.')
    st.write('출발: '+origin['name']+' → 도착: '+destination.get('name',destination.get('address','직장')))
    st.caption('아래 링크를 누르면 이 출발지·도착지 좌표를 카카오맵에서 엽니다.')
    for mode in MODES:
        st.link_button(mode+' 길찾기 열기',route_url(origin,destination,mode))
    day=st.date_input('경로를 확인할 출발일',value=datetime.now(timezone(timedelta(hours=9))).date(),key='commute_departure_day')
    hour=st.time_input('출발 시각 (한국 시간)',value=time(8,30),key='commute_departure_time')
    departure=day.strftime('%Y-%m-%d')+' '+hour.strftime('%H:%M')
    context['departure']=departure
    default_mode=conditions.get('commute_mode','대중교통')
    mode=st.selectbox('기록할 이동수단',list(MODES),index=list(MODES).index(default_mode),key='commute_record_mode')
    identity=record_key(origin,destination,mode,departure)
    with st.form('commute_record_form'):
        minutes=st.number_input('카카오맵에서 확인한 편도 총소요시간 (분)',min_value=1,max_value=1440,value=None,step=1,key='commute_minutes_'+identity)
        confirmed=st.checkbox('카카오맵에서 같은 출발지·도착지·수단·출발일시의 총소요시간을 확인했어요.',key='commute_confirmed_'+identity)
        if st.form_submit_button('사용자 확인 통근시간 저장'):
            try:
                records[identity]=make_record(origin,destination,mode,departure,minutes,confirmed)
                st.success('사용자 확인값을 저장했습니다. 자동 검증값이 아닙니다.')
            except ValueError as error:
                st.warning(str(error))
    st.caption('길찾기 URL에는 출발일시가 포함되지 않습니다. 외부 카카오맵에서도 같은 일시를 선택해 확인해주세요. 경로가 없으면 시간을 입력하지 않고 미확인으로 남깁니다.')
    rows=[]
    for transport in MODES:
        key=record_key(origin,destination,transport,departure)
        saved=records.get(key)
        assessed=assess_record(saved,origin,destination,transport,departure,conditions.get('commute_minutes'))
        rows.append({'수단':transport,'사용자 확인 시간(분)':saved['minutes'] if saved else None,
                     '희망시간 비교':assessed['label'] if transport==conditions.get('commute_mode') else '참고 수단 · 희망 수단과 다름',
                     '확인 기록 시각':saved['recorded_at'] if saved else '미확인'})
    st.dataframe(rows,hide_index=True)
    if identity in records and st.button('현재 수단의 확인 기록 삭제',key='delete_commute_record'):
        records.pop(identity,None); st.rerun()
    return context
