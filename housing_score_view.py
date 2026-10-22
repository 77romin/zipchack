"""생활 선호 비교 표와 계산 근거. 재조회 없이 최신 조건으로 계산한다."""
import streamlit as st
from housing_scores import compare_candidates,preference_weights,score_reply,current_month

def render_housing_scores(result,conditions,points,bikes=None,parks=None):
    context={'points':points,'bikes':bikes,'parks':parks,
             'residents':st.session_state.get('resident_data',{}),
             'month':st.session_state.get('resident_month') or current_month()}
    st.subheader('내 생활 선호로 동네 비교')
    st.caption('예산에 맞는 거래가 있는 동네의 생활 선호 비교입니다. 현재 매물·통근시간·주거 종합 적합도 순위가 아닙니다.')
    if not result:
        st.info('전월세 거래를 먼저 조회해주세요.')
        return context
    if not preference_weights(conditions or {}):
        st.info('대화에서 공원·따릉이·희망 주민 연령대 선호를 알려주세요. 중요도 0은 제외합니다.')
        return context
    rows=compare_candidates(result,conditions,context)
    if not rows:
        st.info('현재 조회 범위와 예산에 맞는 거래가 없어 비교할 후보가 없습니다.')
        return context
    if any(row['rank'] is None for row in rows):
        st.caption('미확정 후보가 있습니다. 숫자로 표시된 순위도 확인된 후보끼리의 비교이며 모든 후보의 최종 순위가 아닙니다.')
    st.dataframe([{'동네':row['dong'],'예산에 맞는 거래':row['count'],
                   '생활 선호 점수':row['score'],'가중 근거 확인율(%)':row['coverage'],
                   '생활 선호 비교 순위':str(row['rank']) if row['rank'] is not None else '미확정',
                   '미확인/제한':', '.join(row['missing']+row['issues']) or '선택 지표 확인'} for row in rows],hide_index=True)
    with st.expander('점수 계산과 동네별 근거'):
        st.write('공원·따릉이는 대표점에서 자료 내 가장 가까운 좌표까지의 직선거리 d(m)를 사용해 max(0, 1-d/1500)×100으로 계산합니다. 주민등록 연령은 희망 연령대 비율(%)을 사용합니다. 중요도 1~5로 가중 평균하고 0은 제외합니다. 연령대 선호가 있지만 연령 중요도를 말하지 않았다면 3을 사용합니다.')
        st.write('누락 항목은 0점으로 채우지 않고 알려진 항목만의 참고 점수를 보여줍니다. 선택 지표·실거래 조회 범위의 미확인이나 제외 기록이 있으면 순위를 부여하지 않습니다. 점수 동률은 공동 순위입니다. 확인율은 근거 완전성이나 정확도 확률이 아닙니다. 공원 목록의 범위 한계와 원본 기준일을 확인해주세요.')
        for row in rows:
            st.write(row['dong'])
            if row['details']:
                st.dataframe(row['details'],hide_index=True)
    return context
