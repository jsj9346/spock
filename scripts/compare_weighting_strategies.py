#!/usr/bin/env python3
"""
Weighting Strategy Comparison Script

Compares IC-weighted vs Equal-weighted multi-factor strategies across
different percentile thresholds (60th, 70th, 80th).

Generates:
- Performance comparison table
- Cumulative return charts
- Drawdown comparison charts
- Risk-return scatter plot
- Statistical significance tests

Usage:
    python3 scripts/compare_weighting_strategies.py

Author: Spock Quant Platform
Date: 2025-10-24
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

# Configure plotting style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10


def load_backtest_results():
    """
    Load all backtest result CSV files

    Returns:
        dict: {strategy_name: DataFrame}
    """
    results_dir = Path("backtest_results")

    # Define file patterns
    files = {
        'IC-Weighted 60th': 'ic_weighted_backtest_2024-10-10_2025-10-22_20251024_120204.csv',
        'IC-Weighted 70th': 'ic_weighted_backtest_2024-10-10_2025-10-22_20251024_120125.csv',
        'IC-Weighted 80th': 'ic_weighted_backtest_2024-10-10_2025-10-22_20251024_120050.csv',
        'Equal-Weighted 60th': 'equal_weighted_backtest_2024-10-10_2025-10-22_20251024_121616.csv',
        'Equal-Weighted 70th': 'equal_weighted_backtest_2024-10-10_2025-10-22_20251024_121642.csv',
        'Equal-Weighted 80th': 'equal_weighted_backtest_2024-10-10_2025-10-22_20251024_121707.csv',
    }

    data = {}
    for name, filename in files.items():
        filepath = results_dir / filename
        if filepath.exists():
            df = pd.read_csv(filepath)
            df['date'] = pd.to_datetime(df['date'])
            data[name] = df
            logger.info(f"✅ Loaded {name}: {len(df)} days")
        else:
            logger.warning(f"⚠️ File not found: {filepath}")

    return data


def calculate_metrics(df: pd.DataFrame, initial_capital: float = 100_000_000) -> dict:
    """
    Calculate performance metrics for a backtest result

    Args:
        df: DataFrame with portfolio values
        initial_capital: Starting capital

    Returns:
        dict: Performance metrics
    """
    # Filter to active portfolio (value > 0)
    df_active = df[df['value'] > 0].copy()

    if len(df_active) < 2:
        return {}

    # Calculate returns
    df_active['returns'] = df_active['value'].pct_change()
    valid_returns = df_active['returns'].replace([np.inf, -np.inf], np.nan).dropna()

    # Total return
    first_value = df_active['value'].iloc[0]
    final_value = df_active['value'].iloc[-1]
    total_return = (final_value / first_value - 1) * 100

    # Annualized metrics
    days = len(df_active)
    years = days / 252
    annualized_return = ((final_value / first_value) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Volatility
    volatility = valid_returns.std() * np.sqrt(252) * 100 if len(valid_returns) > 1 else 0

    # Sharpe ratio
    sharpe = annualized_return / volatility if volatility > 0 else 0

    # Drawdown
    cumulative = (1 + valid_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    avg_drawdown = drawdown.mean() * 100

    # Calmar ratio
    calmar = abs(annualized_return / max_drawdown) if max_drawdown != 0 else 0

    # Win rate
    win_rate = (valid_returns > 0).sum() / len(valid_returns) * 100 if len(valid_returns) > 0 else 0

    # Transaction costs
    total_costs = df_active['cumulative_costs'].iloc[-1] if 'cumulative_costs' in df_active.columns else 0

    # Average positions
    avg_positions = df_active['positions'].mean() if 'positions' in df_active.columns else 0

    return {
        'Total Return (%)': round(total_return, 2),
        'Annualized Return (%)': round(annualized_return, 2),
        'Volatility (%)': round(volatility, 2),
        'Sharpe Ratio': round(sharpe, 3),
        'Calmar Ratio': round(calmar, 3),
        'Max Drawdown (%)': round(max_drawdown, 2),
        'Avg Drawdown (%)': round(avg_drawdown, 2),
        'Win Rate (%)': round(win_rate, 2),
        'Avg Positions': round(avg_positions, 1),
        'Total Costs (₩)': int(total_costs),
        'Trading Days': days
    }


def create_comparison_table(all_data: dict) -> pd.DataFrame:
    """
    Create comprehensive comparison table

    Args:
        all_data: Dictionary of strategy DataFrames

    Returns:
        DataFrame with metrics for all strategies
    """
    metrics_dict = {}

    for strategy_name, df in all_data.items():
        metrics = calculate_metrics(df)
        metrics_dict[strategy_name] = metrics

    comparison_df = pd.DataFrame(metrics_dict).T
    return comparison_df


def plot_cumulative_returns(all_data: dict, output_path: str):
    """
    Plot cumulative returns for all strategies

    Args:
        all_data: Dictionary of strategy DataFrames
        output_path: Path to save the plot
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Cumulative Returns Comparison: IC-Weighted vs Equal-Weighted', fontsize=16, fontweight='bold')

    percentiles = ['60th', '70th', '80th']

    for idx, percentile in enumerate(percentiles):
        ax = axes[0, idx]

        # IC-Weighted
        ic_name = f'IC-Weighted {percentile}'
        if ic_name in all_data:
            df_ic = all_data[ic_name]
            df_ic_active = df_ic[df_ic['value'] > 0].copy()
            df_ic_active['cumulative_return'] = (df_ic_active['value'] / df_ic_active['value'].iloc[0] - 1) * 100
            ax.plot(df_ic_active['date'], df_ic_active['cumulative_return'],
                   label='IC-Weighted', linewidth=2, color='blue')

        # Equal-Weighted
        eq_name = f'Equal-Weighted {percentile}'
        if eq_name in all_data:
            df_eq = all_data[eq_name]
            df_eq_active = df_eq[df_eq['value'] > 0].copy()
            df_eq_active['cumulative_return'] = (df_eq_active['value'] / df_eq_active['value'].iloc[0] - 1) * 100
            ax.plot(df_eq_active['date'], df_eq_active['cumulative_return'],
                   label='Equal-Weighted', linewidth=2, color='red', linestyle='--')

        ax.set_title(f'{percentile} Percentile Threshold', fontsize=12, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Combined plot (all strategies)
    ax_combined = axes[1, :]
    colors = ['blue', 'navy', 'darkblue', 'red', 'darkred', 'maroon']
    linestyles = ['-', '--', ':', '-', '--', ':']

    for ax_idx in range(3):
        axes[1, ax_idx].remove()

    ax_all = fig.add_subplot(2, 1, 2)

    for idx, (strategy_name, df) in enumerate(all_data.items()):
        df_active = df[df['value'] > 0].copy()
        df_active['cumulative_return'] = (df_active['value'] / df_active['value'].iloc[0] - 1) * 100
        ax_all.plot(df_active['date'], df_active['cumulative_return'],
                   label=strategy_name, linewidth=2,
                   color=colors[idx % len(colors)], linestyle=linestyles[idx % len(linestyles)])

    ax_all.set_title('All Strategies Combined', fontsize=12, fontweight='bold')
    ax_all.set_xlabel('Date')
    ax_all.set_ylabel('Cumulative Return (%)')
    ax_all.legend(loc='best', ncol=2)
    ax_all.grid(True, alpha=0.3)
    ax_all.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"💾 Saved cumulative returns chart: {output_path}")
    plt.close()


def plot_drawdown_comparison(all_data: dict, output_path: str):
    """
    Plot drawdown curves for all strategies

    Args:
        all_data: Dictionary of strategy DataFrames
        output_path: Path to save the plot
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Drawdown Comparison: IC-Weighted vs Equal-Weighted', fontsize=16, fontweight='bold')

    percentiles = ['60th', '70th', '80th']

    for idx, percentile in enumerate(percentiles):
        ax = axes[0, idx]

        # IC-Weighted
        ic_name = f'IC-Weighted {percentile}'
        if ic_name in all_data:
            df_ic = all_data[ic_name]
            df_ic_active = df_ic[df_ic['value'] > 0].copy()
            df_ic_active['returns'] = df_ic_active['value'].pct_change()
            valid_returns = df_ic_active['returns'].replace([np.inf, -np.inf], np.nan).fillna(0)
            cumulative = (1 + valid_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max * 100
            ax.plot(df_ic_active['date'], drawdown,
                   label='IC-Weighted', linewidth=2, color='blue')

        # Equal-Weighted
        eq_name = f'Equal-Weighted {percentile}'
        if eq_name in all_data:
            df_eq = all_data[eq_name]
            df_eq_active = df_eq[df_eq['value'] > 0].copy()
            df_eq_active['returns'] = df_eq_active['value'].pct_change()
            valid_returns = df_eq_active['returns'].replace([np.inf, -np.inf], np.nan).fillna(0)
            cumulative = (1 + valid_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max * 100
            ax.plot(df_eq_active['date'], drawdown,
                   label='Equal-Weighted', linewidth=2, color='red', linestyle='--')

        ax.set_title(f'{percentile} Percentile Threshold', fontsize=12, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.fill_between(ax.get_xlim(), -15, 0, alpha=0.2, color='green', label='Target DD')

    # Combined plot (all strategies)
    for ax_idx in range(3):
        axes[1, ax_idx].remove()

    ax_all = fig.add_subplot(2, 1, 2)

    colors = ['blue', 'navy', 'darkblue', 'red', 'darkred', 'maroon']
    linestyles = ['-', '--', ':', '-', '--', ':']

    for idx, (strategy_name, df) in enumerate(all_data.items()):
        df_active = df[df['value'] > 0].copy()
        df_active['returns'] = df_active['value'].pct_change()
        valid_returns = df_active['returns'].replace([np.inf, -np.inf], np.nan).fillna(0)
        cumulative = (1 + valid_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100
        ax_all.plot(df_active['date'], drawdown,
                   label=strategy_name, linewidth=2,
                   color=colors[idx % len(colors)], linestyle=linestyles[idx % len(linestyles)])

    ax_all.set_title('All Strategies Combined', fontsize=12, fontweight='bold')
    ax_all.set_xlabel('Date')
    ax_all.set_ylabel('Drawdown (%)')
    ax_all.legend(loc='best', ncol=2)
    ax_all.grid(True, alpha=0.3)
    ax_all.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax_all.fill_between(ax_all.get_xlim(), -15, 0, alpha=0.2, color='green')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"💾 Saved drawdown chart: {output_path}")
    plt.close()


def plot_risk_return_scatter(comparison_df: pd.DataFrame, output_path: str):
    """
    Plot risk-return scatter plot

    Args:
        comparison_df: Comparison metrics DataFrame
        output_path: Path to save the plot
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    # Separate IC-weighted and Equal-weighted
    ic_mask = comparison_df.index.str.contains('IC-Weighted')
    eq_mask = comparison_df.index.str.contains('Equal-Weighted')

    # Plot IC-weighted
    ax.scatter(comparison_df.loc[ic_mask, 'Volatility (%)'],
              comparison_df.loc[ic_mask, 'Annualized Return (%)'],
              s=200, alpha=0.6, c='blue', marker='o', label='IC-Weighted', edgecolors='black', linewidth=1.5)

    # Plot Equal-weighted
    ax.scatter(comparison_df.loc[eq_mask, 'Volatility (%)'],
              comparison_df.loc[eq_mask, 'Annualized Return (%)'],
              s=200, alpha=0.6, c='red', marker='s', label='Equal-Weighted', edgecolors='black', linewidth=1.5)

    # Annotate points
    for idx, row in comparison_df.iterrows():
        percentile = idx.split()[-1]
        ax.annotate(percentile,
                   (row['Volatility (%)'], row['Annualized Return (%)']),
                   xytext=(5, 5), textcoords='offset points', fontsize=9)

    ax.set_title('Risk-Return Profile: IC-Weighted vs Equal-Weighted', fontsize=14, fontweight='bold')
    ax.set_xlabel('Volatility (Annualized %)', fontsize=12)
    ax.set_ylabel('Annualized Return (%)', fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add reference lines
    ax.axhline(y=15, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Target Return (15%)')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    logger.info(f"💾 Saved risk-return scatter: {output_path}")
    plt.close()


def statistical_significance_test(all_data: dict) -> pd.DataFrame:
    """
    Perform t-test for statistical significance between strategies

    Args:
        all_data: Dictionary of strategy DataFrames

    Returns:
        DataFrame with t-test results
    """
    results = []

    percentiles = ['60th', '70th', '80th']

    for percentile in percentiles:
        ic_name = f'IC-Weighted {percentile}'
        eq_name = f'Equal-Weighted {percentile}'

        if ic_name in all_data and eq_name in all_data:
            # Get returns
            df_ic = all_data[ic_name]
            df_ic_active = df_ic[df_ic['value'] > 0].copy()
            df_ic_active['returns'] = df_ic_active['value'].pct_change()
            ic_returns = df_ic_active['returns'].replace([np.inf, -np.inf], np.nan).dropna()

            df_eq = all_data[eq_name]
            df_eq_active = df_eq[df_eq['value'] > 0].copy()
            df_eq_active['returns'] = df_eq_active['value'].pct_change()
            eq_returns = df_eq_active['returns'].replace([np.inf, -np.inf], np.nan).dropna()

            # Two-sample t-test
            t_stat, p_value = stats.ttest_ind(ic_returns, eq_returns)

            # Mean return difference
            mean_diff = (ic_returns.mean() - eq_returns.mean()) * 252 * 100  # Annualized

            results.append({
                'Percentile': percentile,
                'Mean Return Diff (ann. %)': round(mean_diff, 2),
                't-statistic': round(t_stat, 3),
                'p-value': round(p_value, 4),
                'Significant (α=0.05)': 'Yes' if p_value < 0.05 else 'No',
                'Winner': 'IC-Weighted' if mean_diff > 0 else 'Equal-Weighted'
            })

    return pd.DataFrame(results)


def main():
    """Main execution"""
    logger.info("=" * 80)
    logger.info("WEIGHTING STRATEGY COMPARISON ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    # Load data
    logger.info("[1/6] Loading backtest results...")
    all_data = load_backtest_results()

    if len(all_data) != 6:
        logger.error(f"❌ Expected 6 result files, found {len(all_data)}")
        return 1

    logger.info("")

    # Calculate metrics and create comparison table
    logger.info("[2/6] Calculating performance metrics...")
    comparison_df = create_comparison_table(all_data)

    # Print comparison table
    logger.info("")
    logger.info("=" * 80)
    logger.info("PERFORMANCE COMPARISON TABLE")
    logger.info("=" * 80)
    print(comparison_df.to_string())
    logger.info("")

    # Save comparison table to CSV
    output_dir = Path("analysis")
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / "weighting_strategy_comparison.csv"
    comparison_df.to_csv(csv_path)
    logger.info(f"💾 Saved comparison table: {csv_path}")
    logger.info("")

    # Statistical significance tests
    logger.info("[3/6] Performing statistical significance tests...")
    significance_df = statistical_significance_test(all_data)

    logger.info("")
    logger.info("=" * 80)
    logger.info("STATISTICAL SIGNIFICANCE TESTS (T-TEST)")
    logger.info("=" * 80)
    print(significance_df.to_string(index=False))
    logger.info("")

    significance_csv = output_dir / "statistical_significance.csv"
    significance_df.to_csv(significance_csv, index=False)
    logger.info(f"💾 Saved significance tests: {significance_csv}")
    logger.info("")

    # Generate visualizations
    logger.info("[4/6] Generating cumulative returns chart...")
    returns_chart = output_dir / "cumulative_returns_comparison.png"
    plot_cumulative_returns(all_data, returns_chart)
    logger.info("")

    logger.info("[5/6] Generating drawdown comparison chart...")
    drawdown_chart = output_dir / "drawdown_comparison.png"
    plot_drawdown_comparison(all_data, drawdown_chart)
    logger.info("")

    logger.info("[6/6] Generating risk-return scatter plot...")
    scatter_chart = output_dir / "risk_return_scatter.png"
    plot_risk_return_scatter(comparison_df, scatter_chart)
    logger.info("")

    # Summary
    logger.info("=" * 80)
    logger.info("ANALYSIS COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Generated outputs:")
    logger.info(f"  📊 {csv_path}")
    logger.info(f"  📊 {significance_csv}")
    logger.info(f"  📈 {returns_chart}")
    logger.info(f"  📉 {drawdown_chart}")
    logger.info(f"  🎯 {scatter_chart}")
    logger.info("")

    return 0


if __name__ == "__main__":
    sys.exit(main())
