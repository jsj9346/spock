#!/usr/bin/env python3
"""
Unit Test for Parallel Region Refresh
병렬 지역 수집 로직 검증

목적:
- 병렬 실행 로직 검증 (실제 API 호출 없이)
- 순차 vs 병렬 성능 비교
- 에러 핸들링 검증

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch
from colorama import Fore, Style, init

init(autoreset=True)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def print_header(title: str):
    """헤더 출력"""
    print(f"\n{'='*80}")
    print(f"{Fore.CYAN + Style.BRIGHT}{title}")
    print(f"{'='*80}\n")


def print_result(label: str, status: str, details: str = ""):
    """결과 출력"""
    print(f"  {label:<40} {status:<20} {details}")


def test_parallel_logic():
    """병렬 실행 로직 테스트 (Mock 사용)"""

    print_header("Parallel Region Refresh Logic Test")

    from modules.ticker_refresh.ticker_refresher import TickerRefresher

    # Create mock refresher
    refresher = TickerRefresher()

    # Mock the refresh_region method to simulate delays
    original_refresh_region = refresher.refresh_region

    def mock_refresh_region(region: str, incremental: bool = True):
        """Mock refresh_region with simulated delay"""
        # Simulate different processing times per region
        delays = {
            'KR': 0.05,   # 50ms
            'US': 0.10,   # 100ms
            'HK': 0.08,   # 80ms
            'JP': 0.07,   # 70ms
            'CN': 0.06,   # 60ms
            'VN': 0.09    # 90ms
        }

        time.sleep(delays.get(region, 0.1))

        return {
            'status': 'success',
            'new': 5,
            'updated': 2,
            'delisted': 1,
            'errors': 0,
            'region': region,
            'timestamp': datetime.now()
        }

    # Patch the method
    refresher.refresh_region = mock_refresh_region

    # Test 1: Sequential Execution
    print(f"Test 1: Sequential Execution (순차 처리)")
    print(f"  Expected: ~460ms (50+100+80+70+60+90)")
    print()

    start = time.time()
    result_seq = refresher._refresh_all_regions_sequential(incremental=True)
    elapsed_seq = time.time() - start

    print(f"  Actual:   {elapsed_seq*1000:.2f}ms")
    print(f"  Regions:  {len(result_seq)}")

    # Verify all regions processed
    all_regions_ok = all(
        r.get('status') == 'success'
        for r in result_seq.values()
    )

    if all_regions_ok and len(result_seq) == 6:
        print(f"  Status:   {Fore.GREEN}✅ PASS{Style.RESET_ALL}")
    else:
        print(f"  Status:   {Fore.RED}❌ FAIL{Style.RESET_ALL}")

    # Test 2: Parallel Execution
    print()
    print(f"Test 2: Parallel Execution (병렬 처리)")
    print(f"  Expected: ~100-120ms (max delay + overhead)")
    print()

    start = time.time()
    result_par = refresher._refresh_all_regions_parallel(incremental=True)
    elapsed_par = time.time() - start

    print(f"  Actual:   {elapsed_par*1000:.2f}ms")
    print(f"  Regions:  {len(result_par)}")

    # Verify all regions processed
    all_regions_ok = all(
        r.get('status') == 'success'
        for r in result_par.values()
    )

    if all_regions_ok and len(result_par) == 6:
        print(f"  Status:   {Fore.GREEN}✅ PASS{Style.RESET_ALL}")
    else:
        print(f"  Status:   {Fore.RED}❌ FAIL{Style.RESET_ALL}")

    # Test 3: Performance Comparison
    print()
    print(f"Test 3: Performance Comparison")
    print()

    speedup = elapsed_seq / elapsed_par
    improvement = ((elapsed_seq - elapsed_par) / elapsed_seq) * 100

    print_result("Sequential Time:", f"{elapsed_seq*1000:.2f}ms")
    print_result("Parallel Time:", f"{elapsed_par*1000:.2f}ms")
    print_result("Speedup:", f"{speedup:.2f}x", f"({improvement:.1f}% faster)")

    # Expected: parallel should be ~3-4x faster
    if speedup >= 3.0:
        print(f"  Status:   {Fore.GREEN}✅ PASS{Style.RESET_ALL} (Speedup {speedup:.2f}x >= 3.0x)")
    elif speedup >= 2.0:
        print(f"  Status:   {Fore.YELLOW}⚠️  PARTIAL{Style.RESET_ALL} (Speedup {speedup:.2f}x >= 2.0x)")
    else:
        print(f"  Status:   {Fore.RED}❌ FAIL{Style.RESET_ALL} (Speedup {speedup:.2f}x < 2.0x)")

    # Test 4: Data Integrity
    print()
    print(f"Test 4: Data Integrity (병렬 처리 결과 검증)")
    print()

    # Verify same regions processed
    seq_regions = set(result_seq.keys())
    par_regions = set(result_par.keys())

    regions_match = seq_regions == par_regions
    print_result("Same regions processed:", f"{Fore.GREEN if regions_match else Fore.RED}{'✅' if regions_match else '❌'}{Style.RESET_ALL}")

    # Verify all 6 regions present
    expected_regions = {'KR', 'US', 'HK', 'JP', 'CN', 'VN'}
    all_present = expected_regions == par_regions

    print_result("All 6 regions present:", f"{Fore.GREEN if all_present else Fore.RED}{'✅' if all_present else '❌'}{Style.RESET_ALL}")

    # Test 5: Error Handling
    print()
    print(f"Test 5: Error Handling (에러 상황 처리)")
    print()

    # Create a mock that raises error for one region
    def mock_refresh_region_with_error(region: str, incremental: bool = True):
        """Mock that fails for US region"""
        if region == 'US':
            raise Exception("Simulated API failure")

        time.sleep(0.05)  # 50ms delay
        return {
            'status': 'success',
            'new': 5,
            'updated': 2,
            'delisted': 1,
            'errors': 0
        }

    refresher.refresh_region = mock_refresh_region_with_error

    # Test parallel error handling
    result_with_error = refresher._refresh_all_regions_parallel(incremental=True)

    us_result = result_with_error.get('US', {})
    us_has_error = us_result.get('status') == 'error'
    other_regions_ok = all(
        result_with_error[r].get('status') == 'success'
        for r in ['KR', 'HK', 'JP', 'CN', 'VN']
    )

    print_result("US region error caught:", f"{Fore.GREEN if us_has_error else Fore.RED}{'✅' if us_has_error else '❌'}{Style.RESET_ALL}")
    print_result("Other regions succeeded:", f"{Fore.GREEN if other_regions_ok else Fore.RED}{'✅' if other_regions_ok else '❌'}{Style.RESET_ALL}")

    # Final Summary
    print_header("Test Summary")

    tests_passed = 0
    tests_total = 5

    # Test 1: Sequential execution
    if all_regions_ok and len(result_seq) == 6:
        tests_passed += 1
        print(f"  ✅ Test 1: Sequential Execution - PASS")
    else:
        print(f"  ❌ Test 1: Sequential Execution - FAIL")

    # Test 2: Parallel execution
    if all_regions_ok and len(result_par) == 6:
        tests_passed += 1
        print(f"  ✅ Test 2: Parallel Execution - PASS")
    else:
        print(f"  ❌ Test 2: Parallel Execution - FAIL")

    # Test 3: Performance
    if speedup >= 2.0:
        tests_passed += 1
        print(f"  ✅ Test 3: Performance (Speedup {speedup:.2f}x) - PASS")
    else:
        print(f"  ❌ Test 3: Performance (Speedup {speedup:.2f}x) - FAIL")

    # Test 4: Data integrity
    if regions_match and all_present:
        tests_passed += 1
        print(f"  ✅ Test 4: Data Integrity - PASS")
    else:
        print(f"  ❌ Test 4: Data Integrity - FAIL")

    # Test 5: Error handling
    if us_has_error and other_regions_ok:
        tests_passed += 1
        print(f"  ✅ Test 5: Error Handling - PASS")
    else:
        print(f"  ❌ Test 5: Error Handling - FAIL")

    print()
    print(f"  Overall: {tests_passed}/{tests_total} tests passed ({tests_passed/tests_total*100:.0f}%)")

    if tests_passed == tests_total:
        print(f"\n  {Fore.GREEN + Style.BRIGHT}✅ ALL TESTS PASSED!{Style.RESET_ALL}")
        return 0
    else:
        print(f"\n  {Fore.RED + Style.BRIGHT}❌ SOME TESTS FAILED{Style.RESET_ALL}")
        return 1


if __name__ == '__main__':
    try:
        exit_code = test_parallel_logic()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Tests interrupted by user{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}Tests failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
