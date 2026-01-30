# mcp_server/generators/stock_chart_generator.py
"""
Stock Chart Generator for MCP Server

Generates OHLCV candlestick charts with technical indicators using mplfinance.

Features:
- Candlestick charts (OHLCV)
- Moving average overlays (MA20, MA50, MA200)
- RSI panel (14-period)
- MACD panel (12, 26, 9)
- Bollinger Bands overlay
- Volume bar chart

Author: Spock MCP Server
Date: 2026-01-19
"""

from typing import List, Tuple, Optional, Dict, Any
from io import BytesIO

import pandas as pd
import numpy as np
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use


class StockChartGenerator:
    """
    Stock candlestick chart generator using mplfinance.

    Renders OHLCV candlestick charts with customizable technical indicators
    and exports to PNG format for MCP ImageContent response.

    Usage:
        generator = StockChartGenerator()
        png_bytes = generator.generate(
            ohlcv_df=df,
            ticker="005930",
            indicators=["ma", "rsi", "volume"],
            style="default",
            size=(1200, 800)
        )
    """

    # Chart style configurations
    STYLES: Dict[str, Dict[str, Any]] = {
        "default": {
            "base_mpf_style": "yahoo",
            "up_color": "#26A69A",       # Teal (up)
            "down_color": "#EF5350",     # Red (down)
            "volume_up": "#26A69A80",    # Semi-transparent teal
            "volume_down": "#EF535080",  # Semi-transparent red
            "ma_colors": ["#FF9800", "#2196F3", "#9C27B0"],  # MA20, MA50, MA200
            "background": "#FAFAFA",
            "grid_color": "#E0E0E0",
            "text_color": "#333333"
        },
        "dark": {
            "base_mpf_style": "nightclouds",
            "up_color": "#00E676",
            "down_color": "#FF5252",
            "volume_up": "#00E67680",
            "volume_down": "#FF525280",
            "ma_colors": ["#FFD54F", "#4FC3F7", "#BA68C8"],
            "background": "#1E1E1E",
            "grid_color": "#333333",
            "text_color": "#FFFFFF"
        },
        "classic": {
            "base_mpf_style": "classic",
            "up_color": "#FFFFFF",
            "down_color": "#000000",
            "volume_up": "#00000040",
            "volume_down": "#00000080",
            "ma_colors": ["#FF0000", "#0000FF", "#008000"],
            "background": "#FFFFFF",
            "grid_color": "#CCCCCC",
            "text_color": "#000000"
        }
    }

    # Indicator descriptions for legend
    INDICATOR_LABELS = {
        "ma": "Moving Averages (MA20/50/200)",
        "rsi": "RSI (14)",
        "macd": "MACD (12,26,9)",
        "bollinger": "Bollinger Bands (20,2)",
        "volume": "Volume"
    }

    def __init__(self, dpi: int = 100):
        """
        Initialize StockChartGenerator.

        Args:
            dpi: Image DPI (default: 100)
        """
        self.dpi = dpi

    def generate(
        self,
        ohlcv_df: pd.DataFrame,
        ticker: str,
        ticker_name: Optional[str] = None,
        region: str = "KR",
        indicators: List[str] = None,
        style: str = "default",
        size: Tuple[int, int] = (1200, 800)
    ) -> bytes:
        """
        Generate stock chart image.

        Args:
            ohlcv_df: OHLCV DataFrame with DatetimeIndex
                      Required columns: Open, High, Low, Close, Volume
            ticker: Stock ticker symbol
            ticker_name: Stock name (optional)
            region: Market region code
            indicators: List of indicators to display
                       Options: "ma", "rsi", "macd", "bollinger", "volume"
            style: Chart style ("default", "dark", "classic")
            size: Image size (width, height) in pixels

        Returns:
            PNG image bytes

        Raises:
            ValueError: If DataFrame is invalid or missing required columns
        """
        if indicators is None:
            indicators = ["ma", "volume"]

        # Validate DataFrame
        self._validate_dataframe(ohlcv_df)

        # Get style configuration
        style_config = self.STYLES.get(style, self.STYLES["default"])

        # Create mplfinance style
        mpf_style = self._create_mpf_style(style_config)

        # Build additional plots (indicators)
        addplots, panel_ratios = self._build_indicator_plots(
            ohlcv_df, indicators, style_config
        )

        # Create chart title
        title = self._create_title(ticker, ticker_name, region, ohlcv_df)

        # Calculate figure size
        figsize = (size[0] / self.dpi, size[1] / self.dpi)

        # Render chart
        buf = BytesIO()

        # Build plot kwargs
        plot_kwargs = {
            "type": "candle",
            "style": mpf_style,
            "title": title,
            "volume": "volume" in indicators,
            "panel_ratios": panel_ratios,
            "figsize": figsize,
            "returnfig": True,
            "tight_layout": True,
            "datetime_format": '%Y-%m-%d',
            "xrotation": 45,
            "warn_too_much_data": 1000
        }

        # Only add addplot if there are plots to add
        if addplots:
            plot_kwargs["addplot"] = addplots

        fig, axes = mpf.plot(ohlcv_df, **plot_kwargs)

        # Add panel separators for clear visual distinction
        self._add_panel_separators(fig, axes, indicators, style_config)

        # Add MA legend with colors
        if "ma" in indicators:
            self._add_ma_legend(fig, axes, ohlcv_df, style_config)

        # Add indicator descriptions as annotation
        self._add_indicator_legend(fig, indicators, style_config)

        # Save to PNG
        fig.savefig(
            buf,
            format="png",
            dpi=self.dpi,
            bbox_inches="tight",
            facecolor=style_config["background"],
            edgecolor="none"
        )
        plt.close(fig)

        buf.seek(0)
        return buf.read()

    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate OHLCV DataFrame structure."""
        required_columns = ["Open", "High", "Low", "Close", "Volume"]

        if df is None or df.empty:
            raise ValueError("DataFrame is empty or None")

        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")

    def _create_mpf_style(self, style_config: Dict) -> dict:
        """Create mplfinance style from configuration."""
        mc = mpf.make_marketcolors(
            up=style_config["up_color"],
            down=style_config["down_color"],
            volume={
                "up": style_config["volume_up"],
                "down": style_config["volume_down"]
            },
            edge="inherit",
            wick="inherit"
        )

        return mpf.make_mpf_style(
            base_mpf_style=style_config["base_mpf_style"],
            marketcolors=mc,
            gridcolor=style_config["grid_color"],
            facecolor=style_config["background"],
            figcolor=style_config["background"],
            gridstyle="--",
            gridaxis="both"
        )

    def _build_indicator_plots(
        self,
        df: pd.DataFrame,
        indicators: List[str],
        style_config: Dict
    ) -> Tuple[List, List[int]]:
        """
        Build additional plots for technical indicators.

        Returns:
            Tuple of (addplots list, panel_ratios list)
        """
        addplots = []
        panel_ratios = [4]  # Main candlestick panel ratio

        # Track current panel index
        # Panel 0 = candle chart
        # Panel 1 = volume (if enabled, automatically handled by mplfinance)
        current_panel = 1 if "volume" in indicators else 0

        if "volume" in indicators:
            panel_ratios.append(1)  # Volume panel ratio
            current_panel += 1
        else:
            # If no volume, we still need panel 1 for other indicators
            current_panel = 1

        # Moving Averages (overlay on main panel)
        if "ma" in indicators:
            ma_plots = self._create_ma_plots(df, style_config)
            addplots.extend(ma_plots)

        # Bollinger Bands (overlay on main panel)
        if "bollinger" in indicators:
            bb_plots = self._create_bollinger_plots(df, style_config)
            addplots.extend(bb_plots)

        # RSI (separate panel)
        if "rsi" in indicators:
            rsi_plots = self._create_rsi_plots(df, current_panel)
            addplots.extend(rsi_plots)
            panel_ratios.append(1)
            current_panel += 1

        # MACD (separate panel)
        if "macd" in indicators:
            macd_plots = self._create_macd_plots(df, current_panel)
            addplots.extend(macd_plots)
            panel_ratios.append(1)
            current_panel += 1

        return addplots, panel_ratios

    def _create_ma_plots(
        self,
        df: pd.DataFrame,
        style_config: Dict
    ) -> List:
        """Create moving average overlay plots."""
        plots = []
        ma_colors = style_config["ma_colors"]

        ma_configs = [
            (20, ma_colors[0], "MA20"),
            (50, ma_colors[1], "MA50"),
            (200, ma_colors[2], "MA200")
        ]

        for period, color, label in ma_configs:
            if len(df) >= period:
                ma = df["Close"].rolling(window=period).mean()
                plots.append(mpf.make_addplot(
                    ma,
                    color=color,
                    width=1.0,
                    panel=0,
                    secondary_y=False
                ))

        return plots

    def _create_bollinger_plots(
        self,
        df: pd.DataFrame,
        style_config: Dict,
        period: int = 20,
        std_dev: float = 2.0
    ) -> List:
        """Create Bollinger Bands overlay plots."""
        if len(df) < period:
            return []

        middle = df["Close"].rolling(window=period).mean()
        std = df["Close"].rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        bb_color = "#9E9E9E"  # Gray

        return [
            mpf.make_addplot(upper, color=bb_color, linestyle="--", width=0.8, panel=0),
            mpf.make_addplot(middle, color=bb_color, width=0.8, panel=0),
            mpf.make_addplot(lower, color=bb_color, linestyle="--", width=0.8, panel=0)
        ]

    def _create_rsi_plots(
        self,
        df: pd.DataFrame,
        panel: int,
        period: int = 14
    ) -> List:
        """Create RSI indicator plots."""
        if len(df) < period + 1:
            return []

        rsi = self._calculate_rsi(df, period)

        # RSI reference lines (30, 70)
        rsi_30 = pd.Series([30] * len(df), index=df.index)
        rsi_70 = pd.Series([70] * len(df), index=df.index)

        return [
            mpf.make_addplot(rsi, panel=panel, color="#7B1FA2", ylabel="RSI", width=1.2),
            mpf.make_addplot(rsi_30, panel=panel, color="#4CAF50", linestyle="--", width=0.5),
            mpf.make_addplot(rsi_70, panel=panel, color="#F44336", linestyle="--", width=0.5)
        ]

    def _create_macd_plots(
        self,
        df: pd.DataFrame,
        panel: int,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> List:
        """Create MACD indicator plots."""
        if len(df) < slow + signal:
            return []

        macd_data = self._calculate_macd(df, fast, slow, signal)

        # Create histogram colors based on sign
        hist = macd_data["histogram"]
        hist_colors = ["#26A69A" if v >= 0 else "#EF5350" for v in hist.fillna(0)]

        return [
            mpf.make_addplot(macd_data["macd"], panel=panel, color="#2196F3", ylabel="MACD", width=1.0),
            mpf.make_addplot(macd_data["signal"], panel=panel, color="#FF9800", width=1.0),
            mpf.make_addplot(hist, panel=panel, type="bar", color=hist_colors, width=0.7)
        ]

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI (Relative Strength Index)."""
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # Avoid division by zero
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        exp_fast = df["Close"].ewm(span=fast, adjust=False).mean()
        exp_slow = df["Close"].ewm(span=slow, adjust=False).mean()
        macd_line = exp_fast - exp_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    def _create_title(
        self,
        ticker: str,
        ticker_name: Optional[str],
        region: str,
        df: pd.DataFrame
    ) -> str:
        """Create chart title with ticker info and date range."""
        parts = [ticker]

        if ticker_name:
            parts.append(f"({ticker_name})")

        parts.append(f"- {region}")

        # Date range
        start_date = df.index[0].strftime('%Y-%m-%d')
        end_date = df.index[-1].strftime('%Y-%m-%d')
        parts.append(f"| {start_date} ~ {end_date}")

        return " ".join(parts)

    def _add_panel_separators(
        self,
        fig,
        axes,
        indicators: List[str],
        style_config: Dict
    ) -> None:
        """
        Add visual separators between chart panels for clear distinction.

        Adds horizontal lines and panel labels to clearly separate:
        - Candlestick chart (top)
        - Volume (middle, if enabled)
        - RSI/MACD (bottom panels)
        """
        if not isinstance(axes, (list, tuple)):
            axes = [axes]

        separator_color = style_config.get("grid_color", "#E0E0E0")
        text_color = style_config.get("text_color", "#666666")

        # Panel labels based on indicators
        panel_labels = ["Price"]
        if "volume" in indicators:
            panel_labels.append("Volume")
        if "rsi" in indicators:
            panel_labels.append("RSI(14)")
        if "macd" in indicators:
            panel_labels.append("MACD")

        # Add separator lines and labels for each panel
        for i, ax in enumerate(axes):
            # Add top border line for visual separation (except first panel)
            if i > 0:
                ax.axhline(
                    y=ax.get_ylim()[1],
                    color=separator_color,
                    linewidth=2.0,
                    linestyle='-',
                    alpha=0.8
                )

            # Add panel label in top-left corner
            if i < len(panel_labels):
                ax.text(
                    0.01, 0.95,
                    panel_labels[i],
                    transform=ax.transAxes,
                    fontsize=9,
                    fontweight='bold',
                    color=text_color,
                    alpha=0.8,
                    verticalalignment='top',
                    bbox=dict(
                        boxstyle='round,pad=0.3',
                        facecolor=style_config.get("background", "#FAFAFA"),
                        edgecolor=separator_color,
                        alpha=0.9
                    )
                )

    def _add_ma_legend(
        self,
        fig,
        axes,
        df: pd.DataFrame,
        style_config: Dict
    ) -> None:
        """
        Add moving average legend with color indicators to the price panel.

        Shows which color corresponds to which MA period.
        """
        ma_colors = style_config["ma_colors"]
        text_color = style_config.get("text_color", "#666666")

        # Get the main price axis (first one)
        if isinstance(axes, (list, tuple)):
            main_ax = axes[0]
        else:
            main_ax = axes

        # Build MA legend entries (only for MAs that can be calculated)
        legend_entries = []
        ma_configs = [
            (20, ma_colors[0], "MA20"),
            (50, ma_colors[1], "MA50"),
            (200, ma_colors[2], "MA200")
        ]

        for period, color, label in ma_configs:
            if len(df) >= period:
                legend_entries.append((color, label))

        if not legend_entries:
            return

        # Position legend in top-right corner of price panel
        legend_text_parts = []
        for color, label in legend_entries:
            legend_text_parts.append(f"━ {label}")

        # Create custom legend using text with colored markers
        y_offset = 0.95
        x_pos = 0.99

        for i, (color, label) in enumerate(legend_entries):
            main_ax.text(
                x_pos, y_offset - (i * 0.06),
                f"━ {label}",
                transform=main_ax.transAxes,
                fontsize=8,
                color=color,
                fontweight='bold',
                horizontalalignment='right',
                verticalalignment='top'
            )

    def _add_indicator_legend(
        self,
        fig,
        indicators: List[str],
        style_config: Dict
    ) -> None:
        """Add indicator descriptions as figure annotation."""
        # Build legend text
        legend_items = []
        for ind in indicators:
            if ind in self.INDICATOR_LABELS:
                legend_items.append(self.INDICATOR_LABELS[ind])

        if not legend_items:
            return

        legend_text = " | ".join(legend_items)

        # Add as figure text at bottom
        fig.text(
            0.5, 0.01,
            legend_text,
            ha='center',
            va='bottom',
            fontsize=8,
            color=style_config.get("text_color", "#666666"),
            alpha=0.7
        )
