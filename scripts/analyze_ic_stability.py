#!/usr/bin/env python3
"""
IC Stability Analyzer - Phase 1.1 of Monthly Rebalancing Troubleshooting

Analyzes Information Coefficient (IC) stability across different rebalancing frequencies
to diagnose why monthly rebalancing causes catastrophic losses (-87.66%) while quarterly
rebalancing produces positive returns (+7.11%).

Core Hypothesis (H1): IC becomes unstable and noisy at monthly frequency, causing:
1. Overfitting to short-term noise
2. Whipsaw trading (entering/exiting at worst times)
3. Signal decay faster than monthly intervals

Analysis Approach:
- Calculate IC time-series at Daily, Weekly, Monthly, Quarterly frequencies
- Test multiple IC rolling windows (60, 126, 252, 504 days)
- Measure IC autocorrelation (persistence of signal quality)
- Identify unstable factors and optimal rebalancing frequencies

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


class ICStabilityAnalyzer:
    """
    Analyzes Information Coefficient stability across frequencies and windows

    Key Metrics:
    - IC Autocorrelation: Measures signal persistence (target: >0.5 for stable)
    - IC Volatility: Std/Mean ratio (lower = more stable)
    - Sign Change Rate: % of IC sign flips between periods
    - Mean Absolute IC: Average predictive power
    """

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        factors: List[str],
        start_date: str,
        end_date: str,
        region: str = 'KR',
        holding_period: int = 21,
        min_stocks: int = 10
    ):
        """
        Initialize IC Stability Analyzer

        Args:
            db_manager: PostgreSQL database manager
            factors: List of factor names to analyze
            start_date: Analysis start date (YYYY-MM-DD)
            end_date: Analysis end date (YYYY-MM-DD)
            region: Market region (default: KR)
            holding_period: Forward return calculation period in days
            min_stocks: Minimum stocks required for IC calculation
        """
        self.db = db_manager
        self.factors = factors
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.region = region
        self.holding_period = holding_period
        self.min_stocks = min_stocks

        # Analysis results storage
        self.ic_timeseries_results = {}  # {(factor, freq, window): DataFrame}
        self.autocorr_results = {}       # {(factor, freq, window): Dict[lag, corr]}
        self.stability_metrics = {}      # {(factor, freq, window): Dict[metric, value]}

        logger.info(f"📊 IC Stability Analyzer Initialized")
        logger.info(f"   Factors: {', '.join(factors)}")
        logger.info(f"   Date Range: {start_date} to {end_date}")
        logger.info(f"   Region: {region}, Holding Period: {holding_period} days")

    def _get_sampling_dates(self, frequency: str) -> List[date]:
        """
        Generate analysis dates based on frequency

        Args:
            frequency: 'D' (daily), 'W' (weekly), 'M' (monthly), 'Q' (quarterly)

        Returns:
            List of dates to calculate IC
        """
        dates = []
        current = self.start_date

        if frequency == 'D':
            # Daily: every trading day
            while current <= self.end_date:
                dates.append(current)
                current += timedelta(days=1)

        elif frequency == 'W':
            # Weekly: every Friday (or last trading day of week)
            while current <= self.end_date:
                if current.weekday() == 4:  # Friday
                    dates.append(current)
                current += timedelta(days=1)

        elif frequency == 'M':
            # Monthly: last trading day of each month
            while current <= self.end_date:
                # Check if next day is a different month
                next_day = current + timedelta(days=1)
                if next_day.month != current.month or next_day > self.end_date:
                    dates.append(current)
                current += timedelta(days=1)

        elif frequency == 'Q':
            # Quarterly: last trading day of quarter (Mar, Jun, Sep, Dec)
            while current <= self.end_date:
                if current.month in [3, 6, 9, 12]:
                    next_day = current + timedelta(days=1)
                    if next_day.month != current.month or next_day > self.end_date:
                        dates.append(current)
                current += timedelta(days=1)

        return dates

    def calculate_ic_timeseries(
        self,
        factor: str,
        frequency: str,
        window_days: int
    ) -> pd.DataFrame:
        """
        Calculate IC time-series for a factor at specified frequency and window

        Args:
            factor: Factor name
            frequency: 'D', 'W', 'M', 'Q'
            window_days: Rolling window size (60, 126, 252, 504)

        Returns:
            DataFrame with columns: date, ic, p_value, num_stocks, is_significant
        """
        logger.info(f"   Calculating IC for {factor} at {frequency} frequency (window={window_days})")

        # Initialize IC calculator with specified window
        ic_calc = RollingICCalculator(
            db_manager=self.db,
            window_days=window_days,
            holding_period=self.holding_period,
            region=self.region,
            min_stocks=self.min_stocks
        )

        # Get sampling dates for this frequency
        analysis_dates = self._get_sampling_dates(frequency)

        # Filter dates that have sufficient lookback for IC calculation
        min_ic_date = self.start_date + timedelta(days=window_days)
        valid_dates = [d for d in analysis_dates if d >= min_ic_date]

        if not valid_dates:
            logger.warning(f"   No valid dates for {factor} at {frequency} (window={window_days})")
            return pd.DataFrame()

        # Calculate IC for each date
        ic_data = []
        for calc_date in valid_dates:
            ic_result = ic_calc.calculate_factor_ic(factor, calc_date)

            if ic_result['num_stocks'] >= self.min_stocks:
                ic_data.append({
                    'date': calc_date,
                    'ic': ic_result['ic'],
                    'p_value': ic_result['p_value'],
                    'num_stocks': ic_result['num_stocks'],
                    'is_significant': ic_result['is_significant']
                })

        df = pd.DataFrame(ic_data)

        if not df.empty:
            logger.info(f"   ✅ Calculated {len(df)} IC values from {df['date'].min()} to {df['date'].max()}")
        else:
            logger.warning(f"   ❌ No IC data for {factor} at {frequency}")

        return df

    def calculate_autocorrelation(
        self,
        ic_series: pd.Series,
        max_lag: int = 12
    ) -> Dict[int, float]:
        """
        Calculate autocorrelation of IC series

        Args:
            ic_series: Pandas Series of IC values
            max_lag: Maximum lag to calculate (default: 12)

        Returns:
            Dictionary {lag: autocorrelation_coefficient}
        """
        if len(ic_series) < max_lag + 2:
            logger.warning(f"   Insufficient data for autocorrelation (n={len(ic_series)})")
            return {}

        autocorr = {}
        for lag in range(1, max_lag + 1):
            if len(ic_series) > lag:
                corr = ic_series.autocorr(lag=lag)
                autocorr[lag] = float(corr) if not np.isnan(corr) else 0.0
            else:
                autocorr[lag] = 0.0

        return autocorr

    def calculate_stability_metrics(
        self,
        ic_series: pd.Series
    ) -> Dict[str, float]:
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
                'sign_change_rate': 0.0,
                'pct_significant': 0.0,
                'num_observations': 0
            }

        # Calculate sign changes
        sign_changes = (ic_series.diff().abs() > 0).sum()
        sign_change_rate = sign_changes / (len(ic_series) - 1) if len(ic_series) > 1 else 0.0

        # Volatility (coefficient of variation)
        mean_ic = ic_series.mean()
        std_ic = ic_series.std()
        volatility = abs(std_ic / mean_ic) if mean_ic != 0 else np.inf

        return {
            'mean_ic': float(mean_ic),
            'std_ic': float(std_ic),
            'mean_abs_ic': float(ic_series.abs().mean()),
            'volatility': float(volatility),
            'sign_change_rate': float(sign_change_rate),
            'num_observations': len(ic_series)
        }

    def run_full_analysis(
        self,
        frequencies: List[str] = ['D', 'W', 'M', 'Q'],
        windows: List[int] = [60, 126, 252, 504]
    ):
        """
        Execute comprehensive IC stability analysis

        Args:
            frequencies: List of frequencies to test ('D', 'W', 'M', 'Q')
            windows: List of IC rolling windows to test (days)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔬 STARTING IC STABILITY ANALYSIS")
        logger.info(f"{'='*80}")
        logger.info(f"Factors: {len(self.factors)}, Frequencies: {len(frequencies)}, Windows: {len(windows)}")
        logger.info(f"Total Combinations: {len(self.factors) * len(frequencies) * len(windows)}")

        freq_labels = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly'}

        for factor in self.factors:
            logger.info(f"\n📊 Analyzing Factor: {factor}")
            logger.info(f"{'─'*80}")

            for frequency in frequencies:
                for window in windows:
                    key = (factor, frequency, window)

                    # Calculate IC time-series
                    ic_df = self.calculate_ic_timeseries(factor, frequency, window)

                    if ic_df.empty:
                        continue

                    # Store time-series
                    self.ic_timeseries_results[key] = ic_df

                    # Calculate autocorrelation
                    ic_series = ic_df.set_index('date')['ic']
                    autocorr = self.calculate_autocorrelation(ic_series)
                    self.autocorr_results[key] = autocorr

                    # Calculate stability metrics
                    stability = self.calculate_stability_metrics(ic_series)
                    stability['autocorr_lag1'] = autocorr.get(1, 0.0)
                    stability['autocorr_lag3'] = autocorr.get(3, 0.0)
                    stability['autocorr_lag6'] = autocorr.get(6, 0.0)
                    stability['autocorr_lag12'] = autocorr.get(12, 0.0)
                    self.stability_metrics[key] = stability

                    # Log summary
                    freq_label = freq_labels[frequency]
                    logger.info(
                        f"   {freq_label:10s} (window={window:3d}d): "
                        f"IC={stability['mean_ic']:+.4f} ± {stability['std_ic']:.4f}, "
                        f"Autocorr(1)={autocorr.get(1, 0.0):+.3f}, "
                        f"n={len(ic_df)}"
                    )

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ ANALYSIS COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total IC Time-Series: {len(self.ic_timeseries_results)}")
        logger.info(f"Total Autocorrelation Sets: {len(self.autocorr_results)}")
        logger.info(f"Total Stability Metrics: {len(self.stability_metrics)}")

    def save_results(self, output_dir: str):
        """
        Save analysis results to CSV files

        Args:
            output_dir: Directory to save results
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save IC time-series
        logger.info(f"\n💾 Saving Results to {output_dir}")

        ic_records = []
        for (factor, freq, window), df in self.ic_timeseries_results.items():
            for _, row in df.iterrows():
                ic_records.append({
                    'factor': factor,
                    'frequency': freq,
                    'window_days': window,
                    'date': row['date'],
                    'ic': row['ic'],
                    'p_value': row['p_value'],
                    'num_stocks': row['num_stocks'],
                    'is_significant': row['is_significant']
                })

        if ic_records:
            ic_df = pd.DataFrame(ic_records)
            ic_file = output_path / f'ic_stability_timeseries_{timestamp}.csv'
            ic_df.to_csv(ic_file, index=False)
            logger.info(f"   ✅ Saved IC time-series: {ic_file.name}")

        # Save autocorrelation results
        autocorr_records = []
        for (factor, freq, window), autocorr_dict in self.autocorr_results.items():
            for lag, corr in autocorr_dict.items():
                autocorr_records.append({
                    'factor': factor,
                    'frequency': freq,
                    'window_days': window,
                    'lag': lag,
                    'autocorrelation': corr
                })

        if autocorr_records:
            autocorr_df = pd.DataFrame(autocorr_records)
            autocorr_file = output_path / f'ic_autocorrelation_{timestamp}.csv'
            autocorr_df.to_csv(autocorr_file, index=False)
            logger.info(f"   ✅ Saved autocorrelation: {autocorr_file.name}")

        # Save stability metrics
        metrics_records = []
        for (factor, freq, window), metrics in self.stability_metrics.items():
            record = {
                'factor': factor,
                'frequency': freq,
                'window_days': window
            }
            record.update(metrics)
            metrics_records.append(record)

        if metrics_records:
            metrics_df = pd.DataFrame(metrics_records)
            metrics_file = output_path / f'ic_stability_metrics_{timestamp}.csv'
            metrics_df.to_csv(metrics_file, index=False)
            logger.info(f"   ✅ Saved stability metrics: {metrics_file.name}")

        return timestamp

    def visualize_results(self, output_dir: str, timestamp: str):
        """
        Create visualization plots

        Args:
            output_dir: Directory to save plots
            timestamp: Timestamp for file naming
        """
        output_path = Path(output_dir) / 'plots'
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"\n📊 Creating Visualizations")

        freq_labels = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly'}

        # Plot 1: IC Time-Series for each factor (4 frequencies × 1 window)
        window = 252  # Use 252-day window for comparison

        for factor in self.factors:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'IC Time-Series: {factor} (window=252 days)', fontsize=16, fontweight='bold')

            for idx, freq in enumerate(['D', 'W', 'M', 'Q']):
                ax = axes[idx // 2, idx % 2]
                key = (factor, freq, window)

                if key in self.ic_timeseries_results:
                    df = self.ic_timeseries_results[key]
                    ax.plot(df['date'], df['ic'], linewidth=1.5, alpha=0.8)
                    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
                    ax.grid(True, alpha=0.3)
                    ax.set_title(f'{freq_labels[freq]} Rebalancing', fontsize=12, fontweight='bold')
                    ax.set_xlabel('Date')
                    ax.set_ylabel('IC (Spearman Correlation)')

                    # Add autocorr annotation
                    if key in self.autocorr_results:
                        autocorr_lag1 = self.autocorr_results[key].get(1, 0.0)
                        ax.text(
                            0.02, 0.98, f'Autocorr(1): {autocorr_lag1:+.3f}',
                            transform=ax.transAxes,
                            fontsize=10,
                            verticalalignment='top',
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
                        )
                else:
                    ax.text(0.5, 0.5, 'No Data', ha='center', va='center', fontsize=14)
                    ax.set_title(f'{freq_labels[freq]} Rebalancing (No Data)', fontsize=12)

            plt.tight_layout()
            plot_file = output_path / f'ic_timeseries_{factor}_{timestamp}.png'
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            plt.close()
            logger.info(f"   ✅ Saved plot: {plot_file.name}")

        # Plot 2: Autocorrelation Heatmap (comparing all factors and frequencies)
        window = 252

        # Prepare autocorr data for heatmap
        autocorr_matrix = []
        row_labels = []

        for factor in self.factors:
            for freq in ['D', 'W', 'M', 'Q']:
                key = (factor, freq, window)
                if key in self.autocorr_results:
                    autocorr_values = [self.autocorr_results[key].get(lag, 0.0) for lag in range(1, 13)]
                    autocorr_matrix.append(autocorr_values)
                    row_labels.append(f'{factor[:15]}_{freq_labels[freq][:3]}')

        if autocorr_matrix:
            fig, ax = plt.subplots(figsize=(14, max(8, len(row_labels) * 0.5)))
            sns.heatmap(
                autocorr_matrix,
                annot=True,
                fmt='.2f',
                cmap='RdYlGn',
                center=0,
                vmin=-1,
                vmax=1,
                xticklabels=[f'Lag {i}' for i in range(1, 13)],
                yticklabels=row_labels,
                cbar_kws={'label': 'Autocorrelation'},
                ax=ax
            )
            ax.set_title('IC Autocorrelation Heatmap (window=252 days)', fontsize=14, fontweight='bold')
            ax.set_xlabel('Lag', fontsize=12)
            ax.set_ylabel('Factor_Frequency', fontsize=12)

            plt.tight_layout()
            heatmap_file = output_path / f'ic_autocorr_heatmap_{timestamp}.png'
            plt.savefig(heatmap_file, dpi=150, bbox_inches='tight')
            plt.close()
            logger.info(f"   ✅ Saved autocorrelation heatmap: {heatmap_file.name}")

        logger.info(f"   📁 All plots saved to: {output_path}")

    def generate_report(self, output_dir: str, timestamp: str):
        """
        Generate comprehensive markdown report

        Args:
            output_dir: Directory to save report
            timestamp: Timestamp for file naming
        """
        output_path = Path(output_dir)
        report_file = output_path / f'ic_stability_report_{timestamp}.md'

        logger.info(f"\n📝 Generating Report: {report_file.name}")

        freq_labels = {'D': 'Daily', 'W': 'Weekly', 'M': 'Monthly', 'Q': 'Quarterly'}

        with open(report_file, 'w') as f:
            f.write(f"# IC Stability Analysis Report\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Analysis Period**: {self.start_date} to {self.end_date}\n")
            f.write(f"**Factors Analyzed**: {', '.join(self.factors)}\n")
            f.write(f"**Region**: {self.region}\n")
            f.write(f"**Holding Period**: {self.holding_period} days\n\n")

            f.write(f"---\n\n")
            f.write(f"## Executive Summary\n\n")

            # Summary table comparing Monthly vs Quarterly
            f.write(f"### Quarterly vs Monthly IC Comparison (window=252 days)\n\n")
            f.write(f"| Factor | Metric | Quarterly (Q) | Monthly (M) | Difference | Analysis |\n")
            f.write(f"|--------|--------|---------------|-------------|------------|-----------|\n")

            for factor in self.factors:
                q_key = (factor, 'Q', 252)
                m_key = (factor, 'M', 252)

                if q_key in self.stability_metrics and m_key in self.stability_metrics:
                    q_metrics = self.stability_metrics[q_key]
                    m_metrics = self.stability_metrics[m_key]

                    # Mean IC
                    q_ic = q_metrics['mean_ic']
                    m_ic = m_metrics['mean_ic']
                    ic_diff = m_ic - q_ic
                    ic_status = "✅ Better" if abs(m_ic) > abs(q_ic) else "❌ Worse"
                    f.write(f"| {factor} | Mean IC | {q_ic:+.4f} | {m_ic:+.4f} | {ic_diff:+.4f} | {ic_status} |\n")

                    # Autocorr Lag-1
                    q_autocorr = q_metrics['autocorr_lag1']
                    m_autocorr = m_metrics['autocorr_lag1']
                    autocorr_diff = m_autocorr - q_autocorr
                    autocorr_status = "✅ Stable" if m_autocorr > 0.2 else "❌ Unstable"
                    f.write(f"| {factor} | Autocorr(1) | {q_autocorr:+.3f} | {m_autocorr:+.3f} | {autocorr_diff:+.3f} | {autocorr_status} |\n")

                    # Volatility
                    q_vol = q_metrics['volatility']
                    m_vol = m_metrics['volatility']
                    if q_vol != np.inf and m_vol != np.inf:
                        vol_diff = m_vol - q_vol
                        vol_status = "✅ Lower" if m_vol < q_vol else "❌ Higher"
                        f.write(f"| {factor} | Volatility | {q_vol:.2f} | {m_vol:.2f} | {vol_diff:+.2f} | {vol_status} |\n")

            f.write(f"\n### Key Findings\n\n")

            # Analyze results for each factor
            for factor in self.factors:
                f.write(f"#### {factor}\n\n")

                m_key = (factor, 'M', 252)
                q_key = (factor, 'Q', 252)

                if m_key in self.stability_metrics:
                    m_metrics = self.stability_metrics[m_key]
                    m_autocorr = m_metrics['autocorr_lag1']

                    if m_autocorr < 0.2:
                        f.write(f"🚨 **CRITICAL**: Monthly IC is **UNSTABLE** (autocorr={m_autocorr:+.3f} < 0.2)\n")
                        f.write(f"- IC signal quality degrades rapidly at monthly frequency\n")
                        f.write(f"- Factor predictions become noisy and unreliable\n")
                        f.write(f"- **Root Cause**: This factor cannot support monthly rebalancing\n\n")
                    elif m_autocorr < 0.5:
                        f.write(f"⚠️ **WARNING**: Monthly IC is **MODERATELY STABLE** (autocorr={m_autocorr:+.3f})\n")
                        f.write(f"- IC signal quality degrades at monthly frequency\n")
                        f.write(f"- Factor may work at monthly frequency but with reduced reliability\n\n")
                    else:
                        f.write(f"✅ **STABLE**: Monthly IC is **STABLE** (autocorr={m_autocorr:+.3f} ≥ 0.5)\n")
                        f.write(f"- IC signal quality persists at monthly frequency\n")
                        f.write(f"- Factor is suitable for monthly rebalancing\n\n")

                if q_key in self.stability_metrics:
                    q_metrics = self.stability_metrics[q_key]
                    q_autocorr = q_metrics['autocorr_lag1']

                    if q_autocorr >= 0.5:
                        f.write(f"✅ Quarterly IC is **STABLE** (autocorr={q_autocorr:+.3f} ≥ 0.5)\n")
                        f.write(f"- Factor is well-suited for quarterly rebalancing\n\n")

            f.write(f"\n---\n\n")
            f.write(f"## Detailed Results\n\n")

            # Stability metrics table for all combinations
            f.write(f"### Stability Metrics (All Frequencies & Windows)\n\n")
            f.write(f"| Factor | Frequency | Window | Mean IC | Std IC | Autocorr(1) | Autocorr(3) | Volatility | n |\n")
            f.write(f"|--------|-----------|--------|---------|--------|-------------|-------------|------------|-|\n")

            for (factor, freq, window), metrics in sorted(self.stability_metrics.items()):
                f.write(
                    f"| {factor} | {freq_labels[freq]} | {window} | "
                    f"{metrics['mean_ic']:+.4f} | {metrics['std_ic']:.4f} | "
                    f"{metrics['autocorr_lag1']:+.3f} | {metrics['autocorr_lag3']:+.3f} | "
                    f"{metrics['volatility']:.2f} | {metrics['num_observations']} |\n"
                )

            f.write(f"\n---\n\n")
            f.write(f"## Hypothesis Validation\n\n")

            f.write(f"### H1: Monthly IC is unstable with low autocorrelation\n\n")

            unstable_factors = []
            stable_factors = []

            for factor in self.factors:
                m_key = (factor, 'M', 252)
                if m_key in self.stability_metrics:
                    m_autocorr = self.stability_metrics[m_key]['autocorr_lag1']

                    if m_autocorr < 0.2:
                        unstable_factors.append(f"{factor} (autocorr={m_autocorr:+.3f})")
                    else:
                        stable_factors.append(f"{factor} (autocorr={m_autocorr:+.3f})")

            if unstable_factors:
                f.write(f"**Status**: ✅ **CONFIRMED** - {len(unstable_factors)}/{len(self.factors)} factors are unstable at monthly frequency\n\n")
                f.write(f"**Unstable Factors**:\n")
                for factor_str in unstable_factors:
                    f.write(f"- {factor_str}\n")
                f.write(f"\n**Implication**: Monthly rebalancing failure is caused by IC signal degradation.\n\n")
            else:
                f.write(f"**Status**: ❌ **REJECTED** - All factors show sufficient stability at monthly frequency\n\n")
                f.write(f"**Implication**: IC instability is NOT the root cause. Investigate other hypotheses.\n\n")

            if stable_factors:
                f.write(f"**Stable Factors** (suitable for monthly rebalancing):\n")
                for factor_str in stable_factors:
                    f.write(f"- {factor_str}\n")
                f.write(f"\n")

            f.write(f"---\n\n")
            f.write(f"## Recommendations\n\n")

            if unstable_factors:
                f.write(f"### Immediate Actions (High Priority)\n\n")
                f.write(f"1. **DO NOT USE MONTHLY REBALANCING** for unstable factors\n")
                f.write(f"2. **Stick with quarterly rebalancing** for current IC-weighted strategy\n")
                f.write(f"3. **Optimize IC rolling window** (Phase 1.2) to potentially stabilize monthly IC\n")
                f.write(f"4. **Test individual factors** (Phase 1.3) to isolate unstable factor contribution\n\n")

                f.write(f"### Next Steps (Phase 1.2)\n\n")
                f.write(f"**Test alternative IC windows for monthly rebalancing**:\n")
                f.write(f"- Hypothesis: Shorter window (60 days) may be more appropriate for monthly frequency\n")
                f.write(f"- Current window (252 days) may be too long for monthly signal updates\n")
                f.write(f"- Run `scripts/optimize_ic_window.py` to find optimal window per frequency\n\n")
            else:
                f.write(f"### Next Steps\n\n")
                f.write(f"1. **IC instability is NOT the root cause** - proceed to Phase 2 (Factor Performance Decomposition)\n")
                f.write(f"2. **Investigate alternative hypotheses**:\n")
                f.write(f"   - H2: Factor overfitting to training period\n")
                f.write(f"   - H3: IC weighting method inappropriate for monthly frequency\n")
                f.write(f"   - H4: Stock selection threshold (top 45%) causes excessive turnover\n")
                f.write(f"3. **Test alternative factor weighting methods** (Phase 2.2)\n\n")

            f.write(f"---\n\n")
            f.write(f"## Appendix\n\n")
            f.write(f"### Analysis Configuration\n\n")
            f.write(f"```yaml\n")
            f.write(f"factors: {self.factors}\n")
            f.write(f"frequencies: ['D', 'W', 'M', 'Q']\n")
            f.write(f"windows: [60, 126, 252, 504]\n")
            f.write(f"holding_period: {self.holding_period}\n")
            f.write(f"min_stocks: {self.min_stocks}\n")
            f.write(f"region: {self.region}\n")
            f.write(f"date_range: {self.start_date} to {self.end_date}\n")
            f.write(f"```\n\n")

            f.write(f"### Output Files\n\n")
            f.write(f"- `ic_stability_timeseries_{timestamp}.csv` - IC time-series data\n")
            f.write(f"- `ic_autocorrelation_{timestamp}.csv` - Autocorrelation coefficients\n")
            f.write(f"- `ic_stability_metrics_{timestamp}.csv` - Summary statistics\n")
            f.write(f"- `plots/ic_timeseries_*.png` - IC time-series plots\n")
            f.write(f"- `plots/ic_autocorr_heatmap_{timestamp}.png` - Autocorrelation heatmap\n")
            f.write(f"- `ic_stability_report_{timestamp}.md` - This report\n\n")

            f.write(f"---\n\n")
            f.write(f"**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Spock Quant Platform** - Phase 1.1 IC Stability Analysis\n")

        logger.info(f"   ✅ Report saved: {report_file.name}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='IC Stability Analyzer - Phase 1.1 of Monthly Rebalancing Troubleshooting'
    )

    parser.add_argument(
        '--factors',
        nargs='+',
        default=['Operating_Profit_Margin', 'RSI_Momentum', 'ROE_Proxy'],
        help='Factor names to analyze (default: Tier 3 factors)'
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
        '--frequencies',
        nargs='+',
        default=['D', 'W', 'M', 'Q'],
        help='Frequencies to test: D, W, M, Q (default: all)'
    )

    parser.add_argument(
        '--windows',
        nargs='+',
        type=int,
        default=[60, 126, 252, 504],
        help='IC rolling windows to test in days (default: 60 126 252 504)'
    )

    args = parser.parse_args()

    # Initialize database
    logger.info(f"🔌 Connecting to PostgreSQL database...")
    db = PostgresDatabaseManager()

    # Initialize analyzer
    analyzer = ICStabilityAnalyzer(
        db_manager=db,
        factors=args.factors,
        start_date=args.start_date,
        end_date=args.end_date,
        region=args.region,
        holding_period=args.holding_period
    )

    # Run analysis
    analyzer.run_full_analysis(
        frequencies=args.frequencies,
        windows=args.windows
    )

    # Save results
    timestamp = analyzer.save_results(args.output_dir)

    # Create visualizations
    analyzer.visualize_results(args.output_dir, timestamp)

    # Generate report
    analyzer.generate_report(args.output_dir, timestamp)

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ IC STABILITY ANALYSIS COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Results saved to: {args.output_dir}/")
    logger.info(f"Review report: ic_stability_report_{timestamp}.md")


if __name__ == '__main__':
    main()
