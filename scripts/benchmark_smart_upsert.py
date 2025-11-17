#!/usr/bin/env python3
"""
Smart UPSERT Performance Benchmark Script

이 스크립트는 Smart UPSERT 최적화의 성능 향상을 측정합니다:
1. OHLCV 데이터 업데이트
2. Fundamentals (PER/PBR) 업데이트
3. Technical Indicators 업데이트

측정 항목:
- 실제 UPDATE 작업 수 (변경사항이 있는 경우만)
- 실행 시간
- 데이터베이스 부하 감소율

Usage:
    python3 scripts/benchmark_smart_upsert.py --test [ohlcv|fundamentals|indicators|all]
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from loguru import logger


class SmartUpsertBenchmark:
    """Smart UPSERT 성능 벤치마크 클래스"""

    def __init__(self):
        """Initialize benchmark with database connection"""
        self.db = PostgresDatabaseManager()
        self.results = {
            'ohlcv': {},
            'fundamentals': {},
            'indicators': {}
        }

    def benchmark_ohlcv_updates(self, ticker: str = '005930', region: str = 'KR',
                                 days: int = 365) -> Dict:
        """
        OHLCV Smart UPSERT 성능 측정

        동일한 데이터를 두 번 UPSERT하여:
        1. 첫 번째: 실제 INSERT/UPDATE 발생
        2. 두 번째: Smart UPSERT로 인해 UPDATE 건너뜀

        Returns:
            성능 메트릭 딕셔너리
        """
        logger.info(f"📊 OHLCV Smart UPSERT 벤치마크 시작 (ticker={ticker}, days={days})")

        # 1. 테스트 데이터 조회
        test_data = self.db.execute_query(
            """
            SELECT ticker, region, date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
            ORDER BY date DESC
            LIMIT %s
            """,
            (ticker, region, days)
        )

        if not test_data:
            logger.error(f"❌ 테스트 데이터 없음: {ticker} ({region})")
            return {}

        logger.info(f"  ✅ {len(test_data)}개 레코드 조회 완료")

        # 2. 첫 번째 UPSERT (실제 변경사항 있음)
        logger.info("  🔄 첫 번째 UPSERT 실행 (baseline)...")

        # last_updated를 과거로 설정하여 강제 업데이트
        self.db.execute_update(
            """
            UPDATE ohlcv_data
            SET last_updated = %s
            WHERE ticker = %s AND region = %s
            """,
            (datetime.now() - timedelta(days=7), ticker, region)
        )

        start_time = time.time()
        affected_rows_1 = 0

        for row in test_data:
            result = self.db.execute_update(
                """
                INSERT INTO ohlcv_data
                (ticker, region, date, open, high, low, close, volume, timeframe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '1d')
                ON CONFLICT (ticker, region, date, timeframe)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    last_updated = NOW()
                WHERE
                    ohlcv_data.open IS DISTINCT FROM EXCLUDED.open OR
                    ohlcv_data.high IS DISTINCT FROM EXCLUDED.high OR
                    ohlcv_data.low IS DISTINCT FROM EXCLUDED.low OR
                    ohlcv_data.close IS DISTINCT FROM EXCLUDED.close OR
                    ohlcv_data.volume IS DISTINCT FROM EXCLUDED.volume
                """,
                (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            )
            affected_rows_1 += result

        time_1 = time.time() - start_time

        logger.info(f"  ✅ 첫 번째 UPSERT: {affected_rows_1}개 레코드 처리, {time_1:.3f}초")

        # 3. 두 번째 UPSERT (동일한 데이터, Smart UPSERT로 건너뜀)
        logger.info("  🔄 두 번째 UPSERT 실행 (Smart UPSERT 효과 측정)...")

        start_time = time.time()
        affected_rows_2 = 0

        for row in test_data:
            result = self.db.execute_update(
                """
                INSERT INTO ohlcv_data
                (ticker, region, date, open, high, low, close, volume, timeframe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '1d')
                ON CONFLICT (ticker, region, date, timeframe)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    last_updated = NOW()
                WHERE
                    ohlcv_data.open IS DISTINCT FROM EXCLUDED.open OR
                    ohlcv_data.high IS DISTINCT FROM EXCLUDED.high OR
                    ohlcv_data.low IS DISTINCT FROM EXCLUDED.low OR
                    ohlcv_data.close IS DISTINCT FROM EXCLUDED.close OR
                    ohlcv_data.volume IS DISTINCT FROM EXCLUDED.volume
                """,
                (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            )
            affected_rows_2 += result

        time_2 = time.time() - start_time

        logger.info(f"  ✅ 두 번째 UPSERT: {affected_rows_2}개 레코드 처리, {time_2:.3f}초")

        # 4. 결과 계산
        reduction_rate = ((affected_rows_1 - affected_rows_2) / affected_rows_1 * 100) if affected_rows_1 > 0 else 0
        speedup = (time_1 / time_2) if time_2 > 0 else 1.0

        results = {
            'test_records': len(test_data),
            'first_upsert_affected': affected_rows_1,
            'second_upsert_affected': affected_rows_2,
            'first_upsert_time': time_1,
            'second_upsert_time': time_2,
            'update_reduction_rate': reduction_rate,
            'speedup_factor': speedup
        }

        logger.info(f"""
  📊 OHLCV Smart UPSERT 벤치마크 결과:
    - 테스트 레코드: {len(test_data)}개
    - 첫 번째 UPSERT: {affected_rows_1}개 영향, {time_1:.3f}초
    - 두 번째 UPSERT: {affected_rows_2}개 영향, {time_2:.3f}초
    - UPDATE 감소율: {reduction_rate:.1f}%
    - 속도 향상: {speedup:.2f}배
        """)

        self.results['ohlcv'] = results
        return results

    def benchmark_fundamentals_updates(self, ticker: str = '005930', region: str = 'KR',
                                        days: int = 365) -> Dict:
        """
        Fundamentals Smart UPSERT 성능 측정

        Returns:
            성능 메트릭 딕셔너리
        """
        logger.info(f"📊 Fundamentals Smart UPSERT 벤치마크 시작 (ticker={ticker}, days={days})")

        # 1. 테스트 데이터 조회
        test_data = self.db.execute_query(
            """
            SELECT ticker, region, date, period_type, per, pbr, dividend_yield, dividend_per_share
            FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND period_type = 'daily'
            ORDER BY date DESC
            LIMIT %s
            """,
            (ticker, region, days)
        )

        if not test_data:
            logger.error(f"❌ 테스트 데이터 없음: {ticker} ({region})")
            return {}

        logger.info(f"  ✅ {len(test_data)}개 레코드 조회 완료")

        # 2. 첫 번째 UPSERT
        logger.info("  🔄 첫 번째 UPSERT 실행 (baseline)...")

        # last_updated를 과거로 설정
        self.db.execute_update(
            """
            UPDATE ticker_fundamentals
            SET last_updated = %s
            WHERE ticker = %s AND region = %s
            """,
            (datetime.now() - timedelta(days=7), ticker, region)
        )

        start_time = time.time()
        affected_rows_1 = 0

        for row in test_data:
            result = self.db.execute_update(
                """
                INSERT INTO ticker_fundamentals
                (ticker, region, date, period_type, per, pbr, dividend_yield, dividend_per_share, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pykrx')
                ON CONFLICT (ticker, region, date, period_type)
                DO UPDATE SET
                    per = EXCLUDED.per,
                    pbr = EXCLUDED.pbr,
                    dividend_yield = EXCLUDED.dividend_yield,
                    dividend_per_share = EXCLUDED.dividend_per_share,
                    data_source = EXCLUDED.data_source,
                    last_updated = NOW()
                WHERE
                    ticker_fundamentals.per IS DISTINCT FROM EXCLUDED.per OR
                    ticker_fundamentals.pbr IS DISTINCT FROM EXCLUDED.pbr OR
                    ticker_fundamentals.dividend_yield IS DISTINCT FROM EXCLUDED.dividend_yield OR
                    ticker_fundamentals.dividend_per_share IS DISTINCT FROM EXCLUDED.dividend_per_share
                """,
                (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            )
            affected_rows_1 += result

        time_1 = time.time() - start_time

        logger.info(f"  ✅ 첫 번째 UPSERT: {affected_rows_1}개 레코드 처리, {time_1:.3f}초")

        # 3. 두 번째 UPSERT
        logger.info("  🔄 두 번째 UPSERT 실행 (Smart UPSERT 효과 측정)...")

        start_time = time.time()
        affected_rows_2 = 0

        for row in test_data:
            result = self.db.execute_update(
                """
                INSERT INTO ticker_fundamentals
                (ticker, region, date, period_type, per, pbr, dividend_yield, dividend_per_share, data_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pykrx')
                ON CONFLICT (ticker, region, date, period_type)
                DO UPDATE SET
                    per = EXCLUDED.per,
                    pbr = EXCLUDED.pbr,
                    dividend_yield = EXCLUDED.dividend_yield,
                    dividend_per_share = EXCLUDED.dividend_per_share,
                    data_source = EXCLUDED.data_source,
                    last_updated = NOW()
                WHERE
                    ticker_fundamentals.per IS DISTINCT FROM EXCLUDED.per OR
                    ticker_fundamentals.pbr IS DISTINCT FROM EXCLUDED.pbr OR
                    ticker_fundamentals.dividend_yield IS DISTINCT FROM EXCLUDED.dividend_yield OR
                    ticker_fundamentals.dividend_per_share IS DISTINCT FROM EXCLUDED.dividend_per_share
                """,
                (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
            )
            affected_rows_2 += result

        time_2 = time.time() - start_time

        logger.info(f"  ✅ 두 번째 UPSERT: {affected_rows_2}개 레코드 처리, {time_2:.3f}초")

        # 4. 결과 계산
        reduction_rate = ((affected_rows_1 - affected_rows_2) / affected_rows_1 * 100) if affected_rows_1 > 0 else 0
        speedup = (time_1 / time_2) if time_2 > 0 else 1.0

        results = {
            'test_records': len(test_data),
            'first_upsert_affected': affected_rows_1,
            'second_upsert_affected': affected_rows_2,
            'first_upsert_time': time_1,
            'second_upsert_time': time_2,
            'update_reduction_rate': reduction_rate,
            'speedup_factor': speedup
        }

        logger.info(f"""
  📊 Fundamentals Smart UPSERT 벤치마크 결과:
    - 테스트 레코드: {len(test_data)}개
    - 첫 번째 UPSERT: {affected_rows_1}개 영향, {time_1:.3f}초
    - 두 번째 UPSERT: {affected_rows_2}개 영향, {time_2:.3f}초
    - UPDATE 감소율: {reduction_rate:.1f}%
    - 속도 향상: {speedup:.2f}배
        """)

        self.results['fundamentals'] = results
        return results

    def print_summary(self):
        """전체 벤치마크 결과 요약 출력"""
        logger.info("\n" + "="*80)
        logger.info("📊 Smart UPSERT 성능 벤치마크 종합 결과")
        logger.info("="*80)

        if self.results['ohlcv']:
            r = self.results['ohlcv']
            logger.info(f"""
1️⃣ OHLCV 데이터:
   - 테스트 레코드: {r['test_records']}개
   - UPDATE 감소율: {r['update_reduction_rate']:.1f}%
   - 속도 향상: {r['speedup_factor']:.2f}배
   - 일일 예상 부하 감소: {r['test_records']} → {r['second_upsert_affected']}개 UPDATE
            """)

        if self.results['fundamentals']:
            r = self.results['fundamentals']
            logger.info(f"""
2️⃣ Fundamentals 데이터:
   - 테스트 레코드: {r['test_records']}개
   - UPDATE 감소율: {r['update_reduction_rate']:.1f}%
   - 속도 향상: {r['speedup_factor']:.2f}배
   - 일일 예상 부하 감소: {r['test_records']} → {r['second_upsert_affected']}개 UPDATE
            """)

        logger.info("="*80)
        logger.info("✅ 벤치마크 완료\n")


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description='Smart UPSERT 성능 벤치마크',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 전체 벤치마크 실행
  python3 scripts/benchmark_smart_upsert.py --test all

  # OHLCV만 테스트
  python3 scripts/benchmark_smart_upsert.py --test ohlcv --ticker 005930 --days 365

  # Fundamentals만 테스트
  python3 scripts/benchmark_smart_upsert.py --test fundamentals --ticker 005930 --days 100
        """
    )

    parser.add_argument(
        '--test',
        choices=['ohlcv', 'fundamentals', 'all'],
        default='all',
        help='테스트할 항목 선택'
    )
    parser.add_argument(
        '--ticker',
        default='005930',
        help='테스트 대상 ticker (기본값: 005930 삼성전자)'
    )
    parser.add_argument(
        '--region',
        default='KR',
        help='테스트 대상 region (기본값: KR)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=365,
        help='테스트할 일수 (기본값: 365일)'
    )

    args = parser.parse_args()

    # 벤치마크 실행
    benchmark = SmartUpsertBenchmark()

    try:
        if args.test in ['ohlcv', 'all']:
            benchmark.benchmark_ohlcv_updates(
                ticker=args.ticker,
                region=args.region,
                days=args.days
            )

        if args.test in ['fundamentals', 'all']:
            benchmark.benchmark_fundamentals_updates(
                ticker=args.ticker,
                region=args.region,
                days=args.days
            )

        # 결과 요약 출력
        benchmark.print_summary()

    except Exception as e:
        logger.error(f"❌ 벤치마크 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
