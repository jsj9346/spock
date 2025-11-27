
================================================================================
📊 US/JP 리전 재무 데이터 업데이트 검증 보고서
================================================================================
생성 시각: 2025-11-26 14:10:27

## 요약
- 총 테스트: 4개
- 통과: 3개
- 실패: 1개
- 통과율: 75%

## 상세 결과

### SEC EDGAR (US) API
- 상태: ✅ 통과
- 메시지: 6개 레코드 추출 성공
- 상세:
  - api_connection: True
  - data_extraction: True
  - tickers_tested: ['AAPL', 'MSFT']
  - records_extracted: 6
  - sample_data: {'ticker': 'AAPL', 'fiscal_year': 2022, 'revenue': 394328000000.0, 'net_income': 99803000000.0, 'total_assets': 352755000000.0}

### EDINET (JP) API
- 상태: ❌ 실패
- 메시지: API 키 미설정
- 상세:
- 오류:
  - EDINET_API_KEY 환경변수 미설정

### DB 저장 검증
- 상태: ✅ 통과
- 메시지: 총 10개 레코드 확인
- 상세:
  - db_connection: True
  - us_records: 5
  - jp_records: 5
  - table_schema_valid: True
  - sample_records: [{'ticker': 'A', 'fiscal_year': 2024, 'revenue': Decimal('6510000000.00'), 'net_income': Decimal('1289000000.00'), 'data_source': 'SEC_EDGAR'}, {'ticker': 'A', 'fiscal_year': 2023, 'revenue': Decimal('6833000000.00'), 'net_income': Decimal('1240000000.00'), 'data_source': 'SEC_EDGAR'}, {'ticker': 'A', 'fiscal_year': 2022, 'revenue': Decimal('6848000000.00'), 'net_income': Decimal('1254000000.00'), 'data_source': 'SEC_EDGAR'}, {'ticker': '1301', 'fiscal_year': 2023, 'revenue': Decimal('262519000000.00'), 'net_income': Decimal('2037000000.00'), 'data_source': 'EDINET'}, {'ticker': '1301', 'fiscal_year': 2022, 'revenue': Decimal('256151000000.00'), 'net_income': Decimal('2914000000.00'), 'data_source': 'EDINET'}, {'ticker': '1301', 'fiscal_year': 2021, 'revenue': Decimal('254783000000.00'), 'net_income': Decimal('3211000000.00'), 'data_source': 'EDINET'}]

### Executor 통합
- 상태: ✅ 통과
- 메시지: 모든 Executor 준비 완료
- 상세:
  - sec_executor_ready: True
  - edinet_executor_ready: True
  - orchestrator_routing: True

## 결론
⚠️ 일부 테스트 통과 - 세부 사항 확인 필요

================================================================================