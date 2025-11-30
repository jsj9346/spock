# mcp_server/adapters/screening_adapter.py
"""
ScreeningAdapter - MCP adapter for stock screening and filtering.

Provides fundamental and technical screening capabilities by leveraging
existing PostgresDatabaseManager methods with MCP-optimized caching.

Architecture Pattern (Direct Database Queries):
    MCP Tool -> ScreeningAdapter -> PostgresDatabaseManager -> PostgreSQL

This adapter:
    - Screens stocks by fundamental criteria (P/E, P/B, dividend yield)
    - Combines multiple filters with set intersection logic
    - Provides MCP-specific caching and response formatting
    - Will support technical indicators in Phase 2

Performance:
    - screen_stocks: <1s for 100 tickers, <3s for full KR market
    - Cache TTL: 60 seconds (updated on market close)

Author: Spock MCP Server
Date: 2025-10-31
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from mcp_server.config import Config
from mcp_server.utils.errors import (
    DatabaseError,
    ValidationError,
    SpockMCPError,
)
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.screening.technical_calculator import TechnicalCalculator
from modules.screening.composite_scorer import CompositeScorer
from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.adapters.tech_screening_adapter import TechScreeningAdapter


class ScreeningAdapter:
    """
    MCP adapter for stock screening.

    Leverages existing PostgresDatabaseManager screening methods
    with MCP-optimized caching and response formatting.

    Example:
        >>> adapter = ScreeningAdapter()
        >>> result = await adapter.screen_stocks(
        ...     filters={"per_max": 15, "pbr_max": 2, "dividend_yield_min": 3.0},
        ...     region="KR",
        ...     limit=50
        ... )
        >>> len(result["stocks"])
        23
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize ScreeningAdapter.

        Args:
            config: Optional MCP config (default: load from env)
        """
        self.config = config or Config.from_env()

        # Initialize database manager with small pool (MCP server doesn't need large pool)
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        # Initialize technical calculator (Phase 2 - Legacy, kept for backward compatibility)
        self.technical_calculator = TechnicalCalculator()

        # Initialize data adapter for OHLCV fetching (Phase 2)
        self.data_adapter = DataAdapter(config=self.config)

        # Initialize TechScreeningAdapter for DB-level technical filtering (Phase 2.1 - Optimized)
        self.tech_screening_adapter = TechScreeningAdapter(config=self.config)

        # Initialize composite scorer (Phase 3)
        self.composite_scorer = CompositeScorer(
            fundamental_weight=0.6,
            technical_weight=0.4
        )

        # Cache for screening results (60 second TTL)
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 60  # seconds

        logger.info("screening_adapter_initialized")

    async def screen_stocks(
        self,
        filters: Dict[str, Any],
        technical_filters: Optional[Dict[str, Any]] = None,
        region: str = "KR",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Screen stocks by fundamental and technical criteria.

        Combines multiple filters using set intersection:
        1. Apply fundamental filters using PostgresDatabaseManager methods
        2. Find tickers that pass ALL fundamental filters (intersection)
        3. Apply technical filters (RSI, MA trend) if provided (Phase 2)
        4. Sort by composite score (Phase 3)
        5. Return top N results

        Args:
            filters: Dictionary of fundamental screening criteria:
                - per_max: Maximum P/E ratio (e.g., 15.0)
                - pbr_max: Maximum P/B ratio (e.g., 2.0)
                - dividend_yield_min: Minimum dividend yield % (e.g., 3.0)
                - market_cap_min: Minimum market cap (optional, Phase 3)
            technical_filters: Dictionary of technical criteria (Phase 2):
                - rsi_min: Minimum RSI (e.g., 0 for any)
                - rsi_max: Maximum RSI (e.g., 30 for oversold)
                - ma_trend: Required MA trend ("bullish", "bearish", "neutral")
            region: Market region (KR, US)
            limit: Maximum number of results (default: 50, max: 200)

        Returns:
            Dictionary with screening results:
            {
                "success": true,
                "stocks": [
                    {
                        "ticker": "005930",
                        "name": "Samsung Electronics",
                        "per": 12.5,
                        "pbr": 1.8,
                        "dividend_yield": 3.2,
                        "market_cap": 400000000000,
                        "date": "2025-10-28"
                    },
                    ...
                ],
                "count": 23,
                "filters_applied": {...},
                "region": "KR"
            }

        Raises:
            ValidationError: Invalid filter parameters
            DatabaseError: Database query failure
        """
        try:
            # Validate inputs
            self._validate_filters(filters)
            self._validate_region(region)
            self._validate_limit(limit)

            # Check cache
            cache_key = self._make_cache_key(filters, region, limit, technical_filters)
            if self._is_cache_valid(cache_key):
                logger.debug("cache_hit", key=cache_key)
                return self._cache[cache_key]

            logger.info("screening_stocks_start",
                       filters=filters,
                       region=region,
                       limit=limit)

            # Apply filters using PostgresDatabaseManager methods
            ticker_sets = []

            # Filter 1: P/E ratio
            if "per_max" in filters:
                per_max = float(filters["per_max"])
                per_stocks = self.db_manager.get_stocks_by_per(
                    max_per=per_max,
                    region=region,
                    min_market_cap=filters.get("market_cap_min")
                )
                per_tickers = {s["ticker"] for s in per_stocks}
                ticker_sets.append(per_tickers)
                logger.debug(f"per_filter: {len(per_tickers)} stocks with P/E <= {per_max}")

            # Filter 2: P/B ratio
            if "pbr_max" in filters:
                pbr_max = float(filters["pbr_max"])
                pbr_stocks = self.db_manager.get_stocks_by_pbr(
                    max_pbr=pbr_max,
                    region=region
                )
                pbr_tickers = {s["ticker"] for s in pbr_stocks}
                ticker_sets.append(pbr_tickers)
                logger.debug(f"pbr_filter: {len(pbr_tickers)} stocks with P/B <= {pbr_max}")

            # Filter 3: Dividend yield
            if "dividend_yield_min" in filters:
                div_min = float(filters["dividend_yield_min"])
                div_stocks = self.db_manager.get_dividend_stocks(
                    min_yield=div_min,
                    region=region
                )
                div_tickers = {s["ticker"] for s in div_stocks}
                ticker_sets.append(div_tickers)
                logger.debug(f"dividend_filter: {len(div_tickers)} stocks with yield >= {div_min}%")

            # Find intersection of all filters
            if not ticker_sets:
                raise ValidationError(
                    "At least one filter must be specified",
                    {"filters": filters}
                )

            passing_tickers = ticker_sets[0]
            for ticker_set in ticker_sets[1:]:
                passing_tickers = passing_tickers.intersection(ticker_set)

            logger.info(f"fundamental_filter_intersection: {len(passing_tickers)} stocks pass all fundamental filters")

            # Phase 2.1: Apply technical filters using TechScreeningAdapter (DB-level, 5x faster)
            # 개선됨: Python 기반 계산 → PostgreSQL Window Functions
            indicators = {}  # Store indicators for later use
            if technical_filters and passing_tickers:
                logger.info("applying_technical_filters_v2", filters=technical_filters)

                try:
                    # DB 레벨에서 기술적 지표 조회 및 필터링
                    tech_result = await self.tech_screening_adapter.get_indicators_for_tickers(
                        tickers=list(passing_tickers),
                        region=region,
                        filters=technical_filters  # 필터 적용
                    )

                    if tech_result.get("success"):
                        # 필터를 통과한 ticker만 유지
                        tech_indicators = tech_result.get("indicators", {})
                        tech_passing = set(tech_indicators.keys())
                        passing_tickers = passing_tickers.intersection(tech_passing)

                        # indicators 저장 (나중에 결과에 추가할 때 사용)
                        indicators = tech_indicators

                        logger.info(
                            f"technical_filter_v2_complete: {len(passing_tickers)} stocks pass",
                            execution_time_ms=tech_result.get("execution_time_ms", 0)
                        )
                    else:
                        logger.warning("technical_filter_v2_failed, proceeding without technical filters")

                except Exception as e:
                    logger.error(f"technical_filter_v2_error: {e}")
                    # Fallback: 에러 발생 시 레거시 방식 시도
                    logger.warning("Falling back to legacy technical filtering")
                    try:
                        indicators = await self._apply_legacy_technical_filters(
                            passing_tickers, technical_filters, region
                        )
                        # Legacy 방식에서 통과한 ticker만 유지
                        passing_tickers = passing_tickers.intersection(set(indicators.keys()))
                    except Exception as legacy_error:
                        logger.error(f"legacy_technical_filter_error: {legacy_error}")
                        logger.warning("Proceeding with fundamental filters only")

            # Fetch full details for passing tickers
            stocks = []
            for ticker in passing_tickers:
                # Get latest fundamentals
                fund = self.db_manager.get_latest_fundamentals(
                    ticker=ticker,
                    region=region,
                    period_type="DAILY"
                )

                # Get ticker info
                ticker_info = self.db_manager.get_ticker(ticker, region)

                if fund and ticker_info:
                    stock_data = {
                        "ticker": ticker,
                        "name": ticker_info.get("name"),
                        "per": float(fund.get("per")) if fund.get("per") else None,
                        "pbr": float(fund.get("pbr")) if fund.get("pbr") else None,
                        "dividend_yield": float(fund.get("dividend_yield")) if fund.get("dividend_yield") else None,
                        "market_cap": int(fund.get("market_cap")) if fund.get("market_cap") else None,
                        "date": fund.get("date").isoformat() if fund.get("date") else None,
                    }

                    # Add technical indicator data if available (Phase 2.1 - Optimized format)
                    if technical_filters and ticker in indicators:
                        tech_data = indicators[ticker]
                        # TechScreeningAdapter 포맷 (flat structure)
                        stock_data["rsi"] = tech_data.get("rsi")
                        if tech_data.get("rsi") is not None:
                            rsi_val = tech_data.get("rsi")
                            if rsi_val < 30:
                                stock_data["rsi_signal"] = "oversold"
                            elif rsi_val > 70:
                                stock_data["rsi_signal"] = "overbought"
                            else:
                                stock_data["rsi_signal"] = "neutral"

                        stock_data["ma_trend"] = tech_data.get("trend")
                        stock_data["price_vs_ma20"] = tech_data.get("price_vs_ma20")
                        stock_data["price_vs_ma200"] = tech_data.get("price_vs_ma200")
                        stock_data["ma20"] = tech_data.get("ma20")
                        stock_data["ma50"] = tech_data.get("ma50")
                        stock_data["ma200"] = tech_data.get("ma200")
                        stock_data["current_price"] = tech_data.get("price")
                        stock_data["ma_crossover"] = tech_data.get("ma_crossover")
                        stock_data["volume_surge"] = tech_data.get("volume_surge")
                        stock_data["volume_ratio"] = tech_data.get("volume_ratio")
                        stock_data["ma20_distance"] = tech_data.get("ma20_distance")
                        stock_data["price_change_1m"] = tech_data.get("price_change_1m")

                    stocks.append(stock_data)

            # Phase 3: Calculate composite scores and rank
            stocks_scored = self.composite_scorer.calculate_scores(
                stocks,
                use_zscore=True
            )

            # Sort by composite score (already sorted by calculate_scores)
            stocks_sorted = stocks_scored

            # Apply limit
            stocks_limited = stocks_sorted[:limit]

            result = {
                "success": True,
                "stocks": stocks_limited,
                "count": len(stocks_limited),
                "total_matching": len(stocks),
                "filters_applied": filters,
                "technical_filters_applied": technical_filters if technical_filters else {},
                "region": region,
                "timestamp": datetime.now().isoformat(),
            }

            # Update cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info("screening_stocks_complete",
                       count=len(stocks_limited),
                       total_matching=len(stocks))

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error("screening_stocks_error", error=str(e))
            raise DatabaseError(
                f"Failed to screen stocks: {str(e)}",
                {"filters": filters, "region": region}
            )

    def _validate_filters(self, filters: Dict[str, Any]) -> None:
        """
        Validate filter parameters.

        Args:
            filters: Filter dictionary

        Raises:
            ValidationError: Invalid filter parameters
        """
        valid_filters = {"per_max", "pbr_max", "dividend_yield_min", "market_cap_min"}

        for key in filters:
            if key not in valid_filters:
                raise ValidationError(
                    f"Invalid filter: {key}",
                    {"valid_filters": list(valid_filters)}
                )

        # Validate numeric ranges
        if "per_max" in filters:
            per = float(filters["per_max"])
            if per <= 0 or per > 1000:
                raise ValidationError(
                    f"per_max must be between 0 and 1000, got {per}",
                    {"per_max": per}
                )

        if "pbr_max" in filters:
            pbr = float(filters["pbr_max"])
            if pbr <= 0 or pbr > 100:
                raise ValidationError(
                    f"pbr_max must be between 0 and 100, got {pbr}",
                    {"pbr_max": pbr}
                )

        if "dividend_yield_min" in filters:
            div_yield = float(filters["dividend_yield_min"])
            if div_yield < 0 or div_yield > 50:
                raise ValidationError(
                    f"dividend_yield_min must be between 0 and 50, got {div_yield}",
                    {"dividend_yield_min": div_yield}
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
            filters: Fundamental filter dictionary
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
            return f"screen:{region}:{filter_str}:tech:{tech_str}:{limit}"

        return f"screen:{region}:{filter_str}:{limit}"

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

    async def _apply_legacy_technical_filters(
        self,
        passing_tickers: set,
        technical_filters: Dict[str, Any],
        region: str
    ) -> Dict[str, Dict]:
        """
        Legacy fallback: Python 기반 기술적 필터링.

        TechScreeningAdapter 사용이 실패할 경우 폴백으로 사용.

        Args:
            passing_tickers: 펀더멘털 필터를 통과한 ticker set
            technical_filters: 기술적 필터 조건
            region: 시장 코드

        Returns:
            indicators dict (ticker -> indicator data)
        """
        import pandas as pd

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")

        ohlcv_data = await self.data_adapter.get_ohlcv(
            tickers=list(passing_tickers),
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
        indicators = self.technical_calculator.batch_calculate(ticker_dfs)

        # Apply filters and build filtered indicators dict
        filtered_indicators = {}

        for ticker, ind_data in indicators.items():
            passes_all = True

            # RSI filter
            if "rsi_min" in technical_filters or "rsi_max" in technical_filters:
                rsi_val = ind_data.get("rsi", {}).get("rsi")
                if rsi_val is None:
                    passes_all = False
                else:
                    if "rsi_min" in technical_filters and rsi_val < technical_filters["rsi_min"]:
                        passes_all = False
                    if "rsi_max" in technical_filters and rsi_val > technical_filters["rsi_max"]:
                        passes_all = False

            # MA trend filter
            if passes_all and "ma_trend" in technical_filters:
                trend = ind_data.get("moving_averages", {}).get("trend")
                if trend != technical_filters["ma_trend"]:
                    passes_all = False

            if passes_all:
                # Convert to flat structure for compatibility
                filtered_indicators[ticker] = {
                    "rsi": ind_data.get("rsi", {}).get("rsi"),
                    "trend": ind_data.get("moving_averages", {}).get("trend"),
                    "price_vs_ma20": ind_data.get("moving_averages", {}).get("price_vs_ma20"),
                    "ma20": ind_data.get("moving_averages", {}).get("ma20"),
                    "ma50": ind_data.get("moving_averages", {}).get("ma50"),
                    "ma200": ind_data.get("moving_averages", {}).get("ma200"),
                    "price": ind_data.get("moving_averages", {}).get("price"),
                    "ma_crossover": ind_data.get("moving_averages", {}).get("ma_crossover"),
                }

        logger.info(f"legacy_technical_filter_complete: {len(filtered_indicators)} stocks pass")
        return filtered_indicators
