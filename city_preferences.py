"""도시환경 비교 설정과 결과. 서버에서 결정한 데이터만 지도에 전달한다."""
import streamlit as st
from city_match import FEATURE_LABELS,evaluate_place,upsert_snapshot,comparison_rows

def preference_controls():
    st.subheader("현재환경 비교 기준")
    st.caption("주거 예산·거주민 연령 선호와 별개인 장소 비교입니다. 중요도 0은 제외합니다.")
    defaults={'parking':0,'subway':2,'ev':0,'air':2,'commerce':0,'age':0}
    with st.form('city_preferences_form'):
        weights={key:st.slider(label+' 중요도',0,5,defaults[key],key='city_weight_'+key) for key,label in FEATURE_LABELS.items()}
        ages=st.multiselect('선호하는 현재 인구 연령대',['0~10세','10대','20대','30대','40대','50대','60대','70대 이상'],default=['20대','30대'])
        direction=st.selectbox('현재 상권 활동 선호',['활발한 곳','활동이 적은 곳'])
        if st.form_submit_button('현재환경 선호 적용'):
            st.session_state.city_preferences={'weights':weights,'age_groups':ages,'commerce_direction':direction}
    return st.session_state.get('city_preferences',{'weights':defaults,'age_groups':['20대','30대'],'commerce_direction':'활발한 곳'})

def render_place_comparison(data,preferences):
    st.subheader('내 기준으로 현재환경 비교')
    st.caption('장소 단위의 현재환경 점수이며 집 추천 순위·거주 적합도·안전성·통근시간이 아닙니다. 서로 다른 조회 시각을 함께 확인하세요.')
    if data:
        result=evaluate_place(data,preferences)
        if result['score'] is None:
            st.info('적용할 지표가 없거나 데이터가 부족합니다. 비교 기준과 제공값을 확인해주세요.')
        else:
            a,b=st.columns(2)
            a.metric('현재환경 점수'+(' · 참고값' if not result['complete'] else ''),f"{result['score']:g}/100")
            b.metric('가중 데이터 충족률',f"{result['coverage']:g}%")
        if data.get('replacement')=='Y': st.warning('대체 데이터가 포함된 조회 결과입니다. 비교 시 주의해주세요.')
        if result['missing']: st.warning('미확인: '+', '.join(result['missing'])+' · 확정 순위를 부여하지 않습니다.')
        if result['details']: st.dataframe(result['details'],hide_index=True)
        if st.button('이 장소를 비교 목록에 추가',key='add_city_comparison'):
            current=st.session_state.get('city_comparisons',{})
            if len(current)>=10 and not (data.get('area_code') or data.get('area_name')) in current:
                st.warning('비교 목록은 최대 10곳입니다. 목록을 비우고 추가해주세요.')
            else:
                st.session_state.city_comparisons=upsert_snapshot(current,data)
    snapshots=st.session_state.get('city_comparisons',{})
    if snapshots:
        st.dataframe(comparison_rows(snapshots,preferences),hide_index=True)
        if st.button('비교 목록 비우기',key='clear_city_comparison'):
            st.session_state.city_comparisons={}
            st.rerun()
    with st.expander('점수 계산 기준'):
        st.write('선택 지표를 0~100으로 변환해 중요도 가중 평균을 계산합니다. 주차장·역/노선은 5건, 이용제한 없음 충전소는 3곳에서 100점에 도달합니다. 대기환경은 max(0, 1-지수/500), 상권 활동은 결제건수/(결제건수+1000), 연령은 선택 구간 비율의 합입니다. 이는 비교용 자체 규칙이며 공식 평가가 아닙니다.')
        st.write('빈 시설 목록은 미확인으로 처리합니다. 지표가 빠지면 알려진 값만의 참고점수와 충족률을 표시하고 순위는 미확정으로 남깁니다. 상권 결제건수가 적다고 조용한 주거지라는 뜻은 아닙니다. 성별 비율은 정보 표시만 하고 점수에는 반영하지 않습니다.')
