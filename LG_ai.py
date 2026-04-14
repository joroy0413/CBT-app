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

# ==========================================
# 1. 페이지 및 UI 기본 설정
# ==========================================
st.set_page_config(page_title="CBT 자기분석 가이드", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stChatMessageAvatar { display: none; }
    .report-box { background-color: #f9f9f9; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #4CAF50; }
    .report-title { color: #2E7D32; font-weight: bold; font-size: 1.2em; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

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

# 요청에 맞춰 매우 세밀하고 방대한 양의 분석 결과로 업데이트
cbt_explanations_detailed = {
    "성취 강박": """
    <div class="report-box">
        <div class="report-title">📌 심층 인지 오류 분석: 조건부 가치 부여와 당위적 사고</div>
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
        <div class="report-title">📌 심층 인지 오류 분석: 독심술과 타인 지향적 가치관</div>
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
        <div class="report-title">📌 심층 인지 오류 분석: 흑백논리와 당위적 명제의 함정</div>
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
        <div class="report-title">📌 심층 인지 오류 분석: 파국화와 자기 효능감 저하</div>
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
    "외모가 뛰어나고, 똑똑하고, 돈이 많고, 창의적이지 않으면 행복해지기 어렵다.", "행복은 다른 사람들이 나를 어떻게 생각하느냐보다 나 자신에 대한 나의 태도에 더 많이 달려 있다.", "내가 실수를 하면 사람들은 아마 나를 덜 좋게 생각할 것이다.", "내가 항상 잘하지 않으면, 사람들은 나를 존중하지 않을 것이다.", "작은 위험이라도 감수하는 것은 어리석은 일이다. 왜냐하면 손실이 재앙이 될 수 있기 때문이다.", "특별한 재능이 없어도 다른 사람의 존경을 받을 수 있다.", "내가 아는 대부분의 사람들이 나를 우러러보지 않으면 나는 행복할 수 없다.", "누군가에게 도움을 청하는 것은 나약함의 표시이다.", "내가 다른 사람들만큼 잘하지 못한다면, 그것은 내가 열등한 인간이라는 뜻이다.", "내가 일에서 실패한다면, 나는 인간으로서 실패한 것이다.", "무언가를 아주 잘해낼 수 없다면, 그것을 하는 것은 별 의미가 없다.", "실수를 통해 배울 수 있으므로 실수하는 것은 괜찮다.", "누군가 내 의견에 동의하지 않는다면, 그것은 아마도 나를 좋아하지 않기 때문일 것이다.", "부분적으로라도 실패한다면, 그것은 완전히 실패한 것과 다름없이 끔찍하다.", "다른 사람들이 나의 진짜 모습을 알게 된다면, 나를 안 좋게 생각할 것이다.", "내가 사랑하는 사람이 나를 사랑하지 않는다면 나는 아무것도 아니다.", "최종 결과와 상관없이 활동 자체에서 즐거움을 얻을 수 있다.", "무언가를 시작하기 전에는 성공할 만한 합당한 가능성이 있어야 한다.", "사람으로서 나의 가치는 다른 사람들이 나를 어떻게 생각하느냐에 크게 좌우된다.", "내 자신에게 가장 높은 기준을 세우지 않으면, 나는 이류 인간이 될 가능성이 높다.", "내가 가치 있는 사람이 되려면, 적어도 한 가지 중요한 측면에서는 진정으로 뛰어나야 연다.", "좋은 아이디어를 가진 사람은 그렇지 않은 사람보다 더 가치 있다.", "내가 실수를 한다면 화를 내야 마땅하다.", "나에 대한 내 자신의 의견이 다른 사람들의 의견보다 더 중요하다.", "선량하고 도덕적이며 가치 있는 사람이 되려면 도움이 필요한 모든 사람을 도와야 한다.", "질문을 하면 내가 열등해 보인다.", "내게 중요한 사람들에게 인정받지 못하는 것은 끔찍한 일이다.", "의지할 다른 사람이 없다면, 슬퍼질 수밖에 없다.", "내 자신을 노예처럼 채찍질하지 않아도 중요한 목표를 달성할 수 있다.", "누군가에게 야단을 맞고도 기분이 상하지 않을 수 있다.", "다른 사람들이 나에게 잔인하게 굴 수 있기 때문에 나는 다른 사람들을 믿을 수 없다.", "다른 사람들이 나를 싫어한다면 나는 행복할 수 없다.", "다른 사람들을 기쁘게 하기 위해 내 자신의 이익을 포기하는 것이 최선이다.", "나의 행복은 나 자신보다 다른 사람들에게 더 많이 달려 있다.", "행복해지기 위해 다른 사람들의 승인이 필요한 것은 아니다.", "문제를 회피하면 문제는 사라지는 경향이 있다.", "인생에서 많은 좋은 것들을 놓치더라도 나는 행복할 수 있다.", "다른 사람들이 나에 대해 어떻게 생각하는지는 매우 중요하다.", "다른 사람들과 고립되면 불행해질 수밖에 없다.", "다른 사람의 사랑을 받지 못해도 나는 행복을 찾을 수 있다."
]

# ==========================================
# 3. 항시 표출 사이드바 UI (언제든 DAS 확인 가능)
# ==========================================
if st.session_state.app_step >= 1 and st.session_state.initial_scores:
    with st.sidebar:
        st.header("📊 나의 마음 기준선 (DAS-40)")
        scores = st.session_state.initial_scores
        df_side = pd.DataFrame(dict(r=list(scores.values()), theta=list(scores.keys())))
        df_side = pd.concat([df_side, df_side.iloc[[0]]], ignore_index=True)
        
        fig_side = px.line_polar(df_side, r='r', theta='theta', line_close=True, range_r=[0, 70])
        fig_side.update_traces(fill='toself', fillcolor='rgba(255, 75, 75, 0.3)', line_color='red')
        fig_side.update_layout(
            polar=dict(radialaxis=dict(visible=False)),
            margin=dict(l=20, r=20, t=20, b=20),
            dragmode=False
        )
        st.plotly_chart(fig_side, use_container_width=True, config={'displayModeBar': False})
        
        max_cat_side = max(scores, key=scores.get)
        st.warning(f"🚨 **우선 주의 영역: {max_cat_side}**")
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

# --- 화면 A (Step 0): 온보딩 & 사전 검사 ---
if st.session_state.app_step == 0:
    st.title("Step 1. 내면의 지도 그리기")
    
    st.info("💡 **기존 참여자이신가요?** 진행 중인 이메일을 입력하시면 클라우드에서 이전 상담 기록을 불러옵니다.")
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
    st.markdown("처음 오셨다면, 본격적인 대화에 앞서 **DAS-40 사전 검사**를 진행합니다. 깊은 생각보다 직관적으로 떠오르는 답변을 선택해 주세요.")

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
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=False)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("검사 완료 및 설정 저장")
            
        if submitted:
            if not user_email:
                st.error("진행 상황 저장을 위해 이메일 주소는 필수입니다.")
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
                save_state() 
                st.rerun()

# --- 화면 B (Step 1): 심층 검사 결과 리포트 ---
elif st.session_state.app_step == 1:
    st.title("Step 1.5. 인지적 기준선 심층 분석 결과")
    st.markdown("작성해주신 DAS-40 검사를 바탕으로 내담자님의 마음 지형도를 분석했습니다. 아래의 그래프와 심층 분석 리포트를 꼼꼼히 읽어보세요.")
    
    scores = st.session_state.initial_scores
    max_cat = max(scores, key=scores.get)
    
    # 상단 그래프
    df = pd.DataFrame(dict(r=list(scores.values()), theta=list(scores.keys())))
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0, 70])
    fig.update_traces(fill='toself', fillcolor='rgba(255, 75, 75, 0.2)', line_color='red')
    fig.update_layout(dragmode=False, height=400) 
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.error(f"🚨 진단 결과: 현재 가장 집중적인 CBT 개입이 필요한 핵심 역기능적 신념은 **[{max_cat}]** 영역입니다.")
    
    # 방대한 분석 내용 렌더링
    st.markdown(cbt_explanations_detailed[max_cat], unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("💡 **안내:** 이 심층 분석 결과는 본격적인 상담 중 언제든지 좌측 사이드바(메뉴)를 열어 다시 확인할 수 있습니다.")
    
    if st.button("▶ Day 1 상담 및 인지 훈련 시작하기", use_container_width=True):
        st.session_state.app_step = 2
        save_state() 
        st.rerun()

# --- 화면 C (Step 2): 필링굿 문서 기반 프롬프트 엔지니어링 챗봇 ---
elif st.session_state.app_step == 2:
    st.title(f"CBT 심리 가이드 - Day {st.session_state.current_day} / {st.session_state.target_days}")
    st.caption("안전하고 따뜻한 공간입니다. 마음속 이야기를 편하게 꺼내어 주세요.")
    
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    scores = st.session_state.category_scores
    max_cat = max(scores, key=scores.get)
    past_summaries_text = "\n".join([f"- Day {i+1}: {summary}" for i, summary in enumerate(st.session_state.daily_summaries)]) if st.session_state.daily_summaries else "아직 이전 상담 기록이 없습니다."

    # [프롬프트 엔지니어링] 제공된 <필링굿> docx 파일 내용 완벽 복붙 이식
    base_cbt_instructions = f"""
    당신은 인지행동치료(CBT) 원칙에 기반하여 사용자의 인지 재구조화를 돕는 전문 AI 심리 상담사이다.
    [사용자 취약 영역]: {max_cat}

    [CBT 핵심 치료 원칙 및 필수 지침 - '필링굿' 가이드라인 완벽 적용]
    1. 공감을 적극적으로 표현하고, 인지모델의 맥락에서 추가 정보를 요청하라. 사고의 타당성 검증을 위해 동의를 구하라.
    2. 방어적이지 않은 태도와 호기심을 유지하며, 내담자에 대한 당신의 기대치를 확인하고 있는 그대로 수용하기 위해 노력하라.
    3. 회기 구조화 (반드시 지킬 것): 
       - 기분 확인 -> 의제 설정 -> 지난 활동 계획(숙제) 검토 -> 문제 논의(자동적 사고 도출 및 대응) -> 새로운 활동 계획 공동 설정 -> 피드백 이끌어 내기.
    4. 내담자가 불필요한 세부 정보를 제공하거나 옆길로 새면, 부드럽게 중단하는 것이 중요하다. (예: "방해해서 죄송하지만, 저는 이 부분에 초점을 맞추고 싶어요.")
    5. 목표 설정의 어려움 극복: 내담자가 목표를 설정하기 어려워하면 '기적 질문(해결 중심의 단기 치료)'을 시도하라. "만약 기적이 일어나서 내일 아침 전혀 우울하지/불안하지 않다면 무엇이 다를까요?"
    6. 열망 끌어내기 및 궁극적 의미 도출: "인생을 위해 무엇을 원하나요?", "당신의 열망과 목표를 달성하면 어떤 점이 특히 좋을까요?" 라고 질문하여 가치를 식별하라.
    7. 활동 계획(행동 실험/숙제)의 고안 및 준수 강화:
       - 일률적인 계획(one size fits all)은 없다. 내담자와 협력하여 '공동으로' 행동 계획을 설정하라. 행동 계획을 어렵게 만들기보단 쉽게 만들어라.
       - 좋은 행동 계획은 자신의 경험에 대해 긍정적인 결론을 내리고, 인지를 평가/수정하며, 새로운 행동을 실험하는 것이다.
       - [매우 중요] 행동 계획 설정 후 **완료 가능성**을 반드시 확인하라: "0~100%의 확률로, 내일 이 작업을 수행할 가능성은 얼마나 되나요?"
       - 만약 90% 미만이라고 답하면, 장애물을 예상하고 은밀하게 예행연습(covert rehearsal)을 하도록 돕거나, 행동 계획을 더 쉽게 수정하라.

    [상담사로서의 태도]
    - 내가 내담자로서 대우받고 싶은 방식으로 똑같이 대우하라. 진정한 따뜻함, 관심, 긍정적 존중을 보여주어라.
    - 내담자가 이전 치료(과거의 시도)가 효과 없었다며 회의적이라면, 긍정적으로 강화하라 ("그렇게 말씀해주셔서 좋네요. 여기서는 다를 것입니다.")
    
    [시스템 자동화 제어 지침 - 반드시 엄수]
    - 글씨 강조를 위해 마크다운 '*' 기호를 남용하지 마라.
    - [중요] 단 1~2번 대화만으로 섣불리 종료하지 마라. 하향 화살표 기법 등을 통해 충분한 탐색(최소 4턴 이상)을 거친 후, 대화 후반부에 '행동 계획(숙제)'을 0~100% 확률로 확인하는 과정까지 마쳐라.
    - **[핵심 자동화 트리거]** 내담자가 행동 숙제를 일상에서 해보기로 동의하고, 오늘의 상담을 마무리하는 요약 및 피드백까지 끝났다고 스스로 판단되면 당신의 마지막 답변 맨 끝에 반드시 `[SESSION_END]` 라는 태그를 적어라. 이 태그가 인식되면 시스템이 자동으로 상담을 종료한다.
    """

    if st.session_state.current_day == 1:
        system_prompt = base_cbt_instructions + "\n오늘은 첫 회기이므로, 오늘의 스트레스나 마음 상태(기분 확인)를 묻고 이번 회기의 의제를 설정하면서 대화를 시작하라."
    else:
        system_prompt = base_cbt_instructions + f"""
        [과거 상담 핵심 요약 기록]:
        {past_summaries_text}
        
        [어제 내준 행동 계획(숙제) 요약]: {st.session_state.yesterday_homework}
        
        [지침] 반드시 첫인사로 어제 합의했던 행동 계획을 잘 실천했는지 다정하게 점검하라. 성공했다면 긍정적 결론을 도출하도록 돕고, 실패했다면 그 이유(자동적 사고)를 탐색하라.
        그 후 오늘 새롭게 다룰 문제(의제 설정)를 물어보고 대화를 이어나가라.
        """

    model = genai.GenerativeModel('gemini-3.1-pro-preview', system_instruction=system_prompt)

    dynamic_greetings = [
        "안녕하세요. 오늘 본격적인 첫 상담이네요. 오늘 하루, 당신의 마음을 가장 불편하게 했던 일은 무엇인가요? 오늘의 대화 주제를 정해볼까요?", 
        "안녕하세요! 어제 우리가 함께 정했던 행동 계획은 일상에서 조금 시도해 보셨나요? 편하게 말씀해 주세요.", 
        "Day 3입니다. 마음의 근육이 조금씩 붙고 있는 게 느껴지시나요? 어제 숙제는 어땠는지 먼저 들려주세요.", 
        "Day 4네요. 스스로의 인지를 평가하고 새로운 행동을 실험해 보시면서 어떤 기분이 드셨나요?", 
        "Day 5입니다! 어제 계획했던 일들을 일상에 적용해 보니, 0~100% 중 어느 정도 성취감을 느끼셨나요?", 
        "Day 6입니다. 이제 우리 대화가 꽤 익숙해지셨을 텐데, 어제 숙제를 하면서 새롭게 떠오른 '자동적 사고'가 있었나요?", 
        "Day 7, 어느덧 일주일이 지났네요. 지난주와 비교했을 때 스스로 대처하는 방식이 조금 달라진 것 같나요?", 
        "Day 8입니다. 두 번째 주가 시작되었네요! 어제 행동 실험을 방해했던 어떤 장애물이 있었는지 이야기해 볼까요?", 
        "Day 9네요. 인지 오류를 찾아내는 속도가 조금은 빨라지셨나요? 어제 숙제 이야기를 먼저 들려주세요.", 
        "두 자릿수, Day 10입니다! 꾸준함의 힘을 믿습니다. 오늘 우리가 함께 이야기 나눌 가장 중요한 의제는 무엇인가요?", 
        "Day 11입니다. 깊은 내면의 이야기를 꺼내주셔서 항상 감사합니다. 어제 하루는 어떻게 보내셨나요?", 
        "Day 12, 여정의 후반부네요. 예전이라면 스트레스받았을 일에 당신이 새롭게 적용해 본 대처 전략이 있었나요?", 
        "Day 13입니다. 내일이면 마지막 사후 검사를 앞두고 있네요. 오늘 하루는 내 마음에 어떤 질문을 던져보셨나요?", 
        "안녕하세요. 어느덧 대망의 마지막 날, Day 14네요! 그동안 행동 계획을 꾸준히 실천하며 얻은 가장 큰 긍정적인 결론은 무엇인가요?" 
    ]
    
    if len(st.session_state.chat_history) == 0:
        day_idx = st.session_state.current_day - 1
        first_msg = dynamic_greetings[day_idx] if day_idx < len(dynamic_greetings) else f"안녕하세요, Day {st.session_state.current_day} 상담을 시작하겠습니다. 어제 숙제는 잘 실천해 보셨나요?"
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
            for msg in st.session_state.chat_history[-6:]:
                role = "model" if msg["role"] == "assistant" else "user"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
                
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            with st.chat_message("assistant"):
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
                    full_response = "상담 시스템 처리 중 오류가 발생했습니다. 다시 말씀해 주시겠어요?"
                    display_text = full_response
                    message_placeholder.markdown(full_response)
                    
            clean_response = full_response.replace("[SESSION_END]", "").strip()
            st.session_state.chat_history.append({"role": "assistant", "content": clean_response})
            save_state() 

            if "[SESSION_END]" in full_response:
                st.session_state.session_ended = True
                
                # --- 요약 파이프라인 ---
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
                
                with st.spinner("오늘의 인지개념화를 정리하고 행동 계획을 기록하는 중입니다..."):
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
        st.success(f"🎉 Day {st.session_state.current_day} 회기 목표 달성 및 상담 완료!")
        st.info("오늘의 상담이 구조화된 일정에 따라 잘 마무리되었습니다. 내담자님과 합의한 행동 계획을 꼭 확인해 주세요.")
        st.markdown(f"**📝 내일 일상에서 실험해 볼 과제 (완료 목표 100%):**\n> {st.session_state.yesterday_homework}")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("내일의 나를 위한 이메일 알림 보내기 📧"):
                if send_cbt_email(st.session_state.user_email, st.session_state.current_day + 1):
                    st.toast("전송 성공! 내일 다시 만나요.")
                else:
                    st.error("전송 실패")
        with col2:
            if st.session_state.current_day < st.session_state.target_days:
                if st.button("다음 회기(Next Day)로 시간 점프하기 ⏭️"):
                    st.session_state.current_day += 1
                    st.session_state.chat_history = [] 
                    st.session_state.session_ended = False
                    save_state() 
                    st.rerun()
            else:
                if st.button("🏆 모든 일정 수료! 최종 사후 검사 진행하기"):
                    st.session_state.app_step = 3
                    save_state()
                    st.rerun()

# --- 화면 D (Step 3): 사후 검사 진행 ---
elif st.session_state.app_step == 3:
    st.title("Step 3. 최종 사후 검사 (치료 진전도 확인)")
    st.markdown("그동안 정말 고생 많으셨습니다. 첫 회기에 설정했던 우리의 광범위한 목표가 얼마나 달성되었는지, 역기능적 신념이 얼마나 완화되었는지 객관적으로 평가해 보겠습니다.")
    st.markdown("---")

    with st.form("das_form_final"):
        st.subheader("DAS-40 사후 문항")
        responses = []
        for i, question in enumerate(das_40_questions[:40]):
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=False)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("사후 검사 완료 및 비교 리포트 보기")
            
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

# --- 화면 E (Step 4): 사전/사후 방대한 결과 비교 ---
elif st.session_state.app_step == 4:
    st.title("📈 나의 마음 성장 및 인지 변화 리포트")
    st.markdown("첫날의 경직되어 있던 인지 도식(회색 영역)과 현재의 유연해진 인지 도식(초록색 영역)을 비교해 보세요. 면적이 줄어들수록 '당위적 사고'에서 벗어나 자신을 있는 그대로 수용하게 되었음을 의미합니다.")
    
    categories_list = list(st.session_state.initial_scores.keys())
    initial_vals = list(st.session_state.initial_scores.values())
    final_vals = list(st.session_state.final_scores.values())
    
    categories_list.append(categories_list[0])
    initial_vals.append(initial_vals[0])
    final_vals.append(final_vals[0])
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=initial_vals, theta=categories_list, fill='toself', name='치료 전 (Day 1)', line_color='gray', fillcolor='rgba(128, 128, 128, 0.4)'))
    fig.add_trace(go.Scatterpolar(r=final_vals, theta=categories_list, fill='toself', name=f'치료 후 (Day {st.session_state.target_days})', line_color='green', fillcolor='rgba(0, 255, 0, 0.4)'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 70])), showlegend=True, dragmode=False, height=500)
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.success("🎉 모든 인지행동치료(CBT) 여정을 훌륭하게 마친 것을 진심으로 축하합니다!")
    st.markdown("""
    <div class="report-box" style="border-left-color: #2196F3;">
        <div class="report-title" style="color: #1976D2;">상담사 AI의 마지막 편지 💌</div>
        우리는 지난 시간 동안 함께 자동적 사고를 도출하고, 그 이면에 있는 조건적 가정과 핵심 신념을 들여다보았습니다.<br>
        때로는 행동 실험을 수행하기 전 두려움에 휩싸여 0%의 완료 가능성을 이야기한 적도 있었고, 결국 은밀한 예행연습을 통해 용기를 내어 100% 실천해 낸 날도 있었습니다.<br><br>
        <b>기억해 주세요.</b> 부정적인 감정이나 인지 오류가 앞으로 다시는 찾아오지 않는 것은 아닙니다. 
        하지만 이제 당신에게는 스스로 자신의 인지를 평가하고 반응하며, 일상에서 건강한 행동 계획을 세울 수 있는 <b>'인지 재구조화 도구'</b>가 생겼습니다. <br>
        자신에 대해 긍정적인 결론을 내리는 하루하루가 되시기를 온 마음을 다해 응원합니다.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    if not runtime.exists():
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
        sys.exit()
