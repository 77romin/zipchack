import requests
from kakao_api import search_workplace

import os
from pathlib import Path
from map_view import build_map_html
from bike_data import load_stations, SOURCE_URL
from geo import stations_within
from seoul_api import fetch_citydata, SeoulDataError
from city_view import render_citydata
from city_preferences import preference_controls, render_place_comparison
from city_match import facility_markers

import streamlit as st
from dotenv import load_dotenv

# 다른 화면 출력보다 먼저 설정
st.set_page_config(
    page_title="집.착",
    page_icon="🏠",
    layout="wide",
)


# app.py와 같은 폴더에 있는 .env를 읽습니다.
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)


kakao_javascript_key = os.getenv(
    "KAKAO_JAVASCRIPT_KEY", ""
).strip()

kakao_rest_api_key = os.getenv(
    "KAKAO_REST_API_KEY", ""
).strip()


# 입력한 조건을 보관할 공간
if "housing_conditions" not in st.session_state:
    st.session_state.housing_conditions = None


# 왼쪽 설정 영역
with st.sidebar:
    st.title("집.착")
    st.caption("내 맘에 착, 내 삶에 착.")

    st.subheader("나의 조건")

    with st.form("housing_conditions_form"):
        workplace = st.text_input(
            "직장 주소 또는 장소명",
            placeholder="예: 서울특별시 중구 세종대로 110",
        )

        deposit_max = st.number_input(
            "최대 보증금 (만원)",
            min_value=0,
            value=1000,
            step=100,
        )

        rent_max = st.number_input(
            "최대 월세 (만원)",
            min_value=0,
            value=70,
            step=5,
        )

        search_radius_km = st.slider(
            "직장 기준 탐색 반경 (km)",
            min_value=0.5,
            max_value=10.0,
            value=3.0,
            step=0.5,
            help="직선거리 기준이며 실제 통근시간과는 다릅니다.",
        )

        st.divider()
        st.subheader("내 생활 취향")
        st.caption("0은 반영하지 않음, 5는 매우 중요입니다.")

        park_importance = st.slider(
            "공원 접근성",
            min_value=0,
            max_value=5,
            value=3,
        )

        bike_importance = st.slider(
            "따릉이 대여소 접근성",
            min_value=0,
            max_value=5,
            value=3,
        )

        age_importance = st.slider(
            "희망 연령대의 주민 비율",
            min_value=0,
            max_value=5,
            value=2,
        )

        preferred_age_range = st.slider(
            "관심 있는 주민 연령 범위",
            min_value=0,
            max_value=100,
            value=(20, 39),
            help="연령대 중요도가 0이면 추천에 반영하지 않습니다.",
        )

        submitted = st.form_submit_button(
            "조건 적용",
            use_container_width=True,
        )

    if submitted:
        if not workplace.strip():
            st.warning("직장 주소 또는 장소명을 입력해주세요.")
        else:
            st.session_state.housing_conditions = {
                "workplace": workplace.strip(),
                "deposit_max": deposit_max,
                "rent_max": rent_max,
                "search_radius_km": search_radius_km,
                "preferences": {
                    "park": park_importance,
                    "bike": bike_importance,
                    "age": age_importance,
                },
                "preferred_age_range": list(preferred_age_range),
            }
            st.success("조건을 저장했습니다.")



# 메인 화면
st.title("나에게 착 맞는 집과 동네")
st.caption("예산부터 출근길까지, 내 생활을 기준으로 찾아보세요!")

conditions = st.session_state.housing_conditions

if conditions is None:
    st.info("왼쪽에서 주거 조건을 입력하고 적용해주세요.")
else:
    st.write(f"**직장:** {conditions['workplace']}")

    st.caption(
        f"직장 기준 탐색 반경: "
        f"{conditions.get('search_radius_km', 3.0):g}km "
        f"· 직선거리 기준"
    )

    st.caption(
        f"월세 탐색 · "
        f"보증금 {conditions['deposit_max']:,}만원 이하 · "
        f"월세 {conditions['rent_max']:,}만원 이하"
    )

    preferences = conditions.get("preferences")

    if preferences is not None:
        age_min, age_max = conditions["preferred_age_range"]

        preference_labels = []

        if preferences["park"] > 0:
            preference_labels.append(
                f"공원 {preferences['park']}/5"
            )

        if preferences["bike"] > 0:
            preference_labels.append(
                f"따릉이 {preferences['bike']}/5"
            )

        if preferences["age"] > 0:
            preference_labels.append(
                f"{age_min}~{age_max}세 주민 비율 "
                f"{preferences['age']}/5"
            )

        if preference_labels:
            st.caption(
                "적용한 선호 · " + " · ".join(preference_labels)
            )
        else:
            st.caption(
                "생활 선호 없이 예산 조건으로 탐색합니다."
            )

        with st.expander("저장된 조건 확인"):
            st.json(conditions)


workplace_location = None
if "workplace_search_revision" not in st.session_state:
    st.session_state.workplace_search_revision = 0

if conditions is not None:
    query = conditions["workplace"]

    # 적용한 직장 입력이 바뀌면 이전 검색 결과를 비웁니다.
    previous_search = st.session_state.get(
        "workplace_search", {}
    )

    if previous_search.get("query") != query:
        st.session_state.workplace_search = {
            "query": query,
            "results": [],
        }

    with st.sidebar:
        st.divider()
        st.subheader("직장 위치 확인")

        if st.button("직장 검색", use_container_width=True):
            st.session_state.workplace_search_revision += 1
            st.session_state.workplace_search["results"] = []

            if not kakao_rest_api_key:
                st.warning(
                    ".env에 KAKAO_REST_API_KEY를 설정해주세요."
                )
            else:
                try:
                    with st.spinner("직장을 찾고 있습니다..."):
                        results = search_workplace(
                            query, kakao_rest_api_key
                        )

                    st.session_state.workplace_search[
                        "results"
                    ] = results

                    if not results:
                        st.info(
                            "검색 결과가 없습니다. "
                            "주소나 장소명을 더 구체적으로 입력해주세요."
                        )

                except requests.exceptions.RequestException:
                    st.error(
                        "직장 검색 요청에 실패했습니다. "
                        "REST API 키와 네트워크 상태를 확인해주세요."
                    )

        results = st.session_state.workplace_search["results"]

        if results:
            workplace_location = st.selectbox(
                "검색 결과에서 직장을 선택해주세요.",
                options=results,
                index=None,
                placeholder="직장 선택",
                format_func=lambda item: (
                    f"{item['name']} · {item['address']}"
                ),
                key=f"workplace_selection_{query}_{st.session_state.workplace_search_revision}",
            )

            if workplace_location:
                st.caption(
                    f"선택한 위치: {workplace_location['address']}"
                )


city_data = None
with st.sidebar:
    st.divider()
    st.subheader("서울 현재 상황")
    st.caption("공식 제공 장소만 조회할 수 있습니다. 선택한 직장 위치와 자동 연결된 데이터가 아닙니다.")
    with st.form("citydata_form"):
        city_area = st.text_input("공식 장소명 / 코드", value="광화문·덕수궁")
        city_submitted = st.form_submit_button("현재 상황 조회")
    if city_submitted:
        st.session_state.pop("city_data", None)
        seoul_key = os.getenv("SEOUL_OPEN_DATA_API_KEY", "").strip()
        try:
            with st.spinner("서울시 도시데이터를 조회합니다..."):
                st.session_state.city_data = fetch_citydata(city_area, seoul_key)
        except SeoulDataError as error:
            st.warning(str(error))
    city_data = st.session_state.get("city_data")

with st.sidebar:
    with st.expander("도시환경 비교 선호 설정"):
        city_preferences = preference_controls()

city_facilities = []
if city_data:
    with st.sidebar:
        facility_layers = st.multiselect(
            "도시데이터 시설 지도 레이어", ["주차장", "지하철역", "전기차충전소"],
            default=["지하철역"], key="city_facility_layers",
        )
        layer_keys = {"주차장":"parking", "지하철역":"subways", "전기차충전소":"ev_stations"}
        city_facilities = facility_markers(
            city_data, [layer_keys[x] for x in facility_layers], workplace_location,
            conditions.get("search_radius_km",3.0) if conditions else 3.0,
        )
        st.caption(f"조회 장소 시설 핀 {len(city_facilities)}개 · 직장 선택 시 탐색 반경 안의 좌표만 표시합니다.")

nearby_stations = []
with st.sidebar:
    st.divider()
    st.subheader("따릉이 대여소 위치")
    st.caption("공식 위치 파일을 불러옵니다. 실시간 재고는 사용하지 않습니다.")
    st.link_button("공식 위치 자료 받기", SOURCE_URL)
    bike_file = st.file_uploader("대여소 위치 CSV / XLSX", type=["csv", "xlsx"])
    if bike_file is not None:
        try:
            bike_result = load_stations(bike_file.getvalue(), bike_file.name)
            st.caption(f"위치 {len(bike_result['stations']):,}개 · 제외/중복 {bike_result['skipped']:,}행")
            if workplace_location:
                nearby_stations = stations_within(
                    bike_result["stations"], workplace_location["latitude"],
                    workplace_location["longitude"], conditions.get("search_radius_km", 3.0),
                )
                st.caption(f"탐색 반경 안 대여소 {len(nearby_stations):,}개")
                if not nearby_stations:
                    st.info("불러온 위치 자료에 탐색 반경 안 대여소가 없습니다.")
            else:
                st.info("직장 위치를 선택하면 주변 대여소를 표시합니다.")
        except ValueError as error:
            st.warning(str(error))

map_column, chat_column = st.columns([2, 1], gap="large")

with map_column:
    st.subheader("추천 지도")
    if not kakao_javascript_key:
        st.warning(".env에 KAKAO_JAVASCRIPT_KEY를 설정해주세요.")
    else:
        radius_km = conditions.get("search_radius_km", 3.0) if conditions else 3.0
        st.iframe(
            build_map_html(kakao_javascript_key, workplace_location, radius_km, nearby_stations, city_facilities),
            height=530,
        )
    st.caption("파란 원은 직선거리 탐색 범위이며 실제 통근 가능 영역이 아닙니다.")

    if nearby_stations:
        with st.expander("주변 따릉이 대여소 목록"):
            st.caption("출처: 서울특별시 대여소 위치 자료 · 자료 기준일은 내려받은 원본에서 확인해주세요.")
            st.dataframe([
                {"대여소":x["name"], "직장에서 직선거리(m)":x["distance_m"]}
                for x in nearby_stations
            ], hide_index=True)

    if city_data:
        render_citydata(city_data)
    render_place_comparison(city_data, city_preferences)

with chat_column:
    st.subheader("집.착과 대화하기")

    with st.container(border=True, height=500):
        with st.chat_message("assistant"):
            st.write(
                "안녕하세요! 어떤 집과 동네를 찾고 계신가요?"
            )
