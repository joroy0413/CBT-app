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
    key_dict = dict(st.secrets["firebase"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict["project_id"])
    return db

# --- 데이터 저장/불러오기 함수 (Firebase 연동) ---
def save_state():
    """현재 세션 상태를 Firebase Firestore에 이메일 기준으로 저장합니다."""
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
    "성취 강박": """
    **[인지 오류 분석: 당위적 사고 및 흑백논리]**
    현재 자신의 가치를 '무엇을 이루었는가(결과와 성과)'로 엄격하게 평가하는 경향이 엿보입니다. 성공할 때는 자존감이 높아지지만, 뜻대로 되지 않거나 실수를 했을 때 '나는 무가치하다'는 파국적인 결론으로 도약할 위험이 큽니다. 성취와 자신의 존재 가치를 강하게 결속시키는 인지적 협착 상태일 수 있습니다.
    
    **[CBT 훈련 목표]**
    조건 없는 자기 수용을 연습합니다. '반드시 성공해야만 해'라는 당위적인 사고를 찾아내고, 결과와 무관하게 나의 가치는 변하지 않는다는 점을 증명하는 행동 실험을 진행해 보겠습니다.
    """,
    "인정/승인 욕구": """
    **[인지 오류 분석: 독심술 및 타인 지향적 가치관]**
    타인의 시선이나 평가, 사랑과 인정에 감정의 통제권을 내어주고 있는 상태입니다. 타인의 미세한 표정 변화에도 '나를 싫어하는 게 아닐까?' 지레짐작하는 독심술(Mind-reading) 오류를 범하기 쉽고, 미움받는 것에 대한 과도한 두려움을 가질 수 있습니다.
    
    **[CBT 훈련 목표]**
    내 감정의 주도권을 타인에게서 나 자신에게로 가져오는 연습을 합니다. 모든 사람을 만족시킬 수 없다는 현실을 수용하고, 외부의 승인 없이도 스스로의 가치를 인정할 수 있는 내적 기준을 세우는 훈련을 진행합니다.
    """,
    "완벽주의": """
    **[인지 오류 분석: 흑백논리 및 과도한 일반화]**
    자신에게 매우 높고 엄격한 잣대를 들이대며, '100점이 아니면 0점'이라는 흑백논리적 사고에 갇혀 있을 가능성이 높습니다. 사소한 결점이나 실수 하나를 전체의 실패로 과도하게 일반화하여 스스로를 소진시키기 쉽습니다.
    
    **[CBT 훈련 목표]**
    실수를 성장의 과정으로 받아들이는 인지 재구조화를 진행합니다. 완벽하지 않아도 충분히 훌륭하다는 '적당함의 미학(Good enough)'을 배우고, 스스로에게 허용적인 태도를 가질 수 있도록 하향 화살표 기법을 적용하겠습니다.
    """,
    "의존성": """
    **[인지 오류 분석: 파국화 및 자기 능력 과소평가]**
    어려운 상황을 마주했을 때 스스로 판단하고 해결하기보다는, 타인의 조언이나 지지가 있어야만 안심하는 경향이 있습니다. 최악의 상황을 상상하는 '파국화' 오류로 인해 스스로의 문제 해결 능력을 실제보다 심각하게 과소평가하고 있을 수 있습니다.
    
    **[CBT 훈련 목표]**
    독립적인 결정의 근육을 키워나갑니다. 혼자서 내린 결정의 결과가 치명적이지 않다는 것을 인지 행동 실험을 통해 확인하고, 내 안에 이미 내재된 문제 해결 능력을 객관적으로 들여다보는 연습을 진행하겠습니다.
    """
}

das_40_questions = [
    "외모가 뛰어나고, 똑똑하고, 돈이 많고, 창의적이지 않으면 행복해지기 어렵다.",
    "행복은 다른 사람들이 나를 어떻게 생각하느냐보다 나 자신에 대한 나의 태도에 더 많이 달려 있다.",
    "내가 실수를 하면 사람들은 아마 나를 덜 좋게 생각할 것이다.",
    "내가 항상 잘하지 않으면, 사람들은 나를 존중하지 않을 것이다.",
    "작은 위험이라도 감수하는 것은 어리석은 일이다. 왜냐하면 손실이 재앙이 될 수 있기 때문이다.",
    "특별한 재능이 없어도 다른 사람의 존경을 받을 수 있다.",
    "내가 아는 대부분의 사람들이 나를 우러러보지 않으면 나는 행복할 수 없다.",
    "누군가에게 도움을 청하는 것은 나약함의 표시이다.",
    "내가 다른 사람들만큼 잘하지 못한다면, 그것은 내가 열등한 인간이라는 뜻이다.",
    "내가 일에서 실패한다면, 나는 인간으로서 실패한 것이다.",
    "무언가를 아주 잘해낼 수 없다면, 그것을 하는 것은 별 의미가 없다.",
    "실수를 통해 배울 수 있으므로 실수하는 것은 괜찮다.",
    "누군가 내 의견에 동의하지 않는다면, 그것은 아마도 나를 좋아하지 않기 때문일 것이다.",
    "부분적으로라도 실패한다면, 그것은 완전히 실패한 것과 다름없이 끔찍하다.",
    "다른 사람들이 나의 진짜 모습을 알게 된다면, 나를 안 좋게 생각할 것이다.",
    "내가 사랑하는 사람이 나를 사랑하지 않는다면 나는 아무것도 아니다.",
    "최종 결과와 상관없이 활동 자체에서 즐거움을 얻을 수 있다.",
    "무언가를 시작하기 전에는 성공할 만한 합당한 가능성이 있어야 한다.",
    "사람으로서 나의 가치는 다른 사람들이 나를 어떻게 생각하느냐에 크게 좌우된다.",
    "내 자신에게 가장 높은 기준을 세우지 않으면, 나는 이류 인간이 될 가능성이 높다.",
    "내가 가치 있는 사람이 되려면, 적어도 한 가지 중요한 측면에서는 진정으로 뛰어나야 연다.",
    "좋은 아이디어를 가진 사람은 그렇지 않은 사람보다 더 가치 있다.",
    "내가 실수를 한다면 화를 내야 마땅하다.",
    "나에 대한 내 자신의 의견이 다른 사람들의 의견보다 더 중요하다.",
    "선량하고 도덕적이며 가치 있는 사람이 되려면 도움이 필요한 모든 사람을 도와야 한다.",
    "질문을 하면 내가 열등해 보인다.",
    "내게 중요한 사람들에게 인정받지 못하는 것은 끔찍한 일이다.",
    "의지할 다른 사람이 없다면, 슬퍼질 수밖에 없다.",
    "내 자신을 노예처럼 채찍질하지 않아도 중요한 목표를 달성할 수 있다.",
    "누군가에게 야단을 맞고도 기분이 상하지 않을 수 있다.",
    "다른 사람들이 나에게 잔인하게 굴 수 있기 때문에 나는 다른 사람들을 믿을 수 없다.",
    "다른 사람들이 나를 싫어한다면 나는 행복할 수 없다.",
    "다른 사람들을 기쁘게 하기 위해 내 자신의 이익을 포기하는 것이 최선이다.",
    "나의 행복은 나 자신보다 다른 사람들에게 더 많이 달려 있다.",
    "행복해지기 위해 다른 사람들의 승인이 필요한 것은 아니다.",
    "문제를 회피하면 문제는 사라지는 경향이 있다.",
    "인생에서 많은 좋은 것들을 놓치더라도 나는 행복할 수 있다.",
    "다른 사람들이 나에 대해 어떻게 생각하는지는 매우 중요하다.",
    "다른 사람들과 고립되면 불행해질 수밖에 없다.",
    "다른 사람의 사랑을 받지 못해도 나는 행복을 찾을 수 있다."
]

# ==========================================
# 화면 A (Step 0): 온보딩 & 사전 검사
# ==========================================
if st.session_state.app_step == 0:
    st.title("Step 1. 내면의 지도 그리기")
    
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
                save_state() 
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
        save_state() 
        st.rerun()

# ==========================================
# 화면 C (Step 2): 일일 CBT 챗봇
# ==========================================
elif st.session_state.app_step == 2:
    st.title(f"CBT 가이드 - Day {st.session_state.current_day} / {st.session_state.target_days}")
    
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    scores = st.session_state.category_scores
    max_cat = max(scores, key=scores.get)
    
    past_summaries_text = "\n".join([f"- Day {i+1}: {summary}" for i, summary in enumerate(st.session_state.daily_summaries)]) if st.session_state.daily_summaries else "아직 이전 상담 기록이 없습니다."

    if st.session_state.current_day == 1:
        system_prompt = f"""
        당신은 인지행동치료(CBT)를 기반으로 사용자의 인지 재구조화를 돕는 전문 AI 심리 가이드이다. 
        [사용자 취약 영역]: {max_cat}
        [지침] 글씨나 폰트 강조를 위해 '*' 사용 금지
        하향 화살표 기법으로 사용자의 오늘 하루 스트레스를 탐색하라.
        사용자의 인지오류가 순간적으로 고쳐지거나 사용자의 대화 내용이 계속 반복될 경우, 
        대화의 끝에는 반드시 사용자가 일상에서 실천할 수 있는 '아주 작은 행동 숙제'를 하나 제안해야 한다.
        모든 회기마다 내가 내담자로서 대우받고 싶은 방식으로 모든 내담자를 똑같이 대우하자. 
        상담실에서 따뜻한 한 사람으로 내담자가 안전하다고 느끼도록 돕자. 
        내담자는 도전에 직면해야 함을 기억하자. 그것이 그들이 치료가 필요한 이유이다. 
        내담자와 치료자 자신에 대한 기대치를 합리적으로 유지하자.
        """
    else:
        system_prompt = f"""
        당신은 전문 AI 심리 가이드이다. 
        [사용자 취약 영역]: {max_cat}
        [과거 상담 핵심 요약 기록]:
        {past_summaries_text}
        
        [어제 내준 숙제 요약]: {st.session_state.yesterday_homework}
        [지침] 반드시 첫인사로 어제 내준 숙제를 잘 실천했는지 다정하게 점검하라. 
        과거 요약 기록을 참고하여 내담자의 성장이나 패턴을 자연스럽게 언급하며 공감대를 형성하라.
        그 후 오늘 새롭게 겪은 스트레스 상황을 물어보고, 하향 화살표 기법으로 대화를 이어나가라. 대화 끝에는 내일 해볼 새로운 행동 숙제를 제안하라.
        """

    model = genai.GenerativeModel('gemini-3.1-pro-preview', system_instruction=system_prompt)

    dynamic_greetings = [
        "안녕하세요. 오늘 본격적인 첫 상담이네요. 오늘 하루, 마음을 불편하게 했던 일이 하나 있었나요?", 
        "안녕하세요, 두 번째 만남이네요. 어제 제안해 드린 숙제는 일상에서 조금 시도해 보셨나요? 편하게 말씀해 주세요.", 
        "Day 3입니다. 마음의 근육이 조금씩 붙고 있는 게 느껴지시나요? 어제 숙제는 어땠는지 들려주세요.", 
        "Day 4네요. 꾸준히 기록하고 마주하는 모습이 멋집니다. 어제 행동 실험을 해보시면서 어떤 기분이 드셨나요?", 
        "Day 5입니다! 일상에서 시도해 본 작은 변화들에 대해 편하게 이야기해 볼까요?", 
        "Day 6입니다. 이제 우리 대화가 꽤 익숙해지셨을 텐데, 어제 숙제를 하면서 새롭게 깨달은 점이 있다면 나눠주세요.", 
        "Day 7, 어느덧 일주일이 지났네요. 지난주와 비교했을 때 스스로 어떤 점이 조금 달라진 것 같나요?", 
        "Day 8입니다. 두 번째 주가 시작되었네요! 주말 동안, 혹은 어제 하루 동안 마음을 쓰이게 했던 일이 있었나요?", 
        "Day 9네요. 인지 오류를 찾아내는 속도가 조금은 빨라지셨나요? 어제 숙제 이야기를 먼저 들려주세요.", 
        "두 자릿수, Day 10입니다! 꾸준함의 힘을 믿습니다. 어제 시도해 본 행동 실험에서 어떤 점을 느끼셨나요?", 
        "Day 11입니다. 깊은 내면의 이야기를 꺼내주셔서 항상 감사합니다. 어제 하루는 어떻게 보내셨나요?", 
        "Day 12, 여정의 후반부네요. 예전이라면 스트레스받았을 일에 조금 더 유연하게 대처한 경험이 있다면 들려주세요.", 
        "Day 13입니다. 내일이면 마지막 사후 검사를 앞두고 있네요. 오늘 하루는 내 마음에 어떤 질문을 던져보셨나요?", 
        "안녕하세요. 어느덧 대망의 마지막 날, Day 14네요! 그동안 훈련하며 스스로 어떤 성장을 느끼셨는지 함께 이야기해 봐요." 
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
            save_state() 

        st.markdown("---")
        if st.button("오늘의 상담 종료하고 숙제 받기", use_container_width=True):
            st.session_state.session_ended = True
            save_state()
            st.rerun()

    else:
        st.success(f"Day {st.session_state.current_day} 인지 훈련 세션 완료!")
        st.info("AI가 마지막으로 남긴 메시지(숙제)를 꼭 확인해 주세요.")
        st.markdown("---")
        
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
                    
                    # 1. 내일 점검할 숙제 요약 추출
                    last_ai_msg = st.session_state.chat_history[-1]["content"]
                    summary_prompt = f"""
                    다음은 CBT 심리 가이드가 상담을 종료하며 사용자에게 남긴 마지막 메시지입니다.
                    이 메시지에서 사용자가 내일 일상에서 실천해야 할 '행동 숙제(행동 실험)' 부분만 찾아서 딱 1~2줄로 짧고 명확하게 요약해 주세요.
                    만약 명시적인 숙제가 없다면 '특별한 숙제 없음'이라고 답변해 주세요.
                    [가이드의 마지막 메시지] {last_ai_msg}
                    """
                    
                    # 2. 장기 기억을 위한 오늘 전체 대화 요약 추출
                    chat_full_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.chat_history])
                    daily_memory_prompt = f"""
                    다음은 오늘 사용자와 나눈 심리 상담 대화 기록 전체입니다.
                    이 대화에서 나타난 사용자의 '핵심 감정, 주된 인지 오류, 그리고 대화를 통해 긍정적으로 변화된 점'을 딱 1~2줄로 요약해 주세요.
                    이 요약은 내일 상담 시 AI가 사용자의 성장 과정을 기억하기 위한 참고 자료로 사용됩니다.
                    [오늘의 대화 기록] {chat_full_text}
                    """
                    
                    try:
                        summary_model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        # 숙제 요약 받아오기
                        hw_response = summary_model.generate_content(summary_prompt)
                        st.session_state.yesterday_homework = hw_response.text.strip()
                        
                        # 전체 대화 요약 받아와서 저장소에 넣기
                        mem_response = summary_model.generate_content(daily_memory_prompt)
                        st.session_state.daily_summaries.append(mem_response.text.strip())
                        
                    except:
                        st.session_state.yesterday_homework = last_ai_msg[:50] + "...(요약 오류)"
                        st.session_state.daily_summaries.append("시스템 오류로 요약이 저장되지 않았습니다.")
                    
                    st.session_state.chat_history = [] 
                    st.session_state.session_ended = False
                    save_state() 
                    st.rerun()
            else:
                if st.button("모든 일정 수료! 최종 사후 검사 진행하기"):
                    st.session_state.app_step = 3
                    save_state()
                    st.rerun()

# ==========================================
# 화면 D (Step 3): 사후 검사 진행
# ==========================================
elif st.session_state.app_step == 3:
    st.title("최종 사후 검사")
    st.markdown("그동안 정말 고생 많으셨습니다. 훈련 전과 후, 마음에 어떤 긍정적인 변화가 생겼는지 확인하기 위해 마지막 검사를 진행해 주세요.")
    st.markdown("---")

    with st.form("das_form_final"):
        st.subheader("DAS-40 사후 문항")
        responses = []
        for i, question in enumerate(das_40_questions[:40]):
            ans = st.radio(f"**{i+1}. {question}**", options_7pt, index=None, horizontal=True)
            responses.append((i+1, ans))
            
        submitted = st.form_submit_button("사후 검사 완료 및 결과 보기")
            
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

# ==========================================
# 화면 E (Step 4): 사전/사후 결과 비교
# ==========================================
elif st.session_state.app_step == 4:
    st.title("나의 마음 성장 리포트")
    st.markdown("첫날의 그래프와 마지막 날의 그래프를 비교해 보세요. 뾰족하게 찌그러져 있던 그래프가 둥글어지거나 면적이 줄어들었다면, 그만큼 인지 오류가 건강하게 개선되었다는 뜻입니다.")
    
    categories_list = list(st.session_state.initial_scores.keys())
    initial_vals = list(st.session_state.initial_scores.values())
    final_vals = list(st.session_state.final_scores.values())
    
    categories_list.append(categories_list[0])
    initial_vals.append(initial_vals[0])
    final_vals.append(final_vals[0])
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=initial_vals, theta=categories_list, fill='toself', name='사전 검사 (Day 1)', line_color='gray', fillcolor='rgba(128, 128, 128, 0.4)'))
    fig.add_trace(go.Scatterpolar(r=final_vals, theta=categories_list, fill='toself', name=f'사후 검사 (Day {st.session_state.target_days})', line_color='green', fillcolor='rgba(0, 255, 0, 0.4)'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 70])), showlegend=True, dragmode=False)
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.success("모든 CBT 여정을 훌륭하게 마친 것을 축하합니다. 마음이 힘들 때면 언제든 이 대화법을 떠올려 주세요.")

# ==========================================
# 공통 UI: 모든 화면 하단
# ==========================================
if st.session_state.app_step > 0:
    st.markdown("---")
    if st.button("🔄 초기화하고 처음으로 돌아가기", use_container_width=True):
        clear_state() 
        st.rerun()

if __name__ == "__main__":
    if not runtime.exists():
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])
        sys.exit()
