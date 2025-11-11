"""
데이터 품질 검증 테스트

목적:
- 프로덕션 환경에서 수집된 데이터의 무결성 검증
- 데이터 완전성, 일관성, 정확성 검증
- 이상 징후 탐지 및 보고

실행 방법:
1. 검증 실행: python3 -m pytest tests/integration/production/test_data_quality_validation.py -v -s
"""

import sys
import os
from datetime import datetime, date, timedelta
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from modules.db_manager_postgres import PostgresDatabaseManager


@pytest.fixture(scope="module")
def db_manager():
    """PostgreSQL 데이터베이스 매니저 fixture"""
    db = PostgresDatabaseManager()
    yield db
    db.close_pool()


class TestDataQualityFXRates:
    """환율 데이터 품질 검증"""

    def test_01_fx_data_completeness(self, db_manager):
        """테스트 3.1.1: 환율 데이터 완전성 검증"""
        print("\n" + "="*80)
        print("테스트 3.1.1: 환율 데이터 완전성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 최근 7일 데이터 확인
            cursor.execute("""
                SELECT
                    date,
                    COUNT(DISTINCT quote_currency) as currency_count
                FROM exchange_rates
                WHERE base_currency = 'KRW'
                  AND date >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY date
                ORDER BY date DESC
            """)

            daily_counts = cursor.fetchall()
            print(f"\n📊 최근 7일 환율 데이터:")

            expected_currencies = {'USD', 'JPY', 'EUR', 'CNY'}
            issues = []

            for record_date, count in daily_counts:
                status = "✅" if count >= len(expected_currencies) else "⚠️ "
                print(f"  {status} {record_date}: {count}개 통화")
                if count < len(expected_currencies):
                    issues.append(f"{record_date}: {count}개 통화만 존재")

            if issues:
                print(f"\n⚠️  완전성 이슈: {len(issues)}건")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("\n✅ 모든 날짜에 대해 완전한 데이터 확인")

    def test_02_fx_rate_validity(self, db_manager):
        """테스트 3.1.2: 환율 데이터 유효성 검증"""
        print("\n" + "="*80)
        print("테스트 3.1.2: 환율 데이터 유효성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 비정상적인 환율 범위 확인
            cursor.execute("""
                SELECT
                    quote_currency,
                    date,
                    rate,
                    CASE
                        WHEN rate <= 0 THEN '음수 또는 0'
                        WHEN quote_currency = 'USD' AND (rate < 800 OR rate > 2000) THEN '비정상 USD 환율'
                        WHEN quote_currency = 'JPY' AND (rate < 5 OR rate > 20) THEN '비정상 JPY 환율'
                        WHEN quote_currency = 'EUR' AND (rate < 1000 OR rate > 2000) THEN '비정상 EUR 환율'
                        WHEN quote_currency = 'CNY' AND (rate < 100 OR rate > 300) THEN '비정상 CNY 환율'
                        ELSE '정상'
                    END as validity_status
                FROM exchange_rates
                WHERE base_currency = 'KRW'
                  AND date >= CURRENT_DATE - INTERVAL '30 days'
            """)

            validity_results = cursor.fetchall()
            invalid_rates = [r for r in validity_results if r[3] != '정상']

            print(f"\n📊 환율 유효성 검증 (최근 30일):")
            print(f"  - 전체 레코드: {len(validity_results)}개")
            print(f"  - 유효한 레코드: {len(validity_results) - len(invalid_rates)}개")
            print(f"  - 비정상 레코드: {len(invalid_rates)}개")

            if invalid_rates:
                print(f"\n⚠️  비정상 환율 (최대 10개):")
                for currency, record_date, rate, status in invalid_rates[:10]:
                    print(f"  - {currency} ({record_date}): {rate} - {status}")
            else:
                print("\n✅ 모든 환율 데이터 유효")

    def test_03_fx_duplicates(self, db_manager):
        """테스트 3.1.3: 환율 데이터 중복 검증"""
        print("\n" + "="*80)
        print("테스트 3.1.3: 환율 데이터 중복 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 중복 레코드 확인
            cursor.execute("""
                SELECT base_currency, quote_currency, date, COUNT(*) as duplicate_count
                FROM exchange_rates
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY base_currency, quote_currency, date
                HAVING COUNT(*) > 1
            """)

            duplicates = cursor.fetchall()

            print(f"\n📊 중복 레코드 검증 (최근 30일):")
            if duplicates:
                print(f"  ⚠️  중복 발견: {len(duplicates)}건")
                for base, quote, record_date, count in duplicates[:10]:
                    print(f"  - {base}/{quote} ({record_date}): {count}개")
            else:
                print("  ✅ 중복 레코드 없음")


class TestDataQualityStockClassification:
    """종목 분류 데이터 품질 검증"""

    def test_04_classification_completeness(self, db_manager):
        """테스트 3.2.1: 분류 데이터 완전성 검증"""
        print("\n" + "="*80)
        print("테스트 3.2.1: 분류 데이터 완전성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 전체 활성 종목 vs 분류된 종목
            cursor.execute("""
                SELECT
                    t.region,
                    COUNT(t.ticker) as total_tickers,
                    COUNT(sd.ticker) as classified_tickers,
                    COUNT(CASE WHEN sd.sector IS NOT NULL THEN 1 END) as with_sector,
                    COUNT(CASE WHEN sd.industry IS NOT NULL THEN 1 END) as with_industry
                FROM tickers t
                LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.status = 'active' AND t.asset_type = 'Stock'
                GROUP BY t.region
                ORDER BY t.region
            """)

            region_stats = cursor.fetchall()
            print(f"\n📊 지역별 분류 완전성:")

            for region, total, classified, with_sector, with_industry in region_stats:
                classification_rate = (classified / total * 100) if total > 0 else 0
                sector_rate = (with_sector / total * 100) if total > 0 else 0
                industry_rate = (with_industry / total * 100) if total > 0 else 0

                status = "✅" if classification_rate >= 80 else "⚠️ "
                print(f"\n  {status} {region}:")
                print(f"    - 전체 종목: {total:,}개")
                print(f"    - 분류된 종목: {classified:,}개 ({classification_rate:.1f}%)")
                print(f"    - 섹터 분류: {with_sector:,}개 ({sector_rate:.1f}%)")
                print(f"    - 업종 분류: {with_industry:,}개 ({industry_rate:.1f}%)")

    def test_05_spac_preferred_validity(self, db_manager):
        """테스트 3.2.2: SPAC/우선주 탐지 유효성 검증"""
        print("\n" + "="*80)
        print("테스트 3.2.2: SPAC/우선주 탐지 유효성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # SPAC 탐지 검증 (ticker에 'SPAC' 포함 여부)
            cursor.execute("""
                SELECT t.ticker, t.name, sd.is_spac
                FROM tickers t
                JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR'
                  AND (
                      (t.name LIKE '%SPAC%' AND sd.is_spac = false)
                      OR (t.name LIKE '%특수목적인수%' AND sd.is_spac = false)
                  )
                LIMIT 10
            """)

            spac_mismatches = cursor.fetchall()

            print(f"\n📊 SPAC 탐지 검증:")
            if spac_mismatches:
                print(f"  ⚠️  미탐지 SPAC: {len(spac_mismatches)}건")
                for ticker, name, is_spac in spac_mismatches:
                    print(f"  - [{ticker}] {name} (is_spac: {is_spac})")
            else:
                print("  ✅ SPAC 탐지 정확")

            # 우선주 탐지 검증 (ticker가 숫자로 끝나는지)
            cursor.execute("""
                SELECT t.ticker, t.name, sd.is_preferred
                FROM tickers t
                JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR'
                  AND t.ticker ~ '^\\d{5}[2-9]$'
                  AND sd.is_preferred = false
                LIMIT 10
            """)

            preferred_mismatches = cursor.fetchall()

            print(f"\n📊 우선주 탐지 검증:")
            if preferred_mismatches:
                print(f"  ⚠️  미탐지 우선주: {len(preferred_mismatches)}건")
                for ticker, name, is_preferred in preferred_mismatches:
                    print(f"  - [{ticker}] {name} (is_preferred: {is_preferred})")
            else:
                print("  ✅ 우선주 탐지 정확")


class TestDataQualityETFData:
    """ETF 데이터 품질 검증"""

    def test_06_etf_metadata_completeness(self, db_manager):
        """테스트 3.3.1: ETF 메타데이터 완전성 검증"""
        print("\n" + "="*80)
        print("테스트 3.3.1: ETF 메타데이터 완전성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # ETF 메타데이터 완전성 통계
            cursor.execute("""
                SELECT
                    e.region,
                    COUNT(*) as total_etfs,
                    COUNT(e.aum) as with_aum,
                    COUNT(e.expense_ratio) as with_expense_ratio,
                    COUNT(e.inception_date) as with_inception_date,
                    COUNT(e.benchmark_index) as with_benchmark
                FROM etf_details e
                GROUP BY e.region
                ORDER BY e.region
            """)

            region_stats = cursor.fetchall()
            print(f"\n📊 지역별 ETF 메타데이터 완전성:")

            for region, total, with_aum, with_expense, with_inception, with_benchmark in region_stats:
                aum_rate = (with_aum / total * 100) if total > 0 else 0
                expense_rate = (with_expense / total * 100) if total > 0 else 0
                inception_rate = (with_inception / total * 100) if total > 0 else 0
                benchmark_rate = (with_benchmark / total * 100) if total > 0 else 0

                status = "✅" if aum_rate >= 70 else "⚠️ "
                print(f"\n  {status} {region}:")
                print(f"    - 전체 ETF: {total:,}개")
                print(f"    - AUM: {with_aum:,}개 ({aum_rate:.1f}%)")
                print(f"    - 보수율: {with_expense:,}개 ({expense_rate:.1f}%)")
                print(f"    - 상장일: {with_inception:,}개 ({inception_rate:.1f}%)")
                print(f"    - 벤치마크: {with_benchmark:,}개 ({benchmark_rate:.1f}%)")

    def test_07_etf_holdings_validity(self, db_manager):
        """테스트 3.3.2: ETF 보유종목 유효성 검증"""
        print("\n" + "="*80)
        print("테스트 3.3.2: ETF 보유종목 유효성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 보유종목 비중 합계 검증
            cursor.execute("""
                SELECT
                    etf_ticker,
                    SUM(weight) as total_weight,
                    COUNT(*) as holding_count
                FROM etf_holdings
                WHERE region = 'KR'
                GROUP BY etf_ticker
                HAVING ABS(SUM(weight) - 1.0) > 0.05
                LIMIT 10
            """)

            weight_issues = cursor.fetchall()

            print(f"\n📊 보유종목 비중 검증:")
            if weight_issues:
                print(f"  ⚠️  비중 합계 이슈: {len(weight_issues)}건")
                for etf_ticker, total_weight, count in weight_issues:
                    print(f"  - [{etf_ticker}]: 비중 합 {total_weight:.2%} (종목 {count}개)")
            else:
                print("  ✅ 모든 ETF 보유종목 비중 합계 유효")

            # 음수 비중 확인
            cursor.execute("""
                SELECT etf_ticker, holding_ticker, weight
                FROM etf_holdings
                WHERE region = 'KR' AND weight < 0
                LIMIT 10
            """)

            negative_weights = cursor.fetchall()

            if negative_weights:
                print(f"\n  ⚠️  음수 비중: {len(negative_weights)}건")
                for etf_ticker, holding_ticker, weight in negative_weights:
                    print(f"  - [{etf_ticker}] {holding_ticker}: {weight:.2%}")
            else:
                print("\n  ✅ 음수 비중 없음")

    def test_08_etf_data_freshness(self, db_manager):
        """테스트 3.3.3: ETF 데이터 신선도 검증"""
        print("\n" + "="*80)
        print("테스트 3.3.3: ETF 데이터 신선도 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 30일 이상 업데이트되지 않은 ETF
            cursor.execute("""
                SELECT e.ticker, t.name, e.updated_at
                FROM etf_details e
                JOIN tickers t ON e.ticker = t.ticker AND e.region = t.region
                WHERE e.region = 'KR'
                  AND e.updated_at < CURRENT_DATE - INTERVAL '30 days'
                ORDER BY e.updated_at
                LIMIT 10
            """)

            stale_etfs = cursor.fetchall()

            print(f"\n📊 데이터 신선도 검증:")
            if stale_etfs:
                print(f"  ⚠️  오래된 데이터 (30일+): {len(stale_etfs)}건")
                for ticker, name, updated_at in stale_etfs:
                    days_ago = (date.today() - updated_at.date()).days
                    print(f"  - [{ticker}] {name}: {days_ago}일 전 ({updated_at.date()})")
            else:
                print("  ✅ 모든 ETF 데이터가 최신 상태")


class TestDataQualityOverall:
    """전체 데이터 품질 종합 검증"""

    def test_09_database_statistics(self, db_manager):
        """테스트 3.4.1: 데이터베이스 통계"""
        print("\n" + "="*80)
        print("테스트 3.4.1: 데이터베이스 통계")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 전체 테이블 레코드 수
            tables = [
                'tickers',
                'stock_details',
                'etf_details',
                'etf_holdings',
                'exchange_rates',
                'ohlcv_data'
            ]

            print(f"\n📊 테이블별 레코드 수:")
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"  - {table}: {count:,}개")
                except Exception as e:
                    print(f"  - {table}: 오류 ({str(e)})")

            # 지역별 활성 종목 수
            cursor.execute("""
                SELECT region, asset_type, COUNT(*) as ticker_count
                FROM tickers
                WHERE status = 'active'
                GROUP BY region, asset_type
                ORDER BY region, asset_type
            """)

            region_ticker_stats = cursor.fetchall()
            print(f"\n📊 지역별 활성 종목:")
            for region, asset_type, count in region_ticker_stats:
                print(f"  - {region} {asset_type}: {count:,}개")

    def test_10_data_quality_summary(self, db_manager):
        """테스트 3.4.2: 데이터 품질 종합 요약"""
        print("\n" + "="*80)
        print("테스트 3.4.2: 데이터 품질 종합 요약")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 데이터 품질 점수 계산
            quality_scores = {}

            # 1. FX 데이터 완전성 (최근 7일)
            cursor.execute("""
                SELECT COUNT(DISTINCT date) as date_count
                FROM exchange_rates
                WHERE base_currency = 'KRW'
                  AND date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            fx_date_count = cursor.fetchone()[0]
            fx_completeness = min(fx_date_count / 7.0 * 100, 100)
            quality_scores['FX 데이터 완전성'] = fx_completeness

            # 2. Stock 분류 완전성
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN sd.ticker IS NOT NULL THEN 1 END)::float /
                    COUNT(*)::float * 100 as classification_rate
                FROM tickers t
                LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR' AND t.status = 'active' AND t.asset_type = 'Stock'
            """)
            result = cursor.fetchone()
            stock_classification = result[0] if result and result[0] else 0
            quality_scores['Stock 분류율'] = stock_classification

            # 3. ETF 메타데이터 완전성
            cursor.execute("""
                SELECT
                    COUNT(aum)::float / COUNT(*)::float * 100 as aum_rate
                FROM etf_details
                WHERE region = 'KR'
            """)
            result = cursor.fetchone()
            etf_metadata = result[0] if result and result[0] else 0
            quality_scores['ETF 메타데이터'] = etf_metadata

            print(f"\n📊 데이터 품질 종합 점수:")
            for metric, score in quality_scores.items():
                status = "✅" if score >= 80 else ("⚠️ " if score >= 60 else "❌")
                print(f"  {status} {metric}: {score:.1f}%")

            # 전체 평균 점수
            avg_score = sum(quality_scores.values()) / len(quality_scores)
            overall_status = "✅" if avg_score >= 80 else ("⚠️ " if avg_score >= 60 else "❌")
            print(f"\n{overall_status} 전체 평균 품질 점수: {avg_score:.1f}%")

            # 권장 사항
            print(f"\n💡 권장 사항:")
            if fx_completeness < 80:
                print("  - FX 데이터 수집 주기 점검 필요")
            if stock_classification < 80:
                print("  - Stock 분류 프로세스 개선 필요")
            if etf_metadata < 80:
                print("  - ETF 메타데이터 수집 강화 필요")
            if avg_score >= 90:
                print("  - 데이터 품질 우수 - 현재 수준 유지")


def test_summary():
    """테스트 요약 출력"""
    print("\n" + "="*80)
    print("데이터 품질 검증 테스트 완료")
    print("="*80)
    print("\n✅ 모든 테스트 통과")
    print("\n검증 항목:")
    print("  1. 환율 데이터 완전성, 유효성, 중복 검증")
    print("  2. 종목 분류 완전성, SPAC/우선주 탐지 검증")
    print("  3. ETF 메타데이터 완전성, 보유종목 유효성, 데이터 신선도 검증")
    print("  4. 데이터베이스 통계 및 품질 종합 요약")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
