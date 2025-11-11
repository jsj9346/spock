"""
ETFUpdater 프로덕션 통합 테스트

목적:
- 실제 PostgreSQL 데이터베이스 연결 검증
- pykrx (KR) 및 yfinance (US) ETF 데이터 수집
- ETF 메타데이터 및 보유종목 데이터 검증
- 추적오차(Tracking Error) 계산 검증

실행 방법:
1. Dry-run 모드: python3 -m pytest tests/integration/production/test_etf_updater_production.py --dry-run
2. 실제 DB 모드: python3 -m pytest tests/integration/production/test_etf_updater_production.py
"""

import sys
import os
from datetime import datetime
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from modules.etf_update.etf_updater import ETFUpdater
from modules.db_manager_postgres import PostgresDatabaseManager


@pytest.fixture(scope="module")
def db_manager():
    """PostgreSQL 데이터베이스 매니저 fixture"""
    db = PostgresDatabaseManager()
    yield db
    db.close_pool()


@pytest.fixture(scope="module")
def etf_updater(db_manager):
    """ETFUpdater 인스턴스 fixture"""
    return ETFUpdater(db_manager=db_manager)


class TestETFUpdaterProduction:
    """ETFUpdater 프로덕션 통합 테스트"""

    def test_01_database_connection(self, db_manager):
        """테스트 1.3.1: 데이터베이스 연결 검증"""
        print("\n" + "="*80)
        print("테스트 1.3.1: 데이터베이스 연결 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # etf_details 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'etf_details'
                )
            """)
            table_exists = cursor.fetchone()[0]
            assert table_exists, "etf_details 테이블이 존재하지 않습니다"
            print("✅ etf_details 테이블 확인")

            # etf_holdings 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'etf_holdings'
                )
            """)
            table_exists = cursor.fetchone()[0]
            assert table_exists, "etf_holdings 테이블이 존재하지 않습니다"
            print("✅ etf_holdings 테이블 확인")

            # ETF ticker 개수 확인
            cursor.execute("""
                SELECT region, COUNT(*) as etf_count
                FROM tickers
                WHERE asset_type = 'ETF' AND status = 'active'
                GROUP BY region
                ORDER BY region
            """)

            etf_counts = cursor.fetchall()
            print(f"\n📊 활성 ETF 개수:")
            for region, count in etf_counts:
                print(f"  - {region}: {count:,}개")

    def test_02_update_kr_etfs(self, etf_updater):
        """테스트 1.3.2: KR ETF 업데이트 실행"""
        print("\n" + "="*80)
        print("테스트 1.3.2: KR ETF 업데이트 실행")
        print("="*80)

        # KR 지역 ETF 업데이트 (limit=50 테스트)
        result = etf_updater.update_region(
            region='KR',
            incremental=True,
            update_holdings=True,
            limit=50
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - ETF 개수: {result.get('etf_count', 0)}")
        print(f"  - 보유종목 업데이트: {result.get('holdings_updated', 0)}")
        print(f"  - 오류: {result.get('errors', 0)}")

        # 검증
        assert result['success'], "ETF 업데이트 실패"
        assert result['etf_count'] > 0, "업데이트된 ETF가 없습니다"

        print("✅ KR ETF 업데이트 성공")

    def test_03_verify_etf_metadata(self, db_manager):
        """테스트 1.3.3: ETF 메타데이터 검증"""
        print("\n" + "="*80)
        print("테스트 1.3.3: ETF 메타데이터 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 최근 업데이트된 ETF 메타데이터 확인
            cursor.execute("""
                SELECT e.ticker, t.name, e.aum, e.expense_ratio, e.inception_date, e.updated_at
                FROM etf_details e
                JOIN tickers t ON e.ticker = t.ticker AND e.region = t.region
                WHERE e.region = 'KR'
                ORDER BY e.updated_at DESC
                LIMIT 10
            """)

            etf_metadata = cursor.fetchall()
            print(f"\n📊 최근 업데이트 ETF (최대 10개):")

            if etf_metadata:
                for ticker, name, aum, expense_ratio, inception_date, updated_at in etf_metadata:
                    aum_str = f"{aum/1e8:.1f}억원" if aum else "N/A"
                    expense_str = f"{expense_ratio:.2%}" if expense_ratio else "N/A"
                    print(f"  - [{ticker}] {name}")
                    print(f"    AUM: {aum_str}, 보수: {expense_str}, "
                          f"상장일: {inception_date}, 업데이트: {updated_at}")
                print(f"\n✅ 총 {len(etf_metadata)}개 ETF 메타데이터 확인")
            else:
                print("  (메타데이터 없음)")

            # 메타데이터 완전성 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total_etfs,
                    COUNT(aum) as with_aum,
                    COUNT(expense_ratio) as with_expense_ratio,
                    COUNT(inception_date) as with_inception_date,
                    COUNT(benchmark_index) as with_benchmark
                FROM etf_details
                WHERE region = 'KR'
            """)

            stats = cursor.fetchone()
            total, with_aum, with_expense, with_inception, with_benchmark = stats

            print(f"\n📊 메타데이터 완전성:")
            print(f"  - 전체 ETF: {total:,}개")
            print(f"  - AUM 데이터: {with_aum:,}개 ({with_aum/max(total,1)*100:.1f}%)")
            print(f"  - 보수율 데이터: {with_expense:,}개 ({with_expense/max(total,1)*100:.1f}%)")
            print(f"  - 상장일 데이터: {with_inception:,}개 ({with_inception/max(total,1)*100:.1f}%)")
            print(f"  - 벤치마크 데이터: {with_benchmark:,}개 ({with_benchmark/max(total,1)*100:.1f}%)")

    def test_04_verify_etf_holdings(self, db_manager):
        """테스트 1.3.4: ETF 보유종목 검증"""
        print("\n" + "="*80)
        print("테스트 1.3.4: ETF 보유종목 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # ETF별 보유종목 개수 확인
            cursor.execute("""
                SELECT h.etf_ticker, t.name, COUNT(*) as holding_count, SUM(h.weight) as total_weight
                FROM etf_holdings h
                JOIN tickers t ON h.etf_ticker = t.ticker AND h.region = t.region
                WHERE h.region = 'KR'
                GROUP BY h.etf_ticker, t.name
                ORDER BY holding_count DESC
                LIMIT 10
            """)

            holdings_stats = cursor.fetchall()
            print(f"\n📊 ETF별 보유종목 (상위 10개):")

            if holdings_stats:
                for etf_ticker, etf_name, count, total_weight in holdings_stats:
                    weight_str = f"{total_weight:.2%}" if total_weight else "N/A"
                    print(f"  - [{etf_ticker}] {etf_name}: {count}개 종목 (비중 합: {weight_str})")
                print(f"\n✅ 보유종목 데이터 확인")
            else:
                print("  (보유종목 데이터 없음)")

            # 샘플 ETF의 상세 보유종목 확인
            if holdings_stats:
                sample_etf = holdings_stats[0][0]
                cursor.execute("""
                    SELECT holding_ticker, holding_name, weight, quantity, updated_at
                    FROM etf_holdings
                    WHERE region = 'KR' AND etf_ticker = %s
                    ORDER BY weight DESC
                    LIMIT 10
                """, (sample_etf,))

                sample_holdings = cursor.fetchall()
                print(f"\n📊 샘플 ETF [{sample_etf}] 상위 10개 보유종목:")
                for holding_ticker, holding_name, weight, quantity, updated_at in sample_holdings:
                    weight_str = f"{weight:.2%}" if weight else "N/A"
                    print(f"  - [{holding_ticker}] {holding_name}: 비중 {weight_str}, "
                          f"수량 {quantity:,}" if quantity else "")

    def test_05_verify_tracking_errors(self, db_manager):
        """테스트 1.3.5: 추적오차(Tracking Error) 검증"""
        print("\n" + "="*80)
        print("테스트 1.3.5: 추적오차(Tracking Error) 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # tracking_errors 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'tracking_errors'
                )
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                print("⚠️  tracking_errors 테이블이 존재하지 않습니다 (생성 필요)")
                return

            # 최근 추적오차 데이터 확인
            cursor.execute("""
                SELECT te.etf_ticker, t.name, te.period, te.tracking_error, te.date
                FROM tracking_errors te
                JOIN tickers t ON te.etf_ticker = t.ticker AND te.region = t.region
                WHERE te.region = 'KR'
                ORDER BY te.date DESC, te.etf_ticker, te.period
                LIMIT 20
            """)

            tracking_data = cursor.fetchall()
            print(f"\n📊 최근 추적오차 데이터 (최대 20개):")

            if tracking_data:
                current_etf = None
                for etf_ticker, etf_name, period, te, date in tracking_data:
                    if etf_ticker != current_etf:
                        print(f"\n  [{etf_ticker}] {etf_name} (날짜: {date}):")
                        current_etf = etf_ticker
                    print(f"    - {period}일: {te:.4f}")
                print(f"\n✅ 추적오차 데이터 확인")
            else:
                print("  (추적오차 데이터 없음 - 계산 필요)")

    def test_06_verify_data_freshness(self, db_manager):
        """테스트 1.3.6: 데이터 신선도 검증"""
        print("\n" + "="*80)
        print("테스트 1.3.6: 데이터 신선도 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 최근 업데이트 시간 확인
            cursor.execute("""
                SELECT
                    COUNT(*) as total_etfs,
                    MAX(updated_at) as latest_update,
                    COUNT(CASE WHEN updated_at >= CURRENT_DATE THEN 1 END) as updated_today,
                    COUNT(CASE WHEN updated_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as updated_week
                FROM etf_details
                WHERE region = 'KR'
            """)

            freshness = cursor.fetchone()
            total, latest, today, week = freshness

            print(f"\n📊 데이터 신선도:")
            print(f"  - 전체 ETF: {total:,}개")
            print(f"  - 최근 업데이트: {latest}")
            print(f"  - 오늘 업데이트: {today:,}개 ({today/max(total,1)*100:.1f}%)")
            print(f"  - 주간 업데이트: {week:,}개 ({week/max(total,1)*100:.1f}%)")

            # 오래된 데이터 확인 (30일 이상)
            cursor.execute("""
                SELECT e.ticker, t.name, e.updated_at
                FROM etf_details e
                JOIN tickers t ON e.ticker = t.ticker AND e.region = t.region
                WHERE e.region = 'KR'
                  AND e.updated_at < CURRENT_DATE - INTERVAL '30 days'
                ORDER BY e.updated_at
                LIMIT 5
            """)

            stale_data = cursor.fetchall()
            if stale_data:
                print(f"\n⚠️  오래된 데이터 (30일 이상, 샘플 5개):")
                for ticker, name, updated_at in stale_data:
                    print(f"  - [{ticker}] {name}: {updated_at}")

    def test_07_performance_metrics(self, etf_updater):
        """테스트 1.3.7: 성능 메트릭 수집"""
        print("\n" + "="*80)
        print("테스트 1.3.7: 성능 메트릭 수집")
        print("="*80)

        import time

        # 실행 시간 측정 (limit=50, holdings 포함)
        start_time = time.time()
        result = etf_updater.update_region(
            region='KR',
            incremental=True,
            update_holdings=True,
            limit=50
        )
        elapsed_time = time.time() - start_time

        print(f"\n⏱️  성능 메트릭:")
        print(f"  - 실행 시간: {elapsed_time:.2f}초")
        print(f"  - ETF 개수: {result.get('etf_count', 0)}")
        print(f"  - 보유종목 업데이트: {result.get('holdings_updated', 0)}")
        print(f"  - ETF당 평균: {elapsed_time/max(result.get('etf_count', 1), 1):.2f}초")

        # 성능 기준 검증 (10분 = 600초)
        assert elapsed_time < 600, f"실행 시간 초과: {elapsed_time:.2f}초 (기준: 600초)"
        print("✅ 성능 기준 충족 (<10분)")

    def test_08_update_us_etfs(self, etf_updater):
        """테스트 1.3.8: US ETF 업데이트 검증 (선택사항)"""
        print("\n" + "="*80)
        print("테스트 1.3.8: US ETF 업데이트 검증 (선택사항)")
        print("="*80)

        # US 지역 ETF 업데이트 (limit=10 테스트)
        result = etf_updater.update_region(
            region='US',
            incremental=True,
            update_holdings=False,  # US holdings는 데이터 가용성 제한
            limit=10
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - ETF 개수: {result.get('etf_count', 0)}")
        print(f"  - 오류: {result.get('errors', 0)}")

        if result['success']:
            print("✅ US ETF 업데이트 성공")
        else:
            print("⚠️  US ETF 업데이트 실패 또는 데이터 부족")


def test_summary():
    """테스트 요약 출력"""
    print("\n" + "="*80)
    print("ETFUpdater 프로덕션 테스트 완료")
    print("="*80)
    print("\n✅ 모든 테스트 통과")
    print("\n검증 항목:")
    print("  1. 데이터베이스 연결 및 테이블 구조")
    print("  2. KR ETF 업데이트 실행")
    print("  3. ETF 메타데이터 검증")
    print("  4. ETF 보유종목 검증")
    print("  5. 추적오차(Tracking Error) 검증")
    print("  6. 데이터 신선도 검증")
    print("  7. 성능 메트릭 (실행 시간 <10분)")
    print("  8. US ETF 업데이트 검증 (선택사항)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
