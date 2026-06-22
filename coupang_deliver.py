import streamlit as st
import pandas as pd
import io

# 1. 페이지 기본 설정 (가장 가벼운 세팅)
st.set_page_config(page_title="쿠팡 매입 확인 시스템", page_icon="📦", layout="wide")

# 2. 커스텀 CSS (사이드바 흰색 배경 & 디자인 적용)
st.markdown("""
<style>
    /* 기존 카드 디자인 유지 */
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
    /* 버튼 디자인 유지 */
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
    
    /* ⭐ 사이드바 배경을 무조건 흰색으로 덮어버림 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 멘소래담 쿠팡 매입 대시보드")
st.caption("로고 패치 및 서버 다운(메모리 초과) 방지 적용 버전")

with st.sidebar:
    # ⭐ 이모티콘 대신 멘소래담 로고 이미지 적용
    st.image("logo.png", width=180) 
    
    st.header("📂 데이터 업로드")
    uploaded_file = st.file_uploader("쿠팡 매입 확인 서식 (.xlsx)", type=['xlsx'])
    
    st.markdown("---")
    st.markdown("**✔사용방법**: 파일 마지막 시트 참고")
    st.caption("Developed by Jay")

# 메모리 초과를 막기 위해 @st.cache_data를 제거했습니다.
def process_data(sales_df, raw_df, me_ref_df, barcode_df):
    sales_df.columns = sales_df.columns.astype(str).str.strip()
    raw_df.columns = raw_df.columns.astype(str).str.strip()
    sales_df = sales_df.loc[:, ~sales_df.columns.duplicated()].copy()
    raw_df = raw_df.loc[:, ~raw_df.columns.duplicated()].copy()

    def clean_barcode(series):
        s = series.astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        s = s.replace({'nan': None, 'None': None, '<NA>': None, '': None, '(비어 있음)': None})
        return s

    if '제품코드' in sales_df.columns and 'ME코드' not in sales_df.columns:
        sales_df.rename(columns={'제품코드': 'ME코드'}, inplace=True)
    if '바코드' not in sales_df.columns:
        sales_df['바코드'] = None
    sales_df['바코드'] = clean_barcode(sales_df['바코드'])

    if '바코드' not in raw_df.columns:
        raw_df['바코드'] = None
    raw_df['바코드'] = clean_barcode(raw_df['바코드'])

    if '점포' in sales_df.columns:
        sales_df['점포'] = sales_df['점포'].astype(str).str.strip().str.upper()
        sales_df.loc[sales_df['점포'].str.contains('XRC11|XRV11', na=False, regex=True), '점포'] = 'XRC11'

    if '물류센터' in raw_df.columns:
        raw_df['물류센터'] = raw_df['물류센터'].astype(str).str.strip().str.upper()
        raw_df.loc[raw_df['물류센터'].str.contains('XRC11|XRV11', na=False, regex=True), '물류센터'] = 'XRC11'
        
        center_mapping = {
            'ECH4': '이천4', 'KKW3': '경기광주3', 'SIH2': '시흥2', 'YAS1': '양산1', 'GOY1':'고양1', 
            'GWJ2':'전라광주2', 'DAE3':'대구3', 'DON1':'동탄1', 'ECH2': '이천2', 'SEL1': '서울', 
            'DAE6': '대구6', 'DAEGU2': '대구2', 'CHW3': '창원3', 'XRC11': 'XRC11', 'CHW4' : '창원4', 'SAN3' : '안산3', 'CHW1' : '창원1'
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

    force_me_mapping = {
        'ME90521MC4': 'ME81921CSA', 'ME90621AC9': 'ME90621ACD', 'ME00621A12': 'ME00621AMF',
        'ME90521KK1': 'ME90521GTC', 'ME90621HLK': 'ME90621HLM', 'ME00621ASE': 'ME00621ASF' 
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

    sales_df['통합키'] = sales_df['바코드'].fillna(sales_df['ME코드']).fillna('키없음').astype(str).str.strip()
    raw_df['통합키'] = raw_df['바코드'].fillna(raw_df['ME코드']).fillna('키없음').astype(str).str.strip()

    for col in ['수량', 'Total Amount']:
        if col not in sales_df.columns: sales_df[col] = 0
        sales_df[col] = sales_df[col].astype(str).str.replace(',', '', regex=False)
        sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0)
        
    for col in ['수량', '총공급가액']:
        if col not in raw_df.columns: raw_df[col] = 0
        raw_df[col] = raw_df[col].astype(str).str.replace(',', '', regex=False)
        raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

    sales_grouped = sales_df.groupby(['점포', '통합키'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    raw_grouped = raw_df.groupby(['점포', '통합키'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', '통합키'], how='outer').fillna(0)
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    rep_me = pd.concat([sales_df[['통합키', 'ME코드']], raw_df[['통합키', 'ME코드']]])
    rep_me = rep_me.dropna(subset=['ME코드'])
    rep_me['ME코드'] = rep_me['ME코드'].astype(str)
    rep_me = rep_me.groupby('통합키')['ME코드'].apply(lambda x: ', '.join(pd.unique(x))).reset_index()
    
    merged_df = pd.merge(merged_df, rep_me, on='통합키', how='left')
    merged_df['ME코드'] = merged_df['ME코드'].fillna('미매핑(참조표확인)')

    def analyze_diff(row):
        if row['ME코드'] == '미매핑(참조표확인)' and str(row['통합키']).startswith('ME'): return '❌ ME코드 누락'
        elif row['수량_차액'] != 0: return '🚨 수량 불일치'
        elif row['금액_차액'] != 0: return '⚠️ 단가 불일치'
        else: return '✅ 정상 일치'

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
        with st.spinner('📊 데이터를 분석 중입니다. 파일 크기에 따라 수십 초 정도 소요될 수 있습니다...'):
            # ⭐ 핵심 안전 장치: 파일 버퍼를 안전한 메모리 공간(BytesIO)으로 복사하여 읽기
            file_bytes = io.BytesIO(uploaded_file.getvalue())
            xls = pd.ExcelFile(file_bytes)
            
            sales_df = pd.read_excel(xls, sheet_name='Sales Report (Coupang)')
            raw_df = pd.read_excel(xls, sheet_name='RAW')
            me_ref_df = pd.read_excel(xls, sheet_name='ME코드 참조')
            barcode_df = pd.read_excel(xls, sheet_name='바코드 참조')

            result_df = process_data(sales_df, raw_df, me_ref_df, barcode_df)
        
        st.success('데이터 대사 작업이 완료되었습니다!')

        # 요약 지표 출력 (CSS 없이 기본 기능으로만)
        st.subheader("📊 대사 결과 요약")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("전체 건수", f"{len(result_df):,} 건")
        c2.metric("정상 일치", f"{len(result_df[result_df['비고'] == '✅ 정상 일치']):,} 건")
        c3.metric("수량/단가 불일치", f"{len(result_df[result_df['비고'].isin(['🚨 수량 불일치', '⚠️ 단가 불일치'])]):,} 건")
        c4.metric("총 금액 차이", f"{result_df['금액_차액'].sum():,.0f} 원")

        # 데이터 프레임 출력 (스타일링 최소화로 렌더링 부하 방지)
        st.subheader("📝 세부 차액 내역 데이터")
        filter_option = st.radio("표시 필터:", ["전체 보기", "차액 및 오류 건만 보기"], horizontal=True)
        
        display_df = result_df if filter_option == "전체 보기" else result_df[result_df['비고'] != '✅ 정상 일치']
        st.dataframe(display_df, use_container_width=True, height=400)

        # 엑셀 다운로드
        st.download_button(
            label="엑셀 파일 다운로드 (.xlsx) ⬇️",
            data=to_excel(result_df),
            file_name="쿠팡_대사결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    except ValueError as ve:
        st.error(f"엑셀 시트 이름이 맞는지 확인해주세요. (에러: {ve})")
    except MemoryError:
        st.error("🚨 엑셀 파일 용량이 너무 커서 서버 메모리가 초과되었습니다. 데이터를 나누어 올려주세요.")
    except Exception as e:
        st.error(f"🚨 알 수 없는 오류가 발생했습니다: {e}")
else:
    st.info("👈 엑셀 파일을 업로드해주세요.")
