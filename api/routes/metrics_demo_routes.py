"""
Metrics Demo Routes

Demo endpoints to test application-level metrics collection.

These endpoints simulate backtesting and factor calculation operations
to demonstrate Prometheus metrics integration.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 1.0.0
"""

import time
import random
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from api.utils.metrics_decorators import (
    track_backtest_execution,
    track_factor_calculation,
    track_optimization,
)
from api.utils.application_metrics import (
    FACTOR_USAGE,
    record_backtest_result,
    record_factor_statistics,
)


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class BacktestRequest(BaseModel):
    """Backtest request model"""
    strategy_name: str
    engine: str = 'backtrader'
    simulate_duration: float = 2.0  # seconds
    simulate_failure: bool = False


class BacktestResponse(BaseModel):
    """Backtest response model"""
    strategy_name: str
    engine: str
    status: str
    sharpe_ratio: Optional[float] = None
    total_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    num_trades: Optional[int] = None
    execution_time: float


class FactorCalculationRequest(BaseModel):
    """Factor calculation request model"""
    factor_name: str
    num_tickers: int = 100
    simulate_duration: float = 1.0
    simulate_failure: bool = False


class FactorCalculationResponse(BaseModel):
    """Factor calculation response model"""
    factor_name: str
    num_scores: int
    mean_score: float
    stddev_score: float
    execution_time: float


class OptimizationRequest(BaseModel):
    """Optimization request model"""
    method: str = 'mean_variance'
    num_assets: int = 50
    simulate_duration: float = 3.0
    simulate_failure: bool = False


class OptimizationResponse(BaseModel):
    """Optimization response model"""
    method: str
    num_assets: int
    status: str
    execution_time: float
    weights: Optional[List[float]] = None


# ============================================================================
# Demo Endpoints
# ============================================================================

@router.post("/demo/backtest", response_model=BacktestResponse, tags=["Metrics Demo"])
async def demo_backtest(request: BacktestRequest):
    """
    Demo backtest endpoint with metrics collection.

    Simulates a backtest execution and collects Prometheus metrics:
    - backtest_duration_seconds (histogram)
    - backtest_executions_total (counter)
    - backtest_sharpe_ratio (gauge)
    - backtest_total_return_percent (gauge)
    - backtest_max_drawdown_percent (gauge)
    """
    @track_backtest_execution
    def run_demo_backtest(strategy_name: str, engine: str, duration: float, fail: bool):
        """Simulated backtest function"""
        # Simulate backtest processing
        time.sleep(duration)

        if fail:
            raise ValueError("Simulated backtest failure")

        # Generate random but realistic results
        sharpe_ratio = random.uniform(0.5, 2.5)
        total_return = random.uniform(0.05, 0.50)
        max_drawdown = random.uniform(-0.25, -0.05)
        win_rate = random.uniform(0.45, 0.65)
        num_trades = random.randint(50, 300)

        return {
            'sharpe_ratio': sharpe_ratio,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'num_trades': num_trades
        }

    start_time = time.time()

    try:
        result = run_demo_backtest(
            strategy_name=request.strategy_name,
            engine=request.engine,
            duration=request.simulate_duration,
            fail=request.simulate_failure
        )

        return BacktestResponse(
            strategy_name=request.strategy_name,
            engine=request.engine,
            status='success',
            sharpe_ratio=result['sharpe_ratio'],
            total_return=result['total_return'] * 100,  # Convert to percentage
            max_drawdown=abs(result['max_drawdown']) * 100,
            win_rate=result['win_rate'] * 100,
            num_trades=result['num_trades'],
            execution_time=time.time() - start_time
        )

    except Exception as e:
        return BacktestResponse(
            strategy_name=request.strategy_name,
            engine=request.engine,
            status='failed',
            execution_time=time.time() - start_time
        )


@router.post("/demo/factor", response_model=FactorCalculationResponse, tags=["Metrics Demo"])
async def demo_factor_calculation(request: FactorCalculationRequest):
    """
    Demo factor calculation endpoint with metrics collection.

    Simulates factor calculation and collects Prometheus metrics:
    - factor_calculation_duration_seconds (histogram)
    - factor_calculations_total (counter)
    - factor_usage_total (counter)
    - factor_score_mean (gauge)
    - factor_score_stddev (gauge)
    """
    @track_factor_calculation(factor_name=request.factor_name)
    def calculate_demo_factor(num_tickers: int, duration: float, fail: bool):
        """Simulated factor calculation function"""
        # Simulate factor calculation
        time.sleep(duration)

        if fail:
            raise ValueError("Simulated factor calculation failure")

        # Generate random factor scores (normalized 0-100)
        scores = [random.uniform(20, 80) for _ in range(num_tickers)]
        return scores

    start_time = time.time()

    try:
        scores = calculate_demo_factor(
            num_tickers=request.num_tickers,
            duration=request.simulate_duration,
            fail=request.simulate_failure
        )

        import numpy as np
        mean_score = float(np.mean(scores))
        stddev_score = float(np.std(scores))

        return FactorCalculationResponse(
            factor_name=request.factor_name,
            num_scores=len(scores),
            mean_score=mean_score,
            stddev_score=stddev_score,
            execution_time=time.time() - start_time
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/demo/optimization", response_model=OptimizationResponse, tags=["Metrics Demo"])
async def demo_optimization(request: OptimizationRequest):
    """
    Demo portfolio optimization endpoint with metrics collection.

    Simulates portfolio optimization and collects Prometheus metrics:
    - optimization_duration_seconds (histogram)
    - optimization_executions_total (counter)
    """
    start_time = time.time()

    try:
        with track_optimization(method=request.method, num_assets=request.num_assets):
            # Simulate optimization processing
            time.sleep(request.simulate_duration)

            if request.simulate_failure:
                raise ValueError("Simulated optimization failure")

            # Generate random weights that sum to 1
            weights = [random.random() for _ in range(request.num_assets)]
            weight_sum = sum(weights)
            weights = [w / weight_sum for w in weights]

        return OptimizationResponse(
            method=request.method,
            num_assets=request.num_assets,
            status='success',
            execution_time=time.time() - start_time,
            weights=weights[:10]  # Return first 10 weights for brevity
        )

    except Exception as e:
        return OptimizationResponse(
            method=request.method,
            num_assets=request.num_assets,
            status='failed',
            execution_time=time.time() - start_time
        )


@router.get("/demo/metrics-status", tags=["Metrics Demo"])
async def metrics_status():
    """
    Get current status of application metrics.

    Returns a summary of metrics collection status.
    """
    return {
        "status": "operational",
        "metrics_enabled": True,
        "available_metrics": {
            "backtest": [
                "backtest_duration_seconds",
                "backtest_executions_total",
                "backtest_sharpe_ratio",
                "backtest_total_return_percent",
                "backtest_max_drawdown_percent",
                "backtest_win_rate_percent",
                "backtest_num_trades"
            ],
            "factor": [
                "factor_calculation_duration_seconds",
                "factor_calculations_total",
                "factor_usage_total",
                "factor_score_mean",
                "factor_score_stddev"
            ],
            "optimization": [
                "optimization_duration_seconds",
                "optimization_executions_total"
            ]
        },
        "prometheus_endpoint": "/metrics"
    }
