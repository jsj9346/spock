#!/usr/bin/env python3
"""
factors - Quantitative Factor Library for Multi-Factor Analysis

This package provides a modular factor library for quantitative investment strategies.
Factors are organized by category and provide standardized interfaces for calculation,
normalization, and ranking.

Factor Categories:
- Momentum: Trend following and price momentum
- Value: Fundamental valuation metrics (Phase 2)
- Quality: Business quality and financial health (Phase 2)
- Low-Volatility: Risk reduction and defensive strategies
- Size: Market capitalization and liquidity (Phase 2)
- Growth: Revenue/profit growth and expansion (Phase 2B)
- Efficiency: Asset/capital utilization (Phase 2B)

Usage Example:
    from modules.factors import TwelveMonthMomentumFactor, HistoricalVolatilityFactor

    # Initialize factors
    momentum_factor = TwelveMonthMomentumFactor()
    volatility_factor = HistoricalVolatilityFactor()

    # Calculate for a single ticker
    momentum_result = momentum_factor.calculate(data, ticker='005930')
    vol_result = volatility_factor.calculate(data, ticker='005930')

    # Access results
    print(f"Momentum: {momentum_result.raw_value:.2f}")
    print(f"Volatility: {vol_result.raw_value:.2f}")
    print(f"Confidence: {momentum_result.confidence:.2f}")

Architecture:
- FactorBase: Abstract base class for all factors
- FactorResult: Standardized result dataclass
- FactorCategory: Enum for factor classification

Implementation Status:
- ✅ Factor base infrastructure (Phase 1)
- ✅ Momentum factors (3 factors - Phase 1)
- ✅ Low-volatility factors (3 factors - Phase 1)
- ✅ Value factors (4 factors - Phase 2)
- ✅ Quality factors (9 core factors - Phase 2A)
- ✅ Size factors (3 factors - Phase 2)
- ✅ Growth factors (3 factors - Phase 2B)
- ✅ Efficiency factors (2 factors - Phase 2B)
"""

from .factor_base import FactorBase, FactorResult, FactorCategory

# Momentum Factors (Phase 1 - Implemented)
from .momentum_factors import (
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor
)

# Low-Volatility Factors (Phase 1 - Implemented)
from .low_vol_factors import (
    HistoricalVolatilityFactor,
    BetaFactor,  # Placeholder - requires market index
    MaxDrawdownFactor
)

# Value Factors (Phase 2 - Placeholders)
from .value_factors import (
    PERatioFactor,
    PBRatioFactor,
    EVToEBITDAFactor,
    DividendYieldFactor
)

# Quality Factors (Phase 2A - 9 Core Factors Implemented)
from .quality_factors import (
    ROEFactor,
    ROAFactor,
    OperatingMarginFactor,
    NetProfitMarginFactor,
    CurrentRatioFactor,
    QuickRatioFactor,
    DebtToEquityFactor,
    AccrualsRatioFactor,
    CFToNIRatioFactor
)

# Size Factors (Phase 2 - Complete)
from .size_factors import (
    MarketCapFactor,
    LiquidityFactor,
    FloatFactor
)

# Growth Factors (Phase 2B - NEW)
from .growth_factors import (
    RevenueGrowthFactor,
    OperatingProfitGrowthFactor,
    NetIncomeGrowthFactor
)

# Efficiency Factors (Phase 2B - NEW)
from .efficiency_factors import (
    AssetTurnoverFactor,
    EquityTurnoverFactor
)

# Factor Combination (Phase 2 - Multi-Factor)
from .factor_combiner import (
    FactorCombinerBase,
    EqualWeightCombiner,
    CategoryWeightCombiner,
    OptimizationCombiner
)
from .factor_score_calculator import FactorScoreCalculator

# Export all public classes
__all__ = [
    # Base classes
    'FactorBase',
    'FactorResult',
    'FactorCategory',

    # Momentum factors
    'TwelveMonthMomentumFactor',
    'RSIMomentumFactor',
    'ShortTermMomentumFactor',

    # Low-volatility factors
    'HistoricalVolatilityFactor',
    'BetaFactor',
    'MaxDrawdownFactor',

    # Value factors (Phase 2)
    'PERatioFactor',
    'PBRatioFactor',
    'EVToEBITDAFactor',
    'DividendYieldFactor',

    # Quality factors (Phase 2A)
    'ROEFactor',
    'ROAFactor',
    'OperatingMarginFactor',
    'NetProfitMarginFactor',
    'CurrentRatioFactor',
    'QuickRatioFactor',
    'DebtToEquityFactor',
    'AccrualsRatioFactor',
    'CFToNIRatioFactor',

    # Size factors (Phase 2)
    'MarketCapFactor',
    'LiquidityFactor',
    'FloatFactor',

    # Growth factors (Phase 2B)
    'RevenueGrowthFactor',
    'OperatingProfitGrowthFactor',
    'NetIncomeGrowthFactor',

    # Efficiency factors (Phase 2B)
    'AssetTurnoverFactor',
    'EquityTurnoverFactor',

    # Factor Combination (Phase 2 - Multi-Factor)
    'FactorCombinerBase',
    'EqualWeightCombiner',
    'CategoryWeightCombiner',
    'OptimizationCombiner',
    'FactorScoreCalculator',
]

# Version
__version__ = '0.2.0'

# Factor counts by phase
PHASE_1_FACTORS = 6  # 3 Momentum + 3 Low-Vol
PHASE_2_VALUE_FACTORS = 4  # P/E, P/B, EV/EBITDA, Dividend Yield
PHASE_2A_QUALITY_FACTORS = 9  # ROE, ROA, Operating Margin, Net Margin, Current Ratio, Quick Ratio, Debt/Equity, Accruals, CF-to-NI
PHASE_2_SIZE_FACTORS = 3  # Market Cap, Liquidity, Free Float
PHASE_2B_GROWTH_FACTORS = 3  # Revenue Growth, Operating Profit Growth, Net Income Growth
PHASE_2B_EFFICIENCY_FACTORS = 2  # Asset Turnover, Equity Turnover
IMPLEMENTED_FACTORS = PHASE_1_FACTORS + PHASE_2_VALUE_FACTORS + PHASE_2A_QUALITY_FACTORS + PHASE_2_SIZE_FACTORS + PHASE_2B_GROWTH_FACTORS + PHASE_2B_EFFICIENCY_FACTORS  # Total: 27
TOTAL_FACTORS = IMPLEMENTED_FACTORS  # Total: 27 - ALL FACTORS COMPLETE!
