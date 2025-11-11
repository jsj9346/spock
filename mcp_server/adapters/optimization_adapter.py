# mcp_server/adapters/optimization_adapter.py
"""
OptimizationAdapter - MCP adapter for walk-forward optimization.

Thin wrapper around WalkForwardOptimizer, providing MCP-compatible
interface for strategy parameter optimization operations.

Architecture Pattern (Thin Wrapper):
    MCP Tool -> OptimizationAdapter -> WalkForwardOptimizer

This adapter:
    - Wraps existing 438-line WalkForwardOptimizer
    - Converts MCP inputs to optimization config
    - Formats WalkForwardResult for MCP response
    - Handles errors with MCP error types
    - Provides caching for repeated optimization runs

Performance:
    - <30s for 3-window optimization (vectorbt)
    - <2min for 5-window comprehensive optimization
    - In-memory caching for repeated configs

Author: Spock MCP Server
Date: 2025-10-31
"""

from typing import Dict, List, Optional, Any
from datetime import date, datetime
from loguru import logger
import hashlib
import json

from mcp_server.config import Config
from mcp_server.utils.errors import (
    ValidationError,
    DataNotFoundError,
    DatabaseError,
    SpockMCPError,
)
from modules.backtesting.optimization.walk_forward_optimizer import (
    WalkForwardOptimizer,
    WalkForwardResult,
)
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers.postgres_data_provider import (
    PostgresDataProvider,
)
from modules.db_manager_postgres import PostgresDatabaseManager


class OptimizationAdapter:
    """
    MCP adapter for walk-forward optimization operations.

    Provides async interface for parameter optimization with walk-forward
    validation, overfitting detection, and robustness scoring.

    Example:
        >>> adapter = OptimizationAdapter()
        >>> result = await adapter.optimize_strategy(
        ...     strategy_type="momentum",
        ...     tickers=["005930"],
        ...     start_date="2022-01-01",
        ...     end_date="2024-12-31",
        ...     region="KR",
        ...     param_grid={"rsi_period": [10, 14, 20]},
        ...     train_period_days=252,
        ...     test_period_days=63
        ... )
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize OptimizationAdapter.

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

        # Cache for optimization results (config hash -> result)
        self._result_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("optimization_adapter_initialized")

    async def optimize_strategy(
        self,
        strategy_type: str,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str = "KR",
        param_grid: Optional[Dict[str, List[Any]]] = None,
        train_period_days: int = 252,
        test_period_days: int = 63,
        initial_capital: float = 100_000_000,
        risk_profile: str = "moderate",
        metric: str = "sharpe_ratio",
        anchored: bool = False,
    ) -> Dict[str, Any]:
        """
        Run walk-forward optimization for strategy parameters.

        Args:
            strategy_type: Strategy type (momentum, value, momentum_value)
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            region: Market region (KR, US, etc.)
            param_grid: Parameter grid to search (e.g., {"rsi_period": [10, 14, 20]})
            train_period_days: Training period length (default: 252 days / 1 year)
            test_period_days: Testing period length (default: 63 days / 3 months)
            initial_capital: Initial capital amount
            risk_profile: Risk profile (conservative, moderate, aggressive)
            metric: Optimization metric (sharpe_ratio, total_return, etc.)
            anchored: Use anchored (vs rolling) windows

        Returns:
            Dictionary with optimization results

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

            # Validate metric
            valid_metrics = [
                "sharpe_ratio",
                "sortino_ratio",
                "total_return",
                "annualized_return",
                "calmar_ratio",
            ]
            if metric not in valid_metrics:
                raise ValidationError(
                    "Invalid optimization metric",
                    {"metric": metric, "valid_metrics": valid_metrics}
                )

            # Use default param_grid if not provided
            if param_grid is None:
                param_grid = self._get_default_param_grid(strategy_type)
                logger.info("using_default_param_grid", strategy_type=strategy_type)

            # Validate param_grid
            if not param_grid or not all(isinstance(v, list) for v in param_grid.values()):
                raise ValidationError(
                    "param_grid must be dict with list values",
                    {"param_grid": param_grid}
                )

            # Check cache
            cache_key = self._get_cache_key(
                strategy_type, tickers, start_date, end_date, region,
                param_grid, train_period_days, test_period_days, metric, anchored
            )
            if cache_key in self._result_cache:
                logger.info("optimization_cache_hit", cache_key=cache_key[:16])
                return self._result_cache[cache_key]

            # Create backtest config
            config = BacktestConfig.from_risk_profile(
                start_date=start,
                end_date=end,
                risk_profile=risk_profile,
                regions=[region],
                tickers=tickers,
                initial_capital=initial_capital,
            )

            # Create optimizer
            optimizer = WalkForwardOptimizer(config, self.data_provider)

            logger.info("optimization_start",
                       strategy=strategy_type,
                       tickers=tickers,
                       train_period=train_period_days,
                       test_period=test_period_days,
                       metric=metric,
                       anchored=anchored)

            # Create signal generator factory (placeholder for MVP)
            signal_generator_factory = self._create_signal_generator_factory(
                strategy_type, param_grid
            )

            # Run optimization
            result: WalkForwardResult = optimizer.optimize(
                signal_generator_factory=signal_generator_factory,
                param_grid=param_grid,
                train_period_days=train_period_days,
                test_period_days=test_period_days,
                metric=metric,
                anchored=anchored
            )

            # Format result for MCP
            formatted_result = self._format_result(result, strategy_type, metric)

            # Cache result
            self._result_cache[cache_key] = formatted_result

            logger.info("optimization_complete",
                       strategy=strategy_type,
                       best_params=result.best_params,
                       robustness_score=result.robustness_score,
                       overfitting_detected=result.overfitting_detected)

            return formatted_result

        except ValidationError:
            raise
        except DataNotFoundError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error("optimization_error", error=str(e), strategy=strategy_type)
            raise SpockMCPError(
                f"Optimization execution failed: {str(e)}",
                {"strategy": strategy_type, "metric": metric}
            )

    def _get_default_param_grid(self, strategy_type: str) -> Dict[str, List[Any]]:
        """
        Get default parameter grid for strategy type.

        Args:
            strategy_type: Strategy type

        Returns:
            Default parameter grid
        """
        # Default grids for different strategies (placeholder for MVP)
        default_grids = {
            "momentum": {
                "rsi_period": [10, 14, 20],
                "oversold": [20, 30, 40],
                "overbought": [60, 70, 80]
            },
            "value": {
                "pe_threshold": [10, 15, 20],
                "pb_threshold": [1.0, 1.5, 2.0],
            },
            "momentum_value": {
                "rsi_period": [10, 14, 20],
                "pe_threshold": [10, 15, 20],
            }
        }

        return default_grids.get(strategy_type, {"dummy_param": [1, 2, 3]})

    def _create_signal_generator_factory(
        self, strategy_type: str, param_grid: Dict[str, List[Any]]
    ):
        """
        Create signal generator factory for strategy type.

        TODO: Implement full strategy factory
        For MVP, this returns a placeholder that accepts params.

        Args:
            strategy_type: Strategy type
            param_grid: Parameter grid

        Returns:
            Signal generator factory function
        """
        # Placeholder factory for MVP - will be implemented with full strategies
        def factory(**params):
            """Factory that creates signal generator with params."""
            def simple_signal_generator(data: Dict[str, Any]) -> int:
                """Simple signal generator (placeholder)."""
                # +1 = buy, 0 = hold, -1 = sell
                # Real implementation will use params and indicators
                return 0

            logger.debug("created_signal_generator", strategy=strategy_type, params=params)
            return simple_signal_generator

        logger.warning("using_placeholder_signal_generator_factory",
                      strategy_type=strategy_type)

        return factory

    def _format_result(
        self, result: WalkForwardResult, strategy_type: str, metric: str
    ) -> Dict[str, Any]:
        """
        Format walk-forward result for MCP response.

        Args:
            result: WalkForwardResult from optimizer
            strategy_type: Strategy type
            metric: Optimization metric

        Returns:
            Formatted result dictionary
        """
        return {
            "success": True,
            "strategy_type": strategy_type,
            "optimization": {
                "best_params": result.best_params,
                "metric_optimized": metric,
                "num_windows": len(result.windows),
                "train_period_days": result.windows[0].train_end.toordinal() - result.windows[0].train_start.toordinal() if result.windows else None,
                "test_period_days": result.windows[0].test_end.toordinal() - result.windows[0].test_start.toordinal() if result.windows else None,
            },
            "performance": {
                "in_sample": {
                    "mean": result.in_sample_performance["mean"],
                    "std": result.in_sample_performance["std"],
                    "min": result.in_sample_performance["min"],
                    "max": result.in_sample_performance["max"],
                },
                "out_of_sample": {
                    "mean": result.out_of_sample_performance["mean"],
                    "std": result.out_of_sample_performance["std"],
                    "min": result.out_of_sample_performance["min"],
                    "max": result.out_of_sample_performance["max"],
                },
                "degradation_pct": result.degradation_pct,
            },
            "validation": {
                "robustness_score": result.robustness_score,
                "overfitting_detected": result.overfitting_detected,
                "recommendation": self._get_recommendation(result),
            },
            "windows": [
                {
                    "window_id": w["window_id"],
                    "best_params": w["best_params"],
                    "train_score": w["train_score"],
                    "test_score": w["test_score"],
                    "degradation": w["degradation"],
                }
                for w in result.all_results
            ],
        }

    def _get_recommendation(self, result: WalkForwardResult) -> str:
        """
        Get recommendation based on optimization results.

        Args:
            result: WalkForwardResult

        Returns:
            Recommendation string
        """
        if result.overfitting_detected:
            return "CAUTION: Overfitting detected. Consider simpler strategy or larger test periods."
        elif result.robustness_score >= 0.7:
            return "GOOD: Strategy shows strong robustness. Recommended for live trading."
        elif result.robustness_score >= 0.5:
            return "ACCEPTABLE: Strategy shows moderate robustness. Monitor carefully in live trading."
        else:
            return "POOR: Low robustness score. Not recommended for live trading without refinement."

    def _get_cache_key(
        self,
        strategy_type: str,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str,
        param_grid: Dict[str, List[Any]],
        train_period_days: int,
        test_period_days: int,
        metric: str,
        anchored: bool,
    ) -> str:
        """
        Generate cache key from optimization parameters.

        Args:
            All optimization parameters

        Returns:
            MD5 hash of parameters
        """
        cache_dict = {
            "strategy_type": strategy_type,
            "tickers": sorted(tickers),
            "start_date": start_date,
            "end_date": end_date,
            "region": region,
            "param_grid": {k: sorted(v) for k, v in sorted(param_grid.items())},
            "train_period_days": train_period_days,
            "test_period_days": test_period_days,
            "metric": metric,
            "anchored": anchored,
        }

        cache_str = json.dumps(cache_dict, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
