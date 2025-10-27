#!/usr/bin/env python3
"""
Equal-Weighted Multi-Factor Strategy Backtest

Backtests an equal-weighted baseline strategy for comparison with IC-weighted approach:
- Operating_Profit_Margin: 20%
- ROE_Proxy: 20%
- PE_Ratio: 20%
- 12M_Momentum: 20%
- PB_Ratio: 20%

Includes realistic transaction costs:
- Commission: 0.015% (KIS API standard)
- Slippage: 0.05% (market impact)
- Spread: 0.10% (bid-ask)
- Total round-trip: 0.33%

Usage:
    # Full backtest (2020-2024)
    python3 scripts/backtest_equal_weighted_strategy.py --start 2020-01-01 --end 2024-12-31

    # Shorter period
    python3 scripts/backtest_equal_weighted_strategy.py --start 2023-01-01 --end 2025-10-24

    # Custom parameters
    python3 scripts/backtest_equal_weighted_strategy.py \
      --start 2020-01-01 \
      --end 2024-12-31 \
      --capital 100000000 \
      --top-percentile 80 \
      --rebalance-freq M

Author: Spock Quant Platform
Date: 2025-10-24
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


# Equal-Weighted Factor Configuration (baseline for comparison)
FACTOR_WEIGHTS = {
    'Operating_Profit_Margin': 0.20,  # Equal weight
    'ROE_Proxy': 0.20,                # Equal weight
    'PE_Ratio': 0.20,                 # Equal weight
    '12M_Momentum': 0.20,             # Equal weight
    'PB_Ratio': 0.20                  # Equal weight
}

# Transaction Cost Model (KIS API + Market Impact)
TRANSACTION_COSTS = {
    'commission_pct': 0.00015,   # 0.015% commission (KIS standard)
    'slippage_pct': 0.0005,      # 0.05% slippage (market impact)
    'spread_pct': 0.001          # 0.10% spread (bid-ask)
}


def calculate_transaction_cost(trade_value: float) -> float:
    """
    Calculate total transaction cost for a trade

    Args:
        trade_value: Trade value in KRW

    Returns:
        Transaction cost in KRW
    """
    commission = trade_value * TRANSACTION_COSTS['commission_pct']
    slippage = trade_value * TRANSACTION_COSTS['slippage_pct']
    spread = trade_value * TRANSACTION_COSTS['spread_pct']

    return commission + slippage + spread


def get_top_stocks_equal_weighted(
    db: PostgresDatabaseManager,
    factor_weights: dict,
    top_percentile: float,
    rebalance_date: pd.Timestamp
) -> list:
    """
    Get top stocks by equal-weighted composite factor score

    Args:
        db: Database manager
        factor_weights: Dict of {factor_name: weight} (all equal for this strategy)
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        rebalance_date: Date to use for factor scores

    Returns:
        List of ticker codes
    """
    factor_names = list(factor_weights.keys())

    # Load factor scores for specified factors
    placeholders = ', '.join(['%s'] * len(factor_names))
    query = f"""
        SELECT ticker, factor_name, percentile
        FROM factor_scores
        WHERE factor_name IN ({placeholders})
          AND region = 'KR'
          AND date = (
              SELECT MAX(date)
              FROM factor_scores
              WHERE date <= %s AND region = 'KR'
          )
        ORDER BY ticker, factor_name
    """

    params = factor_names + [rebalance_date.date()]
    factor_data = db.execute_query(query, tuple(params))

    if not factor_data:
        logger.warning(f"No factor data found for {rebalance_date.date()}")
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

    # Calculate equal-weighted composite score (simple mean)
    df_pivot['composite_score'] = df_pivot[list(factor_weights.keys())].mean(axis=1)

    # Select top percentile
    top_tickers = df_pivot[df_pivot['composite_score'] >= top_percentile].index.tolist()

    logger.info(f"  Selected {len(top_tickers)} stocks (Equal-weighted score >= {top_percentile}%ile)")
    return top_tickers


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
) -> tuple:
    """
    Rebalance portfolio to equal-weight top tickers with transaction costs

    Returns:
        (holdings dict, transaction cost)
    """
    holdings = {}

    if not top_tickers:
        return holdings, 0.0

    # Equal weight allocation
    weight_per_stock = 1.0 / len(top_tickers)
    capital_per_stock = capital * weight_per_stock

    total_trade_value = 0.0

    for ticker in top_tickers:
        if ticker in prices.columns and date in prices.index:
            price = prices.loc[date, ticker]
            if not pd.isna(price) and price > 0:
                shares = int(capital_per_stock / price)
                holdings[ticker] = shares
                total_trade_value += shares * price

    # Calculate transaction costs (buying new positions)
    transaction_cost = calculate_transaction_cost(total_trade_value)

    return holdings, transaction_cost


def backtest_equal_weighted_strategy(
    db: PostgresDatabaseManager,
    start_date: str,
    end_date: str,
    factor_weights: dict,
    top_percentile: float = 80.0,
    initial_capital: float = 100_000_000,  # 1억 원
    rebalance_freq: str = 'M'  # Monthly
) -> pd.DataFrame:
    """
    Backtest equal-weighted multi-factor strategy with transaction costs

    Args:
        db: Database manager
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        factor_weights: Dict of {factor_name: weight} (all equal for this strategy)
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        initial_capital: Starting capital in KRW
        rebalance_freq: Rebalancing frequency ('M' = monthly)

    Returns:
        DataFrame with daily portfolio values
    """
    logger.info("=" * 80)
    logger.info("EQUAL-WEIGHTED MULTI-FACTOR STRATEGY BACKTEST")
    logger.info("=" * 80)
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Initial Capital: ₩{initial_capital:,.0f}")
    logger.info(f"Top Percentile: >{top_percentile}% (top {100-top_percentile}%)")
    logger.info(f"Rebalance Frequency: {rebalance_freq}")
    logger.info("")
    logger.info("Factor Weights (Equal-Weighted):")
    for factor, weight in factor_weights.items():
        logger.info(f"  {factor:30s}: {weight:5.1%}")
    logger.info("")
    logger.info("Transaction Cost Model:")
    logger.info(f"  Commission:  {TRANSACTION_COSTS['commission_pct']*100:.3f}%")
    logger.info(f"  Slippage:    {TRANSACTION_COSTS['slippage_pct']*100:.3f}%")
    logger.info(f"  Spread:      {TRANSACTION_COSTS['spread_pct']*100:.3f}%")
    logger.info(f"  Total (round-trip): {sum(TRANSACTION_COSTS.values())*200:.3f}%")
    logger.info("=" * 80)
    logger.info("")

    # Load OHLCV data for the period
    logger.info("Loading OHLCV data...")
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
    logger.info("")

    # Generate rebalance dates
    # Use 'ME' (month-end) instead of deprecated 'M'
    freq_map = {'M': 'ME', 'Q': 'QE', 'Y': 'YE'}
    freq = freq_map.get(rebalance_freq, rebalance_freq)
    rebalance_dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    rebalance_dates = [d for d in rebalance_dates if d in prices.index]

    logger.info(f"📅 {len(rebalance_dates)} rebalance dates: {rebalance_dates[0].date()} to {rebalance_dates[-1].date()}")
    logger.info("")

    # Simulate portfolio
    portfolio_values = []
    holdings = {}
    current_capital = initial_capital
    last_top_tickers = []
    total_transaction_costs = 0.0

    logger.info("Running backtest simulation...")
    logger.info("")

    for i, date in enumerate(prices.index):
        # Rebalance if it's a rebalance date
        if date in rebalance_dates:
            logger.info(f"🔄 Rebalancing {rebalance_dates.index(date)+1}/{len(rebalance_dates)}: {date.date()}...")

            # Calculate current portfolio value
            if holdings:
                portfolio_value = calculate_portfolio_value(holdings, prices, date)

                # Calculate selling transaction costs
                sell_value = portfolio_value
                sell_cost = calculate_transaction_cost(sell_value)
                total_transaction_costs += sell_cost

                current_capital = portfolio_value - sell_cost
                logger.info(f"  Pre-rebalance value: ₩{portfolio_value:,.0f} (sell cost: ₩{sell_cost:,.0f})")

            # Get top tickers based on equal-weighted factor scores
            top_tickers = get_top_stocks_equal_weighted(
                db, factor_weights, top_percentile, date
            )

            if len(top_tickers) == 0:
                logger.warning(f"  ⚠️ No stocks selected, keeping previous positions")
                top_tickers = last_top_tickers

            # Rebalance to equal-weight top tickers
            holdings, buy_cost = rebalance_portfolio(top_tickers, prices, date, current_capital)
            total_transaction_costs += buy_cost
            current_capital -= buy_cost

            post_value = calculate_portfolio_value(holdings, prices, date)

            logger.info(f"  Post-rebalance value: ₩{post_value:,.0f} (buy cost: ₩{buy_cost:,.0f})")
            logger.info(f"  Positions: {len(holdings)}")
            logger.info(f"  Cumulative costs: ₩{total_transaction_costs:,.0f}")
            logger.info("")

            last_top_tickers = top_tickers

        # Calculate daily portfolio value
        portfolio_value = calculate_portfolio_value(holdings, prices, date)

        portfolio_values.append({
            'date': date,
            'value': portfolio_value,
            'positions': len(holdings),
            'cumulative_costs': total_transaction_costs
        })

    logger.info("✅ Backtest simulation complete")
    logger.info("")

    return pd.DataFrame(portfolio_values)


def calculate_performance_metrics(
    portfolio_df: pd.DataFrame,
    initial_capital: float
) -> dict:
    """Calculate comprehensive performance metrics"""

    if portfolio_df.empty or len(portfolio_df) < 2:
        logger.warning("⚠️ Insufficient data for performance metrics")
        return {}

    # Filter to only rows with non-zero portfolio value (after first rebalance)
    portfolio_df_active = portfolio_df[portfolio_df['value'] > 0].copy()

    if len(portfolio_df_active) < 2:
        logger.warning("⚠️ Insufficient active trading days for performance metrics")
        return {}

    # Calculate returns (exclude first return which may be inf from 0 → value transition)
    portfolio_df_active['returns'] = portfolio_df_active['value'].pct_change()

    # Remove inf and nan values from returns for metric calculations
    valid_returns = portfolio_df_active['returns'].replace([np.inf, -np.inf], np.nan).dropna()

    if len(valid_returns) < 2:
        logger.warning("⚠️ Insufficient valid returns for performance metrics")
        return {}

    # Total return (based on actual portfolio values, not daily returns)
    first_value = portfolio_df_active['value'].iloc[0]
    final_value = portfolio_df_active['value'].iloc[-1]
    total_costs = portfolio_df_active['cumulative_costs'].iloc[-1]
    total_return = (final_value / first_value - 1) * 100

    # Annualized return (assuming 252 trading days per year)
    days = len(portfolio_df_active)
    years = days / 252
    annualized_return = ((final_value / first_value) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Volatility (annualized) - using valid returns only
    volatility = valid_returns.std() * np.sqrt(252) * 100

    # Sharpe ratio (assuming 0% risk-free rate)
    sharpe = annualized_return / volatility if volatility > 0 else 0

    # Maximum drawdown - recalculate cumulative returns from valid returns
    cumulative = (1 + valid_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100

    # Average drawdown
    avg_drawdown = drawdown[drawdown < 0].mean() * 100 if (drawdown < 0).any() else 0

    # Calmar ratio (annualized return / max drawdown)
    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # Win rate (% positive days) - using valid returns
    win_rate = (valid_returns > 0).sum() / len(valid_returns) * 100

    # Best/worst day - using valid returns
    best_day = valid_returns.max() * 100
    worst_day = valid_returns.min() * 100

    # Transaction cost impact (relative to first portfolio value)
    cost_impact = (total_costs / first_value) * 100

    metrics = {
        'initial_capital': initial_capital,
        'first_portfolio_value': first_value,
        'final_value': final_value,
        'total_profit': final_value - first_value,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'avg_drawdown': avg_drawdown,
        'calmar_ratio': calmar,
        'win_rate': win_rate,
        'best_day': best_day,
        'worst_day': worst_day,
        'total_costs': total_costs,
        'cost_impact_pct': cost_impact,
        'days': days,
        'years': years
    }

    return metrics


def print_performance_report(metrics: dict):
    """Print comprehensive performance report"""

    logger.info("=" * 80)
    logger.info("BACKTEST PERFORMANCE REPORT")
    logger.info("=" * 80)
    logger.info("")

    logger.info("📊 Portfolio Summary:")
    logger.info(f"  Initial Capital:         ₩{metrics['initial_capital']:>15,.0f}")
    logger.info(f"  First Portfolio Value:   ₩{metrics['first_portfolio_value']:>15,.0f}")
    logger.info(f"  Final Value:             ₩{metrics['final_value']:>15,.0f}")
    logger.info(f"  Total Profit:            ₩{metrics['total_profit']:>15,.0f}")
    logger.info("")

    logger.info("📈 Return Metrics:")
    logger.info(f"  Total Return:       {metrics['total_return']:>10.2f}%")
    logger.info(f"  Annualized Return:  {metrics['annualized_return']:>10.2f}%")
    logger.info(f"  Volatility (ann.):  {metrics['volatility']:>10.2f}%")
    logger.info("")

    logger.info("⚖️ Risk-Adjusted Performance:")
    logger.info(f"  Sharpe Ratio:       {metrics['sharpe_ratio']:>10.2f}")
    logger.info(f"  Calmar Ratio:       {metrics['calmar_ratio']:>10.2f}")
    logger.info("")

    logger.info("📉 Risk Metrics:")
    logger.info(f"  Max Drawdown:       {metrics['max_drawdown']:>10.2f}%")
    logger.info(f"  Avg Drawdown:       {metrics['avg_drawdown']:>10.2f}%")
    logger.info(f"  Best Day:           {metrics['best_day']:>10.2f}%")
    logger.info(f"  Worst Day:          {metrics['worst_day']:>10.2f}%")
    logger.info("")

    logger.info("💰 Transaction Costs:")
    logger.info(f"  Total Costs:        ₩{metrics['total_costs']:>15,.0f}")
    logger.info(f"  Cost Impact:        {metrics['cost_impact_pct']:>10.2f}% of initial capital")
    logger.info(f"  Annual Cost Drag:   {metrics['cost_impact_pct']/metrics['years']:>10.2f}%")
    logger.info("")

    logger.info("📅 Trading Activity:")
    logger.info(f"  Win Rate (days):    {metrics['win_rate']:>10.2f}%")
    logger.info(f"  Total Days:         {metrics['days']:>10.0f} days")
    logger.info(f"  Period:             {metrics['years']:>10.2f} years")
    logger.info("")

    logger.info("=" * 80)
    logger.info("")

    # Performance assessment
    logger.info("🎯 Performance Assessment:")
    if metrics['sharpe_ratio'] >= 1.5:
        logger.info("  ⭐⭐⭐ EXCELLENT - Sharpe ratio exceeds 1.5 target")
    elif metrics['sharpe_ratio'] >= 1.0:
        logger.info("  ⭐⭐ GOOD - Sharpe ratio exceeds 1.0 (industry standard)")
    else:
        logger.info("  ⚠️ BELOW TARGET - Sharpe ratio below 1.0")

    if abs(metrics['max_drawdown']) <= 15:
        logger.info("  ✅ CONTROLLED RISK - Max drawdown within 15% target")
    else:
        logger.info(f"  ⚠️ HIGH RISK - Max drawdown {abs(metrics['max_drawdown']):.1f}% exceeds 15% target")

    if metrics['annualized_return'] >= 15:
        logger.info("  ✅ STRONG RETURNS - Annualized return exceeds 15% target")
    elif metrics['annualized_return'] >= 8:
        logger.info("  ✅ OUTPERFORMANCE - Annualized return exceeds KOSPI ~8%")
    else:
        logger.info("  ⚠️ UNDERPERFORMANCE - Annualized return below KOSPI benchmark")

    logger.info("=" * 80)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description='Backtest IC-weighted multi-factor strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full backtest (2020-2024)
  python3 scripts/backtest_ic_weighted_strategy.py --start 2020-01-01 --end 2024-12-31

  # Shorter period
  python3 scripts/backtest_ic_weighted_strategy.py --start 2023-01-01 --end 2025-10-24

  # Custom parameters
  python3 scripts/backtest_ic_weighted_strategy.py \\
    --start 2020-01-01 \\
    --end 2024-12-31 \\
    --capital 100000000 \\
    --top-percentile 80 \\
    --rebalance-freq M
        """
    )

    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000, help='Initial capital in KRW (default: 100M)')
    parser.add_argument('--top-percentile', type=float, default=80.0, help='Top percentile threshold (default: 80 = top 20%%)')
    parser.add_argument('--rebalance-freq', type=str, default='M', help='Rebalancing frequency (default: M = monthly)')

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager()

    # Run backtest
    portfolio_df = backtest_equal_weighted_strategy(
        db=db,
        start_date=args.start,
        end_date=args.end,
        factor_weights=FACTOR_WEIGHTS,
        top_percentile=args.top_percentile,
        initial_capital=args.capital,
        rebalance_freq=args.rebalance_freq
    )

    if portfolio_df.empty:
        logger.error("❌ Backtest failed - no data")
        return 1

    # Calculate performance metrics
    metrics = calculate_performance_metrics(portfolio_df, args.capital)

    # Print performance report
    print_performance_report(metrics)

    # Save results to CSV
    output_dir = Path("backtest_results")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = output_dir / f"equal_weighted_backtest_{args.start}_{args.end}_{timestamp}.csv"

    portfolio_df.to_csv(csv_path, index=False)
    logger.info(f"💾 Results saved: {csv_path}")
    logger.info("")

    logger.info("✅ Backtest complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
