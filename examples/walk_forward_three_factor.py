#!/usr/bin/env python3
"""
Walk-Forward Optimization for Three-Factor Strategy

2024년 데이터를 활용한 Walk-Forward 검증:
1. 과적합 여부 검증 (In-Sample vs Out-of-Sample 성능 비교)
2. 팩터 가중치 안정성 검증 (시간에 따른 IC 변화)
3. 전략 견고성 평가 (다양한 시장 환경에서의 성능)

Walk-Forward 설정:
- In-Sample (Training): 2024-01-01 ~ 2024-07-31 (7개월)
- Out-of-Sample (Testing): 2024-08-01 ~ 2024-11-30 (4개월)
- 목표: 2024년 전체 백테스트(+18.09%) 대비 IS/OOS 성능 비교

Note: 2022-2023년 데이터는 300개 ticker만 존재하여 제외
      2024년부터 3,700개 ticker로 확대됨

Author: Spock Quant Platform - Phase 2
Date: 2025-11-18
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict, List, Tuple
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

# Walk-Forward Parameters (2024 only - data availability constraint)
IN_SAMPLE_START = '2024-01-01'
IN_SAMPLE_END = '2024-07-31'
OUT_OF_SAMPLE_START = '2024-08-01'
OUT_OF_SAMPLE_END = '2024-11-30'

# Strategy Parameters
TOP_N = 20
REBALANCE_FREQ = 'M'  # 월말 리밸런싱
REGION = 'KR'

# Transaction Costs
COMMISSION_RATE = 0.003  # 0.3%
SLIPPAGE_RATE = 0.001   # 0.1%
TOTAL_COST = COMMISSION_RATE + SLIPPAGE_RATE  # 0.4%

# Portfolio Settings
INITIAL_CAPITAL = 100_000_000  # 1억원
MIN_DATA_DAYS = 180  # 최소 데이터 일수 (6개월)


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_factor_ic(
    tickers: List[str],
    start_date: str,
    end_date: str,
    region: str = 'KR'
) -> Dict[str, float]:
    """
    Training window에서 각 팩터의 IC(Information Coefficient) 계산

    Parameters
    ----------
    tickers : List[str]
        티커 리스트
    start_date : str
        시작 날짜
    end_date : str
        종료 날짜
    region : str
        시장

    Returns
    -------
    Dict[str, float]
        팩터별 IC 값 {'max_drawdown': -0.166, 'liquidity': -0.097, 'momentum': 0.093}
    """
    db = PostgresDatabaseManager()

    # Initialize factors
    from modules.factors.momentum_factors import ShortTermMomentumFactor
    from modules.factors.low_vol_factors import MaxDrawdownFactor
    from modules.factors.size_factors import LiquidityFactor

    momentum_factor = ShortTermMomentumFactor()
    max_dd_factor = MaxDrawdownFactor()
    liquidity_factor = LiquidityFactor()

    # Generate monthly calculation dates
    dates = pd.date_range(start=start_date, end=end_date, freq='M')
    calc_dates = [d + pd.offsets.MonthEnd(0) for d in dates]

    all_factor_values = []

    for calc_date in calc_dates:
        calc_date_str = calc_date.strftime('%Y-%m-%d')
        lookback_start = (calc_date - timedelta(days=300)).strftime('%Y-%m-%d')

        # Forward return calculation date (1 month later)
        forward_date = (calc_date + pd.offsets.MonthEnd(1)).strftime('%Y-%m-%d')

        for ticker in tickers:
            # Fetch OHLCV data for factor calculation
            query = """
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s
                  AND date BETWEEN %s AND %s
                ORDER BY date ASC
            """

            data = db.execute_query(query, (ticker, region, lookback_start, calc_date_str))

            if len(data) < 60:
                continue

            # Convert to DataFrame
            df = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df['volume'] = df['volume'].astype(int)

            # Calculate factors
            momentum_result = momentum_factor.calculate(df, ticker)
            max_dd_result = max_dd_factor.calculate(df, ticker)
            liquidity_result = liquidity_factor.calculate(df, ticker, region)

            if not all([momentum_result, max_dd_result, liquidity_result]):
                continue

            # Get current price
            current_price = df.iloc[-1]['close']

            # Get forward price (1 month later)
            forward_query = """
                SELECT close
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s AND date = %s
            """
            forward_data = db.execute_query(forward_query, (ticker, region, forward_date))

            if not forward_data:
                continue

            forward_price = float(forward_data[0]['close'])
            forward_return = (forward_price - current_price) / current_price

            all_factor_values.append({
                'date': calc_date_str,
                'ticker': ticker,
                'momentum': momentum_result.raw_value,
                'max_drawdown': max_dd_result.raw_value,
                'liquidity': liquidity_result.raw_value,
                'forward_return': forward_return
            })

    if not all_factor_values:
        logger.error("❌ IC 계산 실패: 팩터 값 없음")
        return {}

    # Convert to DataFrame
    df_factors = pd.DataFrame(all_factor_values)

    # Calculate IC for each factor
    ic_results = {}

    for factor_name in ['momentum', 'max_drawdown', 'liquidity']:
        # Spearman correlation
        ic, p_value = stats.spearmanr(df_factors[factor_name], df_factors['forward_return'])
        ic_results[factor_name] = ic

        logger.info(f"   - {factor_name}: IC={ic:.3f}, p={p_value:.4f}")

    return ic_results


def optimize_factor_weights(ic_results: Dict[str, float]) -> Dict[str, float]:
    """
    IC 값 기반 팩터 가중치 최적화

    Parameters
    ----------
    ic_results : Dict[str, float]
        팩터별 IC 값

    Returns
    -------
    Dict[str, float]
        최적화된 가중치
    """
    # Use absolute IC values for weighting
    abs_ic = {k: abs(v) for k, v in ic_results.items()}
    total_ic = sum(abs_ic.values())

    if total_ic == 0:
        logger.warning("⚠️ 총 IC가 0입니다. 동일 가중 사용.")
        return {'max_drawdown': 1/3, 'liquidity': 1/3, 'momentum': 1/3}

    # Normalize to weights
    weights = {k: v / total_ic for k, v in abs_ic.items()}

    return weights


def load_price_data(
    tickers: list,
    start_date: str,
    end_date: str,
    region: str = 'KR'
) -> pd.DataFrame:
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
        logger.error(f"❌ No price data found for {len(tickers)} tickers")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(data, columns=['ticker', 'date', 'close'])
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = df['close'].astype(float)

    # Pivot to wide format
    price_df = df.pivot(index='date', columns='ticker', values='close')

    return price_df


def generate_portfolio_weights(
    signals_df: pd.DataFrame,
    price_df: pd.DataFrame
) -> pd.DataFrame:
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


def run_backtest(
    signals_df: pd.DataFrame,
    price_df: pd.DataFrame,
    initial_capital: float = INITIAL_CAPITAL
) -> Tuple[vbt.Portfolio, Dict]:
    """Run vectorbt backtest and return portfolio + metrics"""
    weights_df = generate_portfolio_weights(signals_df, price_df)

    portfolio = vbt.Portfolio.from_orders(
        close=price_df,
        size=weights_df,
        size_type='targetpercent',
        fees=TOTAL_COST,
        init_cash=initial_capital,
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


# ============================================================================
# Walk-Forward Optimization
# ============================================================================

def walk_forward_optimization():
    """Execute Walk-Forward Optimization (2024 only)"""

    logger.info("=" * 80)
    logger.info("Walk-Forward Optimization - Three-Factor Strategy (2024)")
    logger.info("=" * 80)

    logger.info(
        f"\n📋 Walk-Forward 설정:\n"
        f"   - In-Sample (Training): {IN_SAMPLE_START} ~ {IN_SAMPLE_END}\n"
        f"   - Out-of-Sample (Testing): {OUT_OF_SAMPLE_START} ~ {OUT_OF_SAMPLE_END}\n"
        f"   - Baseline (2024 전체): +18.09% return, Sharpe 0.870"
    )

    # ========================================================================
    # Step 1: In-Sample - Calculate IC and Optimize Weights
    # ========================================================================

    logger.info(f"\n{'='*80}")
    logger.info("Step 1: In-Sample Period (2024-01-01 ~ 2024-07-31)")
    logger.info(f"{'='*80}")

        # Calculate training and testing periods
        train_start = start + pd.DateOffset(months=roll_idx * ROLL_MONTHS)
        train_end = train_start + pd.DateOffset(months=TRAINING_MONTHS) - pd.Timedelta(days=1)
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.DateOffset(months=TESTING_MONTHS) - pd.Timedelta(days=1)

        # Skip if testing period exceeds data range
        if test_end > end:
            logger.warning(f"⚠️ Roll {roll_idx + 1}: Testing period exceeds data range. Stopping.")
            break

        train_start_str = train_start.strftime('%Y-%m-%d')
        train_end_str = train_end.strftime('%Y-%m-%d')
        test_start_str = test_start.strftime('%Y-%m-%d')
        test_end_str = test_end.strftime('%Y-%m-%d')

        logger.info(
            f"📅 기간:\n"
            f"   - Training: {train_start_str} ~ {train_end_str}\n"
            f"   - Testing:  {test_start_str} ~ {test_end_str}"
        )

        # ====================================================================
        # Step 1: Calculate IC on Training Window
        # ====================================================================

        logger.info(f"\n[1/4] Training Window IC 계산...")

        # Get universe for training period
        db = PostgresDatabaseManager()
        query = """
            SELECT DISTINCT ticker
            FROM ohlcv_data
            WHERE region = %s
              AND date BETWEEN %s AND %s
              AND volume > 0
            GROUP BY ticker
            HAVING COUNT(*) >= %s
        """

        train_tickers_data = db.execute_query(
            query,
            (REGION, train_start_str, train_end_str, MIN_DATA_DAYS)
        )

        train_tickers = [row['ticker'] for row in train_tickers_data]

        if len(train_tickers) < 50:
            logger.warning(f"⚠️ Roll {roll_idx + 1}: Training universe too small ({len(train_tickers)}). Skipping.")
            continue

        logger.info(f"   - Training Universe: {len(train_tickers)}개 종목")

        # Calculate IC
        ic_results = calculate_factor_ic(
            tickers=train_tickers,
            start_date=train_start_str,
            end_date=train_end_str,
            region=REGION
        )

        if not ic_results:
            logger.warning(f"⚠️ Roll {roll_idx + 1}: IC 계산 실패. Skipping.")
            continue

        logger.info(
            f"✅ IC 계산 완료:\n"
            f"   - Max_Drawdown: IC={ic_results.get('max_drawdown', 0):.3f}\n"
            f"   - Liquidity: IC={ic_results.get('liquidity', 0):.3f}\n"
            f"   - Momentum: IC={ic_results.get('momentum', 0):.3f}"
        )

        # ====================================================================
        # Step 2: Optimize Factor Weights
        # ====================================================================

        logger.info(f"\n[2/4] 팩터 가중치 최적화...")

        optimized_weights = optimize_factor_weights(ic_results)

        logger.info(
            f"✅ 최적 가중치:\n"
            f"   - Max_Drawdown: {optimized_weights.get('max_drawdown', 0):.3f}\n"
            f"   - Liquidity: {optimized_weights.get('liquidity', 0):.3f}\n"
            f"   - Momentum: {optimized_weights.get('momentum', 0):.3f}"
        )

        # ====================================================================
        # Step 3: Backtest on Testing Window (Out-of-Sample)
        # ====================================================================

        logger.info(f"\n[3/4] Testing Window 백테스트 (Out-of-Sample)...")

        # Initialize strategy with optimized weights
        strategy = ThreeFactorStrategy(
            factor_weights=optimized_weights,
            top_n=TOP_N,
            rebalance_freq=REBALANCE_FREQ,
            transaction_cost=TOTAL_COST
        )

        # Get universe for testing period
        test_tickers_data = db.execute_query(
            query,
            (REGION, test_start_str, test_end_str, MIN_DATA_DAYS // 2)  # Relax requirement for testing
        )

        test_tickers = [row['ticker'] for row in test_tickers_data]

        logger.info(f"   - Testing Universe: {len(test_tickers)}개 종목")

        # Generate signals
        signals_df = strategy.generate_signals(
            universe=test_tickers,
            start_date=test_start_str,
            end_date=test_end_str,
            region=REGION
        )

        if signals_df.empty:
            logger.warning(f"⚠️ Roll {roll_idx + 1}: 신호 생성 실패. Skipping.")
            continue

        # Load price data
        signal_tickers = signals_df['ticker'].unique().tolist()
        price_df = load_price_data(signal_tickers, test_start_str, test_end_str, REGION)

        if price_df.empty:
            logger.warning(f"⚠️ Roll {roll_idx + 1}: 가격 데이터 로드 실패. Skipping.")
            continue

        # Run backtest
        portfolio, metrics = run_backtest(signals_df, price_df)

        logger.info(
            f"✅ Testing Window 백테스트 완료:\n"
            f"   - 수익률: {metrics['total_return']*100:.2f}%\n"
            f"   - Sharpe: {metrics['sharpe_ratio']:.3f}\n"
            f"   - Max DD: {metrics['max_drawdown']*100:.2f}%\n"
            f"   - 거래 수: {metrics['total_trades']}"
        )

        # ====================================================================
        # Step 4: Store Results
        # ====================================================================

        result = {
            'roll': roll_idx + 1,
            'train_start': train_start_str,
            'train_end': train_end_str,
            'test_start': test_start_str,
            'test_end': test_end_str,
            'ic_max_drawdown': ic_results.get('max_drawdown', 0),
            'ic_liquidity': ic_results.get('liquidity', 0),
            'ic_momentum': ic_results.get('momentum', 0),
            'weight_max_drawdown': optimized_weights.get('max_drawdown', 0),
            'weight_liquidity': optimized_weights.get('liquidity', 0),
            'weight_momentum': optimized_weights.get('momentum', 0),
            'oos_return': metrics['total_return'],
            'oos_annual_return': metrics['annual_return'],
            'oos_sharpe': metrics['sharpe_ratio'],
            'oos_max_dd': metrics['max_drawdown'],
            'oos_win_rate': metrics['win_rate'],
            'oos_trades': metrics['total_trades']
        }

        all_results.append(result)

    # ========================================================================
    # Aggregate Results
    # ========================================================================

    if not all_results:
        logger.error("❌ Walk-Forward 최적화 실패: 유효한 롤 없음")
        return

    logger.info(f"\n{'='*80}")
    logger.info("Walk-Forward Optimization 결과 요약")
    logger.info(f"{'='*80}")

    df_results = pd.DataFrame(all_results)

    # Save results
    results_dir = project_root / 'backtest_results'
    results_dir.mkdir(exist_ok=True)

    results_file = results_dir / 'walk_forward_results.csv'
    df_results.to_csv(results_file, index=False)

    logger.info(f"💾 결과 저장: {results_file}")

    # Summary Statistics
    logger.info(f"\n📊 Out-of-Sample 성능 통계 ({len(df_results)}개 롤):")
    logger.info(f"   - 평균 수익률: {df_results['oos_return'].mean()*100:.2f}%")
    logger.info(f"   - 평균 Sharpe: {df_results['oos_sharpe'].mean():.3f}")
    logger.info(f"   - 평균 Max DD: {df_results['oos_max_dd'].mean()*100:.2f}%")
    logger.info(f"   - 평균 승률: {df_results['oos_win_rate'].mean()*100:.2f}%")

    # Factor Weight Stability
    logger.info(f"\n📈 팩터 가중치 안정성:")
    logger.info(f"   - Max_Drawdown: {df_results['weight_max_drawdown'].mean():.3f} ± {df_results['weight_max_drawdown'].std():.3f}")
    logger.info(f"   - Liquidity: {df_results['weight_liquidity'].mean():.3f} ± {df_results['weight_liquidity'].std():.3f}")
    logger.info(f"   - Momentum: {df_results['weight_momentum'].mean():.3f} ± {df_results['weight_momentum'].std():.3f}")

    # IC Stability
    logger.info(f"\n📉 IC 안정성:")
    logger.info(f"   - Max_Drawdown: {df_results['ic_max_drawdown'].mean():.3f} ± {df_results['ic_max_drawdown'].std():.3f}")
    logger.info(f"   - Liquidity: {df_results['ic_liquidity'].mean():.3f} ± {df_results['ic_liquidity'].std():.3f}")
    logger.info(f"   - Momentum: {df_results['ic_momentum'].mean():.3f} ± {df_results['ic_momentum'].std():.3f}")

    # Overfitting Check
    logger.info(f"\n🎯 과적합 검증:")

    # Compare with 2024 baseline (Story 1.1 result: +18.09%, Sharpe 0.870)
    baseline_return = 0.1809
    baseline_sharpe = 0.870

    avg_oos_return = df_results['oos_return'].mean()
    avg_oos_sharpe = df_results['oos_sharpe'].mean()

    degradation_return = (baseline_return - avg_oos_return) / baseline_return * 100
    degradation_sharpe = (baseline_sharpe - avg_oos_sharpe) / baseline_sharpe * 100

    logger.info(f"   - 2024 Baseline: Return={baseline_return*100:.2f}%, Sharpe={baseline_sharpe:.3f}")
    logger.info(f"   - WF Average: Return={avg_oos_return*100:.2f}%, Sharpe={avg_oos_sharpe:.3f}")
    logger.info(f"   - 성능 저하: Return {degradation_return:+.1f}%, Sharpe {degradation_sharpe:+.1f}%")

    if degradation_return < 30 and degradation_sharpe < 30:
        logger.info(f"   ✅ 과적합 없음: 성능 저하 <30%")
    elif degradation_return < 50 and degradation_sharpe < 50:
        logger.info(f"   ⚠️ 경미한 과적합: 성능 저하 30-50%")
    else:
        logger.info(f"   ❌ 과적합 의심: 성능 저하 >50%")

    logger.info(f"\n{'='*80}")
    logger.info("Walk-Forward Optimization 완료")
    logger.info(f"{'='*80}")


def main():
    """Main entry point"""
    walk_forward_optimization()


if __name__ == "__main__":
    main()
