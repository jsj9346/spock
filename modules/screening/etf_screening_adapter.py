# modules/screening/etf_screening_adapter.py
"""
ETFScreeningAdapter - Adapter for ETF screening and filtering.

Provides ETF screening capabilities using available data sources:
- Ticker metadata (name, listing_date) from tickers table
- Price history (OHLCV) for performance metrics
- Technical indicators (RSI, MA trends) for trend analysis
- Name parsing for sector/theme approximation

Known Limitations (documented):
- AUM (Assets Under Management): Not readily available from Korean sources
- TER (Total Expense Ratio): Requires complex web scraping
- Tracking Error: Limited data availability
- Sector/Theme: Approximated from ETF name parsing

Architecture Pattern:
    MCP Tool -> ETFScreeningAdapter -> PostgresDatabaseManager -> PostgreSQL

Performance:
    - screen_etfs: <2s for 100 ETFs, <5s for full KR market
    - Cache TTL: 60 seconds

Author: Spock MCP Server
Date: 2025-10-31
Phase: ETF Screening Tool - Phase 2
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import re

from mcp_server.config import Config
from mcp_server.utils.errors import (
    DatabaseError,
    ValidationError,
    SpockMCPError,
)
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.screening.technical_calculator import TechnicalCalculator
from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.adapters.tech_screening_adapter import TechScreeningAdapter


class ETFScreeningAdapter:
    """
    MCP adapter for ETF screening.

    Screens ETFs using available data sources with intelligent
    workarounds for missing data fields.

    Example:
        >>> adapter = ETFScreeningAdapter()
        >>> result = await adapter.screen_etfs(
        ...     filters={"name_pattern": "반도체"},
        ...     technical_filters={"ma_trend": "bullish", "rsi_max": 70},
        ...     region="KR",
        ...     limit=20
        ... )
        >>> len(result["etfs"])
        5
    """

    # Sector keyword mapping for name-based filtering
    SECTOR_KEYWORDS = {
        "반도체": "Semiconductor",
        "배터리": "Battery",
        "2차전지": "Secondary Battery",
        "바이오": "Bio/Healthcare",
        "금융": "Finance",
        "IT": "Information Technology",
        "에너지": "Energy",
        "부동산": "Real Estate",
        "자동차": "Automotive",
        "화학": "Chemical",
        "건설": "Construction",
        "철강": "Steel",
        "유통": "Retail",
        "엔터": "Entertainment",
        "미디어": "Media",
        "게임": "Game",
        "콘텐츠": "Contents",
    }

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize ETFScreeningAdapter.

        Args:
            config: Optional MCP config (default: load from env)
        """
        self.config = config or Config.from_env()

        # Initialize database manager
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        # Initialize technical calculator for indicators (Legacy, kept for backward compatibility)
        self.technical_calculator = TechnicalCalculator()

        # Initialize data adapter for OHLCV fetching
        self.data_adapter = DataAdapter(config=self.config)

        # Initialize TechScreeningAdapter for DB-level technical indicators (Optimized)
        self.tech_screening_adapter = TechScreeningAdapter(config=self.config)

        # Cache for screening results (60 second TTL)
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 60  # seconds

        logger.info("etf_screening_adapter_initialized")

    async def screen_etfs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        technical_filters: Optional[Dict[str, Any]] = None,
        region: str = "KR",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Screen ETFs by available criteria.

        Filters ETFs using:
        1. Name pattern matching (for sector/theme approximation)
        2. Listing date filtering
        3. Technical indicators (RSI, MA trends)
        4. Performance metrics (price change, volume)

        Args:
            filters: Dictionary of basic screening criteria:
                - name_pattern: ETF name substring (e.g., "반도체" for semiconductor)
                - listing_date_after: Filter ETFs listed after this date (YYYY-MM-DD)
                - listing_date_before: Filter ETFs listed before this date (YYYY-MM-DD)
            technical_filters: Dictionary of technical criteria:
                - rsi_min: Minimum RSI value (0-100)
                - rsi_max: Maximum RSI value (0-100)
                - ma_trend: Required MA trend ("bullish", "bearish", "neutral")
                - price_change_1m_min: Minimum 1-month price change % (e.g., -10.0)
                - price_change_1m_max: Maximum 1-month price change % (e.g., 50.0)
                - volume_avg_20d_min: Minimum 20-day average volume
            region: Market region (KR, US)
            limit: Maximum number of results (default: 50, max: 200)

        Returns:
            Dictionary with screening results:
            {
                "success": true,
                "etfs": [
                    {
                        "ticker": "069500",
                        "name": "KODEX 200",
                        "listing_date": "2002-10-14",
                        "sector_theme": "Broad Market",  # Parsed from name
                        "current_price": 35500,
                        "price_change_1m": 5.2,
                        "volume_avg_20d": 2500000,
                        "rsi": 65.0,
                        "rsi_signal": "neutral",
                        "ma_trend": "bullish",
                        "ma20": 35000,
                        "ma50": 34500,
                        "ma200": 33000
                    },
                    ...
                ],
                "count": 5,
                "total_matching": 12,
                "filters_applied": {...},
                "technical_filters_applied": {...},
                "region": "KR",
                "limitations": [
                    "AUM data not available",
                    "TER data not available",
                    "Sector/theme approximated from name"
                ]
            }

        Raises:
            ValidationError: Invalid filter parameters
            DatabaseError: Database query failure
        """
        try:
            # Use empty dict if filters not provided
            filters = filters or {}

            # Validate inputs
            self._validate_filters(filters)
            if technical_filters:
                self._validate_technical_filters(technical_filters)
            self._validate_region(region)
            self._validate_limit(limit)

            # Check cache
            cache_key = self._make_cache_key(filters, region, limit, technical_filters)
            if self._is_cache_valid(cache_key):
                logger.debug("cache_hit", key=cache_key)
                return self._cache[cache_key]

            logger.info("screening_etfs_start",
                       filters=filters,
                       technical_filters=technical_filters,
                       region=region,
                       limit=limit)

            # Get all ETFs from tickers table
            with self.db_manager._get_connection() as conn:
                with conn.cursor() as cursor:
                    query = """
                        SELECT ticker, name, listing_date
                        FROM tickers
                        WHERE region = %s
                          AND asset_type = 'ETF'
                          AND ticker SIMILAR TO '[0-9]{6}'
                    """
                    params = [region]

                    # Apply listing date filters
                    if "listing_date_after" in filters:
                        query += " AND listing_date >= %s"
                        params.append(filters["listing_date_after"])

                    if "listing_date_before" in filters:
                        query += " AND listing_date <= %s"
                        params.append(filters["listing_date_before"])

                    query += " ORDER BY ticker"

                    cursor.execute(query, params)
                    etf_records = cursor.fetchall()

            logger.info(f"fetched_etfs: {len(etf_records)} total ETFs")

            # Convert to dict format
            etfs = []
            for record in etf_records:
                etf = {
                    "ticker": record[0],
                    "name": record[1],
                    "listing_date": record[2].isoformat() if record[2] else None,
                }
                etfs.append(etf)

            # Apply name pattern filter
            if "name_pattern" in filters and filters["name_pattern"]:
                pattern = filters["name_pattern"].lower()
                etfs = [etf for etf in etfs if pattern in etf["name"].lower()]
                logger.info(f"name_filter: {len(etfs)} ETFs match pattern '{pattern}'")

            if not etfs:
                return {
                    "success": True,
                    "etfs": [],
                    "count": 0,
                    "total_matching": 0,
                    "filters_applied": filters,
                    "technical_filters_applied": technical_filters or {},
                    "region": region,
                    "timestamp": datetime.now().isoformat(),
                    "limitations": self._get_limitations(),
                }

            # Parse sector/theme from names
            for etf in etfs:
                etf["sector_theme"] = self._parse_sector_from_name(etf["name"])

            # Fetch technical indicators using TechScreeningAdapter (DB-level, 5x faster)
            etf_tickers = [etf["ticker"] for etf in etfs]

            logger.info(f"fetching_tech_indicators_v2: {len(etf_tickers)} ETFs")

            # Build technical filters for TechScreeningAdapter format
            tech_adapter_filters = {}
            if technical_filters:
                # Convert to TechScreeningAdapter format
                if "rsi_min" in technical_filters:
                    tech_adapter_filters["rsi_min"] = technical_filters["rsi_min"]
                if "rsi_max" in technical_filters:
                    tech_adapter_filters["rsi_max"] = technical_filters["rsi_max"]
                if "ma_trend" in technical_filters:
                    tech_adapter_filters["trend"] = technical_filters["ma_trend"]

            try:
                # DB 레벨에서 기술적 지표 조회
                tech_result = await self.tech_screening_adapter.get_indicators_for_tickers(
                    tickers=etf_tickers,
                    region=region,
                    filters=tech_adapter_filters if tech_adapter_filters else None
                )

                if tech_result.get("success"):
                    indicators = tech_result.get("indicators", {})
                    passing_tickers = set(indicators.keys())
                    logger.info(
                        f"tech_indicators_v2_fetched: {len(indicators)} ETFs with data",
                        execution_time_ms=tech_result.get("execution_time_ms", 0)
                    )
                else:
                    logger.warning("tech_indicators_v2_failed, falling back to legacy method")
                    indicators, passing_tickers = await self._fetch_indicators_legacy(
                        etf_tickers, region, technical_filters
                    )

            except Exception as e:
                logger.error(f"tech_indicators_v2_error: {e}, falling back to legacy method")
                indicators, passing_tickers = await self._fetch_indicators_legacy(
                    etf_tickers, region, technical_filters
                )

            # Apply additional filters (price_change, volume) - these require indicators data
            if technical_filters:
                # Price change filter (1-month) - use price_change_1m from TechScreeningAdapter
                if "price_change_1m_min" in technical_filters or "price_change_1m_max" in technical_filters:
                    price_passing = set()
                    for ticker in passing_tickers:
                        if ticker in indicators:
                            price_change = indicators[ticker].get("price_change_1m")
                            if price_change is not None:
                                passes = True
                                if "price_change_1m_min" in technical_filters:
                                    passes = passes and price_change >= technical_filters["price_change_1m_min"]
                                if "price_change_1m_max" in technical_filters:
                                    passes = passes and price_change <= technical_filters["price_change_1m_max"]
                                if passes:
                                    price_passing.add(ticker)

                    passing_tickers = passing_tickers.intersection(price_passing)
                    logger.info(f"price_change_filter: {len(passing_tickers)} ETFs pass")

                # Volume filter (20-day average) - use avg_volume_20d from TechScreeningAdapter
                if "volume_avg_20d_min" in technical_filters:
                    volume_passing = set()
                    for ticker in passing_tickers:
                        if ticker in indicators:
                            volume_avg = indicators[ticker].get("avg_volume_20d")
                            if volume_avg is not None and volume_avg >= technical_filters["volume_avg_20d_min"]:
                                volume_passing.add(ticker)

                    passing_tickers = passing_tickers.intersection(volume_passing)
                    logger.info(f"volume_filter: {len(passing_tickers)} ETFs pass")

            # Build final ETF results with all data
            etf_results = []
            for etf in etfs:
                ticker = etf["ticker"]

                # Only include ETFs that pass technical filters
                if ticker not in passing_tickers:
                    continue

                etf_data = {
                    "ticker": ticker,
                    "name": etf["name"],
                    "listing_date": etf["listing_date"],
                    "sector_theme": etf["sector_theme"],
                }

                # Add technical indicators (TechScreeningAdapter flat format)
                if ticker in indicators:
                    tech_data = indicators[ticker]
                    # RSI data
                    etf_data["rsi"] = tech_data.get("rsi")
                    if tech_data.get("rsi") is not None:
                        rsi_val = tech_data.get("rsi")
                        if rsi_val < 30:
                            etf_data["rsi_signal"] = "oversold"
                        elif rsi_val > 70:
                            etf_data["rsi_signal"] = "overbought"
                        else:
                            etf_data["rsi_signal"] = "neutral"

                    # MA data
                    etf_data["ma_trend"] = tech_data.get("trend")
                    etf_data["current_price"] = tech_data.get("price")
                    etf_data["ma20"] = tech_data.get("ma20")
                    etf_data["ma50"] = tech_data.get("ma50")
                    etf_data["ma200"] = tech_data.get("ma200")
                    etf_data["price_vs_ma20"] = tech_data.get("price_vs_ma20")
                    etf_data["price_vs_ma200"] = tech_data.get("price_vs_ma200")
                    etf_data["ma_crossover"] = tech_data.get("ma_crossover")
                    etf_data["ma20_distance"] = tech_data.get("ma20_distance")

                    # Performance metrics (from TechScreeningAdapter)
                    etf_data["price_change_1m"] = tech_data.get("price_change_1m")
                    etf_data["volume_avg_20d"] = tech_data.get("avg_volume_20d")
                    etf_data["volume_surge"] = tech_data.get("volume_surge")
                    etf_data["volume_ratio"] = tech_data.get("volume_ratio")

                etf_results.append(etf_data)

            # Sort by name for consistent ordering
            etf_results.sort(key=lambda x: x["name"])

            # Apply limit
            etf_results_limited = etf_results[:limit]

            result = {
                "success": True,
                "etfs": etf_results_limited,
                "count": len(etf_results_limited),
                "total_matching": len(etf_results),
                "filters_applied": filters,
                "technical_filters_applied": technical_filters or {},
                "region": region,
                "timestamp": datetime.now().isoformat(),
                "limitations": self._get_limitations(),
            }

            # Update cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info("screening_etfs_complete",
                       count=len(etf_results_limited),
                       total_matching=len(etf_results))

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error("screening_etfs_error", error=str(e), exc_info=True)
            raise DatabaseError(
                f"Failed to screen ETFs: {str(e)}",
                {"filters": filters, "region": region}
            )

    async def _fetch_indicators_legacy(
        self,
        etf_tickers: List[str],
        region: str,
        technical_filters: Optional[Dict[str, Any]]
    ) -> tuple:
        """
        Legacy fallback: Python 기반 기술적 지표 계산.

        TechScreeningAdapter 사용이 실패할 경우 폴백으로 사용.

        Returns:
            (indicators dict, passing_tickers set)
        """
        import pandas as pd

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")

        logger.info(f"fetching_ohlcv_legacy: {len(etf_tickers)} ETFs, {start_date} to {end_date}")

        ohlcv_data = await self.data_adapter.get_ohlcv(
            tickers=etf_tickers,
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe="1d"
        )

        ticker_dfs = {}
        for ticker, records in ohlcv_data.items():
            if records:
                df = pd.DataFrame(records)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                ticker_dfs[ticker] = df

        # Calculate technical indicators
        raw_indicators = self.technical_calculator.batch_calculate(ticker_dfs)

        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(ticker_dfs)

        # Convert to flat format and apply filters
        indicators = {}
        passing_tickers = set(etf_tickers)

        for ticker, ind_data in raw_indicators.items():
            passes_all = True

            # Apply RSI filter
            if technical_filters and ("rsi_min" in technical_filters or "rsi_max" in technical_filters):
                rsi_val = ind_data.get("rsi", {}).get("rsi")
                if rsi_val is None:
                    passes_all = False
                else:
                    if "rsi_min" in technical_filters and rsi_val < technical_filters["rsi_min"]:
                        passes_all = False
                    if "rsi_max" in technical_filters and rsi_val > technical_filters["rsi_max"]:
                        passes_all = False

            # Apply MA trend filter
            if passes_all and technical_filters and "ma_trend" in technical_filters:
                trend = ind_data.get("moving_averages", {}).get("trend")
                if trend != technical_filters["ma_trend"]:
                    passes_all = False

            if passes_all:
                # Convert to flat structure
                perf = performance_metrics.get(ticker, {})
                indicators[ticker] = {
                    "rsi": ind_data.get("rsi", {}).get("rsi"),
                    "trend": ind_data.get("moving_averages", {}).get("trend"),
                    "price": ind_data.get("moving_averages", {}).get("price"),
                    "price_vs_ma20": ind_data.get("moving_averages", {}).get("price_vs_ma20"),
                    "ma20": ind_data.get("moving_averages", {}).get("ma20"),
                    "ma50": ind_data.get("moving_averages", {}).get("ma50"),
                    "ma200": ind_data.get("moving_averages", {}).get("ma200"),
                    "ma_crossover": ind_data.get("moving_averages", {}).get("ma_crossover"),
                    "price_change_1m": perf.get("price_change_1m"),
                    "avg_volume_20d": perf.get("volume_avg_20d"),
                }

        passing_tickers = set(indicators.keys())
        logger.info(f"legacy_indicators_complete: {len(indicators)} ETFs pass")

        return indicators, passing_tickers

    def _calculate_performance_metrics(self, ticker_dfs: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """
        Calculate performance metrics from OHLCV data.

        Metrics:
        - price_change_1m: 1-month price change percentage
        - volume_avg_20d: 20-day average volume

        Args:
            ticker_dfs: Dictionary of ticker -> DataFrame

        Returns:
            Dictionary of ticker -> metrics dict
        """
        metrics = {}

        for ticker, df in ticker_dfs.items():
            if df.empty or 'close' not in df.columns:
                continue

            ticker_metrics = {}

            # 1-month price change (≈20 trading days)
            if len(df) >= 20:
                current_price = df['close'].iloc[-1]
                price_1m_ago = df['close'].iloc[-20]
                price_change_1m = ((current_price - price_1m_ago) / price_1m_ago) * 100
                ticker_metrics["price_change_1m"] = round(price_change_1m, 2)

            # 20-day average volume
            if 'volume' in df.columns and len(df) >= 20:
                volume_avg_20d = df['volume'].iloc[-20:].mean()
                ticker_metrics["volume_avg_20d"] = int(volume_avg_20d)

            metrics[ticker] = ticker_metrics

        return metrics

    def _parse_sector_from_name(self, name: str) -> str:
        """
        Parse sector/theme from ETF name using keyword matching.

        This is a workaround for missing sector data from ETF sources.

        Args:
            name: ETF name (e.g., "KODEX 반도체", "TIGER 2차전지")

        Returns:
            Sector/theme string or "General" if no match
        """
        name_lower = name.lower()

        for keyword, sector in self.SECTOR_KEYWORDS.items():
            if keyword.lower() in name_lower:
                return sector

        # Check for index-tracking ETFs
        if any(idx in name for idx in ["200", "코스피", "KOSPI", "코스닥", "KOSDAQ"]):
            return "Broad Market"

        # Check for leveraged/inverse ETFs
        if any(lev in name for lev in ["레버리지", "인버스", "2X", "3X"]):
            return "Leveraged/Inverse"

        return "General"

    def _get_limitations(self) -> List[str]:
        """
        Get list of known data limitations.

        Returns:
            List of limitation strings
        """
        return [
            "AUM (Assets Under Management) data not readily available",
            "TER (Total Expense Ratio) data requires complex web scraping",
            "Tracking Error data has limited availability",
            "Sector/Theme approximated from ETF name parsing",
            "Use average volume as proxy for ETF size/liquidity"
        ]

    def _validate_filters(self, filters: Dict[str, Any]) -> None:
        """
        Validate filter parameters.

        Args:
            filters: Filter dictionary

        Raises:
            ValidationError: Invalid filter parameters
        """
        valid_filters = {
            "name_pattern",
            "listing_date_after",
            "listing_date_before"
        }

        for key in filters:
            if key not in valid_filters:
                raise ValidationError(
                    f"Invalid filter: {key}",
                    {"valid_filters": list(valid_filters)}
                )

        # Validate date formats
        for date_field in ["listing_date_after", "listing_date_before"]:
            if date_field in filters:
                try:
                    datetime.strptime(filters[date_field], "%Y-%m-%d")
                except ValueError:
                    raise ValidationError(
                        f"{date_field} must be in YYYY-MM-DD format",
                        {date_field: filters[date_field]}
                    )

    def _validate_technical_filters(self, technical_filters: Dict[str, Any]) -> None:
        """
        Validate technical filter parameters.

        Args:
            technical_filters: Technical filter dictionary

        Raises:
            ValidationError: Invalid technical filter parameters
        """
        valid_filters = {
            "rsi_min",
            "rsi_max",
            "ma_trend",
            "price_change_1m_min",
            "price_change_1m_max",
            "volume_avg_20d_min"
        }

        for key in technical_filters:
            if key not in valid_filters:
                raise ValidationError(
                    f"Invalid technical filter: {key}",
                    {"valid_technical_filters": list(valid_filters)}
                )

        # Validate RSI range
        if "rsi_min" in technical_filters:
            rsi_min = float(technical_filters["rsi_min"])
            if rsi_min < 0 or rsi_min > 100:
                raise ValidationError(
                    f"rsi_min must be between 0 and 100, got {rsi_min}",
                    {"rsi_min": rsi_min}
                )

        if "rsi_max" in technical_filters:
            rsi_max = float(technical_filters["rsi_max"])
            if rsi_max < 0 or rsi_max > 100:
                raise ValidationError(
                    f"rsi_max must be between 0 and 100, got {rsi_max}",
                    {"rsi_max": rsi_max}
                )

        # Validate MA trend
        if "ma_trend" in technical_filters:
            valid_trends = {"bullish", "bearish", "neutral"}
            trend = technical_filters["ma_trend"]
            if trend not in valid_trends:
                raise ValidationError(
                    f"ma_trend must be one of {valid_trends}, got {trend}",
                    {"ma_trend": trend}
                )

        # Validate price change range
        if "price_change_1m_min" in technical_filters:
            price_min = float(technical_filters["price_change_1m_min"])
            if price_min < -100 or price_min > 1000:
                raise ValidationError(
                    f"price_change_1m_min must be between -100 and 1000, got {price_min}",
                    {"price_change_1m_min": price_min}
                )

        if "price_change_1m_max" in technical_filters:
            price_max = float(technical_filters["price_change_1m_max"])
            if price_max < -100 or price_max > 1000:
                raise ValidationError(
                    f"price_change_1m_max must be between -100 and 1000, got {price_max}",
                    {"price_change_1m_max": price_max}
                )

        # Validate volume
        if "volume_avg_20d_min" in technical_filters:
            volume_min = int(technical_filters["volume_avg_20d_min"])
            if volume_min < 0:
                raise ValidationError(
                    f"volume_avg_20d_min must be >= 0, got {volume_min}",
                    {"volume_avg_20d_min": volume_min}
                )

    def _validate_region(self, region: str) -> None:
        """
        Validate region parameter.

        Args:
            region: Market region code

        Raises:
            ValidationError: Invalid region
        """
        valid_regions = {"KR", "US", "HK", "JP", "CN", "VN"}
        if region not in valid_regions:
            raise ValidationError(
                f"Invalid region: {region}",
                {"valid_regions": list(valid_regions)}
            )

    def _validate_limit(self, limit: int) -> None:
        """
        Validate limit parameter.

        Args:
            limit: Result limit

        Raises:
            ValidationError: Invalid limit
        """
        if limit < 1 or limit > 200:
            raise ValidationError(
                f"limit must be between 1 and 200, got {limit}",
                {"limit": limit}
            )

    def _make_cache_key(self, filters: Dict[str, Any], region: str, limit: int,
                        technical_filters: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate cache key from screening parameters.

        Args:
            filters: Basic filter dictionary
            region: Market region
            limit: Result limit
            technical_filters: Technical filter dictionary (optional)

        Returns:
            Cache key string
        """
        # Sort filters for consistent key generation
        filter_str = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))

        # Add technical filters to cache key if provided
        if technical_filters:
            tech_str = "|".join(f"{k}={v}" for k, v in sorted(technical_filters.items()))
            return f"screen_etf:{region}:{filter_str}:tech:{tech_str}:{limit}"

        return f"screen_etf:{region}:{filter_str}:{limit}"

    def _is_cache_valid(self, key: str) -> bool:
        """
        Check if cached result is still valid.

        Args:
            key: Cache key

        Returns:
            True if cache is valid
        """
        if key not in self._cache or key not in self._cache_time:
            return False

        age = (datetime.now() - self._cache_time[key]).total_seconds()
        return age < self._cache_ttl
