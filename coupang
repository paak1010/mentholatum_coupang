import streamlit as st
import pandas as pd
import io

# 페이지 설정
st.set_page_config(page_title="쿠팡 대사 대시보드", page_icon="📦", layout="wide")

st.title("🌿 멘소래담 쿠팡 매입/매출 차액 대사 대시보드")
st.markdown("자사 매출(Sales) 데이터와 쿠팡 매입(RAW) 데이터를 업로드하면 차액을 자동으로 계산합니다.")

# 사이드바: 파일 업로드
with st.sidebar:
    st.header("📂 데이터 업로드")
    sales_file = st.file_uploader("1. 자사 매출(Sales) CSV 업로드", type=['csv', 'xlsx'])
    raw_file = st.file_uploader("2. 쿠팡 매입(RAW) CSV 업로드", type=['csv', 'xlsx'])

# 데이터 처리 함수
@st.cache_data
def process_data(sales_df, raw_df):
    # 1. RAW 데이터의 물류센터 코드를 한글 점포명으로 매핑
    center_mapping = {
        'ECH4': '이천4',
        'KKW3': '경기광주3',
        'SIH2': '시흥2',
        'YAS1': '양산1'
    }
    raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])

    # 2. 데이터 그룹화
    # 자사 매출 데이터
    sales_grouped = sales_df.groupby(['점포', '제품코드'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'제품코드': 'ME코드', '수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    # 쿠팡 매입 데이터
    raw_grouped = raw_df.groupby(['점포', 'ME코드'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    # 3. 데이터 병합 (Outer Join)
    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', 'ME코드'], how='outer').fillna(0)

    # 4. 차액 계산
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    # 5. 비고 (차액 원인 분석)
    def analyze_difference(row):
        if row['수량_차액'] != 0:
            return '🚨 수량 불일치 (미입고 확인)'
        elif row['금액_차액'] != 0:
            return '⚠️ 단가 불일치 (단가/프로모션 확인)'
        else:
            return '✅ 일치'

    merged_df['비고'] = merged_df.apply(analyze_difference, axis=1)

    # 컬럼 정렬
    final_columns = ['점포', 'ME코드', '자사_출고수량', '쿠팡_매입수량', '수량_차액', '자사_매출액', '쿠팡_매입액', '금액_차액', '비고']
    return merged_df[final_columns]

# 엑셀 다운로드를 위한 버퍼 변환 함수
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='차액_대사_결과')
    processed_data = output.getvalue()
    return processed_data

# 메인 화면 로직
if sales_file and raw_file:
    try:
        # 파일 읽기 (CSV 처리)
        sales_df = pd.read_csv(sales_file)
        raw_df = pd.read_csv(raw_file)

        # 데이터 전처리 실행
        result_df = process_data(sales_df, raw_df)

        # 요약 지표 (KPI) 표시
        st.subheader("📊 대사 결과 요약")
        col1, col2, col3, col4 = st.columns(4)
        
        total_items = len(result_df)
        mismatch_qty = len(result_df[result_df['수량_차액'] != 0])
        mismatch_amt = len(result_df[(result_df['수량_차액'] == 0) & (result_df['금액_차액'] != 0)])
        perfect_match = len(result_df[result_df['비고'] == '✅ 일치'])

        col1.metric("전체 대사 건수", f"{total_items} 건")
        col2.metric("✅ 정상 일치", f"{perfect_match} 건")
        col3.metric("🚨 수량 불일치", f"{mismatch_qty} 건")
        col4.metric("⚠️ 단가 불일치", f"{mismatch_amt} 건")

        st.divider()

        # 데이터프레임 렌더링
        st.subheader("📝 세부 차액 내역")
        
        # 필터링 기능
        filter_option = st.radio("목록 필터링", ["전체 보기", "차액 발생 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 일치']

        # 하이라이팅 적용 (수량이나 금액에 차이가 있으면 행 색상 변경)
        def highlight_diff(row):
            if row['비고'] == '🚨 수량 불일치 (미입고 확인)':
                return ['background-color: #ffcccc'] * len(row)
            elif row['비고'] == '⚠️ 단가 불일치 (단가/프로모션 확인)':
                return ['background-color: #fff2cc'] * len(row)
            return [''] * len(row)

        st.dataframe(display_df.style.apply(highlight_diff, axis=1), use_container_width=True)

        # 엑셀 다운로드 버튼
        st.divider()
        st.subheader("📥 결과 다운로드")
        excel_data = to_excel(result_df)
        st.download_button(
            label="엑셀 파일로 다운로드 (.xlsx)",
            data=excel_data,
            file_name="쿠팡_차액대사_완성본.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다. 파일 형식을 확인해주세요. (에러: {e})")
else:
    st.info("👈 왼쪽 사이드바에서 자사 매출 데이터와 쿠팡 RAW 데이터를 모두 업로드해주세요.")
