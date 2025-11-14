#!/usr/bin/env python3
"""
Stock Screener Module - Phase 2.2
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import pandas as pd
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager


@dataclass
class ScreeningResult:
    """Screening results with metadata."""
    region: str
    filter_type: str
    timestamp: datetime
    total_results: int
    data: pd.DataFrame
    parameters: Dict[str, Any]

    def to_csv(self, path: str) -> None:
        """Export results to CSV."""
        self.data.to_csv(path, index=False)
        logger.info(f"Exported {len(self.data)} results to: {path}")

    def to_excel(self, path: str) -> None:
        """Export results to Excel."""
        self.data.to_excel(path, index=False)
        logger.info(f"Exported {len(self.data)} results to: {path}")


class FilterRegistry:
    """Registry for screening filters."""
    def __init__(self):
        self._filters: Dict[str, Callable] = {}

    def register(self, name: str):
        def decorator(func: Callable):
            self._filters[name] = func
            return func
        return decorator

    def get(self, name: str) -> Optional[Callable]:
        return self._filters.get(name)

    def list_filters(self) -> List[str]:
        return list(self._filters.keys())


class StockScreener:
    """Unified stock screening engine."""
    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.registry = FilterRegistry()

    def screen_technical(
        self,
        region: str = 'HK',
        rsi_max: float = 35.0,
        rsi_min: float = 0.0,
        ma_trend: Optional[str] = None,
        limit: int = 100,
        min_date: str = '2025-10-01'
    ):
        query = """
            WITH latest_data AS (
                SELECT ticker, date, close, rsi_14, macd, macd_signal, ma20, ma60,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                FROM ohlcv_data
                WHERE region = %s AND rsi_14 IS NOT NULL AND date >= %s
            )
            SELECT ticker, date, close, rsi_14 as rsi,
                   (macd - macd_signal) as macd_histogram,
                   CASE WHEN close > ma20 AND close > ma60 THEN 'Uptrend'
                        WHEN close < ma20 AND close < ma60 THEN 'Downtrend'
                        ELSE 'Neutral' END as trend,
                   CASE WHEN rsi_14 < 30 THEN 'Oversold'
                        WHEN rsi_14 > 70 THEN 'Overbought'
                        ELSE 'Neutral' END as rsi_signal
            FROM latest_data
            WHERE rn = 1 AND rsi_14 >= %s AND rsi_14 <= %s
        """
        params = [region, min_date, rsi_min, rsi_max]

        if ma_trend == 'uptrend':
            query += " AND close > ma20 AND close > ma60"
        elif ma_trend == 'downtrend':
            query += " AND close < ma20 AND close < ma60"

        query += " ORDER BY rsi_14 ASC LIMIT %s"
        params.append(limit)

        results_raw = self.db.execute_query(query, tuple(params))
        df = pd.DataFrame(results_raw)

        return ScreeningResult(
            region=region,
            filter_type='technical',
            timestamp=datetime.now(),
            total_results=len(df),
            data=df,
            parameters={'rsi_min': rsi_min, 'rsi_max': rsi_max, 'ma_trend': ma_trend, 'limit': limit}
        )

    def screen_value(
        self,
        region: str = 'US',
        per_max: float = 15.0,
        pbr_max: float = 3.0,
        market_cap_min: float = 1_000_000_000,
        dividend_yield_min: float = 0.0,
        limit: int = 100
    ):
        query = """
            WITH latest_fundamentals AS (
                SELECT ticker, date, per, pbr, dividend_yield, market_cap,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                FROM ticker_fundamentals
                WHERE region = %s AND per IS NOT NULL AND pbr IS NOT NULL AND per > 0 AND pbr > 0
            )
            SELECT ticker, date, per, pbr, dividend_yield, market_cap,
                   ROUND((1.0 / per + 1.0 / pbr) * 100, 2) as value_score
            FROM latest_fundamentals
            WHERE rn = 1 AND per <= %s AND pbr <= %s AND market_cap >= %s AND dividend_yield >= %s
            ORDER BY value_score DESC LIMIT %s
        """

        params = (region, per_max, pbr_max, market_cap_min, dividend_yield_min, limit)
        results_raw = self.db.execute_query(query, params)
        df = pd.DataFrame(results_raw)

        return ScreeningResult(
            region=region,
            filter_type='value',
            timestamp=datetime.now(),
            total_results=len(df),
            data=df,
            parameters={
                'per_max': per_max,
                'pbr_max': pbr_max,
                'market_cap_min': market_cap_min,
                'dividend_yield_min': dividend_yield_min,
                'limit': limit
            }
        )
