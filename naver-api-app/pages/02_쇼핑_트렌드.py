"""
네이버 데이터랩 쇼핑인사이트 키워드별 트렌드 API 분석 대시보드 페이지입니다.

특정 쇼핑 카테고리 내에서 사용자가 입력한 여러 키워드들의 검색 클릭 트렌드를 기간 및 필터 조건(디바이스, 성별, 연령대)에 따라 
수집하고 시각화합니다. Plotly를 활용하여 트렌드 추이 라인 차트를 제공하며, 로딩 스피너 및 데이터 다운로드 기능을 제공합니다.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from utils import (
    render_sidebar, 
    check_api_credentials, 
    parse_keywords, 
    fetch_datalab_shopping_trend
)

# 페이지 레이아웃
st.set_page_config(page_title="쇼핑 트렌드 분석", page_icon="🛍️", layout="wide")

# 사이드바 API 설정 렌더링
render_sidebar()

# 메인 콘텐츠
st.title("🛍️ 네이버 쇼핑 트렌드 분석 (쇼핑인사이트)")
st.markdown("특정 쇼핑 카테고리 내에서 설정한 검색 키워드들의 클릭량 추세를 분석하고 트렌드를 비교합니다.")

# API 연결 검증
client_id = st.session_state.get("client_id", "")
client_secret = st.session_state.get("client_secret", "")

if not check_api_credentials(client_id, client_secret):
    st.warning("⚠️ 사이드바 메뉴에서 네이버 API Key(Client ID, Client Secret)를 설정해 주세요.")
    st.stop()

# 폼 레이아웃 설정
with st.form("shopping_trend_form"):
    st.subheader("🔍 쇼핑 트렌드 분석 조건 설정")
    
    col_cat1, col_cat2 = st.columns([2, 1])
    
    # 카테고리 선택
    categories = {
        "50000000": "패션의류",
        "50000001": "패션잡화",
        "50000002": "화장품/미용",
        "50000003": "디지털/가전",
        "50000004": "가구/인테리어",
        "50000005": "출산/육아",
        "50000006": "식품",
        "50000007": "스포츠/레저",
        "50000008": "생활/건강",
        "50000009": "여가/생활편의"
    }
    
    with col_cat1:
        cat_select = st.selectbox(
            "쇼핑 카테고리 선택",
            options=list(categories.keys()),
            format_func=lambda x: categories[x]
        )
        
    with col_cat2:
        cat_custom = st.text_input(
            "카테고리 코드 직접 입력 (선택)", 
            placeholder="예: 50000000",
            help="입력 시 위의 카테고리 선택보다 우선 적용됩니다."
        )
        
    col1, col2 = st.columns([2, 1])
    
    with col1:
        keywords_input = st.text_input(
            "비교 쇼핑 키워드 (쉼표 `,` 로 구분하여 입력)", 
            value="원피스, 셔츠, 슬랙스",
            help="최대 5개까지 입력하는 것을 권장합니다."
        )
        
    with col2:
        time_unit = st.selectbox(
            "구간 단위", 
            options=["date", "week", "month"], 
            format_func=lambda x: "일간" if x == "date" else "주간" if x == "week" else "월간"
        )
        
    col3, col4, col5 = st.columns(3)
    
    with col3:
        today = datetime.today()
        one_year_ago = today - timedelta(days=365)
        # 쇼핑인사이트는 2017년 8월 1일부터 지원
        start_date = st.date_input("조회 시작일", value=one_year_ago, min_value=datetime(2017, 8, 1), max_value=today)
        
    with col4:
        end_date = st.date_input("조회 종료일", value=today, max_value=today)
        
    with col5:
        device = st.selectbox(
            "디바이스 필터", 
            options=["", "pc", "mo"], 
            format_func=lambda x: "전체" if x == "" else "PC" if x == "pc" else "모바일"
        )
        
    col6, col7 = st.columns(2)
    with col6:
        gender = st.selectbox(
            "성별 필터", 
            options=["", "m", "f"], 
            format_func=lambda x: "전체" if x == "" else "남성" if x == "m" else "여성"
        )
        
    with col7:
        age_options = {
            "10": "10~19세", "20": "20~29세", "30": "30~39세",
            "40": "40~49세", "50": "50~59세", "60": "60세 이상"
        }
        ages_selected = st.multiselect(
            "연령대 필터 (선택 안 할 시 전체 연령)",
            options=list(age_options.keys()),
            format_func=lambda x: age_options[x]
        )
        
    submit_button = st.form_submit_button("🛍️ 쇼핑 트렌드 분석 실행")

# 분석 실행 버튼 처리
if submit_button:
    keywords = parse_keywords(keywords_input)
    category_id = cat_custom.strip() if cat_custom.strip() else cat_select
    
    if not keywords:
        st.error("❌ 최소 하나 이상의 키워드를 입력해 주세요.")
        st.stop()
        
    if not category_id:
        st.error("❌ 카테고리 코드를 선택하거나 올바르게 입력해 주세요.")
        st.stop()
        
    if start_date > end_date:
        st.error("❌ 조회 시작일이 종료일보다 늦을 수 없습니다.")
        st.stop()
        
    st.subheader(f"📊 쇼핑 키워드 클릭 트렌드 ({start_date} ~ {end_date})")
    
    with st.spinner("네이버 쇼핑인사이트 데이터를 분석 중입니다..."):
        try:
            df = fetch_datalab_shopping_trend(
                client_id=client_id,
                client_secret=client_secret,
                category_id=category_id,
                keywords_list=keywords,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                time_unit=time_unit,
                device=device,
                gender=gender,
                ages=ages_selected if ages_selected else None
            )
            
            if df.empty:
                st.info("ℹ️ 해당 기간 및 조건에 대한 쇼핑 트렌드 데이터가 존재하지 않습니다.")
            else:
                # Plotly 시각화
                fig = px.line(
                    df, 
                    x="period", 
                    y="ratio", 
                    color="keyword",
                    title=f"쇼핑 카테고리({categories.get(category_id, category_id)}) 내 키워드 클릭량 추이",
                    labels={"period": "날짜", "ratio": "상대적 클릭량 (%)", "keyword": "키워드"},
                    markers=True if time_unit != 'date' else False
                )
                fig.update_layout(
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=60, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 피벗 형태로 상세 데이터 목록 재구성
                pivot_df = df.pivot(index="period", columns="keyword", values="ratio").reset_index()
                pivot_df["period"] = pivot_df["period"].dt.strftime("%Y-%m-%d")
                pivot_df = pivot_df.rename(columns={"period": "날짜"})
                
                st.subheader("📋 상세 데이터 목록")
                st.dataframe(pivot_df, use_container_width=True)
                
                # 데이터 다운로드 제공
                csv_data = pivot_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 CSV 데이터 다운로드",
                    data=csv_data,
                    file_name=f"naver_shopping_trend_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"❌ 데이터 수집 중 오류가 발생했습니다: {str(e)}")
