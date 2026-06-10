"""
네이버 카페글 검색 API 수집 및 분석 대시보드 페이지입니다.

쉼표(`,`)로 구분된 키워드별 카페 게시글 검색 결과를 수집하여 분석합니다.
네이버 카페글 API 특성상 작성일 정보가 포함되어 있지 않음을 사용자에게 친절하게 안내하고,
수집된 데이터의 키워드별 포스팅 분포 및 상위 노출 카페 분석, 상세 리스트 출력(링크 연결 포함) 및 CSV 다운로드 기능을 제공합니다.
"""

import streamlit as st
import pandas as pd
import re
import plotly.express as px
from datetime import datetime
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
st.set_page_config(page_title="카페 검색 분석", page_icon="☕", layout="wide")

# 사이드바 API 설정 렌더링
render_sidebar()

# 메인 콘텐츠
st.title("☕ 네이버 카페글 검색 및 커뮤니티 분석")
st.markdown("네이버 공개 카페 게시글을 검색하여 키워드 분포와 주요 노출 카페 통계를 제공합니다.")

# API 연결 검증
client_id = st.session_state.get("client_id", "")
client_secret = st.session_state.get("client_secret", "")

if not check_api_credentials(client_id, client_secret):
    st.warning("⚠️ 사이드바 메뉴에서 네이버 API Key(Client ID, Client Secret)를 설정해 주세요.")
    st.stop()

# 폼 레이아웃 설정
with st.form("cafe_search_form"):
    st.subheader("🔍 카페글 검색 조건 설정")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        keywords_input = st.text_input(
            "검색 키워드 (쉼표 `,` 로 구분하여 입력)", 
            value="맥북, 그램",
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
        
    st.info("⚠️ **안내**: 네이버 카페글 검색 API는 공식 스펙상 작성일(날짜) 정보를 제공하지 않습니다. 따라서 기간 필터링 기능 대신 수집 시점의 전체 검색 결과 통계를 시각화합니다.")
    
    submit_button = st.form_submit_button("☕ 카페글 데이터 수집 및 분석")

# 검색 실행 및 데이터 전처리
if submit_button:
    keywords = parse_keywords(keywords_input)
    
    if not keywords:
        st.error("❌ 최소 하나 이상의 키워드를 입력해 주세요.")
        st.stop()
        
    st.subheader("📊 수집 데이터 분석 결과")
    
    all_data = []
    
    with st.spinner("네이버 카페글 검색 API로부터 데이터를 수집하는 중..."):
        for kw in keywords:
            try:
                df_kw = fetch_search_data(
                    api_type="cafearticle",
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
    
    st.success(f"✅ 총 {len(combined_df)}건의 카페글 데이터를 성공적으로 분석했습니다.")
    
    # 시각화 영역 분할
    tab1, tab2 = st.tabs(["📊 커뮤니티 분석 통계", "📋 수집 데이터 리스트"])
    
    with tab1:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # 시각화 1: 키워드별 카페글 분포 (Bar chart)
            kw_counts = combined_df["search_keyword"].value_counts().reset_index()
            kw_counts.columns = ["키워드", "게시글 수"]
            
            fig1 = px.bar(
                kw_counts,
                x="키워드",
                y="게시글 수",
                color="키워드",
                title="키워드별 카페글 게시물 분포",
                text="게시글 수"
            )
            fig1.update_traces(textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            # 시각화 2: 언급이 가장 많은 카페 상위 10개 (Cafename 분포)
            cafe_counts = combined_df["cafename"].value_counts().head(10).reset_index()
            cafe_counts.columns = ["카페명", "언급 횟수"]
            
            fig2 = px.bar(
                cafe_counts,
                x="언급 횟수",
                y="카페명",
                orientation="h",
                title="키워드 언급 빈도가 높은 상위 10개 카페",
                color="언급 횟수",
                color_continuous_scale="Purples"
            )
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            
    with tab2:
        # 데이터프레임 가독성 정돈
        display_df = combined_df[["search_keyword", "title", "description", "cafename", "link"]].copy()
        display_df.columns = ["검색 키워드", "게시글 제목", "내용 요약", "카페명", "이동 링크"]
        
        st.dataframe(
            display_df,
            column_config={
                "이동 링크": st.column_config.LinkColumn("게시글 연결 링크")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 다운로드 기능
        today_str = datetime.today().strftime("%Y-%m-%d")
        csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 수집 데이터 CSV 다운로드",
            data=csv_data,
            file_name=f"naver_cafe_search_{today_str}.csv",
            mime="text/csv"
        )
