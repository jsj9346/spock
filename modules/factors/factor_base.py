#!/usr/bin/env python3
"""
factor_base.py - Abstract Base Class for Factor Library

Purpose:
- Define standardized interface for all quantitative factors
- Provide common utilities for factor calculation, normalization, and ranking
- Enable modular factor development and testing

Factor Categories:
1. Momentum - Trend following and price momentum
2. Value - Fundamental valuation metrics
3. Quality - Business quality and financial health
4. Low-Volatility - Risk reduction and defensive strategies
5. Size - Market capitalization and liquidity

Design Philosophy:
- Factors return z-scores (standardized) for cross-sectional ranking
- Each factor provides confidence score for quality control
- Metadata enables factor attribution and debugging
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FactorCategory(Enum):
    """Factor category classification"""
    MOMENTUM = "momentum"         # Trend following, price momentum
    VALUE = "value"              # Fundamental valuation
    QUALITY = "quality"          # Business quality, financial health
    LOW_VOL = "low_volatility"   # Risk reduction, defensive
    SIZE = "size"                # Market cap, liquidity
    GROWTH = "growth"            # Revenue/profit growth, expansion
    EFFICIENCY = "efficiency"    # Asset/capital utilization


@dataclass
class FactorResult:
    """
    Standardized factor calculation result

    Attributes:
        ticker: Stock ticker symbol
        factor_name: Name of the factor (e.g., '12M_Momentum')
        raw_value: Raw factor value before normalization
        z_score: Standardized z-score for cross-sectional ranking
        percentile: Percentile rank (0-100) across universe
        confidence: Confidence score (0-1) for factor quality
        metadata: Additional details for debugging and attribution
        calculation_date: Date of factor calculation
    """
    ticker: str
    factor_name: str
    raw_value: float
    z_score: float
    percentile: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculation_date: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate factor result ranges"""
        self.percentile = max(0.0, min(100.0, self.percentile))
        self.confidence = max(0.0, min(1.0, self.confidence))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'ticker': self.ticker,
            'factor_name': self.factor_name,
            'raw_value': self.raw_value,
            'z_score': self.z_score,
            'percentile': self.percentile,
            'confidence': self.confidence,
            'metadata': self.metadata,
            'calculation_date': self.calculation_date.isoformat()
        }


class FactorBase(ABC):
    """
    Abstract base class for all quantitative factors

    Subclasses must implement:
    - calculate(): Core factor calculation logic
    - get_required_columns(): Data requirements

    Provides utilities for:
    - Z-score standardization
    - Percentile ranking
    - Data validation
    - Missing data handling
    """

    def __init__(
        self,
        name: str,
        category: FactorCategory,
        lookback_days: int = 250,
        min_required_days: int = 60
    ):
        """
        Initialize factor

        Args:
            name: Factor name (e.g., '12M_Momentum')
            category: Factor category (Momentum, Value, etc.)
            lookback_days: Days of historical data needed
            min_required_days: Minimum days required for calculation
        """
        self.name = name
        self.category = category
        self.lookback_days = lookback_days
        self.min_required_days = min_required_days

    @abstractmethod
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate factor value for a single ticker

        Args:
            data: Historical OHLCV data with technical indicators
                  Required columns depend on factor (see get_required_columns)
            ticker: Stock ticker symbol

        Returns:
            FactorResult if calculation successful, None otherwise
        """
        pass

    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """
        Return list of required DataFrame columns

        Returns:
            List of column names (e.g., ['close', 'volume', 'ma20'])
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate input data meets requirements

        Args:
            data: Input DataFrame to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check empty DataFrame
        if data.empty:
            return False, "Empty DataFrame"

        # Check minimum data length
        if len(data) < self.min_required_days:
            return False, f"Insufficient data: {len(data)} days (min: {self.min_required_days})"

        # Check required columns
        required_columns = self.get_required_columns()
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            return False, f"Missing columns: {missing_columns}"

        # Check for all-NULL columns
        for col in required_columns:
            if data[col].isnull().all():
                return False, f"Column '{col}' is all NULL"

        return True, "Valid"

    def _calculate_z_score(self, value: float, values: np.ndarray) -> float:
        """
        Calculate z-score for cross-sectional standardization

        Args:
            value: Raw factor value for single ticker
            values: Array of factor values across universe

        Returns:
            Standardized z-score
        """
        # Remove NaN values
        clean_values = values[~np.isnan(values)]

        if len(clean_values) < 2:
            return 0.0

        mean = np.mean(clean_values)
        std = np.std(clean_values)

        # Prevent division by zero
        if std == 0:
            return 0.0

        z_score = (value - mean) / std

        # Cap extreme values at ±3 sigma
        return np.clip(z_score, -3.0, 3.0)

    def _calculate_percentile(self, value: float, values: np.ndarray) -> float:
        """
        Calculate percentile rank (0-100)

        Args:
            value: Raw factor value for single ticker
            values: Array of factor values across universe

        Returns:
            Percentile rank (0 = worst, 100 = best)
        """
        # Remove NaN values
        clean_values = values[~np.isnan(values)]

        if len(clean_values) < 2:
            return 50.0  # Default to median if insufficient data

        # Count values less than current value
        rank = np.sum(clean_values < value)

        # Calculate percentile (0-100)
        percentile = (rank / len(clean_values)) * 100

        return percentile

    def _calculate_confidence(
        self,
        data_length: int,
        null_ratio: float,
        additional_factors: Dict[str, float] = None
    ) -> float:
        """
        Calculate confidence score for factor quality

        Args:
            data_length: Number of data points used
            null_ratio: Ratio of NULL values in required columns (0-1)
            additional_factors: Optional dict of factor-specific confidence metrics

        Returns:
            Confidence score (0-1)
        """
        # Base confidence from data length
        length_confidence = min(1.0, data_length / self.lookback_days)

        # Penalize NULL values
        null_penalty = 1.0 - null_ratio

        # Combine factors (weighted average)
        base_confidence = length_confidence * 0.6 + null_penalty * 0.4

        # Apply additional factors if provided
        if additional_factors:
            # additional_factors is dict of {name: score} where score is 0-1
            # Take average of additional factor scores
            additional_score = sum(additional_factors.values()) / len(additional_factors)
            # Blend with base confidence
            base_confidence = base_confidence * 0.7 + additional_score * 0.3

        return max(0.0, min(1.0, base_confidence))

    def _calculate_null_ratio(self, data: pd.DataFrame, columns: List[str]) -> float:
        """
        Calculate ratio of NULL values across required columns

        Args:
            data: Input DataFrame
            columns: Columns to check

        Returns:
            NULL ratio (0-1)
        """
        total_cells = len(data) * len(columns)
        null_count = sum(data[col].isnull().sum() for col in columns if col in data.columns)

        return null_count / total_cells if total_cells > 0 else 0.0

    def save_results(
        self,
        results: List[FactorResult],
        db_manager,
        region: str = 'KR'
    ) -> int:
        """
        Save factor results to database (factor_scores table)

        Args:
            results: List of FactorResult objects
            db_manager: Database manager instance (db_manager_postgres.py)
            region: Region code for multi-regional support

        Returns:
            Number of records inserted/updated
        """
        if not results:
            logger.warning(f"{self.name}: No results to save")
            return 0

        # Prepare records for database insertion
        records = []
        for result in results:
            records.append({
                'ticker': result.ticker,
                'region': region,
                'date': result.calculation_date.date(),
                'factor_name': result.factor_name,
                'score': result.z_score,  # Store z-score as primary score
                'percentile': result.percentile
            })

        if not records:
            return 0

        # UPSERT query
        query = """
            INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region, date, factor_name)
            DO UPDATE SET
                score = EXCLUDED.score,
                percentile = EXCLUDED.percentile
        """

        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(query, [
                        (r['ticker'], r['region'], r['date'], r['factor_name'], r['score'], r['percentile'])
                        for r in records
                    ])
                    conn.commit()
                    logger.info(f"✅ {self.name}: Saved {len(records)} factor scores")
                    return len(records)
        except Exception as e:
            logger.error(f"❌ {self.name}: Failed to save results: {e}")
            return 0

    def load_fundamentals(
        self,
        db_manager,
        region: str = 'KR',
        min_market_cap: int = None
    ) -> pd.DataFrame:
        """
        Load fundamental data from database for factor calculation

        Args:
            db_manager: Database manager instance
            region: Region code to filter (None = all regions)
            min_market_cap: Minimum market cap filter

        Returns:
            DataFrame with ticker fundamentals
        """
        query = """
            SELECT
                tf.ticker,
                tf.region,
                tf.date,
                tf.per,
                tf.pbr,
                tf.market_cap,
                tf.dividend_yield,
                t.sector
            FROM ticker_fundamentals tf
            JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
            WHERE tf.region = %s
        """

        params = [region]

        if min_market_cap:
            query += " AND tf.market_cap >= %s"
            params.append(min_market_cap)

        query += " ORDER BY tf.date DESC"

        try:
            with db_manager.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)
                logger.info(f"✅ Loaded {len(df)} fundamental records for {region}")
                return df
        except Exception as e:
            logger.error(f"❌ Failed to load fundamentals: {e}")
            return pd.DataFrame()

    def __repr__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(name='{self.name}', category={self.category.value})"
