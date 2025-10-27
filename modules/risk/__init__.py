"""
Risk Management Module

This module provides risk assessment and management tools for the Quant Investment Platform.
Implements VaR/CVaR calculation, stress testing, correlation analysis, and factor exposure tracking.

Risk Metrics:
- VaR: Value at Risk (Historical, Parametric, Monte Carlo)
- CVaR: Conditional VaR (Expected Shortfall)
- Stress Testing: Scenario-based portfolio stress analysis
- Correlation Analysis: Asset and factor correlation matrices
- Exposure Tracking: Factor and sector exposure monitoring

Core Components:
- VaRCalculator: Value at Risk calculation with multiple methods
- CVaRCalculator: Conditional VaR calculation
- StressTester: Scenario-based stress testing
- CorrelationAnalyzer: Correlation matrix analysis
- ExposureTracker: Factor and sector exposure tracking

Dependencies:
- scipy 1.11.0+: Statistical functions
- numpy 1.24.3+: Numerical operations
- pandas 2.0.3+: Time-series analysis

Usage Example:
    from modules.risk import VaRCalculator

    calculator = VaRCalculator()
    result = calculator.calculate(
        returns=portfolio_returns,
        confidence_level=0.95,
        time_horizon=10,
        method="historical"
    )

    print(f"10-day VaR (95%): {result.var_percent:.2f}%")

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - In Development
"""

# Base classes and configuration
from .risk_base import RiskCalculator, RiskConfig
from .risk_base import VaRResult, CVaRResult, StressTestResult, CorrelationResult, ExposureResult

# Risk calculators
from .var_calculator import VaRCalculator
from .cvar_calculator import CVaRCalculator
# from .stress_tester import StressTester  # TODO: Implement
# from .correlation_analyzer import CorrelationAnalyzer  # TODO: Implement
# from .exposure_tracker import ExposureTracker  # TODO: Implement

__all__ = [
    # Base classes and configuration
    'RiskCalculator',
    'RiskConfig',

    # Result classes
    'VaRResult',
    'CVaRResult',
    'StressTestResult',
    'CorrelationResult',
    'ExposureResult',

    # Risk calculators
    'VaRCalculator',
    'CVaRCalculator',
    # 'StressTester',  # TODO: Implement
    # 'CorrelationAnalyzer',  # TODO: Implement
    # 'ExposureTracker',  # TODO: Implement
]

__version__ = '1.0.0'

# TODO: Implement VaR/CVaR calculators (Track 5)
# TODO: Add stress test scenarios (2008, 2020, 2022)
# TODO: Add factor exposure analysis
