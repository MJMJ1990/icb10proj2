"""
네이버 블로그 검색 API 수집 및 분석 대시보드 페이지입니다.

쉼표(`,`)로 구분하여 입력한 여러 키워드에 대해 블로그 검색 결과를 수집(정렬 및 건수 설정 가능)한 후,
HTML 태그 제거 및 날짜 변환 등 전처리를 거칩니다. 사용자가 지정한 검색 기간 조건에 따라 데이터를 필터링하고
키워드별 노출 분포, 일자별 작성 트렌드, 주요 활동 블로거 등의 시각화(Plotly) 및 다운로드 기능을 제공합니다.
"""

import streamlit as st
import pandas as pd
import re
import plotly.express as px
from datetime import datetime, date
from utils import (
    render_sidebar, 
    check_api_credentials, 
    parse_keywords, 
    fetch_search_data
)

def clean_html(text: str) -> str:
    """
    텍스트 내 HTML 태그(예: <b>, </b>) 및 엔티티를 정돈합니다.
    """
    if not isinstance(text, str):
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&apos;", "'")
    return clean

# 페이지 레이아웃
st.set_page_config(page_title="블로그 검색 분석", page_icon="📝", layout="wide")

# 사이드바 API 설정 렌더링
render_sidebar()

# 메인 콘텐츠
st.title("📝 네이버 블로그 검색 및 트렌드 분석")
st.markdown("특정 키워드들의 블로그 검색 결과를 수집하여 키워드별 관심도 및 인기 블로그 통계를 제공합니다.")

# API 연결 검증
client_id = st.session_state.get("client_id", "")
client_secret = st.session_state.get("client_secret", "")

if not check_api_credentials(client_id, client_secret):
    st.warning("⚠️ 사이드바 메뉴에서 네이버 API Key(Client ID, Client Secret)를 설정해 주세요.")
    st.stop()

# 폼 레이아웃 설정
with st.form("blog_search_form"):
    st.subheader("🔍 블로그 검색 조건 설정")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        keywords_input = st.text_input(
            "검색 키워드 (쉼표 `,` 로 구분하여 입력)", 
            value="인공지능, 딥러닝",
            help="각 키워드별로 검색 데이터를 개별 수집 후 분석합니다."
        )
        
    with col2:
        sort_type = st.selectbox(
            "정렬 방식", 
            options=["sim", "date"], 
            format_func=lambda x: "유사도순 (정확도)" if x == "sim" else "최신순 (날짜)"
        )
        
    with col3:
        display_num = st.slider(
            "키워드별 수집 건수", 
            min_value=10, 
            max_value=100, 
            value=50, 
            step=10,
            help="네이버 API가 제공하는 1회 최대 수집 건수는 100건입니다."
        )
        
    col4, col5 = st.columns(2)
    with col4:
        # 데이터 시각화/필터용 날짜 범위 설정
        today_date = date.today()
        # 기본 필터 기간은 최근 30일
        default_start = today_date - pd.Timedelta(days=30)
        start_filter_date = st.date_input("분석 기간 시작일 (작성일 기준 필터)", value=default_start)
        
    with col5:
        end_filter_date = st.date_input("분석 기간 종료일 (작성일 기준 필터)", value=today_date)
        
    submit_button = st.form_submit_button("📝 블로그 데이터 수집 및 분석")

# 검색 실행 및 데이터 전처리
if submit_button:
    keywords = parse_keywords(keywords_input)
    
    if not keywords:
        st.error("❌ 최소 하나 이상의 키워드를 입력해 주세요.")
        st.stop()
        
    if start_filter_date > end_filter_date:
        st.error("❌ 분석 시작일이 종료일보다 늦을 수 없습니다.")
        st.stop()
        
    st.subheader("📊 수집 데이터 분석 결과")
    
    all_data = []
    
    with st.spinner("네이버 블로그 검색 API로부터 데이터를 수집하는 중..."):
        for kw in keywords:
            try:
                df_kw = fetch_search_data(
                    api_type="blog",
                    query=kw,
                    client_id=client_id,
                    client_secret=client_secret,
                    display=display_num,
                    start=1,
                    sort=sort_type
                )
                if not df_kw.empty:
                    df_kw["search_keyword"] = kw
                    all_data.append(df_kw)
            except Exception as e:
                st.error(f"❌ '{kw}' 키워드 수집 중 오류가 발생했습니다: {str(e)}")
                
    if not all_data:
        st.info("ℹ️ 수집된 데이터가 없습니다. API 설정이나 검색어를 확인해 주세요.")
        st.stop()
        
    # 데이터 병합 및 전처리
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # HTML 태그 제거
    combined_df["title"] = combined_df["title"].apply(clean_html)
    combined_df["description"] = combined_df["description"].apply(clean_html)
    
    # 날짜 데이터 처리 (postdate format: YYYYMMDD)
    combined_df["post_date"] = pd.to_datetime(combined_df["postdate"], format="%Y%m%d", errors="coerce").dt.date
    
    # 기간 필터링 적용
    filtered_df = combined_df[
        (combined_df["post_date"] >= start_filter_date) & 
        (combined_df["post_date"] <= end_filter_date)
    ]
    
    if filtered_df.empty:
        st.warning(f"⚠️ 수집된 {len(combined_df)}건의 데이터 중 설정한 분석 기간({start_filter_date} ~ {end_filter_date})에 해당하는 포스팅이 없습니다. 기간 설정을 넓혀보세요.")
        st.stop()
        
    st.success(f"✅ 총 {len(filtered_df)}건의 블로그 데이터를 성공적으로 분석했습니다. (수집 데이터: {len(combined_df)}건)")
    
    # 시각화 영역 분할
    tab1, tab2 = st.tabs(["📈 트렌드 및 통계", "📋 수집 데이터 리스트"])
    
    with tab1:
        # 시각화 1: 키워드별 블로그 포스팅 점유율 (Bar chart)
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            kw_counts = filtered_df["search_keyword"].value_counts().reset_index()
            kw_counts.columns = ["키워드", "포스팅 수"]
            
            fig1 = px.bar(
                kw_counts,
                x="키워드",
                y="포스팅 수",
                color="키워드",
                title="분석 기간 내 키워드별 포스팅 분포",
                text="포스팅 수"
            )
            fig1.update_traces(textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            # 시각화 2: 상위 활동 블로거 (Bloggername 분포)
            blogger_counts = filtered_df["bloggername"].value_counts().head(10).reset_index()
            blogger_counts.columns = ["블로그명", "포스팅 수"]
            
            fig2 = px.bar(
                blogger_counts,
                x="포스팅 수",
                y="블로그명",
                orientation="h",
                title="상위 10개 영향력 있는 블로그 (노출 빈도순)",
                color="포스팅 수",
                color_continuous_scale="Viridis"
            )
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            
        # 시각화 3: 일자별 작성 트렌드
        date_trend = filtered_df.groupby(["post_date", "search_keyword"]).size().reset_index(name="count")
        date_trend.columns = ["작성일", "키워드", "작성 건수"]
        
        fig3 = px.line(
            date_trend,
            x="작성일",
            y="작성 건수",
            color="키워드",
            title="일자별 블로그 작성 발행 트렌드",
            markers=True
        )
        fig3.update_layout(hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)
        
    with tab2:
        # 데이터프레임 가독성 정돈
        display_df = filtered_df[["search_keyword", "title", "description", "bloggername", "post_date", "link"]].copy()
        display_df.columns = ["검색 키워드", "포스트 제목", "내용 요약", "블로그명", "작성일", "이동 링크"]
        
        st.dataframe(
            display_df,
            column_config={
                "이동 링크": st.column_config.LinkColumn("포스트 연결 링크")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 다운로드 기능
        csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 수집 데이터 CSV 다운로드",
            data=csv_data,
            file_name=f"naver_blog_search_{today_date}.csv",
            mime="text/csv"
        )
