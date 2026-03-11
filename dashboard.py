import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import json
import numpy as np

# 페이지 설정
st.set_page_config(page_title="네모 상가 매물 프리미엄 대시보드", layout="wide")

# 역별 좌표 매핑 (서울 성동구 주요 역)
STATION_COORDS = {
    '성수역': [37.5445, 127.0560],
    '뚝섬역': [37.5471, 127.0474],
    '서울숲역': [37.5430, 127.0441],
    '한양대역': [37.5552, 127.0436],
    '왕십리역': [37.5612, 127.0384],
    '왕십리(성동구청)역': [37.5612, 127.0384],
    '마장역': [37.5661, 127.0428],
    '행당역': [37.5574, 127.0296],
    '신금호역': [37.5546, 127.0203],
    '금호역': [37.5481, 127.0157],
    '응봉역': [37.5501, 127.0348],
    '용답역': [37.5620, 127.0508],
    '상왕십리역': [37.5643, 127.0293]
}

# 데이터 로드 함수
@st.cache_data
def load_data():
    conn = sqlite3.connect("nemostore/data/nemostores.sqlite")
    query = "SELECT * FROM stores"
    df = pd.read_sql(query, conn)
    conn.close()
    
    # 층수 전처리
    def clean_floor(val):
        if pd.isna(val): return "기타"
        if val == 1: return "1층"
        if val > 1: return "상층"
        if val < 0: return "지하"
        return "기타"
    
    df['floor_cat'] = df['floor'].apply(clean_floor)
    
    # 역 이름 추출 및 좌표 추가
    def get_coords(station_str):
        if not station_str: return None, None
        station_name = station_str.split(',')[0].strip()
        if station_name in STATION_COORDS:
            return STATION_COORDS[station_name]
        return None, None

    coords = df['nearSubwayStation'].apply(get_coords)
    df['lat'] = coords.apply(lambda x: x[0] if x else None)
    df['lng'] = coords.apply(lambda x: x[1] if x else None)
    
    # 사진 URL 처리 (JSON 파싱)
    def parse_photos(url_str):
        try:
            urls = json.loads(url_str)
            return urls if isinstance(urls, list) else []
        except:
            return []
            
    df['photo_list'] = df['smallPhotoUrls'].apply(parse_photos)
    
    # 컬럼명 매핑 (한글로 변경)
    rename_dict = {
        'businessLargeCodeName': '업종_대',
        'businessMiddleCodeName': '업종_중',
        'priceTypeName': '거래형태',
        'deposit': '보증금_만원',
        'monthlyRent': '월세_만원',
        'premium': '권리금_만원',
        'maintenanceFee': '관리비_만원',
        'floor': '층',
        'size': '전용면적_m2',
        'title': '제목',
        'nearSubwayStation': '인근역',
        'viewCount': '조회수',
        'favoriteCount': '찜수',
        'createdDateUtc': '등록일'
    }
    df = df.rename(columns=rename_dict)
    
    return df

# 데이터 로드
df = load_data()

# 사이드바 설정
st.sidebar.header("🔍 상세 검색 필터")

# 1. 키워드 검색
search_query = st.sidebar.text_input("제목 또는 인근역 검색", "")

# 2. 업종 대분류 필터
business_large_categories = sorted(df['업종_대'].unique())
selected_large_categories = st.sidebar.multiselect("업종 대분류", business_large_categories, default=business_large_categories)

# 3. 가격 필터
min_deposit, max_deposit = int(df['보증금_만원'].min()), int(df['보증금_만원'].max())
deposit_range = st.sidebar.slider("보증금 범위 (만원)", min_deposit, max_deposit, (min_deposit, max_deposit))

min_rent, max_rent = int(df['월세_만원'].min()), int(df['월세_만원'].max())
rent_range = st.sidebar.slider("월세 범위 (만원)", min_rent, max_rent, (min_rent, max_rent))

# 데이터 필터링 수행
filtered_df = df[
    (df['제목'].str.contains(search_query, case=False, na=False) | df['인근역'].str.contains(search_query, case=False, na=False)) &
    (df['업종_대'].isin(selected_large_categories)) &
    (df['보증금_만원'].between(deposit_range[0], deposit_range[1])) &
    (df['월세_만원'].between(rent_range[0], rent_range[1]))
]

# 탭 구성
st.title("🏙️ 네모 상가 매물 데이터 센터")
tab1, tab2, tab3 = st.tabs(["🖼️ 이미지 갤러리", "🗺️ 지도 보기", "📊 시장 분석"])

# --- Tab 1: 이미지 갤러리 ---
with tab1:
    st.subheader("📸 매물 갤러리 뷰")
    if not filtered_df.empty:
        # 3열 레이아웃으로 이미지 카드 배치
        cols = st.columns(3)
        for idx, (i, row) in enumerate(filtered_df.iterrows()):
            with cols[idx % 3]:
                # 이미지 컨테이너
                img_url = row['previewPhotoUrl'] if pd.notna(row['previewPhotoUrl']) else "https://via.placeholder.com/300x200?text=No+Image"
                st.image(img_url, use_container_width=True)
                
                # 카드 텍스트 정보
                st.write(f"**{row['제목'][:30]}...**")
                st.caption(f"{row['인근역']} | {row['업종_중']}")
                st.write(f"보증금 {row['보증금_만원']:,} / 월세 {row['월세_만원']:,}")
                
                if st.button(f"상세 정보 보기 #{i}", key=f"det_{i}"):
                    st.session_state.selected_property_id = i
                    st.toast(f"'{row['제목']}' 매물이 선택되었습니다. 아래 상세 페이지에서 확인하세요.")
        
        st.divider()
        
        # 상세 페이지 (이미지 클릭/버튼 클릭 시 트리거되는 것처럼 구현)
        if 'selected_property_id' in st.session_state:
            pid = st.session_state.selected_property_id
            if pid in filtered_df.index:
                selected_row = filtered_df.loc[pid]
                st.subheader(f"✨ 상세 페이지: {selected_row['제목']}")
                
                det_col1, det_col2 = st.columns([2, 3])
                with det_col1:
                    # 갤러리 형태의 여러 사진 (smallPhotoUrls 활용)
                    if selected_row['photo_list']:
                        # Streamlit 기본 이미지 캡션 지원
                        st.image(selected_row['photo_list'], caption=[f"사진 {i+1}" for i in range(len(selected_row['photo_list']))], width=200)
                    else:
                        st.image(selected_row['previewPhotoUrl'], width=400)
                
                with det_col2:
                    st.success("##### 매물 요약 정보")
                    st.write(f"📍 **위치:** {selected_row['인근역']}")
                    st.write(f"🏢 **업종:** {selected_row['업종_대']} > {selected_row['업종_중']}")
                    st.write(f"💰 **가격:** 보증금 {selected_row['보증금_만원']:,} / 월세 {selected_row['월세_만원']:,} / 권리금 {selected_row['권리금_만원']:,} (만원)")
                    st.write(f"📐 **전용면적:** {selected_row['전용면적_m2']} m2")
                    st.write(f"📈 **인기도:** 조회수 {selected_row['조회수']:,} | 찜 {selected_row['찜수']:,}")
                    
                    # --- Benchmarking (상대적 가치 평가) ---
                    st.divider()
                    st.info("📊 **상대적 가치 평가 (Benchmarking)**")
                    
                    # 동일 역 주변 평균 월세와 비교
                    station_name = selected_row['인근역'].split(',')[0].strip()
                    avg_rent = df[df['인근역'].str.contains(station_name, na=False)]['월세_만원'].mean()
                    
                    if not pd.isna(avg_rent) and avg_rent > 0:
                        diff_pct = ((selected_row['월세_만원'] - avg_rent) / avg_rent) * 100
                        status = "비쌈" if diff_pct > 0 else "저렴"
                        st.metric(f"{station_name} 평균 대비 월세", f"{diff_pct:.1f}%", delta=f"{diff_pct:.1f}% ({status})", delta_color="inverse")
                    else:
                        st.write("지역 평균 데이터를 계산할 수 없습니다.")
    else:
        st.warning("검색 조건에 맞는 매물이 없습니다.")

# --- Tab 2: 지도 보기 ---
with tab2:
    st.subheader("📍 역세권 매물 밀집도")
    map_data = filtered_df.dropna(subset=['lat', 'lng'])
    if not map_data.empty:
        # 역별 매물 수 집계
        station_counts = map_data.groupby(['lat', 'lng', '인근역']).size().reset_index(name='매물수')
        
        fig = px.scatter_mapbox(
            station_counts, 
            lat="lat", 
            lon="lng", 
            size="매물수",
            color="매물수",
            hover_name="인근역",
            zoom=13,
            height=600,
            mapbox_style="carto-positron",
            title="성동구 주요 역세권 매물 분포"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("※ 정확한 좌표가 없는 매물은 역 위치를 기준으로 밀집도로 표시됩니다.")
    else:
        st.info("지도로 표시할 좌표 데이터가 없습니다.")

# --- Tab 3: 시장 분석 ---
with tab3:
    st.subheader("📉 지역 및 층별 통계 분석")
    analysis_col1, analysis_col2 = st.columns(2)
    
    with analysis_col1:
        st.write("### 층별 평균 월세 비교")
        floor_analysis = filtered_df.groupby('floor_cat')['월세_만원'].mean().reset_index()
        fig = px.bar(floor_analysis, x='floor_cat', y='월세_만원', color='floor_cat', title="층수(지하/1층/상층)별 임대료 현황")
        st.plotly_chart(fig, use_container_width=True)
        
    with analysis_col2:
        st.write("### 업종 대분류별 비중")
        large_biz_counts = filtered_df['업종_대'].value_counts()
        fig = px.pie(values=large_biz_counts.values, names=large_biz_counts.index, title="현재 검색 기준 업종 비중")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# 상세 리스트 (컬럼명 한글화 완성)
st.subheader("📋 전체 매물 상세 리스트")
display_cols = ['제목', '업종_대', '업종_중', '거래형태', '보증금_만원', '월세_만원', '권리금_만원', '인근역', '층', '전용면적_m2']
st.dataframe(filtered_df[display_cols], use_container_width=True)
