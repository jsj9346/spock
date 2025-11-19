#!/usr/bin/env python3
"""
Three-Factor Strategy Backtesting - vectorbt Engine

검증된 3개 팩터 조합 전략의 2024년 백테스팅:
- Max_Drawdown (IC=-0.166, p=0.0002)
- Liquidity (IC=-0.097, p=0.0297)
- Short_Term_Momentum (IC=0.093, p=0.0384)

전략 로직:
1. 반기말 (6개월) 리밸런싱
2. IC 가중치 기반 복합 점수 산출
3. 상위 20개 종목 동일 가중 포트폴리오
4. 거래 비용 고려 (수수료 0.3%, 슬리피지 0.1%)

목표 성과:
- Sharpe Ratio > 1.0
- Max Drawdown < 15%
- Win Rate > 55%

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
"""

import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import numpy as np
from loguru import logger
import vectorbt as vbt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.strategies.three_factor_strategy import ThreeFactorStrategy
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# Configuration
# ============================================================================

# Backtest period (2024년 전체)
START_DATE = '2024-01-01'
END_DATE = '2024-11-30'

# Region
REGION = 'KR'

# Strategy parameters
TOP_N = 20  # 상위 20개 종목 선택
REBALANCE_FREQ = '2Q'  # 반기말 리밸런싱 (6개월)

# Transaction costs
COMMISSION_RATE = 0.003  # 0.3% 수수료
SLIPPAGE_RATE = 0.001   # 0.1% 슬리피지
TOTAL_COST = COMMISSION_RATE + SLIPPAGE_RATE  # 0.4% 총 거래 비용

# Portfolio settings
INITIAL_CAPITAL = 100_000_000  # 1억원
MIN_DATA_DAYS = 200  # 최소 데이터 일수 (Phase 1.4 기준 224일)


# ============================================================================
# Helper Functions
# ============================================================================

def load_price_data(
    tickers: list,
    start_date: str,
    end_date: str,
    region: str = 'KR'
) -> pd.DataFrame:
    """
    Load OHLCV data for vectorbt backtesting

    Parameters
    ----------
    tickers : list
        Ticker list
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)
    region : str
        Market region

    Returns
    -------
    pd.DataFrame
        Close prices (index: date, columns: tickers)
    """
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
        logger.error(f"❌ No price data found for {len(tickers)} tickers")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(data, columns=['ticker', 'date', 'close'])
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = df['close'].astype(float)

    # Pivot to wide format (index: date, columns: ticker)
    price_df = df.pivot(index='date', columns='ticker', values='close')

    logger.info(
        f"📊 가격 데이터 로드 완료\n"
        f"   - 종목 수: {len(price_df.columns)}\n"
        f"   - 기간: {price_df.index[0].strftime('%Y-%m-%d')} ~ {price_df.index[-1].strftime('%Y-%m-%d')}\n"
        f"   - 데이터 행: {len(price_df)}"
    )

    return price_df


def generate_portfolio_weights(
    signals_df: pd.DataFrame,
    price_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate portfolio weights matrix from rebalancing signals

    Parameters
    ----------
    signals_df : pd.DataFrame
        Rebalancing signals (columns: ['date', 'ticker', 'weight'])
    price_df : pd.DataFrame
        Price data (index: date, columns: ticker)

    Returns
    -------
    pd.DataFrame
        Portfolio weights (index: date, columns: ticker, values: weights)
        Forward-filled between rebalancing dates
    """
    # Initialize weights DataFrame with NaN (not 0.0!)
    weights_df = pd.DataFrame(
        np.nan,
        index=price_df.index,
        columns=price_df.columns
    )

    # Get sorted list of rebalancing dates
    rebal_dates = sorted(signals_df['date'].unique())

    # Process each rebalancing period
    for i, rebal_date in enumerate(rebal_dates):
        # Find closest trading date (handle case where rebal_date > last price date)
        matching_dates = price_df.index[price_df.index >= rebal_date]

        if len(matching_dates) == 0:
            # Use last available date if rebalancing date is after price data
            start_date = price_df.index[-1]
        else:
            start_date = matching_dates[0]

        # Determine end date (day before next rebalancing, or last date)
        if i < len(rebal_dates) - 1:
            next_rebal = rebal_dates[i + 1]
            end_dates = price_df.index[price_df.index < next_rebal]
            end_date = end_dates[-1] if len(end_dates) > 0 else start_date
        else:
            end_date = price_df.index[-1]

        # Get weights for this rebalancing
        rebal_weights = signals_df[signals_df['date'] == rebal_date]

        # Apply weights to all dates in this period
        for _, row in rebal_weights.iterrows():
            ticker = row['ticker']
            weight = row['weight']

            if ticker in weights_df.columns:
                # Set weight for entire period (start_date to end_date)
                date_mask = (weights_df.index >= start_date) & (weights_df.index <= end_date)
                weights_df.loc[date_mask, ticker] = weight

    # Fill remaining NaN with 0.0 (before first rebalancing)
    weights_df = weights_df.fillna(0.0)

    logger.info(
        f"📊 포트폴리오 가중치 생성 완료\n"
        f"   - 리밸런싱 횟수: {signals_df['date'].nunique()}\n"
        f"   - 리밸런싱 기간: {rebal_dates[0].strftime('%Y-%m-%d')} ~ {rebal_dates[-1].strftime('%Y-%m-%d')}\n"
        f"   - 평균 보유 종목 수: {(weights_df > 0).sum(axis=1).mean():.1f}개\n"
        f"   - 최대 가중치: {weights_df.max().max():.2%}"
    )

    return weights_df


# ============================================================================
# Main Backtest
# ============================================================================

def main():
    """Run Three-Factor Strategy Backtest"""

    logger.info("=" * 80)
    logger.info("Three-Factor Strategy Backtesting - vectorbt Engine")
    logger.info("=" * 80)

    # ========================================================================
    # Step 1: Initialize Strategy
    # ========================================================================

    logger.info("\n[1/5] Initializing Three-Factor Strategy...")

    strategy = ThreeFactorStrategy(
        top_n=TOP_N,
        rebalance_freq=REBALANCE_FREQ,
        transaction_cost=TOTAL_COST
    )

    logger.info("✅ Strategy initialized")

    # ========================================================================
    # Step 2: Get Investment Universe
    # ========================================================================

    logger.info("\n[2/5] Loading investment universe...")

    # Get tickers with sufficient data
    tickers = strategy.get_universe(
        region=REGION,
        start_date=START_DATE,
        end_date=END_DATE,
        min_data_days=MIN_DATA_DAYS
    )

    if not tickers:
        logger.error("❌ No tickers found in universe. Exiting.")
        return

    logger.info(f"✅ Universe loaded: {len(tickers)} tickers")

    # ========================================================================
    # Step 3: Generate Rebalancing Signals
    # ========================================================================

    logger.info("\n[3/5] Generating rebalancing signals...")

    signals_df = strategy.generate_signals(
        universe=tickers,
        start_date=START_DATE,
        end_date=END_DATE,
        region=REGION
    )

    if signals_df.empty:
        logger.error("❌ No signals generated. Exiting.")
        return

    logger.info(
        f"✅ Signals generated\n"
        f"   - Total signals: {len(signals_df)}\n"
        f"   - Rebalancing dates: {signals_df['date'].nunique()}\n"
        f"   - Avg holdings: {len(signals_df) / signals_df['date'].nunique():.1f}/semiannual"
    )

    # ========================================================================
    # Step 4: Load Price Data and Generate Portfolio Weights
    # ========================================================================

    logger.info("\n[4/5] Loading price data and generating portfolio weights...")

    # Get unique tickers from signals
    signal_tickers = signals_df['ticker'].unique().tolist()

    # Load price data
    price_df = load_price_data(signal_tickers, START_DATE, END_DATE, REGION)

    if price_df.empty:
        logger.error("❌ No price data loaded. Exiting.")
        return

    # Generate portfolio weights
    weights_df = generate_portfolio_weights(signals_df, price_df)

    logger.info("✅ Price data and weights ready")

    # ========================================================================
    # Step 5: Run vectorbt Portfolio Simulation
    # ========================================================================

    logger.info("\n[5/5] Running vectorbt portfolio simulation...")

    # Create vectorbt Portfolio
    portfolio = vbt.Portfolio.from_orders(
        close=price_df,
        size=weights_df,  # Target weights
        size_type='targetpercent',  # Rebalance to target percentage
        fees=TOTAL_COST,  # Transaction costs (0.4%)
        init_cash=INITIAL_CAPITAL,
        freq='D',  # Daily frequency
        cash_sharing=True  # Share cash across all assets
    )

    # Calculate performance metrics
    logger.info("\n📊 백테스팅 결과:")
    logger.info("=" * 80)

    # Portfolio statistics
    total_return = portfolio.total_return() * 100
    annual_return = portfolio.annualized_return() * 100
    sharpe_ratio = portfolio.sharpe_ratio()
    sortino_ratio = portfolio.sortino_ratio()
    max_drawdown = portfolio.max_drawdown() * 100
    calmar_ratio = portfolio.calmar_ratio()

    # Trade statistics
    total_trades = portfolio.orders.count()
    win_rate = portfolio.trades.win_rate() * 100 if portfolio.trades.count() > 0 else 0

    logger.info(f"\n📈 수익률:")
    logger.info(f"   - 총 수익률: {total_return:.2f}%")
    logger.info(f"   - 연환산 수익률: {annual_return:.2f}%")

    logger.info(f"\n🎯 리스크 조정 성과:")
    logger.info(f"   - Sharpe Ratio: {sharpe_ratio:.3f} {'✅' if sharpe_ratio > 1.0 else '⚠️'}")
    logger.info(f"   - Sortino Ratio: {sortino_ratio:.3f}")
    logger.info(f"   - Calmar Ratio: {calmar_ratio:.3f}")

    logger.info(f"\n⚠️ 리스크:")
    logger.info(f"   - Max Drawdown: {max_drawdown:.2f}% {'✅' if max_drawdown < 15 else '⚠️'}")

    logger.info(f"\n💼 거래 통계:")
    logger.info(f"   - 총 거래 수: {total_trades}")
    logger.info(f"   - 승률: {win_rate:.2f}% {'✅' if win_rate > 55 else '⚠️'}")

    # ========================================================================
    # Step 6: Generate Performance Report
    # ========================================================================

    logger.info("\n📋 성과 검증:")

    goals_met = []
    goals_failed = []

    # Goal 1: Sharpe Ratio > 1.0
    if sharpe_ratio > 1.0:
        goals_met.append(f"✅ Sharpe Ratio > 1.0 (실제: {sharpe_ratio:.3f})")
    else:
        goals_failed.append(f"❌ Sharpe Ratio > 1.0 (실제: {sharpe_ratio:.3f})")

    # Goal 2: Max Drawdown < 15%
    if max_drawdown < 15:
        goals_met.append(f"✅ Max Drawdown < 15% (실제: {max_drawdown:.2f}%)")
    else:
        goals_failed.append(f"❌ Max Drawdown < 15% (실제: {max_drawdown:.2f}%)")

    # Goal 3: Win Rate > 55%
    if win_rate > 55:
        goals_met.append(f"✅ Win Rate > 55% (실제: {win_rate:.2f}%)")
    else:
        goals_failed.append(f"❌ Win Rate > 55% (실제: {win_rate:.2f}%)")

    logger.info(f"\n달성된 목표 ({len(goals_met)}/3):")
    for goal in goals_met:
        logger.info(f"   {goal}")

    if goals_failed:
        logger.info(f"\n미달성 목표:")
        for goal in goals_failed:
            logger.info(f"   {goal}")

    # ========================================================================
    # Step 7: Save Results
    # ========================================================================

    logger.info("\n💾 결과 저장...")

    # Create results directory
    results_dir = project_root / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    # Save equity curve
    equity_curve = portfolio.value()
    equity_curve.to_csv(results_dir / 'three_factor_semiannual_equity_curve.csv')

    # Save portfolio weights
    weights_df.to_csv(results_dir / 'three_factor_semiannual_weights.csv')

    # Save rebalancing signals
    signals_df.to_csv(results_dir / 'three_factor_semiannual_signals.csv', index=False)

    logger.info(f"✅ 결과 저장 완료: {results_dir}")

    # ========================================================================
    # Summary
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("백테스팅 완료 요약")
    logger.info("=" * 80)
    logger.info(f"전략: Three-Factor Strategy (IC 가중치)")
    logger.info(f"기간: {START_DATE} ~ {END_DATE}")
    logger.info(f"초기 자본: {INITIAL_CAPITAL:,.0f}원")
    logger.info(f"최종 자산: {portfolio.final_value():,.0f}원")
    logger.info(f"수익률: {total_return:.2f}%")
    logger.info(f"Sharpe Ratio: {sharpe_ratio:.3f}")
    logger.info(f"Max Drawdown: {max_drawdown:.2f}%")
    logger.info(f"목표 달성: {len(goals_met)}/3")

    if len(goals_met) == 3:
        logger.info("\n🎉 모든 목표 달성! 전략 검증 성공!")
    elif len(goals_met) >= 2:
        logger.info("\n👍 대부분의 목표 달성. 전략 유망함.")
    else:
        logger.info("\n⚠️ 목표 미달. 전략 조정 필요.")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
