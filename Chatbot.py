import streamlit as st
import pandas as pd
import io
from langchain_core.messages.chat import ChatMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime

# API KEY를 환경변수로 관리하기 위한 설정 파일
from dotenv import load_dotenv

# API KEY 정보로드
load_dotenv()

st.set_page_config(
    page_title="참스토어 주문 검색 챗봇",
    layout="wide"  # 화면을 넓게 사용
)

# CSV 파일 업로드하기
uploaded_file = st.file_uploader("CSV 파일 업로드", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file, encoding="utf-8-sig")


# 스트림릿은 매번 새로고침하는 개념이므로, if문을 통해 messages가 비었을 때 처음 1번만 실행하게 만듬
if "messages" not in st.session_state:
    # 대화기록을 저장하기 위한 용도로 생성한다.
    st.session_state["messages"] = []

# 사이드바 생성
with st.sidebar:
    # 초기화 버튼 생성
    clear_btn = st.button("대화 초기화")


# 이전 대화를 출력
def print_messages():
    for chat_message in st.session_state.messages:
        st.chat_message(chat_message["role"]).write(chat_message["content"])


# 초기화 버튼이 눌리면...
if clear_btn:
    st.session_state["messages"] = []

# 이전 대화 기록 출력
print_messages()


# 새로운 메세지를 추가
def add_message(role, message):
    st.session_state["messages"].append(ChatMessage(role=role, content=message))


# 검색 기능 정의
def search_orders(query, df):
    keywords = query.strip().split()
    mask = pd.Series([True] * len(df))  # AND 조건이므로 처음엔 모두 True
    for kw in keywords:
        mask = mask & (
            df["주문자명"].astype(str).str.contains(kw, case=False, na=False)
            | df["약국명"]
            .astype(str)
            .str.contains(kw, case=False, na=False)
            | df["상품명(한국어 쇼핑몰)"]
            .astype(str)
            .str.contains(kw, case=False, na=False)
            | df["주문일시"].astype(str).str.contains(kw, case=False, na=False)
        )
    return df[mask]


def chat_with_gpt(prompt):
    response = client.chat.completions.create(
        model="gpt-4-turbo", messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input(
    "주문자명, 약국명, 상품명, 주문일시(YYYY-MM-DD 형태로 입력) 중 아무거나 섞어서 입력해보세요!"
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # CSV 파일이 업로드되지 않았을 경우 예외 처리
    if uploaded_file is None or 'df' not in locals():
        with st.chat_message("assistant"):
            st.error("📂 CSV 파일을 먼저 업로드해 주세요!")
        st.session_state.messages.append({
            "role": "assistant",
            "content": "📂 CSV 파일을 먼저 업로드해 주세요!"
        })
    else:
        
        # 검색 실행
        search_results = search_orders(prompt, df)
        if not search_results.empty:
            response_text = f"🔍 {len(search_results)}건의 결과를 찾았습니다:\n"
            response_text += search_results[["주문번호", "주문자명", "회원추가항목_약국명", "주문일시", "상품명(한국어 쇼핑몰)", "상품옵션", "수량", "상품구매금액", "결제수단"]].to_markdown(index=False)
    
        else:
            response_text = "😢 해당 조건에 맞는 주문이 없습니다"
    
        # AI 응답 표시
        with st.chat_message("assistant"):
            st.markdown(response_text)
        
        # 검색 결과가 있을 때만 다운로드 기능 추가
        if not search_results.empty:
            # 오늘 날짜를 YYYYMMDD 형식으로 가져오기
            today_str = datetime.today().strftime('%Y%m%d')
    
            # 주문자명이 여러 명일 수 있으므로, 첫 번째 이름만 추출하거나 '다수' 처리
            unique_names = search_results['주문자명'].dropna().unique()
            if len(unique_names) == 1:
                order_name = unique_names[0]
            else:
                order_name = '다수'
        
            # 엑셀 파일로 변환
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                search_results.to_excel(writer, index=False, sheet_name='검색결과')
            output.seek(0)
        
            # 다운로드 버튼 출력
            st.download_button(
                label=f"📥 결과 다운로드: {order_name}_{today_str}.xlsx",
                data=output,
                file_name=f"{order_name}_{today_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
