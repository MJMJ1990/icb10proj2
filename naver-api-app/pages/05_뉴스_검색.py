"""
네이버 뉴스 검색 API 수집 및 분석 대시보드 페이지입니다.

쉼표(`,`)로 구분된 키워드들에 대해 실시간 뉴스를 검색하고, RFC 822 형식의 날짜 파싱 및 언론사 도메인 추출 등 
전처리를 수행합니다. 사용자가 지정한 검색 기간 조건에 따라 뉴스를 필터링하고 주요 보도 언론사 점유율, 
일자별 보도 트렌드를 시각화(Plotly)하며 상세 기사 목록 및 CSV 다운로드를 지원합니다.
"""

import streamlit as st
import pandas as pd
import re
import plotly.express as px
from datetime import datetime, date
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime
from utils import (
    render_sidebar, 
    check_api_credentials, 
    parse_keywords, 
    fetch_search_data
)

def clean_html(text: str) -> str:
    """
    텍스트 내 HTML 태그 및 엔티티를 제거합니다.
    """
    if not isinstance(text, str):
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&apos;", "'")
    return clean

def extract_media(url: str) -> str:
    """
    뉴스 기사 URL에서 주요 도메인명을 추출하여 언론사를 간이 파악합니다.
    """
    if not isinstance(url, str) or not url:
        return "기타"
    try:
        netloc = urlparse(url).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # 자주 노출되는 대표 도메인 한글화 매핑 (옵션)
        media_map = {
            "news.naver.com": "네이버뉴스",
            "sports.news.naver.com": "네이버스포츠",
            "chosun.com": "조선일보",
            "joongang.co.kr": "중앙일보",
            "donga.com": "동아일보",
            "hani.co.kr": "한겨레",
            "khan.co.kr": "경향신문",
            "mk.co.kr": "매일경제",
            "hankyung.com": "한국경제",
            "yna.co.kr": "연합뉴스",
            "ytn.co.kr": "YTN",
            "sbs.co.kr": "SBS",
            "imbc.com": "MBC",
            "kbs.co.kr": "KBS"
        }
        return media_map.get(netloc, netloc)
    except:
        return "기타"

def parse_pubdate(pubdate_str: str) -> datetime:
    """
    RFC 822 형식의 날짜 문자열을 datetime 객체로 파싱합니다.
    """
    try:
        return parsedate_to_datetime(pubdate_str)
    except:
        # 실패 시 현재 시각 반환
        return datetime.now()

# 페이지 레이아웃
st.set_page_config(page_title="뉴스 검색 분석", page_icon="📰", layout="wide")

# 사이드바 API 설정 렌더링
render_sidebar()

# 메인 콘텐츠
st.title("📰 네이버 뉴스 검색 및 미디어 분석")
st.markdown("특정 키워드들의 실시간 뉴스를 검색하고, 언론사 분포 및 주요 보도 트렌드를 추적합니다.")

# API 연결 검증
client_id = st.session_state.get("client_id", "")
client_secret = st.session_state.get("client_secret", "")

if not check_api_credentials(client_id, client_secret):
    st.warning("⚠️ 사이드바 메뉴에서 네이버 API Key(Client ID, Client Secret)를 설정해 주세요.")
    st.stop()

# 폼 레이아웃 설정
with st.form("news_search_form"):
    st.subheader("🔍 뉴스 검색 조건 설정")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        keywords_input = st.text_input(
            "검색 키워드 (쉼표 `,` 로 구분하여 입력)", 
            value="금리, 인플레이션",
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
        today_date = date.today()
        default_start = today_date - pd.Timedelta(days=14)
        start_filter_date = st.date_input("분석 기간 시작일 (보도일 기준 필터)", value=default_start)
        
    with col5:
        end_filter_date = st.date_input("분석 기간 종료일 (보도일 기준 필터)", value=today_date)
        
    submit_button = st.form_submit_button("📰 뉴스 데이터 수집 및 분석")

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
    
    with st.spinner("네이버 뉴스 검색 API로부터 데이터를 수집하는 중..."):
        for kw in keywords:
            try:
                df_kw = fetch_search_data(
                    api_type="news",
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
    
    # 날짜 데이터 처리
    combined_df["news_datetime"] = combined_df["pubDate"].apply(parse_pubdate)
    combined_df["news_date"] = combined_df["news_datetime"].dt.date
    
    # 언론사 추출 (originallink 가 있으면 이를 우선 활용, 없으면 link 활용)
    combined_df["media"] = combined_df["originallink"].fillna(combined_df["link"]).apply(extract_media)
    
    # 기간 필터링 적용
    filtered_df = combined_df[
        (combined_df["news_date"] >= start_filter_date) & 
        (combined_df["news_date"] <= end_filter_date)
    ]
    
    if filtered_df.empty:
        st.warning(f"⚠️ 수집된 {len(combined_df)}건의 데이터 중 설정한 분석 기간({start_filter_date} ~ {end_filter_date})에 보도된 기사가 없습니다. 기간 설정을 넓혀보세요.")
        st.stop()
        
    st.success(f"✅ 총 {len(filtered_df)}건의 뉴스 데이터를 성공적으로 분석했습니다. (수집 데이터: {len(combined_df)}건)")
    
    # 시각화 영역 분할
    tab1, tab2 = st.tabs(["📊 미디어 분석 통계", "📋 수집 뉴스 리스트"])
    
    with tab1:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # 시각화 1: 키워드별 뉴스 점유율
            kw_counts = filtered_df["search_keyword"].value_counts().reset_index()
            kw_counts.columns = ["키워드", "보도 건수"]
            
            fig1 = px.bar(
                kw_counts,
                x="키워드",
                y="보도 건수",
                color="키워드",
                title="키워드별 뉴스 보도량 분포",
                text="보도 건수"
            )
            fig1.update_traces(textposition='outside')
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            # 시각화 2: 상위 보도 언론사 (Media 분포)
            media_counts = filtered_df["media"].value_counts().head(10).reset_index()
            media_counts.columns = ["언론사", "보도 건수"]
            
            fig2 = px.bar(
                media_counts,
                x="보도 건수",
                y="언론사",
                orientation="h",
                title="주요 보도 매체 상위 10개",
                color="보도 건수",
                color_continuous_scale="Tealgrn"
            )
            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
            
        # 시각화 3: 일자별 보도 트렌드
        date_trend = filtered_df.groupby(["news_date", "search_keyword"]).size().reset_index(name="count")
        date_trend.columns = ["보도일", "키워드", "보도 건수"]
        
        fig3 = px.line(
            date_trend,
            x="보도일",
            y="보도 건수",
            color="키워드",
            title="일자별 뉴스 보도 트렌드",
            markers=True
        )
        fig3.update_layout(hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)
        
    with tab2:
        # 데이터프레임 가독성 정돈
        display_df = filtered_df[["search_keyword", "title", "description", "media", "news_datetime", "link"]].copy()
        display_df["news_datetime"] = display_df["news_datetime"].dt.strftime("%Y-%m-%d %H:%M")
        display_df.columns = ["검색 키워드", "기사 제목", "내용 요약", "언론사(도메인)", "보도일시", "이동 링크"]
        
        st.dataframe(
            display_df,
            column_config={
                "이동 링크": st.column_config.LinkColumn("기사 원문 링크")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 다운로드 기능
        csv_data = display_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 수집 데이터 CSV 다운로드",
            data=csv_data,
            file_name=f"naver_news_search_{today_date}.csv",
            mime="text/csv"
        )
