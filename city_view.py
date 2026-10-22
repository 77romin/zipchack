"""도시데이터는 현재 상황으로만 표시한다. 거주민 연령이나 집별 관측값으로 해석하지 않는다."""
import streamlit as st

def render_citydata(data):
    st.subheader(f"현재 동네 상황 · {data['area_name'] or '조회 장소'}")
    if data.get("replacement")=="Y":
        st.warning("서울시 대체 데이터입니다. 현재 실측값으로 단정할 수 없습니다.")
    a,b,c=st.columns(3)
    a.metric("혼잡도",data["congestion"] or "미제공")
    low,high=data["population_min"],data["population_max"]
    b.metric("현재 추정 인구", f"{low:,.0f}~{high:,.0f}명" if low is not None and high is not None else "미제공")
    rate=data["resident_rate"]
    c.metric("상주 인구 비율",f"{rate:g}%" if rate is not None else "미제공")
    st.caption(f"인구 기준: {data['population_time'] or '미제공'} · 조회: {data.get('queried_at','미확인')}")
    st.caption("장소 단위 통신 기반 추정값입니다. 상주 비율은 전체 거주민 수가 아니며, 아래 연령 비율은 거주민만의 연령 분포가 아닙니다.")
    with st.expander("현재 인구 연령 구성·대기환경 보기"):
        rows=[{"연령대":label,"현재 인구 비율(%)":value} for label,value in data["age_rates"].items() if value is not None]
        if rows:
            st.dataframe(rows,hide_index=True)
        else:
            st.info("연령 구성 정보가 제공되지 않았습니다.")
        a,b=st.columns(2)
        a.metric("미세먼지 PM10",f"{data['pm10']:g} μg/m³" if data['pm10'] is not None else "미제공")
        b.metric("초미세먼지 PM2.5",f"{data['pm25']:g} μg/m³" if data['pm25'] is not None else "미제공")
        st.caption(f"환경 기준: {data['weather_time'] or '미제공'} · 개별 건물에서 측정한 값은 아닙니다.")
    st.link_button("출처 · 서울 실시간 도시데이터",data["source_url"])
