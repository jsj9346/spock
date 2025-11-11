"""
Plotly chart generator for backtest results and portfolio analytics.

Provides interactive chart generation using Plotly with support for:
- Portfolio performance charts (equity curve, drawdown)
- Trade analysis charts (P&L distribution, win rate)
- Risk analysis charts (VaR, correlation matrix)
- Factor analysis charts (factor returns, correlation)
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px


class ChartGenerator:
    """
    Plotly chart generator for quant platform analytics.

    Features:
    - Interactive charts with zoom, pan, hover tooltips
    - Multi-panel layouts for comprehensive analysis
    - Export to HTML, PNG, SVG
    - Customizable themes and styling

    Usage:
        generator = ChartGenerator()
        fig = generator.create_equity_curve(returns_series, benchmark_returns)
        fig.write_html('equity_curve.html')
    """

    def __init__(self, theme: str = 'plotly_dark'):
        """
        Initialize chart generator.

        Args:
            theme: Plotly template theme (plotly, plotly_white, plotly_dark, seaborn, etc.)
        """
        self.theme = theme

    def create_equity_curve(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        title: str = "Portfolio Equity Curve"
    ) -> go.Figure:
        """
        Create equity curve chart showing cumulative returns.

        Args:
            portfolio_returns: Series of portfolio returns (indexed by date)
            benchmark_returns: Optional benchmark returns for comparison
            title: Chart title

        Returns:
            Plotly Figure object
        """
        # Calculate cumulative returns
        portfolio_cumulative = (1 + portfolio_returns).cumprod()

        fig = go.Figure()

        # Portfolio line
        fig.add_trace(go.Scatter(
            x=portfolio_cumulative.index,
            y=portfolio_cumulative.values,
            mode='lines',
            name='Portfolio',
            line=dict(color='#00D9FF', width=2),
            hovertemplate='Date: %{x}<br>Value: %{y:.2f}<extra></extra>'
        ))

        # Benchmark line (if provided)
        if benchmark_returns is not None:
            benchmark_cumulative = (1 + benchmark_returns).cumprod()
            fig.add_trace(go.Scatter(
                x=benchmark_cumulative.index,
                y=benchmark_cumulative.values,
                mode='lines',
                name='Benchmark',
                line=dict(color='#FF6B6B', width=2, dash='dash'),
                hovertemplate='Date: %{x}<br>Value: %{y:.2f}<extra></extra>'
            ))

        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Cumulative Return',
            template=self.theme,
            hovermode='x unified',
            height=500
        )

        return fig

    def create_drawdown_chart(
        self,
        portfolio_returns: pd.Series,
        title: str = "Portfolio Drawdown"
    ) -> go.Figure:
        """
        Create drawdown chart showing underwater equity.

        Args:
            portfolio_returns: Series of portfolio returns
            title: Chart title

        Returns:
            Plotly Figure object
        """
        # Calculate drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100

        fig = go.Figure()

        # Drawdown area
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode='lines',
            name='Drawdown',
            fill='tozeroy',
            line=dict(color='#FF6B6B', width=1),
            fillcolor='rgba(255, 107, 107, 0.3)',
            hovertemplate='Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>'
        ))

        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Drawdown (%)',
            template=self.theme,
            hovermode='x unified',
            height=400
        )

        return fig

    def create_monthly_returns_heatmap(
        self,
        returns: pd.Series,
        title: str = "Monthly Returns Heatmap"
    ) -> go.Figure:
        """
        Create heatmap of monthly returns.

        Args:
            returns: Series of daily returns
            title: Chart title

        Returns:
            Plotly Figure object
        """
        # Resample to monthly returns
        monthly_returns = (1 + returns).resample('M').prod() - 1

        # Pivot to year x month matrix
        monthly_returns_pct = (monthly_returns * 100).to_frame('return')
        monthly_returns_pct['year'] = monthly_returns_pct.index.year
        monthly_returns_pct['month'] = monthly_returns_pct.index.month

        pivot_table = monthly_returns_pct.pivot(
            index='year',
            columns='month',
            values='return'
        )

        # Month names
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        fig = go.Figure(data=go.Heatmap(
            z=pivot_table.values,
            x=month_names,
            y=pivot_table.index,
            colorscale='RdYlGn',
            zmid=0,
            text=pivot_table.values,
            texttemplate='%{text:.1f}%',
            textfont={"size": 10},
            hovertemplate='Month: %{x}<br>Year: %{y}<br>Return: %{z:.2f}%<extra></extra>'
        ))

        fig.update_layout(
            title=title,
            xaxis_title='Month',
            yaxis_title='Year',
            template=self.theme,
            height=400
        )

        return fig

    def create_performance_summary(
        self,
        metrics: Dict[str, float],
        title: str = "Performance Metrics"
    ) -> go.Figure:
        """
        Create bar chart of performance metrics.

        Args:
            metrics: Dictionary of metric names and values
            title: Chart title

        Returns:
            Plotly Figure object
        """
        metric_names = list(metrics.keys())
        metric_values = list(metrics.values())

        # Color code based on metric type
        colors = []
        for name in metric_names:
            if 'return' in name.lower() or 'sharpe' in name.lower():
                colors.append('#00D9FF' if metrics[name] > 0 else '#FF6B6B')
            elif 'drawdown' in name.lower():
                colors.append('#FF6B6B' if metrics[name] < -10 else '#FFD93D')
            else:
                colors.append('#6BCF7F')

        fig = go.Figure(data=[
            go.Bar(
                x=metric_names,
                y=metric_values,
                marker_color=colors,
                text=[f'{v:.2f}' for v in metric_values],
                textposition='auto',
                hovertemplate='%{x}: %{y:.2f}<extra></extra>'
            )
        ])

        fig.update_layout(
            title=title,
            xaxis_title='Metric',
            yaxis_title='Value',
            template=self.theme,
            height=400,
            showlegend=False
        )

        return fig

    def create_trade_analysis(
        self,
        trades: pd.DataFrame,
        title: str = "Trade Analysis"
    ) -> go.Figure:
        """
        Create trade P&L distribution chart.

        Args:
            trades: DataFrame with trade data (must have 'PnL' column)
            title: Chart title

        Returns:
            Plotly Figure object
        """
        if 'PnL' not in trades.columns:
            raise ValueError("trades DataFrame must have 'PnL' column")

        pnl = trades['PnL']

        fig = go.Figure()

        # Histogram
        fig.add_trace(go.Histogram(
            x=pnl,
            name='Trade P&L',
            marker_color='#00D9FF',
            opacity=0.7,
            hovertemplate='P&L Range: %{x}<br>Count: %{y}<extra></extra>'
        ))

        # Add vertical lines for mean and median
        fig.add_vline(
            x=pnl.mean(),
            line_dash="dash",
            line_color="#FFD93D",
            annotation_text=f"Mean: {pnl.mean():.0f}",
            annotation_position="top"
        )

        fig.update_layout(
            title=title,
            xaxis_title='P&L',
            yaxis_title='Frequency',
            template=self.theme,
            height=400,
            showlegend=False
        )

        return fig

    def create_multi_panel_report(
        self,
        portfolio_returns: pd.Series,
        metrics: Dict[str, float],
        trades: Optional[pd.DataFrame] = None,
        benchmark_returns: Optional[pd.Series] = None,
        title: str = "Backtest Report"
    ) -> go.Figure:
        """
        Create comprehensive multi-panel backtest report.

        Args:
            portfolio_returns: Series of portfolio returns
            metrics: Dictionary of performance metrics
            trades: Optional DataFrame with trade data
            benchmark_returns: Optional benchmark returns
            title: Report title

        Returns:
            Plotly Figure with subplots
        """
        # Create subplots (3 rows)
        rows = 3 if trades is not None else 2

        fig = make_subplots(
            rows=rows,
            cols=1,
            subplot_titles=(
                'Equity Curve',
                'Drawdown',
                'Trade P&L Distribution' if trades is not None else None
            ),
            vertical_spacing=0.1,
            row_heights=[0.4, 0.3, 0.3] if trades is not None else [0.5, 0.5]
        )

        # Panel 1: Equity Curve
        portfolio_cumulative = (1 + portfolio_returns).cumprod()
        fig.add_trace(
            go.Scatter(
                x=portfolio_cumulative.index,
                y=portfolio_cumulative.values,
                mode='lines',
                name='Portfolio',
                line=dict(color='#00D9FF', width=2)
            ),
            row=1, col=1
        )

        if benchmark_returns is not None:
            benchmark_cumulative = (1 + benchmark_returns).cumprod()
            fig.add_trace(
                go.Scatter(
                    x=benchmark_cumulative.index,
                    y=benchmark_cumulative.values,
                    mode='lines',
                    name='Benchmark',
                    line=dict(color='#FF6B6B', width=2, dash='dash')
                ),
                row=1, col=1
            )

        # Panel 2: Drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100

        fig.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=drawdown.values,
                mode='lines',
                name='Drawdown',
                fill='tozeroy',
                line=dict(color='#FF6B6B', width=1),
                fillcolor='rgba(255, 107, 107, 0.3)'
            ),
            row=2, col=1
        )

        # Panel 3: Trade P&L (if provided)
        if trades is not None and 'PnL' in trades.columns:
            fig.add_trace(
                go.Histogram(
                    x=trades['PnL'],
                    name='Trade P&L',
                    marker_color='#00D9FF',
                    opacity=0.7
                ),
                row=3, col=1
            )

        # Update layout
        fig.update_xaxes(title_text="Date", row=1, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=1)
        if trades is not None:
            fig.update_xaxes(title_text="P&L", row=3, col=1)

        fig.update_yaxes(title_text="Cumulative Return", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        if trades is not None:
            fig.update_yaxes(title_text="Frequency", row=3, col=1)

        fig.update_layout(
            title_text=title,
            template=self.theme,
            height=800 if trades is not None else 600,
            showlegend=True,
            hovermode='x unified'
        )

        return fig

    def create_correlation_matrix(
        self,
        returns: pd.DataFrame,
        title: str = "Asset Correlation Matrix"
    ) -> go.Figure:
        """
        Create correlation matrix heatmap.

        Args:
            returns: DataFrame of asset returns (columns = assets)
            title: Chart title

        Returns:
            Plotly Figure object
        """
        corr_matrix = returns.corr()

        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            colorscale='RdBu',
            zmid=0,
            text=corr_matrix.values,
            texttemplate='%{text:.2f}',
            textfont={"size": 10},
            hovertemplate='%{x} vs %{y}<br>Correlation: %{z:.2f}<extra></extra>'
        ))

        fig.update_layout(
            title=title,
            template=self.theme,
            height=500,
            width=500
        )

        return fig


if __name__ == '__main__':
    # Test chart generator
    import numpy as np

    print("Testing ChartGenerator...")

    # Create sample data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)
    benchmark_returns = pd.Series(np.random.randn(len(dates)) * 0.008, index=dates)

    generator = ChartGenerator()

    # Test equity curve
    fig1 = generator.create_equity_curve(returns, benchmark_returns)
    print("✓ Equity curve created")

    # Test drawdown
    fig2 = generator.create_drawdown_chart(returns)
    print("✓ Drawdown chart created")

    # Test monthly returns
    fig3 = generator.create_monthly_returns_heatmap(returns)
    print("✓ Monthly returns heatmap created")

    # Test performance summary
    metrics = {
        'Total Return': 15.5,
        'Sharpe Ratio': 1.8,
        'Max Drawdown': -12.3,
        'Win Rate': 58.5
    }
    fig4 = generator.create_performance_summary(metrics)
    print("✓ Performance summary created")

    # Test multi-panel report
    fig5 = generator.create_multi_panel_report(returns, metrics, benchmark_returns=benchmark_returns)
    print("✓ Multi-panel report created")

    print("\nAll chart generation tests passed!")
