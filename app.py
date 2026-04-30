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
st.caption("바코드 / ME코드 통합 버전 (ver.260430)")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3045/3045670.png", width=100)
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

    # 🛡️ 2. Sales 시트 정리 (핵심: 바코드를 삭제하지 않고 살려둠!)
    if '제품코드' in sales_df.columns:
        sales_df.rename(columns={'제품코드': 'ME코드'}, inplace=True)
    if '바코드' not in sales_df.columns:
        sales_df['바코드'] = None
    # 바코드가 실수형(예: 880.0)으로 읽히는 것을 방지
    sales_df['바코드'] = sales_df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)

    # 🛡️ 3. RAW 시트 정리 (핵심: SKU ID를 바코드로 통일하고 살려둠!)
    if 'SKU ID' in raw_df.columns and '바코드' not in raw_df.columns:
        raw_df.rename(columns={'SKU ID': '바코드'}, inplace=True)
    if '바코드' not in raw_df.columns:
        raw_df['바코드'] = None
    raw_df['바코드'] = raw_df['바코드'].astype(str).str.replace(r'\.0$', '', regex=True)

    # 🛡️ 4. 물류센터 맵핑 및 XRV11(RC) 완벽 통합
    if '물류센터' in raw_df.columns:
        raw_df['물류센터'] = raw_df['물류센터'].astype(str).str.strip().str.upper()
        # XRV11이 들어간 건 무조건 XRC11로 강제 치환
        raw_df.loc[raw_df['물류센터'].str.contains('XRV11', na=False), '물류센터'] = 'XRC11'
        
        center_mapping = {
            'ECH4': '이천4', 'KKW3': '경기광주3', 'SIH2': '시흥2', 'YAS1': '양산1', 'GOY1':'고양1', 
            'GWJ2':'전라광주2', 'DAE3':'대구3', 'DON1':'동탄1', 'ECH2': '이천2', 'SEL1': '서울', 
            'DAE6': '대구6', 'DAEGU2': '대구2', 'CHW3': '창원3', 'XRC11': 'XRC11'
        }
        raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])
    else:
        raw_df['점포'] = '알수없음'

    # 🛡️ 5. ME코드 매핑 (참조표 기반)
    if len(me_ref_df.columns) >= 2:
        me_ref_df = me_ref_df.iloc[:, :2].copy()
        me_ref_df.columns = ['제품명', 'ME코드']
        me_mapping_table = me_ref_df[['제품명', 'ME코드']].drop_duplicates()
        if 'SKU명' in raw_df.columns:
            raw_df = pd.merge(raw_df, me_mapping_table, left_on='SKU명', right_on='제품명', how='left')
    
    if 'ME코드' not in raw_df.columns:
        raw_df['ME코드'] = None
    raw_df['ME코드'] = raw_df['ME코드'].fillna('미매핑(참조표확인)')

    # 🛡️ 6. 스마트 바코드 매핑 (A열, B열 순서 상관없이 자동 감지)
    if len(barcode_df.columns) >= 2:
        temp_df = barcode_df.iloc[:, :2].copy()
        col1, col2 = temp_df.columns[0], temp_df.columns[1]
        
        # 어느 열이 ME코드인지 자동 감지 ('ME'로 시작하는 데이터가 있는지 확인)
        if temp_df[col1].astype(str).str.contains('^ME', na=False, regex=True).any():
            temp_df.columns = ['ME코드_ref', '바코드_ref']
        else:
            temp_df.columns = ['바코드_ref', 'ME코드_ref']
            
        temp_df['바코드_ref'] = temp_df['바코드_ref'].astype(str).str.replace(r'\.0$', '', regex=True)
        ref_mapping = temp_df[['ME코드_ref', '바코드_ref']].drop_duplicates()
        
        # 원본 데이터에 바코드가 누락되어 있을 경우에만 매핑표에서 가져와서 채워넣음
        sales_df = pd.merge(sales_df, ref_mapping, left_on='ME코드', right_on='ME코드_ref', how='left')
        sales_df['바코드'] = sales_df['바코드'].replace('nan', None).fillna(sales_df['바코드_ref'])
        
        raw_df = pd.merge(raw_df, ref_mapping, left_on='ME코드', right_on='ME코드_ref', how='left')
        raw_df['바코드'] = raw_df['바코드'].replace('nan', None).fillna(raw_df['바코드_ref'])

    sales_df['바코드'] = sales_df['바코드'].replace('nan', None)
    raw_df['바코드'] = raw_df['바코드'].replace('nan', None)

    # 🛡️ 7. 통합키 생성 (무조건 바코드 우선, 없으면 ME코드)
    sales_df['통합키'] = sales_df['바코드'].fillna(sales_df['ME코드'])
    raw_df['통합키'] = raw_df['바코드'].fillna(raw_df['ME코드'])

    # 🛡️ 8. 데이터 그룹화 (다중 ME코드 -> 단일 바코드로 병합)
    sales_grouped = sales_df.groupby(['점포', '통합키'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    raw_grouped = raw_df.groupby(['점포', '통합키'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    # 🛡️ 9. 병합 및 차액 계산
    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', '통합키'], how='outer').fillna(0)
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    # 🛡️ 10. 대표 ME코드 복구 (정상적인 ME코드 하나만 가져옴)
    rep_me = pd.concat([sales_df[['통합키', 'ME코드']], raw_df[['통합키', 'ME코드']]])
    rep_me = rep_me[rep_me['ME코드'] != '미매핑(참조표확인)'].dropna(subset=['ME코드'])
    rep_me = rep_me.drop_duplicates(subset=['통합키'], keep='first')
    
    merged_df = pd.merge(merged_df, rep_me, on='통합키', how='left')
    merged_df['ME코드'] = merged_df['ME코드'].fillna('미매핑(참조표확인)')

    # 🛡️ 11. 비고 작성
    def analyze_difference(row):
        if str(row['ME코드']) == '미매핑(참조표확인)' and str(row['통합키']).startswith('ME'):
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
        
        with st.expander("🔍 데이터 필터링 옵션 열기", expanded=False):
            filter_option = st.radio("표시할 데이터를 선택하세요:", ["전체 보기", "차액 및 오류 발생 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 및 오류 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 정상 일치']

        # 색상 하이라이트 함수
        def highlight_diff(row):
            if row['비고'] == '❌ ME코드 누락': return ['background-color: #f2f2f2'] * len(row)
            elif row['비고'] == '🚨 수량 불일치': return ['background-color: #ffe6e6'] * len(row)
            elif row['비고'] == '⚠️ 단가 불일치': return ['background-color: #fff9e6'] * len(row)
            return [''] * len(row)

        format_dict = {
            '자사_출고수량': '{:,.0f}', '쿠팡_매입수량': '{:,.0f}', '수량_차액': '{:,.0f}',
            '자사_매출액': '{:,.0f}', '쿠팡_매입액': '{:,.0f}', '금액_차액': '{:,.0f}'
        }
        
        st.dataframe(
            display_df.style.apply(highlight_diff, axis=1).format(format_dict), 
            use_container_width=True,
            height=400 
        )

        st.divider()

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
    st.info("👈 왼쪽 사이드바에서 4개의 시트가 모두 포함된 통합 엑셀 파일을 업로드해주세요.")
    st.image("https://www.coupang.com/np/images/img_og_coupang.jpg", width=300)
