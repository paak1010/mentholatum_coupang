import streamlit as st
import pandas as pd
import io

# 1. 페이지 기본 설정
st.set_page_config(page_title="쿠팡 매입 확인 시스템", page_icon="📦", layout="wide")

# 2. 커스텀 CSS
st.markdown("""
<style>
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
    h2, h3 { color: #2C3E50; }
</style>
""", unsafe_allow_html=True)

st.title("🚀 멘소래담 쿠팡 매입 확인 대시보드")
st.caption("바코드 / 특정 ME코드 / 점포 완벽 통합 버전 (ver.260506)")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3045/3045670.png", width=100)
    st.header("📂 데이터 업로드")
    uploaded_file = st.file_uploader("쿠팡 매입 확인 서식 (.xlsx)", type=['xlsx'])
    
    st.markdown("---")
    st.markdown("**✔사용방법**: 파일 마지막 시트 참고")
    st.caption("Developed by Jay")

@st.cache_data
def process_data(sales_df, raw_df, me_ref_df, barcode_df):
    sales_df.columns = sales_df.columns.astype(str).str.strip()
    raw_df.columns = raw_df.columns.astype(str).str.strip()
    sales_df = sales_df.loc[:, ~sales_df.columns.duplicated()].copy()
    raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()

    def clean_barcode(series):
        s = series.astype(str).str.replace(r'\.0$', '', regex=True)
        s = s.replace({'nan': None, 'None': None, '<NA>': None, '': None})
        return s

    if '제품코드' in sales_df.columns and 'ME코드' not in sales_df.columns:
        sales_df.rename(columns={'제품코드': 'ME코드'}, inplace=True)
    if '바코드' not in sales_df.columns:
        sales_df['바코드'] = None
    sales_df['바코드'] = clean_barcode(sales_df['바코드'])

    if 'SKU ID' in raw_df.columns and '바코드' not in raw_df.columns:
        raw_df.rename(columns={'SKU ID': '바코드'}, inplace=True)
    if '바코드' not in raw_df.columns:
        raw_df['바코드'] = None
    raw_df['바코드'] = clean_barcode(raw_df['바코드'])

    # Sales 시트 XRC11 점포 통합
    if '점포' in sales_df.columns:
        sales_df['점포'] = sales_df['점포'].astype(str).str.strip().str.upper()
        sales_df.loc[sales_df['점포'].str.contains('XRC11|XRV11', na=False, regex=True), '점포'] = 'XRC11'

    # RAW 시트 점포명 맵핑 및 XRC11 강제 통합
    if '물류센터' in raw_df.columns:
        raw_df['물류센터'] = raw_df['물류센터'].astype(str).str.strip().str.upper()
        raw_df.loc[raw_df['물류센터'].str.contains('XRC11|XRV11', na=False, regex=True), '물류센터'] = 'XRC11'
        
        center_mapping = {
            'ECH4': '이천4', 'KKW3': '경기광주3', 'SIH2': '시흥2', 'YAS1': '양산1', 'GOY1':'고양1', 
            'GWJ2':'전라광주2', 'DAE3':'대구3', 'DON1':'동탄1', 'ECH2': '이천2', 'SEL1': '서울', 
            'DAE6': '대구6', 'DAEGU2': '대구2', 'CHW3': '창원3', 'XRC11': 'XRC11', 'CHW4' : '창원4'
        }
        raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])
    else:
        raw_df['점포'] = '알수없음'

    if 'ME코드' not in raw_df.columns:
        raw_df['ME코드'] = None
        
    if 'SKU명' in raw_df.columns and len(me_ref_df.columns) >= 2:
        me_temp = me_ref_df.iloc[:, :2].copy()
        me_temp.columns = ['제품명', 'ME코드_ref']
        me_mapping = me_temp.dropna(subset=['ME코드_ref']).drop_duplicates('제품명')
        
        raw_df = pd.merge(raw_df, me_mapping, left_on='SKU명', right_on='제품명', how='left')
        raw_df['ME코드'] = raw_df['ME코드'].fillna(raw_df['ME코드_ref'])

    # ⭐ [수정된 부분] HLK -> HLM 강제 매핑 추가 ⭐
    force_me_mapping = {
        'ME90521MC4': 'ME81921CSA',
        'ME90621AC9': 'ME90621ACD',
        'ME00621A12': 'ME00621AMF',
        'ME90521KK1': 'ME90521GTC',
        'ME90621HLK': 'ME90621HLM'  # <- 요청하신 HLK 오류 해결을 위한 추가 매핑!
    }
    sales_df['ME코드'] = sales_df['ME코드'].replace(force_me_mapping)
    raw_df['ME코드'] = raw_df['ME코드'].replace(force_me_mapping)

    if len(barcode_df.columns) >= 2:
        bc_df = barcode_df.iloc[:, :2].copy()
        col1 = bc_df.columns[0]
        
        if bc_df[col1].astype(str).str.contains('^ME', na=False, regex=True).any():
            bc_df.columns = ['ME코드_ref', '바코드_ref']
        else:
            bc_df.columns = ['바코드_ref', 'ME코드_ref']
            
        bc_df['바코드_ref'] = clean_barcode(bc_df['바코드_ref'])
        bc_mapping = bc_df.dropna(subset=['ME코드_ref']).drop_duplicates('ME코드_ref')

        sales_df = pd.merge(sales_df, bc_mapping, left_on='ME코드', right_on='ME코드_ref', how='left')
        sales_df['바코드'] = sales_df['바코드'].fillna(sales_df['바코드_ref'])
        
        raw_df = pd.merge(raw_df, bc_mapping, left_on='ME코드', right_on='ME코드_ref', how='left')
        raw_df['바코드'] = raw_df['바코드'].fillna(raw_df['바코드_ref'])

    sales_df['통합키'] = sales_df['바코드'].fillna(sales_df['ME코드']).fillna('키없음')
    raw_df['통합키'] = raw_df['바코드'].fillna(raw_df['ME코드']).fillna('키없음')

    for col in ['수량', 'Total Amount']:
        if col not in sales_df.columns: sales_df[col] = 0
        sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0)
        
    for col in ['수량', '총공급가액']:
        if col not in raw_df.columns: raw_df[col] = 0
        raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

    sales_grouped = sales_df.groupby(['점포', '통합키'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    raw_grouped = raw_df.groupby(['점포', '통합키'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', '통합키'], how='outer').fillna(0)
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    rep_me = pd.concat([sales_df[['통합키', 'ME코드']], raw_df[['통합키', 'ME코드']]])
    rep_me = rep_me.dropna(subset=['ME코드']).drop_duplicates(subset=['통합키'], keep='first')
    
    merged_df = pd.merge(merged_df, rep_me, on='통합키', how='left')
    merged_df['ME코드'] = merged_df['ME코드'].fillna('미매핑(참조표확인)')

    def analyze_diff(row):
        if row['ME코드'] == '미매핑(참조표확인)' and str(row['통합키']).startswith('ME'):
            return '❌ ME코드 누락'
        elif row['수량_차액'] != 0:
            return '🚨 수량 불일치'
        elif row['금액_차액'] != 0:
            return '⚠️ 단가 불일치'
        else:
            return '✅ 정상 일치'

    merged_df['비고'] = merged_df.apply(analyze_diff, axis=1)
    
    final_cols = ['점포', '통합키', 'ME코드', '자사_출고수량', '쿠팡_매입수량', '수량_차액', '자사_매출액', '쿠팡_매입액', '금액_차액', '비고']
    merged_df = merged_df[final_cols].rename(columns={'통합키': '바코드(통합키)', 'ME코드': '대표 ME코드'})
    return merged_df

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='차액_대사_결과')
    return output.getvalue()

if uploaded_file:
    try:
        with st.spinner('📊 데이터 병합 및 차액 분석을 진행하고 있습니다...'):
            sales_df = pd.read_excel(uploaded_file, sheet_name='Sales Report (Coupang)')
            raw_df = pd.read_excel(uploaded_file, sheet_name='RAW')
            me_ref_df = pd.read_excel(uploaded_file, sheet_name='ME코드 참조')
            barcode_df = pd.read_excel(uploaded_file, sheet_name='바코드 참조')

            result_df = process_data(sales_df, raw_df, me_ref_df, barcode_df)
        
        st.toast('데이터 대사 작업이 완료되었습니다!', icon='🎉')

        st.subheader("📊 바코드 통합 대사 결과 요약")
        
        total_items = len(result_df)
        perfect_match = len(result_df[result_df['비고'] == '✅ 정상 일치'])
        mismatch_qty = len(result_df[result_df['비고'] == '🚨 수량 불일치'])
        mismatch_amt = len(result_df[result_df['비고'] == '⚠️ 단가 불일치'])
        missing_me = len(result_df[result_df['비고'] == '❌ ME코드 누락'])
        total_diff_amt = result_df['금액_차액'].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("전체 대사 건수", f"{total_items:,} 건")
        col2.metric("✅ 정상 일치", f"{perfect_match:,} 건")
        col3.metric("💰 총 금액 차이 (자사-쿠팡)", f"{total_diff_amt:,.0f} 원")

        st.markdown("<br>", unsafe_allow_html=True)
        
        col4, col5, col6 = st.columns(3)
        col4.metric("🚨 수량 불일치", f"{mismatch_qty:,} 건")
        col5.metric("⚠️ 단가 불일치", f"{mismatch_amt:,} 건")
        col6.metric("❌ 매핑 실패(누락)", f"{missing_me:,} 건")

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("📝 세부 차액 내역 데이터")
        
        with st.expander("🔍 데이터 필터링 옵션 열기", expanded=False):
            filter_option = st.radio("표시할 데이터를 선택하세요:", ["전체 보기", "차액 및 오류 발생 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 및 오류 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 정상 일치']

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
        st.error(f"🚨 데이터 처리 중 오류가 발생했습니다! (에러 내용: {e})")
else:
    st.info("👈 왼쪽 사이드바에서 4개의 시트가 모두 포함된 통합 엑셀 파일을 업로드해주세요.")
    st.image("https://www.coupang.com/np/images/img_og_coupang.jpg", width=300)
