#!/usr/bin/env python3
"""
Factor Weighting Comparison Script - Quarterly Rebalancing

Tests 4 factor combination methods at quarterly frequency:
1. IC-Weighted: Dynamic weights based on rolling IC (current baseline)
2. Equal-Weighted: 1/3 each factor (simple, robust)
3. Inverse-Volatility: Weight by inverse IC volatility
4. Rank-Based: Combine factor ranks, not scores

Usage:
    python3 scripts/compare_factor_weighting_quarterly.py \
        --start 2021-01-01 \
        --end 2024-12-31 \
        --factors "Operating_Profit_Margin,RSI_Momentum,ROE_Proxy" \
        --train-years 1 \
        --test-years 1
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


class FactorWeightingComparison:
    """Compare different factor weighting methods for quarterly rebalancing."""

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        factors: List[str],
        train_years: int = 1,
        test_years: int = 1,
        region: str = 'KR',
        initial_capital: float = 100_000_000.0,
        top_percentile: int = 45,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001
    ):
        self.db = db_manager
        self.factors = factors
        self.train_years = train_years
        self.test_years = test_years
        self.region = region
        self.initial_capital = initial_capital
        self.top_percentile = top_percentile
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

        # IC calculation parameters
        self.ic_window_days = 252  # 1-year rolling window for IC
        self.holding_period_days = 63  # ~3 months (quarterly)

    def generate_walk_forward_periods(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, str]]:
        """Generate train/test period splits for walk-forward validation."""
        periods = []
        current_train_start = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)

        period_num = 1
        while True:
            train_end = current_train_start + pd.DateOffset(years=self.train_years)
            test_start = train_end + pd.Timedelta(days=1)
            test_end = test_start + pd.DateOffset(years=self.test_years)

            if test_end > end_ts:
                break

            periods.append({
                'period': period_num,
                'train_start': current_train_start.strftime('%Y-%m-%d'),
                'train_end': train_end.strftime('%Y-%m-%d'),
                'test_start': test_start.strftime('%Y-%m-%d'),
                'test_end': test_end.strftime('%Y-%m-%d')
            })

            current_train_start = test_start
            period_num += 1

        return periods

    def calculate_ic_timeseries(
        self,
        factor_name: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Calculate Information Coefficient time-series for a factor."""
        query = f"""
        WITH factor_returns AS (
            SELECT
                fs.ticker,
                fs.date as factor_date,
                fs.score as factor_score,
                LEAD(o.close, {self.holding_period_days}) OVER (
                    PARTITION BY fs.ticker ORDER BY fs.date
                ) as future_price,
                o.close as current_price
            FROM factor_scores fs
            JOIN ohlcv_data o ON
                fs.ticker = o.ticker AND
                fs.region = o.region AND
                fs.date = o.date
            WHERE fs.factor_name = %s
                AND fs.region = %s
                AND fs.date >= %s
                AND fs.date <= %s
                AND o.timeframe = '1d'
        ),
        returns_with_scores AS (
            SELECT
                factor_date,
                ticker,
                factor_score,
                (future_price / current_price - 1) * 100 as forward_return
            FROM factor_returns
            WHERE future_price IS NOT NULL
        )
        SELECT
            factor_date,
            COUNT(*) as num_stocks,
            CORR(factor_score, forward_return) as ic,
            STDDEV(factor_score) as factor_std,
            STDDEV(forward_return) as return_std
        FROM returns_with_scores
        GROUP BY factor_date
        HAVING COUNT(*) >= 10
        ORDER BY factor_date
        """

        with self.db._get_connection() as conn:
            df = pd.read_sql(query, conn, params=(factor_name, self.region, start_date, end_date))

        df['factor_name'] = factor_name
        return df

    def get_factor_scores_for_date(
        self,
        date: str,
        factors: List[str]
    ) -> pd.DataFrame:
        """Get factor scores for all tickers on a given date."""
        query = """
        SELECT ticker, factor_name, score, percentile
        FROM factor_scores
        WHERE region = %s
            AND date = %s
            AND factor_name = ANY(%s)
        """

        with self.db._get_connection() as conn:
            df = pd.read_sql(query, conn, params=(self.region, date, factors))

        return df

    def combine_factors_ic_weighted(
        self,
        scores_df: pd.DataFrame,
        ic_weights: Dict[str, float]
    ) -> pd.DataFrame:
        """Method 1: IC-Weighted (current baseline)."""
        # Pivot to get one row per ticker
        pivot_df = scores_df.pivot(index='ticker', columns='factor_name', values='score')

        # Calculate weighted composite score
        composite_scores = []
        for ticker in pivot_df.index:
            weighted_sum = 0
            total_weight = 0
            for factor in self.factors:
                if factor in pivot_df.columns and factor in ic_weights:
                    score = pivot_df.loc[ticker, factor]
                    weight = ic_weights[factor]
                    if pd.notna(score) and weight > 0:
                        weighted_sum += score * weight
                        total_weight += weight

            composite_score = weighted_sum / total_weight if total_weight > 0 else 0
            composite_scores.append({'ticker': ticker, 'composite_score': composite_score})

        result_df = pd.DataFrame(composite_scores)
        return result_df.sort_values('composite_score', ascending=False)

    def combine_factors_equal_weighted(
        self,
        scores_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Method 2: Equal-Weighted (1/n each factor)."""
        pivot_df = scores_df.pivot(index='ticker', columns='factor_name', values='score')

        # Simple average of available factor scores
        composite_scores = []
        for ticker in pivot_df.index:
            scores = []
            for factor in self.factors:
                if factor in pivot_df.columns:
                    score = pivot_df.loc[ticker, factor]
                    if pd.notna(score):
                        scores.append(score)

            composite_score = np.mean(scores) if scores else 0
            composite_scores.append({'ticker': ticker, 'composite_score': composite_score})

        result_df = pd.DataFrame(composite_scores)
        return result_df.sort_values('composite_score', ascending=False)

    def combine_factors_inverse_volatility(
        self,
        scores_df: pd.DataFrame,
        ic_volatilities: Dict[str, float]
    ) -> pd.DataFrame:
        """Method 3: Inverse-Volatility Weighted (favor stable factors)."""
        pivot_df = scores_df.pivot(index='ticker', columns='factor_name', values='score')

        # Calculate inverse volatility weights
        inv_vol_weights = {}
        total_inv_vol = 0
        for factor, vol in ic_volatilities.items():
            if vol > 0:
                inv_vol = 1.0 / vol
                inv_vol_weights[factor] = inv_vol
                total_inv_vol += inv_vol

        # Normalize to sum to 1
        for factor in inv_vol_weights:
            inv_vol_weights[factor] /= total_inv_vol

        # Calculate weighted composite score
        composite_scores = []
        for ticker in pivot_df.index:
            weighted_sum = 0
            total_weight = 0
            for factor in self.factors:
                if factor in pivot_df.columns and factor in inv_vol_weights:
                    score = pivot_df.loc[ticker, factor]
                    weight = inv_vol_weights[factor]
                    if pd.notna(score):
                        weighted_sum += score * weight
                        total_weight += weight

            composite_score = weighted_sum / total_weight if total_weight > 0 else 0
            composite_scores.append({'ticker': ticker, 'composite_score': composite_score})

        result_df = pd.DataFrame(composite_scores)
        return result_df.sort_values('composite_score', ascending=False)

    def combine_factors_rank_based(
        self,
        scores_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Method 4: Rank-Based (combine ranks, not raw scores - outlier robust)."""
        pivot_df = scores_df.pivot(index='ticker', columns='factor_name', values='score')

        # Rank each factor (higher rank = better)
        rank_df = pivot_df.rank(method='average', ascending=True)

        # Average ranks across factors
        composite_scores = []
        for ticker in rank_df.index:
            ranks = []
            for factor in self.factors:
                if factor in rank_df.columns:
                    rank = rank_df.loc[ticker, factor]
                    if pd.notna(rank):
                        ranks.append(rank)

            avg_rank = np.mean(ranks) if ranks else 0
            composite_scores.append({'ticker': ticker, 'composite_score': avg_rank})

        result_df = pd.DataFrame(composite_scores)
        return result_df.sort_values('composite_score', ascending=False)

    def select_top_stocks(
        self,
        composite_df: pd.DataFrame,
        top_percentile: int
    ) -> List[str]:
        """Select top N% stocks by composite score."""
        n_stocks = max(1, int(len(composite_df) * (top_percentile / 100.0)))
        top_stocks = composite_df.head(n_stocks)['ticker'].tolist()
        return top_stocks

    def backtest_portfolio(
        self,
        selected_tickers: List[str],
        test_start: str,
        test_end: str,
        capital: float
    ) -> Dict:
        """Backtest a portfolio over the test period with quarterly rebalancing."""
        # Get quarterly rebalance dates
        query = """
        SELECT DISTINCT date
        FROM ohlcv_data
        WHERE region = %s
            AND timeframe = '1d'
            AND date >= %s
            AND date <= %s
        ORDER BY date
        """

        with self.db._get_connection() as conn:
            all_dates_df = pd.read_sql(query, conn, params=(self.region, test_start, test_end))

        all_dates = pd.to_datetime(all_dates_df['date']).tolist()

        # Generate quarterly rebalance dates (every ~63 trading days)
        rebalance_dates = []
        for i in range(0, len(all_dates), 63):
            if i < len(all_dates):
                rebalance_dates.append(all_dates[i])

        if not rebalance_dates:
            return {'return': 0, 'sharpe': 0, 'max_drawdown': 0, 'num_rebalances': 0}

        # Backtest simulation
        portfolio_value = capital
        holdings = {}  # {ticker: shares}
        cash = capital

        max_portfolio_value = capital
        max_drawdown = 0
        returns = []

        for rebal_idx, rebal_date in enumerate(rebalance_dates):
            # Liquidate existing holdings
            if holdings:
                liquidation_value = self._liquidate_holdings(holdings, rebal_date)
                cash = liquidation_value

            # Rebalance: equal-weight allocation
            if selected_tickers:
                allocation_per_stock = cash / len(selected_tickers)
                holdings = self._buy_stocks(selected_tickers, allocation_per_stock, rebal_date)

            # Calculate portfolio value at next rebalance (or end)
            next_rebal_date = rebalance_dates[rebal_idx + 1] if rebal_idx + 1 < len(rebalance_dates) else all_dates[-1]
            portfolio_value = self._calculate_portfolio_value(holdings, next_rebal_date)

            # Track metrics
            if rebal_idx > 0:
                period_return = (portfolio_value / prev_portfolio_value - 1) * 100
                returns.append(period_return)

            prev_portfolio_value = portfolio_value

            # Drawdown tracking
            if portfolio_value > max_portfolio_value:
                max_portfolio_value = portfolio_value

            current_drawdown = (portfolio_value / max_portfolio_value - 1) * 100
            if current_drawdown < max_drawdown:
                max_drawdown = current_drawdown

        # Calculate final metrics
        total_return = (portfolio_value / capital - 1) * 100

        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return / std_return) * np.sqrt(4) if std_return > 0 else 0  # Annualized (4 quarters)
        else:
            sharpe = 0

        win_rate = (sum(1 for r in returns if r > 0) / len(returns) * 100) if returns else 0

        # Transaction cost estimation
        num_trades = len(rebalance_dates) * len(selected_tickers) * 2  # Buy + Sell
        transaction_costs = capital * self.commission_rate * num_trades / len(rebalance_dates)

        return {
            'return': total_return,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'num_rebalances': len(rebalance_dates),
            'win_rate': win_rate,
            'transaction_costs': transaction_costs,
            'avg_holdings': len(selected_tickers)
        }

    def _liquidate_holdings(self, holdings: Dict[str, int], date: str) -> float:
        """Liquidate all holdings at market price with slippage."""
        if not holdings:
            return 0

        tickers = list(holdings.keys())
        query = """
        SELECT ticker, close
        FROM ohlcv_data
        WHERE region = %s
            AND timeframe = '1d'
            AND date = %s
            AND ticker = ANY(%s)
        """

        with self.db._get_connection() as conn:
            prices_df = pd.read_sql(query, conn, params=(self.region, date, tickers))

        total_value = 0
        for _, row in prices_df.iterrows():
            ticker = row['ticker']
            price = row['close']
            shares = holdings.get(ticker, 0)

            # Apply slippage (sell at lower price)
            sell_price = price * (1 - self.slippage_rate)
            total_value += shares * sell_price

        return total_value

    def _buy_stocks(self, tickers: List[str], allocation: float, date: str) -> Dict[str, int]:
        """Buy stocks with equal allocation, apply commission and slippage."""
        query = """
        SELECT ticker, close
        FROM ohlcv_data
        WHERE region = %s
            AND timeframe = '1d'
            AND date = %s
            AND ticker = ANY(%s)
        """

        with self.db._get_connection() as conn:
            prices_df = pd.read_sql(query, conn, params=(self.region, date, tickers))

        holdings = {}
        for _, row in prices_df.iterrows():
            ticker = row['ticker']
            price = row['close']

            # Apply commission and slippage
            buy_price = price * (1 + self.slippage_rate)
            available_cash = allocation * (1 - self.commission_rate)
            shares = int(available_cash / buy_price)

            if shares > 0:
                holdings[ticker] = shares

        return holdings

    def _calculate_portfolio_value(self, holdings: Dict[str, int], date: str) -> float:
        """Calculate total portfolio value at a given date."""
        if not holdings:
            return 0

        tickers = list(holdings.keys())
        query = """
        SELECT ticker, close
        FROM ohlcv_data
        WHERE region = %s
            AND timeframe = '1d'
            AND date = %s
            AND ticker = ANY(%s)
        """

        with self.db._get_connection() as conn:
            prices_df = pd.read_sql(query, conn, params=(self.region, date, tickers))

        total_value = 0
        for _, row in prices_df.iterrows():
            ticker = row['ticker']
            price = row['close']
            shares = holdings.get(ticker, 0)
            total_value += shares * price

        return total_value

    def run_comparison(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Run walk-forward validation for all 4 weighting methods."""
        periods = self.generate_walk_forward_periods(start_date, end_date)
        logger.info(f"Generated {len(periods)} walk-forward periods")

        all_results = []

        for period in periods:
            logger.info(f"Period {period['period']}: Train {period['train_start']} to {period['train_end']}, Test {period['test_start']} to {period['test_end']}")

            # Calculate IC time-series for training period
            ic_data = {}
            for factor in self.factors:
                ic_df = self.calculate_ic_timeseries(
                    factor,
                    period['train_start'],
                    period['train_end']
                )
                ic_data[factor] = ic_df

            # Calculate IC weights and volatilities
            ic_weights = {}
            ic_volatilities = {}
            for factor, ic_df in ic_data.items():
                if len(ic_df) > 0:
                    mean_ic = ic_df['ic'].mean()
                    std_ic = ic_df['ic'].std()

                    # IC weight: use absolute IC (favor strong signals regardless of sign)
                    ic_weights[factor] = abs(mean_ic) if pd.notna(mean_ic) else 0
                    ic_volatilities[factor] = std_ic if pd.notna(std_ic) else 1.0
                else:
                    ic_weights[factor] = 0
                    ic_volatilities[factor] = 1.0

            # Normalize IC weights
            total_ic = sum(ic_weights.values())
            if total_ic > 0:
                ic_weights = {k: v / total_ic for k, v in ic_weights.items()}
            else:
                # Equal weights if no IC signal
                ic_weights = {factor: 1.0 / len(self.factors) for factor in self.factors}

            # Get factor scores at test period start
            test_start_scores = self.get_factor_scores_for_date(
                period['test_start'],
                self.factors
            )

            if test_start_scores.empty:
                logger.warning(f"No factor scores for {period['test_start']}, skipping period")
                continue

            # Test all 4 methods
            methods = {
                'IC-Weighted': lambda df: self.combine_factors_ic_weighted(df, ic_weights),
                'Equal-Weighted': lambda df: self.combine_factors_equal_weighted(df),
                'Inverse-Volatility': lambda df: self.combine_factors_inverse_volatility(df, ic_volatilities),
                'Rank-Based': lambda df: self.combine_factors_rank_based(df)
            }

            for method_name, combine_func in methods.items():
                logger.info(f"  Testing {method_name}...")

                # Combine factors
                composite_df = combine_func(test_start_scores)

                # Select top stocks
                selected_tickers = self.select_top_stocks(composite_df, self.top_percentile)

                # Backtest
                backtest_results = self.backtest_portfolio(
                    selected_tickers,
                    period['test_start'],
                    period['test_end'],
                    self.initial_capital
                )

                # Record results
                all_results.append({
                    'period': period['period'],
                    'method': method_name,
                    'train_start': period['train_start'],
                    'train_end': period['train_end'],
                    'test_start': period['test_start'],
                    'test_end': period['test_end'],
                    **backtest_results
                })

        results_df = pd.DataFrame(all_results)
        return results_df


def main():
    parser = argparse.ArgumentParser(description='Compare factor weighting methods for quarterly rebalancing')
    parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--factors', type=str, required=True, help='Comma-separated factor names')
    parser.add_argument('--train-years', type=int, default=1, help='Training period years')
    parser.add_argument('--test-years', type=int, default=1, help='Test period years')
    parser.add_argument('--capital', type=float, default=100_000_000.0, help='Initial capital')
    parser.add_argument('--top-percentile', type=int, default=45, help='Top percentile for stock selection')
    parser.add_argument('--region', type=str, default='KR', help='Market region')

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

    # Parse factors
    factors = [f.strip() for f in args.factors.split(',')]

    # Initialize database
    db_manager = PostgresDatabaseManager()

    # Run comparison
    logger.info(f"Factor Weighting Comparison - Quarterly Rebalancing")
    logger.info(f"Factors: {factors}")
    logger.info(f"Period: {args.start} to {args.end}")
    logger.info(f"Train/Test: {args.train_years}y / {args.test_years}y")

    comparator = FactorWeightingComparison(
        db_manager=db_manager,
        factors=factors,
        train_years=args.train_years,
        test_years=args.test_years,
        region=args.region,
        initial_capital=args.capital,
        top_percentile=args.top_percentile
    )

    results_df = comparator.run_comparison(args.start, args.end)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = project_root / 'analysis'
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / f'factor_weighting_comparison_{timestamp}.csv'
    results_df.to_csv(csv_path, index=False)
    logger.info(f"Results saved to {csv_path}")

    # Generate summary report
    logger.info("\n" + "="*80)
    logger.info("SUMMARY BY METHOD")
    logger.info("="*80)

    for method in results_df['method'].unique():
        method_df = results_df[results_df['method'] == method]

        avg_return = method_df['return'].mean()
        avg_sharpe = method_df['sharpe'].mean()
        avg_max_dd = method_df['max_drawdown'].mean()
        avg_win_rate = method_df['win_rate'].mean()

        logger.info(f"\n{method}:")
        logger.info(f"  Average Return: {avg_return:+.2f}%")
        logger.info(f"  Average Sharpe: {avg_sharpe:.2f}")
        logger.info(f"  Average Max DD: {avg_max_dd:.2f}%")
        logger.info(f"  Average Win Rate: {avg_win_rate:.1f}%")
        logger.info(f"  Period Results: {method_df[['period', 'return', 'sharpe']].to_dict('records')}")

    # Generate markdown report
    report_path = output_dir / f'factor_weighting_comparison_report_{timestamp}.md'
    generate_markdown_report(results_df, report_path, args)
    logger.info(f"Report saved to {report_path}")


def generate_markdown_report(results_df: pd.DataFrame, output_path: Path, args):
    """Generate comprehensive markdown report."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    report = f"""# Factor Weighting Comparison Report - Quarterly Rebalancing

**Date**: {timestamp}
**Analysis Period**: {args.start} to {args.end}
**Factors**: {args.factors}
**Train/Test Split**: {args.train_years} year / {args.test_years} year
**Top Percentile**: {args.top_percentile}%
**Initial Capital**: ₩{args.capital:,.0f}

---

## Executive Summary

This report compares 4 factor weighting methods for quarterly rebalancing:

1. **IC-Weighted**: Dynamic weights based on rolling IC (current baseline)
2. **Equal-Weighted**: 1/{len(args.factors.split(','))} each factor (simple, robust)
3. **Inverse-Volatility**: Weight by inverse IC volatility (favor stable factors)
4. **Rank-Based**: Combine factor ranks, not scores (outlier-robust)

**Hypothesis**: Equal-weighted may outperform IC-weighted by avoiding IC estimation error during regime changes.

---

## Results by Method

"""

    for method in ['IC-Weighted', 'Equal-Weighted', 'Inverse-Volatility', 'Rank-Based']:
        method_df = results_df[results_df['method'] == method]

        if method_df.empty:
            continue

        avg_return = method_df['return'].mean()
        avg_sharpe = method_df['sharpe'].mean()
        avg_max_dd = method_df['max_drawdown'].mean()
        avg_win_rate = method_df['win_rate'].mean()

        status = "✅" if avg_return > 0 else "❌"

        report += f"""### {method} {status}

**Average Metrics**:
- Return: **{avg_return:+.2f}%**
- Sharpe Ratio: **{avg_sharpe:.2f}**
- Max Drawdown: **{avg_max_dd:.2f}%**
- Win Rate: **{avg_win_rate:.1f}%**

**Period-by-Period Results**:

| Period | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------------|-------------|--------|--------|--------|----------|----------|
"""

        for _, row in method_df.iterrows():
            report += f"| {row['period']} | {row['train_start']} to {row['train_end']} | {row['test_start']} to {row['test_end']} | {row['return']:+.2f}% | {row['sharpe']:.2f} | {row['max_drawdown']:.2f}% | {row['win_rate']:.1f}% | {row['avg_holdings']:.0f} |\n"

        report += "\n"

    # Comparison table
    report += """---

## Method Comparison Summary

| Method | Avg Return | Avg Sharpe | Avg Max DD | Avg Win Rate | Best Period | Worst Period |
|--------|------------|------------|------------|--------------|-------------|--------------|
"""

    for method in results_df['method'].unique():
        method_df = results_df[results_df['method'] == method]

        avg_return = method_df['return'].mean()
        avg_sharpe = method_df['sharpe'].mean()
        avg_max_dd = method_df['max_drawdown'].mean()
        avg_win_rate = method_df['win_rate'].mean()
        best_period_return = method_df['return'].max()
        worst_period_return = method_df['return'].min()

        report += f"| {method} | {avg_return:+.2f}% | {avg_sharpe:.2f} | {avg_max_dd:.2f}% | {avg_win_rate:.1f}% | {best_period_return:+.2f}% | {worst_period_return:+.2f}% |\n"

    # Key findings
    report += """
---

## Key Findings

"""

    # Find best method
    method_avg_returns = results_df.groupby('method')['return'].mean()
    best_method = method_avg_returns.idxmax()
    best_return = method_avg_returns.max()
    worst_method = method_avg_returns.idxmin()
    worst_return = method_avg_returns.min()

    report += f"""### Best Performing Method
**{best_method}** achieved the highest average return of **{best_return:+.2f}%**.

### Worst Performing Method
**{worst_method}** had the lowest average return of **{worst_return:+.2f}%**.

### Period 1 (2022 Test Year) Performance
"""

    period1_df = results_df[results_df['period'] == 1]
    if not period1_df.empty:
        report += "\n| Method | Return | Sharpe | Max DD | Status |\n"
        report += "|--------|--------|--------|--------|--------|\n"

        for _, row in period1_df.iterrows():
            status = "✅" if row['return'] > -20 else "❌"
            report += f"| {row['method']} | {row['return']:+.2f}% | {row['sharpe']:.2f} | {row['max_drawdown']:.2f}% | {status} |\n"

        # Check if any method avoided catastrophic loss
        period1_max_return = period1_df['return'].max()
        if period1_max_return > -20:
            best_period1_method = period1_df.loc[period1_df['return'].idxmax(), 'method']
            report += f"\n**Critical Finding**: {best_period1_method} avoided catastrophic loss in Period 1 (2022 bear market), suggesting it is more robust to regime changes.\n"
        else:
            report += f"\n**Critical Finding**: All methods failed in Period 1 (2022 bear market), suggesting the problem is systemic and not solved by changing weighting method alone.\n"

    report += """
---

## Recommendations

"""

    if best_return > 0:
        report += f"1. **Deploy {best_method}** as the primary factor weighting method for quarterly rebalancing.\n"
        report += f"2. Continue monitoring performance in live trading.\n"
    else:
        report += f"1. **All methods failed to achieve positive returns** - consider abandoning IC-weighted approach entirely.\n"
        report += f"2. Explore alternative strategies: Single-factor strategies, buy-and-hold, or machine learning approaches.\n"

    report += f"""
---

## Next Steps

"""

    if best_return > 0:
        report += """1. Proceed to Phase 2.4: Threshold Optimization
2. Test optimal top percentile (20%, 30%, 40%, 45%, 50%) for best method
3. Proceed to Phase 2.5: IC Window Optimization
4. Test extended IC windows (2-year, 3-year) for regime smoothing
"""
    else:
        report += """1. HALT further optimization of IC-weighted approach
2. Pivot to Alternative Strategies:
   - Equal-weighted multi-factor (no IC weighting)
   - Single-factor strategies (RSI_Momentum only, Operating_Profit_Margin only)
   - Buy-and-hold with fundamental screens
   - Machine learning factor combination
"""

    report += f"""
---

**Report Generated**: {timestamp}
**Spock Quant Platform** - Phase 2.3 Factor Weighting Comparison
"""

    output_path.write_text(report)


if __name__ == '__main__':
    main()
