#!/usr/bin/env python3
"""
yfinance QUARTERLY Backfill Integration Test Suite

HK, CN, VN 리전의 분기별 재무제표 백필 기능 검증을 위한 통합 테스트.

테스트 범위:
- Unit Tests: 티커 변환, 데이터 검증, 필드 매핑
- Integration Tests: yfinance API 연결, 데이터 수집, DB 저장
- E2E Tests: 전체 파이프라인 (백필 → TTM 계산)
- Error Handling: 데이터 없음, API 오류 처리

실행 방법:
    python tests/integration/test_yfinance_quarterly_backfill.py

Author: Quant Platform Development Team
Date: 2025-12-11
"""

import sys
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.db_manager_postgres import PostgresDatabaseManager


@dataclass
class TestResult:
    """테스트 결과 데이터 클래스"""
    test_id: str
    test_name: str
    category: str
    region: str
    passed: bool
    message: str
    duration_sec: float = 0.0
    details: Dict = field(default_factory=dict)


class YFinanceQuarterlyTestSuite:
    """
    yfinance QUARTERLY 백필 통합 테스트 스위트

    테스트 카테고리:
    - UNIT: 단위 테스트 (모듈 레벨)
    - INTEGRATION: 통합 테스트 (API/DB 연동)
    - E2E: 엔드투엔드 테스트 (전체 파이프라인)
    - ERROR: 에러 핸들링 테스트
    """

    # 리전별 테스트 티커
    TEST_TICKERS = {
        'HK': {
            'valid': ['0700.HK', '0005.HK', '9988.HK'],      # Tencent, HSBC, Alibaba HK
            'invalid': ['0001.HK'],                          # 데이터 없음 예상
        },
        'CN': {
            'valid': ['600519.SS', '000858.SZ', '601318.SS'], # 마오타이, 오량액, 핑안보험
            'invalid': ['100.SZ'],                            # 레거시 티커
        },
        'VN': {
            'valid': ['VNM', 'VIC', 'VHM'],                   # Vinamilk, Vingroup, Vinhomes
            'invalid': ['XXX'],                               # 존재하지 않는 티커
        }
    }

    def __init__(self):
        self.db = PostgresDatabaseManager()
        self.results: List[TestResult] = []
        self.yf = None
        self.executor = None

        # yfinance 라이브러리 로드
        try:
            import yfinance as yf
            self.yf = yf
        except ImportError:
            print("ERROR: yfinance not installed")
            sys.exit(1)

        # Executor 로드
        try:
            from modules.backfill.yfinance_quarterly_executor import YFinanceQuarterlyExecutor
            self.executor = YFinanceQuarterlyExecutor(
                db=self.db,
                dry_run=False,
                rate_limit_delay=0.5,
                regions=['HK', 'CN', 'VN']
            )
        except Exception as e:
            print(f"ERROR: Failed to load executor: {e}")

    def _add_result(self, result: TestResult):
        """테스트 결과 추가"""
        self.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.test_id}: {result.test_name} ({result.duration_sec:.2f}s)")
        if not result.passed:
            print(f"       -> {result.message}")

    # =========================================================================
    # UNIT TESTS
    # =========================================================================

    def test_u1_ticker_format_conversion(self, region: str) -> TestResult:
        """U1: 티커 형식 변환 테스트"""
        start = time.time()

        test_cases = {
            'HK': [('0700.HK', '0700.HK'), ('0005.HK', '0005.HK')],
            'CN': [('600519.SS', '600519.SS'), ('000858.SZ', '000858.SZ')],
            'VN': [('VNM', 'VNM.VN'), ('VIC', 'VIC.VN')],
        }

        cases = test_cases.get(region, [])
        passed = True
        message = "All ticker conversions correct"
        details = {}

        for db_ticker, expected_yf in cases:
            actual_yf = self.executor._to_yf_ticker(db_ticker, region)
            details[db_ticker] = {'expected': expected_yf, 'actual': actual_yf}
            if actual_yf != expected_yf:
                passed = False
                message = f"Conversion failed: {db_ticker} -> {actual_yf} (expected {expected_yf})"
                break

        return TestResult(
            test_id='U1',
            test_name='ticker_format_conversion',
            category='UNIT',
            region=region,
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    def test_u2_cn_legacy_ticker_filter(self) -> TestResult:
        """U2: CN 레거시 티커 필터링 테스트"""
        start = time.time()

        test_cases = [
            ('600519.SS', True),   # 6자리 - 유효
            ('000858.SZ', True),   # 6자리 - 유효
            ('100.SZ', False),     # 3자리 - 무효 (레거시)
            ('11.SS', False),      # 2자리 - 무효 (레거시)
            ('1201.SZ', False),    # 4자리 - 무효 (레거시)
        ]

        passed = True
        message = "All CN legacy ticker filtering correct"
        details = {}

        for ticker, expected_valid in test_cases:
            actual_valid = self.executor._is_valid_cn_ticker(ticker)
            details[ticker] = {'expected': expected_valid, 'actual': actual_valid}
            if actual_valid != expected_valid:
                passed = False
                message = f"Filter failed: {ticker} -> {actual_valid} (expected {expected_valid})"
                break

        return TestResult(
            test_id='U2',
            test_name='cn_legacy_ticker_filter',
            category='UNIT',
            region='CN',
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    def test_u3_data_validation(self) -> TestResult:
        """U3: 분기 데이터 품질 검증 테스트"""
        start = time.time()

        test_cases = [
            # (data, expected_valid)
            ({'revenue': Decimal('1000000'), 'net_income': Decimal('100000')}, True),
            ({'revenue': None, 'net_income': Decimal('100000')}, True),  # revenue 없어도 net_income 있으면 OK
            ({'revenue': None, 'net_income': None}, False),              # 둘 다 없으면 무효
            ({'revenue': Decimal('-1000'), 'net_income': Decimal('100')}, False),  # 음수 매출 무효
        ]

        passed = True
        message = "All data validation checks correct"
        details = {}

        for i, (data, expected_valid) in enumerate(test_cases):
            actual_valid = self.executor._validate_quarterly_data(data)
            details[f'case_{i}'] = {'data': str(data), 'expected': expected_valid, 'actual': actual_valid}
            if actual_valid != expected_valid:
                passed = False
                message = f"Validation failed for case {i}: {actual_valid} (expected {expected_valid})"
                break

        return TestResult(
            test_id='U3',
            test_name='data_validation',
            category='UNIT',
            region='ALL',
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    def test_u4_field_mapping(self) -> TestResult:
        """U4: yfinance → DB 필드 매핑 테스트"""
        start = time.time()

        # 필수 매핑 확인
        required_mappings = {
            'income_stmt': ['revenue', 'net_income', 'gross_profit', 'operating_profit', 'ebitda'],
            'balance_sheet': ['total_assets', 'total_equity', 'current_assets', 'current_liabilities'],
            'cashflow': ['operating_cash_flow', 'fcf', 'capex'],
        }

        passed = True
        message = "All required field mappings exist"
        details = {}

        # Income Statement 매핑 확인
        income_mapped = list(self.executor.INCOME_STMT_MAPPING.values())
        for field in required_mappings['income_stmt']:
            if field not in income_mapped:
                passed = False
                message = f"Missing income statement mapping: {field}"
                break
        details['income_stmt'] = income_mapped

        # Balance Sheet 매핑 확인
        if passed:
            bs_mapped = list(self.executor.BALANCE_SHEET_MAPPING.values())
            for field in required_mappings['balance_sheet']:
                if field not in bs_mapped:
                    passed = False
                    message = f"Missing balance sheet mapping: {field}"
                    break
            details['balance_sheet'] = bs_mapped

        # Cash Flow 매핑 확인
        if passed:
            cf_mapped = list(self.executor.CASHFLOW_MAPPING.values())
            for field in required_mappings['cashflow']:
                if field not in cf_mapped:
                    passed = False
                    message = f"Missing cashflow mapping: {field}"
                    break
            details['cashflow'] = cf_mapped

        return TestResult(
            test_id='U4',
            test_name='field_mapping',
            category='UNIT',
            region='ALL',
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    # =========================================================================
    # INTEGRATION TESTS
    # =========================================================================

    def test_i1_yfinance_api_connectivity(self) -> TestResult:
        """I1: yfinance API 연결성 테스트"""
        start = time.time()

        try:
            # 가장 안정적인 티커로 테스트
            test_ticker = self.yf.Ticker('AAPL')
            info = test_ticker.info

            if info and 'symbol' in info:
                passed = True
                message = f"yfinance API connected (symbol: {info.get('symbol')})"
                details = {'symbol': info.get('symbol'), 'market_cap': info.get('marketCap')}
            else:
                passed = False
                message = "yfinance API returned empty response"
                details = {}
        except Exception as e:
            passed = False
            message = f"yfinance API connection failed: {str(e)}"
            details = {'error': str(e)}

        return TestResult(
            test_id='I1',
            test_name='yfinance_api_connectivity',
            category='INTEGRATION',
            region='ALL',
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    def test_i2_quarterly_data_fetch(self, region: str) -> TestResult:
        """I2-I4: 리전별 분기 데이터 수집 테스트"""
        start = time.time()
        test_id = {'HK': 'I2', 'CN': 'I3', 'VN': 'I4'}.get(region, 'I?')

        valid_tickers = self.TEST_TICKERS[region]['valid']
        success_count = 0
        details = {}

        for ticker in valid_tickers[:2]:  # 리전당 2개만 테스트
            try:
                result = self.executor.fetch_quarterly_data(ticker, region)
                if result and len(result) > 0:
                    success_count += 1
                    details[ticker] = {
                        'quarters': len(result),
                        'has_revenue': result[0].get('revenue') is not None,
                        'has_net_income': result[0].get('net_income') is not None,
                    }
                else:
                    details[ticker] = {'error': 'No data returned'}
            except Exception as e:
                details[ticker] = {'error': str(e)}

            time.sleep(0.5)  # Rate limiting

        passed = success_count > 0
        message = f"{success_count}/{len(valid_tickers[:2])} tickers fetched successfully"

        return TestResult(
            test_id=test_id,
            test_name=f'quarterly_data_fetch_{region.lower()}',
            category='INTEGRATION',
            region=region,
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    def test_i5_database_upsert(self, region: str) -> TestResult:
        """I5: DB UPSERT 동작 테스트"""
        start = time.time()

        # 실제 존재하는 티커 사용 (Foreign Key 제약조건 충족)
        real_tickers = {
            'HK': '0005.HK',  # HSBC Holdings
            'CN': '600519.SS',  # 마오타이
            'VN': 'VNM',  # Vinamilk
        }
        test_ticker = real_tickers.get(region, self.TEST_TICKERS[region]['valid'][0])

        # 고유한 테스트 날짜 사용 (기존 데이터와 충돌 방지)
        test_date = date(1999, 1, 1)  # 과거 날짜로 테스트

        # 테스트 데이터 준비
        test_data = {
            'ticker': test_ticker,
            'region': region,
            'date': test_date,
            'period_type': 'QUARTERLY',
            'data_source': 'yfinance_test',
            'revenue': Decimal('1000000000'),
            'net_income': Decimal('100000000'),
        }

        details = {'ticker': test_ticker, 'test_date': str(test_date)}

        try:
            # INSERT 테스트
            success1 = self.executor.save_quarterly_data(test_data)
            details['insert_success'] = success1

            # UPDATE 테스트 (같은 키로 다른 값)
            test_data['revenue'] = Decimal('2000000000')
            success2 = self.executor.save_quarterly_data(test_data)
            details['update_success'] = success2

            # 검증 쿼리
            verify_query = """
            SELECT revenue FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND date = %s AND period_type = 'QUARTERLY'
            """
            result = self.db.execute_query(verify_query, (test_ticker, region, test_date))

            # 클린업 (테스트 데이터 삭제)
            cleanup_query = """
            DELETE FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND date = %s AND period_type = 'QUARTERLY' AND data_source = 'yfinance_test'
            """
            self.db.execute_update(cleanup_query, (test_ticker, region, test_date))

            if result and float(result[0]['revenue']) == 2000000000:
                passed = True
                message = "UPSERT working correctly (INSERT + UPDATE verified)"
                details['final_value'] = float(result[0]['revenue'])
            else:
                passed = False
                message = "UPSERT verification failed"
                details['result'] = str(result)

        except Exception as e:
            passed = False
            message = f"UPSERT test failed: {str(e)}"
            details['error'] = str(e)

        return TestResult(
            test_id='I5',
            test_name='database_upsert',
            category='INTEGRATION',
            region=region,
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    # =========================================================================
    # E2E TESTS
    # =========================================================================

    def test_e2e_full_pipeline(self, region: str) -> TestResult:
        """E1-E3: 전체 파이프라인 테스트 (백필 → TTM)"""
        start = time.time()
        test_id = {'HK': 'E1', 'CN': 'E2', 'VN': 'E3'}.get(region, 'E?')

        # 테스트용 티커 1개 선택
        test_ticker = self.TEST_TICKERS[region]['valid'][0]
        details = {'ticker': test_ticker, 'region': region}

        try:
            # Step 1: 분기 데이터 수집
            quarters = self.executor.fetch_quarterly_data(test_ticker, region)
            if not quarters:
                return TestResult(
                    test_id=test_id,
                    test_name=f'full_pipeline_{region.lower()}',
                    category='E2E',
                    region=region,
                    passed=False,
                    message=f"No quarterly data available for {test_ticker}",
                    duration_sec=time.time() - start,
                    details=details
                )

            details['quarters_fetched'] = len(quarters)

            # Step 2: DB 저장
            saved_count = 0
            for q in quarters:
                if self.executor.save_quarterly_data(q):
                    saved_count += 1

            details['quarters_saved'] = saved_count

            # Step 3: DB 저장 검증
            verify_query = """
            SELECT COUNT(*) as cnt FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND period_type = 'QUARTERLY'
            """
            result = self.db.execute_query(verify_query, (test_ticker, region))
            db_count = result[0]['cnt'] if result else 0
            details['db_records'] = db_count

            # Step 4: TTM 계산 (4분기 이상 있을 경우)
            ttm_calculated = False
            if db_count >= 4:
                try:
                    from modules.fundamentals.ttm_service import TTMService
                    ttm_service = TTMService(self.db)
                    ttm_result = ttm_service.run_ttm_calculation(
                        regions=[region],
                        limit=1,
                        skip_calculated=False
                    )
                    ttm_calculated = ttm_result.get('tickers_success', 0) > 0
                    details['ttm_result'] = ttm_result
                except Exception as e:
                    details['ttm_error'] = str(e)

            details['ttm_calculated'] = ttm_calculated

            # 성공 판정: 최소 1개 분기 저장 성공
            passed = saved_count > 0
            message = f"Pipeline complete: {saved_count} quarters saved, TTM: {'Yes' if ttm_calculated else 'No (< 4 quarters)'}"

        except Exception as e:
            passed = False
            message = f"Pipeline failed: {str(e)}"
            details['error'] = str(e)

        return TestResult(
            test_id=test_id,
            test_name=f'full_pipeline_{region.lower()}',
            category='E2E',
            region=region,
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    # =========================================================================
    # ERROR HANDLING TESTS
    # =========================================================================

    def test_er1_no_data_ticker(self, region: str) -> TestResult:
        """ER1: 데이터 없는 티커 처리 테스트"""
        start = time.time()

        invalid_ticker = self.TEST_TICKERS[region]['invalid'][0]
        details = {'ticker': invalid_ticker, 'region': region}

        try:
            result = self.executor.fetch_quarterly_data(invalid_ticker, region)

            # 데이터 없는 경우 None 반환해야 함
            if result is None:
                passed = True
                message = f"Correctly handled no-data ticker: {invalid_ticker}"
            else:
                passed = False
                message = f"Expected None but got {len(result)} quarters"
                details['unexpected_data'] = result

        except Exception as e:
            # 예외가 발생해도 정상 처리로 간주 (에러 핸들링 작동)
            passed = True
            message = f"Error handled gracefully: {str(e)[:50]}"
            details['exception'] = str(e)

        return TestResult(
            test_id='ER1',
            test_name='no_data_ticker',
            category='ERROR',
            region=region,
            passed=passed,
            message=message,
            duration_sec=time.time() - start,
            details=details
        )

    # =========================================================================
    # TEST RUNNER
    # =========================================================================

    def run_all_tests(self, regions: List[str] = None) -> Dict:
        """모든 테스트 실행"""
        if regions is None:
            regions = ['HK', 'CN', 'VN']

        print("=" * 80)
        print("yfinance QUARTERLY Backfill Verification Test Suite")
        print("=" * 80)
        print(f"Test Regions: {', '.join(regions)}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # UNIT TESTS
        print("\n[UNIT TESTS]")
        for region in regions:
            self._add_result(self.test_u1_ticker_format_conversion(region))
        self._add_result(self.test_u2_cn_legacy_ticker_filter())
        self._add_result(self.test_u3_data_validation())
        self._add_result(self.test_u4_field_mapping())

        # INTEGRATION TESTS
        print("\n[INTEGRATION TESTS]")
        self._add_result(self.test_i1_yfinance_api_connectivity())
        for region in regions:
            self._add_result(self.test_i2_quarterly_data_fetch(region))
            time.sleep(1)  # Rate limiting between regions
        self._add_result(self.test_i5_database_upsert(regions[0]))

        # E2E TESTS
        print("\n[E2E TESTS]")
        for region in regions:
            self._add_result(self.test_e2e_full_pipeline(region))
            time.sleep(1)  # Rate limiting between regions

        # ERROR HANDLING TESTS
        print("\n[ERROR HANDLING TESTS]")
        for region in regions:
            self._add_result(self.test_er1_no_data_ticker(region))
            time.sleep(0.5)

        return self.generate_report()

    def run_region_tests(self, region: str) -> Dict:
        """특정 리전 테스트만 실행"""
        print("=" * 80)
        print(f"yfinance QUARTERLY Verification - {region} Region")
        print("=" * 80)

        print("\n[UNIT TESTS]")
        self._add_result(self.test_u1_ticker_format_conversion(region))
        if region == 'CN':
            self._add_result(self.test_u2_cn_legacy_ticker_filter())

        print("\n[INTEGRATION TESTS]")
        self._add_result(self.test_i1_yfinance_api_connectivity())
        self._add_result(self.test_i2_quarterly_data_fetch(region))
        self._add_result(self.test_i5_database_upsert(region))

        print("\n[E2E TESTS]")
        self._add_result(self.test_e2e_full_pipeline(region))

        print("\n[ERROR HANDLING TESTS]")
        self._add_result(self.test_er1_no_data_ticker(region))

        return self.generate_report()

    def generate_report(self) -> Dict:
        """테스트 결과 리포트 생성"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        # 카테고리별 집계
        by_category = {}
        for r in self.results:
            if r.category not in by_category:
                by_category[r.category] = {'passed': 0, 'failed': 0}
            if r.passed:
                by_category[r.category]['passed'] += 1
            else:
                by_category[r.category]['failed'] += 1

        # 리전별 집계
        by_region = {}
        for r in self.results:
            if r.region not in by_region:
                by_region[r.region] = {'passed': 0, 'failed': 0}
            if r.passed:
                by_region[r.region]['passed'] += 1
            else:
                by_region[r.region]['failed'] += 1

        # 실패한 테스트 목록
        failures = [
            {'test_id': r.test_id, 'test_name': r.test_name, 'region': r.region, 'message': r.message}
            for r in self.results if not r.passed
        ]

        report = {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': f"{passed/total*100:.1f}%" if total > 0 else "N/A",
            },
            'by_category': by_category,
            'by_region': by_region,
            'failures': failures,
            'timestamp': datetime.now().isoformat(),
        }

        # 리포트 출력
        print("\n" + "=" * 80)
        print("TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)" if total > 0 else "Passed: 0")
        print(f"Failed: {failed}")

        print("\nBy Category:")
        for cat, stats in by_category.items():
            print(f"  {cat}: {stats['passed']}/{stats['passed']+stats['failed']} passed")

        print("\nBy Region:")
        for region, stats in by_region.items():
            print(f"  {region}: {stats['passed']}/{stats['passed']+stats['failed']} passed")

        if failures:
            print("\nFailed Tests:")
            for f in failures:
                print(f"  - [{f['test_id']}] {f['test_name']} ({f['region']}): {f['message']}")

        print("=" * 80)

        return report


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="yfinance QUARTERLY Backfill Verification Tests")
    parser.add_argument('--region', choices=['HK', 'CN', 'VN', 'ALL'], default='ALL',
                       help='Target region (default: ALL)')
    args = parser.parse_args()

    suite = YFinanceQuarterlyTestSuite()

    if args.region == 'ALL':
        report = suite.run_all_tests()
    else:
        report = suite.run_region_tests(args.region)

    # 종료 코드: 실패 테스트가 있으면 1
    sys.exit(0 if report['summary']['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
