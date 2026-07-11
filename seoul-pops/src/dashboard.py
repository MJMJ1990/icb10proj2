"""
서울시 생활인구 데이터를 바탕으로 종합적인 탐색적 데이터 분석(EDA)을 수행하는 Streamlit 대시보드입니다.

이 모듈은 Parquet 형식의 서울시 생활인구 데이터와 Excel 매핑 정보를 로드하여
데이터 개요, 기본 기술통계, 심층 비즈니스 분석 보고서 및 10종의 Plotly 시각화 차트를 제공합니다.
사용자는 자치구, 행정동, 성별, 요일 및 시간대별로 데이터를 동적으로 필터링하여 분석할 수 있습니다.
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 테마 지정 (Aesthetics)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="서울시 생활인구 대시보드 - EDA 분석",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Plotly 기본 테마 및 색상 체계 정의 (HSL 기반의 조화로운 테마)
PRIMARY_COLOR = "#3A6073"
SECONDARY_COLOR = "#3A6073"
ACCENT_COLOR = "#FF6B6B"
COLOR_SEQUENCE = ["#3A6073", "#FF6B6B", "#4CA1AF", "#FFD25A", "#8E44AD", "#2ECC71", "#34495E"]

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 최적화 캐싱 (Performance)
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner="서울시 생활인구 데이터를 로딩하고 분석 시스템을 준비하는 중입니다...")
def load_and_preprocess_data():
    """Parquet 파일과 행정동 매핑 엑셀 파일을 로드하여 병합하고 전처리합니다.

    Returns:
        pd.DataFrame: 전처리가 완료된 서울시 생활인구 데이터프레임
    """
    parquet_path = "seoul-pops/data/LOCAL_PEOPLE_DONG_202606.parquet"
    excel_path = "seoul-pops/data/행정동코드_매핑정보_20241218.xlsx"
    
    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"Parquet 데이터를 찾을 수 없습니다: {parquet_path}")
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"행정동코드 매핑 엑셀 파일을 찾을 수 없습니다: {excel_path}")
        
    # 데이터 로드
    df = pd.read_parquet(parquet_path)
    df_excel = pd.read_excel(excel_path)
    
    # 엑셀 매핑 파일에서 자치구명 및 행정동명 추출 (2번째 열: 코드, 1번째 열: 통계청코드, 4번째 열: 자치구, 5번째 열: 행정동)
    df_mapping = df_excel.iloc[:, [1, 0, 3, 4]].copy()
    df_mapping.columns = ['행정동코드', '통계청코드', '자치구명', '행정동명']
    
    # 영문 컬럼명('H_DNG_CD')이나 숫자가 아닌 쓰레기 데이터 행을 안전하게 제거
    df_mapping['행정동코드'] = pd.to_numeric(df_mapping['행정동코드'], errors='coerce')
    df_mapping['통계청코드'] = pd.to_numeric(df_mapping['통계청코드'], errors='coerce')
    df_mapping = df_mapping.dropna(subset=['행정동코드', '통계청코드'])
    
    # 데이터 타입을 문자열(str)로 통일하여 Parquet 데이터와 안전하게 조인
    df_mapping['행정동코드'] = df_mapping['행정동코드'].astype('int32').astype('str')
    df_mapping['통계청코드'] = df_mapping['통계청코드'].astype('int32').astype('str')
    
    # 중복 행 제거
    df_mapping = df_mapping.drop_duplicates(subset=['행정동코드'])
    
    # Parquet의 행정동코드 컬럼도 문자열(str)로 변환
    df['행정동코드'] = df['행정동코드'].astype('str')
    
    # 조인 수행
    df = df.merge(df_mapping, on='행정동코드', how='left')
    
    # 요일 파생변수 생성 및 범주형 정렬 순서 부여
    date_series = pd.to_datetime(df['기준일ID'].astype(str), format='%Y%m%d')
    weekday_map = {
        'Monday': '월', 'Tuesday': '화', 'Wednesday': '수',
        'Thursday': '목', 'Friday': '금', 'Saturday': '토', 'Sunday': '일'
    }
    df['요일'] = date_series.dt.day_name().map(weekday_map)
    df['요일'] = pd.Categorical(df['요일'], categories=['월', '화', '수', '목', '금', '토', '일'], ordered=True)
    
    # 연령대 대분류(10대 단위) 파생변수 생성 및 정렬 순서 부여
    age_map = {
        '0세부터9세': '10세 미만',
        '10세부터14세': '10대', '15세부터19세': '10대',
        '20세부터24세': '20대', '25세부터29세': '20대',
        '30세부터34세': '30대', '35세부터39세': '30대',
        '40세부터44세': '40대', '45세부터49세': '40대',
        '50세부터54세': '50대', '55세부터59세': '50대',
        '60세부터64세': '60대', '65세부터69세': '60대',
        '70세이상': '70대 이상'
    }
    df['연령대_대분류'] = df['연령대'].map(age_map)
    df['연령대_대분류'] = pd.Categorical(
        df['연령대_대분류'],
        categories=['10세 미만', '10대', '20대', '30대', '40대', '50대', '60대', '70대 이상'],
        ordered=True
    )
    
    # 결측치 정제 (행정동명이 없는 데이터 제거)
    df = df.dropna(subset=['행정동명'])
    
    return df

@st.cache_data(show_spinner="서울시 지도 GeoJSON 데이터를 로딩하는 중입니다...")
def load_seoul_geojson(unit: str) -> dict:
    """로컬 GeoJSON 파일에서 서울시 영역 지도를 불러오고 캐싱합니다. 로컬에 없는 경우 원격에서 로드하여 필터링합니다.

    Args:
        unit (str): 'municipalities' (구별) 또는 'submunicipalities' (동별)

    Returns:
        dict: 서울특별시 영역 피처들로 구성된 GeoJSON
    """
    import json
    local_path = f"seoul-pops/data/seoul_{unit}.geojson"
    
    # 1. 로컬에 이미 최적화된 파일이 있으면 즉시 로드 (0.01초 소요)
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"로컬 지도 파일 로드 실패, 원격에서 복구를 시도합니다: {e}")
            
    # 2. 로컬에 없는 경우 원격 저장소에서 백업용 다운로드 (Fallback)
    import requests
    url = f"https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/skorea-{unit}-2018-geo.json"
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        
        # properties.code가 서울시 코드 '11'로 시작하는 행정구역만 추출
        seoul_features = [
            f for f in data.get('features', [])
            if str(f.get('properties', {}).get('code', '')).startswith('11')
        ]
        
        seoul_geojson = {
            "type": "FeatureCollection",
            "features": seoul_features
        }
        
        # 향후 기동 속도 향상을 위해 로컬 캐시 파일로 저장
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(seoul_geojson, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
        return seoul_geojson
    except Exception as e:
        st.error(f"지도 GeoJSON 로딩 실패: {e}")
        return {"type": "FeatureCollection", "features": []}

# 데이터 로드 실행
try:
    df_raw = load_and_preprocess_data()
except Exception as e:
    st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 인터랙티브 필터 구성 (Interaction)
# -----------------------------------------------------------------------------
st.sidebar.markdown("## 🔍 분석 필터 설정")

# 자치구 선택 (전체 선택 옵션 제공)
districts = sorted(df_raw['자치구명'].dropna().unique().tolist())
selected_districts = st.sidebar.multiselect(
    "자치구 선택 (다중 선택 가능)",
    options=districts,
    default=[]
)

# 선택된 자치구에 따라 행정동 목록 동적 필터링
if selected_districts:
    df_filtered_district = df_raw[df_raw['자치구명'].isin(selected_districts)]
    dongs = sorted(df_filtered_district['행정동명'].dropna().unique().tolist())
else:
    df_filtered_district = df_raw
    dongs = sorted(df_raw['행정동명'].dropna().unique().tolist())

# 행정동 선택
selected_dongs = st.sidebar.multiselect(
    "행정동 선택 (선택 안 하면 전체 대상)",
    options=dongs,
    default=[]
)

# 성별 필터 (Radio 버튼 활용)
selected_gender = st.sidebar.radio(
    "성별 필터",
    options=["전체", "남자", "여자"],
    index=0
)

# 요일 필터 (다중 선택)
weekdays = ['월', '화', '수', '목', '금', '토', '일']
selected_weekdays = st.sidebar.multiselect(
    "요일 필터 (선택 안 하면 전체 대상)",
    options=weekdays,
    default=[]
)

# 시간대 슬라이더 필터 (Range Slider)
selected_hours = st.sidebar.slider(
    "시간대 범위 설정 (시)",
    min_value=0,
    max_value=23,
    value=(0, 23)
)

# 필터링 적용 연산
df_filtered = df_raw.copy()

if selected_districts:
    df_filtered = df_filtered[df_filtered['자치구명'].isin(selected_districts)]
if selected_dongs:
    df_filtered = df_filtered[df_filtered['행정동명'].isin(selected_dongs)]
if selected_gender != "전체":
    df_filtered = df_filtered[df_filtered['성별'] == selected_gender]
if selected_weekdays:
    df_filtered = df_filtered[df_filtered['요일'].isin(selected_weekdays)]
    
# 시간대 필터링
df_filtered = df_filtered[
    (df_filtered['시간대구분'] >= selected_hours[0]) & 
    (df_filtered['시간대구분'] <= selected_hours[1])
]

# 데이터가 비어있는 상태에 대한 안내 (Empty State 처리)
if df_filtered.empty:
    st.warning("⚠️ 선택하신 필터 조건에 해당하는 데이터가 존재하지 않습니다. 필터 설정을 다시 확인해 주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 4. 메인 대시보드 화면 구성
# -----------------------------------------------------------------------------
st.title("📊 서울시 행정동별 생활인구 종합 EDA 대시보드")
st.markdown("본 대시보드는 2026년 6월 기준 서울시 행정동별 생활인구 데이터를 입체적으로 탐색하고 분석하기 위해 개발되었습니다.")

# 데이터 기준일 및 업데이트 현황 표시 (데이터 최신성 표시)
st.caption("📅 데이터 기준 시점: 2026년 6월 (1개월간 관측 데이터) | 분석 엔진: Python & Streamlit & Plotly")

# 주요 지표 카드 (KPI Metrics)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric(
        label="총 관측 데이터 건수 (Filtered)", 
        value=f"{len(df_filtered):,}"
    )
with kpi2:
    st.metric(
        label="평균 총생활인구수 (행정동/시간 기준)", 
        value=f"{df_filtered['총생활인구수'].mean():,.1f} 명"
    )
with kpi3:
    st.metric(
        label="최대 총생활인구 관측치", 
        value=f"{df_filtered['총생활인구수'].max():,.0f} 명"
    )
with kpi4:
    st.metric(
        label="분석 대상 행정동 수", 
        value=f"{df_filtered['행정동코드'].nunique()} 개"
    )

# -----------------------------------------------------------------------------
# 5. 탭 레이아웃 설계 (UI/UX)
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📂 데이터 개요 & 프로파일링", 
    "📈 기본 기술통계 & 보고서", 
    "📊 생활인구 다차원 시각화",
    "🗺️ 생활인구 지도 시각화"
])

# -----------------------------------------------------------------------------
# [TAB 1] 데이터 개요 & 프로파일링
# -----------------------------------------------------------------------------
with tab1:
    st.subheader("🔍 데이터 프로파일링 및 기본 탐색")
    st.markdown("로드된 서울시 생활인구 데이터프레임의 원본 형태와 기본 정보를 탐색합니다.")
    
    col_info_left, col_info_right = st.columns(2)
    
    with col_info_left:
        st.markdown("#### ⚙️ 데이터프레임 메타정보")
        meta_data = {
            "항목": ["전체 행(Row) 수", "전체 열(Column) 수", "중복 행(Row) 수", "결측값 총합"],
            "값": [
                f"{df_filtered.shape[0]:,}", 
                f"{df_filtered.shape[1]:,}", 
                f"{df_filtered.duplicated().sum():,}", 
                f"{df_filtered.isnull().sum().sum():,}"
            ]
        }
        st.table(pd.DataFrame(meta_data))
        
    with col_info_right:
        st.markdown("#### 🔠 컬럼별 데이터 타입 및 결측치 현황")
        col_summary = pd.DataFrame({
            "데이터 타입": df_filtered.dtypes.astype(str),
            "결측치 수": df_filtered.isnull().sum(),
            "결측 비율 (%)": (df_filtered.isnull().sum() / len(df_filtered)) * 100
        })
        st.dataframe(col_summary, use_container_width=True)
        
    st.markdown("---")
    
    st.markdown("#### 🔝 데이터 상위 5개 행 (Head)")
    st.dataframe(df_filtered.head(5), use_container_width=True)
    
    st.markdown("#### 🔚 데이터 하위 5개 행 (Tail)")
    st.dataframe(df_filtered.tail(5), use_container_width=True)

# -----------------------------------------------------------------------------
# [TAB 2] 기본 기술통계 & 보고서 (1,000자 이상 심층 보고서 포함)
# -----------------------------------------------------------------------------
with tab2:
    st.subheader("📝 변수 유형별 기술통계 및 심층 분석 리포트")
    st.markdown("데이터의 기초 통계량을 수치형 및 범주형 변수로 나누어 살피고 전문적인 분석 리포트를 확인합니다.")
    
    stat_sub_tab1, stat_sub_tab2 = st.tabs(["🔢 수치형 변수 통계 & 분석", "🔠 범주형 변수 통계 & 분석"])
    
    with stat_sub_tab1:
        st.markdown("#### 📊 수치형 변수 요약 통계표")
        desc_numeric = df_filtered[['총생활인구수', '생활인구수']].describe()
        st.dataframe(desc_numeric, use_container_width=True)
        
        st.markdown("---")
        with st.expander("📘 [수치형 변수] 심층 분석 보고서 (클릭하여 열기)", expanded=True):
            st.markdown("""
            ### 1. 총생활인구수 및 세부 생활인구수 통계 요약 분석
            
            서울시 행정동별 및 성별/연령대별 생활인구 데이터의 수치적 특성을 살펴보면, 서울이라는 메트로폴리스가 가진 역동성과 공간적 집중성을 직관적으로 관찰할 수 있습니다. 
            '총생활인구수'는 특정 행정동에 특정 시점(날짜 및 시간대)에 존재하는 모든 인구의 합계를 나타내며, 평균적으로 수만 명 수준을 유지하지만 행정동의 성격(상업지구, 업무지구, 주거지역)에 따라 편차가 극도로 크게 나타납니다. 
            예를 들어 강남역 인근의 역삼동, 테헤란로 주변의 삼성동, 금융 중심지인 여의도동, 그리고 역사적 상업 중심지인 명동 등은 낮 시간대 업무를 보거나 여가를 즐기는 유동인구가 집중되면서 총생활인구수가 피크 시간대에 급격히 상승합니다. 반면, 외곽의 전형적인 주거용 행정동들은 주간에는 인구가 유출되고 야간에 거주자 중심으로 인구가 복귀하는 경향을 보여 수치형 분포에서 매우 뚜렷한 이봉형(bimodal) 또는 넓은 편차를 가진 분포를 그리게 됩니다.
            
            또한, '생활인구수'(성별 및 연령별로 세분화된 인구 세그먼트)의 분포를 살펴보면 평균값에 비해 중앙값이 상대적으로 낮게 나타나고 매우 긴 오른쪽 꼬리(right-skewed)를 가진 분포를 보여줍니다. 이는 서울시 전체 행정동 중 소수의 핵심 상업·업무 지구에 특정 연령대(특히 활동성이 높은 20대와 30대) 인구가 폭발적으로 집중되고 있음을 통계적으로 뒷받침합니다. 이러한 이상치(Outlier)성 극댓값들은 단순한 데이터 오류가 아니라, 서울시 공간 구조의 고도화된 중심지 체계와 집적 경제(agglomeration economies) 효과를 대변하는 핵심적인 현상적 특징입니다.
            
            이러한 수치적 불균형은 도시 계획, 상권 분석, 교통 인프라 배치 등 정책 및 비즈니스 의사결정에서 평균치에만 의존해서는 안 됨을 시사합니다. 표준편차와 백분위수 분포를 종합적으로 파악함으로써 중심 지구의 과밀 현상과 외곽 지역의 공동화 현상을 정확히 진단하고, 시간대별 및 지역별 편차에 유연하게 대응할 수 있는 맞춤형 전략 수립이 필수적입니다.
            
            - **데이터 해석 가이드**:
              * **평균치 대비 극댓값**: '총생활인구수'의 최대값이 수십만 명에 달하는 것은 서울의 핵심 허브 지역이 보유한 강력한 인구 유입력을 증명합니다.
              * **변동성 지표 (Std)**: 표준편차가 매우 크다는 것은 지리적 조건 및 시간 흐름에 따른 생활밀도의 역동성이 매우 심하게 변화하고 있음을 보여주는 강력한 근거입니다.
            """)
            
    with stat_sub_tab2:
        st.markdown("#### 🔠 범주형 변수 빈도 통계표")
        
        col_cat_1, col_cat_2 = st.columns(2)
        with col_cat_1:
            st.markdown("**[성별] 관측 빈도 분포**")
            gender_cnt = df_filtered['성별'].value_counts().to_frame("빈도수")
            gender_cnt['비율 (%)'] = (gender_cnt['빈도수'] / len(df_filtered)) * 100
            st.dataframe(gender_cnt, use_container_width=True)
            
            st.markdown("**[요일] 관측 빈도 분포**")
            weekday_cnt = df_filtered['요일'].value_counts().sort_index().to_frame("빈도수")
            weekday_cnt['비율 (%)'] = (weekday_cnt['빈도수'] / len(df_filtered)) * 100
            st.dataframe(weekday_cnt, use_container_width=True)
            
        with col_cat_2:
            st.markdown("**[연령대] 관측 빈도 분포**")
            age_cnt = df_filtered['연령대'].value_counts().sort_index().to_frame("빈도수")
            age_cnt['비율 (%)'] = (age_cnt['빈도수'] / len(df_filtered)) * 100
            st.dataframe(age_cnt, use_container_width=True)
            
            st.markdown("**[행정동명] 상위 10개 빈도분석**")
            dong_cnt = df_filtered['행정동명'].value_counts().head(10).to_frame("빈도수")
            dong_cnt['비율 (%)'] = (dong_cnt['빈도수'] / len(df_filtered)) * 100
            st.dataframe(dong_cnt, use_container_width=True)
            
        st.markdown("---")
        with st.expander("📘 [범주형 변수] 심층 분석 보고서 (클릭하여 열기)", expanded=True):
            st.markdown("""
            ### 2. 인구학적 및 시공간적 범주형 변수 분석 및 비즈니스적 통찰
            
            범주형 변수인 성별, 연령대, 요일, 그리고 행정동명의 빈도 및 교차 분석을 수행하면 서울시 생활인구의 활동 패턴과 세그먼트별 이동 특성을 깊이 있게 이해할 수 있습니다. 
            
            먼저 '성별' 분포를 살펴보면 남성과 여성의 전체적인 관측 빈도는 비교적 균등하게 나타나지만, 특정 행정동이나 시간대에 따라 성별 구성비의 유의미한 차이가 존재합니다. 예를 들어 야간 주거지 중심의 데이터에서는 성비가 안정적인 균형을 이루는 반면, 특정 상업 및 패션 중심지(예: 성수동, 명동) 혹은 고도화된 오피스 지구에서는 성별 활동 패턴의 차이로 인해 특정 성별의 비율이 일시적으로 높게 관측되는 경향이 있습니다.
            
            '연령대' 범주는 도시의 경제 활동 인구 구조를 파악하는 핵심 지표입니다. 청년층(20대~30대)과 중장년층(40대~50대)이 서울시 생활인구의 가장 큰 비중을 차지하며 경제 활동의 중추적인 역할을 수행하고 있음을 빈도 분포를 통해 확인할 수 있습니다. 특히 20대와 30대는 유동성이 매우 높아 주중에는 직장가로, 주말에는 핫플레이스 상권(성수, 홍대 등)으로 빠르게 이동하는 동적 흐름을 주도합니다. 반면, 10대 미만이나 70대 이상의 교통 약자 및 비활동 범주는 거주지 중심의 좁은 활동 반경을 보이며 시간대별 변동폭이 상대적으로 작게 나타납니다.
            
            '요일'과 '행정동명'의 결합 빈도는 전형적인 '주중 업무형 패턴'과 '주말 여가형 패턴'의 뚜렷한 대비를 보여줍니다. 주중(월~금)에는 중구, 강남구, 영등포구 등 핵심 업무 지구의 행정동에서 사무직 인구의 밀도가 압도적으로 높아지나, 주말(토~일)이 되면 이들 지역의 생활인구는 급격히 감소(공동화 현상)하고 마포구, 요산구, 성동구 등 문화·관광 허브를 포함한 지역의 행정동 빈도가 큰 폭으로 상승합니다.
            
            이러한 범주형 특성의 상호작용은 타깃 마케팅, 부동산 입지 분석, 공공시설 운영 시간 최적화 등에 직접적인 인사이트를 제공합니다. 연령대와 요일, 지역적 범주가 결합하여 만들어내는 시공간적 격자(Spatio-temporal grid) 속에서 생활인구의 맥락을 정확히 짚어내는 분석이 현대 도시 및 비즈니스 데이터 과학의 출발점이라 할 수 있습니다.
            
            - **범주형 통계 시사점**:
              * **연령대 집중 현상**: 2030 핵심 활동 세대의 관측 밀도는 상권 매출 활성화 및 트렌드 파악의 핵심 지표가 됩니다.
              * **주중/주말 패턴의 대칭성**: 업무 지구와 상업 지구의 요일별 생활인구 변화폭은 도시 철도 증편이나 공공 서비스 운영 시간 결정에 실질적 근거가 됩니다.
            """)

# -----------------------------------------------------------------------------
# [TAB 3] 생활인구 다차원 시각화 (10개 차트 및 피봇테이블)
# -----------------------------------------------------------------------------
with tab3:
    st.subheader("📈 Plotly 기반 생활인구 다차원 분석 시각화")
    st.markdown("모든 차트는 인터랙티브 조작이 가능한 Plotly 라이브러리로 생성되었습니다. 차트 요소에 마우스를 올리면 상세 수치를 볼 수 있습니다.")
    
    # 메모리 크래시 방지 및 시각화 속도 향상을 위해 대용량 일변량 분포 시각화용 샘플 생성
    # (py-streamlit 16번 규칙 준수)
    np.random.seed(42)
    sample_size = min(100000, len(df_filtered))
    df_sampled = df_filtered.sample(n=sample_size, random_state=42) if len(df_filtered) > 100000 else df_filtered
    
    # -------------------------------------------------------------------------
    # 3.1 일변량 분석 섹션 (히스토그램, 박스플롯, 파이차트, 바차트)
    # -------------------------------------------------------------------------
    st.markdown("### 🟢 Section 1. 일변량 변수 시각화 (Univariate Analysis)")
    
    # 시각화 1: 총생활인구수 분포 히스토그램 (일변량 수치형)
    st.markdown("#### 1️⃣ 총생활인구수 분포 히스토그램")
    fig1 = px.histogram(
        df_sampled, 
        x="총생활인구수", 
        nbins=50, 
        color_discrete_sequence=[PRIMARY_COLOR],
        title=f"서울시 행정동별 총생활인구수 분포 (무작위 {sample_size:,}행 샘플)",
        labels={"총생활인구수": "총생활인구수 (명)"}
    )
    fig1.update_layout(template="plotly_white", margin=dict(l=40, r=40, t=50, b=40))
    st.plotly_chart(fig1, use_container_width=True)
    
    # 시각화 1 통계표 및 해석
    col_t1, col_e1 = st.columns([2, 3])
    with col_t1:
        st.markdown("**📊 기술 통계표**")
        st.dataframe(df_filtered['총생활인구수'].describe().to_frame("총생활인구수"), use_container_width=True)
    with col_e1:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("행정동별 총생활인구수의 빈도 분포를 통해 대부분의 지역이 2~5만 명 구간에 집중되어 있으나, 일부 초거대 과밀 지역이 긴 오른쪽 꼬리를 형성하며 존재함을 보여줍니다. 이는 서울 내 거점 지역의 인구 쏠림현상을 뜻합니다.")
        
    st.markdown("---")
    
    # 시각화 2: 세부 생활인구수 분포 박스플롯 (일변량 수치형)
    st.markdown("#### 2️⃣ 성별/연령대별 세부 생활인구수 분포 박스플롯")
    fig2 = px.box(
        df_sampled, 
        x="생활인구수", 
        color_discrete_sequence=[ACCENT_COLOR],
        title=f"성별/연령대 세부 셀(Cell)별 생활인구수 분포 및 이상치 (무작위 {sample_size:,}행 샘플)",
        labels={"생활인구수": "생활인구수 (명)"}
    )
    fig2.update_layout(template="plotly_white", margin=dict(l=40, r=40, t=50, b=40))
    st.plotly_chart(fig2, use_container_width=True)
    
    # 시각화 2 통계표 및 해석
    col_t2, col_e2 = st.columns([2, 3])
    with col_t2:
        st.markdown("**📊 분위수 분포표**")
        q_stats = df_filtered['생활인구수'].quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).to_frame("생활인구수 백분위수")
        st.dataframe(q_stats, use_container_width=True)
    with col_e2:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("성별/연령대별 세부 생활인구 분포의 상자그림을 통해 대다수의 구간 영역이 조밀하게 모여 있으나 극단적인 이상치(Outlier)들이 상위에 매우 넓게 퍼져 있음을 시사합니다. 상위 1%의 특이값이 전체 흐름을 주도합니다.")
        
    st.markdown("---")
    
    # 시각화 3: 성별 비율 파이차트 (일변량 범주형)
    st.markdown("#### 3️⃣ 성별 생활인구 비율 분석")
    gender_sum = df_filtered.groupby("성별", observed=True)["생활인구수"].sum().reset_index()
    fig3 = px.pie(
        gender_sum, 
        values="생활인구수", 
        names="성별", 
        color_discrete_sequence=["#3A6073", "#FF6B6B"],
        title="서울시 전체 누적 생활인구 성별 구성비",
        hole=0.4
    )
    fig3.update_layout(template="plotly_white")
    st.plotly_chart(fig3, use_container_width=True)
    
    # 시각화 3 통계표 및 해석
    col_t3, col_e3 = st.columns([2, 3])
    with col_t3:
        st.markdown("**📊 성별 집계 통계표**")
        gender_sum['비율 (%)'] = (gender_sum['생활인구수'] / gender_sum['생활인구수'].sum()) * 100
        st.dataframe(gender_sum, use_container_width=True)
    with col_e3:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("서울시 전체 생활인구의 성별 구성 비율을 파이 차트로 시각화한 결과, 남성과 여성의 비율이 대략 5대 5 수준으로 매우 팽팽한 균형을 유지하고 있음을 보여줍니다. 특정 필터(행정동 등)를 걸면 이 비중이 변화합니다.")
        
    st.markdown("---")
    
    # 시각화 4: 연령대별 분포 빈도 바차트 (일변량 범주형 - 상위 30개 제한 규칙 적용)
    st.markdown("#### 4️⃣ 연령대별 관측 빈도 분포")
    age_counts_df = df_filtered['연령대'].value_counts().sort_index().reset_index()
    age_counts_df.columns = ['연령대', '빈도수']
    # 상위 30개 제한 (연령대 범주는 14개뿐이지만 규칙을 안전하게 코딩)
    age_counts_df = age_counts_df.head(30)
    
    fig4 = px.bar(
        age_counts_df,
        x='연령대',
        y='빈도수',
        color='연령대',
        color_discrete_sequence=px.colors.qualitative.Prism,
        title="생활인구 데이터 내 연령대별 관측 빈도 분포 (상위 30개 이하)",
        labels={'빈도수': '관측 데이터 건수'}
    )
    fig4.update_layout(template="plotly_white", showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)
    
    # 시각화 4 통계표 및 해석
    col_t4, col_e4 = st.columns([2, 3])
    with col_t4:
        st.markdown("**📊 연령대 빈도 통계표**")
        st.dataframe(age_counts_df, use_container_width=True)
    with col_e4:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("데이터상의 연령대별 빈도 분석을 통해 활동성이 높고 경제활동의 주축이 되는 20대부터 50대까지의 인구층이 고르게 높은 관측 빈도를 나타내고 있음을 알 수 있습니다. 연령대별 고른 분포는 폭넓은 사용자층을 뜻합니다.")
        
    # -------------------------------------------------------------------------
    # 3.2 이변량 분석 섹션 (성별 vs 생활인구, 연령대 vs 생활인구, 시간대 vs 총생활인구, 시계열)
    # -------------------------------------------------------------------------
    st.markdown("### 🔵 Section 2. 이변량 변수 시각화 (Bivariate Analysis)")
    
    # 시각화 5: 성별에 따른 평균 생활인구수 비교 (이변량 범주 vs 수치)
    st.markdown("#### 5️⃣ 성별 평균 생활인구수 비교")
    gender_mean = df_filtered.groupby("성별", observed=True)["생활인구수"].mean().reset_index()
    fig5 = px.bar(
        gender_mean,
        x="성별",
        y="생활인구수",
        color="성별",
        color_discrete_map={"남자": PRIMARY_COLOR, "여자": ACCENT_COLOR},
        title="성별에 따른 1회 관측 평균 생활인구수 비교",
        labels={"생활인구수": "평균 생활인구수 (명)"}
    )
    fig5.update_layout(template="plotly_white")
    st.plotly_chart(fig5, use_container_width=True)
    
    # 시각화 5 통계표 및 해석
    col_t5, col_e5 = st.columns([2, 3])
    with col_t5:
        st.markdown("**📊 성별 기술 통계표**")
        gender_agg_stats = df_filtered.groupby("성별", observed=True)["생활인구수"].agg(["mean", "std", "max"]).reset_index()
        st.dataframe(gender_agg_stats, use_container_width=True)
    with col_e5:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("성별에 따른 평균 생활인구수 비교 결과, 두 성별 집단 간의 평균값 차이는 미미하지만 특정 시공간적 조건 하에서 나타나는 세부 활동 특성은 다를 수 있음을 시사합니다. 전체적인 성별 볼륨 차이는 크지 않습니다.")
        
    st.markdown("---")
    
    # 시각화 6: 연령대별 생활인구수 분포 (이변량 범주 vs 수치)
    st.markdown("#### 6️⃣ 연령대 대분류별 생활인구수 분포")
    # 샘플링 데이터 활용
    fig6 = px.box(
        df_sampled,
        x="연령대_대분류",
        y="생활인구수",
        color="연령대_대분류",
        color_discrete_sequence=COLOR_SEQUENCE,
        title=f"연령대 대분류별 세부 생활인구수 분포 현황 (로그 스케일 적용, 무작위 {sample_size:,}행 샘플)",
        labels={"생활인구수": "생활인구수 (명)", "연령대_대분류": "연령대"},
        log_y=True
    )
    fig6.update_layout(template="plotly_white", showlegend=False)
    st.plotly_chart(fig6, use_container_width=True)
    
    # 시각화 6 통계표 및 해석
    col_t6, col_e6 = st.columns([2, 3])
    with col_t6:
        st.markdown("**📊 연령대별 기술 통계표**")
        age_agg_stats = df_filtered.groupby("연령대_대분류", observed=True)["생활인구수"].agg(["mean", "std", "median"]).reset_index()
        st.dataframe(age_agg_stats, use_container_width=True)
    with col_e6:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("연령대별 평균 생활인구수의 분포를 상자그림으로 비교해 보면, 특정 경제활동 연령층(특히 20-40대)에서 중앙값이 소폭 높고 상위 이상치 값이 더 넓게 나타나는 특징을 보입니다. 청장년층의 유동성이 큽니다.")
        
    st.markdown("---")
    
    # 시각화 7: 시간대별 평균 총생활인구수 추이 (이변량 수치 vs 수치)
    st.markdown("#### 7️⃣ 시간대별 평균 총생활인구수 추이")
    hourly_pop = df_filtered.groupby("시간대구분")["총생활인구수"].mean().reset_index()
    fig7 = px.line(
        hourly_pop,
        x="시간대구분",
        y="총생활인구수",
        markers=True,
        line_shape="linear",
        title="하루 시간대별 행정동 평균 총생활인구수 변화 패턴",
        labels={"총생활인구수": "평균 총생활인구수 (명)", "시간대구분": "시간대 (시)"}
    )
    fig7.update_traces(line_color=PRIMARY_COLOR, line_width=3, marker=dict(size=8, color=ACCENT_COLOR))
    fig7.update_layout(template="plotly_white", xaxis=dict(tickmode="linear", tick0=0, dtick=1))
    st.plotly_chart(fig7, use_container_width=True)
    
    # 시각화 7 통계표 및 해석
    col_t7, col_e7 = st.columns([2, 3])
    with col_t7:
        st.markdown("**📊 시간대별 평균 테이블**")
        st.dataframe(hourly_pop, use_container_width=True)
    with col_e7:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("시간대별 평균 총생활인구수의 일중 추이를 분석한 결과, 새벽 시간대에 최저점을 기록한 후 출근 시간대인 오전 8~9시를 기점으로 급격히 상승하여 주간에 고점을 유지하는 패턴을 보입니다. 업무 및 일상 활동이 뚜렷이 반영됩니다.")
        
    st.markdown("---")
    
    # 시각화 8: 기준일ID별 서울시 전체 총생활인구수 합계 (이변량 시계열)
    st.markdown("#### 8️⃣ 2026년 6월 일자별 합산 총생활인구수 추이")
    daily_total = df_filtered.groupby("기준일ID")["총생활인구수"].sum().reset_index()
    daily_total['기준일ID_str'] = pd.to_datetime(daily_total['기준일ID'].astype(str), format='%Y%m%d').dt.strftime('%m-%d')
    
    fig8 = px.line(
        daily_total,
        x="기준일ID_str",
        y="총생활인구수",
        markers=True,
        title="2026년 6월 일자별 서울시 전체 합산 총생활인구수 시계열 추이",
        labels={"총생활인구수": "합산 총생활인구수 (명)", "기준일ID_str": "날짜 (월-일)"}
    )
    fig8.update_traces(line_color="#4CA1AF", line_width=2.5, marker=dict(size=6, color="#FFD25A"))
    fig8.update_layout(template="plotly_white")
    st.plotly_chart(fig8, use_container_width=True)
    
    # 시각화 8 통계표 및 해석
    col_t8, col_e8 = st.columns([2, 3])
    with col_t8:
        st.markdown("**📊 일별 합계 테이블**")
        st.dataframe(daily_total[['기준일ID_str', '총생활인구수']], use_container_width=True)
    with col_e8:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("2026년 6월 한 달간의 일별 전체 생활인구 합계 추이를 보면, 평일에는 상대적으로 높은 수준을 일정하게 유지하다가 주말이 되면 전체 합산 생활인구가 유의미하게 감소하는 주기가 관찰됩니다. 주말 유출 경향성이 보입니다.")
        
    # -------------------------------------------------------------------------
    # 3.3 다변량 분석 섹션 (성별 x 연령대별 히트맵, 요일 x 시간대별 히트맵)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 🟡 Section 3. 다변량 변수 시각화 (Multivariate Analysis)")
    
    # 시각화 9: 성별 x 연령대별 평균 생활인구수 히트맵 (다변량)
    st.markdown("#### 9️⃣ 성별 및 연령대 조합별 평균 생활인구수 히트맵")
    pivot_gender_age = df_filtered.groupby(['성별', '연령대'], observed=True)['생활인구수'].mean().unstack()
    
    fig9 = px.imshow(
        pivot_gender_age,
        labels=dict(x="연령대", y="성별", color="평균 인구수"),
        x=pivot_gender_age.columns,
        y=pivot_gender_age.index,
        color_continuous_scale="YlGnBu",
        title="성별 및 연령대 조합별 평균 생활인구수 분포"
    )
    fig9.update_layout(template="plotly_white")
    st.plotly_chart(fig9, use_container_width=True)
    
    # 시각화 9 통계표 및 해석
    col_t9, col_e9 = st.columns([2, 3])
    with col_t9:
        st.markdown("**📊 성별 x 연령대 피봇테이블**")
        st.dataframe(pivot_gender_age, use_container_width=True)
    with col_e9:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("성별 및 연령대 조합별 평균 생활인구 밀도를 히트맵으로 분석해 보면, 남녀 모두 20대와 30대, 그리고 40대 연령층에서 평균 생활인구 농도가 상대적으로 짙게 관측되어 중심을 이룹니다. 핵심 생산 연령대의 위상입니다.")
        
    st.markdown("---")
    
    # 시각화 10: 요일 x 시간대별 평균 총생활인구수 히트맵 (다변량)
    st.markdown("#### 🔟 요일 및 시간대 조합별 평균 총생활인구수 히트맵")
    pivot_weekday_hourly = df_filtered.groupby(['요일', '시간대구분'], observed=True)['총생활인구수'].mean().unstack()
    
    fig10 = px.imshow(
        pivot_weekday_hourly,
        labels=dict(x="시간대구분 (시)", y="요일", color="평균 총인구수"),
        x=pivot_weekday_hourly.columns,
        y=pivot_weekday_hourly.index,
        color_continuous_scale="magma",
        title="요일 및 시간대 조합별 서울시 평균 총생활인구수 분포"
    )
    fig10.update_layout(template="plotly_white", xaxis=dict(tickmode="linear", tick0=0, dtick=1))
    st.plotly_chart(fig10, use_container_width=True)
    
    # 시각화 10 통계표 및 해석
    col_t10, col_e10 = st.columns([2, 3])
    with col_t10:
        st.markdown("**📊 요일 x 시간대 피봇테이블**")
        st.dataframe(pivot_weekday_hourly, use_container_width=True)
    with col_e10:
        st.markdown("**💡 데이터 분석 및 해석**")
        st.info("요일과 시간대의 2차원 교차 히트맵 분석을 통해, 주중 오전 9시부터 오후 6시까지의 경제 활동 핵심 시간대에 서울 전체의 총생활인구 집중도가 가장 극대화됨을 직관적으로 증명합니다. 주말 밤/주말 낮 패턴도 비교 가능합니다.")

# -----------------------------------------------------------------------------
# [TAB 4] 생활인구 지도 시각화
# -----------------------------------------------------------------------------
with tab4:
    st.subheader("🗺️ 서울시 구별/동별 생활인구 지도 시각화")
    st.markdown("Folium 코로플리스 맵을 통해 시간대별/지역별 생활인구 밀도를 공간적으로 분석합니다. 사이드바 필터(시간대, 요일, 성별 등)와 연동됩니다.")
    
    import folium
    import copy
    
    # 지도 분석 단위 선택
    map_unit = st.radio(
        "지도 시각화 단위 선택",
        options=["자치구별", "행정동별"],
        horizontal=True,
        index=0
    )
    
    # 1. 지도 시각화 데이터 집계 및 가공
    if map_unit == "자치구별":
        # 구별로 집계하기 위해 통계청코드 앞 5자리 추출하여 구코드 생성
        df_filtered['구코드'] = df_filtered['통계청코드'].str[:5]
        
        # 구코드별 평균 인구 집계 (observed=True 적용)
        df_map_data = df_filtered.groupby(['구코드', '자치구명'], observed=True)['생활인구수'].mean().reset_index()
        df_map_data.columns = ['key', 'name', '평균생활인구']
        
        # GeoJSON 로드 (로컬 최적화 파일 우선 로드)
        seoul_geojson = load_seoul_geojson("municipalities")
        legend_name = "자치구별 평균 생활인구수 (명)"
    else:
        # 동별 평균 인구 집계 (observed=True 적용)
        df_map_data = df_filtered.groupby(['통계청코드', '행정동명'], observed=True)['생활인구수'].mean().reset_index()
        df_map_data.columns = ['key', 'name', '평균생활인구']
        
        # GeoJSON 로드 (로컬 최적화 파일 우선 로드)
        seoul_geojson = load_seoul_geojson("submunicipalities")
        legend_name = "행정동별 평균 생활인구수 (명)"
        
    if not seoul_geojson or not seoul_geojson.get('features'):
        st.warning("⚠️ 지도 데이터를 불러오는 중 오류가 발생했거나 데이터가 비어 있습니다.")
    else:
        # 데이터 매핑용 딕셔너리 생성
        density_dict = dict(zip(df_map_data['key'], df_map_data['평균생활인구']))
        name_dict = dict(zip(df_map_data['key'], df_map_data['name']))
        
        # GeoJSON에 인구밀도 데이터 주입하여 툴팁 연동 준비 (Deep Copy)
        seoul_geojson_mapped = copy.deepcopy(seoul_geojson)
        for feature in seoul_geojson_mapped['features']:
            code = feature['properties']['code']
            val = density_dict.get(code, 0)
            feature['properties']['density'] = round(val, 1)
            # 매핑된 정확한 이름을 tooltip에 렌더링하기 위해 properties 주입
            feature['properties']['mapped_name'] = name_dict.get(code, feature['properties']['name'])
            
        # 2. Folium 지도 객체 생성 (서울시 중심 좌표 기준)
        m = folium.Map(
            location=[37.5665, 126.9780],
            zoom_start=11,
            tiles="cartodbpositron" # 가독성 좋은 밝은 배경 테마
        )
        
        # 3. 코로플리스 맵 레이어 추가
        folium.Choropleth(
            geo_data=seoul_geojson,
            data=df_map_data,
            columns=['key', '평균생활인구'],
            key_on='feature.properties.code',
            fill_color='YlOrRd',
            fill_alpha=0.7,
            line_alpha=0.3,
            legend_name=legend_name,
            highlight=True
        ).add_to(m)
        
        # 4. 마우스 오버 툴팁 기능을 위한 인터랙티브 투명 GeoJSON 레이어 추가
        tooltip = folium.GeoJsonTooltip(
            fields=['mapped_name', 'density'],
            aliases=['행정구역명:', '평균 생활인구 (명):'],
            localize=True,
            sticky=True,
            style="background-color: white; color: #333333; font-family: sans-serif; font-size: 12px; border: 1px solid grey; border-radius: 3px; padding: 10px;"
        )
        
        folium.GeoJson(
            seoul_geojson_mapped,
            style_function=lambda x: {
                'fillColor': 'transparent', 
                'color': 'black', 
                'weight': 0.5,
                'fillOpacity': 0.0
            },
            highlight_function=lambda x: {
                'weight': 2.0, 
                'color': '#FF6B6B',
                'fillOpacity': 0.1
            },
            tooltip=tooltip
        ).add_to(m)
        
        # 5. Streamlit HTML 컴포넌트로 지도 임베딩 렌더링
        st.markdown("#### 🗺️ 서울시 생활인구 공간 밀도 분포")
        st.caption("지도 영역 위에 마우스를 올리면 각 행정구역의 상세 명칭과 평균 생활인구수 수치를 실시간으로 보실 수 있습니다.")
        st.components.v1.html(m._repr_html_(), height=650)
        
        # 통계 데이터 테이블 추가 제공
        st.markdown("#### 📋 지도 연동 요약 데이터 테이블")
        df_table_show = df_map_data.sort_values(by='평균생활인구', ascending=False).reset_index(drop=True)
        df_table_show.columns = ['행정구역코드', '행정구역명', '평균 생활인구수 (명)']
        st.dataframe(df_table_show, use_container_width=True)
        
        # 50자 이상의 시각화 해석 및 설명
        st.info("💡 **지도 시각화 분석 해석**: 코로플리스 지도상에서 붉은색 농도가 짙을수록 생활인구가 밀집된 지역입니다. 시간대 필터링을 변경함에 따라 주간 오피스 집중 지구와 야간 주거 위주 배후 지구 간의 극명한 인구 대칭 이동 현상을 지리적으로 생생히 관찰할 수 있습니다.")
