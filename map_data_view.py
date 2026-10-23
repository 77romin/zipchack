"""거래 조건 없이도 지역별 지도 자료를 불러온다."""
import os
from datetime import datetime,timedelta,timezone
import streamlit as st
from neighborhood_data import load_neighborhoods
from neighborhood_api import resolve_neighborhood
from resident_api import fetch_residents
from age_colors import age_composition

@st.cache_data(ttl=86400,show_spinner=False)
def locate(code,name):
    return resolve_neighborhood(code[:5],name,os.getenv('KAKAO_REST_API_KEY',''))

@st.cache_data(ttl=86400,show_spinner=False)
def population(code,month):
    return fetch_residents(code,month,os.getenv('MOIS_RESIDENT_API_KEY',''))

def map_region(rental_neighborhood=None):
    rows,_=load_neighborhoods();by_code={row['code']:row for row in rows}
    if rental_neighborhood and rental_neighborhood.get('legal_code') in by_code:
        old=st.session_state.get('map_rental_code')
        if old!=rental_neighborhood['legal_code']:
            st.session_state.map_region_code=rental_neighborhood['legal_code']
            st.session_state.map_rental_code=rental_neighborhood['legal_code']
    if 'map_region_code' not in st.session_state:st.session_state.map_region_code='1114016200'
    code=st.selectbox('지도에서 살펴볼 동네',list(by_code),format_func=lambda c:by_code[c]['full_name'],key='map_region_code')
    item=by_code[code]
    identity=code
    errors=st.session_state.setdefault('map_data_errors',{})
    if st.button('선택 동네 자료 다시 불러오기',key='reload_map_data'):
        locate.clear();population.clear();errors.pop(identity,None)
    if errors.get(identity):
        st.warning(errors[identity]);return None,None
    try:
        with st.spinner('동네 위치와 연령 자료를 불러옵니다...'):
            point=locate(code,item['name'])
        if point.get('legal_code')!=code:
            raise ValueError('조회한 위치의 법정동 코드가 선택 지역과 다릅니다.')
    except ValueError:
        errors[identity]='선택 지역의 위치를 불러오지 못했습니다. 카카오 REST 키·네트워크를 확인한 뒤 다시 불러오세요.'
        st.warning(errors[identity]);return None,None
    today=datetime.now(timezone(timedelta(hours=9)))
    month=(today.replace(day=1)-timedelta(days=1)).strftime('%Y%m')
    residents=st.session_state.setdefault('resident_data',{})
    resident_key=code+':'+month
    if resident_key not in residents:
        try:
            with st.spinner('선택 동네 주민등록 연령 구성을 조회합니다...'):
                residents[resident_key]=population(code,month)
        except ValueError:
            st.warning('연령 자료를 조회하지 못했습니다. 주민등록 API 키·권한·네트워크를 확인해주세요.')
    st.caption('따릉이 위치: 서울시 공식 2026년 6월 파일 · 연령: '+month+' 주민등록 거주자 · 유동인구 아님')
    resident=residents.get(resident_key)
    if resident and resident.get('total'):
        st.caption('선택 동네 주민 구성: '+ ' · '.join(f"{age}대 {resident['ages'][age]/resident['total']*100:.1f}%" for age in [20,30,60]))
        rates={str(age):count/resident['total']*100 for age,count in resident['ages'].items() if count is not None}
        st.session_state.setdefault('map_age_regions',{})[code]={'code':code,'name':item['full_name'],
            'latitude':point['latitude'],'longitude':point['longitude'],'month':month,'composition':age_composition(rates)}
    st.caption('색상은 20~39세와 60세 이상 비중 비교입니다. 지역 전체 평균 나이 또는 좋고 나쁨의 점수가 아닙니다.')
    if st.button('같은 구 동네 색상 비교 불러오기 (최대 8곳)',key='load_age_comparison'):
        candidates=[row for row in rows if row['code'][:5]==code[:5] and row['code']!=code][:7]
        failures=[]
        with st.spinner('같은 자치구의 동네별 연령 구성을 비교합니다...'):
            for other in candidates:
                try:
                    p=locate(other['code'],other['name'])
                    if p.get('legal_code')!=other['code']:raise ValueError()
                    d=population(other['code'],month)
                    if not d.get('total'):raise ValueError()
                    rates={str(age):count/d['total']*100 for age,count in d['ages'].items() if count is not None}
                    residents[other['code']+':'+month]=d
                    st.session_state.setdefault('map_age_regions',{})[other['code']]={'code':other['code'],'name':other['full_name'],
                        'latitude':p['latitude'],'longitude':p['longitude'],'month':month,'composition':age_composition(rates)}
                except ValueError:failures.append(other['full_name'])
        if failures:st.warning('자료 확인 실패: '+', '.join(failures))
        st.caption('선택 동네와 법정동 코드순 최대 7곳을 비교합니다. 서울 전체나 최근접 8곳을 뜻하지 않습니다.')
    extra={}
    if rental_neighborhood and rental_neighborhood.get('legal_code')==code:extra=rental_neighborhood
    return {**point,**extra,'legal_code':code,'dong':item['name'],'name':item['full_name'],
            'month':extra.get('month','미조회'),'count':extra.get('count',0)},month
