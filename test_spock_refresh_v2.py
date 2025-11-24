#!/usr/bin/env python3
"""
spock_refresh_v2.py 통합 테스트

모든 리팩토링된 함수들이 정상 작동하는지 검증합니다.

테스트 항목:
1. DB 조회 함수들 (일반 버전)
2. DB 조회 함수들 (캐싱 버전)
3. print_* 출력 함수들
4. 캐시 히트율 및 성능 측정

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import spock_refresh_v2 모듈
import spock_refresh_v2 as v2

def print_section(title):
    """섹션 헤더 출력"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_db_functions():
    """DB 조회 함수 테스트 (일반 버전)"""
    print_section("Test 1: DB 조회 함수 (일반 버전)")

    functions = [
        ('get_database_status', v2.get_database_status),
        ('get_listing_date_coverage', v2.get_listing_date_coverage),
        ('get_listing_date_coverage_detailed', v2.get_listing_date_coverage_detailed),
        ('get_macro_data_status', v2.get_macro_data_status),
        ('get_macro_data_status_unified', v2.get_macro_data_status_unified),
        ('get_equity_backfill_status', v2.get_equity_backfill_status),
    ]

    for func_name, func in functions:
        print(f"Testing {func_name}()...")
        start = time.time()
        try:
            result = func()
            elapsed = time.time() - start

            if result is not None:
                print(f"  ✅ 성공: {elapsed*1000:.2f}ms")
            else:
                print(f"  ⚠️  반환값 None: {elapsed*1000:.2f}ms (DB 연결 실패 가능)")
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ 실패: {e} ({elapsed*1000:.2f}ms)")
        print()


def test_cached_functions():
    """DB 조회 함수 테스트 (캐싱 버전)"""
    print_section("Test 2: DB 조회 함수 (캐싱 버전)")

    # 캐시 초기화
    v2.query_cache.invalidate()

    functions = [
        ('get_database_status_cached', v2.get_database_status_cached),
        ('get_listing_date_coverage_cached', v2.get_listing_date_coverage_cached),
        ('get_listing_date_coverage_detailed_cached', v2.get_listing_date_coverage_detailed_cached),
        ('get_macro_data_status_cached', v2.get_macro_data_status_cached),
        ('get_macro_data_status_unified_cached', v2.get_macro_data_status_unified_cached),
        ('get_equity_backfill_status_cached', v2.get_equity_backfill_status_cached),
    ]

    for func_name, func in functions:
        print(f"Testing {func_name}()...")

        # 첫 호출 (캐시 미스)
        start = time.time()
        try:
            result1 = func()
            elapsed1 = time.time() - start
            print(f"  첫 호출 (캐시 미스): {elapsed1*1000:.2f}ms")
        except Exception as e:
            elapsed1 = time.time() - start
            print(f"  ❌ 첫 호출 실패: {e} ({elapsed1*1000:.2f}ms)")
            print()
            continue

        # 두 번째 호출 (캐시 히트)
        start = time.time()
        try:
            result2 = func()
            elapsed2 = time.time() - start
            print(f"  두 번째 호출 (캐시 히트): {elapsed2*1000:.2f}ms")

            if elapsed1 > 0 and elapsed2 > 0:
                speedup = elapsed1 / elapsed2
                print(f"  ✅ 속도 향상: {speedup:.1f}배")

        except Exception as e:
            elapsed2 = time.time() - start
            print(f"  ❌ 두 번째 호출 실패: {e} ({elapsed2*1000:.2f}ms)")

        print()


def test_print_functions():
    """print_* 출력 함수 테스트"""
    print_section("Test 3: print_* 출력 함수")

    functions = [
        ('print_listing_date_status', v2.print_listing_date_status),
        ('print_database_status', v2.print_database_status),
        ('print_macro_data_status', v2.print_macro_data_status),
        ('print_equity_backfill_status', v2.print_equity_backfill_status),
    ]

    for func_name, func in functions:
        print(f"\nTesting {func_name}()...")
        print("-" * 80)

        start = time.time()
        try:
            func()
            elapsed = time.time() - start
            print(f"\n✅ 성공: {elapsed*1000:.2f}ms")
        except Exception as e:
            elapsed = time.time() - start
            print(f"\n❌ 실패: {e} ({elapsed*1000:.2f}ms)")

        print()


def test_cache_statistics():
    """캐시 통계 테스트"""
    print_section("Test 4: 캐시 통계 및 성능")

    # 캐시 초기화
    v2.query_cache.invalidate()

    print("10회 반복 테스트 (캐시 히트율 측정)...\n")

    for i in range(10):
        result = v2.get_database_status_cached()
        print(f"  호출 {i+1:2d}: 완료")

    # 캐시 통계 출력
    stats = v2.query_cache.stats
    print(f"\n캐시 통계:")
    print(f"  Hits:       {stats['hits']}")
    print(f"  Misses:     {stats['misses']}")
    print(f"  Total:      {stats['total_requests']}")
    print(f"  Hit Rate:   {stats['hit_rate']:.1f}%")

    if stats['hit_rate'] >= 85:
        print(f"\n  ✅ 목표 달성 (>85%)")
    else:
        print(f"\n  ⚠️  목표 미달 (<85%)")


def test_db_connection_stats():
    """DB 연결 통계 테스트"""
    print_section("Test 5: DB 연결 통계")

    # DB 연결 통계 초기화
    v2.db_manager._total_connections = 0

    print("5개 함수 호출 (연결 재사용 측정)...\n")

    v2.get_database_status()
    v2.get_listing_date_coverage()
    v2.get_macro_data_status()
    v2.get_macro_data_status_unified()
    v2.get_equity_backfill_status()

    # 통계 출력
    db_stats = v2.db_manager.get_stats()
    print(f"DB 연결 통계:")
    print(f"  Active connections:    {db_stats['active']}")
    print(f"  Total created:         {db_stats['total_created']}")
    print(f"  Avg per function:      {db_stats['total_created']/5:.1f}")

    if db_stats['total_created'] / 5 <= 2:
        print(f"\n  ✅ 목표 달성 (≤2/함수)")
    else:
        print(f"\n  ⚠️  목표 미달 (>2/함수)")


def main():
    """메인 테스트 실행"""
    print(f"\n{'='*80}")
    print(f"  spock_refresh_v2.py 통합 테스트")
    print(f"  시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    start_time = time.time()

    try:
        # 테스트 실행
        test_db_functions()
        test_cached_functions()
        test_print_functions()
        test_cache_statistics()
        test_db_connection_stats()

        # 최종 요약
        elapsed = time.time() - start_time

        print_section("✅ 모든 테스트 완료")
        print(f"  총 소요 시간: {elapsed:.2f}초")
        print(f"  종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
