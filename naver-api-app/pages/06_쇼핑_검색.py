"""
네이버 쇼핑 검색 API 수집 및 가격/브랜드 분석 대시보드 페이지입니다.

쉼표(`,`)로 구분된 키워드들에 대해 상품 검색을 수행하고 최저가(lprice) 수치 변환, 쇼핑몰명, 브랜드명 등 
필수 필드 데이터를 전처리합니다. Plotly를 활용해 키워드별 최저가 분포(히스토그램), 상위 인기 브랜드 및 
입점 쇼핑몰 점유율을 시각화합니다. Streamlit의 ImageColumn 기능을 사용해 실물 상품 이미지가 포함된 
프리미엄 데이터 테이블을 출력하며 CSV 다운로드를 지원합니다.
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
    텍스트 내 HTML 태그 및 엔티티를 제거합니다.
    """
    if not isinstance(text, str):
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&apos;", "'")
    return clean

# 페이지 레이아웃
st.set_page_config(page_title="쇼핑 검색 분석", page_icon="🛒", layout="wide")

# 사이드바 API 설정 렌더링
render_sidebar()

# 메인 콘텐츠
st.title("🛒 네이버 쇼핑 상품 검색 및 시장 분석")
st.markdown("특정 상품 키워드들을 검색하여 가격대 분포, 점유율이 높은 판매처 및 브랜드를 분석합니다.")

# API 연결 검증
client_id = st.session_state.get("client_id", "")
client_secret = st.session_state.get("client_secret", "")

if not check_api_credentials(client_id, client_secret):
    st.warning("⚠️ 사이드바 메뉴에서 네이버 API Key(Client ID, Client Secret)를 설정해 주세요.")
    st.stop()

# 폼 레이아웃 설정
with st.form("shop_search_form"):
    st.subheader("🔍 쇼핑 상품 검색 조건 설정")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        keywords_input = st.text_input(
            "검색 키워드 (쉼표 `,` 로 구분하여 입력)", 
            value="기계식 키보드, 무소음 마우스",
            help="각 키워드별로 쇼핑 상품 데이터를 개별 수집 후 분석합니다."
        )
        
    with col2:
        sort_type = st.selectbox(
            "정렬 방식", 
            options=["sim", "date", "asc", "dsc"], 
            format_func=lambda x: "유사도순 (정확도)" if x == "sim" else "날짜순" if x == "date" else "가격 낮은순" if x == "asc" else "가격 높은순"
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
        
    st.info("⚠️ **안내**: 네이버 쇼핑 상품 검색 API는 등록일 필터링 기간 설정을 직접 지원하지 않습니다. 따라서 수집된 상품들의 실시간 가격 분석 및 마켓 통계 분석에 집중한 대시보드를 제공합니다.")
    
    submit_button = st.form_submit_button("🛒 쇼핑 상품 데이터 수집 및 분석")

# 검색 실행 및 데이터 전처리
if submit_button:
    keywords = parse_keywords(keywords_input)
    
    if not keywords:
        st.error("❌ 최소 하나 이상의 키워드를 입력해 주세요.")
        st.stop()
        
    st.subheader("📊 쇼핑 시장 데이터 분석 결과")
    
    all_data = []
    
    with st.spinner("네이버 쇼핑 API로부터 상품 데이터를 수집하는 중..."):
        for kw in keywords:
            try:
                df_kw = fetch_search_data(
                    api_type="shop",
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
    
    # 가격 정보 숫자로 변환 (lprice 최저가)
    combined_df["low_price"] = pd.to_numeric(combined_df["lprice"], errors="coerce").fillna(0).astype(int)
    
    # 브랜드 및 쇼핑몰 공백 채우기
    combined_df["brand"] = combined_df["brand"].replace("", "미지정")
    combined_df["mallName"] = combined_df["mallName"].replace("", "기타 쇼핑몰")
    
    st.success(f"✅ 총 {len(combined_df)}개의 쇼핑 상품 데이터를 성공적으로 수집하여 분석을 시작합니다.")
    
    # 시각화 영역 분할
    tab1, tab2 = st.tabs(["📊 가격 및 브랜드 분석 통계", "📋 수집 상품 리스트"])
    
    with tab1:
        # 시각화 1: 키워드별 가격대 분포 (Histogram)
        st.subheader("💵 키워드별 상품 가격대 분포 비교")
        fig1 = px.histogram(
            combined_df[combined_df["low_price"] > 0],
            x="low_price",
            color="search_keyword",
            marginal="box",  # 상단에 박스플롯 표시하여 유입 범위 시각화
            barmode="overlay",
            title="상품 최저가 분포 (Box Plot 포함)",
            labels={"low_price": "최저 가격 (원)", "count": "상품 수", "search_keyword": "키워드"}
        )
        fig1.update_layout(hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            # 시각화 2: 상위 노출 쇼핑몰 점유율
            mall_counts = combined_df["mallName"].value_counts().head(10).reset_index()
            mall_counts.columns = ["쇼핑몰명", "상품 수"]
            
            fig2 = px.pie(
                mall_counts,
                values="상품 수",
                names="쇼핑몰명",
                title="상위 10개 입점 쇼핑몰 비중",
                hole=0.4
            )
            st.plotly_chart(fig2, use_container_width=True)
            
        with col_chart2:
            # 시각화 3: 상위 인기 브랜드
            brand_counts = combined_df[combined_df["brand"] != "미지정"]["brand"].value_counts().head(10).reset_index()
            brand_counts.columns = ["브랜드명", "상품 수"]
            
            if not brand_counts.empty:
                fig3 = px.bar(
                    brand_counts,
                    x="상품 수",
                    y="브랜드명",
                    orientation="h",
                    title="검색 결과 노출 상위 10개 브랜드",
                    color="상품 수",
                    color_continuous_scale="Viridis"
                )
                fig3.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("ℹ️ 브랜드 정보가 지정된 상품이 없습니다.")
                
    with tab2:
        # 데이터프레임 가독성 정돈 (Image Column 설정 포함)
        display_df = combined_df[["image", "search_keyword", "title", "low_price", "brand", "mallName", "link"]].copy()
        display_df.columns = ["이미지", "검색 키워드", "상품명", "최저가 (원)", "브랜드", "판매처", "이동 링크"]
        
        # 가격 포맷팅 추가 (화면 표시용)
        st.dataframe(
            display_df,
            column_config={
                "이미지": st.column_config.ImageColumn("상품 이미지", width="small"),
                "최저가 (원)": st.column_config.NumberColumn("최저가 (원)", format="%d원"),
                "이동 링크": st.column_config.LinkColumn("구매 페이지 연결")
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
            file_name=f"naver_shopping_search_{today_str}.csv",
            mime="text/csv"
        )
