"""
Backtesting Optimization Framework

Provides walk-forward optimization, parameter scanning, and overfitting
detection for systematic strategy development.

Key Components:
- WalkForwardOptimizer: Time-series cross-validation
- ParameterScanner: Systematic parameter search
- OverfittingDetector: Detect overfitted strategies

Usage:
    from modules.backtesting.optimization import WalkForwardOptimizer

    optimizer = WalkForwardOptimizer(config, data_provider)
    results = optimizer.optimize(signal_generator_factory, param_grid)
"""

from .walk_forward_optimizer import WalkForwardOptimizer
from .parameter_scanner import ParameterScanner
from .overfitting_detector import OverfittingDetector

__all__ = [
    'WalkForwardOptimizer',
    'ParameterScanner',
    'OverfittingDetector',
]
