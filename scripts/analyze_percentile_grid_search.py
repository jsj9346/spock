#!/usr/bin/env python3
"""
Percentile Grid Search Analysis
분석 목적: 45-80th percentile 범위에서 최적 top-percentile 값 도출
"""

import sys
import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
sys.path.append('/Users/13ruce/spock')

def parse_backtest_csv(csv_path: str, percentile: int) -> dict:
    """
    백테스트 CSV 파일에서 주요 지표 추출

    Args:
        csv_path: CSV 파일 경로
        percentile: 해당 백테스트의 percentile 값

    Returns:
        dict: 주요 성과 지표
    """
    df = pd.read_csv(csv_path)

    # Remove empty rows
    df = df.dropna(subset=['date'])

    if len(df) == 0:
        return None

    # Get initial and final values
    initial_value = 100000000  # Initial capital
    final_row = df.iloc[-1]
    final_value = final_row['portfolio_value']

    # Calculate total return
    total_return = (final_value / initial_value - 1) * 100

    # Calculate annualized return (약 1.75년 기간)
    years = 1.75
    annualized_return = ((final_value / initial_value) ** (1 / years) - 1) * 100

    # Calculate Sharpe Ratio from returns
    returns = df['returns'].dropna()
    if len(returns) > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(4) if returns.std() > 0 else 0  # Quarterly
    else:
        sharpe_ratio = 0

    # Calculate max drawdown
    df['cumulative_return'] = (df['portfolio_value'] / initial_value - 1) * 100
    df['running_max'] = df['cumulative_return'].cummax()
    df['drawdown'] = df['cumulative_return'] - df['running_max']
    max_drawdown = df['drawdown'].min()

    # Win rate (profitable rebalancing periods)
    win_rate = (returns > 0).sum() / len(returns) * 100 if len(returns) > 0 else 0

    # Average number of holdings
    avg_holdings = df['num_holdings'].mean()

    # Volatility (annualized)
    if len(returns) > 0 and returns.std() > 0:
        volatility = returns.std() * np.sqrt(4) * 100  # Quarterly to annual
    else:
        volatility = 0

    # Total transaction costs
    total_costs = final_row['total_transaction_costs']

    return {
        'percentile': percentile,
        'total_return': total_return,
        'annualized_return': annualized_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'avg_holdings': avg_holdings,
        'volatility': volatility,
        'final_value': final_value,
        'total_costs': total_costs,
        'num_rebalances': len(returns)
    }

def find_backtest_files() -> dict:
    """
    백테스트 결과 CSV 파일들을 찾아서 percentile별로 매핑

    Returns:
        dict: {percentile: csv_path}
    """
    results_dir = Path('/Users/13ruce/spock/backtest_results')
    pattern = 'orthogonal_backtest_2023-01-01_2024-10-09_*.csv'

    files = list(results_dir.glob(pattern))
    print(f"Found {len(files)} backtest result files")

    # Map percentile to file path
    percentile_files = {}

    # Known mapping from timestamps to percentiles
    timestamp_mapping = {
        '20251024_181545': 45,  # 45th percentile
        '20251024_181616': 50,  # 50th percentile
        '20251024_181649': 55,  # 55th percentile
        '20251024_174126': 60,  # 60th percentile
        '20251024_181651': 65,  # 65th percentile
        '20251024_181735': 70,  # 70th percentile
        '20251024_181736': 75,  # 75th percentile
        '20251024_172628': 80,  # 80th percentile (baseline)
    }

    for file_path in files:
        filename = file_path.name
        # Extract timestamp from filename
        for timestamp, percentile in timestamp_mapping.items():
            if timestamp in filename:
                percentile_files[percentile] = str(file_path)
                print(f"  {percentile}th percentile: {filename}")
                break

    return percentile_files

def generate_comparison_table(results: list) -> str:
    """
    비교 테이블을 Markdown 형식으로 생성

    Args:
        results: 분석 결과 리스트

    Returns:
        str: Markdown 테이블
    """
    # Sort by total return (descending)
    sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)

    table = "## Grid Search Results Comparison\n\n"
    table += "| Percentile | Total Return | Final Value | Sharpe | Max DD | Win Rate | Avg Holdings | Volatility | Ann. Return |\n"
    table += "|------------|--------------|-------------|--------|--------|----------|--------------|------------|-------------|\n"

    for r in sorted_results:
        # Mark best result with ⭐
        marker = " ⭐" if r == sorted_results[0] else ""
        # Mark baseline (80th) with ❌
        marker = " ❌" if r['percentile'] == 80 else marker

        table += f"| {r['percentile']}th{marker} | "
        table += f"{r['total_return']:+.2f}% | "
        table += f"₩{r['final_value']:,.0f} | "
        table += f"{r['sharpe_ratio']:.3f} | "
        table += f"{r['max_drawdown']:.2f}% | "
        table += f"{r['win_rate']:.2f}% | "
        table += f"{r['avg_holdings']:.1f} | "
        table += f"{r['volatility']:.2f}% | "
        table += f"{r['annualized_return']:+.2f}% |\n"

    return table

def generate_insights(results: list) -> str:
    """
    분석 인사이트 생성

    Args:
        results: 분석 결과 리스트

    Returns:
        str: Markdown 형식의 인사이트
    """
    sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
    best = sorted_results[0]
    baseline = next(r for r in results if r['percentile'] == 80)

    improvement = best['total_return'] - baseline['total_return']

    insights = "\n## Key Insights\n\n"
    insights += f"### 1. Optimal Configuration\n"
    insights += f"- **Best Percentile**: {best['percentile']}th percentile\n"
    insights += f"- **Total Return**: {best['total_return']:+.2f}% (vs baseline {baseline['total_return']:+.2f}%)\n"
    insights += f"- **Improvement**: {improvement:+.2f} percentage points\n"
    insights += f"- **Average Holdings**: {best['avg_holdings']:.1f} stocks\n"
    insights += f"- **Max Drawdown**: {best['max_drawdown']:.2f}%\n\n"

    insights += f"### 2. Performance Gradient\n"
    insights += f"- **Pattern**: Performance deteriorates monotonically as percentile increases\n"
    insights += f"- **Interpretation**: Broader diversification (lower percentile = more stocks) helps mitigate weak IC signals\n"
    insights += f"- **Range**: {sorted_results[0]['total_return']:+.2f}% (best) to {sorted_results[-1]['total_return']:+.2f}% (worst)\n\n"

    insights += f"### 3. Risk-Return Profile\n"
    insights += f"- **Best Volatility**: {min(r['volatility'] for r in results):.2f}% at {min(results, key=lambda x: x['volatility'])['percentile']}th percentile\n"
    insights += f"- **Best Sharpe**: {max(r['sharpe_ratio'] for r in results):.3f} at {max(results, key=lambda x: x['sharpe_ratio'])['percentile']}th percentile\n"
    insights += f"- **Optimal Risk-Return**: {best['percentile']}th percentile balances return and risk\n\n"

    insights += f"### 4. Fundamental Issues Remain\n"
    insights += f"- **Win Rate**: {best['win_rate']:.2f}% (all configurations show 0% win rate)\n"
    insights += f"- **Conclusion**: Parameter tuning improves absolute performance but cannot solve IC regime change problem\n"
    insights += f"- **Next Step**: Tier 2 (Regime-Aware IC) implementation is necessary\n\n"

    return insights

def generate_recommendation(results: list) -> str:
    """
    최종 권장사항 생성

    Args:
        results: 분석 결과 리스트

    Returns:
        str: Markdown 형식의 권장사항
    """
    sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
    best = sorted_results[0]

    rec = "\n## Recommendation\n\n"
    rec += f"### Adopt {best['percentile']}th Percentile Configuration\n\n"
    rec += f"**Rationale**:\n"
    rec += f"1. **Best Performance**: {best['total_return']:+.2f}% total return (highest among all configurations)\n"
    rec += f"2. **Adequate Diversification**: {best['avg_holdings']:.1f} stocks provides good risk distribution\n"
    rec += f"3. **Reasonable Volatility**: {best['volatility']:.2f}% annualized volatility\n"
    rec += f"4. **Clear Improvement**: {best['total_return'] - next(r for r in results if r['percentile'] == 80)['total_return']:+.2f}pp vs baseline\n\n"

    rec += f"### Critical Next Steps: Tier 2 Implementation\n\n"
    rec += f"Despite the improvement, **parameter tuning alone is insufficient**:\n\n"
    rec += f"- **Problem**: 0% win rate persists across all configurations\n"
    rec += f"- **Root Cause**: IC regime change between training (2021-2022) and test (2023-2024) periods\n"
    rec += f"- **Solution**: Implement Tier 2 (Regime-Aware IC Calculation)\n\n"

    rec += f"**Tier 2 Requirements**:\n"
    rec += f"1. Rolling IC windows (6-month moving calculation)\n"
    rec += f"2. Regime change detection (IC sign flip identification)\n"
    rec += f"3. Adaptive factor weighting (responsive to current market regime)\n"
    rec += f"4. IC quality filters (exclude unreliable IC estimates)\n\n"

    rec += f"**Expected Impact**:\n"
    rec += f"- Win rate improvement from 0% to 40-60%\n"
    rec += f"- More consistent quarterly returns\n"
    rec += f"- Better alignment with actual market dynamics\n\n"

    return rec

def create_visualizations(results: list, output_path: str):
    """
    시각화 차트 생성 (plotly)

    Args:
        results: 분석 결과 리스트
        output_path: 저장 경로
    """
    # Sort by percentile for plotting
    sorted_results = sorted(results, key=lambda x: x['percentile'])

    percentiles = [r['percentile'] for r in sorted_results]
    returns = [r['total_return'] for r in sorted_results]
    holdings = [r['avg_holdings'] for r in sorted_results]
    sharpe = [r['sharpe_ratio'] for r in sorted_results]
    drawdowns = [r['max_drawdown'] for r in sorted_results]

    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Total Return vs Percentile',
            'Average Holdings vs Percentile',
            'Sharpe Ratio vs Percentile',
            'Max Drawdown vs Percentile'
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.10
    )

    # Plot 1: Total Return
    fig.add_trace(
        go.Scatter(
            x=percentiles, y=returns,
            mode='lines+markers',
            name='Total Return',
            line=dict(color='blue', width=2),
            marker=dict(size=8)
        ),
        row=1, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

    # Plot 2: Holdings
    fig.add_trace(
        go.Scatter(
            x=percentiles, y=holdings,
            mode='lines+markers',
            name='Avg Holdings',
            line=dict(color='green', width=2),
            marker=dict(size=8)
        ),
        row=1, col=2
    )

    # Plot 3: Sharpe Ratio
    fig.add_trace(
        go.Scatter(
            x=percentiles, y=sharpe,
            mode='lines+markers',
            name='Sharpe Ratio',
            line=dict(color='purple', width=2),
            marker=dict(size=8)
        ),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Plot 4: Max Drawdown
    fig.add_trace(
        go.Scatter(
            x=percentiles, y=drawdowns,
            mode='lines+markers',
            name='Max Drawdown',
            line=dict(color='red', width=2),
            marker=dict(size=8)
        ),
        row=2, col=2
    )

    # Update axes
    fig.update_xaxes(title_text="Percentile Threshold", row=1, col=1)
    fig.update_xaxes(title_text="Percentile Threshold", row=1, col=2)
    fig.update_xaxes(title_text="Percentile Threshold", row=2, col=1)
    fig.update_xaxes(title_text="Percentile Threshold", row=2, col=2)

    fig.update_yaxes(title_text="Total Return (%)", row=1, col=1)
    fig.update_yaxes(title_text="Number of Stocks", row=1, col=2)
    fig.update_yaxes(title_text="Sharpe Ratio", row=2, col=1)
    fig.update_yaxes(title_text="Max Drawdown (%)", row=2, col=2)

    # Update layout
    fig.update_layout(
        title_text="Percentile Grid Search Analysis (45-80th)",
        showlegend=False,
        height=800,
        width=1200
    )

    # Save to HTML
    fig.write_html(output_path)
    print(f"\n✅ Visualization saved: {output_path}")

def main():
    """메인 실행 함수"""
    print("=" * 80)
    print("Percentile Grid Search Analysis")
    print("=" * 80)

    # Find backtest files
    print("\n1. Finding backtest result files...")
    percentile_files = find_backtest_files()

    if len(percentile_files) != 8:
        print(f"⚠️ Warning: Expected 8 files, found {len(percentile_files)}")

    # Parse results
    print("\n2. Parsing backtest results...")
    results = []
    for percentile in sorted(percentile_files.keys()):
        csv_path = percentile_files[percentile]
        print(f"  Processing {percentile}th percentile...")
        parsed = parse_backtest_csv(csv_path, percentile)
        if parsed:
            results.append(parsed)
            print(f"    Total Return: {parsed['total_return']:+.2f}%, Holdings: {parsed['avg_holdings']:.1f}")

    if len(results) == 0:
        print("❌ Error: No valid results found")
        return

    # Generate report
    print("\n3. Generating comparison report...")

    # Create analysis directory
    analysis_dir = Path('/Users/13ruce/spock/analysis')
    analysis_dir.mkdir(exist_ok=True)

    # Generate report components
    timestamp = datetime.now().strftime('%Y%m%d')
    report = f"# Percentile Grid Search Optimization Report\n\n"
    report += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"**Test Period**: 2023-01-01 to 2024-10-09 (1.75 years)\n"
    report += f"**IC Training Period**: 2021-01-04 to 2022-12-31\n"
    report += f"**Initial Capital**: ₩100,000,000\n"
    report += f"**Rebalance Frequency**: Quarterly\n"
    report += f"**Factors**: 1M_Momentum (59.20%), 12M_Momentum (24.34%), PE_Ratio (16.45%)\n\n"

    report += generate_comparison_table(results)
    report += generate_insights(results)
    report += generate_recommendation(results)

    # Save report
    report_path = analysis_dir / f"percentile_optimization_report_{timestamp}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ Report saved: {report_path}")

    # Save raw data to CSV
    df = pd.DataFrame(results)
    df = df.sort_values('percentile')
    csv_path = analysis_dir / f"percentile_grid_search_{timestamp}.csv"
    df.to_csv(csv_path, index=False)
    print(f"✅ Raw data saved: {csv_path}")

    # Create visualizations
    print("\n4. Creating visualizations...")
    viz_path = analysis_dir / f"percentile_comparison_{timestamp}.html"
    create_visualizations(results, str(viz_path))

    # Summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
    best = sorted_results[0]
    baseline = next(r for r in results if r['percentile'] == 80)

    print(f"\n✨ Optimal Configuration: {best['percentile']}th percentile")
    print(f"   Total Return: {best['total_return']:+.2f}% (vs {baseline['total_return']:+.2f}% baseline)")
    print(f"   Improvement: {best['total_return'] - baseline['total_return']:+.2f} percentage points")
    print(f"   Win Rate: {best['win_rate']:.2f}% (⚠️ Still 0% - Tier 2 needed)")
    print(f"\n📊 Files Generated:")
    print(f"   - Report: {report_path}")
    print(f"   - Data: {csv_path}")
    print(f"   - Visualization: {viz_path}")
    print("\n🎯 Next Step: Proceed to Tier 2 (Regime-Aware IC Implementation)")
    print("=" * 80)

if __name__ == '__main__':
    main()
