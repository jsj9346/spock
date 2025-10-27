#!/usr/bin/env python3
"""
ETF Preference Scoring 테스트 (Phase 3)

RelativeStrengthModule의 ETF 선호도 점수 계산 기능 검증

Test Cases:
1. ETF에 포함되지 않은 종목 (0점)
2. 낮은 비중으로 ETF에 포함된 종목 (1점)
3. 1-2개 주요 ETF에 포함된 종목 (3점)
4. 3개 이상 주요 ETF에 포함된 종목 (5점)

Author: Spock Trading System
Date: 2025-10-17
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.basic_scoring_modules import RelativeStrengthModule
from modules.layered_scoring_engine import LayerType


def setup_test_data(db_path: str):
    """테스트용 ETF holdings 데이터 생성"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 테스트 시나리오 데이터
    test_scenarios = [
        # Case 1: ETF에 포함되지 않은 종목 (TEST001)
        # - 데이터 없음 → 0점 예상

        # Case 2: 낮은 비중으로 ETF에 포함된 종목 (TEST002)
        # - ETF_A: 2.5% 비중 → 1점 예상
        ('ETF_A', 'TEST002', 2.5, (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')),
        ('ETF_B', 'TEST002', 3.0, (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')),

        # Case 3: 1-2개 주요 ETF에 포함된 종목 (TEST003)
        # - ETF_C: 6.5% 비중 (주요) → 3점 예상
        ('ETF_C', 'TEST003', 6.5, (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')),
        ('ETF_D', 'TEST003', 2.0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')),

        # Case 4: 3개 이상 주요 ETF에 포함된 종목 (TEST004)
        # - ETF_E: 8.5%, ETF_F: 7.0%, ETF_G: 5.5% (3개 주요) → 5점 예상
        ('ETF_E', 'TEST004', 8.5, (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')),
        ('ETF_F', 'TEST004', 7.0, (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d')),
        ('ETF_G', 'TEST004', 5.5, (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d')),
        ('ETF_H', 'TEST004', 2.0, (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d')),
    ]

    # 기존 테스트 데이터 삭제
    cursor.execute("DELETE FROM etf_holdings WHERE stock_ticker LIKE 'TEST%'")

    # 테스트 데이터 삽입
    for etf_ticker, stock_ticker, weight, as_of_date in test_scenarios:
        cursor.execute("""
            INSERT INTO etf_holdings (
                etf_ticker, stock_ticker, weight, shares,
                market_value, rank_in_etf, as_of_date,
                data_source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            etf_ticker, stock_ticker, weight, 1000000,
            100000000, 1, as_of_date,
            'TEST', datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()

    print(f"✅ 테스트 데이터 생성 완료 ({len(test_scenarios)}개 레코드)")


def create_sample_ohlcv_data(ticker: str) -> pd.DataFrame:
    """샘플 OHLCV 데이터 생성 (RelativeStrengthModule 테스트용)"""
    dates = pd.date_range(end=datetime.now(), periods=200, freq='D')
    np.random.seed(42)

    # 상승 추세 데이터
    base_price = 10000
    prices = []
    for i in range(200):
        trend = base_price * (1 + i * 0.005)  # 0.5% 일일 상승
        noise = np.random.normal(0, 0.02)      # 2% 변동성
        price = trend * (1 + noise)
        prices.append(price)

    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'open': prices,
        'volume': [1000000] * 200
    })

    # RSI 계산
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 이동평균
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()

    return df


def test_etf_preference_scoring():
    """ETF 선호도 점수 테스트"""
    print("🧪 ETF Preference Scoring 테스트")
    print("=" * 70)

    db_path = "./data/spock_local.db"

    # 1. 테스트 데이터 생성
    setup_test_data(db_path)

    # 2. RelativeStrengthModule 초기화
    module = RelativeStrengthModule(db_path=db_path)

    # 3. 테스트 케이스 실행
    test_cases = [
        ('TEST001', 0.0, 'ETF에 포함되지 않음'),
        ('TEST002', 1.0, '낮은 비중 ETF 포함'),
        ('TEST003', 3.0, '1-2개 주요 ETF 포함'),
        ('TEST004', 5.0, '3개 이상 주요 ETF 포함'),
    ]

    print(f"\n📊 테스트 케이스:")
    print("-" * 70)
    print(f"{'Ticker':<12} {'예상 점수':<12} {'실제 점수':<12} {'일치':<8} {'설명'}")
    print("-" * 70)

    all_passed = True

    for ticker, expected_score, description in test_cases:
        # OHLCV 데이터 생성
        ohlcv_data = create_sample_ohlcv_data(ticker)

        # 점수 계산
        config = {'ticker': ticker}
        result = module.calculate_score(ohlcv_data, config)

        # ETF 선호도 점수 추출
        actual_etf_score = result.details.get('etf_preference_score', 0.0)
        etf_details = result.details.get('etf_details', {})

        # 검증
        passed = (actual_etf_score == expected_score)
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"{ticker:<12} {expected_score:<12.1f} {actual_etf_score:<12.1f} {status:<8} {description}")

        # 상세 정보 출력
        if etf_details:
            print(f"  └─ ETF 개수: {etf_details.get('etf_count', 0)}, "
                  f"주요 ETF: {etf_details.get('high_weight_count', 0)}, "
                  f"최대 비중: {etf_details.get('max_weight', 0):.2f}%")

        if not passed:
            all_passed = False

    print("-" * 70)

    # 4. 전체 점수 통합 테스트
    print(f"\n🔍 전체 점수 통합 검증:")
    print("-" * 70)

    for ticker, _, description in test_cases[:2]:  # 2개만 상세 확인
        ohlcv_data = create_sample_ohlcv_data(ticker)
        config = {'ticker': ticker}
        result = module.calculate_score(ohlcv_data, config)

        print(f"\n{ticker} - {description}")
        print(f"  총점: {result.score:.2f} / 100")
        print(f"  RSI 점수: {result.details.get('rsi_score', 0):.2f}")
        print(f"  수익률 점수: {result.details.get('return_score', 0):.2f}")
        print(f"  ETF 선호도: {result.details.get('etf_preference_score', 0):.2f} / 5")
        print(f"  신뢰도: {result.confidence:.2f}")

    print("-" * 70)

    # 5. 결과 요약
    if all_passed:
        print("\n✅ 모든 테스트 PASS!")
        print("🎯 ETF 선호도 점수 계산 정상 작동")
    else:
        print("\n❌ 일부 테스트 FAIL")
        print("⚠️ ETF 선호도 점수 계산 로직 재검토 필요")

    # 6. 테스트 데이터 정리
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM etf_holdings WHERE stock_ticker LIKE 'TEST%'")
    conn.commit()
    conn.close()

    print("\n🗑️  테스트 데이터 정리 완료")

    return all_passed


if __name__ == "__main__":
    success = test_etf_preference_scoring()
    sys.exit(0 if success else 1)
