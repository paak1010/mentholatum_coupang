import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="쿠팡 대사 대시보드", page_icon="📦", layout="wide")

st.title("🌿 멘소래담 쿠팡 매입/매출 차액 대사 대시보드 (바코드 통합 버전)")
st.markdown("**'쿠팡 매입 확인 서식' 엑셀 파일 하나만 업로드**하면, 내부 시트를 분석하고 동일 바코드 상품을 자동으로 묶어서 차액을 계산합니다.")

with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded_file = st.file_uploader("쿠팡 매입 확인 서식 엑셀 파일 업로드 (.xlsx)", type=['xlsx'])

@st.cache_data
def process_data(sales_df, raw_df, me_ref_df, barcode_df):
    # 1. RAW 데이터 물류센터명 한글 변환
    center_mapping = {'ECH4': '이천4', 'KKW3': '경기광주3', 'SIH2': '시흥2', 'YAS1': '양산1'}
    raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])

    # 2. RAW에 ME코드 1차 매핑 (제품명 기준)
    me_mapping_table = me_ref_df[['제품명', 'ME코드']].drop_duplicates()
    if 'ME코드' in raw_df.columns:
        raw_df = raw_df.drop(columns=['ME코드'])
    raw_df = pd.merge(raw_df, me_mapping_table, left_on='SKU명', right_on='제품명', how='left')
    raw_df['ME코드'] = raw_df['ME코드'].fillna('미매핑(참조표확인)')

    # Sales 데이터 컬럼명 통일
    sales_df.rename(columns={'제품코드': 'ME코드'}, inplace=True)

    # 3. 바코드 기준으로 동일 상품 묶기 (에러 방어 로직 추가 🛡️)
    # 엑셀 상단에 빈 줄이 있거나 컬럼명이 '상품코드' 등 다른 이름이어도 무조건 돌아가게 만듭니다.
    barcode_df = barcode_df.iloc[:, :2] # 무조건 엑셀의 첫 번째(A), 두 번째(B) 열만 가져오기
    barcode_df.columns = ['ME코드', '바코드'] # 파이썬이 찾을 수 있게 강제로 이름 덮어쓰기
    
    # ME코드가 실제로 'ME'로 시작하는 찐 데이터 행만 남기기 (빈 줄이나 '상품코드' 같은 한글 제목 찌꺼기 자동 삭제)
    barcode_df = barcode_df[barcode_df['ME코드'].astype(str).str.startswith('ME', na=False)]
    
    barcode_mapping = barcode_df[['ME코드', '바코드']].drop_duplicates()
    
    # Sales와 RAW 데이터에 각각 바코드 붙이기
    sales_df = pd.merge(sales_df, barcode_mapping, on='ME코드', how='left')
    raw_df = pd.merge(raw_df, barcode_mapping, on='ME코드', how='left')

    # [통합키 생성] 바코드가 등록되어 있으면 '바코드'를, 없으면 기존 'ME코드'를 통합키로 사용
    sales_df['통합키'] = sales_df['바코드'].fillna(sales_df['ME코드'])
    raw_df['통합키'] = raw_df['바코드'].fillna(raw_df['ME코드'])

    # 4. 데이터 그룹화 (ME코드가 아닌 '통합키(바코드)' 기준으로 수량/금액 합산)
    sales_grouped = sales_df.groupby(['점포', '통합키'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    raw_grouped = raw_df.groupby(['점포', '통합키'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    # 5. 병합 및 차액 계산
    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', '통합키'], how='outer').fillna(0)
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    # 6. 결과창에 보여줄 '대표 ME코드' 하나 가져오기
    rep_me_mapping = pd.concat([sales_df[['통합키', 'ME코드']], raw_df[['통합키', 'ME코드']]]).drop_duplicates(subset=['통합키'], keep='first')
    merged_df = pd.merge(merged_df, rep_me_mapping, on='통합키', how='left')

    # 7. 비고 작성
    def analyze_difference(row):
        if row['ME코드'] == '미매핑(참조표확인)':
            return '❌ ME코드 누락 (참조표 확인)'
        elif row['수량_차액'] != 0:
            return '🚨 수량 불일치'
        elif row['금액_차액'] != 0:
            return '⚠️ 단가 불일치'
        else:
            return '✅ 일치'

    merged_df['비고'] = merged_df.apply(analyze_difference, axis=1)

    # 컬럼 보기 좋게 정렬 (통합키=바코드 포함)
    final_columns = ['점포', '통합키', 'ME코드', '자사_출고수량', '쿠팡_매입수량', '수량_차액', '자사_매출액', '쿠팡_매입액', '금액_차액', '비고']
    merged_df = merged_df[final_columns].rename(columns={'통합키': '바코드(통합키)', 'ME코드': '대표 ME코드'})
    return merged_df

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='차액_대사_결과')
    return output.getvalue()

if uploaded_file:
    try:
        with st.spinner('엑셀 파일 내 4개의 시트를 분석하여 바코드 기준으로 병합 중입니다...'):
            sales_df = pd.read_excel(uploaded_file, sheet_name='Sales Report (Coupang)')
            raw_df = pd.read_excel(uploaded_file, sheet_name='RAW')
            me_ref_df = pd.read_excel(uploaded_file, sheet_name='ME코드 참조')
            barcode_df = pd.read_excel(uploaded_file, sheet_name='바코드 참조')

            # 전처리 실행
            result_df = process_data(sales_df, raw_df, me_ref_df, barcode_df)

        st.subheader("📊 바코드 통합 대사 결과 요약")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_items = len(result_df)
        perfect_match = len(result_df[result_df['비고'] == '✅ 일치'])
        mismatch_qty = len(result_df[result_df['비고'] == '🚨 수량 불일치'])
        mismatch_amt = len(result_df[result_df['비고'] == '⚠️ 단가 불일치'])
        missing_me = len(result_df[result_df['비고'] == '❌ ME코드 누락 (참조표 확인)'])

        col1.metric("통합 대사 건수", f"{total_items} 건")
        col2.metric("✅ 정상 일치", f"{perfect_match} 건")
        col3.metric("🚨 수량 차이", f"{mismatch_qty} 건")
        col4.metric("⚠️ 단가 차이", f"{mismatch_amt} 건")
        col5.metric("❌ 매핑 실패", f"{missing_me} 건")

        st.divider()

        st.subheader("📝 세부 차액 내역")
        filter_option = st.radio("목록 필터링", ["전체 보기", "차액 및 오류 발생 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 및 오류 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 일치']

        def highlight_diff(row):
            if row['비고'] == '❌ ME코드 누락 (참조표 확인)': return ['background-color: #e0e0e0'] * len(row)
            elif row['비고'] == '🚨 수량 불일치': return ['background-color: #ffcccc'] * len(row)
            elif row['비고'] == '⚠️ 단가 불일치': return ['background-color: #fff2cc'] * len(row)
            return [''] * len(row)

        st.dataframe(display_df.style.apply(highlight_diff, axis=1), use_container_width=True)

        st.divider()
        st.subheader("📥 결과 다운로드")
        st.download_button(
            label="엑셀 파일로 다운로드 (.xlsx)",
            data=to_excel(result_df),
            file_name="쿠팡_차액대사_완성본(바코드통합).xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다. (에러: {e})")
else:
    st.info("👈 왼쪽 사이드바에서 [바코드 참조] 시트가 포함된 통합 엑셀 파일을 업로드해주세요.")
