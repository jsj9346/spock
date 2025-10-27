"""
Performance Analyzer

Purpose: Comprehensive performance metrics calculation for backtest results.

Key Features:
  - Return metrics (total_return, annualized_return, CAGR)
  - Risk metrics (Sharpe, Sortino, Calmar, max_drawdown)
  - Trading metrics (win_rate, profit_factor, avg_win_loss_ratio)
  - Pattern-specific metrics (win rate by pattern type)
  - Region-specific metrics (performance by market)
  - Kelly accuracy validation (actual vs predicted win rates)
  - Optional benchmark comparison (alpha, beta, information_ratio)

Design Philosophy:
  - Comprehensive metric calculation
  - Pattern and region-specific analysis
  - Kelly Calculator accuracy validation
  - Evidence-based performance assessment
"""

from datetime import date
from typing import List, Dict, Optional
import logging
import pandas as pd
from collections import defaultdict

from .backtest_config import Trade, PerformanceMetrics, PatternMetrics
from modules.kelly_calculator import PatternType


logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """
    Calculate comprehensive performance metrics from backtest results.

    Attributes:
        trades: List of completed trades
        equity_curve: Time series of portfolio values
        initial_capital: Starting capital
        benchmark_returns: Optional benchmark returns for comparison
    """

    def __init__(
        self,
        trades: List[Trade],
        equity_curve: pd.Series,
        initial_capital: float,
        benchmark_returns: Optional[pd.Series] = None,
    ):
        """
        Initialize performance analyzer.

        Args:
            trades: List of Trade objects from backtest
            equity_curve: Time series of portfolio values (sorted by date)
            initial_capital: Starting capital amount
            benchmark_returns: Optional benchmark returns for alpha/beta calculation
        """
        self.trades = trades
        self.equity_curve = equity_curve.sort_index()
        self.initial_capital = initial_capital
        self.benchmark_returns = benchmark_returns

        # Filter closed trades for analysis
        self.closed_trades = [t for t in trades if t.is_closed]

        logger.info(
            f"PerformanceAnalyzer initialized: {len(self.closed_trades)} closed trades, "
            f"{len(self.equity_curve)} days"
        )

    def calculate_metrics(self) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Returns:
            PerformanceMetrics with all calculated values

        Metrics Calculated:
            - Return metrics: total_return, annualized_return, CAGR
            - Risk metrics: Sharpe, Sortino, Calmar, max_drawdown, downside_deviation
            - Trading metrics: win_rate, profit_factor, avg_win_loss_ratio
            - Kelly accuracy: Actual vs predicted win rates
            - Benchmark metrics (optional): alpha, beta, information_ratio
        """
        logger.info("Calculating comprehensive performance metrics...")

        # Calculate all metric groups
        return_metrics = self._calculate_return_metrics()
        risk_metrics = self._calculate_risk_metrics()
        trading_metrics = self._calculate_trading_metrics()
        kelly_accuracy = self._calculate_kelly_accuracy()

        # Optional benchmark metrics
        benchmark_metrics = {}
        if self.benchmark_returns is not None:
            benchmark_metrics = self._calculate_benchmark_metrics()

        # Combine all metrics
        metrics = PerformanceMetrics(
            # Return metrics
            total_return=return_metrics["total_return"],
            annualized_return=return_metrics["annualized_return"],
            cagr=return_metrics["cagr"],
            # Risk metrics
            sharpe_ratio=risk_metrics["sharpe_ratio"],
            sortino_ratio=risk_metrics["sortino_ratio"],
            calmar_ratio=risk_metrics["calmar_ratio"],
            max_drawdown=risk_metrics["max_drawdown"],
            max_drawdown_duration_days=risk_metrics["max_drawdown_duration_days"],
            std_returns=risk_metrics["std_returns"],
            downside_deviation=risk_metrics["downside_deviation"],
            # Trading metrics
            total_trades=trading_metrics["total_trades"],
            win_rate=trading_metrics["win_rate"],
            profit_factor=trading_metrics["profit_factor"],
            avg_win_pct=trading_metrics["avg_win_pct"],
            avg_loss_pct=trading_metrics["avg_loss_pct"],
            avg_win_loss_ratio=trading_metrics["avg_win_loss_ratio"],
            avg_holding_period_days=trading_metrics["avg_holding_period_days"],
            # Kelly accuracy
            kelly_accuracy=kelly_accuracy,
            # Benchmark metrics (optional)
            alpha=benchmark_metrics.get("alpha"),
            beta=benchmark_metrics.get("beta"),
            information_ratio=benchmark_metrics.get("information_ratio"),
        )

        logger.info(
            f"Metrics calculated: Total Return {metrics.total_return:.1%}, "
            f"Sharpe {metrics.sharpe_ratio:.2f}, Max DD {metrics.max_drawdown:.1%}"
        )

        return metrics

    def calculate_pattern_metrics(self) -> Dict[str, PatternMetrics]:
        """
        Calculate metrics by pattern type.

        Returns:
            Dictionary {pattern_type: PatternMetrics}

        Example:
            {
                'Stage2': PatternMetrics(total_trades=15, win_rate=0.67, ...),
                'VCP': PatternMetrics(total_trades=8, win_rate=0.75, ...),
            }
        """
        logger.info("Calculating pattern-specific metrics...")

        # Group trades by pattern type
        pattern_trades = defaultdict(list)
        for trade in self.closed_trades:
            pattern_trades[trade.pattern_type].append(trade)

        # Calculate metrics for each pattern
        pattern_metrics = {}
        for pattern, trades in pattern_trades.items():
            winning_trades = [t for t in trades if t.pnl > 0]
            win_rate = len(winning_trades) / len(trades) if len(trades) > 0 else 0.0
            avg_return = sum(t.pnl_pct for t in trades) / len(trades)
            total_pnl = sum(t.pnl for t in trades)
            avg_holding = sum(t.holding_period_days for t in trades) / len(trades)

            pattern_metrics[pattern] = PatternMetrics(
                pattern_type=pattern,
                total_trades=len(trades),
                win_rate=win_rate,
                avg_return=avg_return,
                total_pnl=total_pnl,
                avg_holding_days=avg_holding,
            )

            logger.debug(
                f"Pattern {pattern}: {len(trades)} trades, "
                f"win_rate={win_rate:.1%}, avg_return={avg_return:.1%}"
            )

        logger.info(f"Pattern metrics calculated for {len(pattern_metrics)} patterns")
        return pattern_metrics

    def calculate_region_metrics(self) -> Dict[str, PerformanceMetrics]:
        """
        Calculate metrics by region (KR, US, CN, HK, JP, VN).

        Returns:
            Dictionary {region: PerformanceMetrics}

        Example:
            {
                'KR': PerformanceMetrics(total_return=0.25, win_rate=0.58, ...),
                'US': PerformanceMetrics(total_return=0.18, win_rate=0.62, ...),
            }
        """
        logger.info("Calculating region-specific metrics...")

        # Group trades by region
        region_trades = defaultdict(list)
        for trade in self.closed_trades:
            region_trades[trade.region].append(trade)

        # Calculate metrics for each region
        region_metrics = {}
        for region, trades in region_trades.items():
            # Create region-specific equity curve (simplified)
            # Note: This is a simplified version - full implementation would track
            # region-specific portfolio values over time
            region_pnl = sum(t.pnl for t in trades)
            region_return = region_pnl / self.initial_capital

            # Calculate region-specific trading metrics
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl < 0]
            win_rate = len(winning_trades) / len(trades) if len(trades) > 0 else 0.0

            avg_win_pct = (
                sum(t.pnl_pct for t in winning_trades) / len(winning_trades)
                if len(winning_trades) > 0
                else 0.0
            )
            avg_loss_pct = (
                sum(t.pnl_pct for t in losing_trades) / len(losing_trades)
                if len(losing_trades) > 0
                else 0.0
            )
            avg_win_loss_ratio = (
                abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0
            )

            total_profit = sum(t.pnl for t in winning_trades)
            total_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

            avg_holding_days = (
                sum(t.holding_period_days for t in trades) / len(trades)
                if len(trades) > 0
                else 0.0
            )

            # Create PerformanceMetrics for region
            # Note: Simplified risk metrics (no region-specific equity curve)
            region_metrics[region] = PerformanceMetrics(
                total_return=region_return,
                annualized_return=0.0,  # Simplified
                cagr=0.0,  # Simplified
                sharpe_ratio=0.0,  # Simplified
                sortino_ratio=0.0,  # Simplified
                calmar_ratio=0.0,  # Simplified
                max_drawdown=0.0,  # Simplified
                max_drawdown_duration_days=0,  # Simplified
                std_returns=0.0,  # Simplified
                downside_deviation=0.0,  # Simplified
                total_trades=len(trades),
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win_pct=avg_win_pct,
                avg_loss_pct=avg_loss_pct,
                avg_win_loss_ratio=avg_win_loss_ratio,
                avg_holding_period_days=avg_holding_days,
                kelly_accuracy=0.0,  # Simplified
            )

            logger.debug(
                f"Region {region}: {len(trades)} trades, "
                f"win_rate={win_rate:.1%}, total_return={region_return:.1%}"
            )

        logger.info(f"Region metrics calculated for {len(region_metrics)} regions")
        return region_metrics

    def _calculate_return_metrics(self) -> dict:
        """
        Calculate return metrics (total, annualized, CAGR).

        Returns:
            Dictionary with total_return, annualized_return, cagr
        """
        final_value = self.equity_curve.iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital

        # Calculate annualized return and CAGR
        days = (self.equity_curve.index[-1] - self.equity_curve.index[0]).days
        years = days / 365.25

        if years > 0:
            annualized_return = (1 + total_return) ** (1 / years) - 1
        else:
            annualized_return = 0.0

        cagr = annualized_return  # CAGR = annualized return

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "cagr": cagr,
        }

    def _calculate_risk_metrics(self) -> dict:
        """
        Calculate risk metrics (Sharpe, Sortino, Calmar, max_drawdown).

        Returns:
            Dictionary with risk metrics
        """
        # Calculate daily returns
        daily_returns = self.equity_curve.pct_change().dropna()

        # Standard deviation (annualized)
        std_returns = daily_returns.std() * (252 ** 0.5)

        # Annualized return (for Sharpe/Sortino)
        return_metrics = self._calculate_return_metrics()
        annualized_return = return_metrics["annualized_return"]

        # Sharpe Ratio (risk-free rate = 0 for simplicity)
        sharpe_ratio = annualized_return / std_returns if std_returns > 0 else 0.0

        # Downside deviation (for Sortino)
        downside_returns = daily_returns[daily_returns < 0]
        downside_deviation = downside_returns.std() * (252 ** 0.5)
        sortino_ratio = (
            annualized_return / downside_deviation if downside_deviation > 0 else 0.0
        )

        # Max drawdown analysis
        running_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve - running_max) / running_max
        max_drawdown = drawdown.min()

        # Max drawdown duration
        drawdown_start = drawdown.idxmin()
        drawdown_recovery = self.equity_curve[
            self.equity_curve >= self.equity_curve.loc[drawdown_start]
        ]
        if len(drawdown_recovery) > 0:
            recovery_date = drawdown_recovery.index[0]
            max_dd_duration = (recovery_date - drawdown_start).days
        else:
            max_dd_duration = (self.equity_curve.index[-1] - drawdown_start).days

        # Calmar Ratio
        cagr = return_metrics["cagr"]
        calmar_ratio = cagr / abs(max_drawdown) if max_drawdown != 0 else 0.0

        return {
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_duration_days": max_dd_duration,
            "std_returns": std_returns,
            "downside_deviation": downside_deviation,
        }

    def _calculate_trading_metrics(self) -> dict:
        """
        Calculate trading metrics (win_rate, profit_factor, etc.).

        Returns:
            Dictionary with trading metrics
        """
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.pnl < 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0

        avg_win_pct = (
            sum(t.pnl_pct for t in winning_trades) / len(winning_trades)
            if len(winning_trades) > 0
            else 0.0
        )
        avg_loss_pct = (
            sum(t.pnl_pct for t in losing_trades) / len(losing_trades)
            if len(losing_trades) > 0
            else 0.0
        )
        avg_win_loss_ratio = (
            abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0
        )

        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

        avg_holding_days = (
            sum(t.holding_period_days for t in self.closed_trades) / len(self.closed_trades)
            if len(self.closed_trades) > 0
            else 0.0
        )

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win_pct": avg_win_pct,
            "avg_loss_pct": avg_loss_pct,
            "avg_win_loss_ratio": avg_win_loss_ratio,
            "avg_holding_period_days": avg_holding_days,
        }

    def _calculate_kelly_accuracy(self) -> float:
        """
        Calculate Kelly Calculator accuracy.

        Compares actual win rates vs Kelly Calculator predicted win rates by pattern.

        Returns:
            Kelly accuracy score (0.0-1.0)

        Formula:
            accuracy = 1 - |actual_win_rate - predicted_win_rate| / predicted_win_rate
        """
        # Pattern win rate predictions from KellyCalculator
        # Source: modules/kelly_calculator.py PatternType win rates
        kelly_predictions = {
            PatternType.STAGE_1_TO_2.value: 0.65,
            PatternType.VCP_BREAKOUT.value: 0.62,
            PatternType.CUP_HANDLE.value: 0.58,
            PatternType.HIGH_60D_BREAKOUT.value: 0.55,
            PatternType.STAGE_2_CONTINUATION.value: 0.52,
            PatternType.MA200_BREAKOUT.value: 0.50,
        }

        # Calculate actual win rates by pattern
        pattern_trades = defaultdict(list)
        for trade in self.closed_trades:
            pattern_trades[trade.pattern_type].append(trade)

        # Calculate accuracy for each pattern
        accuracy_scores = []
        for pattern, trades in pattern_trades.items():
            if len(trades) == 0:
                continue

            # Get Kelly prediction
            predicted_win_rate = kelly_predictions.get(pattern, 0.55)  # Default 55%

            # Calculate actual win rate
            winning_trades = [t for t in trades if t.pnl > 0]
            actual_win_rate = len(winning_trades) / len(trades)

            # Calculate accuracy for this pattern
            if predicted_win_rate > 0:
                pattern_accuracy = 1 - abs(actual_win_rate - predicted_win_rate) / predicted_win_rate
                pattern_accuracy = max(0.0, min(1.0, pattern_accuracy))  # Clamp to [0, 1]
                accuracy_scores.append(pattern_accuracy)

                logger.debug(
                    f"Pattern {pattern}: Actual {actual_win_rate:.1%} vs "
                    f"Predicted {predicted_win_rate:.1%} = {pattern_accuracy:.1%} accuracy"
                )

        # Overall accuracy (average across patterns)
        if len(accuracy_scores) > 0:
            kelly_accuracy = sum(accuracy_scores) / len(accuracy_scores)
        else:
            kelly_accuracy = 0.95  # Default if no patterns

        logger.info(f"Kelly accuracy: {kelly_accuracy:.1%}")
        return kelly_accuracy

    def _calculate_benchmark_metrics(self) -> dict:
        """
        Calculate benchmark comparison metrics (alpha, beta, information ratio).

        Returns:
            Dictionary with alpha, beta, information_ratio

        Note:
            Requires benchmark_returns to be provided at initialization.
        """
        if self.benchmark_returns is None:
            return {}

        # Calculate portfolio returns
        portfolio_returns = self.equity_curve.pct_change().dropna()

        # Align returns to benchmark
        aligned_portfolio, aligned_benchmark = portfolio_returns.align(
            self.benchmark_returns, join="inner"
        )

        if len(aligned_portfolio) == 0:
            logger.warning("No overlapping dates between portfolio and benchmark")
            return {}

        # Calculate beta (covariance / variance)
        covariance = aligned_portfolio.cov(aligned_benchmark)
        benchmark_variance = aligned_benchmark.var()
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

        # Calculate alpha (portfolio return - beta * benchmark return)
        portfolio_annualized = (1 + aligned_portfolio.mean()) ** 252 - 1
        benchmark_annualized = (1 + aligned_benchmark.mean()) ** 252 - 1
        alpha = portfolio_annualized - beta * benchmark_annualized

        # Calculate information ratio (excess return / tracking error)
        excess_returns = aligned_portfolio - aligned_benchmark
        tracking_error = excess_returns.std() * (252 ** 0.5)
        information_ratio = (
            excess_returns.mean() * 252 / tracking_error if tracking_error > 0 else 0.0
        )

        logger.info(
            f"Benchmark metrics: Alpha {alpha:.2%}, Beta {beta:.2f}, "
            f"Information Ratio {information_ratio:.2f}"
        )

        return {
            "alpha": alpha,
            "beta": beta,
            "information_ratio": information_ratio,
        }
