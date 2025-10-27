#!/usr/bin/env python3
"""
Post-Hoc Metrics Calculator for Backtest Results

Calculates accurate risk-adjusted metrics from daily portfolio values,
enabling reliable Sharpe ratio and Max Drawdown even with quarterly rebalancing.

Usage:
    python3 scripts/calculate_metrics_from_csv.py --csv backtest_results/file.csv
    python3 scripts/calculate_metrics_from_csv.py --csv backtest_results/file.csv --risk-free 0.03

Features:
    - Sharpe Ratio (annualized)
    - Sortino Ratio (downside deviation)
    - Calmar Ratio (return/max DD)
    - Maximum Drawdown
    - Win Rate
    - Volatility (annualized)

Author: Spock Quant Platform
Date: 2025-10-26
Purpose: Accurate metric calculation from daily portfolio values
"""

import sys
from pathlib import Path
import argparse
from loguru import logger
import pandas as pd
import numpy as np
from typing import Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def load_backtest_csv(csv_path: str) -> pd.DataFrame:
    """
    Load backtest CSV file with daily portfolio values.

    Args:
        csv_path: Path to backtest results CSV

    Returns:
        DataFrame with date, portfolio_value, returns columns

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If required columns missing
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logger.info(f"📂 Loading backtest CSV: {csv_path.name}")

    df = pd.read_csv(csv_path)

    # Validate required columns
    required_cols = ['date', 'portfolio_value']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])

    # Sort by date
    df = df.sort_values('date').reset_index(drop=True)

    logger.info(f"   ✅ Loaded {len(df)} rows from {df['date'].min()} to {df['date'].max()}")

    return df


def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate daily returns from portfolio values.

    Args:
        df: DataFrame with portfolio_value column

    Returns:
        DataFrame with added daily_return column
    """
    df = df.copy()

    # Calculate daily returns
    df['daily_return'] = df['portfolio_value'].pct_change()

    # Drop first row (NaN return)
    df = df.dropna(subset=['daily_return']).reset_index(drop=True)

    logger.info(f"   ✅ Calculated {len(df)} daily returns")

    return df


def calculate_sharpe_ratio(
    df: pd.DataFrame,
    risk_free_rate: float = 0.0,
    trading_days: int = 252
) -> float:
    """
    Calculate annualized Sharpe ratio from daily returns.

    Args:
        df: DataFrame with daily_return column
        risk_free_rate: Annual risk-free rate (default 0.0)
        trading_days: Trading days per year (default 252)

    Returns:
        Sharpe ratio (float)
    """
    if len(df) < 2:
        logger.warning("   ⚠️  Insufficient data for Sharpe ratio (need ≥2 returns)")
        return 0.0

    # Calculate annualized return
    total_return = (df['portfolio_value'].iloc[-1] / df['portfolio_value'].iloc[0]) - 1
    num_days = len(df)
    annualized_return = (1 + total_return) ** (trading_days / num_days) - 1

    # Calculate annualized volatility
    daily_volatility = df['daily_return'].std()
    annualized_volatility = daily_volatility * np.sqrt(trading_days)

    # Sharpe ratio
    if annualized_volatility == 0:
        logger.warning("   ⚠️  Zero volatility, cannot calculate Sharpe ratio")
        return 0.0

    sharpe = (annualized_return - risk_free_rate) / annualized_volatility

    return sharpe


def calculate_sortino_ratio(
    df: pd.DataFrame,
    risk_free_rate: float = 0.0,
    trading_days: int = 252
) -> float:
    """
    Calculate annualized Sortino ratio (downside deviation only).

    Args:
        df: DataFrame with daily_return column
        risk_free_rate: Annual risk-free rate (default 0.0)
        trading_days: Trading days per year (default 252)

    Returns:
        Sortino ratio (float)
    """
    if len(df) < 2:
        logger.warning("   ⚠️  Insufficient data for Sortino ratio")
        return 0.0

    # Calculate annualized return
    total_return = (df['portfolio_value'].iloc[-1] / df['portfolio_value'].iloc[0]) - 1
    num_days = len(df)
    annualized_return = (1 + total_return) ** (trading_days / num_days) - 1

    # Calculate downside deviation (only negative returns)
    negative_returns = df['daily_return'][df['daily_return'] < 0]

    if len(negative_returns) == 0:
        logger.info("   ℹ️  No negative returns, Sortino = infinity (capped at 10)")
        return 10.0  # Cap at reasonable value

    downside_deviation = negative_returns.std() * np.sqrt(trading_days)

    if downside_deviation == 0:
        return 10.0  # Cap at reasonable value

    sortino = (annualized_return - risk_free_rate) / downside_deviation

    return sortino


def calculate_max_drawdown(df: pd.DataFrame) -> Tuple[float, str, str]:
    """
    Calculate maximum drawdown from daily portfolio values.

    Args:
        df: DataFrame with portfolio_value and date columns

    Returns:
        Tuple of (max_drawdown, peak_date, trough_date)
    """
    if len(df) < 2:
        logger.warning("   ⚠️  Insufficient data for Max Drawdown")
        return 0.0, None, None

    # Calculate cumulative returns
    df = df.copy()
    df['cumulative'] = df['portfolio_value'] / df['portfolio_value'].iloc[0]

    # Calculate running maximum
    df['running_max'] = df['cumulative'].cummax()

    # Calculate drawdown
    df['drawdown'] = (df['cumulative'] - df['running_max']) / df['running_max']

    # Find maximum drawdown
    max_dd_idx = df['drawdown'].idxmin()
    max_dd = df.loc[max_dd_idx, 'drawdown']

    # Find peak before this trough
    trough_date = df.loc[max_dd_idx, 'date']
    peak_idx = df.loc[:max_dd_idx, 'running_max'].idxmax()
    peak_date = df.loc[peak_idx, 'date']

    return max_dd, str(peak_date.date()), str(trough_date.date())


def calculate_calmar_ratio(
    df: pd.DataFrame,
    trading_days: int = 252
) -> float:
    """
    Calculate Calmar ratio (annualized return / max drawdown).

    Args:
        df: DataFrame with daily_return column
        trading_days: Trading days per year (default 252)

    Returns:
        Calmar ratio (float)
    """
    if len(df) < 2:
        logger.warning("   ⚠️  Insufficient data for Calmar ratio")
        return 0.0

    # Calculate annualized return
    total_return = (df['portfolio_value'].iloc[-1] / df['portfolio_value'].iloc[0]) - 1
    num_days = len(df)
    annualized_return = (1 + total_return) ** (trading_days / num_days) - 1

    # Calculate max drawdown
    max_dd, _, _ = calculate_max_drawdown(df)

    if max_dd == 0:
        logger.info("   ℹ️  No drawdown, Calmar = infinity (capped at 10)")
        return 10.0  # Cap at reasonable value

    calmar = annualized_return / abs(max_dd)

    return calmar


def calculate_win_rate(df: pd.DataFrame) -> float:
    """
    Calculate percentage of positive return days.

    Args:
        df: DataFrame with daily_return column

    Returns:
        Win rate as percentage (0-100)
    """
    if len(df) < 2:
        return 0.0

    positive_days = (df['daily_return'] > 0).sum()
    total_days = len(df)

    win_rate = (positive_days / total_days) * 100

    return win_rate


def calculate_all_metrics(
    csv_path: str,
    risk_free_rate: float = 0.0,
    trading_days: int = 252
) -> Dict:
    """
    Calculate all metrics from backtest CSV.

    Args:
        csv_path: Path to backtest results CSV
        risk_free_rate: Annual risk-free rate (default 0.0)
        trading_days: Trading days per year (default 252)

    Returns:
        Dictionary with all calculated metrics
    """
    logger.info("\n" + "=" * 80)
    logger.info("POST-HOC METRICS CALCULATOR")
    logger.info("=" * 80)

    # Load data
    df = load_backtest_csv(csv_path)

    # Calculate returns
    df = calculate_returns(df)

    logger.info(f"\n📊 Calculating Metrics:")
    logger.info(f"   Risk-Free Rate: {risk_free_rate:.2%}")
    logger.info(f"   Trading Days/Year: {trading_days}")

    # Calculate all metrics
    metrics = {}

    # Basic statistics
    initial_value = df['portfolio_value'].iloc[0]
    final_value = df['portfolio_value'].iloc[-1]
    total_return = (final_value / initial_value) - 1
    num_days = len(df)
    annualized_return = (1 + total_return) ** (trading_days / num_days) - 1

    metrics['initial_value'] = initial_value
    metrics['final_value'] = final_value
    metrics['total_return'] = total_return
    metrics['annualized_return'] = annualized_return
    metrics['num_days'] = num_days

    # Volatility
    daily_volatility = df['daily_return'].std()
    annualized_volatility = daily_volatility * np.sqrt(trading_days)
    metrics['volatility'] = annualized_volatility

    # Risk-adjusted metrics
    metrics['sharpe_ratio'] = calculate_sharpe_ratio(df, risk_free_rate, trading_days)
    metrics['sortino_ratio'] = calculate_sortino_ratio(df, risk_free_rate, trading_days)
    metrics['calmar_ratio'] = calculate_calmar_ratio(df, trading_days)

    # Drawdown
    max_dd, peak_date, trough_date = calculate_max_drawdown(df)
    metrics['max_drawdown'] = max_dd
    metrics['max_dd_peak_date'] = peak_date
    metrics['max_dd_trough_date'] = trough_date

    # Win rate
    metrics['win_rate'] = calculate_win_rate(df)

    return metrics


def print_results(metrics: Dict):
    """Print formatted results."""
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)

    logger.info(f"\n📈 RETURNS:")
    logger.info(f"   Initial Value:       ₩ {metrics['initial_value']:>15,.0f}")
    logger.info(f"   Final Value:         ₩ {metrics['final_value']:>15,.0f}")
    logger.info(f"   Total Return:            {metrics['total_return']:>10.2%}")
    logger.info(f"   Annualized Return:       {metrics['annualized_return']:>10.2%}")

    logger.info(f"\n📊 RISK METRICS:")
    logger.info(f"   Sharpe Ratio:            {metrics['sharpe_ratio']:>10.2f}")
    logger.info(f"   Sortino Ratio:           {metrics['sortino_ratio']:>10.2f}")
    logger.info(f"   Calmar Ratio:            {metrics['calmar_ratio']:>10.2f}")
    logger.info(f"   Volatility (annual):     {metrics['volatility']:>9.2%}")
    logger.info(f"   Max Drawdown:            {metrics['max_drawdown']:>9.2%}")

    if metrics['max_dd_peak_date']:
        logger.info(f"   DD Peak Date:            {metrics['max_dd_peak_date']}")
        logger.info(f"   DD Trough Date:          {metrics['max_dd_trough_date']}")

    logger.info(f"\n📉 TRADING STATS:")
    logger.info(f"   Win Rate:                {metrics['win_rate']:>9.1f}%")
    logger.info(f"   Num Days:                {metrics['num_days']:>10}")

    logger.info("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Calculate post-hoc metrics from backtest CSV'
    )

    parser.add_argument(
        '--csv',
        required=True,
        help='Path to backtest results CSV file'
    )

    parser.add_argument(
        '--risk-free',
        type=float,
        default=0.0,
        help='Annual risk-free rate (default: 0.0)'
    )

    parser.add_argument(
        '--trading-days',
        type=int,
        default=252,
        help='Trading days per year (default: 252)'
    )

    args = parser.parse_args()

    try:
        # Calculate metrics
        metrics = calculate_all_metrics(
            args.csv,
            risk_free_rate=args.risk_free,
            trading_days=args.trading_days
        )

        # Print results
        print_results(metrics)

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
