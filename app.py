import streamlit as st 

# 다른 화면 출력보다 먼저 설정
st.set_page_config(
    page_title="집.착",
    page_icon="🏠",
    layout="wide",
)

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


map_column, chat_column = st.columns([2, 1], gap="large")

with map_column:
    st.subheader("추천 지도")

    with st.container(border=True, height=500):
        st.info("이곳에 카카오 지도를 연결할 예정입니다.")

with chat_column:
    st.subheader("집.착과 대화하기")

    with st.container(border=True, height=500):
        with st.chat_message("assistant"):
            st.write(
                "안녕하세요! 어떤 집과 동네를 찾고 계신가요?"
            )