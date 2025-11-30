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
        Calculate technical indicators using DB-level computation (10x faster).

        **개선됨 (v2.0)**: TechScreeningAdapter를 사용하여 PostgreSQL Window Functions로
        DB 레벨에서 직접 계산. 기존 Python 기반 계산 대비 10x 성능 향상.

        Args:
            tickers: List of ticker symbols
            region: Market region ("KR", "US", "JP", etc.)
            indicators: List of indicators to calculate ["rsi", "ma", "all"] (default: ["all"])
            period_days: (deprecated, ignored) 데이터 기간은 자동으로 400일 사용

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
                            "price_vs_ma200": "above",
                            "ma_crossover": "none",
                            "ma20_distance": 0.97,
                            "ma200_distance": 3.96
                        },
                        "volume": {
                            "volume_ratio": 1.25,
                            "volume_surge": false,
                            "avg_volume_20d": 15000000
                        },
                        "performance": {
                            "price_change_1m": 3.5
                        },
                        "timestamp": "2025-11-30T..."
                    },
                    ...
                },
                "count": N,
                "region": "KR",
                "execution_time_ms": 123.4
            }

        Raises:
            DataNotFoundError: No data available
            DatabaseError: Database query failed

        Performance:
            - 현재 (v2.0): ~1초 (100 tickers), DB 레벨 계산
            - 이전 (v1.0): ~10초 (100 tickers), Python 기반 계산
            - 캐시 히트: <1ms

        Example:
            >>> adapter = DataAdapter()
            >>> result = await adapter.get_technical_indicators(
            ...     tickers=["005930", "000660"],
            ...     region="KR"
            ... )
            >>> result["indicators"]["005930"]["rsi"]["signal"]
            "neutral"
        """
        from .tech_screening_adapter import TechScreeningAdapter

        if indicators is None:
            indicators = ["all"]

        logger.info(
            "get_technical_indicators_start_v2",
            tickers=tickers[:5],  # Log first 5 only
            ticker_count=len(tickers),
            region=region,
            indicators=indicators
        )

        # TechScreeningAdapter를 사용하여 DB 레벨에서 계산
        tech_adapter = TechScreeningAdapter(config=self.config)

        try:
            # DB 레벨 기술적 지표 조회
            tech_result = await tech_adapter.get_indicators_for_tickers(
                tickers=tickers,
                region=region
            )

            if not tech_result.get("success"):
                from ..utils.errors import DatabaseError
                raise DatabaseError(
                    "Technical indicator calculation failed",
                    {"region": region, "tickers": tickers[:5]}
                )

            # 결과를 기존 포맷으로 변환 (하위 호환성 유지)
            results = {}
            for ticker, data in tech_result.get("indicators", {}).items():
                # RSI 데이터 변환
                rsi_value = data.get("rsi")
                rsi_signal = "neutral"
                if rsi_value is not None:
                    if rsi_value < 30:
                        rsi_signal = "oversold"
                    elif rsi_value > 70:
                        rsi_signal = "overbought"

                indicator_result = {
                    "rsi": {
                        "rsi": rsi_value,
                        "signal": rsi_signal,
                        "period": 14,
                        "oversold_threshold": 30.0,
                        "overbought_threshold": 70.0
                    },
                    "moving_averages": {
                        "ma20": data.get("ma20"),
                        "ma50": data.get("ma50"),
                        "ma200": data.get("ma200"),
                        "trend": data.get("trend"),
                        "price": data.get("price"),
                        "price_vs_ma20": data.get("price_vs_ma20"),
                        "price_vs_ma200": data.get("price_vs_ma200"),
                        "ma_crossover": data.get("ma_crossover"),
                        "ma20_distance": data.get("ma20_distance"),
                        "ma200_distance": data.get("ma200_distance")
                    },
                    "volume": {
                        "volume_ratio": data.get("volume_ratio"),
                        "volume_surge": data.get("volume_surge"),
                        "avg_volume_20d": data.get("avg_volume_20d")
                    },
                    "performance": {
                        "price_change_1m": data.get("price_change_1m")
                    },
                    "name": data.get("name"),
                    "date": data.get("date"),
                    "timestamp": datetime.now().isoformat()
                }

                results[ticker] = indicator_result

            logger.info(
                "get_technical_indicators_complete_v2",
                count=len(results),
                total_tickers=len(tickers),
                execution_time_ms=tech_result.get("execution_time_ms", 0)
            )

            return {
                "success": True,
                "indicators": results,
                "count": len(results),
                "region": region,
                "execution_time_ms": tech_result.get("execution_time_ms", 0),
                "from_cache": tech_result.get("from_cache", False)
            }

        except Exception as e:
            logger.error(f"get_technical_indicators_v2_error: {e}")
            # Fallback: 에러 발생 시 기존 방식 사용 (레거시 호환)
            logger.warning("Falling back to legacy Python-based calculation")
            return await self._get_technical_indicators_legacy(
                tickers=tickers,
                region=region,
                indicators=indicators,
                period_days=period_days
            )

    async def _get_technical_indicators_legacy(
        self,
        tickers: List[str],
        region: str = "KR",
        indicators: List[str] = None,
        period_days: int = 400,
    ) -> Dict[str, any]:
        """
        Legacy fallback: Python 기반 기술적 지표 계산.

        TechScreeningAdapter 사용이 실패할 경우 폴백으로 사용.
        """
        from datetime import timedelta
        from modules.screening.technical_calculator import TechnicalCalculator
        import pandas as pd

        if indicators is None:
            indicators = ["all"]

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        logger.info(
            "get_technical_indicators_legacy_start",
            tickers=tickers,
            region=region,
            date_range=f"{start_date} to {end_date}"
        )

        ohlcv_data = await self.get_ohlcv(
            tickers=tickers,
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

        calculator = TechnicalCalculator()
        calc_rsi = "rsi" in indicators or "all" in indicators
        calc_ma = "ma" in indicators or "all" in indicators

        results = {}
        for ticker, df in ticker_dfs.items():
            try:
                indicator_result = {}

                if calc_rsi:
                    rsi_result = calculator.calculate_rsi(df)
                    if rsi_result:
                        indicator_result["rsi"] = rsi_result

                if calc_ma:
                    ma_result = calculator.calculate_moving_averages(df)
                    if ma_result:
                        indicator_result["moving_averages"] = ma_result

                if indicator_result:
                    indicator_result["timestamp"] = datetime.now().isoformat()
                    results[ticker] = indicator_result

            except Exception as e:
                logger.error(f"Legacy indicator calculation failed for {ticker}: {e}")
                continue

        return {
            "success": True,
            "indicators": results,
            "count": len(results),
            "region": region,
            "period_days": period_days,
            "legacy_mode": True
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

    async def get_fundamentals(
        self,
        tickers: List[str],
        fields: List[str],
        period_type: str = "ANNUAL",
        periods: int = 1,
        region: str = "KR",
    ) -> Dict[str, List[Dict]]:
        """
        Get fundamental financial data from ticker_fundamentals table.

        Args:
            tickers: List of ticker symbols
            fields: List of column names to retrieve (e.g., ['revenue', 'net_income'])
            period_type: ANNUAL, QUARTERLY, or DAILY
            periods: Number of periods to retrieve (most recent first)
            region: Market region code

        Returns:
            Dict mapping ticker to list of records:
            {
                "005930": [
                    {
                        "ticker": "005930",
                        "date": "2024-12-31",
                        "fiscal_year": 2024,
                        "period_type": "ANNUAL",
                        "revenue": 300000000000000,
                        "net_income": 35000000000000,
                        ...
                    },
                    ...
                ]
            }

        Raises:
            DataNotFoundError: No data available
            DatabaseError: Database query failed
        """
        import pandas as pd

        logger.info(
            "get_fundamentals_start",
            tickers=tickers,
            fields=fields[:5],  # Log first 5 fields only
            period_type=period_type,
            periods=periods,
            region=region
        )

        # Build field list (always include base fields)
        base_fields = ["ticker", "date", "fiscal_year", "period_type"]
        all_fields = list(set(base_fields + fields))
        field_str = ", ".join(all_fields)

        # Build query with pagination
        ticker_placeholders = ", ".join(["%s"] * len(tickers))

        query = f"""
            WITH ranked_data AS (
                SELECT {field_str},
                       ROW_NUMBER() OVER (
                           PARTITION BY ticker
                           ORDER BY date DESC
                       ) as rn
                FROM ticker_fundamentals
                WHERE ticker IN ({ticker_placeholders})
                  AND region = %s
                  AND period_type = %s
            )
            SELECT {field_str}
            FROM ranked_data
            WHERE rn <= %s
            ORDER BY ticker, date DESC
        """

        try:
            params = tuple(tickers) + (region, period_type, periods)
            rows = self.db_manager.execute_query(query, params)

        except Exception as e:
            logger.error("fundamentals_query_failed", error=str(e))
            raise DatabaseError(
                f"Failed to query fundamentals data: {e}",
                {"tickers": tickers, "region": region}
            )

        if not rows:
            raise DataNotFoundError(
                "No fundamental data available",
                {"tickers": tickers, "region": region, "period_type": period_type}
            )

        # Organize data by ticker
        results: Dict[str, List[Dict]] = {}

        for row in rows:
            ticker = row.get("ticker")
            if ticker not in results:
                results[ticker] = []

            # Convert row to dict with proper types
            record = {}
            for key, value in row.items():
                if key == "rn":  # Skip row number
                    continue
                if value is not None:
                    # Convert date to string
                    if hasattr(value, 'strftime'):
                        record[key] = value.strftime('%Y-%m-%d')
                    # Convert Decimal to float
                    elif hasattr(value, '__float__'):
                        record[key] = float(value)
                    else:
                        record[key] = value
                else:
                    record[key] = None

            results[ticker].append(record)

        logger.info(
            "get_fundamentals_complete",
            ticker_count=len(results),
            total_records=sum(len(r) for r in results.values())
        )

        return results

    async def get_dividend_history(
        self,
        tickers: List[str],
        region: str = "KR",
        years: int = 5,
    ) -> Dict[str, List[Dict]]:
        """
        Get dividend history from dividend_history table.

        Args:
            tickers: List of ticker symbols
            region: Market region code
            years: Number of years to retrieve

        Returns:
            Dict mapping ticker to list of dividend records:
            {
                "005930": [
                    {
                        "ticker": "005930",
                        "fiscal_year": 2024,
                        "dividend_type": "final",
                        "dividend_per_share": 1444.0,
                        "dividend_yield": 1.46,
                        "ex_dividend_date": "2025-03-27",
                        ...
                    },
                    ...
                ]
            }

        Raises:
            DatabaseError: Database query failed
        """
        from datetime import datetime

        logger.info(
            "get_dividend_history_start",
            tickers=tickers,
            region=region,
            years=years
        )

        # Calculate cutoff year
        current_year = datetime.now().year
        cutoff_year = current_year - years

        # Build query
        ticker_placeholders = ", ".join(["%s"] * len(tickers))

        query = f"""
            SELECT
                ticker, region, fiscal_year, dividend_type,
                dividend_per_share, dividend_yield,
                declaration_date, ex_dividend_date, record_date, payment_date,
                currency, total_dividend_amount, payout_ratio, data_source
            FROM dividend_history
            WHERE ticker IN ({ticker_placeholders})
              AND region = %s
              AND fiscal_year >= %s
            ORDER BY ticker, fiscal_year DESC, ex_dividend_date DESC NULLS LAST
        """

        try:
            params = tuple(tickers) + (region, cutoff_year)
            rows = self.db_manager.execute_query(query, params)

        except Exception as e:
            logger.error("dividend_history_query_failed", error=str(e))
            raise DatabaseError(
                f"Failed to query dividend history: {e}",
                {"tickers": tickers, "region": region}
            )

        # Organize data by ticker
        results: Dict[str, List[Dict]] = {ticker: [] for ticker in tickers}

        if rows:
            for row in rows:
                ticker = row.get("ticker")
                if ticker in results:
                    # Convert row to dict with proper types
                    record = {}
                    for key, value in row.items():
                        if value is not None:
                            # Convert date to string
                            if hasattr(value, 'strftime'):
                                record[key] = value.strftime('%Y-%m-%d')
                            # Convert date object to date
                            elif hasattr(value, 'isoformat') and not hasattr(value, 'strftime'):
                                record[key] = str(value)
                            # Convert Decimal to float
                            elif hasattr(value, '__float__'):
                                record[key] = float(value)
                            else:
                                record[key] = value
                        else:
                            record[key] = None

                    results[ticker].append(record)

        logger.info(
            "get_dividend_history_complete",
            ticker_count=len([t for t in results if results[t]]),
            total_records=sum(len(r) for r in results.values())
        )

        return results

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

    async def get_ttm_data(
        self,
        tickers: List[str],
        fields: List[str],
        region: str = "KR",
        as_of_date: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        """
        Get TTM (Trailing Twelve Months) financial data from ticker_fundamentals_ttm table.

        Args:
            tickers: List of ticker symbols
            fields: List of column names to retrieve (e.g., ['revenue_ttm', 'net_income_ttm'])
            region: Market region code (KR, US, JP, HK, CN, VN)
            as_of_date: TTM calculation date (YYYY-MM-DD). If None, returns most recent.

        Returns:
            Dict mapping ticker to list of TTM records:
            {
                "005930": [
                    {
                        "ticker": "005930",
                        "as_of_date": "2024-09-30",
                        "revenue_ttm": 300000000000000,
                        "net_income_ttm": 35000000000000,
                        "roe_ttm": 0.12,
                        ...
                    }
                ]
            }

        Raises:
            DataNotFoundError: No TTM data available
            DatabaseError: Database query failed
        """
        logger.info(
            "get_ttm_data_start",
            tickers=tickers,
            fields=fields[:5],  # Log first 5 fields only
            region=region,
            as_of_date=as_of_date
        )

        # Build field list (always include base fields)
        base_fields = ["ticker", "region", "as_of_date"]
        all_fields = list(set(base_fields + fields))
        # Prefix with table alias to avoid ambiguity in JOIN
        field_str = ", ".join([f"t.{f}" for f in all_fields])

        # Build query
        ticker_placeholders = ", ".join(["%s"] * len(tickers))

        if as_of_date:
            # Get TTM data for specific date
            query = f"""
                SELECT {field_str}
                FROM ticker_fundamentals_ttm t
                WHERE t.ticker IN ({ticker_placeholders})
                  AND t.region = %s
                  AND t.as_of_date = %s
                ORDER BY t.ticker
            """
            params = tuple(tickers) + (region, as_of_date)
        else:
            # Get most recent TTM data for each ticker
            query = f"""
                WITH latest_ttm AS (
                    SELECT ticker, MAX(as_of_date) as max_date
                    FROM ticker_fundamentals_ttm
                    WHERE ticker IN ({ticker_placeholders})
                      AND region = %s
                    GROUP BY ticker
                )
                SELECT {field_str}
                FROM ticker_fundamentals_ttm t
                JOIN latest_ttm lt ON t.ticker = lt.ticker AND t.as_of_date = lt.max_date
                WHERE t.region = %s
                ORDER BY t.ticker
            """
            params = tuple(tickers) + (region, region)

        try:
            rows = self.db_manager.execute_query(query, params)

        except Exception as e:
            logger.error("ttm_data_query_failed", error=str(e))
            raise DatabaseError(
                f"Failed to query TTM data: {e}",
                {"tickers": tickers, "region": region}
            )

        if not rows:
            raise DataNotFoundError(
                "No TTM data available",
                {"tickers": tickers, "region": region, "as_of_date": as_of_date}
            )

        # Organize data by ticker
        results: Dict[str, List[Dict]] = {}

        for row in rows:
            ticker = row.get("ticker")
            if ticker not in results:
                results[ticker] = []

            # Convert row to dict with proper types
            record = {}
            for key, value in row.items():
                if value is not None:
                    # Convert date to string
                    if hasattr(value, 'strftime'):
                        record[key] = value.strftime('%Y-%m-%d')
                    elif hasattr(value, 'isoformat') and not hasattr(value, 'strftime'):
                        record[key] = str(value)
                    # Convert Decimal to float
                    elif hasattr(value, '__float__'):
                        record[key] = float(value)
                    else:
                        record[key] = value
                else:
                    record[key] = None

            results[ticker].append(record)

        logger.info(
            "get_ttm_data_complete",
            ticker_count=len(results),
            total_records=sum(len(r) for r in results.values())
        )

        return results
