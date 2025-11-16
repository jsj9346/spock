# mcp_server/adapters/macro_adapter.py
"""
Macro Analysis Adapter for MCP Server

Provides comprehensive macro environment analysis with 6 data sources:

1. **Currency Valuations** (fx_valuation_signals)
   - FX rates, trends, volatility, attractiveness scores

2. **Global Market Indices** (global_market_indices)
   - Major equity indices (KR, US, JP, HK, CN, EU, UK)

3. **Bond Yields** (bond_yields) ✅ Phase 4
   - US Treasury yields (2Y, 10Y, 30Y)
   - Yield curve analysis (shape, spreads)

4. **Commodities** (commodities) ✅ Phase 4
   - Metals (Gold, Silver, Copper, Platinum)
   - Energy (Crude Oil, Natural Gas)

5. **Sector Performance** (sector_performance) ✅ Phase 4
   - KR sectors (10): Technology, Battery, Automobiles, etc.
   - US sectors (11): Technology, Healthcare, Financials, etc.
   - Sector rotation analysis

6. **Market Regime Classification** ✅ Enhanced Phase 4
   - Multi-factor analysis across all data sources
   - Risk-On / Risk-Off / Rotation / Defensive

Performance:
- Query time: <2s for full analysis (30-day lookback)
- Data freshness: Latest available (T-1 or T-0)
- Component selectivity: Choose specific data sources
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import structlog

from modules.db_manager_postgres import PostgresDatabaseManager
from ..utils.errors import DataNotFoundError, DatabaseError
from ..config import Config

logger = structlog.get_logger()


class MacroAdapter:
    """
    MCP macro analysis adapter.

    Aggregates macro economic indicators for AI-powered analysis:
    - Currency trends and valuations
    - Global equity index performance
    - Market regime classification

    Performance Targets:
    - Query time: <1s for 30-day lookback
    - Data freshness: Latest available (T-1 or T-0)
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize macro adapter.

        Args:
            config: Optional MCP configuration. Defaults to Config.from_env().
        """
        self.config = config or Config.from_env()

        # Initialize PostgreSQL database manager
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        logger.info("macro_adapter_initialized")

    async def analyze_macro_environment(
        self,
        analysis_date: str,
        lookback_days: int = 30,
        components: List[str] = None,
        regions: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze macro economic environment.

        Args:
            analysis_date: Analysis date (YYYY-MM-DD)
            lookback_days: Historical lookback period (default: 30)
            components: Components to analyze (default: ["currencies", "indices"])
                       Options: ["all", "currencies", "indices", "bonds", "commodities", "sectors"]
            regions: Regions to include (default: ["KR", "US"])

        Returns:
            {
                "analysis_date": "2024-01-05",
                "lookback_days": 30,
                "currencies": {
                    "USD": {"latest_rate": 1.0, "change_1m": 0.0, "trend": "stable", ...},
                    "HKD": {...},
                    "JPY": {...}
                },
                "indices": {
                    "^KS11": {"latest_close": 2500, "change_1m": 5.2, "trend": "bullish", ...},
                    "^GSPC": {...},
                    ...
                },
                "bonds": None,              # Phase 3
                "commodities": None,        # Phase 3
                "sectors": None,            # Phase 3
                "market_regime": "Risk-On"  # Risk-On/Off/Rotation/Defensive
            }

        Raises:
            DataNotFoundError: No data available for analysis date
            DatabaseError: Database query failed
        """
        try:
            # Parse date
            analysis_dt = datetime.strptime(analysis_date, "%Y-%m-%d").date()
            start_date = analysis_dt - timedelta(days=lookback_days)

            # Default components and regions
            if components is None:
                components = ["currencies", "indices"]
            elif "all" in components:
                components = ["currencies", "indices", "bonds", "commodities", "sectors"]

            if regions is None:
                regions = ["KR", "US"]

            # Build result
            result = {
                "analysis_date": analysis_date,
                "lookback_days": lookback_days,
                "currencies": None,
                "indices": None,
                "bonds": None,
                "commodities": None,
                "sectors": None,
                "market_regime": None,
            }

            # Fetch currencies
            if "currencies" in components:
                result["currencies"] = await self._get_currencies(
                    analysis_date=analysis_dt,
                    start_date=start_date,
                    regions=regions
                )

            # Fetch indices
            if "indices" in components:
                result["indices"] = await self._get_indices(
                    analysis_date=analysis_dt,
                    start_date=start_date,
                    regions=regions
                )

            # Fetch bonds
            if "bonds" in components:
                result["bonds"] = await self._get_bonds(
                    analysis_date=analysis_dt,
                    start_date=start_date,
                    regions=regions
                )

            # Fetch commodities
            if "commodities" in components:
                result["commodities"] = await self._get_commodities(
                    analysis_date=analysis_dt,
                    start_date=start_date
                )

            # Fetch sectors
            if "sectors" in components:
                result["sectors"] = await self._get_sectors(
                    analysis_date=analysis_dt,
                    start_date=start_date,
                    regions=regions
                )

            # Analyze market regime (with all available data)
            if result["currencies"] and result["indices"]:
                result["market_regime"] = await self._analyze_regime(
                    currencies=result["currencies"],
                    indices=result["indices"],
                    bonds=result["bonds"],
                    commodities=result["commodities"],
                    sectors=result["sectors"]
                )

            logger.info(
                "macro_analysis_completed",
                analysis_date=analysis_date,
                components=components,
                currencies_count=len(result["currencies"]) if result["currencies"] else 0,
                indices_count=len(result["indices"]) if result["indices"] else 0,
            )

            return result

        except ValueError as e:
            raise DataNotFoundError(f"Invalid date format: {e}")
        except Exception as e:
            logger.error("macro_analysis_error", error=str(e))
            raise DatabaseError(f"Macro analysis failed: {e}")

    async def _get_currencies(
        self,
        analysis_date: datetime.date,
        start_date: datetime.date,
        regions: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get currency valuations from fx_valuation_signals.

        Returns:
            {
                "USD": {
                    "region": "US",
                    "latest_rate": 1.0,
                    "latest_date": "2024-01-05",
                    "change_1d": 0.0,
                    "change_1w": 0.5,
                    "change_1m": 2.3,
                    "trend_score": 65.0,
                    "volatility": 1.2,
                    "attractiveness_score": 70.0,
                    "data_quality": "GOOD"
                },
                ...
            }
        """
        try:
            query = """
                WITH latest_data AS (
                    SELECT
                        currency,
                        region,
                        date,
                        usd_rate,
                        trend_score,
                        volatility,
                        attractiveness_score,
                        data_quality,
                        ROW_NUMBER() OVER (PARTITION BY currency ORDER BY date DESC) as rn
                    FROM fx_valuation_signals
                    WHERE date <= %s
                      AND region = ANY(%s)
                      AND data_quality = 'GOOD'
                ),
                historical AS (
                    SELECT
                        currency,
                        date,
                        usd_rate
                    FROM fx_valuation_signals
                    WHERE date BETWEEN %s AND %s
                      AND region = ANY(%s)
                      AND data_quality = 'GOOD'
                )
                SELECT
                    l.currency,
                    l.region,
                    l.date as latest_date,
                    l.usd_rate as latest_rate,
                    l.trend_score,
                    l.volatility,
                    l.attractiveness_score,
                    l.data_quality,
                    -- Calculate returns
                    (SELECT usd_rate FROM historical WHERE currency = l.currency AND date <= l.date - INTERVAL '1 day' ORDER BY date DESC LIMIT 1) as rate_1d_ago,
                    (SELECT usd_rate FROM historical WHERE currency = l.currency AND date <= l.date - INTERVAL '7 days' ORDER BY date DESC LIMIT 1) as rate_1w_ago,
                    (SELECT usd_rate FROM historical WHERE currency = l.currency AND date <= l.date - INTERVAL '30 days' ORDER BY date DESC LIMIT 1) as rate_1m_ago
                FROM latest_data l
                WHERE l.rn = 1
                ORDER BY l.currency
            """

            results = self.db_manager.execute_query(
                query,
                (analysis_date, regions, start_date, analysis_date, regions)
            )

            if not results:
                raise DataNotFoundError(f"No currency data for {analysis_date}")

            currencies = {}
            for row in results:
                # Calculate percentage changes
                change_1d = 0.0
                change_1w = 0.0
                change_1m = 0.0

                if row.get('rate_1d_ago'):
                    change_1d = ((row['latest_rate'] - row['rate_1d_ago']) / row['rate_1d_ago']) * 100
                if row.get('rate_1w_ago'):
                    change_1w = ((row['latest_rate'] - row['rate_1w_ago']) / row['rate_1w_ago']) * 100
                if row.get('rate_1m_ago'):
                    change_1m = ((row['latest_rate'] - row['rate_1m_ago']) / row['rate_1m_ago']) * 100

                currencies[row['currency']] = {
                    "region": row['region'],
                    "latest_rate": float(row['latest_rate']),
                    "latest_date": row['latest_date'].isoformat(),
                    "change_1d": round(change_1d, 2),
                    "change_1w": round(change_1w, 2),
                    "change_1m": round(change_1m, 2),
                    "trend_score": float(row['trend_score']) if row.get('trend_score') else None,
                    "volatility": float(row['volatility']) if row.get('volatility') else None,
                    "attractiveness_score": float(row['attractiveness_score']) if row.get('attractiveness_score') else None,
                    "data_quality": row['data_quality']
                }

            return currencies

        except Exception as e:
            logger.error("get_currencies_error", error=str(e))
            raise DatabaseError(f"Currency query failed: {e}")

    async def _get_indices(
        self,
        analysis_date: datetime.date,
        start_date: datetime.date,
        regions: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get global market indices from global_market_indices.

        Returns:
            {
                "^KS11": {
                    "name": "KOSPI",
                    "region": "KR",
                    "latest_close": 2500.0,
                    "latest_date": "2024-01-05",
                    "change_1d": 1.2,
                    "change_1w": 3.5,
                    "change_1m": 8.7,
                    "volume": 1000000000,
                    "trend": "bullish"
                },
                ...
            }
        """
        try:
            # Index to region mapping
            index_region_map = {
                "^KS11": "KR",   # KOSPI
                "^KQ11": "KR",   # KOSDAQ
                "^GSPC": "US",   # S&P 500
                "^IXIC": "US",   # NASDAQ
                "^DJI": "US",    # Dow Jones
                "^N225": "JP",   # Nikkei
                "^HSI": "HK",    # Hang Seng
                "000001.SS": "CN",  # Shanghai
                "^STOXX": "EU",  # STOXX 50
                "^FTSE": "UK",   # FTSE 100
            }

            # Filter indices by region
            target_indices = [idx for idx, reg in index_region_map.items()
                            if reg in regions or reg in ["JP", "HK", "CN", "EU", "UK"]]

            query = """
                WITH latest_data AS (
                    SELECT
                        symbol,
                        date,
                        close_price,
                        volume,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM global_market_indices
                    WHERE date <= %s
                      AND symbol = ANY(%s)
                ),
                historical AS (
                    SELECT
                        symbol,
                        date,
                        close_price
                    FROM global_market_indices
                    WHERE date BETWEEN %s AND %s
                      AND symbol = ANY(%s)
                )
                SELECT
                    l.symbol,
                    l.date as latest_date,
                    l.close_price as latest_close,
                    l.volume,
                    -- Calculate historical closes
                    (SELECT close_price FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '1 day' ORDER BY date DESC LIMIT 1) as close_1d_ago,
                    (SELECT close_price FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '7 days' ORDER BY date DESC LIMIT 1) as close_1w_ago,
                    (SELECT close_price FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '30 days' ORDER BY date DESC LIMIT 1) as close_1m_ago
                FROM latest_data l
                WHERE l.rn = 1
                ORDER BY l.symbol
            """

            results = self.db_manager.execute_query(
                query,
                (analysis_date, target_indices, start_date, analysis_date, target_indices)
            )

            if not results:
                raise DataNotFoundError(f"No index data for {analysis_date}")

            # Index names
            index_names = {
                "^KS11": "KOSPI",
                "^KQ11": "KOSDAQ",
                "^GSPC": "S&P 500",
                "^IXIC": "NASDAQ",
                "^DJI": "Dow Jones",
                "^N225": "Nikkei 225",
                "^HSI": "Hang Seng",
                "000001.SS": "Shanghai Composite",
                "^STOXX": "STOXX 50",
                "^FTSE": "FTSE 100"
            }

            indices = {}
            for row in results:
                symbol = row['symbol']

                # Calculate percentage changes
                change_1d = 0.0
                change_1w = 0.0
                change_1m = 0.0

                if row.get('close_1d_ago'):
                    change_1d = ((row['latest_close'] - row['close_1d_ago']) / row['close_1d_ago']) * 100
                if row.get('close_1w_ago'):
                    change_1w = ((row['latest_close'] - row['close_1w_ago']) / row['close_1w_ago']) * 100
                if row.get('close_1m_ago'):
                    change_1m = ((row['latest_close'] - row['close_1m_ago']) / row['close_1m_ago']) * 100

                # Determine trend
                trend = "neutral"
                if change_1w > 2:
                    trend = "bullish"
                elif change_1w < -2:
                    trend = "bearish"

                indices[symbol] = {
                    "name": index_names.get(symbol, symbol),
                    "region": index_region_map.get(symbol, "UNKNOWN"),
                    "latest_close": float(row['latest_close']),
                    "latest_date": row['latest_date'].isoformat(),
                    "change_1d": round(change_1d, 2),
                    "change_1w": round(change_1w, 2),
                    "change_1m": round(change_1m, 2),
                    "volume": int(row['volume']) if row.get('volume') else None,
                    "trend": trend
                }

            return indices

        except Exception as e:
            logger.error("get_indices_error", error=str(e))
            raise DatabaseError(f"Index query failed: {e}")

    async def _get_bonds(
        self,
        analysis_date: datetime.date,
        start_date: datetime.date,
        regions: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get bond yields from bond_yields table.

        Returns:
            {
                "US2Y": {
                    "country": "US",
                    "maturity": "3M",
                    "latest_yield": 4.94,
                    "latest_date": "2025-01-10",
                    "change_1d": -2.0,
                    "change_1w": 5.0,
                    "change_1m": 10.0
                },
                "US10Y": {...},
                "US30Y": {...},
                "yield_curve": {
                    "10Y_2Y_spread": -0.50,
                    "30Y_10Y_spread": 0.20,
                    "curve_shape": "inverted"
                }
            }
        """
        try:
            # Map regions to countries
            country_map = {"US": "US", "KR": "KR", "JP": "JP", "EU": "DE"}
            target_countries = [country_map.get(r, r) for r in regions if r in country_map]

            query = """
                WITH latest_data AS (
                    SELECT
                        symbol,
                        country,
                        maturity,
                        date,
                        yield,
                        change_bps,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM bond_yields
                    WHERE date <= %s
                      AND country = ANY(%s)
                ),
                historical AS (
                    SELECT
                        symbol,
                        date,
                        yield
                    FROM bond_yields
                    WHERE date BETWEEN %s AND %s
                      AND country = ANY(%s)
                )
                SELECT
                    l.symbol,
                    l.country,
                    l.maturity,
                    l.date as latest_date,
                    l.yield as latest_yield,
                    l.change_bps,
                    (SELECT yield FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '1 day' ORDER BY date DESC LIMIT 1) as yield_1d_ago,
                    (SELECT yield FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '7 days' ORDER BY date DESC LIMIT 1) as yield_1w_ago,
                    (SELECT yield FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '30 days' ORDER BY date DESC LIMIT 1) as yield_1m_ago
                FROM latest_data l
                WHERE l.rn = 1
                ORDER BY l.symbol
            """

            results = self.db_manager.execute_query(
                query,
                (analysis_date, target_countries, start_date, analysis_date, target_countries)
            )

            if not results:
                return {}

            bonds = {}
            us_yields = {}  # For yield curve calculation

            for row in results:
                # Calculate basis point changes
                change_1d_bps = 0.0
                change_1w_bps = 0.0
                change_1m_bps = 0.0

                if row.get('yield_1d_ago'):
                    change_1d_bps = (row['latest_yield'] - row['yield_1d_ago']) * 100
                if row.get('yield_1w_ago'):
                    change_1w_bps = (row['latest_yield'] - row['yield_1w_ago']) * 100
                if row.get('yield_1m_ago'):
                    change_1m_bps = (row['latest_yield'] - row['yield_1m_ago']) * 100

                bonds[row['symbol']] = {
                    "country": row['country'],
                    "maturity": row['maturity'],
                    "latest_yield": float(row['latest_yield']),
                    "latest_date": row['latest_date'].isoformat(),
                    "change_1d_bps": round(change_1d_bps, 1),
                    "change_1w_bps": round(change_1w_bps, 1),
                    "change_1m_bps": round(change_1m_bps, 1)
                }

                # Store US yields for curve calculation
                if row['country'] == 'US':
                    us_yields[row['symbol']] = float(row['latest_yield'])

            # Calculate yield curve spreads for US
            if 'US10Y' in us_yields and 'US2Y' in us_yields:
                spread_10y_2y = us_yields['US10Y'] - us_yields['US2Y']
                spread_30y_10y = us_yields.get('US30Y', 0) - us_yields['US10Y'] if 'US30Y' in us_yields else None

                # Determine curve shape
                curve_shape = "normal"
                if spread_10y_2y < -0.1:
                    curve_shape = "inverted"
                elif spread_10y_2y < 0.1:
                    curve_shape = "flat"
                elif spread_10y_2y > 1.0:
                    curve_shape = "steep"

                bonds["yield_curve"] = {
                    "10Y_2Y_spread": round(spread_10y_2y, 2),
                    "30Y_10Y_spread": round(spread_30y_10y, 2) if spread_30y_10y is not None else None,
                    "curve_shape": curve_shape
                }

            return bonds

        except Exception as e:
            logger.error("get_bonds_error", error=str(e))
            raise DatabaseError(f"Bond query failed: {e}")

    async def _get_commodities(
        self,
        analysis_date: datetime.date,
        start_date: datetime.date
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get commodity prices from commodities table.

        Returns:
            {
                "GC=F": {
                    "name": "Gold Futures",
                    "category": "Metals",
                    "latest_price": 2397.44,
                    "latest_date": "2025-01-10",
                    "change_1d": 0.5,
                    "change_1w": 2.3,
                    "change_1m": 5.8
                },
                ...
                "by_category": {
                    "Metals": {"avg_change_1m": 4.2, "count": 4},
                    "Energy": {"avg_change_1m": -2.1, "count": 2}
                }
            }
        """
        try:
            query = """
                WITH latest_data AS (
                    SELECT
                        symbol,
                        name,
                        category,
                        date,
                        close,
                        change_pct,
                        ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM commodities
                    WHERE date <= %s
                ),
                historical AS (
                    SELECT
                        symbol,
                        date,
                        close
                    FROM commodities
                    WHERE date BETWEEN %s AND %s
                )
                SELECT
                    l.symbol,
                    l.name,
                    l.category,
                    l.date as latest_date,
                    l.close as latest_price,
                    l.change_pct,
                    (SELECT close FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '1 day' ORDER BY date DESC LIMIT 1) as price_1d_ago,
                    (SELECT close FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '7 days' ORDER BY date DESC LIMIT 1) as price_1w_ago,
                    (SELECT close FROM historical WHERE symbol = l.symbol AND date <= l.date - INTERVAL '30 days' ORDER BY date DESC LIMIT 1) as price_1m_ago
                FROM latest_data l
                WHERE l.rn = 1
                ORDER BY l.category, l.symbol
            """

            results = self.db_manager.execute_query(
                query,
                (analysis_date, start_date, analysis_date)
            )

            if not results:
                return {}

            commodities = {}
            category_stats = {}

            for row in results:
                # Calculate percentage changes
                change_1d = 0.0
                change_1w = 0.0
                change_1m = 0.0

                if row.get('price_1d_ago') and row['price_1d_ago'] > 0:
                    change_1d = ((row['latest_price'] - row['price_1d_ago']) / row['price_1d_ago']) * 100
                if row.get('price_1w_ago') and row['price_1w_ago'] > 0:
                    change_1w = ((row['latest_price'] - row['price_1w_ago']) / row['price_1w_ago']) * 100
                if row.get('price_1m_ago') and row['price_1m_ago'] > 0:
                    change_1m = ((row['latest_price'] - row['price_1m_ago']) / row['price_1m_ago']) * 100

                commodities[row['symbol']] = {
                    "name": row['name'],
                    "category": row['category'],
                    "latest_price": float(row['latest_price']),
                    "latest_date": row['latest_date'].isoformat(),
                    "change_1d": round(change_1d, 2),
                    "change_1w": round(change_1w, 2),
                    "change_1m": round(change_1m, 2)
                }

                # Aggregate by category
                category = row['category']
                if category not in category_stats:
                    category_stats[category] = {"changes": [], "count": 0}
                category_stats[category]["changes"].append(change_1m)
                category_stats[category]["count"] += 1

            # Calculate category averages
            commodities["by_category"] = {}
            for category, stats in category_stats.items():
                avg_change = sum(stats["changes"]) / len(stats["changes"]) if stats["changes"] else 0
                commodities["by_category"][category] = {
                    "avg_change_1m": round(avg_change, 2),
                    "count": stats["count"]
                }

            return commodities

        except Exception as e:
            logger.error("get_commodities_error", error=str(e))
            raise DatabaseError(f"Commodity query failed: {e}")

    async def _get_sectors(
        self,
        analysis_date: datetime.date,
        start_date: datetime.date,
        regions: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get sector performance from sector_performance table.

        Returns:
            {
                "KR": {
                    "Technology": {
                        "avg_return_1d": -0.39,
                        "avg_return_1w": 3.04,
                        "avg_return_1m": 8.31,
                        "momentum": "moderate",
                        "num_stocks": 5,
                        "strong_stocks": 3
                    },
                    ...
                    "rotation": {
                        "leaders": ["Construction", "Automobiles", "Chemicals"],
                        "laggards": ["Battery", "Retail", "Utilities"],
                        "pattern": "Growth-Led"
                    }
                },
                "US": {...}
            }
        """
        try:
            query = """
                WITH latest_data AS (
                    SELECT
                        region,
                        sector,
                        date,
                        avg_return_1d,
                        avg_return_1w,
                        avg_return_1m,
                        avg_return_3m,
                        num_stocks,
                        strong_stocks,
                        momentum,
                        ROW_NUMBER() OVER (PARTITION BY region, sector ORDER BY date DESC) as rn
                    FROM sector_performance
                    WHERE date <= %s
                      AND region = ANY(%s)
                )
                SELECT
                    region,
                    sector,
                    date,
                    avg_return_1d,
                    avg_return_1w,
                    avg_return_1m,
                    avg_return_3m,
                    num_stocks,
                    strong_stocks,
                    momentum
                FROM latest_data
                WHERE rn = 1
                ORDER BY region, avg_return_1m DESC
            """

            results = self.db_manager.execute_query(
                query,
                (analysis_date, regions)
            )

            if not results:
                return {}

            sectors_by_region = {}

            for row in results:
                region = row['region']
                sector = row['sector']

                if region not in sectors_by_region:
                    sectors_by_region[region] = {}

                sectors_by_region[region][sector] = {
                    "avg_return_1d": float(row['avg_return_1d']) if row.get('avg_return_1d') else 0.0,
                    "avg_return_1w": float(row['avg_return_1w']) if row.get('avg_return_1w') else 0.0,
                    "avg_return_1m": float(row['avg_return_1m']) if row.get('avg_return_1m') else 0.0,
                    "avg_return_3m": float(row['avg_return_3m']) if row.get('avg_return_3m') else 0.0,
                    "momentum": row['momentum'],
                    "num_stocks": int(row['num_stocks']) if row.get('num_stocks') else 0,
                    "strong_stocks": int(row['strong_stocks']) if row.get('strong_stocks') else 0
                }

            # Calculate rotation analysis for each region
            for region, sectors in sectors_by_region.items():
                # Sort sectors by 1m return
                sorted_sectors = sorted(
                    sectors.items(),
                    key=lambda x: x[1]['avg_return_1m'],
                    reverse=True
                )

                leaders = [s[0] for s in sorted_sectors[:3]]
                laggards = [s[0] for s in sorted_sectors[-3:]]

                # Determine rotation pattern
                pattern = "Mixed"
                if len(sorted_sectors) >= 3:
                    top_avg = sum(s[1]['avg_return_1m'] for s in sorted_sectors[:3]) / 3
                    if top_avg > 10:
                        pattern = "Growth-Led"
                    elif top_avg > 5:
                        pattern = "Cyclical"
                    else:
                        # Check if defensive sectors (Utilities, Consumer Staples, Healthcare) are leading
                        defensive_sectors = ["Utilities", "Consumer Staples", "Healthcare"]
                        if any(s in leaders for s in defensive_sectors):
                            pattern = "Defensive"

                sectors_by_region[region]["rotation"] = {
                    "leaders": leaders,
                    "laggards": laggards,
                    "pattern": pattern
                }

            return sectors_by_region

        except Exception as e:
            logger.error("get_sectors_error", error=str(e))
            raise DatabaseError(f"Sector query failed: {e}")

    async def _analyze_regime(
        self,
        currencies: Dict[str, Dict[str, Any]],
        indices: Dict[str, Dict[str, Any]],
        bonds: Optional[Dict[str, Dict[str, Any]]] = None,
        commodities: Optional[Dict[str, Dict[str, Any]]] = None,
        sectors: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> str:
        """
        Analyze market regime based on all available macro indicators.

        Market Regimes:
        - Risk-On: Indices up, USD weak, yields rising, commodities strong, growth sectors leading
        - Risk-Off: Indices down, USD strong, yields falling, gold up, defensive sectors leading
        - Rotation: Mixed signals, sector rotation ongoing
        - Defensive: Low volatility, minimal changes, flat yield curve

        Data Sources:
        - Currencies: USD strength, safe haven flows
        - Indices: Equity market trends
        - Bonds: Yield curve shape, rate expectations
        - Commodities: Risk appetite (gold vs energy)
        - Sectors: Growth vs defensive leadership

        Returns:
            Market regime classification: "Risk-On", "Risk-Off", "Rotation", "Defensive"
        """
        try:
            # === Core Indicators (Currencies & Indices) ===
            bullish_count = sum(1 for idx in indices.values() if idx.get('trend') == 'bullish')
            bearish_count = sum(1 for idx in indices.values() if idx.get('trend') == 'bearish')
            total_indices = len(indices)

            # USD strength (negative change = USD weakening)
            usd_change = currencies.get('USD', {}).get('change_1w', 0)

            # Safe haven currencies (JPY typically)
            jpy_change = currencies.get('JPY', {}).get('change_1w', 0)

            # Average index change
            avg_index_change = sum(idx.get('change_1w', 0) for idx in indices.values()) / total_indices if total_indices > 0 else 0

            # === Extended Indicators ===
            # Bond signals (yield curve)
            yield_curve_inverted = False
            yields_rising = False
            if bonds and 'yield_curve' in bonds:
                curve = bonds['yield_curve']
                if curve.get('curve_shape') == 'inverted':
                    yield_curve_inverted = True
                # Rising yields = risk-on (economic growth expectations)
                us10y_change = bonds.get('US10Y', {}).get('change_1w_bps', 0)
                yields_rising = us10y_change > 5  # >5bps increase

            # Commodity signals
            gold_strong = False
            energy_strong = False
            if commodities and 'by_category' in commodities:
                metals_change = commodities['by_category'].get('Metals', {}).get('avg_change_1m', 0)
                energy_change = commodities['by_category'].get('Energy', {}).get('avg_change_1m', 0)
                gold_strong = metals_change > 3  # Gold/metals rising > risk-off
                energy_strong = energy_change > 3  # Energy rising > risk-on

            # Sector signals
            growth_leading = False
            defensive_leading = False
            if sectors:
                for region, region_sectors in sectors.items():
                    if 'rotation' in region_sectors:
                        pattern = region_sectors['rotation'].get('pattern', '')
                        if pattern == 'Growth-Led':
                            growth_leading = True
                        elif pattern == 'Defensive':
                            defensive_leading = True

            # === Multi-Factor Regime Classification ===
            risk_on_signals = 0
            risk_off_signals = 0

            # Equity signals (weight: 3)
            if bullish_count >= total_indices * 0.7 and avg_index_change > 2:
                risk_on_signals += 3
            elif bearish_count >= total_indices * 0.7 and avg_index_change < -2:
                risk_off_signals += 3

            # Currency signals (weight: 2)
            if usd_change < -0.5:  # USD weakening
                risk_on_signals += 2
            elif usd_change > 0.5 or jpy_change > 0.5:  # USD/JPY strengthening
                risk_off_signals += 2

            # Bond signals (weight: 2)
            if yields_rising:
                risk_on_signals += 2
            if yield_curve_inverted:
                risk_off_signals += 2

            # Commodity signals (weight: 1)
            if energy_strong:
                risk_on_signals += 1
            if gold_strong:
                risk_off_signals += 1

            # Sector signals (weight: 2)
            if growth_leading:
                risk_on_signals += 2
            if defensive_leading:
                risk_off_signals += 2

            # Final classification
            total_signals = risk_on_signals + risk_off_signals

            if total_signals == 0 or abs(avg_index_change) < 1:
                return "Defensive"

            # Strong directional signal (>70% agreement)
            risk_on_pct = risk_on_signals / total_signals if total_signals > 0 else 0
            if risk_on_pct > 0.7:
                return "Risk-On"
            elif risk_on_pct < 0.3:
                return "Risk-Off"
            else:
                return "Rotation"

        except Exception as e:
            logger.error("analyze_regime_error", error=str(e))
            return "Unknown"
