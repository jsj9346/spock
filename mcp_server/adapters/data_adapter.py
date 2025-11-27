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

    async def get_cagr_data(
        self,
        tickers: List[str],
        metrics: List[str],
        years: int = 3,
        region: str = "KR",
        period_type: str = "ANNUAL",
    ) -> Dict[str, any]:
        """
        Get fundamental data and calculate CAGR for specified metrics.

        Args:
            tickers: List of ticker symbols
            metrics: List of metric column names from ticker_fundamentals
            years: Number of years for CAGR calculation
            region: Market region
            period_type: Data period type (ANNUAL, QUARTERLY, DAILY)

        Returns:
            Dict with CAGR results per ticker:
            {
                "005930": {
                    "cagr": {"revenue": 0.12, "net_income": 0.08, ...},
                    "period": {"start_date": "2021-12-31", "end_date": "2024-12-31"},
                    "data_quality": {"records_found": 4, "years_covered": 3}
                },
                ...
            }

        Raises:
            DataNotFoundError: No fundamental data available
            DatabaseError: Database query failed
        """
        from dateutil.relativedelta import relativedelta

        logger.info(
            "get_cagr_data_start",
            tickers=tickers,
            metrics=metrics,
            years=years,
            region=region,
            period_type=period_type
        )

        # Build SQL query for fundamental data
        metric_columns = ", ".join(metrics)
        ticker_placeholders = ", ".join(["%s"] * len(tickers))

        # Query to get historical fundamental data ordered by date
        query = f"""
            SELECT ticker, date, fiscal_year, period_type, {metric_columns}
            FROM ticker_fundamentals
            WHERE ticker IN ({ticker_placeholders})
              AND region = %s
              AND period_type = %s
            ORDER BY ticker, date DESC
        """

        try:
            params = tuple(tickers) + (region, period_type)
            rows = self.db_manager.execute_query(query, params)

            if rows:
                # Get column names from first row keys
                columns = list(rows[0].keys())
            else:
                columns = []

        except Exception as e:
            logger.error("cagr_query_failed", error=str(e))
            raise DatabaseError(
                f"Failed to query fundamental data: {e}",
                {"tickers": tickers, "region": region}
            )

        if not rows:
            raise DataNotFoundError(
                "No fundamental data available",
                {"tickers": tickers, "region": region, "period_type": period_type}
            )

        # Organize data by ticker
        import pandas as pd
        df = pd.DataFrame(rows, columns=columns)

        results = {}
        for ticker in tickers:
            ticker_df = df[df['ticker'] == ticker].copy()

            if ticker_df.empty:
                results[ticker] = {
                    "cagr": {m: None for m in metrics},
                    "period": {"start_date": None, "end_date": None},
                    "data_quality": {"records_found": 0, "years_covered": 0, "status": "no_data"}
                }
                continue

            # Sort by date descending to get most recent first
            ticker_df = ticker_df.sort_values('date', ascending=False)

            # Get end (most recent) and start (oldest within range) data points
            end_row = ticker_df.iloc[0]
            end_date = end_row['date']

            # Calculate target start date
            if period_type == "ANNUAL":
                target_start_date = end_date - relativedelta(years=years)
            elif period_type == "QUARTERLY":
                target_start_date = end_date - relativedelta(months=years * 12)
            else:  # DAILY
                target_start_date = end_date - relativedelta(years=years)

            # Find the closest data point to target start date
            older_data = ticker_df[ticker_df['date'] <= target_start_date]
            if older_data.empty:
                # Use oldest available data
                start_row = ticker_df.iloc[-1]
            else:
                start_row = older_data.iloc[0]

            start_date = start_row['date']

            # Calculate actual years between data points
            actual_years = (end_date - start_date).days / 365.25

            if actual_years < 0.5:  # Less than 6 months of data
                results[ticker] = {
                    "cagr": {m: None for m in metrics},
                    "period": {
                        "start_date": str(start_date),
                        "end_date": str(end_date)
                    },
                    "data_quality": {
                        "records_found": len(ticker_df),
                        "years_covered": round(actual_years, 2),
                        "status": "insufficient_history"
                    }
                }
                continue

            # Calculate CAGR for each metric
            cagr_results = {}
            for metric in metrics:
                start_value = start_row.get(metric)
                end_value = end_row.get(metric)

                # Convert to float if not None
                if start_value is not None:
                    start_value = float(start_value)
                if end_value is not None:
                    end_value = float(end_value)

                # Calculate CAGR
                cagr = self._calculate_cagr(start_value, end_value, actual_years)
                cagr_results[metric] = cagr

            results[ticker] = {
                "cagr": cagr_results,
                "period": {
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "start_fiscal_year": int(start_row.get('fiscal_year')) if start_row.get('fiscal_year') else None,
                    "end_fiscal_year": int(end_row.get('fiscal_year')) if end_row.get('fiscal_year') else None
                },
                "data_quality": {
                    "records_found": len(ticker_df),
                    "years_covered": round(actual_years, 2),
                    "status": "ok"
                },
                "raw_values": {
                    metric: {
                        "start": float(start_row.get(metric)) if start_row.get(metric) is not None else None,
                        "end": float(end_row.get(metric)) if end_row.get(metric) is not None else None
                    }
                    for metric in metrics
                }
            }

        logger.info(
            "get_cagr_data_complete",
            ticker_count=len(results),
            successful=sum(1 for r in results.values() if r["data_quality"]["status"] == "ok")
        )

        return results

    def _calculate_cagr(
        self,
        beginning_value: Optional[float],
        ending_value: Optional[float],
        years: float
    ) -> Optional[float]:
        """
        Calculate CAGR (Compound Annual Growth Rate).

        Formula: CAGR = (Ending Value / Beginning Value)^(1/years) - 1

        Args:
            beginning_value: Starting value
            ending_value: Ending value
            years: Number of years between values

        Returns:
            CAGR as decimal (e.g., 0.15 for 15%), or None if calculation not possible
        """
        if beginning_value is None or ending_value is None:
            return None
        if beginning_value <= 0 or years <= 0:
            return None

        try:
            # Handle negative ending value (e.g., loss after profit)
            if ending_value <= 0 and beginning_value > 0:
                return None  # Cannot calculate meaningful CAGR

            cagr = (ending_value / beginning_value) ** (1 / years) - 1
            return round(cagr, 4)  # Round to 4 decimal places
        except (ZeroDivisionError, ValueError, OverflowError):
            return None

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
