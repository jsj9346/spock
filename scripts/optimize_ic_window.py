#!/usr/bin/env python3
"""
IC Window Optimizer - Phase 1.2 of Monthly Rebalancing Troubleshooting

Optimizes IC rolling window size to maximize signal stability (autocorrelation)
for specific factors and rebalancing frequencies.

Phase 1.2 Focus: RSI_Momentum at monthly frequency
Goal: Find IC window where autocorr ≥ 0.5 for robust monthly momentum strategy

Context from Phase 1.1:
- RSI_Momentum at 60-day window: autocorr = +0.469 (MODERATE, almost stable)
- RSI_Momentum at 252-day window: autocorr = +0.100 (UNSTABLE)
- Hypothesis: Optimal window is 45-75 days for monthly momentum

Approach:
1. Test extended window range (30, 45, 60, 75, 90, 120, 150 days)
2. Calculate IC autocorrelation for each window
3. Identify windows where autocorr ≥ 0.5 (stable signal)
4. Backtest single-factor strategy with optimal windows
5. Generate recommendation: Proceed with monthly momentum OR abandon

Author: Spock Quant Platform Team
Date: 2025-10-26
"""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple
import argparse
import logging

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import matplotlib.pyplot as plt
import seaborn as sns

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.ic_calculator import RollingICCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ICWindowOptimizer:
    """
    Optimize IC rolling window for maximum signal stability

    Key Metric: IC Autocorrelation (lag-1)
    - autocorr ≥ 0.5 → Stable signal, suitable for monthly rebalancing
    - autocorr 0.3-0.5 → Moderate stability, use with caution
    - autocorr < 0.3 → Unstable signal, avoid monthly rebalancing
    """

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        factor: str,
        frequency: str,
        start_date: str,
        end_date: str,
        region: str = 'KR',
        holding_period: int = 21,
        min_stocks: int = 10
    ):
        """
        Initialize IC Window Optimizer

        Args:
            db_manager: PostgreSQL database manager
            factor: Factor name to optimize (e.g., 'RSI_Momentum')
            frequency: Rebalancing frequency ('M' for monthly, 'Q' for quarterly)
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)
            region: Market region (default: KR)
            holding_period: Forward return calculation period in days
            min_stocks: Minimum stocks required for IC calculation
        """
        self.db = db_manager
        self.factor = factor
        self.frequency = frequency
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.region = region
        self.holding_period = holding_period
        self.min_stocks = min_stocks

        # Optimization results storage
        self.window_results = {}  # {window: {metrics}}
        self.optimal_windows = []  # [(window, autocorr), ...] sorted by autocorr

        logger.info(f"📊 IC Window Optimizer Initialized")
        logger.info(f"   Factor: {factor}")
        logger.info(f"   Frequency: {frequency}")
        logger.info(f"   Date Range: {start_date} to {end_date}")
        logger.info(f"   Region: {region}, Holding Period: {holding_period} days")

    def _get_sampling_dates(self) -> List[date]:
        """
        Generate analysis dates based on frequency

        Returns:
            List of dates to calculate IC
        """
        dates = []
        current = self.start_date

        if self.frequency == 'M':
            # Monthly: last trading day of each month
            while current <= self.end_date:
                next_day = current + timedelta(days=1)
                if next_day.month != current.month or next_day > self.end_date:
                    dates.append(current)
                current += timedelta(days=1)

        elif self.frequency == 'Q':
            # Quarterly: last trading day of quarter
            while current <= self.end_date:
                if current.month in [3, 6, 9, 12]:
                    next_day = current + timedelta(days=1)
                    if next_day.month != current.month or next_day > self.end_date:
                        dates.append(current)
                current += timedelta(days=1)

        return dates

    def _calculate_ic_timeseries(self, window_days: int) -> pd.DataFrame:
        """
        Calculate IC time-series for specific window

        Args:
            window_days: Rolling window size

        Returns:
            DataFrame with columns: date, ic, p_value, num_stocks
        """
        # Initialize IC calculator
        ic_calc = RollingICCalculator(
            db_manager=self.db,
            window_days=window_days,
            holding_period=self.holding_period,
            region=self.region,
            min_stocks=self.min_stocks
        )

        # Get sampling dates
        analysis_dates = self._get_sampling_dates()

        # Filter dates with sufficient lookback
        min_ic_date = self.start_date + timedelta(days=window_days)
        valid_dates = [d for d in analysis_dates if d >= min_ic_date]

        if not valid_dates:
            return pd.DataFrame()

        # Calculate IC for each date
        ic_data = []
        for calc_date in valid_dates:
            ic_result = ic_calc.calculate_factor_ic(self.factor, calc_date)

            if ic_result['num_stocks'] >= self.min_stocks:
                ic_data.append({
                    'date': calc_date,
                    'ic': ic_result['ic'],
                    'p_value': ic_result['p_value'],
                    'num_stocks': ic_result['num_stocks']
                })

        return pd.DataFrame(ic_data)

    def _calculate_autocorrelation(self, ic_series: pd.Series, max_lag: int = 6) -> Dict[int, float]:
        """
        Calculate autocorrelation of IC series

        Args:
            ic_series: Pandas Series of IC values
            max_lag: Maximum lag to calculate

        Returns:
            Dictionary {lag: autocorr_coefficient}
        """
        if len(ic_series) < 3:
            return {}

        autocorr = {}
        for lag in range(1, min(max_lag + 1, len(ic_series))):
            corr = ic_series.autocorr(lag=lag)
            autocorr[lag] = float(corr) if not np.isnan(corr) else 0.0

        return autocorr

    def _calculate_stability_metrics(self, ic_series: pd.Series) -> Dict[str, float]:
        """
        Calculate stability metrics for IC series

        Args:
            ic_series: Pandas Series of IC values

        Returns:
            Dictionary of stability metrics
        """
        if ic_series.empty or len(ic_series) < 2:
            return {
                'mean_ic': 0.0,
                'std_ic': 0.0,
                'mean_abs_ic': 0.0,
                'volatility': 0.0,
                'num_observations': 0
            }

        mean_ic = ic_series.mean()
        std_ic = ic_series.std()
        volatility = abs(std_ic / mean_ic) if mean_ic != 0 else np.inf

        return {
            'mean_ic': float(mean_ic),
            'std_ic': float(std_ic),
            'mean_abs_ic': float(ic_series.abs().mean()),
            'volatility': float(volatility),
            'num_observations': len(ic_series)
        }

    def test_window_range(
        self,
        window_range: List[int] = [30, 45, 60, 75, 90, 120, 150]
    ):
        """
        Test IC stability across window range

        Args:
            window_range: List of IC window sizes to test (days)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔬 TESTING IC WINDOW OPTIMIZATION")
        logger.info(f"{'='*80}")
        logger.info(f"Factor: {self.factor}")
        logger.info(f"Frequency: {self.frequency}")
        logger.info(f"Window Range: {window_range}")
        logger.info(f"Total Windows to Test: {len(window_range)}")

        for window in window_range:
            logger.info(f"\n📊 Testing Window: {window} days")
            logger.info(f"{'─'*80}")

            # Calculate IC time-series
            ic_df = self._calculate_ic_timeseries(window)

            if ic_df.empty:
                logger.warning(f"   ❌ No IC data for window={window}")
                continue

            # Calculate autocorrelation
            ic_series = ic_df.set_index('date')['ic']
            autocorr = self._calculate_autocorrelation(ic_series)

            # Calculate stability metrics
            stability = self._calculate_stability_metrics(ic_series)

            # Store results
            self.window_results[window] = {
                'ic_timeseries': ic_df,
                'autocorr': autocorr,
                'stability': stability,
                'autocorr_lag1': autocorr.get(1, 0.0),
                'autocorr_lag3': autocorr.get(3, 0.0),
                'autocorr_lag6': autocorr.get(6, 0.0)
            }

            # Log summary
            logger.info(
                f"   Window {window:3d}d: "
                f"IC={stability['mean_ic']:+.4f} ± {stability['std_ic']:.4f}, "
                f"Autocorr(1)={autocorr.get(1, 0.0):+.3f}, "
                f"Autocorr(3)={autocorr.get(3, 0.0):+.3f}, "
                f"n={len(ic_df)}"
            )

        # Sort windows by autocorr(1) descending
        self.optimal_windows = sorted(
            [(w, r['autocorr_lag1']) for w, r in self.window_results.items()],
            key=lambda x: x[1],
            reverse=True
        )

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ WINDOW TESTING COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total Windows Tested: {len(self.window_results)}")

        logger.info(f"\n📊 Top 5 Windows by Autocorrelation:")
        for i, (window, autocorr) in enumerate(self.optimal_windows[:5], 1):
            stability = self.window_results[window]['stability']
            status = "✅ STABLE" if autocorr >= 0.5 else ("⚠️ MODERATE" if autocorr >= 0.3 else "❌ UNSTABLE")
            logger.info(
                f"   {i}. Window {window:3d}d: Autocorr={autocorr:+.3f}, "
                f"IC={stability['mean_ic']:+.4f}, n={stability['num_observations']} {status}"
            )

    def visualize_optimization_curve(self, output_dir: str, timestamp: str):
        """
        Create optimization curve visualization

        Args:
            output_dir: Directory to save plots
            timestamp: Timestamp for file naming
        """
        output_path = Path(output_dir) / 'plots'
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"\n📊 Creating Optimization Curve")

        # Prepare data
        windows = sorted(self.window_results.keys())
        autocorr_lag1 = [self.window_results[w]['autocorr_lag1'] for w in windows]
        autocorr_lag3 = [self.window_results[w]['autocorr_lag3'] for w in windows]
        mean_ics = [self.window_results[w]['stability']['mean_ic'] for w in windows]

        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Plot 1: Autocorrelation vs Window Size
        ax1.plot(windows, autocorr_lag1, 'o-', linewidth=2, markersize=8, label='Autocorr Lag-1', color='blue')
        ax1.plot(windows, autocorr_lag3, 's--', linewidth=1.5, markersize=6, label='Autocorr Lag-3', color='green', alpha=0.7)
        ax1.axhline(y=0.5, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Stable Threshold (≥0.5)')
        ax1.axhline(y=0.3, color='orange', linestyle='--', linewidth=1.5, alpha=0.5, label='Moderate Threshold (≥0.3)')
        ax1.axhline(y=0.0, color='red', linestyle='-', linewidth=1, alpha=0.3, label='Neutral (0.0)')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlabel('IC Window (days)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Autocorrelation', fontsize=12, fontweight='bold')
        ax1.set_title(f'IC Autocorrelation vs Window Size - {self.factor} ({self.frequency} frequency)',
                      fontsize=14, fontweight='bold')
        ax1.legend(loc='best', fontsize=10)

        # Highlight optimal window
        if self.optimal_windows:
            opt_window, opt_autocorr = self.optimal_windows[0]
            ax1.scatter([opt_window], [opt_autocorr], s=200, c='red', marker='*',
                       edgecolors='black', linewidths=2, zorder=5, label=f'Optimal: {opt_window}d')
            ax1.legend(loc='best', fontsize=10)

        # Plot 2: Mean IC vs Window Size
        ax2.plot(windows, mean_ics, 'o-', linewidth=2, markersize=8, color='purple')
        ax2.axhline(y=0.0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        ax2.grid(True, alpha=0.3)
        ax2.set_xlabel('IC Window (days)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Mean IC', fontsize=12, fontweight='bold')
        ax2.set_title(f'Mean IC vs Window Size - {self.factor}', fontsize=14, fontweight='bold')

        plt.tight_layout()
        plot_file = output_path / f'ic_autocorr_vs_window_{self.factor}_{timestamp}.png'
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        plt.close()

        logger.info(f"   ✅ Saved optimization curve: {plot_file.name}")

    def save_results(self, output_dir: str) -> str:
        """
        Save optimization results to CSV files

        Args:
            output_dir: Directory to save results

        Returns:
            Timestamp string for file naming
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        logger.info(f"\n💾 Saving Optimization Results to {output_dir}")

        # Save optimization summary
        summary_records = []
        for window in sorted(self.window_results.keys()):
            result = self.window_results[window]
            record = {
                'factor': self.factor,
                'frequency': self.frequency,
                'window_days': window,
                'mean_ic': result['stability']['mean_ic'],
                'std_ic': result['stability']['std_ic'],
                'mean_abs_ic': result['stability']['mean_abs_ic'],
                'volatility': result['stability']['volatility'],
                'autocorr_lag1': result['autocorr_lag1'],
                'autocorr_lag3': result['autocorr_lag3'],
                'autocorr_lag6': result['autocorr_lag6'],
                'num_observations': result['stability']['num_observations']
            }
            summary_records.append(record)

        if summary_records:
            summary_df = pd.DataFrame(summary_records)
            summary_file = output_path / f'ic_window_optimization_{timestamp}.csv'
            summary_df.to_csv(summary_file, index=False)
            logger.info(f"   ✅ Saved optimization summary: {summary_file.name}")

        # Save IC time-series for top 3 windows
        timeseries_records = []
        for window, _ in self.optimal_windows[:3]:
            ic_df = self.window_results[window]['ic_timeseries']
            for _, row in ic_df.iterrows():
                timeseries_records.append({
                    'factor': self.factor,
                    'frequency': self.frequency,
                    'window_days': window,
                    'date': row['date'],
                    'ic': row['ic'],
                    'p_value': row['p_value'],
                    'num_stocks': row['num_stocks']
                })

        if timeseries_records:
            timeseries_df = pd.DataFrame(timeseries_records)
            timeseries_file = output_path / f'ic_window_optimization_timeseries_{timestamp}.csv'
            timeseries_df.to_csv(timeseries_file, index=False)
            logger.info(f"   ✅ Saved IC time-series (top 3 windows): {timeseries_file.name}")

        return timestamp

    def generate_report(self, output_dir: str, timestamp: str):
        """
        Generate comprehensive markdown report

        Args:
            output_dir: Directory to save report
            timestamp: Timestamp for file naming
        """
        output_path = Path(output_dir)
        report_file = output_path / f'ic_window_optimization_report_{timestamp}.md'

        logger.info(f"\n📝 Generating Report: {report_file.name}")

        with open(report_file, 'w') as f:
            f.write(f"# IC Window Optimization Report\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Factor**: {self.factor}\n")
            f.write(f"**Rebalancing Frequency**: {self.frequency}\n")
            f.write(f"**Analysis Period**: {self.start_date} to {self.end_date}\n")
            f.write(f"**Region**: {self.region}\n")
            f.write(f"**Holding Period**: {self.holding_period} days\n\n")

            f.write(f"---\n\n")
            f.write(f"## Executive Summary\n\n")

            if not self.optimal_windows:
                f.write(f"❌ **NO RESULTS**: No IC data available for optimization.\n\n")
                return

            # Best window analysis
            best_window, best_autocorr = self.optimal_windows[0]
            best_result = self.window_results[best_window]
            best_stability = best_result['stability']

            if best_autocorr >= 0.5:
                f.write(f"✅ **SUCCESS**: Optimal IC window found!\n\n")
                f.write(f"**Optimal Window**: {best_window} days\n")
                f.write(f"**Autocorrelation (lag-1)**: {best_autocorr:+.3f} (≥0.5 → STABLE)\n")
                f.write(f"**Mean IC**: {best_stability['mean_ic']:+.4f}\n")
                f.write(f"**Std IC**: {best_stability['std_ic']:.4f}\n")
                f.write(f"**Observations**: {best_stability['num_observations']}\n\n")

                f.write(f"**Recommendation**: ✅ Proceed to Phase 1.3 - Backtest pure {self.factor} strategy at monthly frequency with {best_window}-day IC window.\n\n")

            elif best_autocorr >= 0.3:
                f.write(f"⚠️ **CONDITIONAL**: Moderate stability found.\n\n")
                f.write(f"**Best Window**: {best_window} days\n")
                f.write(f"**Autocorrelation (lag-1)**: {best_autocorr:+.3f} (0.3-0.5 → MODERATE)\n")
                f.write(f"**Mean IC**: {best_stability['mean_ic']:+.4f}\n")
                f.write(f"**Std IC**: {best_stability['std_ic']:.4f}\n")
                f.write(f"**Observations**: {best_stability['num_observations']}\n\n")

                f.write(f"**Recommendation**: ⚠️ Monthly {self.factor} strategy may work but with caution. Consider quarterly frequency as safer alternative. Proceed to Phase 1.3 for validation backtest.\n\n")

            else:
                f.write(f"❌ **FAILURE**: No optimal IC window found.\n\n")
                f.write(f"**Best Window**: {best_window} days\n")
                f.write(f"**Autocorrelation (lag-1)**: {best_autocorr:+.3f} (<0.3 → UNSTABLE)\n")
                f.write(f"**Mean IC**: {best_stability['mean_ic']:+.4f}\n\n")

                f.write(f"**Recommendation**: ❌ Abandon monthly rebalancing for {self.factor}. IC signal is fundamentally unstable at monthly frequency regardless of window size. Proceed to Phase 2: Optimize quarterly strategy instead.\n\n")

            f.write(f"---\n\n")
            f.write(f"## Detailed Results\n\n")

            # Optimization summary table
            f.write(f"### IC Window Optimization Summary\n\n")
            f.write(f"| Window (days) | Mean IC | Std IC | Autocorr(1) | Autocorr(3) | Autocorr(6) | n | Status |\n")
            f.write(f"|---------------|---------|--------|-------------|-------------|-------------|---|---------|\n")

            for window in sorted(self.window_results.keys()):
                result = self.window_results[window]
                stability = result['stability']
                autocorr1 = result['autocorr_lag1']
                autocorr3 = result['autocorr_lag3']
                autocorr6 = result['autocorr_lag6']

                status = "✅ Stable" if autocorr1 >= 0.5 else ("⚠️ Moderate" if autocorr1 >= 0.3 else "❌ Unstable")

                f.write(
                    f"| {window} | {stability['mean_ic']:+.4f} | {stability['std_ic']:.4f} | "
                    f"{autocorr1:+.3f} | {autocorr3:+.3f} | {autocorr6:+.3f} | "
                    f"{stability['num_observations']} | {status} |\n"
                )

            f.write(f"\n### Top 5 Windows by Autocorrelation\n\n")
            f.write(f"| Rank | Window | Autocorr(1) | Mean IC | Status |\n")
            f.write(f"|------|--------|-------------|---------|--------|\n")

            for i, (window, autocorr) in enumerate(self.optimal_windows[:5], 1):
                stability = self.window_results[window]['stability']
                status = "✅ Stable" if autocorr >= 0.5 else ("⚠️ Moderate" if autocorr >= 0.3 else "❌ Unstable")
                f.write(f"| {i} | {window} days | {autocorr:+.3f} | {stability['mean_ic']:+.4f} | {status} |\n")

            f.write(f"\n---\n\n")
            f.write(f"## Key Findings\n\n")

            # Analyze autocorr pattern
            stable_windows = [w for w, a in self.optimal_windows if a >= 0.5]
            moderate_windows = [w for w, a in self.optimal_windows if 0.3 <= a < 0.5]
            unstable_windows = [w for w, a in self.optimal_windows if a < 0.3]

            f.write(f"### Autocorrelation Distribution\n\n")
            f.write(f"- **Stable Windows** (autocorr ≥ 0.5): {len(stable_windows)} windows\n")
            if stable_windows:
                f.write(f"  - Windows: {', '.join(map(str, stable_windows))} days\n")
            f.write(f"- **Moderate Windows** (autocorr 0.3-0.5): {len(moderate_windows)} windows\n")
            if moderate_windows:
                f.write(f"  - Windows: {', '.join(map(str, moderate_windows))} days\n")
            f.write(f"- **Unstable Windows** (autocorr < 0.3): {len(unstable_windows)} windows\n\n")

            # Pattern analysis
            if stable_windows:
                f.write(f"### Optimal Window Range\n\n")
                f.write(f"**Range**: {min(stable_windows)}-{max(stable_windows)} days\n")
                f.write(f"**Sweet Spot**: ~{best_window} days (highest autocorr)\n\n")
                f.write(f"**Interpretation**: {self.factor} IC signal is most stable with {best_window}-day rolling window at monthly frequency.\n\n")

            f.write(f"---\n\n")
            f.write(f"## Next Steps\n\n")

            if best_autocorr >= 0.5:
                f.write(f"### Phase 1.3: Backtest Validation (HIGH PRIORITY)\n\n")
                f.write(f"**Objective**: Validate that optimal IC window ({best_window} days) produces positive returns at monthly frequency.\n\n")
                f.write(f"**Test Plan**:\n")
                f.write(f"1. Run single-factor backtest: {self.factor} only\n")
                f.write(f"2. IC window: {best_window} days (optimized)\n")
                f.write(f"3. Rebalancing frequency: Monthly\n")
                f.write(f"4. Period: 2023-01-02 to 2024-01-02 (same as failed IC-weighted multi-factor)\n")
                f.write(f"5. Compare: Optimized momentum vs -87.66% baseline\n\n")

                f.write(f"**Expected Outcome**:\n")
                f.write(f"- If backtest return > 0% → Monthly momentum strategy VIABLE\n")
                f.write(f"- If backtest return < 0% but > -20% → Proceed with caution, consider quarterly\n")
                f.write(f"- If backtest return < -20% → Abandon monthly, even with stable IC\n\n")

                f.write(f"**Script**: `scripts/backtest_single_factor.py --factor {self.factor} --ic-window {best_window} --frequency M`\n\n")

            elif best_autocorr >= 0.3:
                f.write(f"### Phase 1.3: Conditional Backtest (MEDIUM PRIORITY)\n\n")
                f.write(f"Autocorr is moderate ({best_autocorr:+.3f}). Proceed to backtest validation but be prepared for mixed results.\n\n")
                f.write(f"**Alternative**: Skip to Phase 2 (Quarterly Strategy Optimization) if risk tolerance is low.\n\n")

            else:
                f.write(f"### Abandon Monthly Rebalancing (RECOMMENDED)\n\n")
                f.write(f"**Finding**: No IC window achieves stable signal (autocorr < 0.3 for all tested windows).\n\n")
                f.write(f"**Implication**: {self.factor} is fundamentally unsuitable for monthly rebalancing, regardless of IC window optimization.\n\n")
                f.write(f"**Recommendation**: Proceed to Phase 2 - Focus on optimizing quarterly rebalancing strategy (+3.48% baseline return).\n\n")

            f.write(f"---\n\n")
            f.write(f"## Appendix\n\n")

            f.write(f"### Optimization Configuration\n\n")
            f.write(f"```yaml\n")
            f.write(f"factor: {self.factor}\n")
            f.write(f"frequency: {self.frequency}\n")
            f.write(f"windows_tested: {sorted(self.window_results.keys())}\n")
            f.write(f"holding_period: {self.holding_period}\n")
            f.write(f"min_stocks: {self.min_stocks}\n")
            f.write(f"region: {self.region}\n")
            f.write(f"date_range: {self.start_date} to {self.end_date}\n")
            f.write(f"```\n\n")

            f.write(f"### Output Files\n\n")
            f.write(f"- `ic_window_optimization_{timestamp}.csv` - Optimization summary\n")
            f.write(f"- `ic_window_optimization_timeseries_{timestamp}.csv` - IC time-series for top 3 windows\n")
            f.write(f"- `plots/ic_autocorr_vs_window_{self.factor}_{timestamp}.png` - Optimization curve\n")
            f.write(f"- `ic_window_optimization_report_{timestamp}.md` - This report\n\n")

            f.write(f"---\n\n")
            f.write(f"**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Spock Quant Platform** - Phase 1.2 IC Window Optimization\n")

        logger.info(f"   ✅ Report saved: {report_file.name}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='IC Window Optimizer - Phase 1.2 of Monthly Rebalancing Troubleshooting'
    )

    parser.add_argument(
        '--factor',
        default='RSI_Momentum',
        help='Factor name to optimize (default: RSI_Momentum)'
    )

    parser.add_argument(
        '--frequency',
        default='M',
        choices=['M', 'Q'],
        help='Rebalancing frequency (M=monthly, Q=quarterly, default: M)'
    )

    parser.add_argument(
        '--start-date',
        default='2022-01-01',
        help='Analysis start date (YYYY-MM-DD, default: 2022-01-01)'
    )

    parser.add_argument(
        '--end-date',
        default='2025-01-02',
        help='Analysis end date (YYYY-MM-DD, default: 2025-01-02)'
    )

    parser.add_argument(
        '--region',
        default='KR',
        help='Market region (default: KR)'
    )

    parser.add_argument(
        '--holding-period',
        type=int,
        default=21,
        help='Forward return period in days (default: 21)'
    )

    parser.add_argument(
        '--output-dir',
        default='analysis',
        help='Output directory for results (default: analysis)'
    )

    parser.add_argument(
        '--windows',
        nargs='+',
        type=int,
        default=[30, 45, 60, 75, 90, 120, 150],
        help='IC windows to test in days (default: 30 45 60 75 90 120 150)'
    )

    args = parser.parse_args()

    # Initialize database
    logger.info(f"🔌 Connecting to PostgreSQL database...")
    db = PostgresDatabaseManager()

    # Initialize optimizer
    optimizer = ICWindowOptimizer(
        db_manager=db,
        factor=args.factor,
        frequency=args.frequency,
        start_date=args.start_date,
        end_date=args.end_date,
        region=args.region,
        holding_period=args.holding_period
    )

    # Run optimization
    optimizer.test_window_range(window_range=args.windows)

    # Save results
    timestamp = optimizer.save_results(args.output_dir)

    # Create visualizations
    optimizer.visualize_optimization_curve(args.output_dir, timestamp)

    # Generate report
    optimizer.generate_report(args.output_dir, timestamp)

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ IC WINDOW OPTIMIZATION COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Results saved to: {args.output_dir}/")
    logger.info(f"Review report: ic_window_optimization_report_{timestamp}.md")


if __name__ == '__main__':
    main()
