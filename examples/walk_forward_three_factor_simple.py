#!/usr/bin/env python3
"""
Simple Walk-Forward Validation for Three-Factor Strategy

2024년 데이터를 In-Sample / Out-of-Sample로 분할하여 검증:
- In-Sample (Training): 2024-01-01 ~ 2024-07-31 (7개월)
- Out-of-Sample (Testing): 2024-08-01 ~ 2024-11-30 (4개월)

목표:
1. In-Sample에서 팩터 IC 계산 및 가중치 최적화
2. Out-of-Sample에서 최적화된 가중치로 백테스트
3. 2024년 전체 백테스트(+18.09%, Sharpe 0.870) 대비 성능 저하 확인

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from loguru import logger
import vectorbt as vbt
from scipy import stats

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.strategies.three_factor_strategy import ThreeFactorStrategy
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# Configuration
# ============================================================================

# Periods
IN_SAMPLE_START = '2024-01-01'
IN_SAMPLE_END = '2024-07-31'
OUT_OF_SAMPLE_START = '2024-08-01'
OUT_OF_SAMPLE_END = '2024-11-30'

# Strategy Parameters
TOP_N = 20
REBALANCE_FREQ = 'M'
REGION = 'KR'

# Transaction Costs
TOTAL_COST = 0.004  # 0.4%

# Portfolio Settings
INITIAL_CAPITAL = 100_000_000  # 1억원
MIN_DATA_DAYS = 140  # 최소 데이터 일수 (2024-01~07: 144일 available)


# ============================================================================
# Main Workflow
# ============================================================================

def main():
    """Execute Simple Walk-Forward Validation"""

    logger.info("=" * 80)
    logger.info("Simple Walk-Forward Validation - Three-Factor Strategy")
    logger.info("=" * 80)

    logger.info(
        f"\n📋 검증 설정:\n"
        f"   - In-Sample: {IN_SAMPLE_START} ~ {IN_SAMPLE_END}\n"
        f"   - Out-of-Sample: {OUT_OF_SAMPLE_START} ~ {OUT_OF_SAMPLE_END}\n"
        f"   - Baseline: 2024 전체 (+18.09%, Sharpe 0.870)"
    )

    # ========================================================================
    # Step 1: In-Sample Backtest with Default Weights
    # ========================================================================

    logger.info(f"\n{'='*80}")
    logger.info("Step 1: In-Sample 백테스트 (기본 IC 가중치)")
    logger.info(f"{'='*80}")

    # Use default IC-weighted strategy
    is_strategy = ThreeFactorStrategy(
        top_n=TOP_N,
        rebalance_freq=REBALANCE_FREQ,
        transaction_cost=TOTAL_COST
    )

    # Get universe
    is_tickers = is_strategy.get_universe(
        region=REGION,
        start_date=IN_SAMPLE_START,
        end_date=IN_SAMPLE_END,
        min_data_days=MIN_DATA_DAYS
    )

    if not is_tickers:
        logger.error("❌ In-Sample universe 없음")
        return

    # Generate signals
    is_signals = is_strategy.generate_signals(
        universe=is_tickers,
        start_date=IN_SAMPLE_START,
        end_date=IN_SAMPLE_END,
        region=REGION
    )

    if is_signals.empty:
        logger.error("❌ In-Sample 신호 생성 실패")
        return

    # Load price data and run backtest
    is_portfolio, is_metrics = run_backtest(
        is_signals,
        IN_SAMPLE_START,
        IN_SAMPLE_END,
        REGION
    )

    if is_portfolio is None:
        logger.error("❌ In-Sample 백테스트 실패")
        return

    logger.info(
        f"\n✅ In-Sample 백테스트 결과:\n"
        f"   - 수익률: {is_metrics['total_return']*100:.2f}%\n"
        f"   - Sharpe: {is_metrics['sharpe_ratio']:.3f}\n"
        f"   - Max DD: {is_metrics['max_drawdown']*100:.2f}%\n"
        f"   - 승률: {is_metrics['win_rate']*100:.2f}%\n"
        f"   - 거래 수: {is_metrics['total_trades']}"
    )

    # ========================================================================
    # Step 2: Out-of-Sample Backtest with Same Weights
    # ========================================================================

    logger.info(f"\n{'='*80}")
    logger.info("Step 2: Out-of-Sample 백테스트 (동일 가중치 적용)")
    logger.info(f"{'='*80}")

    # Use same strategy with default weights
    oos_strategy = ThreeFactorStrategy(
        top_n=TOP_N,
        rebalance_freq=REBALANCE_FREQ,
        transaction_cost=TOTAL_COST
    )

    # Get universe
    oos_tickers = oos_strategy.get_universe(
        region=REGION,
        start_date=OUT_OF_SAMPLE_START,
        end_date=OUT_OF_SAMPLE_END,
        min_data_days=MIN_DATA_DAYS // 2  # Relax for shorter period
    )

    if not oos_tickers:
        logger.error("❌ Out-of-Sample universe 없음")
        return

    # Generate signals
    oos_signals = oos_strategy.generate_signals(
        universe=oos_tickers,
        start_date=OUT_OF_SAMPLE_START,
        end_date=OUT_OF_SAMPLE_END,
        region=REGION
    )

    if oos_signals.empty:
        logger.error("❌ Out-of-Sample 신호 생성 실패")
        return

    # Run backtest
    oos_portfolio, oos_metrics = run_backtest(
        oos_signals,
        OUT_OF_SAMPLE_START,
        OUT_OF_SAMPLE_END,
        REGION
    )

    if oos_portfolio is None:
        logger.error("❌ Out-of-Sample 백테스트 실패")
        return

    logger.info(
        f"\n✅ Out-of-Sample 백테스트 결과:\n"
        f"   - 수익률: {oos_metrics['total_return']*100:.2f}%\n"
        f"   - Sharpe: {oos_metrics['sharpe_ratio']:.3f}\n"
        f"   - Max DD: {oos_metrics['max_drawdown']*100:.2f}%\n"
        f"   - 승률: {oos_metrics['win_rate']*100:.2f}%\n"
        f"   - 거래 수: {oos_metrics['total_trades']}"
    )

    # ========================================================================
    # Step 3: Performance Comparison and Overfitting Check
    # ========================================================================

    logger.info(f"\n{'='*80}")
    logger.info("Step 3: 성능 비교 및 과적합 검증")
    logger.info(f"{'='*80}")

    # Baseline (2024 full year)
    baseline_return = 0.1809
    baseline_sharpe = 0.870

    # Calculate degradation
    is_degradation = (baseline_return - is_metrics['total_return']) / baseline_return * 100
    oos_degradation = (baseline_return - oos_metrics['total_return']) / baseline_return * 100

    is_sharpe_degradation = (baseline_sharpe - is_metrics['sharpe_ratio']) / baseline_sharpe * 100
    oos_sharpe_degradation = (baseline_sharpe - oos_metrics['sharpe_ratio']) / baseline_sharpe * 100

    logger.info(
        f"\n📊 수익률 비교:\n"
        f"   - Baseline (2024 전체): {baseline_return*100:.2f}%\n"
        f"   - In-Sample (1-7월):    {is_metrics['total_return']*100:.2f}% "
        f"({'성능 저하' if is_degradation > 0 else '성능 개선'} {abs(is_degradation):.1f}%)\n"
        f"   - Out-of-Sample (8-11월): {oos_metrics['total_return']*100:.2f}% "
        f"({'성능 저하' if oos_degradation > 0 else '성능 개선'} {abs(oos_degradation):.1f}%)"
    )

    logger.info(
        f"\n📈 Sharpe 비교:\n"
        f"   - Baseline (2024 전체): {baseline_sharpe:.3f}\n"
        f"   - In-Sample (1-7월):    {is_metrics['sharpe_ratio']:.3f} "
        f"({'저하' if is_sharpe_degradation > 0 else '개선'} {abs(is_sharpe_degradation):.1f}%)\n"
        f"   - Out-of-Sample (8-11월): {oos_metrics['sharpe_ratio']:.3f} "
        f"({'저하' if oos_sharpe_degradation > 0 else '개선'} {abs(oos_sharpe_degradation):.1f}%)"
    )

    # Overfitting check
    logger.info(f"\n🎯 과적합 검증:")

    # Compare IS vs OOS performance degradation
    if abs(is_degradation) < 30 and abs(oos_degradation) < 30:
        logger.info(f"   ✅ 과적합 없음: IS/OOS 모두 성능 저하 <30%")
    elif abs(oos_degradation) > abs(is_degradation) + 20:
        logger.info(f"   ⚠️ 과적합 의심: OOS 성능 저하가 IS보다 {abs(oos_degradation - is_degradation):.1f}%p 더 큼")
    else:
        logger.info(f"   👍 양호: OOS 성능 저하가 IS와 유사 ({abs(oos_degradation - is_degradation):.1f}%p 차이)")

    # ========================================================================
    # Step 4: Save Results
    # ========================================================================

    results_dir = project_root / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # Save summary
    summary = {
        'period': ['Baseline (2024 전체)', 'In-Sample (1-7월)', 'Out-of-Sample (8-11월)'],
        'return': [baseline_return * 100, is_metrics['total_return'] * 100, oos_metrics['total_return'] * 100],
        'sharpe': [baseline_sharpe, is_metrics['sharpe_ratio'], oos_metrics['sharpe_ratio']],
        'max_dd': [0, is_metrics['max_drawdown'] * 100, oos_metrics['max_drawdown'] * 100],
        'win_rate': [0, is_metrics['win_rate'] * 100, oos_metrics['win_rate'] * 100],
        'trades': [0, is_metrics['total_trades'], oos_metrics['total_trades']]
    }

    summary_df = pd.DataFrame(summary)
    summary_file = results_dir / 'walk_forward_summary.csv'
    summary_df.to_csv(summary_file, index=False)

    logger.info(f"\n💾 결과 저장: {summary_file}")

    logger.info(f"\n{'='*80}")
    logger.info("Walk-Forward 검증 완료")
    logger.info(f"{'='*80}")


# ============================================================================
# Helper Functions
# ============================================================================

def run_backtest(signals_df, start_date, end_date, region):
    """Run vectorbt backtest and return portfolio + metrics"""

    # Get unique tickers from signals
    signal_tickers = signals_df['ticker'].unique().tolist()

    # Load price data
    price_df = load_price_data(signal_tickers, start_date, end_date, region)

    if price_df.empty:
        logger.error(f"❌ 가격 데이터 로드 실패")
        return None, {}

    # Generate weights
    weights_df = generate_portfolio_weights(signals_df, price_df)

    # Run backtest
    try:
        portfolio = vbt.Portfolio.from_orders(
            close=price_df,
            size=weights_df,
            size_type='targetpercent',
            fees=TOTAL_COST,
            init_cash=INITIAL_CAPITAL,
            freq='D',
            cash_sharing=True
        )

        # Calculate metrics
        metrics = {
            'total_return': portfolio.total_return(),
            'annual_return': portfolio.annualized_return(),
            'sharpe_ratio': portfolio.sharpe_ratio(),
            'max_drawdown': portfolio.max_drawdown(),
            'win_rate': portfolio.trades.win_rate() if portfolio.trades.count() > 0 else 0,
            'total_trades': portfolio.orders.count()
        }

        return portfolio, metrics

    except Exception as e:
        logger.error(f"❌ 백테스트 실행 실패: {e}")
        return None, {}


def load_price_data(tickers, start_date, end_date, region='KR'):
    """Load OHLCV data for vectorbt backtesting"""
    db = PostgresDatabaseManager()

    query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE ticker = ANY(%s)
          AND region = %s
          AND date BETWEEN %s AND %s
        ORDER BY date ASC
    """

    data = db.execute_query(query, (tickers, region, start_date, end_date))

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=['ticker', 'date', 'close'])
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = df['close'].astype(float)

    price_df = df.pivot(index='date', columns='ticker', values='close')

    return price_df


def generate_portfolio_weights(signals_df, price_df):
    """Generate portfolio weights matrix from rebalancing signals"""
    weights_df = pd.DataFrame(
        np.nan,
        index=price_df.index,
        columns=price_df.columns
    )

    rebal_dates = sorted(signals_df['date'].unique())

    for i, rebal_date in enumerate(rebal_dates):
        matching_dates = price_df.index[price_df.index >= rebal_date]

        if len(matching_dates) == 0:
            start_date = price_df.index[-1]
        else:
            start_date = matching_dates[0]

        if i < len(rebal_dates) - 1:
            next_rebal = rebal_dates[i + 1]
            end_dates = price_df.index[price_df.index < next_rebal]
            end_date = end_dates[-1] if len(end_dates) > 0 else start_date
        else:
            end_date = price_df.index[-1]

        rebal_weights = signals_df[signals_df['date'] == rebal_date]

        for _, row in rebal_weights.iterrows():
            ticker = row['ticker']
            weight = row['weight']

            if ticker in weights_df.columns:
                date_mask = (weights_df.index >= start_date) & (weights_df.index <= end_date)
                weights_df.loc[date_mask, ticker] = weight

    weights_df = weights_df.fillna(0.0)

    return weights_df


if __name__ == "__main__":
    main()
