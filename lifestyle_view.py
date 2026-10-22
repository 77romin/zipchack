"""선택 동네 대표점 주변 시설과 별도 주민등록 연령 통계."""
import os
from datetime import datetime,timedelta,timezone
import streamlit as st
from geo import stations_within
from resident_api import fetch_residents,preferred_share,SOURCE_URL

def render_lifestyle(neighborhood,conditions,bikes=None,parks=None):
    if not neighborhood:
        return []
    st.subheader('선택 동네의 생활환경 확인')
    st.caption('동네 대표점 기준의 직선거리입니다. 개별 집에서 걷는 거리나 동네 전체의 접근성을 뜻하지 않습니다.')
    radius=st.select_slider('동네 대표점 주변 확인 반경 (m)',options=[300,500,1000,1500],value=500,key='lifestyle_radius')
    markers=[]
    for key,label,data,records in [('parks','공원',parks,(parks or {}).get('parks')),
                                  ('bikes','따릉이',bikes,(bikes or {}).get('stations'))]:
        if records is None:
            st.info(label+' 위치 자료 미확인 · 공식 자료를 불러오면 확인할 수 있습니다.')
            continue
        nearby=stations_within(records,neighborhood['latitude'],neighborhood['longitude'],radius/1000)
        st.metric(f'대표점 {radius}m 안의 '+label,f'{len(nearby)}곳')
        st.caption(f"{label} 출처: {data.get('source_url','미제공')} · 자료: {data.get('origin','업로드 파일')} · 불러온 시각: {data.get('queried_at','원본 기준일 확인 필요')}")
        st.caption(f'반경 밖이나 자료에 없는 시설은 포함하지 않습니다. {data.get("skipped",0)}행 제외·중복. 0곳은 입력 자료의 좌표 기준이며 실제 시설 부재를 보장하지 않습니다.')
        if nearby:
            st.dataframe([{'시설':item['name'],'대표점에서 직선거리(m)':item['distance_m']} for item in nearby],hide_index=True)
        markers += [{**item,'kind':key,'kind_name':label,'detail':f'동네 대표점에서 직선 {item["distance_m"]}m'} for item in nearby]
    st.caption('공원 자료는 주요 공원 목록으로 소규모 시설 등이 누락될 수 있습니다. 따릉이는 위치만 확인하며 재고는 조회하지 않습니다.')
    st.subheader('법정동 주민등록 연령 구성')
    st.link_button('주민등록 인구 API 활용신청',SOURCE_URL)
    st.caption('주민등록 거주자 기준·외국인 제외. 실시간 유동인구와 다르며, 법정동 단위 통계를 사용합니다.')
    today=datetime.now(timezone(timedelta(hours=9)))
    month=st.text_input('주민등록 기준월 (YYYYMM)',value=(today.replace(day=1)-timedelta(days=1)).strftime('%Y%m'),key='resident_month')
    code=neighborhood.get('legal_code')
    if not code:
        st.info('법정동 코드 미확인 · 이전 위치 캐시라면 앱 재시작 후 동네 위치를 다시 조회해주세요.')
        return markers
    cache=st.session_state.setdefault('resident_data',{})
    identity=code+':'+month
    if st.button('선택 동네 주민등록 인구 조회',key='fetch_residents'):
        try:
            with st.spinner('주민등록 연령 통계를 확인합니다...'):
                cache[identity]=fetch_residents(code,month,os.getenv('MOIS_RESIDENT_API_KEY',''))
        except ValueError as error:
            cache.pop(identity,None)
            st.warning(str(error))
    data=cache.get(identity)
    if data:
        st.caption(f"기준월 {data['month']} · 조회 시각 {data['queried_at']} · 법정동 코드 {code}")
        st.metric('주민등록 거주자',f"{data['total']:,}명")
        ages=(conditions or {}).get('preferred_ages',[])
        share=preferred_share(data,ages)
        if share is not None:
            st.metric('희망 연령대 비율 ('+'·'.join(f'{age}대' for age in ages)+')',f'{share:g}%')
        st.bar_chart({f'{age}대' if age<100 else '100세 이상':count for age,count in data['ages'].items()})
    else:
        st.info('주민등록 연령 구성은 아직 미확인입니다. 키 설정과 조회가 필요하며 추천 점수에 임의 반영하지 않습니다.')
    return markers
