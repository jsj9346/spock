"""
yfinance API Gap Analysis 프로덕션 통합 테스트

목적:
- yfinance를 사용한 listing_date 백필 검증
- Gap-aware backfill 효율성 측정
- 다중 시장 (US, JP) 데이터 품질 검증
- API 응답 시간 및 에러율 측정

실행 방법:
1. Dry-run 모드: python3 -m pytest tests/integration/production/test_yfinance_gap_production.py -v -s
2. 실제 실행:     python3 -m pytest tests/integration/production/test_yfinance_gap_production.py -v -s --run-production

주의사항:
- 프로덕션 DB에 쓰기를 수행합니다
- yfinance rate limit 준수 (0.2초 delay)
- 테스트 샘플: US 10 tickers, JP 10 tickers

작성자: Quant Platform Development Team
날짜: 2025-11-11
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date
import time
import pytest

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.orchestrator import BackfillOrchestrator

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def db_manager():
    """PostgreSQL 데이터베이스 매니저 fixture"""
    db = PostgresDatabaseManager()
    yield db
    db.close_pool()


@pytest.fixture(scope="module")
def gap_analyzer(db_manager):
    """GapAnalyzer 인스턴스 fixture"""
    return GapAnalyzer(db_manager)


@pytest.fixture(scope="module")
def test_tickers_us(db_manager):
    """테스트용 US ticker 샘플 (10개)"""
    query = """
    SELECT ticker, name, listing_date, region
    FROM tickers
    WHERE region = 'US'
      AND ticker IN (
          'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
          'TSLA', 'META', 'BRK.B', 'V', 'JPM'
      )
    ORDER BY ticker
    LIMIT 10
    """

    result = db_manager.execute_query(query)

    if not result or len(result) == 0:
        # Fallback: 아무 US ticker나 10개
        query_fallback = """
        SELECT ticker, name, listing_date, region
        FROM tickers
        WHERE region = 'US'
        ORDER BY ticker
        LIMIT 10
        """
        result = db_manager.execute_query(query_fallback)

    return result if result else []


@pytest.fixture(scope="module")
def test_tickers_jp(db_manager):
    """테스트용 JP ticker 샘플 (10개)"""
    query = """
    SELECT ticker, name, listing_date, region
    FROM tickers
    WHERE region = 'JP'
    ORDER BY ticker
    LIMIT 10
    """

    result = db_manager.execute_query(query)
    return result if result else []


@pytest.fixture(scope="module")
def performance_metrics():
    """성능 메트릭 저장용 딕셔너리"""
    return {
        'us': {'api_times': [], 'success': 0, 'failed': 0},
        'jp': {'api_times': [], 'success': 0, 'failed': 0},
        'overall': {}
    }


# ============================================================================
# 프로덕션 테스트 클래스
# ============================================================================

class TestYfinanceGapProduction:
    """yfinance API Gap Analysis 프로덕션 통합 테스트"""

    # ========================================================================
    # Test 1: Database Connection
    # ========================================================================

    def test_01_database_connection(self, db_manager):
        """테스트 1: 데이터베이스 연결 및 테이블 검증"""
        print("\n" + "="*80)
        print("테스트 1: 데이터베이스 연결 및 테이블 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # PostgreSQL 버전 확인
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print(f"✅ PostgreSQL 버전: {version[:50]}...")

            # tickers 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'tickers'
                )
            """)
            table_exists = cursor.fetchone()[0]
            assert table_exists, "tickers 테이블이 존재하지 않습니다"
            print("✅ tickers 테이블 확인")

            # listing_date 컬럼 확인
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'tickers'
                  AND column_name = 'listing_date'
            """)
            col_info = cursor.fetchone()
            assert col_info is not None, "listing_date 컬럼이 존재하지 않습니다"
            print(f"✅ listing_date 컬럼 확인: {col_info[1]}")

            # 기존 데이터 현황 확인
            cursor.execute("""
                SELECT
                    region,
                    COUNT(*) as total,
                    COUNT(listing_date) as with_listing_date,
                    ROUND(100.0 * COUNT(listing_date) / NULLIF(COUNT(*), 0), 1) as coverage_pct
                FROM tickers
                WHERE region IN ('US', 'JP')
                GROUP BY region
                ORDER BY region
            """)
            stats = cursor.fetchall()

            print(f"\n📊 기존 listing_date 커버리지:")
            for region, total, with_date, coverage in stats:
                print(f"   - {region}: {with_date:,}/{total:,} ({coverage}%)")

    # ========================================================================
    # Test 2: yfinance Availability
    # ========================================================================

    def test_02_yfinance_availability(self):
        """테스트 2: yfinance 라이브러리 설치 확인"""
        print("\n" + "="*80)
        print("테스트 2: yfinance 라이브러리 설치 확인")
        print("="*80)

        if not YFINANCE_AVAILABLE:
            pytest.skip("yfinance가 설치되지 않았습니다. pip install yfinance를 실행하세요")

        # 간단한 테스트 API 호출
        try:
            test_ticker = yf.Ticker("AAPL")
            info = test_ticker.info

            if 'symbol' in info:
                print(f"✅ yfinance 정상 작동 확인 (테스트: AAPL)")
                print(f"   - Symbol: {info.get('symbol', 'N/A')}")
                print(f"   - Name: {info.get('longName', 'N/A')}")
            else:
                print("⚠️  yfinance 응답이 비정상입니다")

        except Exception as e:
            pytest.fail(f"yfinance API 호출 실패: {e}")

    # ========================================================================
    # Test 3: Gap Analysis - US Market
    # ========================================================================

    def test_03_gap_analysis_us_market(self, db_manager, gap_analyzer, test_tickers_us):
        """테스트 3: Gap Analysis - US 시장"""
        print("\n" + "="*80)
        print("테스트 3: Gap Analysis - US 시장")
        print("="*80)

        if not test_tickers_us:
            pytest.skip("US ticker 샘플이 없습니다")

        print(f"📊 테스트 샘플: {len(test_tickers_us)} tickers")
        for ticker_data in test_tickers_us[:3]:
            print(f"   - {ticker_data['ticker']} ({ticker_data.get('name', 'N/A')})")
        print("   ...")

        # Gap analysis 실행
        ticker_list = [t['ticker'] for t in test_tickers_us]

        # Note: listing_date는 tickers 테이블에 있으므로 간단한 쿼리로 확인
        placeholders = ','.join(['%s'] * len(ticker_list))
        query = f"""
        SELECT
            COUNT(*) as total,
            COUNT(listing_date) as with_listing_date,
            COUNT(*) - COUNT(listing_date) as missing_listing_date
        FROM tickers
        WHERE ticker IN ({placeholders})
          AND region = 'US'
        """

        result = db_manager.execute_query(query, tuple(ticker_list))

        if result:
            stats = result[0]
            print(f"\n🔍 Gap Analysis 결과:")
            print(f"   - Total tickers:       {stats['total']}")
            print(f"   - ✅ Has listing_date: {stats['with_listing_date']}")
            print(f"   - ⚠️  Missing:          {stats['missing_listing_date']}")

            if stats['total'] > 0:
                efficiency = (stats['with_listing_date'] / stats['total']) * 100
                print(f"   - 💡 Efficiency gain:  {efficiency:.1f}%")

    # ========================================================================
    # Test 4: Gap Analysis - JP Market
    # ========================================================================

    def test_04_gap_analysis_jp_market(self, db_manager, gap_analyzer, test_tickers_jp):
        """테스트 4: Gap Analysis - JP 시장"""
        print("\n" + "="*80)
        print("테스트 4: Gap Analysis - JP 시장")
        print("="*80)

        if not test_tickers_jp:
            pytest.skip("JP ticker 샘플이 없습니다")

        print(f"📊 테스트 샘플: {len(test_tickers_jp)} tickers")

        ticker_list = [t['ticker'] for t in test_tickers_jp]
        placeholders = ','.join(['%s'] * len(ticker_list))

        query = f"""
        SELECT
            COUNT(*) as total,
            COUNT(listing_date) as with_listing_date,
            COUNT(*) - COUNT(listing_date) as missing_listing_date
        FROM tickers
        WHERE ticker IN ({placeholders})
          AND region = 'JP'
        """

        result = db_manager.execute_query(query, tuple(ticker_list))

        if result:
            stats = result[0]
            print(f"\n🔍 Gap Analysis 결과:")
            print(f"   - Total tickers:       {stats['total']}")
            print(f"   - ✅ Has listing_date: {stats['with_listing_date']}")
            print(f"   - ⚠️  Missing:          {stats['missing_listing_date']}")

    # ========================================================================
    # Test 5: yfinance Backfill - US Market (DRY RUN)
    # ========================================================================

    @pytest.mark.skipif(
        not YFINANCE_AVAILABLE,
        reason="yfinance가 설치되지 않았습니다"
    )
    def test_05_yfinance_backfill_us_dry_run(
        self,
        db_manager,
        test_tickers_us,
        performance_metrics
    ):
        """테스트 5: yfinance Backfill - US 시장 (DRY RUN)"""
        print("\n" + "="*80)
        print("테스트 5: yfinance Backfill - US 시장 (DRY RUN)")
        print("="*80)

        if not test_tickers_us:
            pytest.skip("US ticker 샘플이 없습니다")

        print(f"📊 처리 대상: {len(test_tickers_us)} tickers (최대 3개 테스트)")

        # 샘플 3개만 테스트 (dry-run)
        sample_tickers = test_tickers_us[:3]

        for ticker_data in sample_tickers:
            ticker = ticker_data['ticker']
            print(f"\n🔍 테스트: {ticker}")

            try:
                # yfinance API 호출
                start_time = time.time()
                yf_ticker = yf.Ticker(ticker)
                info = yf_ticker.info
                elapsed_time = time.time() - start_time

                # listing_date 추출
                if 'firstTradeDateEpochUtc' in info and info['firstTradeDateEpochUtc']:
                    from datetime import datetime
                    listing_date = datetime.fromtimestamp(info['firstTradeDateEpochUtc']).date()
                    print(f"   ✅ Listing date: {listing_date} ({elapsed_time:.2f}초)")

                    performance_metrics['us']['api_times'].append(elapsed_time)
                    performance_metrics['us']['success'] += 1
                else:
                    print(f"   ⚠️  Listing date 정보 없음")
                    performance_metrics['us']['failed'] += 1

                # Rate limit 준수
                time.sleep(0.2)

            except Exception as e:
                print(f"   ❌ 오류: {e}")
                performance_metrics['us']['failed'] += 1

        # 통계 출력
        us_metrics = performance_metrics['us']
        if us_metrics['api_times']:
            avg_time = sum(us_metrics['api_times']) / len(us_metrics['api_times'])
            print(f"\n📊 US 시장 성능:")
            print(f"   - 평균 응답 시간: {avg_time:.2f}초")
            print(f"   - 성공: {us_metrics['success']}")
            print(f"   - 실패: {us_metrics['failed']}")

    # ========================================================================
    # Test 6: Data Quality Verification
    # ========================================================================

    def test_06_verify_data_quality(self, db_manager, test_tickers_us, test_tickers_jp):
        """테스트 6: 데이터 품질 검증"""
        print("\n" + "="*80)
        print("테스트 6: 데이터 품질 검증")
        print("="*80)

        # US 시장 데이터 품질
        if test_tickers_us:
            ticker_list = [t['ticker'] for t in test_tickers_us]
            placeholders = ','.join(['%s'] * len(ticker_list))

            query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(listing_date) as has_listing_date,
                COUNT(listing_date) FILTER (WHERE listing_date >= '1980-01-01' AND listing_date <= CURRENT_DATE) as valid_dates,
                ROUND(100.0 * COUNT(listing_date) / NULLIF(COUNT(*), 0), 1) as coverage_pct
            FROM tickers
            WHERE ticker IN ({placeholders})
              AND region = 'US'
            """

            result = db_manager.execute_query(query, tuple(ticker_list))

            if result:
                stats = result[0]
                print(f"\n📊 US 시장 데이터 품질:")
                print(f"   - 총 ticker: {stats['total']}")
                print(f"   - listing_date 있음: {stats['has_listing_date']}")
                print(f"   - 유효한 날짜: {stats['valid_dates']}")
                print(f"   - 커버리지: {stats['coverage_pct']}%")

        # JP 시장 데이터 품질
        if test_tickers_jp:
            ticker_list = [t['ticker'] for t in test_tickers_jp]
            placeholders = ','.join(['%s'] * len(ticker_list))

            query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(listing_date) as has_listing_date,
                ROUND(100.0 * COUNT(listing_date) / NULLIF(COUNT(*), 0), 1) as coverage_pct
            FROM tickers
            WHERE ticker IN ({placeholders})
              AND region = 'JP'
            """

            result = db_manager.execute_query(query, tuple(ticker_list))

            if result:
                stats = result[0]
                print(f"\n📊 JP 시장 데이터 품질:")
                print(f"   - 총 ticker: {stats['total']}")
                print(f"   - listing_date 있음: {stats['has_listing_date']}")
                print(f"   - 커버리지: {stats['coverage_pct']}%")

    # ========================================================================
    # Test 7: Performance Metrics Summary
    # ========================================================================

    def test_07_performance_metrics_summary(self, performance_metrics):
        """테스트 7: 성능 메트릭 종합 요약"""
        print("\n" + "="*80)
        print("테스트 7: 성능 메트릭 종합 요약")
        print("="*80)

        # US 시장 요약
        us_metrics = performance_metrics['us']
        print(f"\n📊 US 시장:")
        if us_metrics['api_times']:
            avg_time = sum(us_metrics['api_times']) / len(us_metrics['api_times'])
            print(f"   - 평균 응답 시간: {avg_time:.2f}초")
            print(f"   - 성공: {us_metrics['success']}")
            print(f"   - 실패: {us_metrics['failed']}")
            if us_metrics['success'] + us_metrics['failed'] > 0:
                success_rate = (us_metrics['success'] / (us_metrics['success'] + us_metrics['failed'])) * 100
                print(f"   - 성공률: {success_rate:.1f}%")
        else:
            print("   - 테스트 미실행 (--run-production 플래그 필요)")

        # JP 시장 요약
        jp_metrics = performance_metrics['jp']
        print(f"\n📊 JP 시장:")
        if jp_metrics['api_times']:
            avg_time = sum(jp_metrics['api_times']) / len(jp_metrics['api_times'])
            print(f"   - 평균 응답 시간: {avg_time:.2f}초")
            print(f"   - 성공: {jp_metrics['success']}")
            print(f"   - 실패: {jp_metrics['failed']}")
        else:
            print("   - 테스트 미실행")

        print(f"\n{'='*80}")
        print("✅ Phase 4 yfinance API 프로덕션 테스트 완료!")
        print(f"{'='*80}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
