from app_startup import check_runtime
check_runtime()

import requests
from kakao_api import search_workplace

import os
from pathlib import Path
from map_view import build_map_html,map_asset_revision
from map_explore import map_card,read_boundaries,region_cards
from bike_data import load_stations, bundled_stations, SOURCE_URL
from map_data_view import map_region,district_regions
from boundary_data import bundled_boundaries
from map_viewport import render_viewport,update_population
from recommendations import recommendation_rows
from geo import stations_within
from seoul_api import fetch_citydata, SeoulDataError
from city_view import render_citydata
from city_preferences import preference_controls, render_place_comparison
from city_match import facility_markers
from chat_view import render_chat
from rag_view import render_rag
from rent_view import render_rents
from park_data import fetch_parks, load_parks, bundled_parks, SOURCE_URL as PARK_SOURCE_URL
from lifestyle_view import render_lifestyle
from housing_score_view import render_housing_scores
from commute_view import render_commute

import streamlit as st
from dotenv import load_dotenv

# 다른 화면 출력보다 먼저 설정
st.set_page_config(
    page_title="집.착",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    st.caption("수동 설정과 검증 · 필요할 때 펼쳐 확인하세요.")

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
st.caption("원하는 집과 동네를 대화로 찾아보세요.")

conditions = st.session_state.housing_conditions

with st.sidebar.expander('적용된 조건 확인'):
    if conditions is None:
        st.info("대화로 조건을 알려주거나 이 사이드바에서 직접 설정하세요.")
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
bike_result=bundled_stations()
with st.sidebar:
    st.divider()
    st.subheader("따릉이 대여소 위치")
    st.caption("공식 위치 파일을 불러옵니다. 실시간 재고는 사용하지 않습니다.")
    st.link_button("공식 위치 자료 받기", SOURCE_URL)
    bike_file = st.file_uploader("대여소 위치 CSV / XLSX", type=["csv", "xlsx"])
    if bike_file is not None:
        try:
            bike_result = load_stations(bike_file.getvalue(), bike_file.name)
            bike_result.update({"source_url":SOURCE_URL,"origin":bike_file.name+" (자료 기준일은 원본 확인)"})
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
    elif bike_result:
        st.caption(f"공식 기본 위치 {len(bike_result['stations']):,}개 · 2026년 6월 자료 · 실시간 재고 아님")

with st.sidebar:
    st.divider()
    st.subheader('공원 위치 자료')
    if st.button('서울 주요 공원 API 조회',key='fetch_parks'):
        try:
            with st.spinner('주요 공원 좌표를 불러옵니다...'):
                st.session_state.park_data=fetch_parks(os.getenv('SEOUL_OPEN_DATA_API_KEY',''))
        except ValueError as error:
            st.session_state.pop('park_data',None)
            st.warning(str(error))
    st.link_button('공식 공원 자료 받기',PARK_SOURCE_URL)
    park_file=st.file_uploader('공원 위치 CSV / XLSX',type=['csv','xlsx'],key='park_file')
    if park_file is not None:
        try:
            park_data=load_parks(park_file.getvalue(),park_file.name)
        except ValueError as error:
            park_data=None
            st.warning(str(error))
    else:
        park_data=st.session_state.get('park_data')
        if park_data is None:
            park_data=bundled_parks()
            st.info('서울시 공식 CSV 스냅샷 사용 · API 실조회 아님 · 확보 2026-10-22 / 데이터셋 갱신 2026-09-23')
    if park_data:
        st.caption(f"공원 좌표 {len(park_data['parks'])}개 · 제외/중복 {park_data['skipped']}행")

boundaries=bundled_boundaries()
with st.sidebar:
    with st.expander('지도 경계 자료 (선택)'):
        st.caption('서울 법정동 기본 경계 제공. 최신 공식 WGS84 GeoJSON으로 교체할 수 있어요. properties.legal_code는 법정동 10자리 코드입니다.')
        boundary_file=st.file_uploader('법정동 경계 GeoJSON',type=['geojson','json'],key='boundary_file')
        if boundary_file:
            try:boundaries.update(read_boundaries(boundary_file.getvalue()))
            except (ValueError,KeyError,TypeError):st.warning('경계 파일의 코드·좌표·형식을 확인해주세요.')

# 수동 조회·검증은 사이드바에서 수행하고 결과만 지도/대화에 전달한다.
with st.sidebar:
    with st.expander('전월세 거래 수동 조회·확인'):
        neighborhood=render_rents(st.session_state.get('conversation_conditions') or conditions)
    with st.expander('생활 인프라 수동 확인'):
        lifestyle_facilities=render_lifestyle(neighborhood,st.session_state.get('conversation_conditions') or conditions,bike_result,park_data)
        if nearby_stations:
            st.dataframe([{'대여소':x['name'],'직장에서 직선거리(m)':x['distance_m']} for x in nearby_stations],hide_index=True)
    with st.expander('지도 위치·자료 확인'):
        map_neighborhood,map_month=map_region(neighborhood)
        st.caption('법정동 경계: 2023-07-29 공개 자료의 KnellBalm 변환본. 현재 경계와 차이가 있을 수 있습니다.')
        st.caption('연령 색상은 동별 통계를 부드럽게 혼합한 시각화이며 경계 부근의 실측 비율이 아닙니다. 동을 누르면 원래 수치를 확인할 수 있습니다.')
        st.caption('파란 원은 직선거리 탐색 범위입니다. 동네 이름표는 대표점이며 개별 주택이나 통근 가능 범위를 뜻하지 않습니다.')
    with st.expander('통근시간 수동 검증'):
        commute_context=render_commute(neighborhood,workplace_location,st.session_state.get('conversation_conditions') or conditions,
            st.session_state.get('rent_result'),st.session_state.get('neighborhood_locations',{}))
        commute_context['workplace_query']=(st.session_state.get('workplace_search') or {}).get('query')
    with st.expander('추천 점수·환경 근거 확인'):
        score_context=render_housing_scores(st.session_state.get('rent_result'),st.session_state.get('conversation_conditions') or conditions,
            st.session_state.get('neighborhood_locations',{}),bike_result,park_data)
        if city_data:render_citydata(city_data)
        render_place_comparison(city_data,city_preferences)
    with st.expander('동네 근거 수동 질문·검증'):
        render_rag(neighborhood)
    age_controls=st.expander('지도 연령 조회 상태·재시도')

recommendations=recommendation_rows(st.session_state.get('rent_result'),st.session_state.get('conversation_conditions') or conditions or {},score_context)

map_column,chat_column=st.columns([2,1],gap='large')
with map_column:
    st.subheader('동네 지도')
    map_stations=bike_result['stations'] if bike_result else []
    if not kakao_javascript_key:
        st.warning('지도 연결 설정이 필요합니다. 사이드바에서 설정과 자료를 확인해주세요.')
    else:
        radius_km=conditions.get('search_radius_km',3.0) if conditions else 3.0
        card=map_card(map_neighborhood,st.session_state.get('rent_result'),st.session_state.get('conversation_conditions') or conditions,
            bike_result,st.session_state.get('resident_data',{}),map_month,park_data)
        regions=region_cards(district_regions(map_neighborhood,map_month),map_neighborhood,st.session_state.get('rent_result'),
            st.session_state.get('conversation_conditions') or conditions,bike_result,park_data,st.session_state.get('resident_data',{}),map_month,st.session_state.get('neighborhood_locations',{}))
        viewport_value=render_viewport(build_map_html(kakao_javascript_key,workplace_location,radius_km,map_stations,city_facilities+lifestyle_facilities,
            map_neighborhood,card,boundaries.get((map_neighborhood or {}).get('legal_code')),regions,recommendations),
            regions=regions,explore=card,navigation=str((map_neighborhood or {}).get('legal_code'))+':'+str(workplace_location)+':'+map_asset_revision(),
            month=map_month,stations=map_stations,defer_population=True,recommendations=recommendations,busy=bool(st.session_state.get('pending_housing_prompt') or st.session_state.get('housing_message')))
with chat_column:
    render_chat(score_context,commute_context,map_neighborhood)

# 대화 위젯이 등록된 뒤 범위 조회를 처리해 지도 갱신 중에도 검색 옵션을 유지한다.
if kakao_javascript_key:
    with age_controls:
        update_population(viewport_value,regions,map_month)
