import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai
import sys
import subprocess
import streamlit.runtime as runtime
import smtplib
from email.mime.text import MIMEText
import os
from google.cloud import firestore
from google.oauth2 import service_account

# 1. 페이지 설정
st.set_page_config(page_title="CBT 자기분석 가이드", layout="centered")

st.markdown("""
<style>
    .stChatMessageAvatar { display: none; }
</style>
""", unsafe_allow_html=True)

# --- Firebase DB 연결 함수 ---
@st.cache_resource
def get_db():
    """Streamlit Secrets에 저장된 Firebase 인증 정보를 바탕으로 DB에 연결합니다."""
    # st.secrets["firebase"]의 값들을 딕셔너리로 변환하여 인증
    key_dict = dict(st.secrets["firebase"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict["project_id"])
    return db

# --- 데이터 저장/불러오기 함수 (Firebase 연동) ---
def save_state():
    """현재 세션 상태를 Firebase Firestore에 이메일 기준으로 저장합니다."""
    if not st.session_state.user_email:
        return # 이메일이 없으면 저장하지 않음

    db = get_db()
    # 'cbt_users' 컬렉션 아래에 사용자 이메일을 문서 ID로 사용
    doc_ref = db.collection("cbt_users").document(st.session_state.user_email)
    
    data = {
        "app_step": st.session_state.app_step,
        "initial_scores": st.session_state.initial_scores,
        "final_scores": st.session_state.final_scores,
        "category_scores": st.session_state.category_scores,
        "chat_history": st.session_state.chat_history,
        "current_day": st.session_state.current_day,
        "target_days": st.session_state.target_days,
        "user_email": st.session_state.user_email,
        "yesterday_homework": st.session_state.yesterday_homework,
        "session_ended": st.session_state.session_ended,
        "daily_summaries": st.session_state.daily_summaries
    }
    doc_ref.set(data) # DB에 덮어쓰기/생성

def load_state(email):
    """Firebase Firestore에서 특정 이메일의 데이터를 불러옵니다."""
    if not email:
        return False
        
    db = get_db()
    doc_ref = db.collection("cbt_users").document(email)
    doc = doc_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        for key, value in data.items():
            st.session_state[key] = value
        return True
    return False

def clear_state():
    """DB 데이터는 놔두고, 현재 접속 중인 브라우저의 화면만 초기화합니다."""
    st.session_state.clear()

# --- 세션 상태 초기화 (앱 실행 시 최초 1회) ---
if "initialized" not in st.session_state:
    st.session_state.app_step = 0
    st.session_state.initial_scores = {}
    st.session_state.final_scores = {}
    st.session_state.category_scores = {}
    st.session_state.chat_history = []
    st.session_state.current_day = 1
    st.session_state.target_days = 7
    st.session_state.user_email = ""
    st.session_state.yesterday_homework = "없음"
    st.session_state.session_ended = False
    st.session_state.daily_summaries = [] 
    st.session_state.initialized = True

# --- 이메일 발송 함수 ---
def send_cbt_email(user_email, day):
    try:
        title = "오늘의 마음 점검 시간입니다"
        content = f"오늘 하루는 어떠셨나요? 어제 받은 숙제를 실천해 보셨는지 대화를 나눠보세요."
        msg = MIMEText(content)
        msg['Subject'] = title
        msg['From'] = "aggang0923@gmail.com"
        msg['To'] = user_email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Secrets에서 안전하게 비밀번호 호출
        email_password = st.secrets["EMAIL_PASSWORD"] 
        server.login("aggang0923@gmail.com", email_password)
        
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
        return False

# --- 척도 및 세팅 ---
options_7pt = ["전적으로 동의함", "매우 동의함", "약간 동의함", "중립", "약간 동의하지 않음", "매우 동의하지 않음", "전적으로 동의하지 않음"]
score_map = {"전적으로 동의함": 7, "매우 동의함": 6, "약간 동의함": 5, "중립": 4, "약간 동의하지 않음": 3, "매우 동의하지 않음": 2, "전적으로 동의하지 않음": 1, None: 4}
reverse_score_map = {"전적으로 동의함": 1, "매우 동의함": 2, "약간 동의함": 3, "중립": 4, "약간 동의하지 않음": 5, "매우 동의하지 않음": 6, "전적으로 동의하지 않음": 7, None: 4}
reverse_items = [2, 6, 12, 17, 24, 29, 30, 35, 37, 40]

categories = {
    "성취 강박": [1, 5, 9, 10, 11, 14, 18, 21, 22, 36],
    "인정/승인 욕구": [2, 3, 4, 6, 7, 13, 19, 27, 35, 38],
    "완벽주의": [12, 17, 20, 23, 24, 25, 26, 29, 30, 33],
    "의존성": [8, 15, 16, 28, 31, 32, 34, 37, 39, 40]
}

cbt_explanations = {
    "성취 강박": """**[인지 오류 분석]** 조건 없는 자기 수용 연습이 필요합니다... (생략)""",
    "인정/승인 욕구": """**[인지 오류 분석]** 내 감정의 주도권을 타인에게서 나 자신에게로... (생략)""",
    "완벽주의": """**[인지 오류 분석]** 실수를 성장의 과정으로 받아들이는 인지 재구조화... (생략)""",
    "의존성": """**[인지 오류 분석]** 독립적인 결정의 근육을 키워나갑니다... (생략)"""
}

das_40_questions = [
    "외모가 뛰어나고, 똑똑하고, 돈이 많고, 창의적이지 않으면 행복해지기 어렵다.",
    "행복은 다른 사람들이 나를 어떻게 생각하느냐보다 나 자신에 대한 나의 태도에 더 많이 달려 있다.",
    # ... 공간 관계상 생략했지만 기존 문항 40개 그대로 넣으시면 됩니다. ...
    "다른 사람의 사랑을 받지 못해도 나는 행복을 찾을 수 있다."
]

# ==========================================
# 화면 A (Step 0): 온보딩 & 사전 검사
# ==========================================
if st.session_state.app_step == 0:
    st.title("Step 1. 내면의 지도 그리기")
    
    # DB에서 기록 불러오기 UI
    st.info("💡 **기존 참여자이신가요?**")
    col_em, col_btn = st.columns([3, 1])
    with col_em:
        load_email_input = st.text_input("진행 중인 이메일을 입력하세요.", label_visibility="collapsed")
    with col_btn:
        if st.button("기록 불러오기"):
            if load_state(load_email_input):
                st.success("클라우드에서 기록을 성공적으로 불러왔습니다!")
                st.rerun()
            else:
                st.error("해당 이메일로 저장된 기록이 없습니다.")
                
    st.markdown("---")
    st.markdown("처음 오셨다면, 본격적인 대화에 앞서 **DAS-40 사전 검사**를 진행합니다.")

    with st.form("das_form_initial"):
        st.subheader("상담 목표 설정")
        col1, col2 = st.columns(2)
        with col1:
            target_days = st.slider("CBT 진행 기간을 선택하세요", min_value=7, max_value=14, value=7)
        with col2:
            user_email = st.text_input("알림을 받을 이메일 주소", placeholder="example@gmail.com")
        
        st.markdown("---")
        st.subheader("DAS-40 사전 문항")
        
        responses = []
        for i, question in enumerate(das_40_questions[:40]):
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=True)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("검사 완료 및 설정 저장")
            
        if submitted:
            if not user_email:
                st.error("이메일 주소는 필수입니다.")
            else:
                st.session_state.target_days = target_days
                st.session_state.user_email = user_email
                
                scores = {"성취 강박": 0, "인정/승인 욕구": 0, "완벽주의": 0, "의존성": 0}
                for q_num, ans in responses:
                    if ans:
                        point = reverse_score_map[ans] if q_num in reverse_items else score_map[ans]
                        for cat, q_list in categories.items():
                            if q_num in q_list:
                                scores[cat] += point
                
                st.session_state.initial_scores = scores 
                st.session_state.category_scores = scores 
                st.session_state.app_step = 1
                save_state() # DB에 최초 저장
                st.rerun()

# ==========================================
# 화면 B (Step 1): 검사 결과 리포트
# ==========================================
elif st.session_state.app_step == 1:
    st.title("Step 1.5. 인지적 기준선 분석 결과")
    
    scores = st.session_state.initial_scores
    df = pd.DataFrame(dict(r=list(scores.values()), theta=list(scores.keys())))
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0, 70])
    fig.update_traces(fill='toself', fillcolor='rgba(255, 75, 75, 0.2)', line_color='red')
    
    fig.update_layout(dragmode=False) 
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    max_cat = max(scores, key=scores.get)
    st.warning(f"검사 결과, 현재 당신의 내면에서 가장 주의가 필요한 영역은 **'{max_cat}'** 입니다.")
    st.info(cbt_explanations[max_cat])
    
    if st.button("Day 1 상담 시작하기", use_container_width=True):
        st.session_state.app_step = 2
        save_state() # DB에 상태 업데이트
        st.rerun()

# ==========================================
# 화면 C (Step 2): 일일 CBT 챗봇
# ==========================================
elif st.session_state.app_step == 2:
    st.title(f"CBT 가이드 - Day {st.session_state.current_day} / {st.session_state.target_days}")
    
    # Secrets에서 Gemini API 키 안전하게 호출
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    scores = st.session_state.category_scores
    max_cat = max(scores, key=scores.get)
    
    past_summaries_text = "\n".join([f"- Day {i+1}: {summary}" for i, summary in enumerate(st.session_state.daily_summaries)]) if st.session_state.daily_summaries else "아직 이전 상담 기록이 없습니다."

    if st.session_state.current_day == 1:
        system_prompt = f"당신은 인지행동치료(CBT) 기반 AI 가이드이다. [취약 영역]: {max_cat}. (이하 프롬프트 동일)"
    else:
        system_prompt = f"당신은 AI 심리 가이드이다. [과거 기록]: {past_summaries_text} [어제 숙제]: {st.session_state.yesterday_homework}"

    model = genai.GenerativeModel('gemini-3.1-pro-preview', system_instruction=system_prompt)

    if len(st.session_state.chat_history) == 0:
        st.session_state.chat_history.append({"role": "assistant", "content": f"안녕하세요, Day {st.session_state.current_day} 상담을 시작하겠습니다."})
        save_state()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not st.session_state.session_ended:
        if user_input := st.chat_input("당신의 생각을 적어주세요..."):
            with st.chat_message("user"):
                st.markdown(user_input)
            
            gemini_history = [{"role": "user", "parts": ["안녕! 시작하자"]}]
            for msg in st.session_state.chat_history[-6:]:
                role = "model" if msg["role"] == "assistant" else "user"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
                
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                try:
                    chat = model.start_chat(history=gemini_history)
                    response = chat.send_message(user_input, stream=True)
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                except Exception as e:
                    full_response = "오류가 발생했습니다."
                    message_placeholder.markdown(full_response)
                    
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})
            save_state() # 대화 내용 DB에 실시간 백업

        st.markdown("---")
        if st.button("오늘의 상담 종료하고 숙제 받기", use_container_width=True):
            st.session_state.session_ended = True
            save_state()
            st.rerun()

    else:
        st.success(f"Day {st.session_state.current_day} 인지 훈련 세션 완료!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("이메일 알림 테스트"):
                if send_cbt_email(st.session_state.user_email, st.session_state.current_day + 1):
                    st.toast("전송 성공!")
                else:
                    st.error("전송 실패")
        with col2:
            if st.session_state.current_day < st.session_state.target_days:
                if st.button("다음 날(Next Day) 대화로 넘어가기"):
                    st.session_state.current_day += 1
                    # (여기에 요약 추출하는 기존 코드 동일하게 작성)
                    st.session_state.chat_history = [] 
                    st.session_state.session_ended = False
                    save_state() # 다음 날로 넘어간 상태 DB에 저장
                    st.rerun()
            else:
                if st.button("최종 사후 검사 진행하기"):
                    st.session_state.app_step = 3
                    save_state()
                    st.rerun()

# ==========================================
# 공통 UI: 모든 화면 하단
# ==========================================
if st.session_state.app_step > 0:
    st.markdown("---")
    if st.button("🔄 초기화하고 처음으로 돌아가기", use_container_width=True):
        clear_state() # DB는 놔두고 화면만 초기화
        st.rerun()

if __name__ == "__main__":
    if not runtime.exists():
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
        sys.exit()