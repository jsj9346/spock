"""
Engine Comparator Utility

Purpose: Compare vectorbt and custom BacktestEngine results for consistency validation.

Usage:
    from cli.utils.engine_comparator import EngineComparator
    from modules.backtesting.backtest_config import BacktestConfig
    from datetime import date

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        regions=['KR'],
        tickers=['005930'],
        initial_capital=100_000_000
    )

    comparator = EngineComparator(config, data_provider)
    results = comparator.compare_engines()

    print(f"Total return difference: {results['total_return_diff']:.2%}")
    print(f"Final value match: {results['final_value_match']}")
"""

from typing import Dict, Any, Optional
import pandas as pd
import logging

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engine import BacktestEngine
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class EngineComparator:
    """
    Compare vectorbt and custom BacktestEngine results for consistency validation.

    Attributes:
        config: Backtest configuration
        data_provider: Data provider for both engines
        vectorbt_available: Whether vectorbt is installed
    """

    def __init__(self, config: BacktestConfig, data_provider: BaseDataProvider):
        """
        Initialize engine comparator.

        Args:
            config: Backtest configuration
            data_provider: Data provider implementing BaseDataProvider interface
        """
        self.config = config
        self.data_provider = data_provider

        # Check vectorbt availability
        try:
            from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
            self.vectorbt_available = VECTORBT_AVAILABLE
            self.VectorbtAdapter = VectorbtAdapter
        except ImportError:
            self.vectorbt_available = False
            self.VectorbtAdapter = None
            logger.warning("vectorbt not available - comparison functionality limited")

    def compare_engines(
        self,
        tolerance: float = 0.02,
        signal_agreement_threshold: float = 0.95
    ) -> Dict[str, Any]:
        """
        Compare vectorbt and custom engine results.

        Args:
            tolerance: Acceptable difference for metrics (0.02 = 2%)
            signal_agreement_threshold: Minimum signal agreement ratio (0.95 = 95%)

        Returns:
            Dictionary with comparison results:
                - vectorbt_result: vectorbt BacktestResult object
                - custom_result: custom BacktestResult object
                - total_return_diff: Absolute difference in total returns
                - final_value_diff: Absolute difference in final portfolio values
                - final_value_match: Whether final values match within tolerance
                - sharpe_ratio_diff: Absolute difference in Sharpe ratios
                - max_drawdown_diff: Absolute difference in max drawdowns
                - signal_agreement: Percentage of matching trade signals
                - metrics_match: Whether all key metrics match within tolerance
                - comparison_summary: Human-readable summary string

        Raises:
            RuntimeError: If vectorbt not available
            ValueError: If comparison fails due to data inconsistency
        """
        if not self.vectorbt_available:
            raise RuntimeError("vectorbt not available - cannot compare engines")

        logger.info("Starting engine comparison...")

        # Run vectorbt backtest
        logger.info("Running vectorbt backtest...")
        vectorbt_adapter = self.VectorbtAdapter(
            config=self.config,
            data_provider=self.data_provider
        )
        vectorbt_result = vectorbt_adapter.run()

        # Run custom engine backtest
        logger.info("Running custom engine backtest...")
        custom_engine = BacktestEngine(
            config=self.config,
            data_provider=self.data_provider
        )

        # Check if custom engine initialized properly
        if custom_engine.strategy_runner is None:
            raise RuntimeError(
                "Custom BacktestEngine requires SQLite database for StrategyRunner. "
                "Engine comparison not available with PostgresDataProvider only. "
                "This is a known limitation (see modules/backtesting/backtest_engine.py:118-134)"
            )

        custom_result = custom_engine.run()

        # Compare total returns
        vectorbt_total_return = vectorbt_result.total_return
        custom_total_return = custom_result.metrics.total_return
        total_return_diff = abs(vectorbt_total_return - custom_total_return)

        # Compare final portfolio values
        vectorbt_final_value = vectorbt_result.equity_curve.iloc[-1]
        custom_final_value = custom_result.final_portfolio_value
        final_value_diff = abs(vectorbt_final_value - custom_final_value)
        final_value_diff_pct = final_value_diff / vectorbt_final_value
        final_value_match = final_value_diff_pct <= tolerance

        # Compare Sharpe ratios
        sharpe_ratio_diff = abs(vectorbt_result.sharpe_ratio - custom_result.metrics.sharpe_ratio)

        # Compare max drawdowns
        max_drawdown_diff = abs(vectorbt_result.max_drawdown - custom_result.metrics.max_drawdown)

        # Compare trade signals (simplified - compare number of trades)
        # Note: Exact signal matching would require access to raw signals, which vectorbt doesn't expose
        vectorbt_trade_count = vectorbt_result.total_trades
        custom_trade_count = len([t for t in custom_result.trades if t.is_closed])

        # Signal agreement approximation based on trade count similarity
        if vectorbt_trade_count > 0:
            trade_count_ratio = min(vectorbt_trade_count, custom_trade_count) / max(vectorbt_trade_count, custom_trade_count)
            signal_agreement = trade_count_ratio  # Approximation
        else:
            signal_agreement = 1.0 if custom_trade_count == 0 else 0.0

        # Overall metrics match
        metrics_match = (
            total_return_diff <= tolerance and
            final_value_match and
            sharpe_ratio_diff <= 0.1 and  # Sharpe can vary more due to calculation differences
            max_drawdown_diff <= tolerance and
            signal_agreement >= signal_agreement_threshold
        )

        # Generate summary
        summary_lines = [
            f"Engine Comparison Results:",
            f"  Total Return: vectorbt={vectorbt_total_return:.2%}, custom={custom_total_return:.2%}, diff={total_return_diff:.2%}",
            f"  Final Value: vectorbt={vectorbt_final_value:,.0f}, custom={custom_final_value:,.0f}, diff={final_value_diff:,.0f} ({final_value_diff_pct:.2%})",
            f"  Sharpe Ratio: vectorbt={vectorbt_result.sharpe_ratio:.2f}, custom={custom_result.metrics.sharpe_ratio:.2f}, diff={sharpe_ratio_diff:.2f}",
            f"  Max Drawdown: vectorbt={vectorbt_result.max_drawdown:.2%}, custom={custom_result.metrics.max_drawdown:.2%}, diff={max_drawdown_diff:.2%}",
            f"  Trade Count: vectorbt={vectorbt_trade_count}, custom={custom_trade_count}, agreement={signal_agreement:.1%}",
            f"  Metrics Match: {'✅ PASS' if metrics_match else '❌ FAIL'}",
            f"  Tolerance: {tolerance:.1%}, Signal Agreement Threshold: {signal_agreement_threshold:.1%}"
        ]
        comparison_summary = "\n".join(summary_lines)

        logger.info(f"\n{comparison_summary}")

        return {
            'vectorbt_result': vectorbt_result,
            'custom_result': custom_result,
            'total_return_diff': total_return_diff,
            'final_value_diff': final_value_diff,
            'final_value_diff_pct': final_value_diff_pct,
            'final_value_match': final_value_match,
            'sharpe_ratio_diff': sharpe_ratio_diff,
            'max_drawdown_diff': max_drawdown_diff,
            'signal_agreement': signal_agreement,
            'vectorbt_trade_count': vectorbt_trade_count,
            'custom_trade_count': custom_trade_count,
            'metrics_match': metrics_match,
            'comparison_summary': comparison_summary,
            'tolerance': tolerance,
            'signal_agreement_threshold': signal_agreement_threshold
        }

    def get_equity_curve_comparison(self) -> Optional[pd.DataFrame]:
        """
        Get side-by-side equity curve comparison.

        Returns:
            DataFrame with columns ['vectorbt', 'custom', 'diff', 'diff_pct']
            or None if engines not run yet
        """
        if not hasattr(self, '_vectorbt_result') or not hasattr(self, '_custom_result'):
            logger.warning("Engines not run yet - call compare_engines() first")
            return None

        # Align equity curves by date
        vectorbt_curve = self._vectorbt_result.equity_curve
        custom_curve = self._custom_result.equity_curve

        comparison = pd.DataFrame({
            'vectorbt': vectorbt_curve,
            'custom': custom_curve
        })

        comparison['diff'] = comparison['vectorbt'] - comparison['custom']
        comparison['diff_pct'] = comparison['diff'] / comparison['vectorbt']

        return comparison
