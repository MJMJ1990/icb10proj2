"""
서울시 생활인구 Parquet 데이터를 가공하고 집계하여 SQLite 데이터베이스로 저장하는 사전 연산(Pre-computation) 프로그램입니다.

이 모듈은 대용량 원본 데이터에서 대시보드 시각화 및 지도 필터 연동에 필요한 모든 집계 데이터를 
미리 계산(Group By)하고 SQLite 데이터베이스의 고속 인덱싱 테이블로 적재합니다.
이를 통해 대시보드 구동 시의 메모리 점유율을 줄이고, 런타임 조회 속도를 극대화합니다.
"""

import os
import sqlite3
import pandas as pd
import numpy as np

def main():
    # 경로 정의
    parquet_path = "seoul-pops/data/LOCAL_PEOPLE_DONG_202606.parquet"
    excel_path = "seoul-pops/data/행정동코드_매핑정보_20241218.xlsx"
    db_path = "seoul-pops/data/seoul_pops_precomputed.db"
    
    # 기존 DB 파일 삭제 후 재생성 (갱신을 위해)
    if os.path.exists(db_path):
        os.remove(db_path)
        print("기존의 사전 계산 DB 파일을 삭제하였습니다.")

    print("1. 서울시 생활인구 원본 데이터 및 매핑 데이터 로드 중...")
    df = pd.read_parquet(parquet_path)
    df_excel = pd.read_excel(excel_path)
    
    print(f"원본 데이터 로드 완료. 데이터 크기: {len(df):,} 행")

    print("\n2. 매핑 데이터 가공 및 정제 중...")
    # 엑셀 매핑 파일에서 자치구명 및 행정동명 추출 (2번째 열: 코드, 1번째 열: 통계청코드, 4번째 열: 자치구, 5번째 열: 행정동)
    df_mapping = df_excel.iloc[:, [1, 0, 3, 4]].copy()
    df_mapping.columns = ['행정동코드', '통계청코드', '자치구명', '행정동명']
    
    # 쓰레기 데이터(영문 컬럼명) 정제
    df_mapping['행정동코드'] = pd.to_numeric(df_mapping['행정동코드'], errors='coerce')
    df_mapping['통계청코드'] = pd.to_numeric(df_mapping['통계청코드'], errors='coerce')
    df_mapping = df_mapping.dropna(subset=['행정동코드', '통계청코드'])
    
    # 타입 문자열로 통일
    df_mapping['행정동코드'] = df_mapping['행정동코드'].astype('int32').astype('str')
    df_mapping['통계청코드'] = df_mapping['통계청코드'].astype('int32').astype('str')
    df_mapping = df_mapping.drop_duplicates(subset=['행정동코드'])

    # Parquet 행정동코드도 문자열 변환 후 병합
    df['행정동코드'] = df['행정동코드'].astype('str')
    df = df.merge(df_mapping, on='행정동코드', how='left')
    df = df.dropna(subset=['행정동명'])

    # 요일 파생변수 생성
    date_series = pd.to_datetime(df['기준일ID'].astype(str), format='%Y%m%d')
    weekday_map = {
        'Monday': '월', 'Tuesday': '화', 'Wednesday': '수',
        'Thursday': '목', 'Friday': '금', 'Saturday': '토', 'Sunday': '일'
    }
    df['요일'] = date_series.dt.day_name().map(weekday_map)
    df['요일'] = pd.Categorical(df['요일'], categories=['월', '화', '수', '목', '금', '토', '일'], ordered=True)

    # 연령대 대분류 파생변수 생성
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

    print("\n3. SQLite 데이터베이스 커넥션 설정 중...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- 3.1. df_sample: 10만 행 무작위 샘플 (수치형 분포 및 개요 조회용) ---
    print("사전 적재 1: df_sample (10만 행 샘플) 생성 및 적재 중...")
    np.random.seed(42)
    sample_size = min(100000, len(df))
    df_sample = df.sample(n=sample_size, random_state=42).copy()
    
    # 카테고리 형식을 문자열로 변환하여 SQL 적재 호환성 유지
    df_sample['성별'] = df_sample['성별'].astype(str)
    df_sample['연령대'] = df_sample['연령대'].astype(str)
    df_sample['요일'] = df_sample['요일'].astype(str)
    df_sample['연령대_대분류'] = df_sample['연령대_대분류'].astype(str)
    
    df_sample.to_sql('df_sample', conn, if_exists='replace', index=False)

    # --- 3.2. daily_pop_trend: 일자별 합산 총생활인구수 (시계열 차트용) ---
    print("사전 적재 2: daily_pop_trend (일별 합계) 집계 및 적재 중...")
    daily_trend = df.groupby('기준일ID', observed=True)['총생활인구수'].sum().reset_index()
    daily_trend.to_sql('daily_pop_trend', conn, if_exists='replace', index=False)

    # --- 3.3. hourly_pop_trend: 시간대별 평균 총생활인구수 (시간대 차트용) ---
    print("사전 적재 3: hourly_pop_trend (시간대별 평균) 집계 및 적재 중...")
    hourly_trend = df.groupby('시간대구분', observed=True)['총생활인구수'].mean().reset_index()
    hourly_trend.to_sql('hourly_pop_trend', conn, if_exists='replace', index=False)

    # --- 3.4. gender_pop_mean: 성별 기술 통계 집계 (성별 차트용) ---
    print("사전 적재 4: gender_pop_mean (성별 기술통계) 집계 및 적재 중...")
    gender_stats = df.groupby('성별', observed=True)['생활인구수'].agg(['mean', 'std', 'max']).reset_index()
    gender_stats['성별'] = gender_stats['성별'].astype(str)
    gender_stats.to_sql('gender_pop_mean', conn, if_exists='replace', index=False)

    # --- 3.5. age_pop_mean: 연령대 대분류별 기술 통계 집계 (연령대 차트용) ---
    print("사전 적재 5: age_pop_mean (연령대별 기술통계) 집계 및 적재 중...")
    age_stats = df.groupby('연령대_대분류', observed=True)['생활인구수'].agg(['mean', 'std', 'median']).reset_index()
    age_stats['연령대_대분류'] = age_stats['연령대_대분류'].astype(str)
    age_stats.to_sql('age_pop_mean', conn, if_exists='replace', index=False)

    # --- 3.6. gender_age_heatmap: 성별 x 연령대별 평균 생활인구 (2D Heatmap 1용) ---
    print("사전 적재 6: gender_age_heatmap (성별x연령대 조합 평균) 집계 및 적재 중...")
    gender_age = df.groupby(['성별', '연령대'], observed=True)['생활인구수'].mean().reset_index()
    gender_age['성별'] = gender_age['성별'].astype(str)
    gender_age['연령대'] = gender_age['연령대'].astype(str)
    gender_age.to_sql('gender_age_heatmap', conn, if_exists='replace', index=False)

    # --- 3.7. weekday_hourly_heatmap: 요일 x 시간대별 평균 총생활인구 (2D Heatmap 2용) ---
    print("사전 적재 7: weekday_hourly_heatmap (요일x시간대 조합 평균) 집계 및 적재 중...")
    weekday_hourly = df.groupby(['요일', '시간대구분'], observed=True)['총생활인구수'].mean().reset_index()
    weekday_hourly['요일'] = weekday_hourly['요일'].astype(str)
    weekday_hourly.to_sql('weekday_hourly_heatmap', conn, if_exists='replace', index=False)

    # --- 3.8. map_municipalities_hourly: 시간대 x 요일 x 성별 x 구코드 다차원 집계 (구별 지도용) ---
    print("사전 적재 8: map_municipalities_hourly (구별 다차원 집계 큐브) 집계 및 적재 중...")
    df['구코드'] = df['통계청코드'].str[:5]
    map_muni = df.groupby(['시간대구분', '요일', '성별', '구코드', '자치구명'], observed=True)['생활인구수'].mean().reset_index()
    map_muni['요일'] = map_muni['요일'].astype(str)
    map_muni['성별'] = map_muni['성별'].astype(str)
    map_muni.to_sql('map_municipalities_hourly', conn, if_exists='replace', index=False)

    # --- 3.9. map_submunicipalities_hourly: 시간대 x 요일 x 성별 x 통계청코드 다차원 집계 (동별 지도용) ---
    print("사전 적재 9: map_submunicipalities_hourly (동별 다차원 집계 큐브) 집계 및 적재 중...")
    map_sub = df.groupby(['시간대구분', '요일', '성별', '통계청코드', '행정동명'], observed=True)['생활인구수'].mean().reset_index()
    map_sub['요일'] = map_sub['요일'].astype(str)
    map_sub['성별'] = map_sub['성별'].astype(str)
    map_sub.to_sql('map_submunicipalities_hourly', conn, if_exists='replace', index=False)

    # --- 3.10. filter_metadata: 자치구 및 행정동 필터 메타데이터 (사이드바 고속 렌더링용) ---
    print("사전 적재 10: filter_metadata (필터용 행정구역 메타데이터) 집계 및 적재 중...")
    filter_meta = df[['자치구명', '행정동명']].drop_duplicates().reset_index(drop=True)
    filter_meta.to_sql('filter_metadata', conn, if_exists='replace', index=False)

    # --- 4. 데이터베이스 인덱스 설정 (조회 쿼리 획기적 최적화) ---
    print("\n4. SQLite 인덱싱 설정 중 (고속 검색 튜닝)...")
    # 지도 시각화 쿼리는 (시간대, 요일, 성별)을 복합적으로 조회하므로 다차원 인덱스 필수 지정
    cursor.execute("CREATE INDEX idx_muni_filters ON map_municipalities_hourly (시간대구분, 요일, 성별);")
    cursor.execute("CREATE INDEX idx_sub_filters ON map_submunicipalities_hourly (시간대구분, 요일, 성별);")
    cursor.execute("CREATE INDEX idx_meta ON filter_metadata (자치구명);")
    conn.commit()

    # DB 용량 최적화 (진공 청소 연산)
    cursor.execute("VACUUM;")
    conn.commit()
    conn.close()

    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"\n==============================================")
    print(f" [사전 계산 완료] SQLite 데이터베이스 구축 완료!")
    print(f" 저장 경로: {db_path} ({db_size_mb:.2f} MB)")
    print(f"==============================================")

if __name__ == '__main__':
    main()
