import streamlit as st
import pandas as pd
import io

# 페이지 설정
st.set_page_config(page_title="쿠팡 대사 대시보드", page_icon="📦", layout="wide")

st.title("🌿 멘소래담 쿠팡 매입/매출 차액 대사 대시보드")
st.markdown("**'쿠팡 매입 확인 서식' 엑셀 파일 하나만 업로드**하면, 내부 시트를 자동으로 분석해 차액을 계산합니다.")

# 사이드바: 엑셀 파일 1개만 업로드
with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded_file = st.file_uploader("쿠팡 매입 확인 서식 엑셀 파일 업로드 (.xlsx)", type=['xlsx'])

# 데이터 처리 함수
@st.cache_data
def process_data(sales_df, raw_df, me_ref_df):
    # 1. RAW 데이터의 물류센터 코드를 한글 점포명으로 매핑
    center_mapping = {
        'ECH4': '이천4',
        'KKW3': '경기광주3',
        'SIH2': '시흥2',
        'YAS1': '양산1'
    }
    raw_df['점포'] = raw_df['물류센터'].map(center_mapping).fillna(raw_df['물류센터'])

    # 2. RAW 데이터에 ME코드 자동 매핑 (엑셀의 VLOOKUP 역할)
    # ME코드 참조표에서 '제품명'과 'ME코드'만 가져와서 중복 제거
    me_mapping_table = me_ref_df[['제품명', 'ME코드']].drop_duplicates()
    
    # RAW에 이미 'ME코드' 열이 빈 채로 있다면 삭제 후 매핑
    if 'ME코드' in raw_df.columns:
        raw_df = raw_df.drop(columns=['ME코드'])
        
    # RAW의 'SKU명'과 참조표의 '제품명'을 기준으로 결합 (Left Join)
    raw_df = pd.merge(raw_df, me_mapping_table, left_on='SKU명', right_on='제품명', how='left')
    
    # 만약 참조표에 없어서 매핑이 안 된 항목은 표시
    raw_df['ME코드'] = raw_df['ME코드'].fillna('미매핑(참조표확인)')

    # 3. 데이터 그룹화
    # 자사 매출 데이터
    sales_grouped = sales_df.groupby(['점포', '제품코드'])[['수량', 'Total Amount']].sum().reset_index()
    sales_grouped.rename(columns={'제품코드': 'ME코드', '수량': '자사_출고수량', 'Total Amount': '자사_매출액'}, inplace=True)

    # 쿠팡 매입 데이터
    raw_grouped = raw_df.groupby(['점포', 'ME코드'])[['수량', '총공급가액']].sum().reset_index()
    raw_grouped.rename(columns={'수량': '쿠팡_매입수량', '총공급가액': '쿠팡_매입액'}, inplace=True)

    # 4. 데이터 병합 (Outer Join)
    merged_df = pd.merge(sales_grouped, raw_grouped, on=['점포', 'ME코드'], how='outer').fillna(0)

    # 5. 차액 계산
    merged_df['수량_차액'] = merged_df['자사_출고수량'] - merged_df['쿠팡_매입수량']
    merged_df['금액_차액'] = merged_df['자사_매출액'] - merged_df['쿠팡_매입액']

    # 6. 비고 (차액 원인 분석)
    def analyze_difference(row):
        if row['ME코드'] == '미매핑(참조표확인)':
            return '❌ ME코드 누락 (참조표 확인)'
        elif row['수량_차액'] != 0:
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
if uploaded_file:
    try:
        with st.spinner('엑셀 파일의 시트들을 분석하는 중입니다...'):
            # 엑셀 파일 내의 특정 시트들을 각각 읽어오기
            sales_df = pd.read_excel(uploaded_file, sheet_name='Sales Report (Coupang)')
            raw_df = pd.read_excel(uploaded_file, sheet_name='RAW')
            me_ref_df = pd.read_excel(uploaded_file, sheet_name='ME코드 참조')

            # 데이터 전처리 실행
            result_df = process_data(sales_df, raw_df, me_ref_df)

        # 요약 지표 (KPI) 표시
        st.subheader("📊 대사 결과 요약")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_items = len(result_df)
        perfect_match = len(result_df[result_df['비고'] == '✅ 일치'])
        mismatch_qty = len(result_df[result_df['비고'] == '🚨 수량 불일치 (미입고 확인)'])
        mismatch_amt = len(result_df[result_df['비고'] == '⚠️ 단가 불일치 (단가/프로모션 확인)'])
        missing_me = len(result_df[result_df['비고'] == '❌ ME코드 누락 (참조표 확인)'])

        col1.metric("전체 건수", f"{total_items} 건")
        col2.metric("✅ 일치", f"{perfect_match} 건")
        col3.metric("🚨 수량 차이", f"{mismatch_qty} 건")
        col4.metric("⚠️ 단가 차이", f"{mismatch_amt} 건")
        col5.metric("❌ 매핑 실패", f"{missing_me} 건")

        st.divider()

        # 데이터프레임 렌더링
        st.subheader("📝 세부 차액 내역")
        
        filter_option = st.radio("목록 필터링", ["전체 보기", "차액 및 오류 발생 건만 보기", "ME코드 매핑 실패 건만 보기"], horizontal=True)
        
        display_df = result_df
        if filter_option == "차액 및 오류 발생 건만 보기":
            display_df = result_df[result_df['비고'] != '✅ 일치']
        elif filter_option == "ME코드 매핑 실패 건만 보기":
            display_df = result_df[result_df['비고'] == '❌ ME코드 누락 (참조표 확인)']

        # 하이라이팅 적용
        def highlight_diff(row):
            if row['비고'] == '❌ ME코드 누락 (참조표 확인)':
                return ['background-color: #e0e0e0'] * len(row)
            elif row['비고'] == '🚨 수량 불일치 (미입고 확인)':
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
            file_name="쿠팡_차액대사_완성본(원클릭).xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except ValueError as ve:
        st.error(f"엑셀 파일 내에 필요한 시트가 없습니다. 시트 이름이 'Sales Report (Coupang)', 'RAW', 'ME코드 참조'로 되어 있는지 확인해주세요. (상세 에러: {ve})")
    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다. (에러: {e})")
else:
    st.info("👈 왼쪽 사이드바에서 기존에 작업하시던 엑셀 서식 파일 하나만 업로드해주세요.")
