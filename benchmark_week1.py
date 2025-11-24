#!/usr/bin/env python3
"""
Week 1 Performance Benchmark

목적:
- Before/After 성능 비교
- DB 연결 수 모니터링
- 캐시 히트율 측정
- 메모리 사용량 프로파일링

측정 항목:
1. 상태 조회 시간 (목표: 500ms → 200ms)
2. DB 연결 수 (목표: 10개 → 1-2개 재사용)
3. 캐시 히트율 (목표: >85%)
4. 메모리 증가 (허용: <10MB)

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
import psutil
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def print_header(title: str):
    """헤더 출력"""
    print(f"\n{'='*80}")
    print(f"{Fore.CYAN + Style.BRIGHT}{title}")
    print(f"{'='*80}\n")


def print_result(label: str, value: str, color=Fore.WHITE):
    """결과 출력"""
    print(f"  {label:<30} {color}{value}{Style.RESET_ALL}")


def benchmark_database_status():
    """데이터베이스 상태 조회 벤치마크"""

    print_header("1. Database Status Query Benchmark")

    try:
        # Import old version
        import spock_refresh
        old_func = spock_refresh.get_database_status

        # Import new version
        import spock_refresh_v2
        new_func = spock_refresh_v2.get_database_status
        new_func_cached = spock_refresh_v2.get_database_status_cached
        query_cache = spock_refresh_v2.query_cache
        db_manager = spock_refresh_v2.db_manager

    except Exception as e:
        print(f"{Fore.RED}❌ Import failed: {e}")
        return

    iterations = 5  # 5회 측정

    # ========================================================================
    # Test 1: Original Version
    # ========================================================================
    print(f"{Fore.YELLOW}Test 1: Original Version (spock_refresh.py)")
    print("-" * 80)

    times_old = []
    for i in range(iterations):
        start = time.time()
        result = old_func()
        elapsed = time.time() - start
        times_old.append(elapsed)

        status = "✅" if result is not None else "❌"
        print(f"  Run {i+1}: {status} {elapsed*1000:.2f}ms")

    avg_old = sum(times_old) / len(times_old)
    min_old = min(times_old)
    max_old = max(times_old)

    print()
    print_result("Average:", f"{avg_old*1000:.2f}ms", Fore.CYAN)
    print_result("Min:", f"{min_old*1000:.2f}ms", Fore.GREEN)
    print_result("Max:", f"{max_old*1000:.2f}ms", Fore.RED)

    # ========================================================================
    # Test 2: New Version (without cache)
    # ========================================================================
    print(f"\n{Fore.YELLOW}Test 2: New Version - Without Cache (spock_refresh_v2.py)")
    print("-" * 80)

    times_new = []
    for i in range(iterations):
        start = time.time()
        result = new_func()
        elapsed = time.time() - start
        times_new.append(elapsed)

        status = "✅" if result is not None else "❌"
        print(f"  Run {i+1}: {status} {elapsed*1000:.2f}ms")

    avg_new = sum(times_new) / len(times_new)
    min_new = min(times_new)
    max_new = max(times_new)

    print()
    print_result("Average:", f"{avg_new*1000:.2f}ms", Fore.CYAN)
    print_result("Min:", f"{min_new*1000:.2f}ms", Fore.GREEN)
    print_result("Max:", f"{max_new*1000:.2f}ms", Fore.RED)

    # ========================================================================
    # Test 3: New Version (with cache)
    # ========================================================================
    print(f"\n{Fore.YELLOW}Test 3: New Version - With Cache (spock_refresh_v2.py)")
    print("-" * 80)

    # 캐시 초기화
    query_cache.invalidate()

    times_cached = []

    # 첫 호출 (캐시 미스)
    print(f"  {Fore.CYAN}First call (cache miss):")
    start = time.time()
    result = new_func_cached()
    elapsed_miss = time.time() - start
    times_cached.append(elapsed_miss)
    status = "✅" if result is not None else "❌"
    print(f"    {status} {elapsed_miss*1000:.2f}ms")

    # 이후 호출들 (캐시 히트)
    print(f"\n  {Fore.CYAN}Subsequent calls (cache hits):")
    for i in range(iterations - 1):
        start = time.time()
        result = new_func_cached()
        elapsed = time.time() - start
        times_cached.append(elapsed)

        status = "✅" if result is not None else "❌"
        print(f"    Run {i+2}: {status} {elapsed*1000:.2f}ms")

    avg_cached = sum(times_cached) / len(times_cached)
    min_cached = min(times_cached)
    max_cached = max(times_cached)
    avg_hit = sum(times_cached[1:]) / (len(times_cached) - 1)  # 캐시 히트만

    print()
    print_result("Average (all):", f"{avg_cached*1000:.2f}ms", Fore.CYAN)
    print_result("Average (hits only):", f"{avg_hit*1000:.2f}ms", Fore.GREEN)
    print_result("Min:", f"{min_cached*1000:.2f}ms", Fore.GREEN)
    print_result("Max:", f"{max_cached*1000:.2f}ms", Fore.RED)

    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n{Fore.CYAN + Style.BRIGHT}Performance Summary")
    print("-" * 80)

    improvement_nocache = ((avg_old - avg_new) / avg_old) * 100
    improvement_cached = ((avg_old - avg_hit) / avg_old) * 100
    speedup_cached = avg_old / avg_hit

    print_result("Original (avg):", f"{avg_old*1000:.2f}ms", Fore.WHITE)
    print_result("New without cache (avg):", f"{avg_new*1000:.2f}ms", Fore.YELLOW)
    print_result("New with cache (hits):", f"{avg_hit*1000:.2f}ms", Fore.GREEN)
    print()
    print_result("Improvement (no cache):", f"{improvement_nocache:+.1f}%",
                 Fore.GREEN if improvement_nocache > 0 else Fore.RED)
    print_result("Improvement (cached):", f"{improvement_cached:+.1f}%",
                 Fore.GREEN if improvement_cached > 0 else Fore.RED)
    print_result("Speedup (cached):", f"{speedup_cached:.1f}x", Fore.GREEN)

    # Cache stats
    cache_stats = query_cache.stats
    print()
    print(f"{Fore.CYAN}Cache Statistics:")
    print_result("Hit rate:", f"{cache_stats['hit_rate']:.1f}%", Fore.GREEN)
    print_result("Hits:", f"{cache_stats['hits']}", Fore.WHITE)
    print_result("Misses:", f"{cache_stats['misses']}", Fore.WHITE)

    # DB connection stats
    db_stats = db_manager.get_stats()
    print()
    print(f"{Fore.CYAN}DB Connection Statistics:")
    print_result("Active connections:", f"{db_stats['active']}", Fore.WHITE)
    print_result("Total created:", f"{db_stats['total_created']}", Fore.WHITE)

    # Goal check
    print()
    print(f"{Fore.CYAN + Style.BRIGHT}Goal Achievement:")

    goal_time = avg_old * 0.6  # 40% reduction target
    goal_cache = 85.0

    time_achieved = avg_hit * 1000 < goal_time * 1000
    cache_achieved = cache_stats['hit_rate'] >= goal_cache

    print_result("Time goal (<200ms):",
                 f"{'✅ Achieved' if time_achieved else '❌ Not achieved'} ({avg_hit*1000:.2f}ms)",
                 Fore.GREEN if time_achieved else Fore.RED)
    print_result("Cache goal (>85%):",
                 f"{'✅ Achieved' if cache_achieved else '❌ Not achieved'} ({cache_stats['hit_rate']:.1f}%)",
                 Fore.GREEN if cache_achieved else Fore.RED)


def benchmark_memory():
    """메모리 사용량 벤치마크"""

    print_header("2. Memory Usage Benchmark")

    try:
        import spock_refresh_v2
        query_cache = spock_refresh_v2.query_cache
        get_status = spock_refresh_v2.get_database_status_cached

    except Exception as e:
        print(f"{Fore.RED}❌ Import failed: {e}")
        return

    process = psutil.Process(os.getpid())

    # 초기 메모리
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    print(f"{Fore.YELLOW}Initial memory: {mem_before:.2f} MB")

    # 캐시 100개 채우기
    print(f"\n{Fore.CYAN}Filling cache with 100 queries...")
    query_cache.invalidate()

    for i in range(100):
        get_status()
        if (i + 1) % 20 == 0:
            mem_current = process.memory_info().rss / 1024 / 1024
            print(f"  {i+1}/100: {mem_current:.2f} MB (+{mem_current - mem_before:.2f} MB)")

    # 최종 메모리
    mem_after = process.memory_info().rss / 1024 / 1024
    mem_delta = mem_after - mem_before

    print()
    print_result("Before:", f"{mem_before:.2f} MB", Fore.WHITE)
    print_result("After:", f"{mem_after:.2f} MB", Fore.WHITE)
    print_result("Delta:", f"+{mem_delta:.2f} MB", Fore.YELLOW)

    # Goal check
    goal_mem = 10.0  # < 10MB
    mem_achieved = mem_delta < goal_mem

    print()
    print(f"{Fore.CYAN + Style.BRIGHT}Goal Achievement:")
    print_result("Memory goal (<10MB):",
                 f"{'✅ Achieved' if mem_achieved else '❌ Not achieved'} (+{mem_delta:.2f}MB)",
                 Fore.GREEN if mem_achieved else Fore.RED)


def benchmark_connection_reuse():
    """DB 연결 재사용 벤치마크"""

    print_header("3. DB Connection Reuse Benchmark")

    try:
        import spock_refresh
        import spock_refresh_v2

        db_manager = spock_refresh_v2.db_manager

    except Exception as e:
        print(f"{Fore.RED}❌ Import failed: {e}")
        return

    # Reset stats
    db_manager._total_connections = 0

    print(f"{Fore.YELLOW}Running 10 status queries...")
    print()

    for i in range(10):
        status = spock_refresh_v2.get_database_status()
        stats = db_manager.get_stats()

        print(f"  Query {i+1:2d}: Active={stats['active']}, Total={stats['total_created']}")

    final_stats = db_manager.get_stats()

    print()
    print(f"{Fore.CYAN}Final Statistics:")
    print_result("Active connections:", f"{final_stats['active']}", Fore.WHITE)
    print_result("Total created:", f"{final_stats['total_created']}", Fore.WHITE)
    print_result("Avg per query:", f"{final_stats['total_created']/10:.1f}", Fore.YELLOW)

    # Goal check
    goal_connections = 2  # <= 2 per query on average
    conn_achieved = final_stats['total_created'] / 10 <= goal_connections

    print()
    print(f"{Fore.CYAN + Style.BRIGHT}Goal Achievement:")
    print_result("Connection goal (≤2/query):",
                 f"{'✅ Achieved' if conn_achieved else '❌ Not achieved'} ({final_stats['total_created']/10:.1f})",
                 Fore.GREEN if conn_achieved else Fore.RED)


def main():
    """메인 벤치마크 실행"""

    print(f"""
{Fore.CYAN + Style.BRIGHT}{'='*80}
Week 1 Performance Benchmark
{'='*80}{Style.RESET_ALL}

목표:
  ✓ 상태 조회 시간: 500ms → <200ms (40% 향상)
  ✓ 캐시 히트율: >85%
  ✓ DB 연결 재사용: ≤2개/쿼리
  ✓ 메모리 증가: <10MB

시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

    start_time = time.time()

    # 벤치마크 실행
    try:
        benchmark_database_status()
        benchmark_memory()
        benchmark_connection_reuse()

    except Exception as e:
        print(f"\n{Fore.RED}❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 최종 요약
    elapsed = time.time() - start_time

    print_header("Final Summary")

    print(f"{Fore.GREEN + Style.BRIGHT}✅ Benchmark completed successfully!")
    print()
    print_result("Total time:", f"{elapsed:.2f}s", Fore.WHITE)
    print_result("End time:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), Fore.WHITE)

    print(f"\n{Fore.CYAN}Next steps:")
    print(f"  1. Review results above")
    print(f"  2. If goals achieved, proceed to Week 1 Day 2 (Query Caching)")
    print(f"  3. If not achieved, debug and re-run")

    return 0


if __name__ == '__main__':
    sys.exit(main())
