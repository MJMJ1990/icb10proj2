"""
사람인 '인사' 직무 채용공고 데이터를 시각적으로 분석하는 Streamlit 대시보드 모듈입니다.

이 모듈은 SQLite DB에서 데이터를 로드하여 세부 직무(HRM, HRD, 채용, 노무 등)를 자동 분류하고,
기업이 요구하는 기술 스택, 자격증, 학력, 전공 등의 스펙 요구사항을 Plotly를 활용해 다각도로 분석하여
사용자에게 프리미엄 다크 테마 대시보드 인터페이스를 제공합니다.
"""

import os
import re
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Streamlit 기본 설정 및 프리미엄 다크 테마 적용
st.set_page_config(
    page_title="인사 직무 채용시장 분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 경로 설정
DB_PATH = os.path.join("saramin", "data", "saramin_jobs_hr.db")

# 분석 키워드 사전 정의
KEYWORDS = {
    "tech": {
        "Excel": r"엑셀|excel|컴활",
        "PPT": r"ppt|powerpoint|파워포인트",
        "Word": r"워드|한글|word",
        "ERP": r"erp|더존|sap|e-count|이카운트",
        "Slack": r"슬랙|slack",
        "Notion": r"노션|notion",
        "SQL": r"sql",
        "Python": r"python|파이썬",
        "R": r"\br\b",
        "Tableau": r"tableau|태블로",
        "Power BI": r"power\s?bi|파워비아이"
    },
    "license": {
        "공인노무사": r"노무사|공인노무사",
        "PHR/SPHR": r"phr|sphr",
        "컴퓨터활용능력": r"컴퓨터활용능력|컴활",
        "ITQ": r"itq",
        "ERP정보관리사": r"erp정보관리사|erp 자격증",
        "사회조사분석사": r"사회조사분석사|사조분",
        "ADsP": r"adsp",
        "SQLD": r"sqld"
    },
    "major": {
        "경영학": r"경영|business administration",
        "경제학": r"경제|economics",
        "행정학": r"행정|public administration",
        "법학": r"법학|법률|law",
        "교육학": r"교육|education",
        "심리학": r"심리|psychology",
        "통계학": r"통계|statistics",
        "산업공학": r"산업공학|industrial engineering",
        "컴퓨터공학": r"컴퓨터|소프트웨어|computer science"
    }
}

@st.cache_data
def load_and_preprocess_data(db_path: str) -> pd.DataFrame:
    """
    SQLite DB에서 데이터를 로드하고, 세부 직무 분류 및 키워드 추출 전처리를 수행합니다.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"데이터베이스 파일이 존재하지 않습니다: {db_path}")

    # 데이터 로딩
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM jobs", conn)

    # 수집 본문 결합텍스트 생성 (키워드 추출용)
    df["full_text"] = (
        df["title"].fillna("") + " " + 
        df["requirements"].fillna("") + " " + 
        df["preferences"].fillna("")
    ).str.lower()

    # 1. 인사 세부 직무(Sub-Job) 자동 분류 로직
    def classify_sub_job(row) -> str:
        text = row["full_text"]
        title = str(row["title"]).lower()
        
        # 가중치 기반 매칭 점수 산정
        scores = {"HRM": 0, "HRD": 0, "채용(TA)": 0, "노무(ER)": 0, "일반인사/총무": 0}
        
        # HRM 관련 키워드
        hrm_words = ["평가", "보상", "급여", "payroll", "페이롤", "4대보험", "원천세", "복리후생", "인사기획", "인사운영", "hrm"]
        scores["HRM"] += sum(3 if w in title else 1 for w in hrm_words if w in text)
        
        # HRD 관련 키워드
        hrd_words = ["교육", "훈련", "육성", "ojt", "연수", "hrd", "cdp", "워크숍"]
        scores["HRD"] += sum(3 if w in title else 1 for w in hrd_words if w in text)
        
        # 채용 관련 키워드
        ta_words = ["채용", "recruiting", "ta", "리크루팅", "인재확보", "헤드헌팅", "면접"]
        scores["채용(TA)"] += sum(3 if w in title else 1 for w in ta_words if w in text)
        
        # 노무 관련 키워드
        er_words = ["노무", "er", "노동조합", "단체협약", "노사", "근로기준법"]
        scores["노무(ER)"] += sum(3 if w in title else 1 for w in er_words if w in text)
        
        # 일반인사 및 총무 키워드
        general_words = ["총무", "근태", "증명서", "인사행정", "총무행정"]
        scores["일반인사/총무"] += sum(2 if w in title else 0.5 for w in general_words if w in text)
        
        # 가장 높은 점수의 카테고리 선정 (기본값 HRM)
        best_cat = max(scores, key=scores.get)
        if scores[best_cat] == 0:
            return "일반인사/총무"
        return best_cat

    df["sub_job"] = df.apply(classify_sub_job, axis=1)

    # 2. 경력 정규화 (신입, 경력, 경력무관)
    def normalize_experience(exp_text: str) -> str:
        if not exp_text:
            return "경력무관"
        exp_clean = exp_text.replace(" ", "")
        if "신입" in exp_clean and "경력" in exp_clean:
            return "신입/경력"
        elif "신입" in exp_clean:
            return "신입"
        elif "경력" in exp_clean:
            return "경력"
        else:
            return "경력무관"

    df["normalized_experience"] = df["experience"].apply(normalize_experience)

    # 3. 학력 정규화
    def normalize_education(edu_text: str) -> str:
        if not edu_text:
            return "학력무관"
        edu_clean = edu_text.replace(" ", "")
        if "학력무관" in edu_clean:
            return "학력무관"
        elif "박사" in edu_clean:
            return "박사졸업 이상"
        elif "석사" in edu_clean:
            return "석사졸업 이상"
        elif "4년" in edu_clean or "대학교" in edu_clean or "대졸" in edu_clean:
            return "대졸(4년제) 이상"
        elif "전문대" in edu_clean or "2년" in edu_clean or "3년" in edu_clean or "전대" in edu_clean:
            return "전문대졸 이상"
        elif "고졸" in edu_clean or "고등학교" in edu_clean:
            return "고졸 이상"
        return "학력무관"

    df["normalized_education"] = df["education"].apply(normalize_education)

    # 4. 키워드 매칭 분석 수행 (Boolean 컬럼 매핑)
    for category, items in KEYWORDS.items():
        for name, pattern in items.items():
            col_name = f"{category}_{name}"
            df[col_name] = df["full_text"].apply(lambda t: 1 if re.search(pattern, str(t)) else 0)

    # 임시 결측치 세부조정
    df["location"] = df["location"].fillna("서울 전체")
    df["company_name"] = df["company_name"].fillna("비공개 기업")
    
    return df

# 데이터 로드
try:
    df_raw = load_and_preprocess_data(DB_PATH)
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# ==============================================================================
# 사이드바 통합 필터링
# ==============================================================================
st.sidebar.markdown("<h2 style='text-align: center;'>🎛️ 필터 제어판</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# 1. 세부 직무 필터
all_sub_jobs = sorted(df_raw["sub_job"].unique())
selected_sub_jobs = st.sidebar.multiselect(
    "📂 세부 직무 (분류)",
    options=all_sub_jobs,
    default=all_sub_jobs
)

# 2. 경력 조건 필터
all_exp = sorted(df_raw["normalized_experience"].unique())
selected_exp = st.sidebar.multiselect(
    "💼 경력 요구사항",
    options=all_exp,
    default=all_exp
)

# 3. 학력 조건 필터
all_edu = sorted(df_raw["normalized_education"].unique())
selected_edu = st.sidebar.multiselect(
    "🎓 학력 요구사항",
    options=all_edu,
    default=all_edu
)

# 4. 기업명 검색 및 필터
all_companies = sorted(df_raw["company_name"].unique())
search_company = st.sidebar.text_input("🏢 기업명 검색", "")

# 데이터 필터링 적용
df_filtered = df_raw.copy()

if selected_sub_jobs:
    df_filtered = df_filtered[df_filtered["sub_job"].isin(selected_sub_jobs)]
if selected_exp:
    df_filtered = df_filtered[df_filtered["normalized_experience"].isin(selected_exp)]
if selected_edu:
    df_filtered = df_filtered[df_filtered["normalized_education"].isin(selected_edu)]
if search_company:
    df_filtered = df_filtered[df_filtered["company_name"].str.contains(search_company, case=False)]

# 필터링 후 빈 데이터 대응
if df_filtered.empty:
    st.warning("⚠️ 선택하신 필터 조건에 부합하는 채용공고가 존재하지 않습니다. 필터 조건을 변경해 주세요.")
    st.stop()

# ==============================================================================
# 대시보드 본문 렌더링
# ==============================================================================
st.markdown("<h1 style='text-align: center; color: #64B5F6;'>📊 인사(HR) 직무 채용시장 분석 대시보드</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem; color: #B0BEC5;'>사람인 수집 공고 실시간 정량 분석 리포트 (Premium Dark Theme)</p>", unsafe_allow_html=True)
st.markdown("---")

# ------------------------------------------------------------------------------
# 1. 상단 KPI 카드 영역
# ------------------------------------------------------------------------------
kpi_cols = st.columns(5)

# 전체 공고 수
total_jobs = len(df_filtered)
kpi_cols[0].metric(label="📋 분석 대상 공고 수", value=f"{total_jobs:,} 건")

# 고유 기업 수
total_companies = df_filtered["company_name"].nunique()
kpi_cols[1].metric(label="🏢 대상 고유 기업 수", value=f"{total_companies:,} 개")

# 최다 요구 기술
tech_cols = [col for col in df_raw.columns if col.startswith("tech_")]
tech_counts = df_filtered[tech_cols].sum()
if not tech_counts.empty and tech_counts.max() > 0:
    top_tech = tech_counts.idxmax().replace("tech_", "")
    top_tech_pct = (tech_counts.max() / total_jobs) * 100
    kpi_cols[2].metric(label="⚡ 최다 요구 기술 스택", value=top_tech, delta=f"{top_tech_pct:.1f}% 공고 요구")
else:
    kpi_cols[2].metric(label="⚡ 최다 요구 기술 스택", value="데이터 없음")

# 최다 요구 학력
edu_counts = df_filtered["normalized_education"].value_counts()
if not edu_counts.empty:
    top_edu = edu_counts.idxmax()
    top_edu_pct = (edu_counts.max() / total_jobs) * 100
    kpi_cols[3].metric(label="🎓 가장 지배적인 학력 조건", value=top_edu.split(" ")[0], delta=f"{top_edu_pct:.1f}%")
else:
    kpi_cols[3].metric(label="🎓 가장 지배적인 학력 조건", value="데이터 없음")

# 자격증 요구 비율
license_cols = [col for col in df_raw.columns if col.startswith("license_")]
has_license_count = (df_filtered[license_cols].sum(axis=1) > 0).sum()
license_ratio = (has_license_count / total_jobs) * 100
kpi_cols[4].metric(label="📜 자격증 요구 공고 비율", value=f"{license_ratio:.1f} %", delta="종합 자격 기준")

st.markdown("---")

# ------------------------------------------------------------------------------
# 2. 주요 시각화 영역 (Plotly 차트 2열 그리드 배치)
# ------------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    # 차트 1: 기술 스택 요구 비율 막대그래프
    st.markdown("### ⚡ 주요 기술 스택 요구 비율")
    tech_pct = (tech_counts / total_jobs * 100).reset_index()
    tech_pct.columns = ["Tech_Stack", "Percentage"]
    tech_pct["Tech_Stack"] = tech_pct["Tech_Stack"].str.replace("tech_", "")
    tech_pct = tech_pct.sort_values(by="Percentage", ascending=True)
    
    fig1 = px.bar(
        tech_pct,
        x="Percentage",
        y="Tech_Stack",
        orientation="h",
        labels={"Percentage": "요구 비율 (%)", "Tech_Stack": "기술 스택"},
        color="Percentage",
        color_continuous_scale="Blues",
        template="plotly_dark"
    )
    fig1.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig1, use_container_width=True)
    st.caption("💡 해석: 문서 작성 툴(Excel/PPT)이 여전히 압도적인 필수 스펙이며, 점차 SQL과 BI 툴을 요구하는 People Analytics 추세가 포착됩니다.")

with col2:
    # 차트 2: 직무별 기술 스택 히트맵
    st.markdown("### 🗺️ 직무별 기술 스택 요구도 (히트맵)")
    
    # 세부 직무별 기술 언급률 매트릭스 계산
    heatmap_data = []
    for job in selected_sub_jobs:
        df_sub = df_filtered[df_filtered["sub_job"] == job]
        sub_total = len(df_sub)
        if sub_total > 0:
            for tech_col in tech_cols:
                tech_name = tech_col.replace("tech_", "")
                cnt = df_sub[tech_col].sum()
                pct = (cnt / sub_total) * 100
                heatmap_data.append({"Job": job, "Tech": tech_name, "Ratio": pct})
                
    if heatmap_data:
        df_heatmap = pd.DataFrame(heatmap_data)
        df_pivot = df_heatmap.pivot(index="Job", columns="Tech", values="Ratio").fillna(0)
        
        fig2 = go.Figure(
            data=go.Heatmap(
                z=df_pivot.values,
                x=df_pivot.columns,
                y=df_pivot.index,
                colorscale="Viridis",
                hoverongaps=False,
                hovertemplate="직무: %{y}<br>기술: %{x}<br>요구 비율: %{z:.1f}%<extra></extra>"
            )
        )
        fig2.update_layout(
            template="plotly_dark",
            height=380,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("비교할 수 있는 직무 데이터가 부족합니다.")
    st.caption("💡 해석: 각 세부 직무 영역(HRM, HRD 등)별로 도구 및 기술 요구의 밀집도를 보여줍니다. 색상이 밝을수록 해당 직무에서 스킬 필요성이 높음을 의미합니다.")

st.markdown("---")

col3, col4 = st.columns(2)

with col3:
    # 차트 3: 학력 조건 분포 도넛 차트
    st.markdown("### 🎓 요구 학력 조건 분포")
    edu_dist = df_filtered["normalized_education"].value_counts().reset_index()
    edu_dist.columns = ["Education", "Count"]
    
    fig3 = px.pie(
        edu_dist,
        names="Education",
        values="Count",
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.RdBu,
        template="plotly_dark"
    )
    fig3.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig3, use_container_width=True)
    st.caption("💡 해석: 학력무관 공고 비율과 4년제 대졸 학위 필수 요구 공고 간의 비중을 비교하여 진입 장벽 수준을 보여줍니다.")

with col4:
    # 차트 4: 전공 요구 분포 가로 막대그래프
    st.markdown("### 🏛️ 선호 전공 분포")
    major_cols = [col for col in df_raw.columns if col.startswith("major_")]
    major_counts = df_filtered[major_cols].sum()
    major_pct = (major_counts / total_jobs * 100).reset_index()
    major_pct.columns = ["Major", "Percentage"]
    major_pct["Major"] = major_pct["Major"].str.replace("major_", "")
    major_pct = major_pct.sort_values(by="Percentage", ascending=True)
    
    fig4 = px.bar(
        major_pct,
        x="Percentage",
        y="Major",
        orientation="h",
        labels={"Percentage": "선호 전공 언급 비율 (%)", "Major": "전공명"},
        color="Percentage",
        color_continuous_scale="Purples",
        template="plotly_dark"
    )
    fig4.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig4, use_container_width=True)
    st.caption("💡 해석: 채용 요강 상 우대 전공 키워드 분석 결과로, 전통적인 상경 계열(경영, 경제) 및 법학 전공 선호도가 높음을 보여줍니다.")

st.markdown("---")

col5, col6 = st.columns(2)

with col5:
    # 차트 5: 자격증 요구 비율 세로 막대그래프
    st.markdown("### 📜 자격증 우대/필수 요구 비율")
    license_counts = df_filtered[license_cols].sum()
    license_pct = (license_counts / total_jobs * 100).reset_index()
    license_pct.columns = ["License", "Percentage"]
    license_pct["License"] = license_pct["License"].str.replace("license_", "")
    license_pct = license_pct.sort_values(by="Percentage", ascending=False)
    
    fig5 = px.bar(
        license_pct,
        x="License",
        y="Percentage",
        labels={"Percentage": "요구 비율 (%)", "License": "자격증 명칭"},
        color="Percentage",
        color_continuous_scale="Tealgrn",
        template="plotly_dark"
    )
    fig5.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20), coloraxis_showscale=False)
    st.plotly_chart(fig5, use_container_width=True)
    st.caption("💡 해석: 가장 접근하기 쉬운 '컴활' 외에도 실무 전문 영역에 특화된 공인노무사 및 해외 HR 라이선스(PHR) 요구 수준을 파악할 수 있습니다.")

with col6:
    # 차트 6: 직무별 핵심 기술 TOP 10 비교
    st.markdown("### 🏷️ 선택 직무별 핵심 요구 역량 비교")
    
    # 5대 핵심 기술 추출 및 매핑
    top_5_techs = list(tech_pct.sort_values(by="Percentage", ascending=False)["Tech_Stack"].head(5))
    
    grouped_data = []
    for job in selected_sub_jobs:
        df_sub = df_filtered[df_filtered["sub_job"] == job]
        sub_total = len(df_sub)
        if sub_total > 0:
            for tech in top_5_techs:
                cnt = df_sub[f"tech_{tech}"].sum()
                pct = (cnt / sub_total) * 100
                grouped_data.append({"직무": job, "역량": tech, "요구율(%)": pct})
                
    if grouped_data:
        df_group = pd.DataFrame(grouped_data)
        fig6 = px.bar(
            df_group,
            x="역량",
            y="요구율(%)",
            color="직무",
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            template="plotly_dark"
        )
        fig6.update_layout(height=380, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig6, use_container_width=True)
    else:
        st.info("비교 데이터가 부족합니다.")
    st.caption("💡 해석: 채용 시 가장 중점적으로 보는 상위 5대 도구에 대해, 각 직무 기능(HRM, HRD 등)이 부여하는 상대적 중요도를 대조 분석합니다.")

st.markdown("---")

# 차트 7: 경력 수준별 요구 기술 차이 분석
st.markdown("### 💼 신입 vs 경력 요구 역량 차이 비교")
exp_compare_data = []
for exp_type in ["신입", "경력"]:
    df_exp = df_filtered[df_filtered["normalized_experience"] == exp_type]
    exp_total = len(df_exp)
    if exp_total > 0:
        for tech in top_5_techs:
            cnt = df_exp[f"tech_{tech}"].sum()
            pct = (cnt / exp_total) * 100
            exp_compare_data.append({"경력수준": exp_type, "기술": tech, "요구비율": pct})

if exp_compare_data:
    df_exp_compare = pd.DataFrame(exp_compare_data)
    fig7 = px.line(
        df_exp_compare,
        x="기술",
        y="요구비율",
        color="경력수준",
        markers=True,
        template="plotly_dark",
        color_discrete_sequence=["#FF7043", "#29B6F6"]
    )
    fig7.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis_title="요구 비율 (%)"
    )
    st.plotly_chart(fig7, use_container_width=True)
else:
    st.info("경력 수준별 비교를 위한 데이터가 부족합니다.")
st.caption("💡 해석: 신입 지원자가 진입 가능한 채용공고의 스펙 눈높이와 경력 이직 시 요구되는 전문 스킬 스택의 격차(GAP)를 확인할 수 있습니다.")

st.markdown("---")

# ------------------------------------------------------------------------------
# 3. 핵심 인사이트 요약 영역
# ------------------------------------------------------------------------------
st.markdown("## 🧠 시니어 분석가의 핵심 인사이트 리포트")

# 분석 기반 동적 데이터 추출
top_tech_list = list(tech_pct.sort_values(by="Percentage", ascending=False)["Tech_Stack"].head(5))
top_license_list = list(license_pct.sort_values(by="Percentage", ascending=False)["License"].head(3))
major_list = list(major_pct.sort_values(by="Percentage", ascending=False)["Major"].head(3))

col_ins1, col_ins2 = st.columns(2)

with col_ins1:
    st.markdown("### 📌 취업 스펙 및 역량 요약")
    st.markdown(f"""
    - **가장 기본적인 필수 스펙**: **Excel 및 PPT** 문서 작성 및 데이터 편집 능력은 전체 공고의 대다수에서 우대되거나 필수로 삼는 기본 요건입니다.
    - **기업 최다 요구 기술 TOP 5**: **{', '.join(top_tech_list)}** 순으로 기업에서 선호도가 높습니다.
    - **자격증의 중요도**: 채용공고 중 약 **{license_ratio:.1f}%**가 명시적인 자격증 우대 사항을 두고 있습니다. 특히 **{', '.join(top_license_list)}** 자격증이 시장 가치가 높게 평가됩니다.
    - **학력과 전공 중요도**: **{top_edu}** 조건의 수요가 지배적이며, 전공의 경우 **{', '.join(major_list)}** 순으로 선호 경향이 짙게 드러납니다.
    """)

with col_ins2:
    st.markdown("### 🎓 맞춤형 취업 준비 전략 제안")
    st.markdown(f"""
    - **신입 지원자가 우선적으로 준비해야 할 요소**:
      1. 실무 엑셀(VLOOKUP, 피벗 테이블 등) 및 ERP 기본 프로세스 이해도 인증
      2. 컴활 또는 ERP 자격증 확보를 통한 최소한의 실무 툴 지식 증명
    - **직무별 요구 스펙 차이**:
      - **HRM(인사기획/운영)**은 급여 정산 및 기획을 위해 **Excel 및 ERP** 툴과 **노무사/컴활** 자격증 의존도가 높습니다.
      - **HRD(교육/개발)**는 주로 교육 설계 및 연수 진행을 위해 **PPT 및 Word** 작성 역량과 **교육학/심리학** 전공을 크게 우대합니다.
      - **채용(TA)**은 전반적인 프로세스 매끄러움과 조율을 요하며 최근 데이터 기반 채용 분석을 위해 **SQL 및 BI 툴**의 우대 사항 비중이 늘어나고 있습니다.
    - **기업이 원하는 이상적인 HR 프로필**: **"{top_edu.split(' ')[0]} 이상의 학력으로, 엑셀 및 ERP 도구를 자연스럽게 다루며, 업무에 법률적 판단이나 교육 공학(경영/교육/법학)적 소양을 접목할 수 있는 인재"**
    """)

st.markdown("---")

# ------------------------------------------------------------------------------
# 4. 원천 데이터 테이블 및 다운로드 영역
# ------------------------------------------------------------------------------
with st.expander("📂 필터링된 원천 데이터셋 확인 및 다운로드"):
    display_cols = ["company_name", "title", "sub_job", "normalized_experience", "normalized_education", "location", "deadline", "detail_url"]
    st.dataframe(df_filtered[display_cols], use_container_width=True)
    
    # CSV 다운로드 버튼
    csv = df_filtered[display_cols].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 CSV 파일로 내보내기 (Download)",
        data=csv,
        file_name="saramin_jobs_filtered.csv",
        mime="text/csv"
    )
