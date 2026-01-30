# mcp_server/generators/return_comparison_generator.py
"""
Return Comparison Chart Generator for MCP Server

Generates multi-stock return comparison charts in Google Finance style:
- Clean, minimal design with white background
- Percentage-based Y-axis (0% as baseline)
- Clear color-coded lines for each stock
- Simple legend with stock name and return percentage

Author: Spock MCP Server
Date: 2026-01-20
"""

from typing import List, Tuple, Optional, Dict, Any
from io import BytesIO
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import matplotlib
import matplotlib.font_manager as fm
matplotlib.use('Agg')  # Non-interactive backend for server use

# Configure Korean font support
def _setup_korean_font():
    """Setup Korean font for matplotlib."""
    # Try to find Korean fonts in order of preference
    korean_fonts = [
        'AppleGothic',           # macOS
        'Apple SD Gothic Neo',   # macOS
        'Malgun Gothic',         # Windows
        'NanumGothic',           # Linux/Common
        'NanumBarunGothic',
        'Noto Sans CJK KR',
        'Source Han Sans KR',
    ]

    # Get available fonts
    available_fonts = set(f.name for f in fm.fontManager.ttflist)

    # Find first available Korean font
    for font_name in korean_fonts:
        if font_name in available_fonts:
            plt.rcParams['font.family'] = font_name
            plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign
            return font_name

    # Fallback: try to use any available font with CJK support
    return None

_korean_font = _setup_korean_font()


class ReturnComparisonGenerator:
    """
    Multi-stock return comparison chart generator (Google Finance style).

    Generates clean comparison charts showing cumulative returns for multiple
    stocks with a simple, readable design.

    Features:
    - Percentage-based return visualization (0% baseline)
    - Clean white background with subtle grid
    - Color-coded lines with clear legend
    - Support for up to 5 stocks + 1 benchmark
    - Minimal, professional appearance

    Usage:
        generator = ReturnComparisonGenerator()
        png_bytes, metrics = generator.generate(
            price_data={"005930": df1, "000660": df2},
            ticker_names={"005930": "삼성전자", "000660": "SK하이닉스"},
            benchmark_data=kospi_df,
            benchmark_name="KOSPI"
        )
    """

    # Maximum number of stocks to compare (excluding benchmark)
    MAX_STOCKS = 5

    # Google Finance inspired color palette
    STOCK_COLORS = [
        "#1a73e8",  # Google Blue
        "#ea4335",  # Google Red
        "#34a853",  # Google Green
        "#fbbc04",  # Google Yellow
        "#9334e6",  # Purple
    ]

    # Benchmark color (gray)
    BENCHMARK_COLOR = "#5f6368"

    def __init__(self, dpi: int = 100):
        """
        Initialize ReturnComparisonGenerator.

        Args:
            dpi: Image DPI (default: 100)
        """
        self.dpi = dpi

    def generate(
        self,
        price_data: Dict[str, pd.DataFrame],
        ticker_names: Optional[Dict[str, str]] = None,
        benchmark_data: Optional[pd.DataFrame] = None,
        benchmark_name: str = "Benchmark",
        region: str = "KR",
        show_volatility: bool = False,  # Ignored in Google Finance style
        show_drawdown: bool = False,    # Ignored in Google Finance style
        style: str = "default",
        size: Tuple[int, int] = (1000, 500)
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Generate return comparison chart in Google Finance style.

        Args:
            price_data: Dict of {ticker: DataFrame with 'close' column and DatetimeIndex}
            ticker_names: Dict of {ticker: display_name} (optional)
            benchmark_data: DataFrame with 'close' column for benchmark (optional)
            benchmark_name: Display name for benchmark
            region: Market region code
            show_volatility: Ignored (not used in Google Finance style)
            show_drawdown: Ignored (not used in Google Finance style)
            style: Chart style (currently only "default" supported)
            size: Image size (width, height) in pixels

        Returns:
            Tuple of (PNG bytes, metrics dict)

        Raises:
            ValueError: If data is invalid or too many stocks
        """
        # Validate inputs
        self._validate_inputs(price_data)

        # Calculate returns for all stocks
        returns_data = {}
        metrics = {}

        for ticker, df in price_data.items():
            pct_return, stock_metrics = self._calculate_returns(df)
            returns_data[ticker] = pct_return
            metrics[ticker] = stock_metrics

        # Calculate benchmark returns if provided
        benchmark_returns = None
        benchmark_metrics = None
        if benchmark_data is not None and not benchmark_data.empty:
            benchmark_returns, benchmark_metrics = self._calculate_returns(benchmark_data)

        # Create figure with Google Finance style
        figsize = (size[0] / self.dpi, size[1] / self.dpi)
        fig, ax = plt.subplots(figsize=figsize, facecolor='white')
        ax.set_facecolor('white')

        # Plot benchmark first (background)
        if benchmark_returns is not None:
            return_pct = benchmark_metrics["total_return_pct"]
            ax.plot(
                benchmark_returns.index,
                benchmark_returns.values,
                color=self.BENCHMARK_COLOR,
                linewidth=1.5,
                label=f"{benchmark_name} ({return_pct:+.1f}%)",
                alpha=0.6,
                zorder=5
            )

        # Plot stock returns
        for i, (ticker, pct_return) in enumerate(returns_data.items()):
            color = self.STOCK_COLORS[i % len(self.STOCK_COLORS)]
            display_name = ticker_names.get(ticker, ticker) if ticker_names else ticker
            return_pct = metrics[ticker]["total_return_pct"]

            ax.plot(
                pct_return.index,
                pct_return.values,
                color=color,
                linewidth=2.0,
                label=f"{display_name} ({return_pct:+.1f}%)",
                zorder=10
            )

        # Add baseline at 0%
        ax.axhline(y=0, color='#dadce0', linestyle='-', linewidth=1, zorder=1)

        # Configure axes (Google Finance style)
        self._configure_axes_google_style(ax, returns_data, benchmark_returns)

        # Add title
        title = self._create_title(price_data, region)
        ax.set_title(title, fontsize=14, fontweight='500', color='#202124', pad=15, loc='left')

        # Add legend (Google Finance style - horizontal, top right)
        self._add_legend_google_style(ax)

        # Tight layout
        plt.tight_layout()

        # Save to PNG
        buf = BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=self.dpi,
            bbox_inches="tight",
            facecolor='white',
            edgecolor="none"
        )
        plt.close(fig)

        buf.seek(0)
        png_bytes = buf.read()

        # Build complete metrics response
        response_metrics = {
            "stocks": metrics,
            "benchmark": benchmark_metrics,
            "benchmark_name": benchmark_name if benchmark_metrics else None
        }

        return png_bytes, response_metrics

    def _validate_inputs(self, price_data: Dict[str, pd.DataFrame]) -> None:
        """Validate input data."""
        if not price_data:
            raise ValueError("price_data cannot be empty")

        if len(price_data) > self.MAX_STOCKS:
            raise ValueError(
                f"Maximum {self.MAX_STOCKS} stocks allowed, got {len(price_data)}"
            )

        if len(price_data) < 2:
            raise ValueError("At least 2 stocks required for comparison")

        for ticker, df in price_data.items():
            if df is None or df.empty:
                raise ValueError(f"Empty data for ticker: {ticker}")

            # Check for close column (case-insensitive)
            close_col = None
            for col in df.columns:
                if col.lower() == "close":
                    close_col = col
                    break

            if close_col is None:
                raise ValueError(f"Missing 'close' column for ticker: {ticker}")

    def _calculate_returns(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, float]]:
        """
        Calculate percentage returns from first day (Google Finance style).

        Args:
            df: DataFrame with 'close' column

        Returns:
            Tuple of (percentage_return_series, metrics_dict)
        """
        # Find close column (case-insensitive)
        close_col = None
        for col in df.columns:
            if col.lower() == "close":
                close_col = col
                break

        prices = df[close_col].dropna()

        if len(prices) < 2:
            raise ValueError("Insufficient data points for return calculation")

        # Calculate percentage return from first day (Google Finance style)
        # Return = (Current Price / First Price - 1) * 100
        first_price = prices.iloc[0]
        pct_return = ((prices / first_price) - 1) * 100

        # Calculate metrics
        total_return = (prices.iloc[-1] / first_price - 1) * 100

        # Calculate daily returns for volatility
        daily_returns = prices.pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized

        metrics = {
            "total_return_pct": round(total_return, 2),
            "volatility_pct": round(volatility, 2),
            "trading_days": len(daily_returns),
            "start_date": prices.index[0].strftime("%Y-%m-%d"),
            "end_date": prices.index[-1].strftime("%Y-%m-%d"),
            "start_price": round(float(first_price), 2),
            "end_price": round(float(prices.iloc[-1]), 2)
        }

        return pct_return, metrics

    def _configure_axes_google_style(
        self,
        ax,
        returns_data: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series]
    ) -> None:
        """Configure chart axes in Google Finance style."""

        # Collect all values for y-axis limits
        all_values = []
        for pct_return in returns_data.values():
            all_values.extend(pct_return.values)
        if benchmark_returns is not None:
            all_values.extend(benchmark_returns.values)

        # Calculate y-axis limits with padding
        if all_values:
            min_val = min(all_values)
            max_val = max(all_values)

            # Ensure 0 is visible and add padding
            if min_val > 0:
                min_val = -5  # Show at least -5% if all positive
            if max_val < 0:
                max_val = 5   # Show at least +5% if all negative

            padding = (max_val - min_val) * 0.1
            ax.set_ylim(min_val - padding, max_val + padding)

        # Y-axis formatting (percentage with + sign for positive)
        def format_pct(x, pos):
            if x >= 0:
                return f'+{x:.0f}%'
            return f'{x:.0f}%'

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(format_pct))

        # Subtle grid (Google Finance style)
        ax.grid(True, axis='y', linestyle='-', alpha=0.3, color='#dadce0', linewidth=0.5)
        ax.grid(True, axis='x', linestyle='-', alpha=0.2, color='#dadce0', linewidth=0.5)

        # X-axis date formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')

        # Axis styling
        ax.tick_params(axis='both', colors='#5f6368', labelsize=10)
        ax.tick_params(axis='x', pad=8)
        ax.tick_params(axis='y', pad=5)

        # Remove spines for cleaner look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#dadce0')
        ax.spines['bottom'].set_color('#dadce0')

        # Remove axis labels (Google Finance style - clean)
        ax.set_xlabel('')
        ax.set_ylabel('')

    def _create_title(
        self,
        price_data: Dict[str, pd.DataFrame],
        region: str
    ) -> str:
        """Create chart title."""
        # Get date range from first ticker
        first_ticker = list(price_data.keys())[0]
        first_df = price_data[first_ticker]

        start_date = first_df.index[0].strftime('%Y.%m.%d')
        end_date = first_df.index[-1].strftime('%Y.%m.%d')

        return f"수익률 비교  {start_date} - {end_date}"

    def _add_legend_google_style(self, ax) -> None:
        """Add legend in Google Finance style."""
        legend = ax.legend(
            loc='upper left',
            fontsize=11,
            frameon=True,
            fancybox=False,
            edgecolor='#dadce0',
            facecolor='white',
            framealpha=1.0,
            borderpad=0.8,
            labelspacing=0.5,
            handlelength=2,
            handleheight=0.7
        )

        # Style legend text
        for text in legend.get_texts():
            text.set_color('#202124')
