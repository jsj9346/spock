"""
Performance Metrics Calculator for Backtesting

Provides comprehensive performance analytics including:
- Return metrics (total, annualized, cumulative)
- Risk-adjusted ratios (Sharpe, Sortino, Calmar, Information)
- Drawdown analysis (max, average, duration)
- Trade analytics (win rate, profit factor, expectancy)
- Statistical measures (volatility, skewness, kurtosis)

References:
- Modern Portfolio Theory: Markowitz (1952)
- Sharpe Ratio: Sharpe (1966)
- Sortino Ratio: Sortino & van der Meer (1991)
- Information Ratio: Grinold & Kahn (1995)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, Union
from scipy import stats
from loguru import logger


class PerformanceMetrics:
    """
    Comprehensive performance metrics calculator.

    Calculates industry-standard performance metrics for backtesting
    results, portfolio analysis, and strategy evaluation.

    All return-based metrics assume daily returns unless specified.
    Risk-free rate defaults to 0 (can be customized for Korean bonds).
    """

    def __init__(
        self,
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252  # Trading days
    ):
        """
        Initialize performance metrics calculator.

        Args:
            returns: Series of period returns (daily/weekly/monthly)
            benchmark_returns: Benchmark returns for comparison
            risk_free_rate: Annualized risk-free rate (e.g., 0.03 for 3%)
            periods_per_year: Number of periods per year for annualization
        """
        self.returns = returns.dropna()
        self.benchmark = benchmark_returns.dropna() if benchmark_returns is not None else None
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

        # Pre-calculate common values
        self._excess_returns = self.returns - (risk_free_rate / periods_per_year)
        self._downside_returns = self.returns[self.returns < 0]

        logger.debug(f"PerformanceMetrics initialized: {len(self.returns)} periods")

    # ========== Return Metrics ==========

    def total_return(self) -> float:
        """Calculate total return"""
        return (1 + self.returns).prod() - 1

    def annualized_return(self) -> float:
        """Calculate annualized return (CAGR)"""
        total_ret = self.total_return()
        n_periods = len(self.returns)
        years = n_periods / self.periods_per_year
        return (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0.0

    def cumulative_returns(self) -> pd.Series:
        """Calculate cumulative returns over time"""
        return (1 + self.returns).cumprod() - 1

    def monthly_returns(self) -> pd.Series:
        """Calculate monthly returns (from daily)"""
        if len(self.returns) == 0:
            return pd.Series()

        returns_df = pd.DataFrame({'returns': self.returns})
        returns_df['year_month'] = returns_df.index.to_period('M')
        monthly = returns_df.groupby('year_month')['returns'].apply(
            lambda x: (1 + x).prod() - 1
        )
        return monthly

    def annual_returns(self) -> pd.Series:
        """Calculate annual returns"""
        if len(self.returns) == 0:
            return pd.Series()

        returns_df = pd.DataFrame({'returns': self.returns})
        returns_df['year'] = returns_df.index.year
        annual = returns_df.groupby('year')['returns'].apply(
            lambda x: (1 + x).prod() - 1
        )
        return annual

    # ========== Volatility Metrics ==========

    def volatility(self) -> float:
        """Calculate annualized volatility (standard deviation)"""
        return self.returns.std() * np.sqrt(self.periods_per_year)

    def downside_volatility(self, mar: float = 0.0) -> float:
        """
        Calculate downside deviation (for Sortino ratio).

        Args:
            mar: Minimum acceptable return (MAR)
        """
        downside = self.returns[self.returns < mar] - mar
        if len(downside) == 0:
            return 0.0
        return downside.std() * np.sqrt(self.periods_per_year)

    def skewness(self) -> float:
        """Calculate return skewness"""
        return stats.skew(self.returns.dropna())

    def kurtosis(self) -> float:
        """Calculate return kurtosis (excess)"""
        return stats.kurtosis(self.returns.dropna())

    # ========== Risk-Adjusted Ratios ==========

    def sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio (risk-adjusted return).

        Sharpe Ratio = (Return - RiskFreeRate) / Volatility
        """
        if self._excess_returns.std() == 0:
            return 0.0

        return (
            self._excess_returns.mean() * self.periods_per_year /
            (self.returns.std() * np.sqrt(self.periods_per_year))
        )

    def sortino_ratio(self, mar: float = 0.0) -> float:
        """
        Calculate Sortino ratio (downside risk-adjusted return).

        Sortino Ratio = (Return - MAR) / Downside Deviation
        Better than Sharpe for asymmetric return distributions.

        Args:
            mar: Minimum acceptable return (annualized)
        """
        downside_vol = self.downside_volatility(mar / self.periods_per_year)
        if downside_vol == 0:
            return 0.0

        excess_return = self.annualized_return() - mar
        return excess_return / downside_vol

    def calmar_ratio(self) -> float:
        """
        Calculate Calmar ratio (return over max drawdown).

        Calmar Ratio = Annualized Return / Max Drawdown
        Measures return per unit of worst drawdown.
        """
        max_dd = self.max_drawdown()
        if max_dd == 0:
            return 0.0

        return self.annualized_return() / abs(max_dd)

    def information_ratio(self) -> float:
        """
        Calculate Information ratio (excess return vs benchmark).

        Information Ratio = (Portfolio Return - Benchmark Return) / Tracking Error
        Requires benchmark returns.
        """
        if self.benchmark is None:
            logger.warning("Information ratio requires benchmark returns")
            return 0.0

        # Align returns
        aligned_returns, aligned_benchmark = self.returns.align(self.benchmark, join='inner')
        excess = aligned_returns - aligned_benchmark

        tracking_error = excess.std() * np.sqrt(self.periods_per_year)
        if tracking_error == 0:
            return 0.0

        return excess.mean() * self.periods_per_year / tracking_error

    def omega_ratio(self, mar: float = 0.0) -> float:
        """
        Calculate Omega ratio (probability-weighted gains vs losses).

        Omega = Sum(Returns above MAR) / Sum(Returns below MAR)
        Values > 1 indicate positive performance.

        Args:
            mar: Minimum acceptable return (per period)
        """
        gains = self.returns[self.returns > mar] - mar
        losses = mar - self.returns[self.returns < mar]

        if losses.sum() == 0:
            return np.inf if gains.sum() > 0 else 0.0

        return gains.sum() / losses.sum()

    # ========== Drawdown Analysis ==========

    def drawdown_series(self) -> pd.Series:
        """Calculate drawdown series over time"""
        cumulative = self.cumulative_returns()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / (1 + running_max)
        return drawdown

    def max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        dd = self.drawdown_series()
        return dd.min() if len(dd) > 0 else 0.0

    def max_drawdown_duration(self) -> int:
        """Calculate longest drawdown duration (in periods)"""
        dd = self.drawdown_series()
        if len(dd) == 0:
            return 0

        # Find drawdown periods
        is_drawdown = dd < 0
        drawdown_periods = []
        current_duration = 0

        for in_dd in is_drawdown:
            if in_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    drawdown_periods.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            drawdown_periods.append(current_duration)

        return max(drawdown_periods) if drawdown_periods else 0

    def recovery_factor(self) -> float:
        """
        Calculate recovery factor (total return / max drawdown).

        Measures how much return was generated per unit of maximum risk.
        """
        max_dd = abs(self.max_drawdown())
        if max_dd == 0:
            return 0.0

        return self.total_return() / max_dd

    # ========== Value at Risk ==========

    def value_at_risk(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR) at given confidence level.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95%)

        Returns:
            VaR as negative return threshold
        """
        return np.percentile(self.returns, (1 - confidence) * 100)

    def conditional_var(self, confidence: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).

        Average loss beyond VaR threshold.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95%)
        """
        var = self.value_at_risk(confidence)
        return self.returns[self.returns <= var].mean()

    # ========== Comprehensive Report ==========

    def calculate_all(self) -> Dict[str, float]:
        """
        Calculate all performance metrics.

        Returns:
            Dictionary with all metrics
        """
        metrics = {
            # Return metrics
            'total_return': self.total_return(),
            'annualized_return': self.annualized_return(),
            'annualized_volatility': self.volatility(),

            # Risk-adjusted ratios
            'sharpe_ratio': self.sharpe_ratio(),
            'sortino_ratio': self.sortino_ratio(),
            'calmar_ratio': self.calmar_ratio(),
            'omega_ratio': self.omega_ratio(),

            # Drawdown metrics
            'max_drawdown': self.max_drawdown(),
            'max_drawdown_duration': self.max_drawdown_duration(),
            'recovery_factor': self.recovery_factor(),

            # Risk metrics
            'skewness': self.skewness(),
            'kurtosis': self.kurtosis(),
            'value_at_risk_95': self.value_at_risk(0.95),
            'conditional_var_95': self.conditional_var(0.95),

            # Statistical
            'best_period': self.returns.max(),
            'worst_period': self.returns.min(),
            'positive_periods': (self.returns > 0).sum(),
            'negative_periods': (self.returns < 0).sum(),
            'win_rate': (self.returns > 0).sum() / len(self.returns) if len(self.returns) > 0 else 0.0,
        }

        # Add benchmark metrics if available
        if self.benchmark is not None:
            metrics['information_ratio'] = self.information_ratio()

        return metrics

    def summary_table(self) -> pd.DataFrame:
        """Generate formatted summary table"""
        metrics = self.calculate_all()

        summary = pd.DataFrame([
            {'Metric': 'Total Return', 'Value': f"{metrics['total_return']:.2%}"},
            {'Metric': 'Annualized Return', 'Value': f"{metrics['annualized_return']:.2%}"},
            {'Metric': 'Annualized Volatility', 'Value': f"{metrics['annualized_volatility']:.2%}"},
            {'Metric': 'Sharpe Ratio', 'Value': f"{metrics['sharpe_ratio']:.2f}"},
            {'Metric': 'Sortino Ratio', 'Value': f"{metrics['sortino_ratio']:.2f}"},
            {'Metric': 'Calmar Ratio', 'Value': f"{metrics['calmar_ratio']:.2f}"},
            {'Metric': 'Max Drawdown', 'Value': f"{metrics['max_drawdown']:.2%}"},
            {'Metric': 'Win Rate', 'Value': f"{metrics['win_rate']:.2%}"},
        ])

        return summary.set_index('Metric')


class TradeAnalyzer:
    """
    Trade-level performance analytics.

    Analyzes individual trades for pattern recognition and
    strategy improvement insights.
    """

    def __init__(self, trades: pd.DataFrame):
        """
        Initialize trade analyzer.

        Args:
            trades: DataFrame with columns [entry_date, exit_date, entry_price,
                    exit_price, quantity, pnl, return]
        """
        self.trades = trades

    def win_rate(self) -> float:
        """Calculate percentage of winning trades"""
        if len(self.trades) == 0:
            return 0.0
        return (self.trades['pnl'] > 0).sum() / len(self.trades)

    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        wins = self.trades[self.trades['pnl'] > 0]['pnl'].sum()
        losses = abs(self.trades[self.trades['pnl'] < 0]['pnl'].sum())

        if losses == 0:
            return np.inf if wins > 0 else 0.0

        return wins / losses

    def expectancy(self) -> float:
        """Calculate trade expectancy (average PnL per trade)"""
        if len(self.trades) == 0:
            return 0.0
        return self.trades['pnl'].mean()

    def average_win_loss_ratio(self) -> float:
        """Calculate average win / average loss"""
        wins = self.trades[self.trades['pnl'] > 0]['pnl']
        losses = self.trades[self.trades['pnl'] < 0]['pnl']

        if len(losses) == 0:
            return np.inf if len(wins) > 0 else 0.0

        avg_win = wins.mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses.mean())

        return avg_win / avg_loss if avg_loss != 0 else 0.0

    def holding_period(self) -> Dict[str, float]:
        """Calculate holding period statistics"""
        durations = (self.trades['exit_date'] - self.trades['entry_date']).dt.days

        return {
            'mean': durations.mean(),
            'median': durations.median(),
            'min': durations.min(),
            'max': durations.max()
        }
