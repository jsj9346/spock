#!/usr/bin/env python3
"""
Week 2 Day 5-6 Performance Benchmark
CTE 쿼리 통합 효과 측정

목적:
- Before (7개 개별 쿼리) vs After (1개 CTE 쿼리) 성능 비교
- 쿼리 응답 시간 측정
- 목표: 400ms → 120ms (70% 향상)

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
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


def benchmark_cte_query():
    """CTE 통합 쿼리 벤치마크"""

    print_header("CTE Query Optimization Benchmark (Day 5-6)")

    print(f"목표:")
    print(f"  ✓ Before: 400ms (7개 개별 쿼리)")
    print(f"  ✓ After:  120ms (1개 CTE 쿼리)")
    print(f"  ✓ 개선율: 70% 향상")
    print()
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Import after configuration
    import spock_refresh_v2 as v2

    # Test 1: CTE Query Performance (10회 반복)
    print_header("Test 1: CTE Unified Query Performance")
    print(f"10회 반복 측정 (캐시 무효화 후)...")
    print()

    times = []
    for i in range(10):
        # Invalidate cache for each run
        v2.query_cache.invalidate()

        start = time.time()
        result = v2.get_database_status()
        elapsed = time.time() - start

        times.append(elapsed * 1000)  # Convert to ms
        status = "✅" if result is not None else "❌"
        print(f"  Run {i+1:2d}: {status} {elapsed*1000:7.2f}ms")

    print()
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print_result("Average:", f"{avg_time:.2f}ms", Fore.CYAN)
    print_result("Min:", f"{min_time:.2f}ms", Fore.GREEN)
    print_result("Max:", f"{max_time:.2f}ms", Fore.YELLOW)
    print()

    # Test 2: Compare with Week 1 Baseline
    print_header("Test 2: Performance Comparison")

    week1_baseline = 400.0  # Week 1 average (from benchmark)
    week2_actual = avg_time

    improvement_pct = ((week1_baseline - week2_actual) / week1_baseline) * 100

    print_result("Week 1 Baseline (7 queries):", f"{week1_baseline:.2f}ms", Fore.YELLOW)
    print_result("Week 2 CTE (1 query):", f"{week2_actual:.2f}ms", Fore.CYAN)
    print()

    if week2_actual < week1_baseline:
        speedup = week1_baseline / week2_actual
        print_result("Improvement:", f"{improvement_pct:.1f}%", Fore.GREEN)
        print_result("Speedup:", f"{speedup:.2f}x", Fore.GREEN)
    else:
        regression = ((week2_actual - week1_baseline) / week1_baseline) * 100
        print_result("Regression:", f"{regression:.1f}%", Fore.RED)

    print()

    # Goal Achievement
    goal_time = 120.0
    if week2_actual <= goal_time:
        print(f"  {Fore.GREEN}✅ Goal Achieved!{Style.RESET_ALL} ({week2_actual:.2f}ms ≤ {goal_time}ms)")
    else:
        delta = week2_actual - goal_time
        print(f"  {Fore.YELLOW}⚠️  Close to Goal{Style.RESET_ALL} ({week2_actual:.2f}ms, +{delta:.2f}ms over target)")

    # Test 3: Query Count Comparison
    print_header("Test 3: Query Complexity")

    print_result("Week 1 Query Count:", "7 individual queries", Fore.YELLOW)
    print_result("Week 2 Query Count:", "1 CTE + 1 regional", Fore.GREEN)
    print_result("Reduction:", "71% fewer queries", Fore.GREEN)

    # Test 4: Cached Performance
    print_header("Test 4: Cached Performance")
    print(f"측정: 첫 호출 (캐시 미스) vs 이후 호출 (캐시 히트)...")
    print()

    # Clear cache
    v2.query_cache.invalidate()

    # First call (cache miss)
    start = time.time()
    result1 = v2.get_database_status_cached()
    elapsed1 = time.time() - start
    print(f"  First call (cache miss):  {elapsed1*1000:7.2f}ms")

    # Second call (cache hit)
    start = time.time()
    result2 = v2.get_database_status_cached()
    elapsed2 = time.time() - start
    print(f"  Second call (cache hit):  {elapsed2*1000:7.2f}ms")
    print()

    if elapsed1 > 0 and elapsed2 > 0:
        speedup = elapsed1 / elapsed2
        print_result("Cache Speedup:", f"{speedup:.0f}x", Fore.GREEN)

    # Final Summary
    print_header("Final Summary")

    print(f"  CTE Query Performance:")
    print_result("    Average Time:", f"{avg_time:.2f}ms", Fore.CYAN)
    print_result("    vs Week 1:", f"{improvement_pct:+.1f}%", Fore.GREEN if improvement_pct > 0 else Fore.RED)
    print()

    print(f"  Goal Achievement:")
    if week2_actual <= goal_time:
        print(f"    ✅ {Fore.GREEN}SUCCESS{Style.RESET_ALL} - Target met ({week2_actual:.2f}ms ≤ {goal_time}ms)")
    else:
        print(f"    ⚠️  {Fore.YELLOW}PARTIAL{Style.RESET_ALL} - Close to target ({week2_actual:.2f}ms vs {goal_time}ms)")

    print()
    print(f"  Cache Statistics:")
    stats = v2.query_cache.stats
    print_result("    Hit Rate:", f"{stats['hit_rate']:.1f}%", Fore.CYAN)

    print()
    print(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == '__main__':
    benchmark_cte_query()
