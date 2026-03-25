import streamlit as st
import pandas as pd
import io

# 1. 페이지 기본 설정 (가장 먼저 와야 함)
st.set_page_config(page_title="쿠팡 매입 확인 시스템", page_icon="📦", layout="wide")

# 2. 커스텀 CSS 디자인 주입
st.markdown("""
<style>
    /* 상단 요약(Metric) 카드 스타일링 */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px);
        box-shadow: 2px 5px 15px rgba(0,0,0,0.1);
    }
    /* 다운로드 버튼 스타일링 */
    .stDownloadButton button {
        background-color: #4CAF50 !important;
        color: white !important;
        font-weight: bold;
        border-radius: 8px;
        border: none;
    }
    .stDownloadButton button:hover {
        background-color: #45a049 !important;
    }
    /* 서브헤더 텍스트 색상 포인트 */
    h2, h3 {
        color: #2C3E50;
    }
</style>
""", unsafe_allow_html=True)

# 메인 타이틀
st.title("🚀 멘소래담 쿠팡 매입 확인 대시보드")
st.caption("바코드 / ME코드 통합 버전 (ver.260325)")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3045/3045670.png", width=100) # 귀여운 박스 아이콘 (선택 사항)
    st.header("📂 데이터 업로드")
    uploaded_file = st.file_uploader("쿠팡 매입 확인 서식 (.xlsx)", type=['xlsx'])
    
    st.markdown("---")
    st.markdown("""
    **✔사용방법**
    : 파일 마지막 시트 참고   """)
    st.caption("Developed by Jay")

@st.cache_data
def process_data(sales_df, raw_df, me_ref_df, barcode_df):
    # 🛡️ 1. 컬럼명 공백 제거 및 중복 삭제
    sales_df.columns = sales_df.columns.astype(str).str.strip()
    raw_df.columns = raw_df.columns.astype(str).str.strip()
    sales_df = sales_df.loc[:, ~sales_df.columns.duplicated()].copy()
    raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()

    # 🛡️ 2. Sales 시트 정리
    if '바코드' in sales_df.columns:
        sales_df = sales_df.drop(columns=['바코드'])
    if '제품코드' in sales_df.columns:
        if 'ME코드' in sales_df.columns:
            sales_df = sales_df.drop(columns=['ME코드'])
        sales_df.rename(columns={'제품코드': 'ME코드'}, inplace=True)

    # 🛡️ 3. RAW 시트 정리
    if '바코드' in raw_df.columns:
        raw_df = raw_df.drop(columns=['바코드'])
    if 'ME코드' in raw_df.columns:
        raw_df = raw_df.drop(columns=['ME코드'])

    # 4. ME코드 참조 시트 덮어쓰기
    if len(me_ref_df.columns) >= 2:
        me_ref_df = me_ref_df.iloc[:, :2].copy()
        me_ref_df.columns = ['제품명', 'ME코드']
        me_ref_df = me_ref_df[me_ref_df['ME코드'].astype(str).str.startswith('ME', na=False)]
        me_mapping_table = me_ref_df[['제품명', 'ME코드']].drop_duplicates()
    else:
        me_mapping_table = pd.DataFrame(columns=['제품명', 'ME코드'])

    # 5. RAW 데이터 센터명 변환 및 ME코드 매핑
    center_mapping = {'ECH4': '이천4', 'KKW3': '경기광주3', 'SIH2': '시흥2', 'YAS1': '양산1', 'GOY1':'고양1', 'GWJ2':'전라광주2',
                      'DAE3':'대구3', 'DON1':'동탄1', 'XRC11':'XRC11(RC)', 'ECH2' : '이천2'}
    if '물류센터' in raw_df.columns:
        raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])
    else:
        raw_df['점포'] = '알수없음'

    if 'SKU명' in raw_df.columns:
        raw_df = pd.merge(raw_df, me_mapping_table, left_on='SKU명', right_on='제품명', how='left')
    else:
        raw_df['ME코드'] = None
    raw_df['ME코드'] = raw_df['ME코드'].fillna('미매핑(참조표확인)')

    # 6. 바코드 결합
    if len(barcode_df.columns) >= 2:
        barcode_df = barcode_df.iloc[:, :2].copy()
        barcode_df.columns = ['ME코드', '바코드']
        barcode_df = barcode_df[barcode_df['ME코드'].astype(str).str.startswith('ME', na=False)]
        barcode_mapping = barcode_df[['ME코드', '바코드']].drop_duplicates()
    else:
        barcode_mapping = pd.DataFrame(columns=['ME코드', '바코드'])
    
    sales_df = pd.merge(sales_df, barcode_mapping, on='ME코드', how='left')
    raw_df = pd.merge(raw_df, barcode_mapping, on='ME코드', how='left')

    sales_df['통합키'] = sales_df['바코드'].fillna(sales_df['ME코드'])
    raw_df['통합키'] = raw_df['바코드'].fillna(raw_df['ME코드'])

    # 7. 데이터 그룹화
    sales_grouped = sales_df.groupby(['점포', '통합키'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    raw_grouped = raw_df.groupby(['점포', '통합키'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    # 8. 병합 및 차액 계산
    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', '통합키'], how='outer').fillna(0)
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    # 9. 대표 ME코드 복구
    rep_me_mapping = pd.concat([sales_df[['통합키', 'ME코드']], raw_df[['통합키', 'ME코드']]]).drop_duplicates(subset=['통합키'], keep='first')
    merged_df = pd.merge(merged_df, rep_me_mapping, on='통합키', how='left')

    # 10. 비고 작성
    def analyze_difference(row):
        if str(row['ME코드']) == '미매핑(참조표확인)':
            return '❌ ME코드 누락'
        elif row['수량_차액'] != 0:
            return '🚨 수량 불일치'
        elif row['금액_차액'] != 0:
            return '⚠️ 단가 불일치'
        else:
            return '✅ 정상 일치'

    merged_df['비고'] = merged_df.apply(analyze_difference, axis=1)

    final_columns = ['점포', '통합키', 'ME코드', '자사_출고수량', '쿠팡_매입수량', '수량_차액', '자사_매출액', '쿠팡_매입액', '금액_차액', '비고']
    merged_df = merged_df[final_columns].rename(columns={'통합키': '바코드(통합키)', 'ME코드': '대표 ME코드'})
    return merged_df

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='차액_대사_결과')
    return output.getvalue()

# 메인 화면 로직
if uploaded_file:
    try:
        with st.spinner('📊 데이터 병합 및 차액 분석을 진행하고 있습니다...'):
            sales_df = pd.read_excel(uploaded_file, sheet_name='Sales Report (Coupang)')
            raw_df = pd.read_excel(uploaded_file, sheet_name='RAW')
            me_ref_df = pd.read_excel(uploaded_file, sheet_name='ME코드 참조')
            barcode_df = pd.read_excel(uploaded_file, sheet_name='바코드 참조')

            # 전처리 실행
            result_df = process_data(sales_df, raw_df, me_ref_df, barcode_df)
        
        # 분석 완료 알림 팝업
        st.toast('데이터 대사 작업이 완료되었습니다!', icon='🎉')

        st.subheader("📊 바코드 통합 대사 결과 요약")
        total_items = len(result_df)
        perfect_match = len(result_df[result_df['비고'] == '✅ 정상 일치'])
        mismatch_qty = len(result_df[result_df['비고'] == '🚨 수량 불일치'])
        mismatch_amt = len(result_df[result_df['비고'] == '⚠️ 단가 불일치'])
        missing_me = len(result_df[result_df['비고'] == '❌ ME코드 누락'])

        # 메트릭 카드 5분할 레이아웃
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("전체 대사 건수", f"{total_items:,} 건")
        col2.metric("✅ 정상 일치", f"{perfect_match:,} 건")
        col3.metric("🚨 수량 차이 발생", f"{mismatch_qty:,} 건")
        col4.metric("⚠️ 단가 차이 발생", f"{mismatch_amt:,} 건")
        col5.metric("❌ 매핑 실패(누락)", f"{missing_me:,} 건")

        st.markdown("<br>", unsafe_allow_html=True) # 여백 추가

        # 세부 내역 섹션
        st.subheader("📝 세부 차액 내역 데이터")
        
        # 필터링 옵션을 Expander(접기/펴기) 안에 넣어서 깔끔하게 정리
        with st.expander("🔍 데이터 필터링 옵션 열기", expanded=False):
            filter_option = st.radio("표시할 데이터를 선택하세요:", ["전체 보기", "차액 및 오류 발생 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 및 오류 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 정상 일치']

        # 색상 하이라이트 함수
        def highlight_diff(row):
            if row['비고'] == '❌ ME코드 누락': return ['background-color: #f2f2f2'] * len(row)
            elif row['비고'] == '🚨 수량 불일치': return ['background-color: #ffe6e6'] * len(row) # 연한 빨강
            elif row['비고'] == '⚠️ 단가 불일치': return ['background-color: #fff9e6'] * len(row) # 연한 노랑
            return [''] * len(row)

        # 데이터 프레임 출력 시 숫자 천단위 콤마 포맷팅 적용
        format_dict = {
            '자사_출고수량': '{:,.0f}', '쿠팡_매입수량': '{:,.0f}', '수량_차액': '{:,.0f}',
            '자사_매출액': '{:,.0f}', '쿠팡_매입액': '{:,.0f}', '금액_차액': '{:,.0f}'
        }
        
        st.dataframe(
            display_df.style.apply(highlight_diff, axis=1).format(format_dict), 
            use_container_width=True,
            height=400 # 스크롤 박스 높이 지정
        )

        st.divider()

        # 다운로드 섹션을 컬럼으로 나눠서 우측 정렬된 느낌 주기
        down_col1, down_col2 = st.columns([3, 1])
        with down_col1:
            st.markdown("##### 📥 최종 결과 다운로드")
            st.info("오류가 발생한 항목들은 다운로드 된 엑셀 파일에서 필터를 걸어 확인해보세요.")
        with down_col2:
            st.download_button(
                label="엑셀 파일 다운로드 (.xlsx) ⬇️",
                data=to_excel(result_df),
                file_name="쿠팡_차액대사_완성본(바코드통합).xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다. (에러 원인: {e})")
else:
    # 업로드 전 보여주는 대기 화면 플레이스홀더
    st.info("👈 왼쪽 사이드바에서 4개의 시트가 모두 포함된 통합 엑셀 파일을 업로드해주세요.")
    st.image("https://www.coupang.com/np/images/img_og_coupang.jpg", width=300) # 쿠팡 관련 썸네일 예시
