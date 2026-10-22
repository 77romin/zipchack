"""장소 단위의 현재 상황과 시설 정보. 미제공을 0이나 이용 가능으로 해석하지 않는다."""
import pandas as pd
import streamlit as st

def display(value,suffix=""):
    if value is None or value=="": return "미제공"
    return f"{value:,.0f}{suffix}" if isinstance(value,(int,float)) else str(value)+suffix

def rate_chart(rates,label):
    rows=[{"구분":k,"비율(%)":v} for k,v in rates.items() if v is not None]
    if not rows:
        st.info(f"{label} 정보가 제공되지 않았습니다.")
        return
    st.bar_chart(pd.DataFrame(rows).set_index("구분"),y="비율(%)")
    st.dataframe(rows,hide_index=True)

def render_citydata(data):
    st.subheader(f"현재 동네 상황 · {data['area_name'] or '조회 장소'}")
    if data.get("replacement")=="Y":
        st.warning("서울시 대체 데이터입니다. 현재 실측값으로 단정할 수 없습니다.")
    a,b,c=st.columns(3)
    a.metric("혼잡도",data["congestion"] or "미제공")
    low,high=data["population_min"],data["population_max"]
    b.metric("현재 추정 인구",f"{low:,.0f}~{high:,.0f}명" if low is not None and high is not None else "미제공")
    rate=data["resident_rate"]
    c.metric("상주 인구 비율",f"{rate:g}%" if rate is not None else "미제공")
    st.caption(f"인구 기준: {data['population_time'] or '미제공'} · 조회: {data.get('queried_at','미확인')}")
    tabs=st.tabs(["인구 구성","주차장","지하철","전기차 충전","대기환경","상권"])
    with tabs[0]:
        st.caption("현재 장소에 있는 통신 기반 추정 인구입니다. 거주민만의 성별·연령 구성이 아니며 성별 비율로 안전성을 판단하지 않습니다.")
        rate_chart(data.get("gender_rates",{}),"현재 인구 성별 구성")
        rate_chart(data["age_rates"],"현재 인구 연령 구성")
        st.caption("상주 비율과 전체 인구 연령 비율을 곱해 거주민 연령 분포로 해석하지 않습니다.")
    with tabs[1]:
        rows=data.get("parking",[])
        if rows:
            st.caption(f"응답에 포함된 주차장 {len(rows):,}곳 · 미제공 실시간 값은 이용 가능 면수로 표시하지 않습니다.")
            st.dataframe([{"주차장":r['name'],"주소":r['address'],"수용 면수":r['capacity'],
                "실시간 제공":r['realtime'] or '미확인',"주차 가능 면수":r['available'],
                "유무료 코드":r['paid'],"기본요금(원)":r['base_fee'],"기본시간(분)":r['base_minutes'],
                "기준 시각":r['updated_at']} for r in rows],hide_index=True)
        else: st.info("주차장 자료가 응답에 없습니다. 주변에 주차장이 없다는 뜻은 아닙니다.")
    with tabs[2]:
        rows=data.get("subways",[])
        if rows:
            st.caption(f"응답 역·노선 {len(rows):,}건 · 동일 역의 여러 호선은 구분합니다. 출퇴근시간은 별도 길찾기로 확인해야 합니다.")
            st.dataframe([{"역명":r['name'],"호선":r['line'],"주소":r['address']} for r in rows],hide_index=True)
        else: st.info("지하철역 자료가 응답에 없습니다.")
    with tabs[3]:
        rows=data.get("ev_stations",[])
        if rows:
            st.dataframe([{"충전소":r['name'],"주소":r['address'],"운영시간":r['hours'],
                "이용제한 코드":r['restricted'],"이용제한 설명":r['restriction'],"주차료 코드":r['parking_fee'],
                "응답 충전기 수":len(r['chargers'])} for r in rows],hide_index=True)
            for r in rows:
                if r['chargers']:
                    with st.expander(f"{r['name']} · 충전기 상태"):
                        st.dataframe([{"충전기 ID":c['id'],"타입 코드":c['type'],"상태 코드":c['status_code'],
                            "출력(kW)":c['output_kw'],"방식":c['method'],"갱신 시각":c['updated_at']} for c in r['chargers']],hide_index=True)
            st.caption("충전소 존재가 즉시 충전 가능함을 뜻하지 않습니다. 이용 제한과 상태 코드를 확인해야 합니다.")
        else: st.info("충전소 자료가 응답에 없습니다.")
    with tabs[4]:
        air=data.get('air',{})
        a,b,c=st.columns(3)
        a.metric("통합대기환경등급",display(air.get('grade')))
        b.metric("통합대기환경지수",display(air.get('value')))
        c.metric("결정물질",display(air.get('main_pollutant')))
        a,b=st.columns(2)
        a.metric("미세먼지 PM10",display(data['pm10'],' μg/m³'))
        b.metric("초미세먼지 PM2.5",display(data['pm25'],' μg/m³'))
        if air.get('message'): st.write(air['message'])
        st.caption(f"환경 기준: {data['weather_time'] or '미제공'} · 개별 건물의 관측값이나 장기 평균이 아닙니다.")
    with tabs[5]:
        commerce=data.get('commerce',{})
        a,b=st.columns(2)
        a.metric("장소 실시간 상권현황",display(commerce.get('level')))
        b.metric("신한카드 결제 건수",display(commerce.get('payment_count'),'건'))
        low,high=commerce.get('amount_min'),commerce.get('amount_max')
        st.write(f"결제 금액 범위(원본 단위): {display(low)} ~ {display(high)}")
        st.caption(f"상권 기준: {commerce.get('updated_at') or '미제공'} · 금액은 단위 환산 없이 원본값으로 표시합니다. 신한카드 내국인 표본으로 전체 매출·소비자·거주민을 대표하지 않습니다.")
        rows=commerce.get('industries',[])
        if rows:
            st.dataframe([{"대분류":r['category'],"중분류":r['subcategory'],"현황":r['level'],
                "결제 건수":r['payment_count'],"금액 하한(원본 단위)":r['amount_min'],"금액 상한(원본 단위)":r['amount_max'],
                "가맹점 수":r['merchant_count'],"가맹점 기준월":r['merchant_time']} for r in rows],hide_index=True)
        with st.expander("소비 구성 보기 · 인구 구성과 다름"):
            rate_chart(commerce.get('gender_rates',{}),'소비 성별 구성')
            rate_chart(commerce.get('age_rates',{}),'소비 연령 구성')
    st.link_button("출처 · 서울 실시간 도시데이터",data['source_url'])
