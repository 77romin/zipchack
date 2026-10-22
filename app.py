import requests
from kakao_api import search_workplace

import os
from pathlib import Path
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components
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
                key=f"workplace_selection_{query}",
            )

            if workplace_location:
                st.caption(
                    f"선택한 위치: {workplace_location['address']}"
                )


map_column, chat_column = st.columns([2, 1], gap="large")

with map_column:
    st.subheader("추천 지도")

    if not kakao_javascript_key:
        st.warning(
            ".env에 KAKAO_JAVASCRIPT_KEY를 설정해주세요."
        )
    else:
        encoded_key = quote(kakao_javascript_key, safe="")


        latitude = 37.5665
        longitude = 126.9780
        marker_script = ""

        if workplace_location:
            latitude = workplace_location["latitude"]
            longitude = workplace_location["longitude"]

            marker_script = """
                new kakao.maps.Marker({
                    map: map,
                    position: map.getCenter()
                });
            """


        map_html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="utf-8">
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                }}

                #map {{
                    width: 100%;
                    height: 500px;
                    border-radius: 12px;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>

            <script
                src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={encoded_key}&autoload=false">
            </script>

            <script>
                if (window.kakao && window.kakao.maps) {{
                    kakao.maps.load(function () {{
                        const container =
                            document.getElementById("map");

                        const options = {{
                            center: new kakao.maps.LatLng(
                                {latitude}, {longitude}
                            ),
                            level: 7
                        }};

                        const map = new kakao.maps.Map(
                            container, options
                        );
                        
                        {marker_script}

                        map.addControl(
                            new kakao.maps.ZoomControl(),
                            kakao.maps.ControlPosition.RIGHT
                        );
                    }});
                }} else {{
                    document.getElementById("map").textContent =
                        "지도를 불러오지 못했습니다. 카카오맵 활성화, JavaScript 키, 등록 도메인을 확인해주세요.";
                }}
            </script>
        </body>
        </html>
        """

        components.html(
            map_html,
            height=510,
            scrolling=False,
        )

with chat_column:
    st.subheader("집.착과 대화하기")

    with st.container(border=True, height=500):
        with st.chat_message("assistant"):
            st.write(
                "안녕하세요! 어떤 집과 동네를 찾고 계신가요?"
            )