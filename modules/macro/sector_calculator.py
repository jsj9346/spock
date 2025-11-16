# modules/macro/sector_calculator.py
"""
Sector Performance Calculator

Purpose:
- Calculate daily sector performance from ohlcv_data
- Store results in sector_performance table
- Support both KR and US markets

Data Flow:
1. Read ohlcv_data for sector tickers (last 90 days)
2. Calculate sector-level returns (1d, 1w, 1m, 3m)
3. Classify momentum (strong/moderate/weak/negative)
4. Identify sector rotation patterns
5. Save to sector_performance table

Author: Spock Quant Platform
Created: 2025-11-12
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from modules.db_manager_postgres import PostgresDatabaseManager
from .sector_definitions import KR_SECTORS, US_SECTORS

logger = logging.getLogger(__name__)


class SectorPerformanceCalculator:
    """
    Calculate and store sector performance metrics

    Features:
    - SQL-based calculation for efficiency
    - Momentum classification (strong/moderate/weak/negative)
    - Sector rotation detection
    - Database persistence
    """

    def __init__(self, db_manager: Optional[PostgresDatabaseManager] = None):
        """
        Initialize sector calculator

        Args:
            db_manager: Optional database manager (creates new if None)
        """
        self.db = db_manager or PostgresDatabaseManager()
        logger.info("SectorPerformanceCalculator initialized")

    def calculate_daily_performance(
        self,
        analysis_date: date,
        region: str = "KR"
    ) -> Dict[str, Dict]:
        """
        Calculate sector performance for a given date

        Args:
            analysis_date: Date to calculate performance for
            region: Market region ('KR' or 'US')

        Returns:
            {
                "Technology": {
                    "avg_return_1d": 1.23,
                    "avg_return_1w": 3.45,
                    "avg_return_1m": 8.67,
                    "avg_return_3m": 15.32,
                    "num_stocks": 5,
                    "strong_stocks": 4,
                    "weak_stocks": 1,
                    "momentum": "strong"
                },
                ...
            }
        """
        logger.info(f"Calculating sector performance for {region} on {analysis_date}")

        if region == "KR":
            return self._calculate_kr_sectors(analysis_date)
        elif region == "US":
            return self._calculate_us_sectors(analysis_date)
        else:
            raise ValueError(f"Unsupported region: {region}")

    def _calculate_kr_sectors(self, analysis_date: date) -> Dict[str, Dict]:
        """
        Calculate KR sector performance using SQL

        Strategy:
        - Use LAG() window function to get historical prices
        - Calculate returns for each ticker
        - Aggregate by sector
        - Classify momentum based on avg_return_1m

        Args:
            analysis_date: Analysis date

        Returns:
            Sector performance dictionary
        """
        results = {}

        for sector_name, sector_data in KR_SECTORS.items():
            tickers = sector_data["tickers"]

            # SQL query to calculate sector performance
            query = """
                WITH sector_prices AS (
                    -- Get current and historical prices for sector tickers
                    SELECT
                        o.ticker,
                        o.date,
                        o.close as current_close,
                        LAG(o.close, 1) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1d,
                        LAG(o.close, 5) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1w,
                        LAG(o.close, 21) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1m,
                        LAG(o.close, 63) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_3m
                    FROM ohlcv_data o
                    WHERE o.ticker = ANY(%s)
                      AND o.region = 'KR'
                      AND o.timeframe = '1d'
                      AND o.date <= %s
                      AND o.date >= %s - INTERVAL '90 days'
                ),
                sector_returns AS (
                    -- Calculate returns for each ticker
                    SELECT
                        ticker,
                        date,
                        CASE WHEN close_1d > 0
                             THEN ((current_close - close_1d) / close_1d) * 100
                             ELSE NULL END as return_1d,
                        CASE WHEN close_1w > 0
                             THEN ((current_close - close_1w) / close_1w) * 100
                             ELSE NULL END as return_1w,
                        CASE WHEN close_1m > 0
                             THEN ((current_close - close_1m) / close_1m) * 100
                             ELSE NULL END as return_1m,
                        CASE WHEN close_3m > 0
                             THEN ((current_close - close_3m) / close_3m) * 100
                             ELSE NULL END as return_3m
                    FROM sector_prices
                    WHERE date = %s
                )
                SELECT
                    AVG(return_1d) as avg_return_1d,
                    AVG(return_1w) as avg_return_1w,
                    AVG(return_1m) as avg_return_1m,
                    AVG(return_3m) as avg_return_3m,
                    COUNT(*) as num_stocks,
                    SUM(CASE WHEN return_1m > 0 THEN 1 ELSE 0 END) as strong_stocks,
                    SUM(CASE WHEN return_1m <= 0 THEN 1 ELSE 0 END) as weak_stocks
                FROM sector_returns;
            """

            try:
                rows = self.db.execute_query(
                    query,
                    (tickers, analysis_date, analysis_date, analysis_date)
                )

                if rows and len(rows) > 0:
                    row = rows[0]

                    # Extract values (handle NULL)
                    avg_return_1d = float(row['avg_return_1d']) if row['avg_return_1d'] is not None else 0.0
                    avg_return_1w = float(row['avg_return_1w']) if row['avg_return_1w'] is not None else 0.0
                    avg_return_1m = float(row['avg_return_1m']) if row['avg_return_1m'] is not None else 0.0
                    avg_return_3m = float(row['avg_return_3m']) if row['avg_return_3m'] is not None else 0.0
                    num_stocks = int(row['num_stocks']) if row['num_stocks'] else 0
                    strong_stocks = int(row['strong_stocks']) if row['strong_stocks'] else 0
                    weak_stocks = int(row['weak_stocks']) if row['weak_stocks'] else 0

                    # Classify momentum
                    momentum = self._classify_momentum(avg_return_1m)

                    results[sector_name] = {
                        "avg_return_1d": round(avg_return_1d, 4),
                        "avg_return_1w": round(avg_return_1w, 4),
                        "avg_return_1m": round(avg_return_1m, 4),
                        "avg_return_3m": round(avg_return_3m, 4),
                        "num_stocks": num_stocks,
                        "strong_stocks": strong_stocks,
                        "weak_stocks": weak_stocks,
                        "momentum": momentum
                    }

                    logger.debug(f"  {sector_name}: {avg_return_1m:+.2f}% (1M), momentum={momentum}")
                else:
                    logger.warning(f"  {sector_name}: No data for {analysis_date}")

            except Exception as e:
                logger.error(f"Error calculating {sector_name}: {e}")
                continue

        return results

    def _calculate_us_sectors(self, analysis_date: date) -> Dict[str, Dict]:
        """
        Calculate US sector performance using ETF prices

        Strategy:
        - Query ohlcv_data for sector ETFs (XLK, XLV, XLF, etc.)
        - Calculate returns from ETF prices
        - Note: This requires ETF data to be in ohlcv_data

        Args:
            analysis_date: Analysis date

        Returns:
            Sector performance dictionary
        """
        results = {}

        # Get sector ETF symbols
        sector_etfs = {
            sector: data["representative_etf"]
            for sector, data in US_SECTORS.items()
        }

        etf_symbols = list(sector_etfs.values())

        # SQL query to calculate ETF-based sector performance
        query = """
            WITH etf_prices AS (
                SELECT
                    o.ticker,
                    o.date,
                    o.close as current_close,
                    LAG(o.close, 1) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1d,
                    LAG(o.close, 5) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1w,
                    LAG(o.close, 21) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1m,
                    LAG(o.close, 63) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_3m
                FROM ohlcv_data o
                WHERE o.ticker = ANY(%s)
                  AND o.region = 'US'
                  AND o.timeframe = '1d'
                  AND o.date <= %s
                  AND o.date >= %s - INTERVAL '90 days'
            ),
            etf_returns AS (
                SELECT
                    ticker,
                    date,
                    CASE WHEN close_1d > 0
                         THEN ((current_close - close_1d) / close_1d) * 100
                         ELSE NULL END as return_1d,
                    CASE WHEN close_1w > 0
                         THEN ((current_close - close_1w) / close_1w) * 100
                         ELSE NULL END as return_1w,
                    CASE WHEN close_1m > 0
                         THEN ((current_close - close_1m) / close_1m) * 100
                         ELSE NULL END as return_1m,
                    CASE WHEN close_3m > 0
                         THEN ((current_close - close_3m) / close_3m) * 100
                         ELSE NULL END as return_3m
                FROM etf_prices
                WHERE date = %s
            )
            SELECT
                ticker,
                return_1d,
                return_1w,
                return_1m,
                return_3m
            FROM etf_returns;
        """

        try:
            rows = self.db.execute_query(
                query,
                (etf_symbols, analysis_date, analysis_date, analysis_date)
            )

            if not rows:
                logger.warning(f"No US sector ETF data for {analysis_date}")
                return results

            # Map ETF ticker to sector name
            etf_to_sector = {etf: sector for sector, etf in sector_etfs.items()}

            for row in rows:
                etf_ticker = row['ticker']
                sector_name = etf_to_sector.get(etf_ticker)

                if not sector_name:
                    continue

                # Extract returns
                return_1d = float(row['return_1d']) if row['return_1d'] is not None else 0.0
                return_1w = float(row['return_1w']) if row['return_1w'] is not None else 0.0
                return_1m = float(row['return_1m']) if row['return_1m'] is not None else 0.0
                return_3m = float(row['return_3m']) if row['return_3m'] is not None else 0.0

                # Classify momentum
                momentum = self._classify_momentum(return_1m)

                results[sector_name] = {
                    "avg_return_1d": round(return_1d, 4),
                    "avg_return_1w": round(return_1w, 4),
                    "avg_return_1m": round(return_1m, 4),
                    "avg_return_3m": round(return_3m, 4),
                    "num_stocks": 1,  # ETF represents sector
                    "strong_stocks": 1 if return_1m > 0 else 0,
                    "weak_stocks": 0 if return_1m > 0 else 1,
                    "momentum": momentum
                }

                logger.debug(f"  {sector_name} ({etf_ticker}): {return_1m:+.2f}% (1M), momentum={momentum}")

        except Exception as e:
            logger.error(f"Error calculating US sectors: {e}")

        return results

    def _classify_momentum(self, avg_return_1m: float) -> str:
        """
        Classify sector momentum based on 1-month return

        Classification:
        - strong: > 10%
        - moderate: 3% to 10%
        - weak: 0% to 3%
        - negative: < 0%

        Args:
            avg_return_1m: Average 1-month return

        Returns:
            Momentum classification string
        """
        if avg_return_1m > 10:
            return "strong"
        elif avg_return_1m > 3:
            return "moderate"
        elif avg_return_1m > 0:
            return "weak"
        else:
            return "negative"

    def identify_rotation(
        self,
        sector_performance: Dict[str, Dict]
    ) -> Dict[str, List[str]]:
        """
        Identify sector rotation patterns

        Rotation Patterns:
        - Growth → Value: Tech, Healthcare lead → Financials, Energy lead
        - Value → Growth: Financials, Energy lead → Tech, Healthcare lead
        - Risk-On → Risk-Off: Cyclicals → Defensives
        - Risk-Off → Risk-On: Defensives → Cyclicals

        Args:
            sector_performance: Sector performance dictionary

        Returns:
            {
                "leaders": ["Technology", "Healthcare"],    # Top 3 by 1M return
                "laggards": ["Utilities", "Real Estate"],  # Bottom 3 by 1M return
                "pattern": "Growth-Led",  # Rotation pattern
                "confidence": "high"      # Pattern confidence
            }
        """
        # Sort sectors by avg_return_1m
        sorted_sectors = sorted(
            sector_performance.items(),
            key=lambda x: x[1]["avg_return_1m"],
            reverse=True
        )

        # Get top 3 and bottom 3
        leaders = [s[0] for s in sorted_sectors[:3]]
        laggards = [s[0] for s in sorted_sectors[-3:]]

        # Determine rotation pattern
        pattern, confidence = self._determine_rotation_pattern(leaders, laggards)

        return {
            "leaders": leaders,
            "laggards": laggards,
            "pattern": pattern,
            "confidence": confidence
        }

    def _determine_rotation_pattern(
        self,
        leaders: List[str],
        laggards: List[str]
    ) -> Tuple[str, str]:
        """
        Determine rotation pattern based on leading/lagging sectors

        Args:
            leaders: Top performing sectors
            laggards: Bottom performing sectors

        Returns:
            (pattern, confidence) tuple
        """
        # Define sector categories
        growth_sectors = {"Technology", "Healthcare", "Information Technology", "Consumer Discretionary"}
        value_sectors = {"Financials", "Energy", "Materials"}
        defensive_sectors = {"Utilities", "Consumer Staples", "Real Estate"}
        cyclical_sectors = {"Industrials", "Materials", "Energy"}

        # Count sector types in leaders
        growth_count = sum(1 for s in leaders if s in growth_sectors)
        value_count = sum(1 for s in leaders if s in value_sectors)
        defensive_count = sum(1 for s in leaders if s in defensive_sectors)
        cyclical_count = sum(1 for s in leaders if s in cyclical_sectors)

        # Determine pattern
        if growth_count >= 2:
            pattern = "Growth-Led"
            confidence = "high" if growth_count == 3 else "medium"
        elif value_count >= 2:
            pattern = "Value-Led"
            confidence = "high" if value_count == 3 else "medium"
        elif defensive_count >= 2:
            pattern = "Defensive"
            confidence = "high" if defensive_count == 3 else "medium"
        elif cyclical_count >= 2:
            pattern = "Cyclical"
            confidence = "high" if cyclical_count == 3 else "medium"
        else:
            pattern = "Mixed"
            confidence = "low"

        return pattern, confidence

    def save_to_db(
        self,
        analysis_date: date,
        region: str,
        sector_performance: Dict[str, Dict]
    ) -> int:
        """
        Save sector performance to database

        Args:
            analysis_date: Analysis date
            region: Market region
            sector_performance: Sector performance dictionary

        Returns:
            Number of records inserted
        """
        inserted_count = 0

        for sector, metrics in sector_performance.items():
            query = """
                INSERT INTO sector_performance (
                    region,
                    sector,
                    date,
                    avg_return_1d,
                    avg_return_1w,
                    avg_return_1m,
                    avg_return_3m,
                    num_stocks,
                    strong_stocks,
                    weak_stocks,
                    momentum,
                    created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (region, sector, date)
                DO UPDATE SET
                    avg_return_1d = EXCLUDED.avg_return_1d,
                    avg_return_1w = EXCLUDED.avg_return_1w,
                    avg_return_1m = EXCLUDED.avg_return_1m,
                    avg_return_3m = EXCLUDED.avg_return_3m,
                    num_stocks = EXCLUDED.num_stocks,
                    strong_stocks = EXCLUDED.strong_stocks,
                    weak_stocks = EXCLUDED.weak_stocks,
                    momentum = EXCLUDED.momentum,
                    created_at = NOW()
                RETURNING id
            """

            try:
                success = self.db.execute_update(
                    query,
                    (region, sector, analysis_date,
                     metrics["avg_return_1d"], metrics["avg_return_1w"],
                     metrics["avg_return_1m"], metrics["avg_return_3m"],
                     metrics["num_stocks"], metrics["strong_stocks"],
                     metrics["weak_stocks"], metrics["momentum"])
                )

                if success:
                    inserted_count += 1
                    logger.debug(f"  Saved {region}/{sector}: {metrics['avg_return_1m']:+.2f}%")

            except Exception as e:
                logger.error(f"Error saving {region}/{sector}: {e}")
                continue

        logger.info(f"Saved {inserted_count} sector performance records for {region} on {analysis_date}")
        return inserted_count
