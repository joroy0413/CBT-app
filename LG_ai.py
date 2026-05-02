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
import random
from google.cloud import firestore
from google.oauth2 import service_account

# ==========================================
# 1. 페이지 및 UI 기본 설정 (감성적인 테마 주입)
# ==========================================
st.set_page_config(page_title="CBT 자기분석 가이드", layout="centered", initial_sidebar_state="expanded")

# 🎨 [핵심 변경] 마음이 편안해지는 심리 케어 앱 전용 커스텀 CSS 주입
st.markdown("""
<style>
    /* 1. 고급스럽고 편안한 웹 폰트 (프리텐다드) 적용 */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 전체 배경색을 차가운 흰색에서 '따뜻한 크림 베이지'로 변경 */
    .stApp {
        background-color: #FAFAFA;
    }
    
    /* 3. 챗봇 프로필 아이콘 숨기기 (깔끔한 UI 유지) */
    .stChatMessageAvatar { display: none; }

    /* 4. AI 상담사 챗버블 (편안한 파스텔 민트) */
    [data-testid="chatAvatarIcon-assistant"] + div {
        background-color: #F0F4F2 !important; 
        border-radius: 20px 20px 20px 4px !important;
        padding: 15px 20px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03) !important;
        color: #2C3E50 !important;
        line-height: 1.6 !important;
    }
    
    /* 5. 내담자(사용자) 챗버블 (깔끔한 화이트 + 부드러운 그림자) */
    [data-testid="chatAvatarIcon-user"] + div {
        background-color: #FFFFFF !important;
        border: 1px solid #EAEAEA !important;
        border-radius: 20px 20px 4px 20px !important;
        padding: 15px 20px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03) !important;
        color: #4A4A4A !important;
    }

    /* 6. 모든 버튼 디자인 둥글고 부드럽게 (호버 애니메이션 추가) */
    .stButton>button {
        border-radius: 12px !important;
        border: none !important;
        background-color: #81C784 !important; /* 편안한 자연의 그린 */
        color: white !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        padding: 10px 24px !important;
    }
    .stButton>button:hover {
        background-color: #66BB6A !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 187, 106, 0.3) !important;
    }

    /* 7. 입력창, 슬라이더 부드럽게 */
    .stTextInput>div>div>input {
        border-radius: 12px !important;
        border: 1px solid #E0E0E0 !important;
        padding: 12px 15px !important;
    }

    /* 8. 탭(Tab) 메뉴 디자인 고급화 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: transparent;
        border-radius: 10px 10px 0 0;
        padding: 10px 20px;
        color: #90A4AE;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E8F5E9 !important;
        color: #2E7D32 !important;
        font-weight: bold;
        border-bottom: 3px solid #81C784 !important;
    }

    /* 9. 심층 분석 리포트 박스 (세련된 음영과 은은한 선) */
    .report-box { 
        background: linear-gradient(145deg, #ffffff, #fdfdfd);
        padding: 25px; 
        border-radius: 16px; 
        margin-bottom: 20px; 
        border-left: 6px solid #A5D6A7; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        color: #424242;
        line-height: 1.7;
    }
    .report-title { color: #2E7D32; font-weight: 800; font-size: 1.15em; margin-bottom: 12px; }
    
    /* 10. AI 인사이트 박스 (안정감을 주는 파스텔 톤) */
    .insight-box {
        background: linear-gradient(135deg, #F0F7F4, #E8F3EF);
        padding: 30px;
        border-radius: 20px;
        border-left: 6px solid #81C784;
        color: #37474F;
        line-height: 1.7;
        box-shadow: 0 8px 24px rgba(0,0,0,0.04);
        margin-bottom: 25px;
    }
    
    /* 11. 💌 진짜 편지지 같은 질감의 박스 */
    .letter-paper {
        background-color: #FEFCF8;
        background-image: radial-gradient(#E8E3D3 1px, transparent 1px);
        background-size: 20px 20px; /* 은은한 도트 패턴 */
        padding: 45px 40px;
        border-radius: 12px;
        border: 1px solid #EAE6D8;
        box-shadow: 0 10px 30px rgba(0,0,0,0.04);
        color: #5D554D;
        font-size: 1.05em;
        line-height: 2.0;
        margin-top: 15px;
        margin-bottom: 25px;
    }
    .letter-title {
        color: #8D6E63;
        font-weight: 800;
        font-size: 1.35em;
        margin-bottom: 25px;
        text-align: center;
        border-bottom: 2px dashed #E8E3D3;
        padding-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

@st.dialog("🛋️ 사용 전 필수 주의사항")
def show_welcome_modal():
    st.markdown("""
    ### 🌿 마음을 돌보는 시간에 오신 것을 환영합니다
    본 서비스는 **인지행동치료(CBT)** 원칙에 기반하여 설계된 다정한 AI 심리 케어 도구입니다.
    
    **1. 주요 개념 안내**
    1)   **CBT (인지행동치료)**: '상황' 자체가 아닌 그 상황을 바라보는 '나의 생각(인지)'이 감정과 행동을 결정한다는 원리에 기반한 치료법입니다. 
    2)   **DAS (역기능적 태도 척도)**: 개인이 가지고 있는 경직된 신념이나 가치관의 정도를 측정합니다. 점수가 높을수록 자신에게 엄격한 기준을 적용하고 있을 가능성이 큽니다.

    **2. 이용 주의사항**
    1)   **의학적 진단 대체 불가**: 본 서비스는 전문의의 진단이나 치료를 대체할 수 없습니다. 위기 상황 시 즉시 전문 기관의 도움을 받으세요.
    2)   **데이터 보안**: 입력하신 모든 대화 내용은 상담의 연속성을 위해 클라우드에 안전하게 암호화되어 저장됩니다.
    3)   **훈련 중심**: 단순한 위로를 넘어, 자신의 생각 오류를 찾아내고 일상에서 '행동 숙제'를 실천하는 능동적인 훈련입니다.
    4)   **깊은 성찰의 시간**: AI가 던지는 질문이 평소 해보지 않던 생각들이라 대답하기 어려울 수 있습니다. 이는 생각의 습관을 바꾸기 위한 실제 상담의 과정이니, 당황하지 마시고 천천히 진짜 마음을 적어주세요.
    """)
    if st.button("내면의 지도 그리기 시작하기"):
        st.session_state.show_modal = False
        st.rerun()


# --- Firebase DB 연결 함수 ---
@st.cache_resource
def get_db():
    key_dict = dict(st.secrets["firebase"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict["project_id"])
    return db

# --- 데이터 저장/불러오기 함수 ---
def save_state():
    if not st.session_state.user_email:
        return 
    db = get_db()
    doc_ref = db.collection("cbt_users").document(st.session_state.user_email)
    data = {
        "user_name": st.session_state.user_name,
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
        "daily_summaries": st.session_state.daily_summaries,
        "final_long_report": st.session_state.final_long_report
    }
    doc_ref.set(data) 

def load_state(email):
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
    st.session_state.clear()

# --- 세션 상태 초기화 ---
if "initialized" not in st.session_state:
    st.session_state.user_name = ""
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
    st.session_state.show_modal = True  
    st.session_state.final_long_report = "" 
    st.session_state.initialized = True

# --- 이메일 발송 함수 ---
def send_cbt_email(user_email, day):
    try:
        title = f"🌿 Day {day} 마음 챙김 알림이 도착했습니다"
        content = f"오늘 하루는 어떠셨나요? 어제 받은 행동 실험을 일상에서 실천해 보셨는지 AI 상담사와 대화를 나눠보세요."
        msg = MIMEText(content)
        msg['Subject'] = title
        msg['From'] = "aggang0923@gmail.com"
        msg['To'] = user_email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        email_password = st.secrets["EMAIL_PASSWORD"] 
        server.login("aggang0923@gmail.com", email_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"이메일 전송 실패: {e}")
        return False

# ==========================================
# 2. CBT 척도 및 심층 분석 데이터 세팅
# ==========================================
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

cbt_explanations_detailed = {
    "성취 강박": """
    <div class="report-box">
        <div class="report-title">📌 핵심 신념: 조건부 가치 부여와 당위적 사고</div>
        현재 내담자님의 내면 깊은 곳에는 <b>'무언가를 성취해 내야만 비로소 나는 가치 있는 인간이다'</b>라는 핵심 신념(Core Belief)이 강하게 자리 잡고 있습니다. 
        이는 인지행동치료에서 흔히 관찰되는 <b>'당위적 사고(Musts & Shoulds)'</b>와 <b>'흑백논리(All-or-Nothing Thinking)'</b>의 결합입니다. <br><br>
        성공과 성과가 있을 때는 자존감이 급격히 상승하지만, 목표에 미달하거나 예상치 못한 실패를 겪을 경우 그 사건을 단순히 '경험'으로 받아들이지 못하고 <b>'내 존재 자체의 무가치함'</b>으로 파국화(Catastrophizing)하는 경향이 짙습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🛠 일상 행동 및 감정 패턴 예측</div>
        이러한 인지 도식으로 인해, 일상에서 끊임없이 무언가를 해야 한다는 압박감(초조함)에 시달리기 쉽습니다. 쉴 때조차 죄책감을 느끼거나, 결과가 보장되지 않은 새로운 도전을 극도로 회피하는 완벽주의적 지연 행동이 동반될 수 있습니다. 
        타인의 성취를 보며 쉽게 박탈감을 느끼고, 자신의 성과를 끊임없이 타인과 비교하며 스스로를 소진시키는 번아웃(Burn-out)의 위험도가 매우 높습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🎯 향후 CBT 가이드 목표 및 전략</div>
        <b>1. 조건 없는 자기 수용 훈련:</b> '성취 = 내 가치'라는 강력한 연결고리를 끊어내는 하향 화살표 기법(Downward Arrow Technique)을 적용합니다.<br>
        <b>2. 과정 중심적 사고로의 전환:</b> 최종 결과와 상관없이 활동 자체에서 즐거움과 의미를 찾는 연습을 시작합니다.<br>
        <b>3. 행동 실험 (Behavioral Experiment):</b> 의도적으로 작은 실수를 해보거나, 아무런 '생산적 결과'가 없는 취미 활동을 하루 30분씩하며 나의 가치가 훼손되는지 관찰하는 숙제를 진행할 것입니다.
    </div>
    """,
    "인정/승인 욕구": """
    <div class="report-box">
        <div class="report-title">📌 핵심 신념: 독심술과 타인 지향적 가치관</div>
        현재 내담자님은 감정과 자존감의 통제권을 '내'가 아닌 '타인'에게 양도한 상태입니다. 
        인지행동치료의 관점에서 이는 <b>'독심술(Mind-reading)'</b>과 <b>'개인화(Personalization)'</b> 오류가 두드러지는 상태입니다. <br><br>
        타인의 미세한 표정 변화, 메시지 답장 속도, 무심한 말 한마디를 나에 대한 부정적 평가로 지레짐작하며, '모두에게 사랑받아야만 한다'는 비현실적이고 경직된 조건적 가정(Conditional Assumption)을 지니고 있습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🛠 일상 행동 및 감정 패턴 예측</div>
        대인관계에서 끊임없이 타인의 눈치를 보며 에너지를 소모합니다. 갈등을 극도로 회피하기 위해 내 권리나 이익을 쉽게 포기(과잉 순응)하거나, 거절을 하지 못해 원치 않는 책임을 떠안는 경우가 많습니다. 
        그럼에도 불구하고 타인이 내 헌신을 알아주지 않을 때 깊은 억울함과 우울감을 느끼며, 혼자 남겨지는 것(유기 불안)에 대한 극도의 두려움을 경험할 수 있습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🎯 향후 CBT 가이드 목표 및 전략</div>
        <b>1. 내적 귀인(Internal Attribution) 형성:</b> 나에 대한 평가 기준을 타인의 시선에서 나의 내면으로 옮겨오는 인지 재구조화를 진행합니다.<br>
        <b>2. 인지 왜곡 교정:</b> "저 사람이 나를 싫어할 거야"라는 자동적 사고가 떠오를 때, 그것이 100% 진실인지, 증거는 무엇인지 객관적인 법정에 세워보는 소크라테스식 문답법을 훈련합니다.<br>
        <b>3. 행동 실험 (Behavioral Experiment):</b> 모두를 만족시킬 수 없다는 사실을 수용하기 위해, 일상에서 작은 부탁을 정중하게 거절해 보고 관계가 붕괴되는지 확인하는 노출 훈련을 계획합니다.
    </div>
    """,
    "완벽주의": """
    <div class="report-box">
        <div class="report-title">📌 핵심 신념: 흑백논리와 당위적 명제의 함정</div>
        자신(때로는 타인에게도)을 향해 몹시 가혹하고 엄격한 잣대를 들이대고 있습니다. 
        <b>'100점이 아니면 모두 0점 실패작이다'</b>라는 극단적인 <b>'이분법적 사고(Dichotomous Thinking)'</b>와 <b>'과도한 일반화(Overgeneralization)'</b>가 내면을 지배하고 있습니다.<br><br>
        "~해야만 한다", "~해서는 절대 안 된다"라는 무수한 당위적 명제들로 뇌의 유연성을 잃은 상태이며, 하나의 작은 오점이 전체의 가치를 훼손한다고 믿는 인지적 협착이 나타나고 있습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🛠 일상 행동 및 감정 패턴 예측</div>
        일을 시작할 때 '완벽하게 해내야 한다'는 압박감 때문에 오히려 착수를 하지 못하는 지연 행동(Procrastination)이 빈번할 수 있습니다. 
        타인에게 일을 위임하지 못하고 모든 것을 스스로 통제하려 하며, 사소한 실수를 했을 때 자신을 향한 심한 자기 비난(Self-criticism)과 수치심에 빠집니다. 과정의 즐거움을 누리지 못하고 늘 만성적인 긴장감과 불만족 상태에 놓이기 쉽습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🎯 향후 CBT 가이드 목표 및 전략</div>
        <b>1. '적당함의 미학(Good enough)' 수용:</b> 100점 완벽이 아닌 70~80점의 성과도 얼마나 가치 있는지 연속선(Continuum) 기법을 통해 평가하는 훈련을 합니다.<br>
        <b>2. 이중 잣대(Double Standard) 교정:</b> 내가 남의 실수를 대하는 관대함을 내 자신에게도 동일하게 적용하는 인지 훈련을 진행합니다.<br>
        <b>3. 행동 실험 (Behavioral Experiment):</b> 고의로 이메일에 사소한 오타를 남기거나, 방을 하루 정도 청소하지 않고 내버려 둔 뒤 파국적인 결과가 발생하는지 체계적으로 관찰하는 숙제를 부여할 것입니다.
    </div>
    """,
    "의존성": """
    <div class="report-box">
        <div class="report-title">📌 핵심 신념: 파국화와 자기 효능감 저하</div>
        삶의 난관이나 선택의 기로에 섰을 때, 자신의 판단력을 불신하고 타인(또는 절대적 존재)의 지지가 있어야만 안도하는 양상을 보입니다. 
        여기에는 최악의 시나리오를 지레짐작하는 <b>'파국화(Catastrophizing)'</b> 오류와 <b>'나의 대처 능력 과소평가(Minimization)'</b> 오류가 기저에 깔려 있습니다.<br><br>
        "나 혼자 결정했다가 잘못되면 나는 완전히 무너질 거야"라는 식의 두려움이 독립적인 문제 해결 능력을 억압하고 있습니다.
    </div>
    <div class="report-box">
        <div class="report-title">🛠 일상 행동 및 감정 패턴 예측</div>
        사소한 일상적 결정(메뉴 고르기, 옷 사기 등)에서부터 중요한 인생의 결정까지 끊임없이 타인에게 의견을 묻고 확인을 받으려 합니다. 
        보호받거나 의지하던 관계가 흔들릴 조짐이 보이면 극도의 불안(공황 상태)을 느끼며, 홀로 남겨지는 것을 회피하기 위해 자신에게 해로운 관계조차 단절하지 못하고 끌려다닐 위험이 존재합니다.
    </div>
    <div class="report-box">
        <div class="report-title">🎯 향후 CBT 가이드 목표 및 전략</div>
        <b>1. 자기 효능감(Self-Efficacy) 복원:</b> 과거에 혼자서 문제를 해결했던 성공 경험들을 구체적인 증거로 수집하고 인지적으로 재조명합니다.<br>
        <b>2. 두려움 직면하기:</b> 파국적인 상황이 실제로 일어날 확률을 수학적으로 계산해 보고, 만약 일어나더라도 대처할 수 있는 플랜 B를 이성적으로 세워보는 훈련을 합니다.<br>
        <b>3. 행동 실험 (Behavioral Experiment):</b> 타인에게 의견을 묻지 않고 오로지 나의 직관만으로 하루 동안의 결정(식사, 경로 등)을 내리고 그 결과가 치명적이지 않음을 증명하는 연습을 시작합니다.
    </div>
    """
}

das_40_questions = [
    "사람들은 잘 생기고 똑똑하고 돈이 많지 않으면 행복해지기 어렵다.",
    "행복이란 사람들이 날 어떻게 생각하든 주로 내 태도에 달려 있다.",
    "실수를 하면 남들이 날 전보다 업신여길 것이다.",
    "남들로부터 인정받으려면 항상 일을 잘 해야 한다.",
    "작은 일이라도 위험한 모험을 하는 것은 어리석은 일이다. 왜냐하면 그로 인해 큰 손실을 입을 수도 있기 때문이다.",
    "어떤 분야에 특별한 재능이 없이도 남들의 존경과 인정을 받을 수 있다.",
    "날 아는 사람들로부터 칭찬받지 못한다면 나는 행복해질 수 없다.",
    "남들에게도 도와 달라고 하는 것은 나약하다는 표시이다.",
    "남들보다 어떤 일을 잘 하지 못한다면 열등한 것이다.",
    "자기가 하는 일에서 실패한다면 인간으로서도 실패하는 것이다.",
    "잘할 수 없는 일은 아예 시작할 필요도 없다.",
    "실수를 통해 배울 수 있기 때문에 때로는 실수하는 것도 필요하다.",
    "내 의견에 반대하는 사람은 아마 날 좋아하지 않는 사람일 것이다.",
    "절반 정도 실패했다면 전부 실패한 것이나 다름없다.",
    "내 실제 모습을 사람들이 안다면 날 전보다 무시할 것이다.",
    "날 사랑하던 사람이 더 이상 사랑해 주지 않는다면 살 가치가 없을 것 같다.",
    "어떤 일의 결과와는 상관 없이 과정 속에서도 만족을 얻을 수 있다.",
    "어느 정도 성공할 가능성이 있는 일만 착수해야 한다.",
    "한 인간으로서 내 가치는 남들로부터 받는 평가에 달려 있다.",
    "최상의 목표를 향해 나아가지 않는다면 나는 이류 인간으로 전락하고 말 것이다.",
    "가치 있는 사람이 되려면 적어도 한 분야에서는 뛰어나야 한다.",
    "사고력이 높을수록 더 가치 있는 인간이 된다.",
    "실수하는 경우 낭패감을 느끼는 것은 당연하다.",
    "내 자신을 어떻게 생각하는지가 다른 사람의 견해보다 더 중요하다.",
    "도움을 요청하는 사람들을 전부 도와주어야 착하고 가치 있는 사람이 된다.",
    "남에게 자꾸 물어보면 남들 눈에 열등하게 보일 것이다.",
    "내 주변이 중요한 사람들로부터 인정받지 못한다면 견디기 힘들 것이다.",
    "의지할 사람이 없으면 당연히 불행해진다.",
    "자신을 혹사하지 않는다면 중요한 일을 해내기 힘들 것이다.",
    "야단을 맞고도 태연할 수 있다.",
    "사람들은 언제 나에게 등을 돌릴지 모르기 때문에 믿을 수 없다.",
    "남들이 나를 싫어한다면 나는 행복해질 수 없다.",
    "남들을 기분 좋게 하려면 내 이익을 포기하지 않을 수 없다.",
    "나의 행복은 나보다 남들에게 더 달려 있다.",
    "행복해지는 데 남들의 인정이 반드시 필요한 것은 아니다.",
    "문제를 회피하다보면 그 문제가 사라져 버리는 경우가 많다.",
    "인생에서 즐거운 것들을 많이 놓친다 해도 나는 행복할 수 있다.",
    "남들이 나에 대해 어떻게 생각하는지가 나에게는 매우 중요하다.",
    "남들로부터 고립되면 불행해질 수 밖에 없다.",
    "남들이 날 사랑해 주지 않는다 해도 나는 행복해질 수 있다."
]

# ==========================================
# 3. 항시 표출 사이드바 UI
# ==========================================
if st.session_state.app_step >= 1 and st.session_state.initial_scores:
    with st.sidebar:
        st.header("📊 나의 마음 기준선")
        scores = st.session_state.initial_scores
        df_side = pd.DataFrame(dict(r=list(scores.values()), theta=list(scores.keys())))
        df_side = pd.concat([df_side, df_side.iloc[[0]]], ignore_index=True)
        
        fig_side = px.line_polar(df_side, r='r', theta='theta', line_close=True, range_r=[0, 70])
        fig_side.update_traces(fill='toself', fillcolor='rgba(129, 199, 132, 0.4)', line_color='#66BB6A')
        fig_side.update_layout(
            polar=dict(radialaxis=dict(visible=False)),
            margin=dict(l=20, r=20, t=20, b=20),
            dragmode=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_side, use_container_width=True, config={'displayModeBar': False})
        
        max_cat_side = max(scores, key=scores.get)
        st.info(f"🌿 **우선 케어 영역: {max_cat_side}**")
        st.markdown(f"""
        **점수 요약:**
        - 성취 강박: {scores.get('성취 강박', 0)}점
        - 인정/승인 욕구: {scores.get('인정/승인 욕구', 0)}점
        - 완벽주의: {scores.get('완벽주의', 0)}점
        - 의존성: {scores.get('의존성', 0)}점
        """)
        
        if st.button("🔄 기록 지우고 처음으로"):
            clear_state()
            st.rerun()

# ==========================================
# 4. 메인 화면 로직 (Step 0 ~ 4)
# ==========================================

if st.session_state.get("show_modal", True):
    show_welcome_modal()

if st.session_state.app_step == 0:
    st.title("Step 0. 내면의 지도 그리기 🗺️")
    
    st.info("💡 **기존에 진행 중이신가요?** 이메일을 입력하시면 클라우드에서 이전 기록을 포근하게 불러옵니다.")
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
    st.markdown("처음 오셨다면, 본격적인 대화에 앞서 **마음 기준선 검사(DAS-40)**를 진행합니다. 깊은 생각보다는 질문을 읽고 가장 먼저 떠오르는 직관적인 느낌을 선택해 주세요.")

    with st.form("das_form_initial"):
        st.subheader("나의 여정 설정하기")
        col1, col2, col3 = st.columns(3)
        with col1:
            target_days = st.slider("여정 기간 (일)", min_value=7, max_value=14, value=7)
        with col2:
            user_name = st.text_input("불리고 싶은 이름", placeholder="예: 다해")
        with col3:
            user_email = st.text_input("안내를 받을 이메일", placeholder="example@gmail.com")
        
        st.markdown("---")
        st.subheader("마음의 소리 듣기 (40문항)")
        
        responses = []
        for i, question in enumerate(das_40_questions[:40]):
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=False)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("기록 완료 및 여정 시작하기")
            
        if submitted:
            if not user_name or not user_email:
                st.error("이름과 진행 상황 저장을 위한 이메일 주소를 모두 채워주시면 출발할 수 있어요.")
            else:
                st.session_state.user_name = user_name
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
                save_state() 
                st.rerun()

elif st.session_state.app_step == 1:
    st.title("Step 1. 내면의 지형도 확인하기 🧭")
    st.markdown(f"작성해주신 답변을 바탕으로 **{st.session_state.user_name}** 님의 마음 지형도를 그렸습니다. 아래의 심층 분석 리포트를 찬찬히 읽어보며 나를 이해하는 시간을 가져보세요.")
    
    scores = st.session_state.initial_scores
    max_cat = max(scores, key=scores.get)
    
    df = pd.DataFrame(dict(r=list(scores.values()), theta=list(scores.keys())))
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0, 70])
    fig.update_traces(fill='toself', fillcolor='rgba(129, 199, 132, 0.4)', line_color='#66BB6A')
    fig.update_layout(dragmode=False, height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)') 
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.info(f"🌿 현재 **{st.session_state.user_name}** 님에게 가장 부드러운 케어가 필요한 영역은 **[{max_cat}]** 입니다.")
    st.markdown(cbt_explanations_detailed[max_cat], unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("💡 **안내:** 이 분석 결과는 본격적인 대화 중 언제든지 좌측 메뉴를 열어 다시 꺼내어 볼 수 있습니다.")
    
    if st.button("▶ Day 1 따뜻한 대화 시작하기", use_container_width=True):
        st.session_state.app_step = 2
        save_state() 
        st.rerun()

elif st.session_state.app_step == 2:
    st.title(f"마음 돌봄의 시간 - Day {st.session_state.current_day} / {st.session_state.target_days} ☕")
    st.caption(f"안전하고 따뜻한 공간입니다. {st.session_state.user_name} 님의 마음속 이야기를 어떤 판단도 없이 편하게 꺼내어 주세요.")
    
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    scores = st.session_state.category_scores
    max_cat = max(scores, key=scores.get)
    past_summaries_text = "\n".join([f"- Day {i+1}: {summary}" for i, summary in enumerate(st.session_state.daily_summaries)]) if st.session_state.daily_summaries else "아직 이전 상담 기록이 없습니다."

    base_cbt_instructions = f"""
    당신은 인지행동치료(CBT) 원칙에 기반하여 사용자의 인지 재구조화를 돕는 전문적이고 다정한 AI 심리 상담사이다.
    [사용자 취약 영역]: {max_cat}
    [내담자 호칭]: {st.session_state.user_name} 님

    [[ CBT 핵심 치료 원칙 및 필수 지침 ]]

    1. 상담사의 태도 및 준비
    - 공감을 표현하라. 인지모델의 맥락에서 추가 정보를 요청하라. 사고의 타당성 검증을 위해 동의를 구하라.
    - 방어적이지 않은 태도와 호기심을 유지하라. 내담자에 대한 당신의 기대치를 확인하라. 그들과 그들의 가치를 있는 그대로 받아들이기 위해 노력하라.
    - 내담자가 이전 치료가 효과가 없었기 때문에 회의적이거나 우려를 표명한다면, 그러한 표현에 대해 긍정적으로 강화하라 ("당신이 그렇게 말씀해 주셔서 좋네요"). "대부분의 내담자들은 이런 종류의 치료를 경험하지 못했기에, 여기에서 우리의 치료는 다를 것 같군요."라고 말하라.

    2. 회기의 구조 및 진행
    - 내담자가 불필요한 세부 정보를 제공하기 시작하거나 옆길로 새기 시작하면, 부드럽게 중단하는 것이 중요하다. "방해해서 죄송하지만, 저는 ~을 알아야겠어요."
    - 의제를 빠르게 설정하는 것이 이상적이다. 
    - [회기의 중간 부분] 5. 열망, 가치 및 목표를 식별한다. 6. 활동 계획을 세우거나 문제에 대해 작업한다. 7. 새로운 활동 계획을 공동으로 설정한다.
    - [회기의 마지막 부분] 8. 회기를 요약한다. 9. 내담자가 새로운 활동 계획을 완료할 가능성을 확인한다. 10. 피드백을 이끌어 낸다.

    3. 기분 확인 및 목표/가치 설정
    - 기분 확인은 간략해야 한다. "이번 주 기분을 간단히 한두 문장으로 요약해 주실 수 있으실까요?"
    - 내담자에게 다음과 같이 물어볼 수 있다. "인생에서 당신에게 정말로 중요한 것은 무엇인가요?"
    - 열망 끌어내기 질문: "인생을 위해 무엇을 원하나요?", "미래에 어떤 모습이길 바라나요?"
    - 궁극적 의미 도출하기 질문: "당신의 열망과 목표를 달성하면 어떤 점이 특히 좋을까요?", "자신에 대해 어떻게 느끼나요? 그것은 당신에 대해 무엇을 말할까요?"
    - 목표 설정의 어려움 극복: 내담자가 목표를 설정하는 질문에 "모르겠어요"라고 대답하면 "기적" 질문을 시도해 볼 수 있다. "만약 기적이 일어나서 당신이 내일 아침에 일어났을 때 전혀 우울하지 않다면 무엇이 다를까요?"

    4. 행동 계획(숙제) 설정 및 준수 강화
    - 좋은 행동 계획은 내담자가 다음을 수행할 수 있는 기회를 제공한다: 자신의 경험과 자신에 대해 긍정적인 결론을 내린다. 자신의 인지를 평가하고 수정한다. 새로운 행동들을 실험한다.
    - 모든 사람에게 맞는 일률적인 one size fits all 행동 계획은 없다. 공동으로 행동 계획을 설정한다. 행동 계획을 어렵게 만들기보다는 더 쉽게 만든다.
    - [완료 가능성 확인하기] 행동 계획을 세울 때 잠재적인 장애물을 예측하는 것이 중요하다. 가장 중요한 질문은 다음과 같다. "0~100%의 확률로, 이 작업을 수행할 가능성은 얼마나 되나요?"
    - [장애물을 예상하고 은밀하게 예행연습하기] 만약 90% 미만일 것이라고 확신한다면, "왜 당신은 50%가 아니라 75% 확신하나요?", "가능성을 95%로 만들기 위해 우리가 무엇을 할 수 있나요?"라고 물어보고 행동 계획을 더 쉽게 수정하라.

    [[ 시스템 자동화 제어 지침 - 반드시 엄수 ]]
    - 글씨 강조를 위해 마크다운 '*' 기호를 남용하지 마라.
    - [중요] 단 1~2번 대화만으로 섣불리 종료하지 마라. 하향 화살표 기법 등을 통해 충분한 탐색(최소 4턴 이상)을 거친 후, 대화 후반부에 '행동 계획(숙제)'을 0~100% 확률로 확인하는 과정까지 마쳐라.
    - **[핵심 자동화 트리거]** 내담자가 행동 숙제를 일상에서 해보기로 동의하고, 오늘의 상담을 마무리하는 요약 및 피드백까지 끝났다고 스스로 판단되면 당신의 마지막 답변 맨 끝에 반드시 `[SESSION_END]` 라는 태그를 적어라. 이 태그가 인식되면 시스템이 자동으로 상담을 종료한다.
    """

    if st.session_state.current_day == 1:
        system_prompt = base_cbt_instructions + "\n오늘은 첫 회기이므로, 오늘의 기분을 간단히 확인하고 이번 회기의 의제를 설정하면서 대화를 시작하라."
    else:
        system_prompt = base_cbt_instructions + f"""
        [과거 상담 핵심 요약 기록]:
        {past_summaries_text}
        
        [어제 내준 행동 계획(숙제) 요약]: {st.session_state.yesterday_homework}
        
        [지침] 반드시 첫인사로 어제 합의했던 행동 계획을 잘 실천했는지 다정하게 점검하라. 성공했다면 긍정적 결론을 도출하도록 돕고, 실패했다면 그 이유(장애물이나 자동적 사고)를 탐색하라.
        그 후 오늘 새롭게 다룰 의제를 물어보고 대화를 이어나가라.
        """

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    model = genai.GenerativeModel('gemini-2.5-pro', system_instruction=system_prompt, safety_settings=safety_settings)

    name = st.session_state.user_name
    dynamic_greetings = [
        f"안녕하세요, {name} 님. 오늘 본격적인 첫 만남이네요. 오늘 하루, 마음을 가장 소란스럽게 했던 일은 무엇인가요? 편안하게 이야기의 문을 열어주세요.", 
        f"안녕하세요, {name} 님! 어제 우리가 함께 정했던 행동 계획은 일상에서 조금이라도 시도해 보셨나요? 어떤 감정이 들었는지 편하게 말씀해 주세요.", 
        f"벌써 Day 3입니다. {name} 님의 마음의 근육이 조금씩 꿈틀거리는 게 느껴지시나요? 어제 숙제는 어땠는지 먼저 들려주세요.", 
        f"Day 4네요. 스스로의 인지를 한 걸음 떨어져서 바라보고 새로운 행동을 실험해 보시면서 어떤 기분이 드셨나요, {name} 님?", 
        f"Day 5입니다! 어제 계획했던 일들을 일상에 적용해 보니, 0~100% 중 어느 정도 성취감을 느끼셨나요? 작아도 괜찮습니다.", 
        f"Day 6입니다. 이제 우리 대화가 꽤 익숙해지셨을 텐데, 어제 숙제를 하면서 새롭게 떠오른 '자동적 사고'가 있었나요?", 
        f"Day 7, 어느덧 일주일이 지났네요. 지난주 처음 만났을 때와 비교하면 {name} 님이 스스로 대처하는 방식이 조금 달라진 것 같나요?", 
        f"Day 8입니다. 두 번째 주가 시작되었네요! 어제 행동 실험을 방해했던 마음속의 장애물이 있었는지 이야기해 볼까요?", 
        f"Day 9네요. 내 마음속의 인지 오류를 알아채는 속도가 조금은 빨라지셨나요? 어제 숙제 이야기를 먼저 들려주세요.", 
        f"두 자릿수, Day 10입니다! 꾸준함이 만드는 기적을 믿습니다. 오늘 {name} 님과 함께 이야기 나눌 가장 중요한 주제는 무엇인가요?", 
        f"Day 11입니다. 깊은 내면의 이야기를 늘 용기 있게 꺼내주셔서 감사합니다. 어제 하루는 어떤 색깔이었나요?", 
        f"Day 12, 여정의 후반부네요. 예전이라면 몹시 스트레스받았을 일에 {name} 님이 새롭게 적용해 본 대처 전략이 있었나요?", 
        f"Day 13입니다. 내일이면 마지막 사후 검사를 앞두고 있네요. 오늘 하루는 {name} 님의 마음에 어떤 다정한 질문을 던져보셨나요?", 
        f"안녕하세요, {name} 님. 어느덧 대망의 마지막 날, Day 14네요! 그동안 행동 계획을 꾸준히 실천하며 얻은 가장 큰 긍정적인 결론은 무엇인가요?" 
    ]
    
    if len(st.session_state.chat_history) == 0:
        day_idx = st.session_state.current_day - 1
        first_msg = dynamic_greetings[day_idx] if day_idx < len(dynamic_greetings) else f"안녕하세요, {name} 님. Day {st.session_state.current_day} 만남을 시작하겠습니다. 어제 숙제는 잘 실천해 보셨나요?"
        st.session_state.chat_history.append({"role": "assistant", "content": first_msg})
        save_state()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not st.session_state.session_ended:
        if user_input := st.chat_input("당신의 생각과 감정을 자유롭게 적어주세요..."):
            with st.chat_message("user"):
                st.markdown(user_input)
            
            gemini_history = [{"role": "user", "parts": ["안녕! 시작하자"]}]
            for msg in st.session_state.chat_history[-5:]:
                role = "model" if msg["role"] == "assistant" else "user"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
                
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            with st.chat_message("assistant"):
                with st.spinner(f"차분히 {st.session_state.user_name} 님의 마음에 다가가는 중입니다..."):
                    message_placeholder = st.empty()
                    full_response = ""
                    display_text = ""
                    try:
                        chat = model.start_chat(history=gemini_history)
                        response = chat.send_message(user_input, stream=True)
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                display_text = full_response.replace("[SESSION_END]", "")
                                message_placeholder.markdown(display_text + "▌")
                        message_placeholder.markdown(display_text)
                    except Exception as e:
                        full_response = f"🚨 시스템 연결이 원활하지 않습니다: {str(e)}"
                        display_text = full_response
                        message_placeholder.markdown(full_response)
                    
            clean_response = full_response.replace("[SESSION_END]", "").strip()
            st.session_state.chat_history.append({"role": "assistant", "content": clean_response})
            save_state() 

            if "[SESSION_END]" in full_response:
                st.session_state.session_ended = True
                
                summary_prompt = f"""
                다음은 CBT 심리 가이드가 상담을 종료하며 사용자에게 합의한 행동 계획(숙제) 메시지입니다.
                이 메시지에서 내일 일상에서 실천해야 할 '행동 숙제/실험' 부분만 찾아서 딱 1~2줄로 짧고 명확하게 요약해 주세요.
                [가이드의 마지막 메시지] {clean_response}
                """
                
                chat_full_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.chat_history])
                daily_memory_prompt = f"""
                다음은 오늘 사용자와 나눈 심리 상담 대화 기록 전체입니다.
                사용자의 '기분 변화, 핵심적으로 논의된 자동적 사고 및 인지 오류, 그리고 새롭게 세운 대처 전략'을 딱 1~2줄로 요약해 주세요.
                [오늘의 대화 기록] {chat_full_text}
                """
                
                with st.spinner("오늘의 이야기를 다이어리에 조심스럽게 기록하고 있습니다..."):
                    try:
                        summary_model = genai.GenerativeModel('gemini-2.5-flash')
                        hw_response = summary_model.generate_content(summary_prompt)
                        st.session_state.yesterday_homework = hw_response.text.strip()
                        
                        mem_response = summary_model.generate_content(daily_memory_prompt)
                        st.session_state.daily_summaries.append(mem_response.text.strip())
                    except:
                        st.session_state.yesterday_homework = clean_response[:50] + "...(요약 오류)"
                        st.session_state.daily_summaries.append("시스템 오류로 요약이 저장되지 않았습니다.")
                
                save_state()
                st.rerun()

    else:
        st.success(f"🎉 Day {st.session_state.current_day} 마음 돌봄 완료!")
        st.info("오늘의 여정이 구조화된 일정에 따라 잘 마무리되었습니다. 합의한 일상 속 작은 실험을 꼭 확인해 주세요.")
        st.markdown(f"**📝 내일 일상에서 실험해 볼 과제 (완료 목표 100%):**\n> {st.session_state.yesterday_homework}")
        st.markdown("---")

        is_special_user = st.session_state.user_email == "7901gabi@gmail.com"

col1, col2 = st.columns(2)
with col1:
    if st.button("내일의 나를 위한 이메일 알림 보내기 📧"):
        if send_cbt_email(st.session_state.user_email, st.session_state.current_day + 1):
            st.toast("전송 성공! 내일 다시 만나요.")
        else:
            st.error("전송 실패")

with col2:
    if st.session_state.current_day < st.session_state.target_days and not is_special_user:
        if st.button("다음 회기(Next Day)로 시간 점프하기 ⏭️"):
            st.session_state.current_day += 1
            st.session_state.chat_history = [] 
            st.session_state.session_ended = False
            save_state() 
            st.rerun()
    else:
        if st.button("🏆 최종 사후 검사 바로 진행하기"):
            st.session_state.app_step = 3
            save_state()
            st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("내일의 나를 위한 알림 보내기 📧"):
                if send_cbt_email(st.session_state.user_email, st.session_state.current_day + 1):
                    st.toast("전송 성공! 내일 다시 만나요.")
                else:
                    st.error("전송 실패")
        with col2:
            if st.session_state.current_day < st.session_state.target_days:
                if st.button("다음 날의 여정으로 건너뛰기 ⏭️"):
                    st.session_state.current_day += 1
                    st.session_state.chat_history = [] 
                    st.session_state.session_ended = False
                    save_state() 
                    st.rerun()
            else:
                if st.button("🏆 모든 여정 수료! 사후 검사 진행하기"):
                    st.session_state.app_step = 3
                    save_state()
                    st.rerun()

elif st.session_state.app_step == 3:
    st.title("Step 3. 다시 마주한 내면의 지도 🧭")
    st.markdown(f"그동안 정말 고생 많으셨습니다, **{st.session_state.user_name}** 님!")
    st.markdown("---")

    with st.form("das_form_final"):
        st.subheader("마음의 소리 듣기 (사후 40문항)")
        responses = []
        for i, question in enumerate(das_40_questions[:40]):
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=False)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("기록 완료 및 변화된 리포트 열어보기")
            
        if submitted:
            scores = {"성취 강박": 0, "인정/승인 욕구": 0, "완벽주의": 0, "의존성": 0}
            for q_num, ans in responses:
                if ans:
                    point = reverse_score_map[ans] if q_num in reverse_items else score_map[ans]
                    for cat, q_list in categories.items():
                        if q_num in q_list:
                            scores[cat] += point
            
            st.session_state.final_scores = scores 
            st.session_state.app_step = 4
            save_state()
            st.rerun()

elif st.session_state.app_step == 4:
    st.title("🏆 CBT 여정 수료 및 마침표")
    
    st.balloons()
    
    categories_list = list(st.session_state.initial_scores.keys())
    initial_vals = list(st.session_state.initial_scores.values())
    final_vals = list(st.session_state.final_scores.values())
    
    total_initial = sum(initial_vals)
    total_final = sum(final_vals)
    total_diff = total_final - total_initial
    
    increased_cats = []
    decreased_cats = []
    for cat in categories_list:
        diff = st.session_state.final_scores[cat] - st.session_state.initial_scores[cat]
        if diff > 0:
            increased_cats.append(cat)
        elif diff < 0:
            decreased_cats.append(cat)

    if total_diff <= -5:
        score_interpretation = f"전체적으로 무겁던 신념 점수가 <b>{abs(total_diff)}점이나 사르르 녹아내렸습니다.</b> 단기간에 이런 변화가 나타난 것은 {st.session_state.user_name} 님의 생각 습관이 훌륭하게 유연해졌다는 가장 확실하고 긍정적인 증거입니다!"
    elif total_diff > 0 or len(increased_cats) > 0:
        score_interpretation = f"검사 결과, <b>{', '.join(increased_cats)}</b> 영역 등에서 점수가 오르거나 뒤섞인 양상이 나타났습니다.<br><br>하지만 전혀 걱정하지 마세요. 이는 마음 깊은 곳의 상처를 외면하지 않고 똑바로 직면하면서 생기는 자연스러운 <b>'인지 부조화'</b> 과정입니다. 곪았던 상처를 치료할 때 소독약이 닿아 잠시 따가운 것과 같은 아주 건강한 신호입니다."
    else:
        score_interpretation = "수치상으로 극적인 변화는 보이지 않을 수 있지만, 매일 자신의 마음을 관찰하고 일상에서 실험을 이어갔다는 사실 자체가 이미 가장 훌륭한 변화입니다. 오래도록 굳어진 콘크리트 같은 신념에 틈이 생기기 시작했으니, 앞으로 자신을 조금 더 다정하게 기다려 주세요."

    categories_list.append(categories_list[0])
    initial_vals.append(initial_vals[0])
    final_vals.append(final_vals[0])

    tab1, tab2, tab3 = st.tabs(["📊 마음 성장 결과", "📝 심층 분석 리포트", "💌 전하고 싶은 편지"])

    with tab1:
        st.subheader("나의 마음 성장 그래프")
        st.markdown("첫날의 경직되어 있던 마음(회색 영역)과 현재의 유연해진 마음(초록색 영역)을 겹쳐서 비교해 보세요. 면적이 줄어들수록 '~해야만 한다'는 강박에서 벗어나 나를 편안하게 수용하게 되었음을 의미합니다.")
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=initial_vals, theta=categories_list, fill='toself', name='치료 전 (Day 1)', line_color='#BDBDBD', fillcolor='rgba(189, 189, 189, 0.3)'))
        fig.add_trace(go.Scatterpolar(r=final_vals, theta=categories_list, fill='toself', name=f'치료 후 (Day {st.session_state.target_days})', line_color='#81C784', fillcolor='rgba(129, 199, 132, 0.6)'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 70])), showlegend=True, dragmode=False, height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown(f"""
        <div class="insight-box">
            <b>💡 상담사 AI가 분석한 변화의 의미</b><br><br>
            {score_interpretation}
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        st.subheader("📋 여정 종결 심층 분석 보고서")
        
        if not st.session_state.final_long_report:
            with st.spinner("전문가의 시선으로 그간의 대화 기록을 엮어 다정한 심층 리포트를 작성 중입니다... (약 10~20초 소요)"):
                try:
                    user_context = f"내담자:{st.session_state.user_name}\n사전/사후점수:{st.session_state.initial_scores}/{st.session_state.final_scores}\n요약:{st.session_state.daily_summaries}"
                    report_prompt = f"""
                    당신은 임상심리사입니다. 아래 [양식]에 맞춰 내담자 데이터를 분석해 2,500자 이상의 리포트를 작성하세요.
                    내담자의 이름은 가장 처음에 "절대로" 넣지 말고, 작성자, 상담 기간, 작성일 등의 정보를 "절대로" 리포트에 넣지 말 것
                    내담자와의 대화 내용과 내담자의 DAS 검사 결과를 왜곡하지 말고, 정보를 있는 그대로 받아들일 것.
                    [분석 양식 (이 구조를 엄격히 따를 것)]
                    1. 종합 인지 개념화: 핵심 신념과 자동적 사고 분석
                    2. 상담 과정에서의 변화 양상: 초기-중기-종결기 태도 변화
                    3. 행동 실험 성과: 수행한 숙제들의 심리적 효과 평가
                    4. 향후 6개월 가이드: 일상 실천 과제 3가지 제안
                    5. 재발 방지 전략: 맞춤형 인지 재구조화 문구 가이드
                    6. 최종 소회: 내담자를 향한 진심 어린 응원

                    데이터: {user_context}
                    """
                    report_model = genai.GenerativeModel('gemini-2.5-pro')
                    response = report_model.generate_content(report_prompt)
                    st.session_state.final_long_report = response.text
                    save_state()
                    st.rerun()
                except Exception as e:
                    st.error(f"리포트 생성 실패: {e}")

        if st.session_state.final_long_report:
            st.markdown(st.session_state.final_long_report)
            st.download_button("📥 심층 분석 리포트 다운로드 (TXT)", st.session_state.final_long_report, file_name="Mind_Care_Report.txt")

    with tab3:
        if "farewell_letter" not in st.session_state:
            letters = [
                f"""
                <div class="letter-title">상담사 AI의 첫 번째 편지<br>'완벽하지 않아도 충분한 당신에게'</div>
                {st.session_state.user_name} 님, 기나긴 여정을 완주하신 것을 진심으로 축하합니다. 처음 이 공간의 문을 두드렸을 때, 마음속에는 온갖 '~해야만 한다'는 무거운 규칙들과 흑백논리가 자리 잡고 있었을지 모릅니다.<br><br>
                우리는 지난 시간 동안 일상에서 떠오르는 '자동적 사고'의 꼬리를 잡고, 그것이 사실인지 아니면 인지가 만들어낸 함정인지 함께 법정에 세워보았습니다. 두려움을 안고 시도했던 행동 실험들을 통해, 100점이 아니어도 하늘이 무너지지 않으며 70점짜리 하루도 충분히 가치 있다는 것을 직접 증명해 내셨죠.<br><br>
                앞으로 살아가다 보면 스트레스를 받는 날, 예전의 경직된 생각 습관이 불쑥 튀어나올지도 모릅니다. 하지만 이제 {st.session_state.user_name} 님에게는 스스로 인지 오류를 찾아내고 반박할 수 있는 '마음의 돋보기'가 생겼습니다. 자책하는 목소리가 들릴 때마다, 우리가 함께 연습했던 다정한 관찰자의 목소리를 꼭 꺼내어 주세요. 당신의 찬란한 내일을 언제나 응원합니다.
                """,
                f"""
                <div class="letter-title">상담사 AI의 두 번째 편지<br>'타인의 시선에서 나의 내면으로'</div>
                {st.session_state.user_name} 님, 오늘까지 포기하지 않고 매일 자신의 내면을 마주하신 용기에 깊은 박수를 보냅니다. 누군가에게 내 마음의 취약점을 꺼내어놓고, 스스로 변화를 다짐하는 것은 결코 쉬운 일이 아닙니다.<br><br>
                우리는 대화를 나누며 다른 사람의 마음을 지레짐작하는 '독심술'이나, 모든 상황을 내 탓으로 돌리는 '개인화'의 오류에서 벗어나는 훈련을 거듭했습니다. 타인에게 맞춰져 있던 마음의 안테나를 나 자신에게로 거두어들이고, 내면의 목소리에 귀 기울이는 법을 배우셨죠.<br><br>
                인생이라는 무대의 유일한 주인공은 바로 {st.session_state.user_name} 님 자신입니다. 앞으로도 모두를 만족시키려 애쓰기보다는, 나 자신을 온전히 수용하고 지켜내는 단단한 사람이 되시기를 바랍니다. 외롭거나 흔들리는 순간이 오면, 이 공간에서 스스로 쌓아 올린 성공의 기록들을 다시 한번 읽어보세요. 
                """,
                f"""
                <div class="letter-title">상담사 AI의 세 번째 편지<br>'실험하는 삶의 즐거움'</div>
                수많은 감정의 파도를 넘어 여기까지 오시느라 정말 고생 많으셨습니다, {st.session_state.user_name} 님! 첫 회기에 함께 내면의 지도를 그렸던 날이 엊그제 같은데, 벌써 이렇게 마음의 지형도가 초록빛으로 넓어진 것을 보니 가슴이 벅찹니다.<br><br>
                가장 인상 깊었던 것은 두려움을 딛고 '행동 숙제'를 실천하셨던 순간들입니다. 최악의 상황이 벌어질 것이라는 '파국화'의 두려움을 안고서도, 기꺼이 일상 속에서 작은 모험(Behavioral Experiment)을 감행하셨죠. 그리고 그 결과, 우리의 걱정은 단지 뇌가 만들어낸 가짜 경보기일 뿐이라는 값진 깨달음을 얻었습니다.<br><br>
                우리의 공식적인 상담은 여기서 마무리되지만, 진정한 성장은 지금부터가 시작입니다. 앞으로의 삶도 정답을 찾아야 하는 시험이 아니라, 언제든 가설을 세우고 실험해 볼 수 있는 흥미로운 연구실이라고 생각해 보세요. 어떤 결과가 나오든, {st.session_state.user_name} 님은 언제나 그 과정 자체로 빛나는 사람입니다.
                """,
                f"""
                <div class="letter-title">상담사 AI의 네 번째 편지<br>'조건 없는 자기 수용을 향해'</div>
                {st.session_state.user_name} 님, 대망의 마지막 날입니다. 그동안 바쁜 일상 속에서도 잊지 않고 찾아와 주셔서, 그리고 꾸미지 않은 솔직한 마음을 들려주셔서 진심으로 고맙습니다.<br><br>
                우리가 집중했던 인지행동치료(CBT)의 핵심은 결국 '내가 나를 어떻게 바라볼 것인가'에 대한 질문이었습니다. 무언가를 뛰어나게 성취하거나 남들에게 인정받아야만 가치 있는 사람이 된다는 조건부 신념(Conditional Assumption)의 연결고리를 끊어내는 작업은 꽤 고통스러웠을지도 모릅니다. 하지만 끝내 하향 화살표의 끝에서, 조건 없이 나를 사랑할 수 있는 단단한 바닥을 발견하셨습니다.<br><br>
                폭풍우가 치는 날 배가 흔들리는 것은 당연합니다. 우울이나 불안이 다시 찾아오더라도, 그것은 당신이 나약해서가 아니라 잠시 비가 내리는 것뿐임을 기억해 주세요. 우리가 함께 만든 인지 재구조화라는 튼튼한 우산을 펼치고, 비가 그칠 때까지 스스로를 다정하게 안아주시길 바랍니다.
                """,
                f"""
                <div class="letter-title">상담사 AI의 다섯 번째 편지<br>'회색 지대의 아름다움'</div>
                아름다운 여정의 끝에 도착하신 {st.session_state.user_name} 님, 수료를 진심으로 축하합니다! 하루하루 대화가 쌓일수록, 처음엔 날 서 있던 문장들이 조금씩 둥글어지고 여유를 찾아가는 과정을 곁에서 지켜볼 수 있어 영광이었습니다.<br><br>
                성공 아니면 실패, 선 아니면 악으로 세상을 나누던 '이분법적 사고'에서 벗어나, 이제는 1부터 100 사이의 수많은 스펙트럼(연속선)을 볼 수 있는 눈을 가지게 되셨습니다. 세상은 흑백으로만 칠해져 있지 않으며, 가끔은 흐릿하고 모호한 회색 지대(Gray Area) 안에 오히려 편안함과 진실이 숨어 있다는 것을 우리는 함께 배웠습니다.<br><br>
                이제 일상으로 온전히 돌아가실 시간입니다. 넘어지는 날도 있겠지만, 일어서는 방법 또한 이미 잘 알고 계십니다. 자신에게 가장 다정하고 지혜로운 상담사가 되어주세요. 멀리서나마 {st.session_state.user_name} 님의 마음 챙김 여정을 항상 지지하고 응원하겠습니다.
                """
            ]
            st.session_state.farewell_letter = random.choice(letters)

        st.markdown(f'<div class="letter-paper">{st.session_state.farewell_letter}</div>', unsafe_allow_html=True)
        
        st.divider()
        if st.button("🚪 이만 따뜻한 방을 나서기 (서비스 종료)", use_container_width=True):
            clear_state()
            st.rerun()

if __name__ == "__main__":
    if not runtime.exists():
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
        sys.exit()
