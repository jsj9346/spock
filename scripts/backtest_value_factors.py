#!/usr/bin/env python3
"""
Simple Factor Performance Backtester

Backtests value factor performance by:
1. Loading historical factor scores and OHLCV data
2. Creating portfolios based on factor percentiles
3. Simulating monthly rebalancing
4. Calculating performance metrics

Usage:
    python3 scripts/backtest_value_factors.py --start 2023-01-01 --end 2025-10-22
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate simple returns from price data"""
    return prices.pct_change().fillna(0)


def calculate_portfolio_value(
    holdings: dict,
    prices: pd.DataFrame,
    date: pd.Timestamp
) -> float:
    """Calculate total portfolio value on a given date"""
    total_value = 0.0

    for ticker, shares in holdings.items():
        if ticker in prices.columns and date in prices.index:
            price = prices.loc[date, ticker]
            if not pd.isna(price):
                total_value += shares * price

    return total_value


def rebalance_portfolio(
    top_tickers: list,
    prices: pd.DataFrame,
    date: pd.Timestamp,
    capital: float
) -> dict:
    """Rebalance portfolio to equal-weight top tickers"""
    holdings = {}

    if not top_tickers:
        return holdings

    # Equal weight allocation
    weight_per_stock = 1.0 / len(top_tickers)
    capital_per_stock = capital * weight_per_stock

    for ticker in top_tickers:
        if ticker in prices.columns and date in prices.index:
            price = prices.loc[date, ticker]
            if not pd.isna(price) and price > 0:
                shares = int(capital_per_stock / price)
                holdings[ticker] = shares

    return holdings


def backtest_factor_strategy(
    db: PostgresDatabaseManager,
    factor_name: str,
    start_date: str,
    end_date: str,
    top_percentile: float = 80.0,
    initial_capital: float = 100_000_000,  # 1억 원
    rebalance_freq: str = 'M'  # Monthly
) -> pd.DataFrame:
    """
    Backtest a factor-based strategy

    Args:
        db: Database manager
        factor_name: Factor to backtest (PE_Ratio or PB_Ratio)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        initial_capital: Starting capital in KRW
        rebalance_freq: Rebalancing frequency ('M' = monthly, 'Q' = quarterly)

    Returns:
        DataFrame with daily portfolio values
    """
    logger.info(f"🔄 Backtesting {factor_name} strategy...")
    logger.info(f"   Period: {start_date} to {end_date}")
    logger.info(f"   Top Percentile: >{top_percentile}% (top {100-top_percentile}%)")
    logger.info(f"   Initial Capital: ₩{initial_capital:,.0f}")

    # Load OHLCV data for the period
    logger.info("📊 Loading OHLCV data...")

    ohlcv_query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date >= %s AND date <= %s
        ORDER BY date, ticker
    """

    ohlcv_data = db.execute_query(ohlcv_query, (start_date, end_date))

    if not ohlcv_data:
        logger.error("❌ No OHLCV data found for the period")
        return pd.DataFrame()

    # Pivot to get ticker columns
    df_ohlcv = pd.DataFrame(ohlcv_data)
    df_ohlcv['date'] = pd.to_datetime(df_ohlcv['date'])
    df_ohlcv['close'] = pd.to_numeric(df_ohlcv['close'], errors='coerce')

    prices = df_ohlcv.pivot(index='date', columns='ticker', values='close')
    logger.info(f"✅ Loaded {len(prices)} days, {len(prices.columns)} tickers")

    # Load factor scores (we only have latest, so use them for all rebalance dates)
    logger.info(f"📈 Loading {factor_name} scores...")

    factor_query = """
        SELECT ticker, percentile
        FROM factor_scores
        WHERE factor_name = %s AND region = 'KR'
        ORDER BY percentile DESC
    """

    factor_data = db.execute_query(factor_query, (factor_name,))

    if not factor_data:
        logger.error(f"❌ No factor data found for {factor_name}")
        return pd.DataFrame()

    df_factors = pd.DataFrame(factor_data)
    df_factors['percentile'] = pd.to_numeric(df_factors['percentile'], errors='coerce')

    # Get top tickers by percentile
    top_tickers = df_factors[df_factors['percentile'] >= top_percentile]['ticker'].tolist()
    logger.info(f"✅ Selected {len(top_tickers)} top stocks (>{top_percentile}%ile)")

    # Generate rebalance dates
    rebalance_dates = pd.date_range(start=start_date, end=end_date, freq=rebalance_freq)
    rebalance_dates = [d for d in rebalance_dates if d in prices.index]

    logger.info(f"📅 {len(rebalance_dates)} rebalance dates")

    # Simulate portfolio
    portfolio_values = []
    holdings = {}
    current_capital = initial_capital

    for i, date in enumerate(prices.index):
        # Rebalance if it's a rebalance date
        if date in rebalance_dates:
            logger.info(f"🔄 Rebalancing on {date.date()}...")

            # Calculate current portfolio value
            if holdings:
                current_capital = calculate_portfolio_value(holdings, prices, date)

            # Rebalance to equal-weight top tickers
            holdings = rebalance_portfolio(top_tickers, prices, date, current_capital)

            logger.info(f"   Portfolio value: ₩{current_capital:,.0f}")
            logger.info(f"   Positions: {len(holdings)}")

        # Calculate daily portfolio value
        portfolio_value = calculate_portfolio_value(holdings, prices, date)

        portfolio_values.append({
            'date': date,
            'value': portfolio_value,
            'positions': len(holdings)
        })

    return pd.DataFrame(portfolio_values)


def calculate_performance_metrics(portfolio_df: pd.DataFrame, initial_capital: float):
    """Calculate performance metrics from portfolio values"""

    if portfolio_df.empty or len(portfolio_df) < 2:
        logger.warning("⚠️ Insufficient data for performance metrics")
        return {}

    # Calculate returns
    portfolio_df['returns'] = portfolio_df['value'].pct_change().fillna(0)

    # Total return
    final_value = portfolio_df['value'].iloc[-1]
    total_return = (final_value / initial_capital - 1) * 100

    # Annualized return (assuming 252 trading days per year)
    days = len(portfolio_df)
    years = days / 252
    annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Volatility (annualized)
    volatility = portfolio_df['returns'].std() * np.sqrt(252) * 100

    # Sharpe ratio (assuming 0% risk-free rate)
    sharpe = annualized_return / volatility if volatility > 0 else 0

    # Maximum drawdown
    cumulative = (1 + portfolio_df['returns']).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100

    # Win rate
    win_rate = (portfolio_df['returns'] > 0).sum() / len(portfolio_df) * 100

    return {
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'final_value': final_value
    }


def main():
    """Main execution"""
    logger.info("=== Factor Performance Backtester ===\n")

    db = PostgresDatabaseManager()

    # Backtest parameters
    start_date = "2023-01-01"
    end_date = "2025-10-22"
    initial_capital = 100_000_000  # 1억 원

    # Test both P/E and P/B factors
    factors_to_test = ['PE_Ratio', 'PB_Ratio']

    results = {}

    for factor_name in factors_to_test:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing {factor_name} Factor")
        logger.info(f"{'='*80}\n")

        # Run backtest
        portfolio_df = backtest_factor_strategy(
            db=db,
            factor_name=factor_name,
            start_date=start_date,
            end_date=end_date,
            top_percentile=80.0,  # Top 20% stocks
            initial_capital=initial_capital,
            rebalance_freq='M'  # Monthly rebalancing
        )

        if portfolio_df.empty:
            logger.error(f"❌ Backtest failed for {factor_name}")
            continue

        # Calculate metrics
        metrics = calculate_performance_metrics(portfolio_df, initial_capital)
        results[factor_name] = metrics

        # Display results
        logger.info(f"\n📊 {factor_name} Performance Metrics:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Return:       {metrics['total_return']:>10.2f}%")
        logger.info(f"Annualized Return:  {metrics['annualized_return']:>10.2f}%")
        logger.info(f"Volatility:         {metrics['volatility']:>10.2f}%")
        logger.info(f"Sharpe Ratio:       {metrics['sharpe_ratio']:>10.2f}")
        logger.info(f"Max Drawdown:       {metrics['max_drawdown']:>10.2f}%")
        logger.info(f"Win Rate:           {metrics['win_rate']:>10.2f}%")
        logger.info(f"Final Value:        ₩{metrics['final_value']:>15,.0f}")
        logger.info(f"{'='*80}\n")

    # Summary comparison
    if len(results) > 1:
        logger.info("\n🏆 Factor Comparison Summary:")
        logger.info(f"{'='*80}")
        logger.info(f"{'Factor':<15} {'Return':<12} {'Sharpe':<10} {'Max DD':<10}")
        logger.info(f"{'-'*80}")

        for factor_name, metrics in results.items():
            logger.info(
                f"{factor_name:<15} "
                f"{metrics['annualized_return']:>10.2f}%  "
                f"{metrics['sharpe_ratio']:>8.2f}  "
                f"{metrics['max_drawdown']:>8.2f}%"
            )
        logger.info(f"{'='*80}\n")

    logger.info("✅ Backtest complete!")


if __name__ == "__main__":
    main()
