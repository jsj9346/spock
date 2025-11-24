#!/usr/bin/env python3
"""
Week 3 Day 7-8 Performance Benchmark
병렬 지역별 데이터 수집 효과 측정

목적:
- Before (순차 실행) vs After (병렬 실행) 성능 비교
- 6개 지역 동시 처리 성능 측정
- 목표: 1,800ms → 300ms (83% 향상)

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


def benchmark_parallel_region_refresh():
    """병렬 지역 수집 벤치마크"""

    print_header("Parallel Region Refresh Benchmark (Day 7-8)")

    print(f"목표:")
    print(f"  ✓ Before: 1,800ms (6개 지역 순차 처리)")
    print(f"  ✓ After:    300ms (6개 지역 병렬 처리)")
    print(f"  ✓ 개선율: 83% 향상")
    print()
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Import TickerRefresher
    from modules.ticker_refresh.ticker_refresher import TickerRefresher

    # Create refresher instance
    refresher = TickerRefresher()

    # Test 1: Sequential Execution (5회 반복)
    print_header("Test 1: Sequential Region Refresh (Before)")
    print(f"5회 반복 측정 (순차 실행)...")
    print()

    sequential_times = []
    for i in range(5):
        try:
            start = time.time()
            result = refresher.refresh_all_regions(incremental=True, parallel=False)
            elapsed = time.time() - start

            sequential_times.append(elapsed * 1000)  # Convert to ms

            # Count total changes
            total_changes = sum(
                r.get('new', 0) + r.get('updated', 0) + r.get('delisted', 0)
                for r in result.values()
                if isinstance(r, dict) and r.get('status') != 'error'
            )

            status = "✅" if result else "❌"
            print(f"  Run {i+1}: {status} {elapsed*1000:7.2f}ms ({total_changes} changes)")

        except Exception as e:
            print(f"  Run {i+1}: ❌ Error: {e}")
            sequential_times.append(0)

    print()
    if sequential_times:
        valid_times = [t for t in sequential_times if t > 0]
        if valid_times:
            avg_sequential = sum(valid_times) / len(valid_times)
            min_sequential = min(valid_times)
            max_sequential = max(valid_times)

            print_result("Average:", f"{avg_sequential:.2f}ms", Fore.YELLOW)
            print_result("Min:", f"{min_sequential:.2f}ms", Fore.GREEN)
            print_result("Max:", f"{max_sequential:.2f}ms", Fore.RED)
    print()

    # Test 2: Parallel Execution (5회 반복)
    print_header("Test 2: Parallel Region Refresh (After)")
    print(f"5회 반복 측정 (병렬 실행)...")
    print()

    parallel_times = []
    for i in range(5):
        try:
            start = time.time()
            result = refresher.refresh_all_regions(incremental=True, parallel=True)
            elapsed = time.time() - start

            parallel_times.append(elapsed * 1000)  # Convert to ms

            # Count total changes
            total_changes = sum(
                r.get('new', 0) + r.get('updated', 0) + r.get('delisted', 0)
                for r in result.values()
                if isinstance(r, dict) and r.get('status') != 'error'
            )

            status = "✅" if result else "❌"
            print(f"  Run {i+1}: {status} {elapsed*1000:7.2f}ms ({total_changes} changes)")

        except Exception as e:
            print(f"  Run {i+1}: ❌ Error: {e}")
            parallel_times.append(0)

    print()
    if parallel_times:
        valid_times = [t for t in parallel_times if t > 0]
        if valid_times:
            avg_parallel = sum(valid_times) / len(valid_times)
            min_parallel = min(valid_times)
            max_parallel = max(valid_times)

            print_result("Average:", f"{avg_parallel:.2f}ms", Fore.CYAN)
            print_result("Min:", f"{min_parallel:.2f}ms", Fore.GREEN)
            print_result("Max:", f"{max_parallel:.2f}ms", Fore.YELLOW)
    print()

    # Test 3: Performance Comparison
    print_header("Test 3: Performance Comparison")

    if sequential_times and parallel_times:
        valid_seq = [t for t in sequential_times if t > 0]
        valid_par = [t for t in parallel_times if t > 0]

        if valid_seq and valid_par:
            avg_sequential = sum(valid_seq) / len(valid_seq)
            avg_parallel = sum(valid_par) / len(valid_par)

            improvement_pct = ((avg_sequential - avg_parallel) / avg_sequential) * 100

            print_result("Sequential (순차):", f"{avg_sequential:.2f}ms", Fore.YELLOW)
            print_result("Parallel (병렬):", f"{avg_parallel:.2f}ms", Fore.CYAN)
            print()

            if avg_parallel < avg_sequential:
                speedup = avg_sequential / avg_parallel
                print_result("Improvement:", f"{improvement_pct:.1f}%", Fore.GREEN)
                print_result("Speedup:", f"{speedup:.2f}x", Fore.GREEN)
            else:
                regression = ((avg_parallel - avg_sequential) / avg_sequential) * 100
                print_result("Regression:", f"{regression:.1f}%", Fore.RED)

            print()

            # Goal Achievement
            goal_time = 300.0  # 300ms target
            if avg_parallel <= goal_time:
                print(f"  {Fore.GREEN}✅ Goal Achieved!{Style.RESET_ALL} ({avg_parallel:.2f}ms ≤ {goal_time}ms)")
            else:
                delta = avg_parallel - goal_time
                print(f"  {Fore.YELLOW}⚠️  Close to Goal{Style.RESET_ALL} ({avg_parallel:.2f}ms, +{delta:.2f}ms over target)")

    # Test 4: Region-by-Region Analysis
    print_header("Test 4: Region-by-Region Analysis")

    try:
        # Run one more time to get detailed results
        print("Running detailed analysis...")
        result = refresher.refresh_all_regions(incremental=True, parallel=True)

        region_emojis = {
            'KR': '🇰🇷',
            'US': '🇺🇸',
            'HK': '🇭🇰',
            'JP': '🇯🇵',
            'CN': '🇨🇳',
            'VN': '🇻🇳'
        }

        print(f"\n{'Region':<10} {'Status':<10} {'New':<8} {'Updated':<10} {'Delisted':<10} {'Total'}")
        print("-" * 70)

        for region in ['KR', 'US', 'HK', 'JP', 'CN', 'VN']:
            if region in result:
                data = result[region]
                emoji = region_emojis.get(region, '🌍')

                if data.get('status') == 'error':
                    print(f"{emoji} {region:<8} {Fore.RED}Error{Style.RESET_ALL}     -        -          -          -")
                else:
                    new = data.get('new', 0)
                    updated = data.get('updated', 0)
                    delisted = data.get('delisted', 0)
                    total = new + updated + delisted

                    status_color = Fore.GREEN if total > 0 else Fore.CYAN
                    status = f"{Fore.GREEN}✅ OK{Style.RESET_ALL}"

                    print(f"{emoji} {region:<8} {status}     {new:<8} {updated:<10} {delisted:<10} {total}")

    except Exception as e:
        print(f"  {Fore.RED}Error running detailed analysis: {e}{Style.RESET_ALL}")

    # Final Summary
    print_header("Final Summary")

    if sequential_times and parallel_times:
        valid_seq = [t for t in sequential_times if t > 0]
        valid_par = [t for t in parallel_times if t > 0]

        if valid_seq and valid_par:
            avg_sequential = sum(valid_seq) / len(valid_seq)
            avg_parallel = sum(valid_par) / len(valid_par)
            improvement_pct = ((avg_sequential - avg_parallel) / avg_sequential) * 100

            print(f"  Parallel Region Refresh Performance:")
            print_result("    Sequential Time:", f"{avg_sequential:.2f}ms", Fore.YELLOW)
            print_result("    Parallel Time:", f"{avg_parallel:.2f}ms", Fore.CYAN)
            print_result("    Improvement:", f"{improvement_pct:+.1f}%", Fore.GREEN if improvement_pct > 0 else Fore.RED)
            print()

            print(f"  Goal Achievement:")
            goal_time = 300.0
            if avg_parallel <= goal_time:
                print(f"    ✅ {Fore.GREEN}SUCCESS{Style.RESET_ALL} - Target met ({avg_parallel:.2f}ms ≤ {goal_time}ms)")
            else:
                print(f"    ⚠️  {Fore.YELLOW}PARTIAL{Style.RESET_ALL} - Close to target ({avg_parallel:.2f}ms vs {goal_time}ms)")

    print()
    print(f"종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == '__main__':
    try:
        benchmark_parallel_region_refresh()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Benchmark interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Benchmark failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
