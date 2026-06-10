"""
네이버 API 통합 데이터 분석 대시보드의 메인 진입점(App.py) 파일입니다.

대시보드 애플리케이션의 홈 화면을 렌더링하며, 사용자가 사이드바를 통해 네이버 Client ID 및 Client Secret을 
설정하고 서비스(검색어 트렌드, 쇼핑, 블로그, 카페, 뉴스, 쇼핑트렌드)를 선택하여 분석할 수 있도록 가이드합니다.
"""

import streamlit as st
from utils import render_sidebar, check_api_credentials

# 페이지 설정
st.set_page_config(
    page_title="네이버 API 통합 분석 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바 렌더링 (전역 API 설정)
render_sidebar()

# 메인 헤더
st.title("📊 네이버 API 통합 데이터 분석 대시보드")
st.markdown("---")

# 소개 글 및 가이드라인
st.markdown("""
네이버 오픈 API와 데이터랩 API를 연동하여 트렌드 비교 분석 및 각 채널별(블로그, 카페, 뉴스, 쇼핑) 데이터를 수집하고
시각화 분석을 제공하는 프리미엄 데이터 대시보드입니다.

### 🚀 시작 가이드
1. **API Key 등록**: 왼쪽 사이드바 메뉴의 **🔑 네이버 API 설정** 영역에 Client ID와 Client Secret을 입력해 주세요.
   - 키가 발급되지 않았다면 [네이버 개발자 센터](https://developers.naver.com/)에서 애플리케이션을 등록하고 발급받을 수 있습니다.
2. **분석 페이지 선택**: 왼쪽 사이드바의 페이지 메뉴에서 원하는 분석 도구를 선택해 주세요.
   - **📈 검색어 트렌드**: 네이버 통합 검색량 트렌드를 다각도로 비교합니다.
   - **🛍️ 쇼핑 트렌드**: 카테고리별 쇼핑 키워드 검색량 추세를 분석합니다.
   - **📝 블로그 검색**: 블로그 채널의 키워드 검색 데이터 및 트렌드를 수집합니다.
   - **☕ 카페 검색**: 카페글 내 키워드 언급 추이와 상세 목록을 분석합니다.
   - **📰 뉴스 검색**: 실시간 관련 뉴스와 언론사별 분포를 시각화합니다.
   - **🛒 쇼핑 검색**: 쇼핑 검색 데이터 수집 및 가격대/브랜드별 패턴을 발견합니다.

---
""")

# 상태 카드 렌더링
col1, col2 = st.columns(2)
with col1:
    st.info("💡 **Tip**: 검색어는 쉼표(`,`)로 구분하여 여러 개를 동시에 비교 분석할 수 있습니다. (예: `아이폰, 갤럭시, 픽셀`)")

with col2:
    client_id = st.session_state.get("client_id", "")
    client_secret = st.session_state.get("client_secret", "")
    if check_api_credentials(client_id, client_secret):
        st.success("✅ **연결 상태**: 네이버 API 키가 입력되어 분석 준비가 완료되었습니다. 왼쪽 메뉴에서 원하시는 분석 대시보드로 이동해 주세요!")
    else:
        st.warning("⚠️ **연결 상태**: API 키가 아직 설정되지 않았습니다. 사이드바에 키를 입력한 후 시작해 주세요.")
