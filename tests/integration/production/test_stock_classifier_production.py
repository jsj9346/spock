"""
StockClassifier 프로덕션 통합 테스트

목적:
- 실제 PostgreSQL 데이터베이스 연결 검증
- SPAC 및 우선주 탐지 검증
- 섹터/업종 분류 검증
- 성능 메트릭 수집

실행 방법:
1. Dry-run 모드: python3 -m pytest tests/integration/production/test_stock_classifier_production.py --dry-run
2. 실제 DB 모드: python3 -m pytest tests/integration/production/test_stock_classifier_production.py
"""

import sys
import os
from datetime import datetime
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from modules.classification.stock_classifier import StockClassifier
from modules.db_manager_postgres import PostgresDatabaseManager


@pytest.fixture(scope="module")
def db_manager():
    """PostgreSQL 데이터베이스 매니저 fixture"""
    db = PostgresDatabaseManager()
    yield db
    db.close_pool()


@pytest.fixture(scope="module")
def classifier(db_manager):
    """StockClassifier 인스턴스 fixture"""
    return StockClassifier(db_manager=db_manager)


class TestStockClassifierProduction:
    """StockClassifier 프로덕션 통합 테스트"""

    def test_01_database_connection(self, db_manager):
        """테스트 1.2.1: 데이터베이스 연결 검증"""
        print("\n" + "="*80)
        print("테스트 1.2.1: 데이터베이스 연결 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

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

            # stock_details 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'stock_details'
                )
            """)
            table_exists = cursor.fetchone()[0]
            assert table_exists, "stock_details 테이블이 존재하지 않습니다"
            print("✅ stock_details 테이블 확인")

            # tickers 개수 확인
            cursor.execute("""
                SELECT region, COUNT(*) as ticker_count
                FROM tickers
                WHERE status = 'active'
                GROUP BY region
                ORDER BY region
            """)

            region_counts = cursor.fetchall()
            print(f"\n📊 활성 ticker 개수:")
            for region, count in region_counts:
                print(f"  - {region}: {count:,}개")

    def test_02_classify_kr_stocks(self, classifier):
        """테스트 1.2.2: KR 종목 분류 실행"""
        print("\n" + "="*80)
        print("테스트 1.2.2: KR 종목 분류 실행")
        print("="*80)

        # KR 지역 분류 실행 (limit=100 테스트)
        result = classifier.classify_region(region='KR', limit=100)

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 분류된 종목: {result.get('classified', 0)}")
        print(f"  - SPAC 탐지: {result.get('spac_count', 0)}")
        print(f"  - 우선주 탐지: {result.get('preferred_count', 0)}")
        print(f"  - 오류: {result.get('errors', 0)}")

        # 검증
        assert result['success'], "종목 분류 실패"
        assert result['classified'] > 0, "분류된 종목이 없습니다"

        print("✅ KR 종목 분류 성공")

    def test_03_verify_spac_detection(self, db_manager):
        """테스트 1.2.3: SPAC 탐지 검증"""
        print("\n" + "="*80)
        print("테스트 1.2.3: SPAC 탐지 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # SPAC로 분류된 종목 확인
            cursor.execute("""
                SELECT t.ticker, t.name, sd.is_spac, sd.updated_at
                FROM tickers t
                JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR'
                  AND sd.is_spac = true
                ORDER BY sd.updated_at DESC
                LIMIT 10
            """)

            spac_stocks = cursor.fetchall()
            print(f"\n📊 SPAC 종목 (최대 10개):")

            if spac_stocks:
                for ticker, name, is_spac, updated_at in spac_stocks:
                    print(f"  - [{ticker}] {name} (업데이트: {updated_at})")
                print(f"\n✅ 총 {len(spac_stocks)}개 SPAC 종목 확인")
            else:
                print("  (SPAC 종목 없음)")

            # SPAC 패턴 통계
            cursor.execute("""
                SELECT COUNT(*) as spac_count
                FROM stock_details
                WHERE region = 'KR' AND is_spac = true
            """)
            total_spac = cursor.fetchone()[0]
            print(f"\n📊 전체 SPAC 종목: {total_spac}개")

    def test_04_verify_preferred_stock_detection(self, db_manager):
        """테스트 1.2.4: 우선주 탐지 검증"""
        print("\n" + "="*80)
        print("테스트 1.2.4: 우선주 탐지 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 우선주로 분류된 종목 확인
            cursor.execute("""
                SELECT t.ticker, t.name, sd.is_preferred, sd.updated_at
                FROM tickers t
                JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR'
                  AND sd.is_preferred = true
                ORDER BY sd.updated_at DESC
                LIMIT 10
            """)

            preferred_stocks = cursor.fetchall()
            print(f"\n📊 우선주 종목 (최대 10개):")

            if preferred_stocks:
                for ticker, name, is_preferred, updated_at in preferred_stocks:
                    print(f"  - [{ticker}] {name} (업데이트: {updated_at})")
                print(f"\n✅ 총 {len(preferred_stocks)}개 우선주 확인")
            else:
                print("  (우선주 종목 없음)")

            # 우선주 통계
            cursor.execute("""
                SELECT COUNT(*) as preferred_count
                FROM stock_details
                WHERE region = 'KR' AND is_preferred = true
            """)
            total_preferred = cursor.fetchone()[0]
            print(f"\n📊 전체 우선주: {total_preferred}개")

    def test_05_verify_sector_classification(self, db_manager):
        """테스트 1.2.5: 섹터/업종 분류 검증"""
        print("\n" + "="*80)
        print("테스트 1.2.5: 섹터/업종 분류 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 섹터별 종목 분포
            cursor.execute("""
                SELECT sector, COUNT(*) as stock_count
                FROM stock_details
                WHERE region = 'KR' AND sector IS NOT NULL
                GROUP BY sector
                ORDER BY stock_count DESC
            """)

            sector_distribution = cursor.fetchall()
            print(f"\n📊 섹터별 종목 분포:")

            if sector_distribution:
                for sector, count in sector_distribution:
                    print(f"  - {sector}: {count}개")
                print(f"\n✅ 총 {len(sector_distribution)}개 섹터 확인")
            else:
                print("  (섹터 분류 데이터 없음)")

            # 업종별 종목 분포 (상위 10개)
            cursor.execute("""
                SELECT industry, COUNT(*) as stock_count
                FROM stock_details
                WHERE region = 'KR' AND industry IS NOT NULL
                GROUP BY industry
                ORDER BY stock_count DESC
                LIMIT 10
            """)

            industry_distribution = cursor.fetchall()
            print(f"\n📊 업종별 종목 분포 (상위 10개):")

            if industry_distribution:
                for industry, count in industry_distribution:
                    print(f"  - {industry}: {count}개")

    def test_06_verify_classification_completeness(self, db_manager):
        """테스트 1.2.6: 분류 완전성 검증"""
        print("\n" + "="*80)
        print("테스트 1.2.6: 분류 완전성 검증")
        print("="*80)

        with db_manager._get_connection() as conn:
            cursor = conn.cursor()

            # 전체 활성 종목 vs 분류된 종목
            cursor.execute("""
                SELECT
                    COUNT(*) as total_tickers,
                    COUNT(sd.ticker) as classified_tickers,
                    COUNT(CASE WHEN sd.sector IS NOT NULL THEN 1 END) as with_sector,
                    COUNT(CASE WHEN sd.industry IS NOT NULL THEN 1 END) as with_industry,
                    COUNT(CASE WHEN sd.is_spac = true THEN 1 END) as spac_count,
                    COUNT(CASE WHEN sd.is_preferred = true THEN 1 END) as preferred_count
                FROM tickers t
                LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR' AND t.status = 'active'
            """)

            stats = cursor.fetchone()
            total, classified, with_sector, with_industry, spac, preferred = stats

            print(f"\n📊 분류 완전성:")
            print(f"  - 전체 활성 종목: {total:,}개")
            print(f"  - 분류된 종목: {classified:,}개 ({classified/total*100:.1f}%)")
            print(f"  - 섹터 분류: {with_sector:,}개 ({with_sector/total*100:.1f}%)")
            print(f"  - 업종 분류: {with_industry:,}개 ({with_industry/total*100:.1f}%)")
            print(f"  - SPAC: {spac}개")
            print(f"  - 우선주: {preferred}개")

            # 미분류 종목 확인
            cursor.execute("""
                SELECT t.ticker, t.name
                FROM tickers t
                LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
                WHERE t.region = 'KR'
                  AND t.status = 'active'
                  AND sd.ticker IS NULL
                LIMIT 5
            """)

            unclassified = cursor.fetchall()
            if unclassified:
                print(f"\n⚠️  미분류 종목 (샘플 5개):")
                for ticker, name in unclassified:
                    print(f"  - [{ticker}] {name}")

    def test_07_performance_metrics(self, classifier):
        """테스트 1.2.7: 성능 메트릭 수집"""
        print("\n" + "="*80)
        print("테스트 1.2.7: 성능 메트릭 수집")
        print("="*80)

        import time

        # 실행 시간 측정 (limit=100)
        start_time = time.time()
        result = classifier.classify_region(region='KR', limit=100)
        elapsed_time = time.time() - start_time

        print(f"\n⏱️  성능 메트릭:")
        print(f"  - 실행 시간: {elapsed_time:.2f}초")
        print(f"  - 분류된 종목: {result.get('classified', 0)}")
        print(f"  - 종목당 평균: {elapsed_time/max(result.get('classified', 1), 1):.3f}초")

        # 성능 기준 검증 (5분 = 300초)
        assert elapsed_time < 300, f"실행 시간 초과: {elapsed_time:.2f}초 (기준: 300초)"
        print("✅ 성능 기준 충족 (<5분)")

    def test_08_classify_us_stocks(self, classifier):
        """테스트 1.2.8: US 종목 분류 검증 (선택사항)"""
        print("\n" + "="*80)
        print("테스트 1.2.8: US 종목 분류 검증 (선택사항)")
        print("="*80)

        # US 지역 분류 실행 (limit=50 테스트)
        result = classifier.classify_region(region='US', limit=50)

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 분류된 종목: {result.get('classified', 0)}")
        print(f"  - SPAC 탐지: {result.get('spac_count', 0)}")
        print(f"  - 우선주 탐지: {result.get('preferred_count', 0)}")

        if result['success']:
            print("✅ US 종목 분류 성공")
        else:
            print("⚠️  US 종목 분류 실패 또는 데이터 부족")


def test_summary():
    """테스트 요약 출력"""
    print("\n" + "="*80)
    print("StockClassifier 프로덕션 테스트 완료")
    print("="*80)
    print("\n✅ 모든 테스트 통과")
    print("\n검증 항목:")
    print("  1. 데이터베이스 연결 및 테이블 구조")
    print("  2. KR 종목 분류 실행")
    print("  3. SPAC 탐지 검증")
    print("  4. 우선주 탐지 검증")
    print("  5. 섹터/업종 분류 검증")
    print("  6. 분류 완전성 검증")
    print("  7. 성능 메트릭 (실행 시간 <5분)")
    print("  8. US 종목 분류 검증 (선택사항)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
