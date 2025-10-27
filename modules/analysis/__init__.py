#!/usr/bin/env python3
"""
Factor Analysis Module - Week 2-3 Transition

Provides quantitative factor analysis tools for systematic investment research:

1. FactorAnalyzer - Quintile return analysis and Information Coefficient (IC) calculation
2. FactorCorrelationAnalyzer - Pairwise factor correlations and redundancy detection
3. PerformanceReporter - Visualization and reporting tools

Academic Foundation:
- Fama & French (1992, 1993) - Cross-sectional return analysis
- Grinold & Kahn (2000) - Active Portfolio Management (IC framework)
- Sloan (1996) - Accruals and future stock returns

Author: Spock Quant Platform
Date: 2025-10-23
"""

from .factor_analyzer import FactorAnalyzer
from .factor_correlation import FactorCorrelationAnalyzer
from .performance_reporter import PerformanceReporter

__all__ = [
    'FactorAnalyzer',
    'FactorCorrelationAnalyzer',
    'PerformanceReporter',
]

__version__ = '1.0.0'
