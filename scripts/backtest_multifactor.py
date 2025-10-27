#!/usr/bin/env python3
"""
Multi-Factor Strategy Backtester

Compares performance of different factor combinations:
1. Value only (PE + PB)
2. Momentum only (12M + RSI)
3. Quality only (Earnings + BookValue + Dividend)
4. Multi-factor (Value + Momentum + Quality)

Usage:
    python3 scripts/backtest_multifactor.py --start 2023-01-01 --end 2025-10-22
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


def get_top_stocks_multi_factor(
    db: PostgresDatabaseManager,
    factor_names: list,
    top_percentile: float = 80.0,
    rebalance_date: pd.Timestamp = None
) -> list:
    """
    Get top stocks by combined factor scores

    Args:
        db: Database manager
        factor_names: List of factor names to combine
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        rebalance_date: Date to use (if None, use latest)

    Returns:
        List of ticker codes
    """
    if rebalance_date is None:
        rebalance_date = pd.Timestamp.today()

    # Load factor scores for specified factors
    placeholders = ', '.join(['%s'] * len(factor_names))
    query = f"""
        SELECT ticker, factor_name, percentile
        FROM factor_scores
        WHERE factor_name IN ({placeholders})
          AND region = 'KR'
          AND date <= %s
        ORDER BY ticker, factor_name
    """

    params = factor_names + [rebalance_date.date()]
    factor_data = db.execute_query(query, tuple(params))

    if not factor_data:
        logger.warning(f"No factor data found for {factor_names} on {rebalance_date.date()}")
        return []

    df = pd.DataFrame(factor_data)
    df['percentile'] = pd.to_numeric(df['percentile'], errors='coerce')

    # Pivot to get one row per ticker
    df_pivot = df.pivot(index='ticker', columns='factor_name', values='percentile')

    # Only keep stocks with all factors available
    df_pivot = df_pivot.dropna()

    if len(df_pivot) == 0:
        logger.warning(f"No stocks with all factors on {rebalance_date.date()}")
        return []

    # Calculate composite score (equal weight average)
    df_pivot['composite_score'] = df_pivot.mean(axis=1)

    # Select top percentile
    top_tickers = df_pivot[df_pivot['composite_score'] >= top_percentile].index.tolist()

    logger.info(f"Selected {len(top_tickers)} stocks (composite score >= {top_percentile}%ile)")
    return top_tickers


def backtest_strategy(
    db: PostgresDatabaseManager,
    strategy_name: str,
    factor_names: list,
    start_date: str,
    end_date: str,
    top_percentile: float = 80.0,
    initial_capital: float = 100_000_000,  # 1억 원
    rebalance_freq: str = 'M'  # Monthly
) -> pd.DataFrame:
    """
    Backtest a multi-factor strategy

    Args:
        db: Database manager
        strategy_name: Name of the strategy (for logging)
        factor_names: List of factors to combine
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        initial_capital: Starting capital in KRW
        rebalance_freq: Rebalancing frequency ('M' = monthly)

    Returns:
        DataFrame with daily portfolio values
    """
    logger.info(f"🔄 Backtesting {strategy_name} strategy...")
    logger.info(f"   Factors: {', '.join(factor_names)}")
    logger.info(f"   Period: {start_date} to {end_date}")
    logger.info(f"   Top Percentile: >{top_percentile}% (top {100-top_percentile}%)")
    logger.info(f"   Initial Capital: ₩{initial_capital:,.0f}")

    # Load OHLCV data for the period
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

    # Generate rebalance dates
    rebalance_dates = pd.date_range(start=start_date, end=end_date, freq=rebalance_freq)
    rebalance_dates = [d for d in rebalance_dates if d in prices.index]

    logger.info(f"📅 {len(rebalance_dates)} rebalance dates")

    # Simulate portfolio
    portfolio_values = []
    holdings = {}
    current_capital = initial_capital
    last_top_tickers = []

    for i, date in enumerate(prices.index):
        # Rebalance if it's a rebalance date
        if date in rebalance_dates:
            logger.info(f"🔄 Rebalancing on {date.date()}...")

            # Calculate current portfolio value
            if holdings:
                current_capital = calculate_portfolio_value(holdings, prices, date)

            # Get top tickers based on factor scores
            top_tickers = get_top_stocks_multi_factor(
                db, factor_names, top_percentile, date
            )

            if len(top_tickers) == 0:
                logger.warning(f"⚠️ No stocks selected on {date.date()}, keeping previous positions")
                top_tickers = last_top_tickers

            # Rebalance to equal-weight top tickers
            holdings = rebalance_portfolio(top_tickers, prices, date, current_capital)

            logger.info(f"   Portfolio value: ₩{current_capital:,.0f}")
            logger.info(f"   Positions: {len(holdings)}")

            last_top_tickers = top_tickers

        # Calculate daily portfolio value
        portfolio_value = calculate_portfolio_value(holdings, prices, date)

        portfolio_values.append({
            'date': date,
            'value': portfolio_value,
            'positions': len(holdings)
        })

    return pd.DataFrame(portfolio_values)


def calculate_performance_metrics(portfolio_df: pd.DataFrame, initial_capital: float, strategy_name: str):
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

    metrics = {
        'strategy': strategy_name,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'final_value': final_value
    }

    return metrics


def main():
    """Main execution"""
    logger.info("=== Multi-Factor Strategy Backtester ===\n")

    db = PostgresDatabaseManager()

    # Backtest parameters
    start_date = "2023-01-01"
    end_date = "2025-10-22"
    initial_capital = 100_000_000  # 1억 원

    # Define strategies to test
    strategies = [
        {
            'name': 'Value (PE+PB)',
            'factors': ['PE_Ratio', 'PB_Ratio']
        },
        {
            'name': 'Momentum (12M+RSI)',
            'factors': ['12M_Momentum', 'RSI_Momentum']
        },
        {
            'name': 'Quality (Earnings+BookValue+Dividend)',
            'factors': ['Earnings_Quality', 'Book_Value_Quality', 'Dividend_Stability']
        },
        {
            'name': 'Multi-Factor (Value+Momentum+Quality)',
            'factors': ['PE_Ratio', 'PB_Ratio', '12M_Momentum', 'RSI_Momentum',
                       'Earnings_Quality', 'Book_Value_Quality', 'Dividend_Stability']
        }
    ]

    results = []

    for strategy in strategies:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing {strategy['name']} Strategy")
        logger.info(f"{'='*80}\n")

        # Run backtest
        portfolio_df = backtest_strategy(
            db=db,
            strategy_name=strategy['name'],
            factor_names=strategy['factors'],
            start_date=start_date,
            end_date=end_date,
            top_percentile=80.0,  # Top 20% stocks
            initial_capital=initial_capital,
            rebalance_freq='M'  # Monthly rebalancing
        )

        if portfolio_df.empty:
            logger.error(f"❌ Backtest failed for {strategy['name']}")
            continue

        # Calculate metrics
        metrics = calculate_performance_metrics(portfolio_df, initial_capital, strategy['name'])
        results.append(metrics)

        # Display results
        logger.info(f"\n📊 {strategy['name']} Performance Metrics:")
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
        logger.info("\n🏆 Strategy Comparison Summary:")
        logger.info(f"{'='*100}")
        logger.info(f"{'Strategy':<40} {'Return':<12} {'Sharpe':<10} {'Max DD':<10} {'Win %':<10}")
        logger.info(f"{'-'*100}")

        for metrics in results:
            logger.info(
                f"{metrics['strategy']:<40} "
                f"{metrics['annualized_return']:>10.2f}%  "
                f"{metrics['sharpe_ratio']:>8.2f}  "
                f"{metrics['max_drawdown']:>8.2f}%  "
                f"{metrics['win_rate']:>8.2f}%"
            )
        logger.info(f"{'='*100}\n")

        # Find best strategy by Sharpe ratio
        best_strategy = max(results, key=lambda x: x['sharpe_ratio'])
        logger.info(f"🥇 Best Strategy (by Sharpe Ratio): {best_strategy['strategy']}")
        logger.info(f"   Sharpe: {best_strategy['sharpe_ratio']:.2f}")
        logger.info(f"   Annualized Return: {best_strategy['annualized_return']:.2f}%")

    logger.info("\n✅ Multi-factor backtest complete!")


if __name__ == "__main__":
    main()
