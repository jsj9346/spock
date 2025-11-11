#!/usr/bin/env python3
"""
Week 3 Momentum Strategy Example - Real Database Data

Demonstrates backtesting workflow using Week 3 collected data:
1. Load OHLCV data from PostgreSQL database
2. Calculate 12-month momentum signals
3. Run backtest with both custom and vectorbt engines
4. Compare performance and validate results

This example uses REAL data collected during Week 3:
- Universe: 350 tickers (KOSPI 200 + KOSDAQ 150)
- Date Range: 2019-01-01 to 2024-12-31 (5 years)
- Data Source: pykrx via PostgreSQL + TimescaleDB

Strategy Details:
- Momentum Calculation: 12-month return (skip last month)
- Rebalancing: Monthly
- Position Sizing: Equal weight across top N stocks
- Transaction Costs: KIS broker fees (0.015% + 0.23% tax)

Usage:
    # Run with custom engine (production-grade)
    python3 examples/backtest/week3_momentum_strategy_example.py --engine custom

    # Run with vectorbt (research-grade, 100x faster)
    python3 examples/backtest/week3_momentum_strategy_example.py --engine vectorbt

    # Compare both engines
    python3 examples/backtest/week3_momentum_strategy_example.py --compare

    # Custom parameters
    python3 examples/backtest/week3_momentum_strategy_example.py \
      --start 2020-01-01 --end 2023-12-31 \
      --top-n 10 --rebalance-freq M

Author: Spock Quant Platform - Week 3 Integration
Date: 2025-10-27
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Optional
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.common.costs import TransactionCostModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Week3MomentumBacktest:
    """
    Momentum strategy backtester using Week 3 database data
    """

    def __init__(self, db: PostgresDatabaseManager):
        """
        Initialize backtester

        Args:
            db: PostgreSQL database manager
        """
        self.db = db

    def load_universe_tickers(self, universe_file: str = 'data/kr_universe_week3.csv') -> List[str]:
        """
        Load ticker universe from Week 3 CSV file

        Args:
            universe_file: Path to universe CSV file

        Returns:
            List of ticker codes (zero-padded to 6 digits)
        """
        if not os.path.exists(universe_file):
            logger.error(f"Universe file not found: {universe_file}")
            raise FileNotFoundError(f"Universe file not found: {universe_file}")

        df = pd.read_csv(universe_file)

        if 'ticker' not in df.columns:
            raise ValueError("Universe file must have 'ticker' column")

        # Ensure zero-padding for KR tickers
        tickers = [str(ticker).zfill(6) for ticker in df['ticker'].tolist()]

        logger.info(f"Loaded {len(tickers)} tickers from universe file")
        return tickers

    def load_ohlcv_data(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data from database for specified tickers

        Args:
            tickers: List of ticker codes
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary of {ticker: OHLCV DataFrame}
        """
        logger.info(f"Loading OHLCV data for {len(tickers)} tickers...")
        logger.info(f"Date range: {start_date} to {end_date}")

        data = {}
        successful = 0
        failed = 0

        for ticker in tickers:
            try:
                query = """
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s
                  AND region = 'KR'
                  AND date BETWEEN %s AND %s
                  AND timeframe = '1d'
                ORDER BY date
                """

                results = self.db.execute_query(query, (ticker, start_date, end_date))

                if not results or len(results) == 0:
                    logger.warning(f"  {ticker}: No data found")
                    failed += 1
                    continue

                # Convert to DataFrame
                df = pd.DataFrame(results)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)

                # Validate data quality
                if len(df) < 252:  # Need at least 1 year for momentum calculation
                    logger.warning(f"  {ticker}: Insufficient data ({len(df)} days)")
                    failed += 1
                    continue

                data[ticker] = df
                successful += 1

            except Exception as e:
                logger.error(f"  {ticker}: Failed to load data - {e}")
                failed += 1

        logger.info(f"✅ Loaded data for {successful} tickers ({failed} failed)")
        return data

    def calculate_momentum_signals(
        self,
        data: Dict[str, pd.DataFrame],
        lookback_periods: int = 252,  # 12 months
        skip_recent: int = 21,  # Skip last month (reversal effect)
        top_n: int = 10,
        rebalance_freq: str = 'M'  # Monthly rebalancing
    ) -> Dict[str, pd.Series]:
        """
        Calculate momentum-based trading signals

        Strategy:
        - Calculate 12-month return (skip last month)
        - Rank stocks by momentum
        - Hold top N stocks
        - Rebalance monthly

        Args:
            data: Dictionary of OHLCV DataFrames
            lookback_periods: Momentum calculation period (default: 252 days = 12 months)
            skip_recent: Period to skip for reversal (default: 21 days = 1 month)
            top_n: Number of top momentum stocks to hold
            rebalance_freq: Rebalancing frequency ('M' = monthly, 'W' = weekly)

        Returns:
            Dictionary of {ticker: boolean signal Series}
        """
        logger.info(f"Calculating momentum signals...")
        logger.info(f"  Lookback: {lookback_periods} days, Skip: {skip_recent} days")
        logger.info(f"  Top N: {top_n}, Rebalance: {rebalance_freq}")

        # Get close prices for all tickers
        close_prices = pd.DataFrame({
            ticker: df['close'] for ticker, df in data.items()
        })

        # Calculate momentum (skip recent period to avoid reversal)
        shifted_prices = close_prices.shift(skip_recent)
        momentum = shifted_prices.pct_change(periods=lookback_periods)

        # Rank stocks by momentum
        momentum_ranks = momentum.rank(axis=1, ascending=False, method='first')

        # Generate signals (True for top N)
        signals_raw = momentum_ranks <= top_n

        # Apply rebalancing frequency
        if rebalance_freq == 'M':
            # Rebalance on first trading day of each month
            signals = signals_raw.resample('MS').first().reindex(signals_raw.index, method='ffill')
        elif rebalance_freq == 'W':
            # Rebalance on first trading day of each week
            signals = signals_raw.resample('W-MON').first().reindex(signals_raw.index, method='ffill')
        else:
            signals = signals_raw

        # Fill NaN with False (no signal)
        signals = signals.fillna(False)

        # Convert to dictionary
        signals_dict = {
            ticker: signals[ticker]
            for ticker in signals.columns
        }

        total_signals = signals.sum().sum()
        logger.info(f"✅ Generated {total_signals} total buy signals")

        return signals_dict

    def run_custom_engine_backtest(
        self,
        data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.Series],
        initial_capital: float = 100_000_000
    ) -> dict:
        """
        Run backtest with custom event-driven engine

        Args:
            data: Dictionary of OHLCV DataFrames
            signals: Dictionary of signal Series
            initial_capital: Starting capital (KRW)

        Returns:
            Dictionary with backtest results
        """
        logger.info("=" * 80)
        logger.info("RUNNING CUSTOM ENGINE BACKTEST")
        logger.info("=" * 80)

        # Create cost model with KIS broker fees
        cost_model = TransactionCostModel(
            broker='KIS',
            slippage_bps=5.0  # 5 bps slippage assumption
        )

        # Create backtest engine
        engine = BacktestEngine(
            initial_capital=initial_capital,
            cost_model=cost_model,
            size_type='equal_weight',
            target_positions=len([s for s in signals.values() if s.any()])
        )

        # Run backtest
        results = engine.run(data=data, signals=signals)

        return results

    def run_vectorbt_backtest(
        self,
        data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.Series],
        initial_capital: float = 100_000_000
    ) -> dict:
        """
        Run backtest with vectorbt (fast research engine)

        Args:
            data: Dictionary of OHLCV DataFrames
            signals: Dictionary of signal Series
            initial_capital: Starting capital (KRW)

        Returns:
            Dictionary with backtest results
        """
        logger.info("=" * 80)
        logger.info("RUNNING VECTORBT BACKTEST (RESEARCH)")
        logger.info("=" * 80)

        # Create vectorbt adapter
        adapter = VectorBTAdapter(
            initial_capital=initial_capital,
            commission=0.00015,  # 0.015%
            slippage=0.0005  # 5 bps
        )

        # Run portfolio backtest
        portfolio = adapter.run_portfolio_backtest(
            data=data,
            signals=signals,
            size_type='percent',
            size=1.0 / len(signals)  # Equal weight
        )

        # Calculate metrics
        metrics = adapter.calculate_metrics(portfolio)

        return {
            'portfolio': portfolio,
            'metrics': metrics
        }

    def print_comparison(self, custom_results: dict, vbt_results: dict = None):
        """
        Print backtest results comparison

        Args:
            custom_results: Custom engine results
            vbt_results: VectorBT results (optional)
        """
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)

        custom_metrics = custom_results['metrics']

        # Custom Engine Results
        print("\n📊 Custom Event-Driven Engine (Production):")
        print(f"  Total Return:         {custom_metrics['total_return_pct']:>10.2%}")
        print(f"  Annualized Return:    {custom_metrics['annualized_return']:>10.2%}")
        print(f"  Sharpe Ratio:         {custom_metrics['sharpe_ratio']:>10.2f}")
        print(f"  Max Drawdown:         {custom_metrics['max_drawdown']:>10.2%}")
        print(f"  Total Trades:         {custom_results['trade_stats']['total_trades']:>10,}")
        print(f"  Win Rate:             {custom_results['trade_stats']['win_rate']:>10.2%}")

        if vbt_results:
            vbt_metrics = vbt_results['metrics']

            # Extract scalar values
            vbt_total_return = vbt_metrics['total_return']
            if isinstance(vbt_total_return, pd.Series):
                vbt_total_return = vbt_total_return.iloc[0]

            vbt_sharpe = vbt_metrics['sharpe_ratio']
            if isinstance(vbt_sharpe, pd.Series):
                vbt_sharpe = vbt_sharpe.iloc[0]

            print("\n⚡ VectorBT Engine (Research, 100x faster):")
            print(f"  Total Return:         {vbt_total_return:>10.2%}")
            print(f"  Sharpe Ratio:         {vbt_sharpe:>10.2f}")
            print(f"  Total Trades:         {vbt_metrics['total_trades']:>10,}")

            print("\n📈 Performance Comparison:")
            print(f"  Return Difference:    {abs(custom_metrics['total_return_pct'] - vbt_total_return):>10.2%}")
            print(f"  Note: Small differences expected due to execution model differences")

        # Trade Statistics
        print("\n💰 Trade Analysis (Custom Engine):")
        trade_stats = custom_results['trade_stats']
        print(f"  Winning Trades:       {trade_stats.get('winning_trades', 0):>10,}")
        print(f"  Losing Trades:        {trade_stats.get('losing_trades', 0):>10,}")
        print(f"  Average Win:          ₩{trade_stats.get('avg_win', 0):>10,.0f}")
        print(f"  Average Loss:         ₩{trade_stats.get('avg_loss', 0):>10,.0f}")
        print(f"  Total Commission:     ₩{trade_stats.get('total_commission', 0):>10,.0f}")
        print(f"  Total Tax:            ₩{trade_stats.get('total_tax', 0):>10,.0f}")

        print("\n" + "=" * 80)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Week 3 Momentum Strategy Backtest')
    parser.add_argument('--start', type=str, default='2020-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000,
                       help='Initial capital (KRW)')
    parser.add_argument('--top-n', type=int, default=10,
                       help='Number of top momentum stocks to hold')
    parser.add_argument('--rebalance-freq', type=str, default='M',
                       choices=['M', 'W'],
                       help='Rebalancing frequency (M=monthly, W=weekly)')
    parser.add_argument('--engine', type=str, default='custom',
                       choices=['custom', 'vectorbt'],
                       help='Backtesting engine to use')
    parser.add_argument('--compare', action='store_true',
                       help='Run both engines and compare')
    parser.add_argument('--limit-tickers', type=int,
                       help='Limit number of tickers (for testing)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("WEEK 3 MOMENTUM STRATEGY BACKTEST")
    logger.info("=" * 80)
    logger.info(f"Period: {args.start} to {args.end}")
    logger.info(f"Capital: ₩{args.capital:,.0f}")
    logger.info(f"Top N: {args.top_n}")
    logger.info(f"Rebalance: {args.rebalance_freq}")
    logger.info("")

    # Connect to database
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize backtester
    backtester = Week3MomentumBacktest(db)

    # Load universe
    try:
        tickers = backtester.load_universe_tickers()
        if args.limit_tickers:
            tickers = tickers[:args.limit_tickers]
            logger.info(f"⚠️  Limited to {args.limit_tickers} tickers for testing")
    except Exception as e:
        logger.error(f"❌ Failed to load universe: {e}")
        return 1

    # Load OHLCV data
    try:
        data = backtester.load_ohlcv_data(tickers, args.start, args.end)
        if len(data) == 0:
            logger.error("❌ No data loaded")
            return 1
    except Exception as e:
        logger.error(f"❌ Failed to load OHLCV data: {e}")
        return 1

    # Calculate signals
    try:
        signals = backtester.calculate_momentum_signals(
            data,
            top_n=args.top_n,
            rebalance_freq=args.rebalance_freq
        )
    except Exception as e:
        logger.error(f"❌ Failed to calculate signals: {e}")
        return 1

    # Run backtests
    custom_results = None
    vbt_results = None

    if args.engine == 'custom' or args.compare:
        try:
            custom_results = backtester.run_custom_engine_backtest(
                data, signals, args.capital
            )
        except Exception as e:
            logger.error(f"❌ Custom engine backtest failed: {e}")
            return 1

    if args.engine == 'vectorbt' or args.compare:
        try:
            vbt_results = backtester.run_vectorbt_backtest(
                data, signals, args.capital
            )
        except Exception as e:
            logger.error(f"❌ VectorBT backtest failed: {e}")
            return 1

    # Print results
    if custom_results:
        backtester.print_comparison(custom_results, vbt_results if args.compare else None)
    elif vbt_results:
        # VectorBT only mode
        logger.info("VectorBT results generated (use --compare for detailed output)")

    logger.info("\n✅ Backtest completed successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
