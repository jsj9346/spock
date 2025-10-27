"""
Metrics Collection Decorators

Decorators for automatic metrics collection on business logic functions.

Usage:
    @track_backtest_execution
    def run_backtest(...):
        # backtest logic
        return results

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 1.0.0
"""

import time
from functools import wraps
from typing import Callable, Any
from contextlib import contextmanager

from loguru import logger

from api.utils.application_metrics import (
    BACKTEST_DURATION,
    BACKTEST_EXECUTIONS,
    FACTOR_CALCULATION_DURATION,
    FACTOR_CALCULATIONS,
    FACTOR_USAGE,
    OPTIMIZATION_DURATION,
    OPTIMIZATION_EXECUTIONS,
    DATA_COLLECTION_DURATION,
    DATA_COLLECTION_ERRORS,
    record_backtest_result,
    record_factor_statistics,
)


# ============================================================================
# Backtest Metrics Decorators
# ============================================================================

def track_backtest_execution(func: Callable) -> Callable:
    """
    Decorator to track backtest execution metrics.

    Automatically records:
    - Execution duration
    - Success/failure status
    - Result metrics (Sharpe ratio, returns, etc.)

    Usage:
        @track_backtest_execution
        def run_backtest(strategy_name, engine, ...):
            # backtest logic
            return {
                'sharpe_ratio': 1.5,
                'total_return': 0.25,
                'max_drawdown': -0.12,
                'win_rate': 0.58,
                'num_trades': 150
            }
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        # Extract strategy_name and engine from args/kwargs
        strategy_name = kwargs.get('strategy_name', 'unknown')
        engine = kwargs.get('engine', 'unknown')

        # If not in kwargs, try to extract from args
        if strategy_name == 'unknown' and len(args) >= 1:
            strategy_name = str(args[0])
        if engine == 'unknown' and len(args) >= 2:
            engine = str(args[1])

        start_time = time.time()
        status = 'failed'
        result = None

        try:
            # Execute backtest
            result = func(*args, **kwargs)
            status = 'success'

            # Record result metrics if available
            if isinstance(result, dict):
                record_backtest_result(
                    strategy_name=strategy_name,
                    sharpe_ratio=result.get('sharpe_ratio'),
                    total_return=result.get('total_return'),
                    max_drawdown=result.get('max_drawdown'),
                    win_rate=result.get('win_rate'),
                    num_trades=result.get('num_trades')
                )

            logger.info(
                f"Backtest completed: strategy={strategy_name}, "
                f"engine={engine}, duration={time.time() - start_time:.2f}s"
            )

            return result

        except TimeoutError:
            status = 'timeout'
            logger.warning(
                f"Backtest timeout: strategy={strategy_name}, engine={engine}"
            )
            raise

        except Exception as e:
            status = 'failed'
            logger.error(
                f"Backtest failed: strategy={strategy_name}, "
                f"engine={engine}, error={e}"
            )
            raise

        finally:
            # Record execution duration
            duration = time.time() - start_time
            BACKTEST_DURATION.labels(
                strategy_name=strategy_name,
                engine=engine
            ).observe(duration)

            # Record execution counter
            BACKTEST_EXECUTIONS.labels(
                strategy_name=strategy_name,
                engine=engine,
                status=status
            ).inc()

    return wrapper


# ============================================================================
# Factor Calculation Metrics Decorators
# ============================================================================

def track_factor_calculation(factor_name: str = None):
    """
    Decorator to track factor calculation metrics.

    Args:
        factor_name: Factor name (optional, will try to infer from function name)

    Usage:
        @track_factor_calculation(factor_name='momentum')
        def calculate_momentum_factor(tickers, data):
            # calculation logic
            return scores

        # Or with auto-detection:
        @track_factor_calculation()
        def momentum_factor(tickers, data):  # factor_name = 'momentum'
            return scores
    """
    def decorator(func: Callable) -> Callable:
        # Infer factor name from function name if not provided
        inferred_factor_name = factor_name
        if inferred_factor_name is None:
            func_name = func.__name__
            # Remove common prefixes/suffixes
            inferred_factor_name = func_name.replace('calculate_', '').replace('_factor', '')

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status = 'failed'
            result = None

            try:
                # Execute factor calculation
                result = func(*args, **kwargs)
                status = 'success'

                # Record factor usage
                FACTOR_USAGE.labels(factor_name=inferred_factor_name).inc()

                # Record factor statistics if result is a list/dict of scores
                if isinstance(result, (list, dict)):
                    scores = list(result.values()) if isinstance(result, dict) else result
                    record_factor_statistics(inferred_factor_name, scores)

                logger.debug(
                    f"Factor calculated: factor={inferred_factor_name}, "
                    f"duration={time.time() - start_time:.3f}s"
                )

                return result

            except Exception as e:
                status = 'failed'
                logger.error(
                    f"Factor calculation failed: factor={inferred_factor_name}, error={e}"
                )
                raise

            finally:
                # Record calculation duration
                duration = time.time() - start_time
                FACTOR_CALCULATION_DURATION.labels(
                    factor_name=inferred_factor_name
                ).observe(duration)

                # Record calculation counter
                FACTOR_CALCULATIONS.labels(
                    factor_name=inferred_factor_name,
                    status=status
                ).inc()

        return wrapper

    # Support both @track_factor_calculation and @track_factor_calculation()
    if callable(factor_name):
        func = factor_name
        factor_name = None
        return decorator(func)

    return decorator


# ============================================================================
# Optimization Metrics Context Manager
# ============================================================================

@contextmanager
def track_optimization(method: str, num_assets: int):
    """
    Context manager to track portfolio optimization metrics.

    Usage:
        with track_optimization(method='mean_variance', num_assets=50):
            weights = optimizer.optimize()
            return weights
    """
    start_time = time.time()
    status = 'failed'

    try:
        yield
        status = 'success'

    except TimeoutError:
        status = 'timeout'
        logger.warning(f"Optimization timeout: method={method}, num_assets={num_assets}")
        raise

    except ValueError as e:
        if 'no solution' in str(e).lower():
            status = 'no_solution'
        logger.error(f"Optimization failed: method={method}, error={e}")
        raise

    except Exception as e:
        status = 'failed'
        logger.error(f"Optimization error: method={method}, error={e}")
        raise

    finally:
        # Record optimization duration
        duration = time.time() - start_time
        OPTIMIZATION_DURATION.labels(
            method=method,
            num_assets=str(num_assets)
        ).observe(duration)

        # Record optimization counter
        OPTIMIZATION_EXECUTIONS.labels(
            method=method,
            status=status
        ).inc()

        logger.info(
            f"Optimization completed: method={method}, "
            f"num_assets={num_assets}, status={status}, duration={duration:.2f}s"
        )


# ============================================================================
# Data Collection Metrics Decorators
# ============================================================================

def track_data_collection(data_source: str, data_type: str):
    """
    Decorator to track data collection metrics.

    Args:
        data_source: Data source name (kis_api, polygon_io, yfinance)
        data_type: Data type (ohlcv, fundamentals, technical_indicators)

    Usage:
        @track_data_collection(data_source='kis_api', data_type='ohlcv')
        def collect_kr_ohlcv_data(tickers, start_date, end_date):
            # collection logic
            return data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                # Execute data collection
                result = func(*args, **kwargs)

                logger.debug(
                    f"Data collected: source={data_source}, type={data_type}, "
                    f"duration={time.time() - start_time:.2f}s"
                )

                return result

            except Exception as e:
                # Record error
                error_type = type(e).__name__
                DATA_COLLECTION_ERRORS.labels(
                    data_source=data_source,
                    error_type=error_type
                ).inc()

                logger.error(
                    f"Data collection failed: source={data_source}, "
                    f"type={data_type}, error={e}"
                )
                raise

            finally:
                # Record collection duration
                duration = time.time() - start_time
                DATA_COLLECTION_DURATION.labels(
                    data_source=data_source,
                    data_type=data_type
                ).observe(duration)

        return wrapper

    return decorator


# ============================================================================
# Utility Functions
# ============================================================================

def safe_execute_with_metrics(
    func: Callable,
    metric_name: str,
    *args,
    **kwargs
) -> Any:
    """
    Execute a function and safely record metrics without breaking on metric errors.

    Args:
        func: Function to execute
        metric_name: Metric name for logging
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Metric recording failed for {metric_name}: {e}")
        # Don't break application logic due to metric errors
        pass
