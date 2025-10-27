#!/usr/bin/env python3
"""
Orthogonal Factor IC-Weighted Strategy Backtest

Backtests multi-factor strategy using ONLY orthogonal factors
(max pairwise correlation < 0.5) to maximize diversification.

This addresses the critical redundancy issues discovered in factor analysis:
- Earnings_Quality ≡ PE_Ratio (r=1.000) - Using PE_Ratio (has IC data)
- Book_Value_Quality ≡ PB_Ratio (r=1.000) - REMOVED

Recommended orthogonal factors:
- 12M_Momentum
- 1M_Momentum
- PE_Ratio (alias: Earnings_Quality)

Usage:
    # Use recommended orthogonal factors
    python3 scripts/backtest_orthogonal_factors.py \
      --start 2021-01-04 \
      --end 2024-10-09 \
      --capital 100000000

    # Custom factor selection
    python3 scripts/backtest_orthogonal_factors.py \
      --start 2021-01-04 \
      --end 2024-10-09 \
      --factors "12M_Momentum,1M_Momentum,ROE_Proxy"

Author: Spock Quant Platform
Date: 2025-10-24
"""

import sys
from pathlib import Path
from datetime import datetime
import argparse
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.optimization.factor_optimizer import FactorOptimizer
from modules.ic_calculator import RollingICCalculator

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

# Default orthogonal factors (from correlation analysis)
DEFAULT_ORTHOGONAL_FACTORS = [
    '12M_Momentum',
    '1M_Momentum',
    'PE_Ratio'  # FIX: PE_Ratio exists in DB (Earnings_Quality was alias with no IC data)
]

# Transaction Cost Model
TRANSACTION_COSTS = {
    'commission_pct': 0.00015,   # 0.015% commission
    'slippage_pct': 0.0005,      # 0.05% slippage
    'spread_pct': 0.001          # 0.10% spread
}


def calculate_transaction_cost(trade_value: float) -> float:
    """Calculate total transaction cost for a trade"""
    commission = trade_value * TRANSACTION_COSTS['commission_pct']
    slippage = trade_value * TRANSACTION_COSTS['slippage_pct']
    spread = trade_value * TRANSACTION_COSTS['spread_pct']
    return commission + slippage + spread


def get_ic_weights(
    db: PostgresDatabaseManager,
    factors: list,
    ic_start_date: str,
    ic_end_date: str
) -> dict:
    """
    Calculate IC weights for specified factors (MUST precede backtest period to avoid look-ahead bias)

    Args:
        db: Database manager
        factors: List of factor names
        ic_start_date: Start date for IC calculation (should precede backtest)
        ic_end_date: End date for IC calculation (should precede backtest)

    Returns:
        Dict of {factor_name: ic_weight}
    """
    query = """
        SELECT
            factor_name,
            AVG(ic) as avg_ic,
            COUNT(*) as num_obs
        FROM ic_time_series
        WHERE region = 'KR'
          AND date >= %s
          AND date <= %s
          AND factor_name = ANY(%s)
        GROUP BY factor_name
        HAVING COUNT(*) >= 100
    """

    results = db.execute_query(query, (ic_start_date, ic_end_date, factors))

    ic_weights = {}
    total_abs_ic = 0.0

    for row in results:
        factor = row['factor_name']
        avg_ic = float(row['avg_ic'])
        # FIX: Use ABS(IC) - factors contribute based on predictive strength, not direction
        ic_weights[factor] = abs(avg_ic)
        total_abs_ic += abs(avg_ic)

    # Normalize to sum to 1.0 (all weights positive now)
    if total_abs_ic > 0:
        for factor in ic_weights:
            ic_weights[factor] = ic_weights[factor] / total_abs_ic

    logger.info(f"\n📊 IC Weights (normalized, ABS values - all positive):")
    for factor, weight in sorted(ic_weights.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {factor:30s}: {weight:6.2%}")

    return ic_weights


def get_top_stocks_ic_weighted(
    db: PostgresDatabaseManager,
    factor_weights: dict,
    top_percentile: float,
    rebalance_date: pd.Timestamp
) -> list:
    """
    Select top stocks using IC-weighted composite score

    Args:
        db: Database manager
        factor_weights: Dict of {factor_name: weight}
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        rebalance_date: Date for factor scores

    Returns:
        List of (ticker, composite_score) tuples
    """
    # Get factor scores for all factors
    query = """
        SELECT ticker, factor_name, score
        FROM factor_scores
        WHERE region = 'KR'
          AND date = %s
          AND factor_name = ANY(%s)
        ORDER BY ticker, factor_name
    """

    factors = list(factor_weights.keys())
    date_str = rebalance_date.strftime('%Y-%m-%d')

    results = db.execute_query(query, (date_str, factors))

    if not results:
        logger.warning(f"No factor scores found for {date_str}")
        return []

    # Pivot to wide format
    df = pd.DataFrame(results)
    # Convert Decimal to float
    df['score'] = df['score'].astype(float)
    pivot_df = df.pivot(index='ticker', columns='factor_name', values='score')

    # Calculate IC-weighted composite score
    composite_scores = pd.Series(0.0, index=pivot_df.index)

    for factor, weight in factor_weights.items():
        if factor in pivot_df.columns:
            composite_scores += weight * pivot_df[factor].fillna(0)

    # Select top percentile
    threshold = np.percentile(composite_scores.dropna(), top_percentile)
    top_stocks = composite_scores[composite_scores >= threshold].sort_values(ascending=False)

    logger.info(f"  Selected {len(top_stocks)} stocks (>{top_percentile}th percentile)")

    return list(zip(top_stocks.index, top_stocks.values))


def get_top_stocks_equal_weighted(
    db: PostgresDatabaseManager,
    factors: list,
    top_percentile: float,
    rebalance_date: pd.Timestamp
) -> list:
    """
    Select top stocks using equal-weighted composite score (1/n per factor)

    Args:
        db: Database manager
        factors: List of factor names
        top_percentile: Percentile threshold (e.g., 80 = top 20%)
        rebalance_date: Date for factor scores

    Returns:
        List of (ticker, composite_score) tuples
    """
    # Get factor scores for all factors
    query = """
        SELECT ticker, factor_name, score
        FROM factor_scores
        WHERE region = 'KR'
          AND date = %s
          AND factor_name = ANY(%s)
        ORDER BY ticker, factor_name
    """

    date_str = rebalance_date.strftime('%Y-%m-%d')

    results = db.execute_query(query, (date_str, factors))

    if not results:
        logger.warning(f"No factor scores found for {date_str}")
        return []

    # Pivot to wide format
    df = pd.DataFrame(results)
    # Convert Decimal to float
    df['score'] = df['score'].astype(float)
    pivot_df = df.pivot(index='ticker', columns='factor_name', values='score')

    # Calculate equal-weighted composite score (simple mean)
    # Each factor contributes equally: 1/n weight
    composite_scores = pivot_df[factors].mean(axis=1)

    # Select top percentile
    threshold = np.percentile(composite_scores.dropna(), top_percentile)
    top_stocks = composite_scores[composite_scores >= threshold].sort_values(ascending=False)

    logger.info(f"  Selected {len(top_stocks)} stocks (>{top_percentile}th percentile)")
    logger.info(f"  Equal weighting: {1.0/len(factors):.2%} per factor")

    return list(zip(top_stocks.index, top_stocks.values))


def run_backtest(
    db: PostgresDatabaseManager,
    start_date: str,
    end_date: str,
    factors: list,
    ic_start_date: str,
    ic_end_date: str,
    initial_capital: float = 100_000_000,
    top_percentile: float = 80,
    rebalance_freq: str = 'M',
    weighting_method: str = 'ic',  # Phase 3: 'ic' or 'equal'
    rolling_window: int = 0,  # NEW: 0 = static IC (legacy), >0 = rolling IC (Tier 2)
    ic_min_p_value: float = 0.05,  # Phase 2B: Quality filter
    ic_min_observations: int = 30,  # Phase 2B: Quality filter
    ic_min_threshold: float = 0.08,  # Phase 2B: Quality filter
    use_signed_ic: bool = True  # Phase 2B: Signed IC weighting
):
    """
    Run multi-factor backtest with orthogonal factors

    Args:
        db: Database manager
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        factors: List of factor names to use
        ic_start_date: IC calculation start date (must precede start_date for static IC)
        ic_end_date: IC calculation end date (must precede start_date for static IC)
        initial_capital: Starting capital in KRW
        top_percentile: Percentile threshold for stock selection
        rebalance_freq: Rebalancing frequency ('M'=monthly, 'Q'=quarterly)
        weighting_method: Phase 3 - Factor weighting method ('ic'=IC-weighted, 'equal'=1/n per factor)
        rolling_window: Rolling IC window in days (0=static, 60=3mo, 126=6mo, 252=12mo)
        ic_min_p_value: Phase 2B quality filter - max p-value (default: 0.05)
        ic_min_observations: Phase 2B quality filter - min observations (default: 30)
        ic_min_threshold: Phase 2B quality filter - min |IC| (default: 0.08)
        use_signed_ic: Phase 2B signed IC weighting - exclude negative IC (default: True)
    """
    logger.info("=" * 80)
    if weighting_method == 'equal':
        logger.info("ORTHOGONAL FACTOR EQUAL-WEIGHTED STRATEGY BACKTEST")
        logger.info("⚖️  PHASE 3: EQUAL-WEIGHTED MODE (1/n per factor)")
    else:
        logger.info("ORTHOGONAL FACTOR IC-WEIGHTED STRATEGY BACKTEST")
        if rolling_window > 0:
            if use_signed_ic or ic_min_p_value < 1.0 or ic_min_observations > 0 or ic_min_threshold > 0:
                logger.info(f"🔄 TIER 2B: ROLLING IC WITH QUALITY FILTERS (window={rolling_window} days)")
                logger.info(f"   • Signed IC: {'ENABLED' if use_signed_ic else 'DISABLED'}")
                logger.info(f"   • Quality Filters: p<{ic_min_p_value}, n≥{ic_min_observations}, |IC|≥{ic_min_threshold}")
            else:
                logger.info(f"🔄 TIER 2: ROLLING IC MODE (window={rolling_window} days)")
        else:
            logger.info("⚙️  TIER 1: STATIC IC MODE (legacy)")
    logger.info("=" * 80)
    logger.info(f"\nBacktest Period: {start_date} to {end_date}")
    logger.info(f"Initial Capital: ₩{initial_capital:,.0f}")
    logger.info(f"Top Percentile: {top_percentile}%")
    logger.info(f"Rebalance Frequency: {rebalance_freq}")
    logger.info(f"\nFactors ({len(factors)}):")
    for factor in factors:
        logger.info(f"  • {factor}")

    # Initialize IC calculator (static or rolling) - SKIP if equal-weighted
    ic_calculator = None
    ic_weights = None

    if weighting_method == 'equal':
        # Phase 3: Equal-weighted - no IC calculation needed
        logger.info(f"\n⚖️  Equal weighting: {1.0/len(factors):.2%} per factor (no IC calculation)")
    elif rolling_window > 0:
        ic_calculator = RollingICCalculator(
            db,
            window_days=rolling_window,
            holding_period=21,
            region='KR',
            min_p_value=ic_min_p_value,
            min_observations=ic_min_observations,
            min_ic_threshold=ic_min_threshold,
            use_signed_ic=use_signed_ic
        )
        logger.info(f"\n🔄 Rolling IC Calculator initialized (window={rolling_window} days)")
        logger.info(f"   Quality Filters: {'ENABLED' if use_signed_ic or ic_min_p_value < 1.0 else 'DISABLED'}")
        ic_weights = None  # Will be calculated dynamically at each rebalance
    else:
        # Legacy: Calculate static IC weights once
        ic_weights = get_ic_weights(db, factors, ic_start_date, ic_end_date)
        if not ic_weights:
            logger.error("❌ No IC weights available. Cannot proceed.")
            return

    # Load ALL OHLCV data upfront (bulk-load for performance)
    logger.info(f"\n📊 Loading OHLCV data...")
    ohlcv_query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date >= %s
          AND date <= %s
        ORDER BY date, ticker
    """

    ohlcv_data = db.execute_query(ohlcv_query, (start_date, end_date))

    if not ohlcv_data:
        logger.error("❌ No OHLCV data available for period")
        return

    # Pivot to DataFrame with date index, ticker columns
    df_ohlcv = pd.DataFrame(ohlcv_data)
    df_ohlcv['date'] = pd.to_datetime(df_ohlcv['date'])
    df_ohlcv['close'] = pd.to_numeric(df_ohlcv['close'], errors='coerce')
    prices = df_ohlcv.pivot(index='date', columns='ticker', values='close')

    logger.info(f"📅 Loaded {len(prices)} trading days with {len(prices.columns)} unique tickers")

    # Generate rebalance dates and filter to actual trading days
    freq_map = {'M': 'ME', 'Q': 'QE', 'Y': 'YE'}
    freq = freq_map.get(rebalance_freq, rebalance_freq)
    rebalance_dates = pd.date_range(start=start_date, end=end_date, freq=freq)

    # CRITICAL: Filter to actual trading days with price data
    rebalance_dates = [d for d in rebalance_dates if d in prices.index]

    if not rebalance_dates:
        logger.error("❌ No valid rebalance dates found")
        return

    logger.info(f"🔄 Rebalance Dates: {len(rebalance_dates)} (filtered to trading days)")

    # Initialize backtest state
    portfolio_value = initial_capital
    cash = initial_capital
    holdings = {}  # {ticker: shares}
    total_transaction_costs = 0.0

    results = []

    # Run backtest
    for i, rebalance_date in enumerate(rebalance_dates):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Rebalance #{i+1}/{len(rebalance_dates)}: {rebalance_date.strftime('%Y-%m-%d')}")
        logger.info(f"{'=' * 80}")

        # Calculate IC weights dynamically if using rolling window (skip for equal-weighted)
        if ic_calculator is not None:
            ic_weights = ic_calculator.get_rolling_ic_weights(
                factors,
                rebalance_date.date(),
                verbose=(i == 0)  # Show details only on first rebalance
            )

        # Get top stocks using appropriate weighting method
        if weighting_method == 'equal':
            # Phase 3: Equal-weighted
            top_stocks = get_top_stocks_equal_weighted(
                db, factors, top_percentile, rebalance_date
            )
        else:
            # IC-weighted (static or rolling)
            top_stocks = get_top_stocks_ic_weighted(
                db, ic_weights, top_percentile, rebalance_date
            )

        if not top_stocks:
            logger.warning("⚠️ No stocks selected, skipping rebalance")
            continue

        # Get current prices from bulk-loaded DataFrame
        tickers = [t[0] for t in top_stocks]

        # Debug: Check if date exists in index
        if rebalance_date not in prices.index:
            logger.warning(f"⚠️ Rebalance date {rebalance_date} not in price index (type: {type(rebalance_date)})")
            logger.warning(f"   First 5 index dates: {list(prices.index[:5])}")
            continue

        current_prices = prices.loc[rebalance_date]

        # Convert to dict for compatibility with existing code
        price_dict = {
            ticker: current_prices[ticker]
            for ticker in tickers
            if ticker in current_prices and pd.notna(current_prices[ticker])
        }

        # Debug: Check what tickers are available
        if not price_dict:
            available_tickers = [t for t in tickers if t in current_prices]
            logger.warning(f"⚠️ No price data for selected tickers")
            logger.warning(f"   Selected tickers: {tickers[:5]}... (showing first 5)")
            logger.warning(f"   Available in prices: {available_tickers[:5]}... (showing first 5)")
            logger.warning(f"   Total in price DataFrame: {len(current_prices)} tickers")
            continue

        # Liquidate old holdings FIRST to get available cash
        liquidation_costs = 0.0

        for ticker, shares in holdings.items():
            if ticker in price_dict:
                sell_value = shares * price_dict[ticker]
                cost = calculate_transaction_cost(sell_value)
                cash += sell_value - cost  # Add proceeds to cash
                liquidation_costs += cost

        holdings = {}

        # Calculate target portfolio using AVAILABLE CASH (after liquidation)
        num_stocks = len(top_stocks)
        target_value_per_stock = cash / num_stocks

        # Buy new holdings
        purchase_costs = 0.0

        # Debug logging
        skipped_no_price = 0
        skipped_insufficient_cash = 0
        purchased = 0

        logger.info(f"  Target value per stock: ₩{target_value_per_stock:,.0f}")
        logger.info(f"  Available cash: ₩{cash:,.0f}")
        logger.info(f"  Attempting to buy {len(top_stocks)} stocks")

        for ticker, score in top_stocks:
            if ticker not in price_dict:
                skipped_no_price += 1
                logger.debug(f"    {ticker}: SKIP (no price data)")
                continue

            price = price_dict[ticker]
            shares = int(target_value_per_stock / price)

            if shares > 0:
                purchase_value = shares * price
                cost = calculate_transaction_cost(purchase_value)

                if cash >= purchase_value + cost:
                    holdings[ticker] = shares
                    cash -= (purchase_value + cost)
                    purchase_costs += cost
                    purchased += 1
                    logger.debug(f"    {ticker}: BUY {shares} shares @ ₩{price:,.0f} = ₩{purchase_value:,.0f}")
                else:
                    skipped_insufficient_cash += 1
                    logger.debug(f"    {ticker}: SKIP (need ₩{purchase_value + cost:,.0f}, have ₩{cash:,.0f})")

        logger.info(f"  Purchase Summary:")
        logger.info(f"    Purchased: {purchased}")
        logger.info(f"    Skipped (no price): {skipped_no_price}")
        logger.info(f"    Skipped (insufficient cash): {skipped_insufficient_cash}")

        total_costs = liquidation_costs + purchase_costs
        total_transaction_costs += total_costs

        # Calculate portfolio value
        holdings_value = sum(
            shares * price_dict.get(ticker, 0)
            for ticker, shares in holdings.items()
        )
        portfolio_value = cash + holdings_value

        logger.info(f"  Portfolio Value: ₩{portfolio_value:,.0f}")
        logger.info(f"  Transaction Costs: ₩{total_costs:,.0f}")
        logger.info(f"  Holdings: {len(holdings)} stocks")

        # Record results
        results.append({
            'date': rebalance_date,
            'portfolio_value': portfolio_value,
            'cash': cash,
            'holdings_value': holdings_value,
            'num_holdings': len(holdings),
            'transaction_costs': total_costs,
            'total_transaction_costs': total_transaction_costs
        })

    # Calculate performance metrics
    results_df = pd.DataFrame(results)

    total_return = (portfolio_value - initial_capital) / initial_capital
    num_years = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25
    annualized_return = (1 + total_return) ** (1 / num_years) - 1

    # Calculate returns for Sharpe ratio
    results_df['returns'] = results_df['portfolio_value'].pct_change()
    mean_return = results_df['returns'].mean()
    std_return = results_df['returns'].std()
    sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0

    # Max drawdown
    cummax = results_df['portfolio_value'].cummax()
    drawdowns = (results_df['portfolio_value'] - cummax) / cummax
    max_drawdown = drawdowns.min()

    # Win rate
    winning_periods = (results_df['returns'] > 0).sum()
    total_periods = len(results_df['returns'].dropna())
    win_rate = winning_periods / total_periods if total_periods > 0 else 0

    # Print results
    logger.info("\n" + "=" * 80)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"\n📈 RETURNS:")
    logger.info(f"  Initial Capital:     ₩{initial_capital:>15,.0f}")
    logger.info(f"  Final Value:         ₩{portfolio_value:>15,.0f}")
    logger.info(f"  Total Return:         {total_return:>14.2%}")
    logger.info(f"  Annualized Return:    {annualized_return:>14.2%}")

    logger.info(f"\n📊 RISK METRICS:")
    logger.info(f"  Sharpe Ratio:         {sharpe_ratio:>14.2f}")
    logger.info(f"  Max Drawdown:         {max_drawdown:>14.2%}")
    logger.info(f"  Volatility (annual):  {std_return * np.sqrt(252):>14.2%}")

    logger.info(f"\n💰 TRANSACTION COSTS:")
    logger.info(f"  Total Costs:         ₩{total_transaction_costs:>15,.0f}")
    logger.info(f"  % of Capital:         {total_transaction_costs/initial_capital:>14.2%}")

    logger.info(f"\n📉 TRADING STATS:")
    logger.info(f"  Win Rate:             {win_rate:>14.2%}")
    logger.info(f"  Num Rebalances:       {len(results):>14,}")
    logger.info(f"  Avg Holdings:         {results_df['num_holdings'].mean():>14.1f}")

    # Save results
    output_dir = project_root / 'backtest_results'
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'orthogonal_backtest_{start_date}_{end_date}_{timestamp}.csv'

    results_df.to_csv(output_file, index=False)
    logger.info(f"\n💾 Results saved: {output_file}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Orthogonal Factor IC-Weighted Backtest')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000, help='Initial capital (KRW)')
    parser.add_argument('--factors', type=str, help='Comma-separated factor names (default: 12M_Momentum,1M_Momentum,Earnings_Quality)')
    parser.add_argument('--top-percentile', type=float, default=80, help='Top percentile threshold (default: 80)')
    parser.add_argument('--rebalance-freq', type=str, default='M', choices=['M', 'Q'], help='Rebalancing frequency (M=monthly, Q=quarterly)')
    parser.add_argument('--weighting-method', type=str, default='ic', choices=['ic', 'equal'],
                        help='Phase 3: Factor weighting method (ic=IC-weighted, equal=1/n per factor)')
    parser.add_argument('--validate-orthogonal', action='store_true', help='Validate factors are orthogonal before backtest')
    parser.add_argument('--max-correlation', type=float, default=0.5, help='Maximum allowed correlation (default: 0.5)')
    parser.add_argument('--ic-start', required=True, help='IC calculation start date (YYYY-MM-DD) - must precede backtest')
    parser.add_argument('--ic-end', required=True, help='IC calculation end date (YYYY-MM-DD) - must precede backtest')
    parser.add_argument('--rolling-window', type=int, default=0,
                        help='Rolling IC window in days (0=static IC, 60=3mo, 126=6mo, 252=12mo)')

    # Phase 2B: Quality filter parameters
    parser.add_argument('--ic-min-p-value', type=float, default=0.05,
                        help='Phase 2B: Max p-value for IC quality filter (default: 0.05)')
    parser.add_argument('--ic-min-observations', type=int, default=30,
                        help='Phase 2B: Min observations for IC quality filter (default: 30)')
    parser.add_argument('--ic-min-threshold', type=float, default=0.08,
                        help='Phase 2B: Min |IC| for quality filter (default: 0.08)')
    parser.add_argument('--use-signed-ic', action='store_true', default=True,
                        help='Phase 2B: Use signed IC weighting (exclude negative IC) (default: True)')
    parser.add_argument('--no-signed-ic', dest='use_signed_ic', action='store_false',
                        help='Phase 2B: Disable signed IC weighting (use absolute IC)')

    args = parser.parse_args()

    # Parse factors
    if args.factors:
        factors = [f.strip() for f in args.factors.split(',')]
    else:
        factors = DEFAULT_ORTHOGONAL_FACTORS

    # Initialize database
    db = PostgresDatabaseManager()

    # Validate orthogonal factors
    if args.validate_orthogonal:
        logger.info("\n🔍 Validating factor orthogonality...")
        optimizer = FactorOptimizer(db, region='KR', max_correlation=args.max_correlation)

        # Get latest factor scores
        result = optimizer.analyze_factors()

        # Check if selected factors are in orthogonal set
        for factor in factors:
            if factor not in result.orthogonal_factors:
                logger.warning(f"⚠️ {factor} is NOT in orthogonal set!")
                logger.warning(f"   Recommended orthogonal factors: {result.orthogonal_factors}")

                response = input("\nContinue anyway? [y/N]: ")
                if response.lower() != 'y':
                    logger.info("Backtest cancelled.")
                    return
                break

    # Validate IC period precedes backtest period (NO LOOK-AHEAD BIAS!)
    from datetime import datetime
    ic_end = datetime.strptime(args.ic_end, '%Y-%m-%d')
    backtest_start = datetime.strptime(args.start, '%Y-%m-%d')

    if ic_end >= backtest_start:
        logger.error("❌ LOOK-AHEAD BIAS DETECTED!")
        logger.error(f"   IC end date ({args.ic_end}) must precede backtest start date ({args.start})")
        logger.error(f"   Current overlap: {(backtest_start - ic_end).days} days")
        logger.error("\n💡 Suggestion: Use IC from prior period")
        logger.error(f"   Example: --ic-start 2021-01-01 --ic-end 2022-12-31 --start 2023-01-01")
        return

    logger.info(f"\n✅ No look-ahead bias: IC period ({args.ic_start} to {args.ic_end}) precedes backtest ({args.start} to {args.end})")
    logger.info(f"   Gap: {(backtest_start - ic_end).days} days\n")

    # Run backtest
    run_backtest(
        db=db,
        start_date=args.start,
        end_date=args.end,
        factors=factors,
        ic_start_date=args.ic_start,
        ic_end_date=args.ic_end,
        initial_capital=args.capital,
        top_percentile=args.top_percentile,
        rebalance_freq=args.rebalance_freq,
        weighting_method=args.weighting_method,
        rolling_window=args.rolling_window,
        ic_min_p_value=args.ic_min_p_value,
        ic_min_observations=args.ic_min_observations,
        ic_min_threshold=args.ic_min_threshold,
        use_signed_ic=args.use_signed_ic
    )


if __name__ == '__main__':
    main()
