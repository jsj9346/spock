#!/usr/bin/env python3
"""
Tech Screening Tool 테스트 스크립트

TechScreeningAdapter의 DB 레벨 기술적 지표 스크리닝 기능을 테스트합니다.

Usage:
    python3 scripts/test_tech_screening.py

Tests:
    1. 기본 스크리닝 (필터 없음)
    2. Bullish 트렌드 필터
    3. RSI 과매도 필터 (RSI < 30)
    4. 복합 필터 (Bullish + RSI < 40)
    5. 성능 벤치마크

Author: Spock MCP Server
Date: 2025-11-30
"""

import asyncio
import sys
import os
import time

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.adapters.tech_screening_adapter import TechScreeningAdapter


async def test_basic_screening():
    """기본 스크리닝 테스트 (필터 없음)"""
    print("\n" + "=" * 60)
    print("테스트 1: 기본 스크리닝 (필터 없음)")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={},
        sort_by="volume_desc",
        limit=10
    )

    print(f"성공: {result['success']}")
    print(f"결과 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    if result['stocks']:
        print("\n상위 5개 종목:")
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']})")
            print(f"    가격: {stock['price']:,.0f}원")
            print(f"    트렌드: {tech['trend']}, RSI: {tech['rsi']}")
            print(f"    MA20: {tech['ma20']:,.0f}, MA50: {tech['ma50']:,.0f}, MA200: {tech['ma200']:,.0f}")

    return result['success']


async def test_bullish_filter():
    """Bullish 트렌드 필터 테스트"""
    print("\n" + "=" * 60)
    print("테스트 2: Bullish 트렌드 필터")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"trend": "bullish"},
        sort_by="volume_desc",
        limit=20
    )

    print(f"성공: {result['success']}")
    print(f"Bullish 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    # 트렌드 검증
    all_bullish = all(s['technical']['trend'] == 'bullish' for s in result['stocks'])
    print(f"모든 종목이 Bullish: {all_bullish}")

    if result['stocks']:
        print("\n상위 5개 Bullish 종목:")
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']}): RSI={tech['rsi']}, Vol Ratio={tech['volume_ratio']}")

    return result['success'] and all_bullish


async def test_oversold_filter():
    """RSI 과매도 필터 테스트 (RSI < 30)"""
    print("\n" + "=" * 60)
    print("테스트 3: RSI 과매도 필터 (RSI < 30)")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"rsi_max": 30},
        sort_by="rsi_asc",
        limit=20
    )

    print(f"성공: {result['success']}")
    print(f"과매도 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    # RSI 검증 (None 체크 포함)
    if result['stocks']:
        all_oversold = all(
            s['technical']['rsi'] is not None and s['technical']['rsi'] <= 30
            for s in result['stocks']
        )
        print(f"모든 종목이 RSI <= 30: {all_oversold}")

        print("\n상위 5개 과매도 종목:")
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']}): RSI={tech['rsi']}, 트렌드={tech['trend']}")

        return result['success'] and all_oversold

    print("과매도 종목이 없습니다.")
    return result['success']


async def test_combined_filter():
    """복합 필터 테스트 (Bullish + RSI < 40)"""
    print("\n" + "=" * 60)
    print("테스트 4: 복합 필터 (Bullish + RSI < 40)")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={
            "trend": "bullish",
            "rsi_max": 40
        },
        sort_by="rsi_asc",
        limit=20
    )

    print(f"성공: {result['success']}")
    print(f"조건 충족 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    if result['stocks']:
        # 필터 검증
        all_valid = all(
            s['technical']['trend'] == 'bullish' and s['technical']['rsi'] <= 40
            for s in result['stocks']
        )
        print(f"모든 종목이 조건 충족: {all_valid}")

        print("\n상위 5개 종목 (Bullish + 낮은 RSI):")
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']})")
            print(f"    RSI: {tech['rsi']}, Price vs MA20: {tech['price_vs_ma20']}")

        return result['success'] and all_valid

    print("조건을 충족하는 종목이 없습니다.")
    return result['success']


async def test_ma_crossover_filter():
    """MA Crossover 필터 테스트 (Golden Cross / Death Cross)"""
    print("\n" + "=" * 60)
    print("테스트 5: MA Crossover 필터 (Golden Cross)")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    # Golden Cross 테스트
    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"ma_crossover": "golden_cross"},
        sort_by="volume_desc",
        limit=50
    )

    print(f"성공: {result['success']}")
    print(f"Golden Cross 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    if result['stocks']:
        # 크로스오버 검증
        all_golden = all(
            s['technical']['ma_crossover'] == 'golden_cross'
            for s in result['stocks']
        )
        print(f"모든 종목이 Golden Cross: {all_golden}")

        print("\nGolden Cross 종목:")
        for stock in result['stocks'][:10]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']})")
            print(f"    MA20: {tech['ma20']:,.0f}, MA50: {tech['ma50']:,.0f}, RSI: {tech['rsi']}")

        # Death Cross도 테스트
        print("\n" + "-" * 40)
        print("Death Cross 테스트:")
        death_result = await adapter.screen_by_technical_indicators(
            region="KR",
            filters={"ma_crossover": "death_cross"},
            sort_by="volume_desc",
            limit=50
        )
        print(f"Death Cross 종목 수: {death_result['count']}")

        if death_result['stocks']:
            for stock in death_result['stocks'][:5]:
                tech = stock['technical']
                print(f"  {stock['ticker']} ({stock['name']}): MA20={tech['ma20']:,.0f}, MA50={tech['ma50']:,.0f}")

        return result['success'] and all_golden

    print("Golden Cross 종목이 없습니다. (시장 상황에 따라 정상)")
    return result['success']


async def test_volume_surge_filter():
    """Volume Surge 필터 테스트 (거래량 2배 이상)"""
    print("\n" + "=" * 60)
    print("테스트 6: Volume Surge 필터 (거래량 급증)")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"volume_surge": True},
        sort_by="volume_desc",
        limit=20
    )

    print(f"성공: {result['success']}")
    print(f"거래량 급증 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    if result['stocks']:
        # Volume Surge 검증 (volume_ratio >= 2.0)
        all_surge = all(
            s['technical']['volume_surge'] is True or
            (s['technical']['volume_ratio'] is not None and s['technical']['volume_ratio'] >= 2.0)
            for s in result['stocks']
        )
        print(f"모든 종목이 Volume Surge: {all_surge}")

        print("\n상위 10개 거래량 급증 종목:")
        for stock in result['stocks'][:10]:
            tech = stock['technical']
            vol_ratio = tech['volume_ratio'] if tech['volume_ratio'] else 0
            print(f"  {stock['ticker']} ({stock['name']}): Vol Ratio={vol_ratio:.2f}x, RSI={tech['rsi']}")

        return result['success'] and all_surge

    print("거래량 급증 종목이 없습니다.")
    return result['success']


async def test_price_vs_ma200_filter():
    """price_vs_ma200 필터 테스트"""
    print("\n" + "=" * 60)
    print("테스트 7: price_vs_ma200 필터")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    # MA200 위에 있는 종목 필터
    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"price_vs_ma200": "above"},
        sort_by="volume_desc",
        limit=20
    )

    print(f"성공: {result['success']}")
    print(f"MA200 상단 종목 수: {result['count']}")
    print(f"실행 시간: {result['execution_time_ms']:.2f}ms")

    if result['stocks']:
        # 필터 검증
        all_above = all(
            s['technical']['price_vs_ma200'] == 'above'
            for s in result['stocks']
        )
        print(f"모든 종목이 MA200 상단: {all_above}")

        print("\n상위 5개 MA200 상단 종목:")
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            print(f"  {stock['ticker']} ({stock['name']})")
            print(f"    가격: {stock['price']:,.0f}, MA200: {tech['ma200']:,.0f}")

        # MA200 아래 종목도 테스트
        print("\n" + "-" * 40)
        below_result = await adapter.screen_by_technical_indicators(
            region="KR",
            filters={"price_vs_ma200": "below"},
            sort_by="volume_desc",
            limit=20
        )
        print(f"MA200 하단 종목 수: {below_result['count']}")

        return result['success'] and all_above

    print("MA200 상단 종목이 없습니다.")
    return result['success']


async def test_advanced_sort_options():
    """고급 정렬 옵션 테스트"""
    print("\n" + "=" * 60)
    print("테스트 8: 고급 정렬 옵션")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    # MA20 이격도 정렬 테스트 (MA20에 가장 가까운 종목)
    print("\n1. MA20 이격도 정렬 (가장 가까운 순):")
    result = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"trend": "bullish"},
        sort_by="ma20_distance_asc",
        limit=10
    )

    print(f"성공: {result['success']}")
    if result['stocks']:
        for stock in result['stocks'][:5]:
            tech = stock['technical']
            dist = tech.get('ma20_distance', 0)
            print(f"  {stock['ticker']} ({stock['name']}): MA20 이격도={dist:+.2f}%")

    # MA20 위에서 가장 가까운 종목
    print("\n2. MA20 위 + 가장 가까운 종목:")
    result2 = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"price_vs_ma20": "above"},
        sort_by="ma20_above_close",
        limit=10
    )

    if result2['stocks']:
        for stock in result2['stocks'][:5]:
            tech = stock['technical']
            dist = tech.get('ma20_distance', 0)
            print(f"  {stock['ticker']} ({stock['name']}): MA20 이격도={dist:+.2f}%")

    # MA200 이격도 정렬
    print("\n3. MA200 이격도 정렬:")
    result3 = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={},
        sort_by="ma200_distance_asc",
        limit=10
    )

    if result3['stocks']:
        for stock in result3['stocks'][:5]:
            tech = stock['technical']
            dist = tech.get('ma200_distance', 0)
            print(f"  {stock['ticker']} ({stock['name']}): MA200 이격도={dist:+.2f}%")

    # 가격 오름차순 (저가주)
    print("\n4. 가격 오름차순 (저가주):")
    result4 = await adapter.screen_by_technical_indicators(
        region="KR",
        filters={"trend": "bullish"},
        sort_by="price_asc",
        limit=10
    )

    if result4['stocks']:
        for stock in result4['stocks'][:5]:
            print(f"  {stock['ticker']} ({stock['name']}): 가격={stock['price']:,.0f}원")

    return result['success'] and result2['success'] and result3['success'] and result4['success']


async def test_performance_benchmark():
    """성능 벤치마크 테스트"""
    print("\n" + "=" * 60)
    print("테스트 9: 성능 벤치마크")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    # 캐시 초기화 (콜드 스타트)
    adapter._cache = {}
    adapter._cache_time = {}

    # 테스트 시나리오
    scenarios = [
        ("전체 스캔 (limit=100)", {}, 100),
        ("Bullish 필터", {"trend": "bullish"}, 50),
        ("RSI 과매도", {"rsi_max": 30}, 50),
        ("복합 필터", {"trend": "bullish", "rsi_max": 40, "price_vs_ma20": "above"}, 50),
    ]

    print("\n콜드 스타트 성능:")
    for name, filters, limit in scenarios:
        # 캐시 초기화
        adapter._cache = {}
        adapter._cache_time = {}

        start = time.time()
        result = await adapter.screen_by_technical_indicators(
            region="KR",
            filters=filters,
            limit=limit
        )
        elapsed = (time.time() - start) * 1000

        print(f"  {name}: {elapsed:.0f}ms (결과: {result['count']}개)")

    # 캐시 히트 성능
    print("\n캐시 히트 성능:")
    for name, filters, limit in scenarios:
        # 첫 번째 호출 (캐시 생성)
        await adapter.screen_by_technical_indicators(
            region="KR",
            filters=filters,
            limit=limit
        )

        # 두 번째 호출 (캐시 히트)
        start = time.time()
        result = await adapter.screen_by_technical_indicators(
            region="KR",
            filters=filters,
            limit=limit
        )
        elapsed = (time.time() - start) * 1000

        cache_hit = result.get('from_cache', False)
        print(f"  {name}: {elapsed:.0f}ms (캐시 히트: {cache_hit})")

    return True


async def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("Tech Screening Tool 테스트")
    print("=" * 60)

    tests = [
        ("기본 스크리닝", test_basic_screening),
        ("Bullish 필터", test_bullish_filter),
        ("과매도 필터", test_oversold_filter),
        ("복합 필터", test_combined_filter),
        ("MA Crossover 필터", test_ma_crossover_filter),
        ("Volume Surge 필터", test_volume_surge_filter),
        ("price_vs_ma200 필터", test_price_vs_ma200_filter),
        ("고급 정렬 옵션", test_advanced_sort_options),
        ("성능 벤치마크", test_performance_benchmark),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n테스트 실패: {name}")
            print(f"오류: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")

    print(f"\n총 결과: {passed}/{total} 테스트 통과")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
