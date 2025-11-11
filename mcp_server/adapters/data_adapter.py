# mcp_server/adapters/data_adapter.py
"""
Data Adapter for MCP Server

Thin wrapper around PostgresDataProvider with MCP-optimized caching.
Reuses existing business logic from modules/backtesting/data_providers/.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import structlog

from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager
from ..utils.errors import DataNotFoundError, DatabaseError
from ..config import Config

logger = structlog.get_logger()


class DataAdapter:
    """
    MCP data adapter with caching layer.

    Wraps PostgresDataProvider for MCP-optimized OHLCV queries.
    Provides in-memory caching with LRU eviction (future enhancement).

    Performance Targets:
    - Cache hit: <100ms
    - Cache miss: <500ms (batch), <200ms (single ticker)
    - Cache hit rate: >80%
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize data adapter.

        Args:
            config: Optional MCP configuration. Defaults to Config.from_env().
        """
        self.config = config or Config.from_env()

        # Initialize PostgreSQL database manager with small pool (MCP server doesn't need large pool)
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        # Initialize data provider with caching enabled
        self.provider = PostgresDataProvider(
            db_manager=self.db_manager,
            cache_enabled=True,
            backfill_enabled=False  # Disable auto-backfill for MCP server
        )

        self._cache: Dict[str, Dict[str, List[Dict]]] = {}

        logger.info(
            "data_adapter_initialized",
            cache_max_size_mb=self.config.cache_max_size_mb,
            cache_ttl_seconds=self.config.cache_ttl_seconds,
        )
    
    async def get_ohlcv(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str = "KR",
        timeframe: str = "1d",
    ) -> Dict[str, List[Dict]]:
        """
        Get OHLCV data with MCP-optimized output format.
        
        Args:
            tickers: List of ticker symbols (e.g., ["005930", "000660"])
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            region: Market region ("KR" or "US")
            timeframe: Data timeframe (default: "1d")
        
        Returns:
            Dict mapping ticker to list of OHLCV records:
            {
                "005930": [
                    {"date": "2024-01-01", "open": 75000, "high": 76000, ...},
                    ...
                ],
                ...
            }
        
        Raises:
            DataNotFoundError: No data available for requested tickers/dates
            DatabaseError: Database connection or query failed
        
        Example:
            >>> adapter = DataAdapter()
            >>> data = await adapter.get_ohlcv(
            ...     tickers=["005930"],
            ...     start_date="2024-01-01",
            ...     end_date="2024-12-31",
            ...     region="KR"
            ... )
            >>> len(data["005930"])
            245  # ~245 trading days in 2024
        """
        # Check cache
        cache_key = self._make_cache_key(tickers, start_date, end_date, region, timeframe)
        if cache_key in self._cache:
            logger.debug("cache_hit", cache_key=cache_key)
            return self._cache[cache_key]
        
        # Convert dates
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise DataNotFoundError(
                f"Invalid date format: {e}",
                {"start_date": start_date, "end_date": end_date}
            )
        
        # Call PostgresDataProvider
        try:
            if len(tickers) == 1:
                # Single ticker optimization
                df = self.provider.get_ohlcv(
                    ticker=tickers[0],
                    region=region,
                    start_date=start_dt,
                    end_date=end_dt,
                    timeframe=timeframe,
                )
                # Convert DataFrame to list of dicts
                if not df.empty:
                    # Convert date columns to string for JSON serialization
                    df = df.copy()
                    if 'date' in df.columns:
                        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                    records = df.to_dict('records')
                    result = {tickers[0]: records}
                else:
                    result = {}
            else:
                # Batch query
                df_dict = self.provider.get_ohlcv_batch(
                    tickers=tickers,
                    region=region,
                    start_date=start_dt,
                    end_date=end_dt,
                    timeframe=timeframe,
                )
                # Convert DataFrames to list of dicts
                result = {}
                for ticker, df in df_dict.items():
                    if not df.empty:
                        # Convert date columns to string for JSON serialization
                        df = df.copy()
                        if 'date' in df.columns:
                            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                        result[ticker] = df.to_dict('records')
        except Exception as e:
            logger.error("database_query_failed", error=str(e), tickers=tickers)
            raise DatabaseError(
                f"Failed to query OHLCV data: {e}",
                {"tickers": tickers, "start_date": start_date, "end_date": end_date}
            )
        
        # Validate result
        if not result or all(len(records) == 0 for records in result.values()):
            logger.warning("no_data_found", tickers=tickers, start_date=start_date, end_date=end_date)
            raise DataNotFoundError(
                "No OHLCV data available for requested tickers/dates",
                {
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                    "region": region
                }
            )
        
        # Cache result
        self._cache[cache_key] = result
        logger.debug(
            "cache_miss",
            cache_key=cache_key,
            record_count=sum(len(records) for records in result.values())
        )
        
        return result
    
    async def get_technical_indicators(
        self,
        tickers: List[str],
        region: str = "KR",
        indicators: List[str] = None,
        period_days: int = 400,
    ) -> Dict[str, any]:
        """
        Calculate technical indicators without returning raw OHLCV data.

        Optimized for Claude Desktop to avoid context length issues.
        Returns only calculated indicators (RSI, MA trends) - 96% size reduction vs full OHLCV.

        Args:
            tickers: List of ticker symbols
            region: Market region ("KR" or "US")
            indicators: List of indicators to calculate ["rsi", "ma", "all"] (default: ["all"])
            period_days: Number of calendar days for data (default: 400, sufficient for MA200)

        Returns:
            {
                "success": True,
                "indicators": {
                    "005930": {
                        "rsi": {
                            "rsi": 45.2,
                            "signal": "neutral",
                            "period": 14,
                            "oversold_threshold": 30.0,
                            "overbought_threshold": 70.0
                        },
                        "moving_averages": {
                            "ma20": 52000.5,
                            "ma50": 51800.2,
                            "ma200": 50500.0,
                            "trend": "bullish",
                            "price": 52500.0,
                            "price_vs_ma20": "above",
                            "ma_crossover": "none"
                        },
                        "timestamp": "2025-10-31T..."
                    },
                    ...
                },
                "count": N,
                "region": "KR",
                "period_days": 400
            }

        Raises:
            DataNotFoundError: No data available
            DatabaseError: Database query failed

        Example:
            >>> adapter = DataAdapter()
            >>> result = await adapter.get_technical_indicators(
            ...     tickers=["005930", "000660"],
            ...     region="KR",
            ...     indicators=["all"],
            ...     period_days=400
            ... )
            >>> result["indicators"]["005930"]["rsi"]["signal"]
            "neutral"
        """
        from datetime import timedelta
        from modules.screening.technical_calculator import TechnicalCalculator
        import pandas as pd

        if indicators is None:
            indicators = ["all"]

        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        logger.info(
            "get_technical_indicators_start",
            tickers=tickers,
            region=region,
            indicators=indicators,
            period_days=period_days,
            date_range=f"{start_date} to {end_date}"
        )

        # Fetch OHLCV data (internal use only, not returned to client)
        ohlcv_data = await self.get_ohlcv(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe="1d"
        )

        # Convert to DataFrames for TechnicalCalculator
        ticker_dfs = {}
        for ticker, records in ohlcv_data.items():
            if records:
                df = pd.DataFrame(records)
                # Ensure 'date' is datetime
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                ticker_dfs[ticker] = df

        # Calculate indicators using TechnicalCalculator
        calculator = TechnicalCalculator()

        # Determine which indicators to calculate
        calc_rsi = "rsi" in indicators or "all" in indicators
        calc_ma = "ma" in indicators or "all" in indicators

        results = {}
        for ticker, df in ticker_dfs.items():
            try:
                indicator_result = {}

                # Calculate RSI if requested
                if calc_rsi:
                    rsi_result = calculator.calculate_rsi(df)
                    if rsi_result:
                        indicator_result["rsi"] = rsi_result

                # Calculate Moving Averages if requested
                if calc_ma:
                    ma_result = calculator.calculate_moving_averages(df)
                    if ma_result:
                        indicator_result["moving_averages"] = ma_result

                # Add timestamp if we have any indicators
                if indicator_result:
                    indicator_result["timestamp"] = datetime.now().isoformat()
                    results[ticker] = indicator_result
                    logger.debug(f"Indicators calculated for {ticker}")
                else:
                    logger.warning(f"No indicators calculated for {ticker}")

            except Exception as e:
                logger.error(f"Indicator calculation failed for {ticker}: {e}")
                continue

        logger.info(
            "get_technical_indicators_complete",
            count=len(results),
            total_tickers=len(tickers),
            success_rate=f"{len(results)}/{len(tickers)}"
        )

        return {
            "success": True,
            "indicators": results,
            "count": len(results),
            "region": region,
            "period_days": period_days
        }

    def _make_cache_key(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str,
        timeframe: str,
    ) -> str:
        """
        Generate cache key for OHLCV query.

        Args:
            tickers: Ticker list
            start_date: Start date
            end_date: End date
            region: Market region
            timeframe: Data timeframe

        Returns:
            Cache key string (deterministic)
        """
        ticker_str = ",".join(sorted(tickers))
        return f"{ticker_str}:{start_date}:{end_date}:{region}:{timeframe}"
