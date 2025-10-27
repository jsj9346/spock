#!/usr/bin/env python3
"""
IC Chart Generator - Interactive Plotly Visualizations

Provides comprehensive IC (Information Coefficient) visualization capabilities:
1. IC time series line charts with rolling averages
2. Monthly IC heatmaps (calendar-style)
3. IC distribution histograms
4. Rolling IC average charts for regime identification
5. Multi-factor comparison dashboards

Designed for Streamlit dashboard integration with multi-factor extensibility.

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
from typing import List, Optional, Dict, Tuple
from datetime import date

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


class ICChartGenerator:
    """
    Interactive IC Visualization Engine using Plotly

    Supports multi-factor IC visualization with extensible design for
    future momentum/quality factors.

    Features:
    - Interactive charts (hover, zoom, pan, range selector)
    - Multi-factor support (automatic color assignment)
    - Statistical annotations (mean IC, significance markers)
    - Export to HTML (interactive) and PNG (static)

    Usage:
        generator = ICChartGenerator(theme='plotly_white')
        fig = generator.plot_ic_time_series(ic_df)
        fig.show()  # or fig.write_html('chart.html')
    """

    # Default color palette for up to 10 factors
    DEFAULT_COLORS = [
        '#1f77b4',  # Blue
        '#ff7f0e',  # Orange
        '#2ca02c',  # Green
        '#d62728',  # Red
        '#9467bd',  # Purple
        '#8c564b',  # Brown
        '#e377c2',  # Pink
        '#7f7f7f',  # Gray
        '#bcbd22',  # Olive
        '#17becf'   # Cyan
    ]

    def __init__(
        self,
        theme: str = 'plotly_white',
        color_palette: Optional[List[str]] = None
    ):
        """
        Initialize ICChartGenerator

        Args:
            theme: Plotly theme (plotly, plotly_white, plotly_dark, ggplot2, seaborn, simple_white)
            color_palette: Custom color palette for factors (default: DEFAULT_COLORS)
        """
        self.theme = theme
        self.color_palette = color_palette or self.DEFAULT_COLORS

    def plot_ic_time_series(
        self,
        ic_df: pd.DataFrame,
        rolling_window: int = 20,
        title: Optional[str] = None,
        show_significance: bool = True,
        height: int = 600
    ) -> go.Figure:
        """
        Interactive IC time series line chart with rolling average

        Args:
            ic_df: DataFrame with columns [date, factor_name, ic, p_value, is_significant, num_stocks]
            rolling_window: Window size for moving average (default: 20 days)
            title: Custom chart title (default: auto-generated)
            show_significance: Highlight statistically significant IC values (p < 0.05)
            height: Chart height in pixels

        Returns:
            plotly.graph_objects.Figure

        Example:
            >>> ic_df = pd.read_sql("SELECT * FROM ic_time_series WHERE region='KR'", conn)
            >>> fig = generator.plot_ic_time_series(ic_df)
            >>> fig.write_html('ic_timeseries.html')
        """
        if ic_df.empty:
            logger.warning("Empty IC DataFrame provided")
            return go.Figure()

        # Ensure date column is datetime
        ic_df['date'] = pd.to_datetime(ic_df['date'])
        ic_df = ic_df.sort_values('date')

        # Get unique factors
        factors = ic_df['factor_name'].unique()

        # Create figure
        fig = go.Figure()

        # Add IC line for each factor
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor].copy()
            color = self.color_palette[i % len(self.color_palette)]

            # Main IC line
            fig.add_trace(go.Scatter(
                x=factor_data['date'],
                y=factor_data['ic'],
                mode='lines+markers',
                name=factor,
                line=dict(color=color, width=2),
                marker=dict(
                    size=6,
                    color=color,
                    opacity=0.7,
                    line=dict(width=1, color='white')
                ),
                hovertemplate=(
                    f'<b>{factor}</b><br>' +
                    'Date: %{x|%Y-%m-%d}<br>' +
                    'IC: %{y:.4f}<br>' +
                    '<extra></extra>'
                )
            ))

            # Add rolling average
            if len(factor_data) >= rolling_window:
                rolling_ic = factor_data['ic'].rolling(window=rolling_window, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=factor_data['date'],
                    y=rolling_ic,
                    mode='lines',
                    name=f'{factor} ({rolling_window}d MA)',
                    line=dict(color=color, width=3, dash='dash'),
                    opacity=0.6,
                    hovertemplate=(
                        f'<b>{factor} Rolling Avg</b><br>' +
                        'Date: %{x|%Y-%m-%d}<br>' +
                        'IC (MA): %{y:.4f}<br>' +
                        '<extra></extra>'
                    )
                ))

            # Highlight significant IC values
            if show_significance and 'is_significant' in factor_data.columns:
                sig_data = factor_data[factor_data['is_significant'] == True]
                if not sig_data.empty:
                    fig.add_trace(go.Scatter(
                        x=sig_data['date'],
                        y=sig_data['ic'],
                        mode='markers',
                        name=f'{factor} (p<0.05)',
                        marker=dict(
                            size=10,
                            color=color,
                            symbol='star',
                            line=dict(width=2, color='gold')
                        ),
                        hovertemplate=(
                            f'<b>{factor} (Significant)</b><br>' +
                            'Date: %{x|%Y-%m-%d}<br>' +
                            'IC: %{y:.4f}<br>' +
                            'p-value < 0.05<br>' +
                            '<extra></extra>'
                        )
                    ))

        # Add zero line
        fig.add_hline(
            y=0,
            line=dict(color='black', width=1, dash='dash'),
            annotation_text='IC = 0',
            annotation_position='right'
        )

        # Update layout
        default_title = f'Information Coefficient (IC) Time Series<br><sub>Period: {ic_df["date"].min():%Y-%m-%d} to {ic_df["date"].max():%Y-%m-%d}</sub>'
        fig.update_layout(
            title=dict(
                text=title or default_title,
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='Date',
                showgrid=True,
                gridcolor='lightgray',
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label='1m', step='month', stepmode='backward'),
                        dict(count=3, label='3m', step='month', stepmode='backward'),
                        dict(count=6, label='6m', step='month', stepmode='backward'),
                        dict(step='all', label='All')
                    ])
                ),
                rangeslider=dict(visible=True),
                type='date'
            ),
            yaxis=dict(
                title='Information Coefficient (IC)',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor='black'
            ),
            hovermode='x unified',
            template=self.theme,
            height=height,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )

        return fig

    def plot_monthly_ic_heatmap(
        self,
        ic_df: pd.DataFrame,
        factor_name: str,
        title: Optional[str] = None,
        height: int = 600
    ) -> go.Figure:
        """
        Monthly IC heatmap (calendar-style visualization)

        Args:
            ic_df: DataFrame with IC time series
            factor_name: Which factor to visualize
            title: Custom chart title
            height: Chart height in pixels

        Returns:
            plotly.graph_objects.Figure
        """
        if ic_df.empty:
            logger.warning("Empty IC DataFrame provided")
            return go.Figure()

        # Filter for specific factor
        factor_data = ic_df[ic_df['factor_name'] == factor_name].copy()

        if factor_data.empty:
            logger.warning(f"No data found for factor: {factor_name}")
            return go.Figure()

        # Ensure date column is datetime
        factor_data['date'] = pd.to_datetime(factor_data['date'])

        # Extract month and year
        factor_data['year_month'] = factor_data['date'].dt.to_period('M').astype(str)
        factor_data['day'] = factor_data['date'].dt.day

        # Pivot to create heatmap data
        pivot_data = factor_data.pivot_table(
            values='ic',
            index='year_month',
            columns='day',
            aggfunc='mean'
        )

        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=pivot_data.values,
            x=pivot_data.columns,
            y=pivot_data.index,
            colorscale='RdYlGn',
            zmid=0,
            text=np.round(pivot_data.values, 3),
            texttemplate='%{text}',
            textfont=dict(size=10),
            hovertemplate=(
                'Month: %{y}<br>' +
                'Day: %{x}<br>' +
                'IC: %{z:.4f}<br>' +
                '<extra></extra>'
            ),
            colorbar=dict(
                title='IC',
                thickness=15,
                len=0.7
            )
        ))

        # Update layout
        default_title = f'{factor_name} - Monthly IC Heatmap'
        fig.update_layout(
            title=dict(
                text=title or default_title,
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='Day of Month',
                showgrid=False
            ),
            yaxis=dict(
                title='Month',
                showgrid=False
            ),
            template=self.theme,
            height=height
        )

        return fig

    def plot_ic_distribution(
        self,
        ic_df: pd.DataFrame,
        title: Optional[str] = None,
        height: int = 600
    ) -> go.Figure:
        """
        IC distribution histogram with statistical annotations

        Args:
            ic_df: DataFrame with IC values
            title: Custom chart title
            height: Chart height in pixels

        Returns:
            plotly.graph_objects.Figure
        """
        if ic_df.empty:
            logger.warning("Empty IC DataFrame provided")
            return go.Figure()

        # Get unique factors
        factors = ic_df['factor_name'].unique()

        # Create figure
        fig = go.Figure()

        # Add histogram for each factor
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor]
            color = self.color_palette[i % len(self.color_palette)]

            # Calculate statistics
            mean_ic = factor_data['ic'].mean()
            std_ic = factor_data['ic'].std()
            pct_positive = (factor_data['ic'] > 0).sum() / len(factor_data) * 100
            pct_significant = (factor_data['is_significant'] == True).sum() / len(factor_data) * 100 if 'is_significant' in factor_data.columns else 0

            fig.add_trace(go.Histogram(
                x=factor_data['ic'],
                name=factor,
                marker=dict(
                    color=color,
                    opacity=0.7,
                    line=dict(color='white', width=1)
                ),
                nbinsx=30,
                hovertemplate=(
                    f'<b>{factor}</b><br>' +
                    'IC Range: %{x}<br>' +
                    'Count: %{y}<br>' +
                    '<extra></extra>'
                ),
                legendgroup=factor,
                showlegend=True
            ))

            # Add mean line
            fig.add_vline(
                x=mean_ic,
                line=dict(color=color, width=2, dash='dash'),
                annotation_text=f'{factor} Mean: {mean_ic:.4f}',
                annotation_position='top',
                legendgroup=factor,
                showlegend=False
            )

        # Add zero line
        fig.add_vline(
            x=0,
            line=dict(color='black', width=2, dash='solid'),
            annotation_text='IC = 0',
            annotation_position='bottom'
        )

        # Update layout
        default_title = 'IC Distribution'
        fig.update_layout(
            title=dict(
                text=title or default_title,
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='Information Coefficient (IC)',
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title='Frequency',
                showgrid=True,
                gridcolor='lightgray'
            ),
            barmode='overlay',
            template=self.theme,
            height=height,
            legend=dict(
                orientation='v',
                yanchor='top',
                y=1,
                xanchor='right',
                x=1
            )
        )

        return fig

    def plot_rolling_ic_average(
        self,
        ic_df: pd.DataFrame,
        window: int = 20,
        title: Optional[str] = None,
        height: int = 600
    ) -> go.Figure:
        """
        Rolling IC average chart for regime identification

        Args:
            ic_df: DataFrame with IC time series
            window: Rolling window size (default: 20 days)
            title: Custom chart title
            height: Chart height in pixels

        Returns:
            plotly.graph_objects.Figure
        """
        if ic_df.empty:
            logger.warning("Empty IC DataFrame provided")
            return go.Figure()

        # Ensure date column is datetime
        ic_df['date'] = pd.to_datetime(ic_df['date'])
        ic_df = ic_df.sort_values('date')

        # Get unique factors
        factors = ic_df['factor_name'].unique()

        # Create figure
        fig = go.Figure()

        # Add rolling IC for each factor
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor].copy()
            color = self.color_palette[i % len(self.color_palette)]

            if len(factor_data) >= window:
                rolling_ic = factor_data['ic'].rolling(window=window, min_periods=1).mean()

                fig.add_trace(go.Scatter(
                    x=factor_data['date'],
                    y=rolling_ic,
                    mode='lines',
                    name=f'{factor} ({window}d MA)',
                    line=dict(color=color, width=3),
                    fill='tozeroy',
                    fillcolor=f'rgba{tuple(list(bytes.fromhex(color[1:])) + [0.2])}',
                    hovertemplate=(
                        f'<b>{factor}</b><br>' +
                        'Date: %{x|%Y-%m-%d}<br>' +
                        'Rolling IC: %{y:.4f}<br>' +
                        '<extra></extra>'
                    )
                ))

        # Add threshold lines
        fig.add_hline(
            y=0,
            line=dict(color='black', width=2, dash='solid'),
            annotation_text='IC = 0',
            annotation_position='right'
        )

        fig.add_hline(
            y=0.05,
            line=dict(color='green', width=1, dash='dot'),
            annotation_text='Threshold: +0.05',
            annotation_position='right',
            opacity=0.5
        )

        fig.add_hline(
            y=-0.05,
            line=dict(color='red', width=1, dash='dot'),
            annotation_text='Threshold: -0.05',
            annotation_position='right',
            opacity=0.5
        )

        # Update layout
        default_title = f'Rolling IC Average ({window}-Day Window)'
        fig.update_layout(
            title=dict(
                text=title or default_title,
                font=dict(size=18, family='Arial, sans-serif')
            ),
            xaxis=dict(
                title='Date',
                showgrid=True,
                gridcolor='lightgray',
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label='1m', step='month', stepmode='backward'),
                        dict(count=3, label='3m', step='month', stepmode='backward'),
                        dict(count=6, label='6m', step='month', stepmode='backward'),
                        dict(step='all', label='All')
                    ])
                ),
                type='date'
            ),
            yaxis=dict(
                title='Rolling IC Average',
                showgrid=True,
                gridcolor='lightgray',
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor='black'
            ),
            hovermode='x unified',
            template=self.theme,
            height=height,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )

        return fig

    def create_multi_factor_dashboard(
        self,
        ic_df: pd.DataFrame,
        rolling_window: int = 20,
        title: Optional[str] = None,
        height: int = 1000
    ) -> go.Figure:
        """
        Combined dashboard with all IC visualizations (2x2 grid)

        Creates subplot grid:
        - Top-left: IC time series with rolling average
        - Top-right: IC distribution histogram
        - Bottom-left: Rolling IC average
        - Bottom-right: Monthly heatmap (first factor)

        Args:
            ic_df: DataFrame with multi-factor IC data
            rolling_window: Window for moving averages
            title: Dashboard title
            height: Total dashboard height

        Returns:
            plotly.graph_objects.Figure
        """
        if ic_df.empty:
            logger.warning("Empty IC DataFrame provided")
            return go.Figure()

        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'IC Time Series',
                'IC Distribution',
                f'Rolling IC Average ({rolling_window}d)',
                'Monthly IC Heatmap (First Factor)'
            ),
            vertical_spacing=0.12,
            horizontal_spacing=0.1,
            specs=[
                [{'type': 'scatter'}, {'type': 'histogram'}],
                [{'type': 'scatter'}, {'type': 'heatmap'}]
            ]
        )

        # Ensure date column is datetime
        ic_df['date'] = pd.to_datetime(ic_df['date'])
        ic_df = ic_df.sort_values('date')

        # Get unique factors
        factors = ic_df['factor_name'].unique()

        # Subplot 1: IC Time Series
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor].copy()
            color = self.color_palette[i % len(self.color_palette)]

            # Main IC line
            fig.add_trace(go.Scatter(
                x=factor_data['date'],
                y=factor_data['ic'],
                mode='lines+markers',
                name=factor,
                line=dict(color=color, width=2),
                marker=dict(size=4, color=color),
                showlegend=True,
                legendgroup=factor
            ), row=1, col=1)

            # Rolling average
            if len(factor_data) >= rolling_window:
                rolling_ic = factor_data['ic'].rolling(window=rolling_window, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=factor_data['date'],
                    y=rolling_ic,
                    mode='lines',
                    name=f'{factor} MA',
                    line=dict(color=color, width=2, dash='dash'),
                    showlegend=False,
                    legendgroup=factor
                ), row=1, col=1)

        # Subplot 2: IC Distribution
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor]
            color = self.color_palette[i % len(self.color_palette)]

            fig.add_trace(go.Histogram(
                x=factor_data['ic'],
                name=factor,
                marker=dict(color=color, opacity=0.7),
                nbinsx=20,
                showlegend=False,
                legendgroup=factor
            ), row=1, col=2)

        # Subplot 3: Rolling IC Average
        for i, factor in enumerate(factors):
            factor_data = ic_df[ic_df['factor_name'] == factor].copy()
            color = self.color_palette[i % len(self.color_palette)]

            if len(factor_data) >= rolling_window:
                rolling_ic = factor_data['ic'].rolling(window=rolling_window, min_periods=1).mean()

                fig.add_trace(go.Scatter(
                    x=factor_data['date'],
                    y=rolling_ic,
                    mode='lines',
                    name=factor,
                    line=dict(color=color, width=3),
                    showlegend=False,
                    legendgroup=factor
                ), row=2, col=1)

        # Subplot 4: Monthly Heatmap (first factor only)
        if len(factors) > 0:
            first_factor = factors[0]
            factor_data = ic_df[ic_df['factor_name'] == first_factor].copy()
            factor_data['year_month'] = factor_data['date'].dt.to_period('M').astype(str)
            factor_data['day'] = factor_data['date'].dt.day

            pivot_data = factor_data.pivot_table(
                values='ic',
                index='year_month',
                columns='day',
                aggfunc='mean'
            )

            fig.add_trace(go.Heatmap(
                z=pivot_data.values,
                x=pivot_data.columns,
                y=pivot_data.index,
                colorscale='RdYlGn',
                zmid=0,
                showscale=True,
                showlegend=False
            ), row=2, col=2)

        # Update layout
        default_title = f'IC Analysis Dashboard<br><sub>Period: {ic_df["date"].min():%Y-%m-%d} to {ic_df["date"].max():%Y-%m-%d}</sub>'
        fig.update_layout(
            title=dict(
                text=title or default_title,
                font=dict(size=20, family='Arial, sans-serif'),
                x=0.5,
                xanchor='center'
            ),
            template=self.theme,
            height=height,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.05,
                xanchor='center',
                x=0.5
            )
        )

        # Update axes
        fig.update_xaxes(title_text='Date', row=1, col=1)
        fig.update_yaxes(title_text='IC', row=1, col=1)

        fig.update_xaxes(title_text='IC', row=1, col=2)
        fig.update_yaxes(title_text='Frequency', row=1, col=2)

        fig.update_xaxes(title_text='Date', row=2, col=1)
        fig.update_yaxes(title_text='Rolling IC', row=2, col=1)

        fig.update_xaxes(title_text='Day', row=2, col=2)
        fig.update_yaxes(title_text='Month', row=2, col=2)

        return fig
