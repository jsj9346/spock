#!/usr/bin/env python3
"""
Simple Backtest for Multi-Factor Strategy

Evaluates performance of generated signals with realistic transaction costs.

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from modules.db_manager_postgres import PostgresDatabaseManager
import logging

logger = logging.getLogger(__name__)


class SimpleBacktester:
    """
    Simple backtester for long-short strategy

    Assumptions:
    - Equal-weight portfolio
    - Monthly rebalancing
    - Transaction cost: 0.3% one-way
    """

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        transaction_cost: float = 0.003
    ):
        self.db = db_manager
        self.transaction_cost = transaction_cost

    def get_forward_returns(
        self,
        ticker: str,
        start_date: datetime,
        holding_days: int = 21
    ) -> float:
        """
        Calculate forward return from start_date

        Args:
            ticker: Stock ticker
            start_date: Purchase date
            holding_days: Holding period in days (default: 21 ~ 1 month)

        Returns:
            Forward return (%) or None if data unavailable
        """
        end_date = start_date + timedelta(days=holding_days + 15)  # Buffer for weekends

        query = """
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = %s
              AND region = 'KR'
              AND timeframe = '1d'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
        """

        result = self.db.execute_query(query, (ticker, start_date.date(), end_date.date()))

        if len(result) < 2:
            return None

        # Get entry and exit prices
        entry_price = float(result[0]['close'])

        # Find price after ~holding_days
        if len(result) >= holding_days:
            exit_price = float(result[holding_days - 1]['close'])
        else:
            # Use last available price
            exit_price = float(result[-1]['close'])

        # Calculate return
        gross_return = (exit_price - entry_price) / entry_price

        # Subtract transaction costs (buy + sell)
        net_return = gross_return - 2 * self.transaction_cost

        return net_return

    def backtest_signals(
        self,
        signals_df: pd.DataFrame,
        holding_days: int = 21
    ) -> pd.DataFrame:
        """
        Backtest signals and calculate returns

        Args:
            signals_df: DataFrame with columns: date, ticker, signal, rank, score
            holding_days: Holding period in days (default: 21)

        Returns:
            DataFrame with backtest results per rebalancing date
        """
        rebal_dates = signals_df['date'].unique()
        results = []

        for rebal_date in rebal_dates:
            rebal_date_dt = pd.to_datetime(rebal_date)
            logger.info(f"Backtesting rebalancing date: {rebal_date}")

            # Get signals for this date
            rebal_signals = signals_df[signals_df['date'] == rebal_date]

            # Long portfolio
            long_signals = rebal_signals[rebal_signals['signal'] == 1]
            long_returns = []

            for _, row in long_signals.iterrows():
                fwd_return = self.get_forward_returns(
                    row['ticker'],
                    rebal_date_dt,
                    holding_days
                )
                if fwd_return is not None:
                    long_returns.append(fwd_return)

            # Short portfolio
            short_signals = rebal_signals[rebal_signals['signal'] == -1]
            short_returns = []

            for _, row in short_signals.iterrows():
                fwd_return = self.get_forward_returns(
                    row['ticker'],
                    rebal_date_dt,
                    holding_days
                )
                if fwd_return is not None:
                    # Invert for short position
                    short_returns.append(-fwd_return)

            # Portfolio return = 50% long + 50% short
            if long_returns and short_returns:
                long_avg = np.mean(long_returns)
                short_avg = np.mean(short_returns)
                portfolio_return = 0.5 * long_avg + 0.5 * short_avg

                results.append({
                    'date': rebal_date,
                    'long_return': long_avg,
                    'short_return': short_avg,
                    'portfolio_return': portfolio_return,
                    'long_count': len(long_returns),
                    'short_count': len(short_returns)
                })

                logger.info(f"  Long: {long_avg:.2%} ({len(long_returns)} stocks)")
                logger.info(f"  Short: {short_avg:.2%} ({len(short_returns)} stocks)")
                logger.info(f"  Portfolio: {portfolio_return:.2%}")

        return pd.DataFrame(results)

    def calculate_performance_metrics(
        self,
        results_df: pd.DataFrame
    ) -> dict:
        """
        Calculate strategy performance metrics

        Args:
            results_df: Backtest results DataFrame

        Returns:
            Dictionary of performance metrics
        """
        returns = results_df['portfolio_return'].values

        # Total return (compounded)
        cumulative_return = np.prod(1 + returns) - 1

        # Annualized return (assuming monthly rebalancing)
        months = len(returns)
        annualized_return = (1 + cumulative_return) ** (12 / months) - 1

        # Annualized volatility
        monthly_vol = np.std(returns)
        annualized_vol = monthly_vol * np.sqrt(12)

        # Sharpe ratio (assume 0% risk-free rate)
        sharpe_ratio = annualized_return / annualized_vol if annualized_vol > 0 else 0

        # Max drawdown
        cum_returns = (1 + results_df['portfolio_return']).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max
        max_drawdown = drawdown.min()

        # Win rate
        win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0

        # Average win/loss
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = losses.mean() if len(losses) > 0 else 0

        # Profit factor
        total_wins = wins.sum() if len(wins) > 0 else 0
        total_losses = abs(losses.sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else np.inf

        return {
            'total_return': cumulative_return,
            'annualized_return': annualized_return,
            'annualized_volatility': annualized_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'num_periods': months
        }


def main():
    """Run backtest on generated signals"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Load signals
    signals_file = 'multi_factor_signals_2024.csv'
    logger.info(f"Loading signals from {signals_file}...")
    signals_df = pd.read_csv(signals_file, dtype={'ticker': str})  # Force ticker as string
    signals_df['date'] = pd.to_datetime(signals_df['date'])

    logger.info(f"Loaded {len(signals_df)} signals from {signals_df['date'].nunique()} rebalancing dates")

    # Initialize backtester
    db = PostgresDatabaseManager()
    backtester = SimpleBacktester(db, transaction_cost=0.003)

    # Run backtest
    logger.info("\n" + "="*80)
    logger.info("Running Backtest...")
    logger.info("="*80)

    results_df = backtester.backtest_signals(signals_df, holding_days=21)

    # Calculate metrics
    metrics = backtester.calculate_performance_metrics(results_df)

    # Print results
    print("\n" + "="*80)
    print("Multi-Factor Strategy Backtest Results (2024)")
    print("="*80)
    print(f"Period: {results_df['date'].min()} to {results_df['date'].max()}")
    print(f"Rebalancing: Monthly ({metrics['num_periods']} periods)")
    print(f"Transaction Cost: {backtester.transaction_cost * 100:.2f}% (one-way)")
    print("")
    print("Performance Metrics:")
    print(f"  Total Return:        {metrics['total_return']:>10.2%}")
    print(f"  Annualized Return:   {metrics['annualized_return']:>10.2%}")
    print(f"  Annualized Vol:      {metrics['annualized_volatility']:>10.2%}")
    print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:>10.2f}")
    print(f"  Max Drawdown:        {metrics['max_drawdown']:>10.2%}")
    print(f"  Win Rate:            {metrics['win_rate']:>10.2%}")
    print(f"  Avg Win:             {metrics['avg_win']:>10.2%}")
    print(f"  Avg Loss:            {metrics['avg_loss']:>10.2%}")
    print(f"  Profit Factor:       {metrics['profit_factor']:>10.2f}")
    print("="*80)

    # Save results
    results_file = 'backtest_results_2024.csv'
    results_df.to_csv(results_file, index=False)
    logger.info(f"\nBacktest results saved to {results_file}")

    # Save metrics
    metrics_df = pd.DataFrame([metrics])
    metrics_file = 'backtest_metrics_2024.csv'
    metrics_df.to_csv(metrics_file, index=False)
    logger.info(f"Performance metrics saved to {metrics_file}")


if __name__ == '__main__':
    main()
