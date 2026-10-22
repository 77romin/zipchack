import streamlit as st 

# 다른 화면 출력보다 먼저 설정
st.set_page_config(
    page_title="집.착",
    page_icon="🏠",
    layout="wide",
)

# 왼쪽 설정 영역
with st.sidebar:
    st.title("집.착")
    st.caption("내 맘에 착, 내 삶에 착")
    
    st.subheader("나의 조건")
    st.info("직장 위치와 주거 조건을 입력할 공간입니다.")
    
# 메인 화면
st.title("나에게 착 맞는 집과 동네")
st.caption("예산부터 출근길까지, 내 생활을 기준으로 찾아보세요!")

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