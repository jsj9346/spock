#!/usr/bin/env python3
"""
PerformanceReporter - Factor Performance Visualization and Reporting

Generates comprehensive factor analysis reports with:
1. Quintile performance charts
2. IC time series visualization
3. Correlation heatmaps
4. Export to CSV/PDF/PNG formats

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
from typing import Dict, List, Optional
from datetime import datetime
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger

from .factor_analyzer import FactorAnalyzer, QuintileResult, ICResult
from .factor_correlation import FactorCorrelationAnalyzer

# Import Plotly for interactive visualizations
try:
    from modules.visualization.ic_charts import ICChartGenerator
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("Plotly visualization module not available. Interactive IC charts disabled.")

# Suppress matplotlib warnings
warnings.filterwarnings('ignore', category=UserWarning)

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

# Seaborn style
sns.set_style("whitegrid")
sns.set_palette("husl")


class PerformanceReporter:
    """
    Factor Performance Reporting and Visualization Engine

    Methods:
        quintile_performance_report() - Generate quintile analysis report
        ic_time_series_report() - Generate IC time series report (Matplotlib)
        ic_time_series_report_plotly() - Generate interactive IC report (Plotly)
        correlation_heatmap() - Generate factor correlation heatmap
        factor_comparison_dashboard() - Multi-factor comparison dashboard

    Usage:
        reporter = PerformanceReporter(output_dir='reports/')
        reporter.quintile_performance_report('12M_Momentum', quintile_results)

        # Interactive IC visualization
        reporter.ic_time_series_report_plotly('PE_Ratio', ic_results, chart_types=['dashboard'])
    """

    def __init__(self, output_dir: str = 'reports/', theme: str = 'plotly_white'):
        """
        Initialize PerformanceReporter

        Args:
            output_dir: Directory for saving reports (default: 'reports/')
            theme: Plotly theme for interactive charts (default: 'plotly_white')
        """
        self.output_dir = output_dir
        self.theme = theme
        os.makedirs(output_dir, exist_ok=True)

        # Initialize Plotly chart generator if available
        if PLOTLY_AVAILABLE:
            self.ic_chart_generator = ICChartGenerator(theme=theme)
        else:
            self.ic_chart_generator = None

    def quintile_performance_report(
        self,
        factor_name: str,
        quintile_results: List[QuintileResult],
        analysis_date: str,
        region: str = 'KR',
        holding_period: int = 21,
        export_formats: List[str] = ['png', 'csv']
    ) -> Dict[str, str]:
        """
        Generate quintile performance report with charts and statistics

        Creates:
        1. Bar chart: Mean return by quintile
        2. Table: Detailed statistics (Sharpe, hit rate, num stocks)
        3. CSV export: Quintile data

        Args:
            factor_name: Name of factor
            quintile_results: List of QuintileResult from FactorAnalyzer
            analysis_date: Analysis date (YYYY-MM-DD)
            region: Market region
            holding_period: Forward return period (days)
            export_formats: List of formats to export (['png', 'csv', 'pdf'])

        Returns:
            Dict[str, str]: Paths to generated files

        Example:
            >>> reporter = PerformanceReporter()
            >>> files = reporter.quintile_performance_report('PE_Ratio', results, '2025-10-22', 'KR')
            >>> print(f"Chart saved to: {files['chart']}")
        """
        if not quintile_results:
            logger.warning("No quintile results to report")
            return {}

        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Extract data
        quintiles = [q.quintile for q in quintile_results]
        mean_returns = [q.mean_return * 100 for q in quintile_results]  # Convert to %
        sharpe_ratios = [q.sharpe_ratio for q in quintile_results]
        num_stocks = [q.num_stocks for q in quintile_results]

        # Plot 1: Mean return by quintile (bar chart)
        colors = ['red' if r < 0 else 'green' for r in mean_returns]
        ax1.bar(quintiles, mean_returns, color=colors, alpha=0.7, edgecolor='black')
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax1.set_xlabel('Quintile', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Mean Return (%)', fontsize=12, fontweight='bold')
        ax1.set_title(
            f'{factor_name} - Quintile Returns\n'
            f'{analysis_date} | {region} | {holding_period}d holding period',
            fontsize=14, fontweight='bold'
        )
        ax1.set_xticks(quintiles)
        ax1.grid(axis='y', alpha=0.3)

        # Add return values on bars
        for i, (q, ret) in enumerate(zip(quintiles, mean_returns)):
            ax1.text(q, ret, f'{ret:.2f}%', ha='center', va='bottom' if ret >= 0 else 'top', fontsize=10)

        # Plot 2: Sharpe ratio by quintile
        ax2.plot(quintiles, sharpe_ratios, marker='o', linewidth=2, markersize=8, color='navy')
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax2.set_xlabel('Quintile', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Sharpe Ratio', fontsize=12, fontweight='bold')
        ax2.set_title('Sharpe Ratio by Quintile', fontsize=14, fontweight='bold')
        ax2.set_xticks(quintiles)
        ax2.grid(axis='y', alpha=0.3)

        # Add Sharpe values
        for q, sharpe in zip(quintiles, sharpe_ratios):
            ax2.text(q, sharpe, f'{sharpe:.2f}', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()

        # Save files
        output_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'{factor_name}_quintile_{analysis_date}_{timestamp}'

        # Save chart
        if 'png' in export_formats:
            chart_path = os.path.join(self.output_dir, f'{base_filename}.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            output_files['chart'] = chart_path
            logger.info(f"Quintile chart saved: {chart_path}")

        if 'pdf' in export_formats:
            pdf_path = os.path.join(self.output_dir, f'{base_filename}.pdf')
            plt.savefig(pdf_path, bbox_inches='tight')
            output_files['pdf'] = pdf_path

        plt.close()

        # Save CSV
        if 'csv' in export_formats:
            df = pd.DataFrame([
                {
                    'quintile': q.quintile,
                    'num_stocks': q.num_stocks,
                    'mean_return': q.mean_return,
                    'median_return': q.median_return,
                    'std_dev': q.std_dev,
                    'sharpe_ratio': q.sharpe_ratio,
                    'hit_rate': q.hit_rate,
                    'min_return': q.min_return,
                    'max_return': q.max_return
                }
                for q in quintile_results
            ])

            csv_path = os.path.join(self.output_dir, f'{base_filename}.csv')
            df.to_csv(csv_path, index=False)
            output_files['csv'] = csv_path
            logger.info(f"Quintile CSV saved: {csv_path}")

        return output_files

    def ic_time_series_report(
        self,
        factor_name: str,
        ic_results: List[ICResult],
        export_formats: List[str] = ['png', 'csv']
    ) -> Dict[str, str]:
        """
        Generate IC time series report

        Creates:
        1. Line chart: IC over time
        2. Rolling mean IC (20-period window)
        3. Histogram: IC distribution
        4. CSV export: IC time series

        Args:
            factor_name: Name of factor
            ic_results: List of ICResult from FactorAnalyzer
            export_formats: List of formats to export

        Returns:
            Dict[str, str]: Paths to generated files
        """
        if not ic_results:
            logger.warning("No IC results to report")
            return {}

        # Extract data
        dates = [ic.date for ic in ic_results]
        ic_values = [ic.ic_value for ic in ic_results]

        # Create figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Plot 1: IC time series
        ax1.plot(dates, ic_values, marker='o', linewidth=1.5, markersize=4, label='IC', alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.8)

        # Rolling mean (20-period)
        if len(ic_values) >= 20:
            rolling_mean = pd.Series(ic_values).rolling(window=20, min_periods=1).mean()
            ax1.plot(dates, rolling_mean, linewidth=2, color='red', label='20-Period MA', alpha=0.8)

        ax1.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax1.set_ylabel('IC', fontsize=12, fontweight='bold')
        ax1.set_title(f'{factor_name} - Information Coefficient Time Series', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(alpha=0.3)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Plot 2: IC distribution
        ax2.hist(ic_values, bins=30, edgecolor='black', alpha=0.7, color='steelblue')
        ax2.axvline(x=np.mean(ic_values), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(ic_values):.4f}')
        ax2.axvline(x=0, color='black', linestyle='--', linewidth=0.8)
        ax2.set_xlabel('IC', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax2.set_title('IC Distribution', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        # Save files
        output_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'{factor_name}_ic_timeseries_{timestamp}'

        if 'png' in export_formats:
            chart_path = os.path.join(self.output_dir, f'{base_filename}.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            output_files['chart'] = chart_path
            logger.info(f"IC time series chart saved: {chart_path}")

        if 'pdf' in export_formats:
            pdf_path = os.path.join(self.output_dir, f'{base_filename}.pdf')
            plt.savefig(pdf_path, bbox_inches='tight')
            output_files['pdf'] = pdf_path

        plt.close()

        # Save CSV
        if 'csv' in export_formats:
            df = pd.DataFrame([
                {
                    'date': ic.date,
                    'ic_value': ic.ic_value,
                    'num_stocks': ic.num_stocks,
                    'p_value': ic.p_value,
                    'is_significant': ic.is_significant
                }
                for ic in ic_results
            ])

            csv_path = os.path.join(self.output_dir, f'{base_filename}.csv')
            df.to_csv(csv_path, index=False)
            output_files['csv'] = csv_path
            logger.info(f"IC CSV saved: {csv_path}")

        return output_files

    def ic_time_series_report_plotly(
        self,
        factor_name: str,
        ic_results: List[ICResult],
        region: str = 'KR',
        holding_period: int = 21,
        export_formats: List[str] = ['html'],
        chart_types: List[str] = ['timeseries', 'distribution']
    ) -> Dict[str, str]:
        """
        Generate interactive IC time series report using Plotly

        Parallel implementation to ic_time_series_report() with interactive features.

        Creates:
        1. Interactive line chart: IC over time with rolling average
        2. Interactive histogram: IC distribution
        3. HTML export with full interactivity (zoom, pan, hover)

        Args:
            factor_name: Name of factor
            ic_results: List of ICResult from FactorAnalyzer
            region: Market region (for chart title)
            holding_period: Forward return period (for chart title)
            export_formats: List of formats to export (['html', 'png'])
            chart_types: List of chart types to generate
                - 'timeseries': IC time series with rolling average
                - 'distribution': IC distribution histogram
                - 'rolling': Rolling IC average
                - 'dashboard': Multi-chart dashboard

        Returns:
            Dict[str, str]: Paths to generated files

        Example:
            >>> reporter = PerformanceReporter()
            >>> files = reporter.ic_time_series_report_plotly('PE_Ratio', ic_results, 'KR')
            >>> print(f"Interactive chart: {files['timeseries_html']}")

        Note:
            Requires Plotly installation. Falls back to Matplotlib if unavailable.
        """
        if not PLOTLY_AVAILABLE or self.ic_chart_generator is None:
            logger.warning("Plotly not available. Use ic_time_series_report() for Matplotlib version.")
            return self.ic_time_series_report(factor_name, ic_results, export_formats=['png', 'csv'])

        if not ic_results:
            logger.warning("No IC results to report")
            return {}

        # Convert ICResult list to DataFrame format expected by ICChartGenerator
        ic_df = pd.DataFrame([
            {
                'date': ic.date,
                'factor_name': factor_name,
                'ic': ic.ic_value,
                'p_value': ic.p_value,
                'num_stocks': ic.num_stocks,
                'is_significant': ic.is_significant
            }
            for ic in ic_results
        ])

        ic_df['date'] = pd.to_datetime(ic_df['date'])

        # Generate charts
        output_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Chart 1: IC Time Series
        if 'timeseries' in chart_types:
            try:
                fig = self.ic_chart_generator.plot_ic_time_series(
                    ic_df=ic_df,
                    rolling_window=20,
                    show_significance=True
                )

                if 'html' in export_formats:
                    filename = f'{factor_name}_ic_timeseries_interactive_{timestamp}.html'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_html(filepath)
                    output_files['timeseries_html'] = filepath
                    logger.info(f"Interactive IC time series saved: {filepath}")

                if 'png' in export_formats:
                    filename = f'{factor_name}_ic_timeseries_interactive_{timestamp}.png'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_image(filepath, width=1200, height=600)
                    output_files['timeseries_png'] = filepath
                    logger.info(f"Static IC time series saved: {filepath}")

            except Exception as e:
                logger.error(f"Failed to generate IC time series chart: {e}")

        # Chart 2: IC Distribution
        if 'distribution' in chart_types:
            try:
                fig = self.ic_chart_generator.plot_ic_distribution(ic_df=ic_df)

                if 'html' in export_formats:
                    filename = f'{factor_name}_ic_distribution_interactive_{timestamp}.html'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_html(filepath)
                    output_files['distribution_html'] = filepath
                    logger.info(f"Interactive IC distribution saved: {filepath}")

                if 'png' in export_formats:
                    filename = f'{factor_name}_ic_distribution_interactive_{timestamp}.png'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_image(filepath, width=1000, height=600)
                    output_files['distribution_png'] = filepath

            except Exception as e:
                logger.error(f"Failed to generate IC distribution chart: {e}")

        # Chart 3: Rolling IC Average
        if 'rolling' in chart_types:
            try:
                fig = self.ic_chart_generator.plot_rolling_ic_average(
                    ic_df=ic_df,
                    window=20
                )

                if 'html' in export_formats:
                    filename = f'{factor_name}_ic_rolling_avg_interactive_{timestamp}.html'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_html(filepath)
                    output_files['rolling_html'] = filepath
                    logger.info(f"Interactive rolling IC average saved: {filepath}")

                if 'png' in export_formats:
                    filename = f'{factor_name}_ic_rolling_avg_interactive_{timestamp}.png'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_image(filepath, width=1200, height=600)
                    output_files['rolling_png'] = filepath

            except Exception as e:
                logger.error(f"Failed to generate rolling IC chart: {e}")

        # Chart 4: Multi-Factor Dashboard (single factor version)
        if 'dashboard' in chart_types:
            try:
                fig = self.ic_chart_generator.create_multi_factor_dashboard(
                    ic_df=ic_df,
                    rolling_window=20
                )

                if 'html' in export_formats:
                    filename = f'{factor_name}_ic_dashboard_interactive_{timestamp}.html'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_html(filepath)
                    output_files['dashboard_html'] = filepath
                    logger.info(f"Interactive IC dashboard saved: {filepath}")

                if 'png' in export_formats:
                    filename = f'{factor_name}_ic_dashboard_interactive_{timestamp}.png'
                    filepath = os.path.join(self.output_dir, filename)
                    fig.write_image(filepath, width=1600, height=1000)
                    output_files['dashboard_png'] = filepath

            except Exception as e:
                logger.error(f"Failed to generate IC dashboard: {e}")

        return output_files

    def correlation_heatmap(
        self,
        corr_matrix: pd.DataFrame,
        analysis_date: str,
        region: str = 'KR',
        export_formats: List[str] = ['png']
    ) -> Dict[str, str]:
        """
        Generate factor correlation heatmap

        Args:
            corr_matrix: Correlation matrix from FactorCorrelationAnalyzer
            analysis_date: Analysis date (YYYY-MM-DD)
            region: Market region
            export_formats: List of formats to export

        Returns:
            Dict[str, str]: Paths to generated files
        """
        if corr_matrix.empty:
            logger.warning("Empty correlation matrix")
            return {}

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 10))

        # Heatmap
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.5,
            cbar_kws={'label': 'Correlation'},
            ax=ax
        )

        ax.set_title(
            f'Factor Correlation Matrix\n{analysis_date} | {region}',
            fontsize=14,
            fontweight='bold',
            pad=20
        )

        plt.tight_layout()

        # Save files
        output_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'factor_correlation_{analysis_date}_{timestamp}'

        if 'png' in export_formats:
            chart_path = os.path.join(self.output_dir, f'{base_filename}.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            output_files['chart'] = chart_path
            logger.info(f"Correlation heatmap saved: {chart_path}")

        if 'pdf' in export_formats:
            pdf_path = os.path.join(self.output_dir, f'{base_filename}.pdf')
            plt.savefig(pdf_path, bbox_inches='tight')
            output_files['pdf'] = pdf_path

        plt.close()

        return output_files

    def factor_comparison_dashboard(
        self,
        factor_quintiles: Dict[str, List[QuintileResult]],
        analysis_date: str,
        region: str = 'KR',
        export_formats: List[str] = ['png']
    ) -> Dict[str, str]:
        """
        Generate multi-factor comparison dashboard

        Args:
            factor_quintiles: Dict mapping factor_name to List[QuintileResult]
            analysis_date: Analysis date (YYYY-MM-DD)
            region: Market region
            export_formats: List of formats to export

        Returns:
            Dict[str, str]: Paths to generated files
        """
        if not factor_quintiles:
            logger.warning("No factor data for comparison")
            return {}

        num_factors = len(factor_quintiles)
        fig, axes = plt.subplots(1, num_factors, figsize=(6 * num_factors, 6), sharey=True)

        if num_factors == 1:
            axes = [axes]

        for ax, (factor_name, quintile_results) in zip(axes, factor_quintiles.items()):
            quintiles = [q.quintile for q in quintile_results]
            mean_returns = [q.mean_return * 100 for q in quintile_results]

            colors = ['red' if r < 0 else 'green' for r in mean_returns]
            ax.bar(quintiles, mean_returns, color=colors, alpha=0.7, edgecolor='black')
            ax.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
            ax.set_xlabel('Quintile', fontsize=12, fontweight='bold')
            if ax == axes[0]:
                ax.set_ylabel('Mean Return (%)', fontsize=12, fontweight='bold')
            ax.set_title(factor_name, fontsize=14, fontweight='bold')
            ax.set_xticks(quintiles)
            ax.grid(axis='y', alpha=0.3)

            # Add values
            for q, ret in zip(quintiles, mean_returns):
                ax.text(q, ret, f'{ret:.2f}%', ha='center', va='bottom' if ret >= 0 else 'top', fontsize=9)

        fig.suptitle(
            f'Factor Comparison - Quintile Returns\n{analysis_date} | {region}',
            fontsize=16,
            fontweight='bold',
            y=1.02
        )

        plt.tight_layout()

        # Save files
        output_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f'factor_comparison_{analysis_date}_{timestamp}'

        if 'png' in export_formats:
            chart_path = os.path.join(self.output_dir, f'{base_filename}.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            output_files['chart'] = chart_path
            logger.info(f"Factor comparison dashboard saved: {chart_path}")

        if 'pdf' in export_formats:
            pdf_path = os.path.join(self.output_dir, f'{base_filename}.pdf')
            plt.savefig(pdf_path, bbox_inches='tight')
            output_files['pdf'] = pdf_path

        plt.close()

        return output_files
