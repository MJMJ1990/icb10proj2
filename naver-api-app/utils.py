"""
네이버 Open API 호출 및 데이터 가공을 위한 공통 유틸리티 모듈입니다.

이 모듈은 네이버 검색(블로그, 카페, 뉴스, 쇼핑) API 및 데이터랩(검색어 트렌드, 쇼핑인사이트) API를 
안전하게 호출하고, 반환된 데이터를 Pandas DataFrame 형태로 가공하는 헬퍼 함수들을 제공합니다.
Streamlit의 캐싱 데코레이터(@st.cache_data)를 활용하여 불필요한 API 중복 호출을 방지합니다.
"""

import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def check_api_credentials(client_id: str, client_secret: str) -> bool:
    """
    네이버 API Key의 입력 여부를 간단히 확인합니다.
    """
    return bool(client_id and client_secret)

def get_headers(client_id: str, client_secret: str) -> dict:
    """
    네이버 Open API 인증을 위한 HTTP 헤더를 구성합니다.
    앞뒤 공백문자(Space, Tab, 줄바꿈 등)를 자동으로 제거하여 인증 오류를 방지합니다.
    """
    clean_id = client_id.strip() if isinstance(client_id, str) else ""
    clean_secret = client_secret.strip() if isinstance(client_secret, str) else ""
    return {
        "X-Naver-Client-Id": clean_id,
        "X-Naver-Client-Secret": clean_secret,
        "Content-Type": "application/json"
    }

def parse_keywords(keywords_str: str) -> list:
    """
    쉼표로 구분된 키워드를 분리하여 리스트로 반환합니다.
    """
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split(",") if k.strip()]

def render_sidebar():
    """
    모든 페이지에서 공통으로 사용되는 사이드바 컴포넌트를 렌더링합니다.
    .env 파일에 API 키가 설정되어 있으면 자동으로 로드하여 세션에 저장하고 사이드바 입력을 생략합니다.
    설정되어 있지 않은 경우에만 사용자로부터 직접 입력을 받습니다.
    """
    st.sidebar.title("🔑 네이버 API 설정")
    
    # .env 파일 혹은 환경 변수에서 로드 시도
    env_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    env_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    
    # 세션 상태 초기화
    if "client_id" not in st.session_state:
        st.session_state["client_id"] = env_id
    if "client_secret" not in st.session_state:
        st.session_state["client_secret"] = env_secret
        
    # 만약 .env에 유효한 키가 설정되어 있다면 바로 사용
    if env_id and env_secret:
        st.session_state["client_id"] = env_id
        st.session_state["client_secret"] = env_secret
        st.sidebar.success("✅ .env 환경 변수에서 API 키를 자동으로 로드했습니다.")
    else:
        # .env에 키가 없는 경우에만 수동 입력란 노출 (폴백)
        client_id = st.sidebar.text_input(
            "Naver Client ID",
            value=st.session_state["client_id"],
            placeholder="Client ID를 입력하세요"
        )
        client_secret = st.sidebar.text_input(
            "Naver Client Secret",
            value=st.session_state["client_secret"],
            type="password",
            placeholder="Client Secret을 입력하세요"
        )
        st.session_state["client_id"] = client_id
        st.session_state["client_secret"] = client_secret
        
        if check_api_credentials(client_id, client_secret):
            st.sidebar.success("✅ API 설정 완료")
        else:
            st.sidebar.warning("⚠️ API 설정을 완료해주세요 (사이드바 입력 혹은 .env 파일 설정).")

@st.cache_data(show_spinner=False)
def fetch_search_data(
    api_type: str, 
    query: str, 
    client_id: str, 
    client_secret: str, 
    display: int = 100, 
    start: int = 1, 
    sort: str = "sim"
) -> pd.DataFrame:
    """
    네이버 검색 API(블로그, 카페글, 뉴스, 쇼핑)를 호출하여 데이터프레임으로 반환합니다.
    
    Args:
        api_type: 'blog', 'cafearticle', 'news', 'shop' 중 하나
        query: 검색어
        client_id: 네이버 API 클라이언트 아이디
        client_secret: 네이버 API 클라이언트 시크릿
        display: 검색 결과 출력 건수 (최대 100)
        start: 검색 시작 위치 (최대 1000)
        sort: 정렬 방식 ('sim' 또는 'date')
    """
    # 쇼핑 API의 경우 URL 엔드포인트가 'shop.json'이고 나머지는 '{api_type}.json'임
    endpoint = "shop" if api_type == "shop" else api_type
    url = f"https://openapi.naver.com/v1/search/{endpoint}.json"
    
    # 공통 헤더 생성기 사용 (공백 자동 제거 기능 내장)
    headers = get_headers(client_id, client_secret)
    
    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            df = pd.DataFrame(items)
            return df
        else:
            # 에러 발생 시 빈 데이터프레임과 에러 코드 전달을 위해 예외 발생
            response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"네이버 {api_type} API 호출 중 에러가 발생했습니다: {str(e)}")
    
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def fetch_datalab_search_trend(
    client_id: str,
    client_secret: str,
    keywords_list: list,
    start_date: str,
    end_date: str,
    time_unit: str = "date",
    device: str = "",
    gender: str = "",
    ages: list = None
) -> pd.DataFrame:
    """
    네이버 데이터랩 통합 검색어 트렌드 API를 호출하여 데이터프레임으로 반환합니다.
    
    Args:
        keywords_list: 비교 분석할 키워드 목록 (예: ['아이폰', '갤럭시'])
        time_unit: 'date', 'week', 'month'
        device: 'pc', 'mo' (기본값은 전체)
        gender: 'm', 'f' (기본값은 전체)
        ages: 연령대 리스트 (예: ['1', '2', '3'])
    """
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = get_headers(client_id, client_secret)
    
    # 키워드별 그룹 구성 (검색어 트렌드는 키워드 그룹으로 요청함)
    keyword_groups = []
    for kw in keywords_list:
        keyword_groups.append({
            "groupName": kw,
            "keywords": [kw]
        })
        
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "keywordGroups": keyword_groups
    }
    
    if device:
        payload["device"] = device
    if gender:
        payload["gender"] = gender
    if ages:
        payload["ages"] = ages
        
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            # 여러 키워드 그룹의 데이터를 병합하여 데이터프레임 생성
            all_df = []
            for res in results:
                title = res.get("title")
                df_data = res.get("data", [])
                if df_data:
                    df = pd.DataFrame(df_data)
                    df["keyword"] = title
                    all_df.append(df)
            
            if all_df:
                final_df = pd.concat(all_df, ignore_index=True)
                final_df["period"] = pd.to_datetime(final_df["period"])
                return final_df
            return pd.DataFrame()
        else:
            response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"네이버 통합 검색어 트렌드 API 호출 중 에러가 발생했습니다: {str(e)}")

@st.cache_data(show_spinner=False)
def fetch_datalab_shopping_trend(
    client_id: str,
    client_secret: str,
    category_id: str,
    keywords_list: list,
    start_date: str,
    end_date: str,
    time_unit: str = "date",
    device: str = "",
    gender: str = "",
    ages: list = None
) -> pd.DataFrame:
    """
    네이버 데이터랩 쇼핑인사이트 키워드별 트렌드 API를 호출하여 데이터프레임으로 반환합니다.
    
    Args:
        category_id: 쇼핑 카테고리 코드 (예: 패션의류는 '50000000')
        keywords_list: 비교 분석할 쇼핑 키워드 목록
    """
    url = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"
    headers = get_headers(client_id, client_secret)
    
    keyword_payload = []
    for kw in keywords_list:
        keyword_payload.append({
            "name": kw,
            "param": [kw]
        })
        
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "timeUnit": time_unit,
        "category": category_id,
        "keyword": keyword_payload
    }
    
    if device:
        payload["device"] = device
    if gender:
        payload["gender"] = gender
    if ages:
        payload["ages"] = ages
        
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            all_df = []
            for res in results:
                title = res.get("title")
                df_data = res.get("data", [])
                if df_data:
                    df = pd.DataFrame(df_data)
                    df["keyword"] = title
                    all_df.append(df)
            
            if all_df:
                final_df = pd.concat(all_df, ignore_index=True)
                final_df["period"] = pd.to_datetime(final_df["period"])
                return final_df
            return pd.DataFrame()
        else:
            response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"네이버 쇼핑인사이트 API 호출 중 에러가 발생했습니다: {str(e)}")
