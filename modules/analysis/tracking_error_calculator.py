# modules/analysis/tracking_error_calculator.py
"""
Tracking Error Calculator for ETFs

Calculates tracking error between ETF and its underlying index:
- Daily tracking error (20-day, 60-day, 120-day, 250-day)
- Annualized tracking error
- Tracking difference (mean deviation)
- Information ratio

Tracking Error Definition:
    TE = StdDev(ETF_Returns - Index_Returns)

Where:
- Lower TE = Better tracking (closer to index)
- Typical range: 0.1% - 1.5% annually for passive ETFs
- >2% indicates tracking issues

Formula:
    TE_annual = sqrt(252) * StdDev(daily_return_diff)

Author: Spock Quant Platform
Date: 2025-10-31
Phase: ETF Screening - Tracking Error Implementation
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from config.database import get_connection
from modules.data_collection.kis_data_collector import KISDataCollector


class TrackingErrorCalculator:
    """
    Calculate tracking error between ETF and its underlying index.

    Example:
        >>> calc = TrackingErrorCalculator()
        >>> result = await calc.calculate_tracking_error(
        ...     etf_ticker="091160",  # KODEX 반도체
        ...     index_ticker="U011",   # KOSPI 반도체 지수
        ...     window_days=20
        ... )
        >>> result["tracking_error_annualized"]
        0.35  # 0.35% tracking error (good)
    """

    def __init__(self):
        """Initialize calculator"""
        self.data_collector = KISDataCollector()

    async def calculate_tracking_error(
        self,
        etf_ticker: str,
        index_ticker: str,
        window_days: int = 250,
        region: str = "KR"
    ) -> Dict[str, float]:
        """
        Calculate tracking error for ETF vs. index.

        Args:
            etf_ticker: ETF ticker (e.g., "091160")
            index_ticker: Index ticker (e.g., "U011")
            window_days: Rolling window in trading days (default: 250 = 1 year)
            region: Market region (default: "KR")

        Returns:
            Dict with tracking error metrics:
            {
                "tracking_error_daily": 0.05,        # Daily TE %
                "tracking_error_annualized": 0.79,   # Annualized TE %
                "tracking_difference": -0.12,        # Mean deviation %
                "correlation": 0.998,                # Correlation coefficient
                "information_ratio": -0.15,          # IR = TD / TE
                "window_days": 250,
                "data_points": 245,
                "calculation_date": "2025-10-31"
            }

        Raises:
            ValueError: If insufficient data or mismatched dates
        """
        # Get price data
        etf_data = await self._get_price_data(etf_ticker, window_days, region)
        index_data = await self._get_price_data(index_ticker, window_days, region)

        if etf_data is None or index_data is None:
            raise ValueError(f"Insufficient data for {etf_ticker} or {index_ticker}")

        # Calculate returns
        etf_returns = etf_data['close'].pct_change().dropna()
        index_returns = index_data['close'].pct_change().dropna()

        # Align dates
        common_dates = etf_returns.index.intersection(index_returns.index)
        if len(common_dates) < 20:
            raise ValueError(f"Insufficient overlapping data points: {len(common_dates)}")

        etf_returns = etf_returns.loc[common_dates]
        index_returns = index_returns.loc[common_dates]

        # Calculate tracking metrics
        return_diff = etf_returns - index_returns

        tracking_error_daily = return_diff.std() * 100  # %
        tracking_error_annualized = tracking_error_daily * np.sqrt(252)  # Annualized
        tracking_difference = return_diff.mean() * 100  # Mean deviation %
        correlation = etf_returns.corr(index_returns)

        # Information Ratio = Tracking Difference / Tracking Error
        information_ratio = (
            tracking_difference / tracking_error_daily
            if tracking_error_daily > 0
            else 0.0
        )

        result = {
            "tracking_error_daily": round(tracking_error_daily, 4),
            "tracking_error_annualized": round(tracking_error_annualized, 4),
            "tracking_difference": round(tracking_difference, 4),
            "correlation": round(correlation, 4),
            "information_ratio": round(information_ratio, 4),
            "window_days": window_days,
            "data_points": len(return_diff),
            "calculation_date": datetime.now().strftime("%Y-%m-%d")
        }

        logger.debug(f"Calculated TE for {etf_ticker}: {result['tracking_error_annualized']:.2f}%")
        return result

    async def calculate_multiple_windows(
        self,
        etf_ticker: str,
        index_ticker: str,
        windows: List[int] = [20, 60, 120, 250],
        region: str = "KR"
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate tracking error across multiple time windows.

        Args:
            etf_ticker: ETF ticker
            index_ticker: Index ticker
            windows: List of window sizes in trading days
            region: Market region

        Returns:
            Dict mapping window sizes to tracking error results:
            {
                "20d": {...},
                "60d": {...},
                "120d": {...},
                "250d": {...}
            }
        """
        results = {}

        for window in windows:
            try:
                result = await self.calculate_tracking_error(
                    etf_ticker, index_ticker, window, region
                )
                results[f"{window}d"] = result
            except Exception as e:
                logger.warning(f"Failed to calculate TE for {window}d window: {e}")
                results[f"{window}d"] = None

        return results

    async def _get_price_data(
        self,
        ticker: str,
        window_days: int,
        region: str
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve price data from database.

        Args:
            ticker: Stock/ETF/Index ticker
            window_days: Number of trading days needed
            region: Market region

        Returns:
            DataFrame with date index and OHLCV columns, or None if insufficient data
        """
        # Calculate calendar days needed (window_days * 1.4 for weekends/holidays)
        calendar_days = int(window_days * 1.4)
        start_date = (datetime.now() - timedelta(days=calendar_days)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT date, open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker = %s
                      AND region = %s
                      AND date >= %s
                      AND date <= %s
                    ORDER BY date ASC
                """

                cursor.execute(query, (ticker, region, start_date, end_date))
                rows = cursor.fetchall()

                if len(rows) < window_days * 0.8:
                    # Insufficient data (need at least 80% of requested window)
                    logger.warning(f"Insufficient data for {ticker}: {len(rows)} < {window_days}")
                    return None

                # Convert to DataFrame
                df = pd.DataFrame(rows)
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')

                # Take most recent window_days
                df = df.tail(window_days)

                return df

        except Exception as e:
            logger.error(f"Failed to fetch price data for {ticker}: {e}")
            return None

    async def save_tracking_errors(
        self,
        etf_ticker: str,
        index_ticker: str,
        region: str = "KR"
    ) -> bool:
        """
        Calculate and save tracking errors to database.

        Args:
            etf_ticker: ETF ticker
            index_ticker: Index ticker (from ETF metadata)
            region: Market region

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate for all standard windows
            results = await self.calculate_multiple_windows(
                etf_ticker, index_ticker, [20, 60, 120, 250], region
            )

            # Extract annualized values
            te_20d = results["20d"]["tracking_error_annualized"] if results["20d"] else None
            te_60d = results["60d"]["tracking_error_annualized"] if results["60d"] else None
            te_120d = results["120d"]["tracking_error_annualized"] if results["120d"] else None
            te_250d = results["250d"]["tracking_error_annualized"] if results["250d"] else None

            # Save to database
            with get_connection() as conn:
                cursor = conn.cursor()

                # Update etf_details table
                cursor.execute("""
                    UPDATE etf_details
                    SET tracking_error_20d = %s,
                        tracking_error_60d = %s,
                        tracking_error_120d = %s,
                        tracking_error_250d = %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE ticker = %s AND region = %s
                """, (te_20d, te_60d, te_120d, te_250d, etf_ticker, region))

                # Check if update affected any rows
                if cursor.rowcount == 0:
                    # No existing record - insert new one
                    cursor.execute("""
                        INSERT INTO etf_details (
                            ticker, region, tracking_index,
                            tracking_error_20d, tracking_error_60d,
                            tracking_error_120d, tracking_error_250d,
                            expense_ratio, created_at, last_updated
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (etf_ticker, region, index_ticker, te_20d, te_60d, te_120d, te_250d))

                conn.commit()

                logger.info(f"Saved tracking errors for {etf_ticker}: "
                           f"20d={te_20d:.2f}%, 60d={te_60d:.2f}%, "
                           f"120d={te_120d:.2f}%, 250d={te_250d:.2f}%")
                return True

        except Exception as e:
            logger.error(f"Failed to save tracking errors for {etf_ticker}: {e}")
            return False

    @staticmethod
    def interpret_tracking_error(te_annual: float) -> Dict[str, str]:
        """
        Interpret annualized tracking error value.

        Args:
            te_annual: Annualized tracking error %

        Returns:
            Dict with interpretation:
            {
                "rating": "excellent" | "good" | "acceptable" | "poor",
                "description": "...",
                "threshold": "< 0.5%"
            }
        """
        if te_annual < 0.5:
            return {
                "rating": "excellent",
                "description": "Very tight tracking, minimal deviation from index",
                "threshold": "< 0.5%"
            }
        elif te_annual < 1.0:
            return {
                "rating": "good",
                "description": "Good tracking within acceptable range",
                "threshold": "0.5% - 1.0%"
            }
        elif te_annual < 2.0:
            return {
                "rating": "acceptable",
                "description": "Moderate tracking error, within industry average",
                "threshold": "1.0% - 2.0%"
            }
        else:
            return {
                "rating": "poor",
                "description": "High tracking error, significant deviation from index",
                "threshold": "> 2.0%"
            }
