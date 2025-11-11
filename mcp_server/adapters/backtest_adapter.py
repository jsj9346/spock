# mcp_server/adapters/backtest_adapter.py
"""
BacktestAdapter - MCP adapter for backtesting functionality.

Thin wrapper around BacktestRunner and VectorbtAdapter, providing MCP-compatible
interface for strategy backtesting operations.

Architecture Pattern (Thin Wrapper):
    MCP Tool -> BacktestAdapter -> BacktestRunner/VectorbtAdapter

This adapter:
    - Wraps existing 500-line BacktestRunner
    - Wraps existing 384-line VectorbtAdapter
    - Converts MCP inputs to backtest config
    - Formats results for MCP response
    - Handles errors with MCP error types

Performance:
    - <1s for vectorbt 5-year backtest
    - <5s for custom engine backtest
    - In-memory caching for repeated configs

Author: Spock MCP Server
Date: 2025-10-30
"""

from typing import Dict, List, Optional, Any
from datetime import date, datetime
import traceback
import math
from loguru import logger

from mcp_server.config import Config
from mcp_server.utils.errors import (
    ValidationError,
    DataNotFoundError,
    DatabaseError,
    SpockMCPError,
)
from mcp_server.strategies import SignalGeneratorFactory
from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.backtest_engines.vectorbt_adapter import (
    VectorbtAdapter,
    VECTORBT_AVAILABLE,
)
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers.postgres_data_provider import (
    PostgresDataProvider,
)
from modules.db_manager_postgres import PostgresDatabaseManager


class BacktestAdapter:
    """
    MCP adapter for backtesting operations.

    Provides async interface for running backtests with either vectorbt or
    custom engine, with proper error handling and result formatting.

    Example:
        >>> adapter = BacktestAdapter()
        >>> result = await adapter.run_backtest(
        ...     strategy_type="momentum",
        ...     tickers=["005930"],
        ...     start_date="2023-01-01",
        ...     end_date="2023-12-31",
        ...     region="KR",
        ...     engine="vectorbt"
        ... )
    """

    @staticmethod
    def _to_json_serializable(value: Any) -> Any:
        """
        Convert numpy/pandas types to JSON-serializable Python types.

        Args:
            value: Value to convert (int64, float64, nan, inf, etc.)

        Returns:
            JSON-serializable Python type (int, float, None, str)
        """
        # Handle None
        if value is None:
            return None

        # Handle numpy/pandas integer types
        if hasattr(value, 'item'):
            # numpy scalar with .item() method
            value = value.item()

        # Handle nan and inf
        if isinstance(value, float):
            if math.isnan(value):
                return None
            elif math.isinf(value):
                return "inf" if value > 0 else "-inf"

        # Convert to native Python types
        if isinstance(value, (int, float, str, bool)):
            return value

        # Fallback: try to convert to float, then int
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return int(value)
            except (TypeError, ValueError):
                return str(value)

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize BacktestAdapter.

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

        # Initialize data provider
        self.data_provider = PostgresDataProvider(
            db_manager=self.db_manager,
            cache_enabled=True,
            backfill_enabled=False,  # MCP doesn't backfill
        )

        # Cache for backtest runners (config-specific)
        self._runner_cache: Dict[str, BacktestRunner] = {}

        logger.info("backtest_adapter_initialized",
                   vectorbt_available=VECTORBT_AVAILABLE)

    async def run_backtest(
        self,
        strategy_type: str,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str = "KR",
        engine: str = "vectorbt",
        initial_capital: float = 100_000_000,
        risk_profile: str = "moderate",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run backtest with specified strategy and parameters.

        Args:
            strategy_type: Strategy type (momentum, value, momentum_value)
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            region: Market region (KR, US, etc.)
            engine: Engine type (vectorbt, custom)
            initial_capital: Initial capital amount
            risk_profile: Risk profile (conservative, moderate, aggressive)
            parameters: Optional strategy parameters

        Returns:
            Dictionary with backtest results

        Raises:
            ValidationError: Invalid inputs
            DataNotFoundError: No data for tickers/dates
            DatabaseError: Database connection failure
            SpockMCPError: Other errors
        """
        try:
            # Convert dates
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Validate engine
            if engine == "vectorbt" and not VECTORBT_AVAILABLE:
                raise ValidationError(
                    "vectorbt engine not available (not installed)",
                    {"available_engines": ["custom"]}
                )

            if engine not in ["vectorbt", "custom"]:
                raise ValidationError(
                    "Invalid engine type",
                    {
                        "engine": engine,
                        "valid_engines": ["vectorbt", "custom"]
                    }
                )

            # Create backtest config
            config = BacktestConfig.from_risk_profile(
                start_date=start,
                end_date=end,
                risk_profile=risk_profile,
                regions=[region],
                tickers=tickers,
                initial_capital=initial_capital,
            )

            # Get or create runner
            cache_key = f"{region}:{start_date}:{end_date}:{risk_profile}"
            if cache_key not in self._runner_cache:
                runner = BacktestRunner(config, self.data_provider)
                self._runner_cache[cache_key] = runner
            else:
                runner = self._runner_cache[cache_key]

            logger.info("backtest_start",
                       strategy=strategy_type,
                       tickers=tickers,
                       engine=engine,
                       start_date=start_date,
                       end_date=end_date)

            # Create signal generator using factory
            signal_generator = SignalGeneratorFactory.create(
                strategy_type=strategy_type,
                parameters=parameters or {}
            )

            # Run backtest
            if engine == "vectorbt":
                result = runner.run(
                    engine="vectorbt",
                    signal_generator=signal_generator
                )
            else:
                result = runner.run(
                    engine="custom",
                    signal_generator=signal_generator
                )

            # Format result for MCP
            formatted_result = self._format_result(result, engine)

            logger.info("backtest_complete",
                       strategy=strategy_type,
                       engine=engine,
                       total_return=formatted_result.get("total_return"),
                       sharpe_ratio=formatted_result.get("sharpe_ratio"))

            return formatted_result

        except ValidationError:
            raise
        except DataNotFoundError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            # Log full exception details with traceback
            error_context = {
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "traceback": traceback.format_exc(),
                "strategy": strategy_type,
                "engine": engine,
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
            }
            logger.error("backtest_error", **error_context)

            # Raise with full error context
            raise SpockMCPError(
                code="BACKTEST_ERROR",
                message=f"Backtest execution failed: {type(e).__name__}: {str(e)}",
                details=error_context
            )


    def _format_result(
        self, result: Any, engine: str
    ) -> Dict[str, Any]:
        """
        Format backtest result for MCP response.

        Args:
            result: BacktestResult or VectorbtResult
            engine: Engine type

        Returns:
            Formatted result dictionary
        """
        if engine == "vectorbt":
            # VectorbtResult - convert all numpy types to JSON-serializable
            return {
                "success": True,
                "engine": "vectorbt",
                "performance": {
                    "total_return": self._to_json_serializable(result.total_return),
                    "annual_return": self._to_json_serializable(result.annual_return),
                    "sharpe_ratio": self._to_json_serializable(result.sharpe_ratio),
                    "sortino_ratio": self._to_json_serializable(result.sortino_ratio),
                    "calmar_ratio": self._to_json_serializable(result.calmar_ratio),
                    "max_drawdown": self._to_json_serializable(result.max_drawdown),
                    "max_drawdown_duration": self._to_json_serializable(result.max_drawdown_duration),
                },
                "trades": {
                    "total_trades": self._to_json_serializable(result.total_trades),
                    "win_rate": self._to_json_serializable(result.win_rate),
                    "avg_win": self._to_json_serializable(result.avg_win),
                    "avg_loss": self._to_json_serializable(result.avg_loss),
                    "profit_factor": self._to_json_serializable(result.profit_factor),
                },
                "execution": {
                    "execution_time": self._to_json_serializable(result.execution_time),
                    "start_date": result.start_date.isoformat() if result.start_date else None,
                    "end_date": result.end_date.isoformat() if result.end_date else None,
                    "initial_capital": self._to_json_serializable(result.initial_capital),
                },
            }
        else:
            # BacktestResult (custom engine) - convert all numpy types to JSON-serializable
            metrics = result.metrics
            return {
                "success": True,
                "engine": "custom",
                "performance": {
                    "total_return": self._to_json_serializable(metrics.total_return),
                    "annualized_return": self._to_json_serializable(metrics.annualized_return),
                    "cagr": self._to_json_serializable(metrics.cagr),
                    "sharpe_ratio": self._to_json_serializable(metrics.sharpe_ratio),
                    "sortino_ratio": self._to_json_serializable(metrics.sortino_ratio),
                    "calmar_ratio": self._to_json_serializable(metrics.calmar_ratio),
                    "max_drawdown": self._to_json_serializable(metrics.max_drawdown),
                    "max_drawdown_duration": self._to_json_serializable(metrics.max_drawdown_duration_days),
                },
                "trades": {
                    "total_trades": self._to_json_serializable(metrics.total_trades),
                    "win_rate": self._to_json_serializable(metrics.win_rate),
                    "profit_factor": self._to_json_serializable(metrics.profit_factor),
                    "avg_win_pct": self._to_json_serializable(metrics.avg_win_pct),
                    "avg_loss_pct": self._to_json_serializable(metrics.avg_loss_pct),
                    "avg_win_loss_ratio": self._to_json_serializable(metrics.avg_win_loss_ratio),
                    "avg_holding_period_days": self._to_json_serializable(metrics.avg_holding_period_days),
                },
                "execution": {
                    "execution_time": self._to_json_serializable(result.execution_time_seconds),
                    "start_date": result.config.start_date.isoformat(),
                    "end_date": result.config.end_date.isoformat(),
                    "initial_capital": self._to_json_serializable(result.config.initial_capital),
                },
                "final_value": self._to_json_serializable(result.final_portfolio_value),
                "total_profit": self._to_json_serializable(result.total_profit),
            }
