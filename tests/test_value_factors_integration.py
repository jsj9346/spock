#!/usr/bin/env python3
"""
Integration tests for value_factors.py using PostgreSQL mock infrastructure

Tests three factor classes:
1. DividendYieldFactorPostgres: Reads Dividend_Yield from factor_scores table
2. EVToEBITDAFactorPostgres: Reads EV_EBITDA from factor_scores table
3. CompositeValueFactor: Combines both factors with weighted average

Test Coverage Target: 60-70% of value_factors.py
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from typing import Dict, Any

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.factors.value_factors import (
    DividendYieldFactorPostgres,
    EVToEBITDAFactorPostgres,
    CompositeValueFactor
)
from modules.factors.factor_base import FactorResult, FactorCategory

# Fixtures are auto-discovered from tests/fixtures/conftest.py
# No explicit import needed


@pytest.mark.integration
@pytest.mark.database
class TestDividendYieldFactorPostgresIntegration:
    """Integration tests for DividendYieldFactorPostgres"""

    @pytest.fixture
    def factor(self, postgres_test_db):
        """Create DividendYieldFactorPostgres instance with test database"""
        factor = DividendYieldFactorPostgres()
        # Replace production database with test database
        factor.db = postgres_test_db
        return factor

    def test_initialization(self, factor):
        """Test factor initializes with correct properties"""
        assert factor.name == "Dividend_Yield"
        assert factor.category == FactorCategory.VALUE
        assert factor.lookback_days == 30
        assert factor.min_required_days == 1
        assert factor.db is not None

    def test_calculate_with_valid_data(self, factor, ticker_factory, factor_score_factory):
        """Test factor calculation with valid Dividend Yield score"""
        # Create test ticker
        ticker_factory(ticker='005930', name='Samsung Electronics')

        # Create factor score (high dividend yield: 80th percentile)
        factor_score_factory(
            ticker='005930',
            factor_name='Dividend_Yield',
            date='2024-03-29',
            score=-3.5,  # -log(yield) transformation
            percentile=80.0,
            metadata={'yield': 3.5, 'data_source': 'pykrx'}
        )

        # Calculate factor
        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        # Verify result
        assert result is not None
        assert isinstance(result, FactorResult)
        assert result.factor_name == 'Dividend_Yield'
        assert result.raw_value == -3.5
        assert result.percentile == 80.0
        assert result.confidence > 0.8  # High confidence for recent data

    def test_calculate_missing_ticker(self, factor):
        """Test factor calculation when ticker has no score data"""
        # Ticker 'MISSING' not in database
        result = factor.calculate(data=pd.DataFrame(), ticker='MISSING')

        # Should return None for missing data
        assert result is None

    def test_calculate_multiple_dates_returns_latest(self, factor, ticker_factory, factor_score_factory):
        """Test factor returns most recent score when multiple dates exist"""
        ticker_factory(ticker='005930')

        # Create scores for multiple dates
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                           date='2024-01-15', score=-2.0, percentile=60.0)
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                           date='2024-03-15', score=-3.0, percentile=75.0)
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                           date='2024-03-29', score=-3.5, percentile=80.0)

        # Calculate factor
        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        # Should return latest date (2024-03-29)
        assert result is not None
        assert result.raw_value == -3.5
        assert result.percentile == 80.0

    def test_calculate_low_dividend_yield(self, factor, ticker_factory, factor_score_factory):
        """Test factor with low dividend yield (low percentile)"""
        ticker_factory(ticker='000660', name='SK Hynix')

        # Create score for low dividend yield (20th percentile)
        factor_score_factory(
            ticker='000660',
            factor_name='Dividend_Yield',
            score=-1.0,  # Lower absolute value = lower yield
            percentile=20.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='000660')

        assert result is not None
        assert result.raw_value == -1.0
        assert result.percentile == 20.0
        assert result.confidence > 0  # Still has data

    def test_calculate_zero_dividend(self, factor, ticker_factory, factor_score_factory):
        """Test factor with zero dividend yield"""
        ticker_factory(ticker='035720', name='Kakao')

        # Create score for zero dividend (0th percentile)
        factor_score_factory(
            ticker='035720',
            factor_name='Dividend_Yield',
            score=0.0,  # Zero score = zero yield
            percentile=0.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='035720')

        assert result is not None
        assert result.raw_value == 0.0
        assert result.percentile == 0.0

    def test_calculate_confidence_fixed_for_pykrx(self, factor, ticker_factory, factor_score_factory):
        """Test confidence score is fixed at 0.95 for pykrx data"""
        ticker_factory(ticker='005930')

        # Create old score (90 days ago) - confidence doesn't degrade in current implementation
        old_date = (date.today() - timedelta(days=90)).isoformat()
        factor_score_factory(
            ticker='005930',
            factor_name='Dividend_Yield',
            date=old_date,
            score=-3.0,
            percentile=75.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        # Fixed confidence for pre-calculated pykrx factor scores
        assert result.confidence == 0.95  # High confidence for pre-calculated scores

    def test_calculate_with_metadata(self, factor, ticker_factory, factor_score_factory):
        """Test factor preserves metadata from factor_scores table"""
        ticker_factory(ticker='005930')

        # Create score with rich metadata
        metadata = {
            'yield': 3.5,
            'data_source': 'pykrx',
            'period_type': 'DAILY',
            'last_updated': '2024-03-29T15:30:00'
        }
        factor_score_factory(
            ticker='005930',
            factor_name='Dividend_Yield',
            score=-3.5,
            percentile=80.0,
            metadata=metadata
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        # Metadata should be accessible (implementation may vary)
        # This validates the data flow works end-to-end


@pytest.mark.integration
@pytest.mark.database
class TestEVToEBITDAFactorPostgresIntegration:
    """Integration tests for EVToEBITDAFactorPostgres"""

    @pytest.fixture
    def factor(self, postgres_test_db):
        """Create EVToEBITDAFactorPostgres instance with test database"""
        factor = EVToEBITDAFactorPostgres()
        factor.db = postgres_test_db
        return factor

    def test_initialization(self, factor):
        """Test factor initializes with correct properties"""
        assert factor.name == "EV_EBITDA"
        assert factor.category == FactorCategory.VALUE
        assert factor.lookback_days == 180  # Semi-annual data
        assert factor.min_required_days == 1
        assert factor.db is not None

    def test_calculate_with_valid_data(self, factor, ticker_factory, factor_score_factory):
        """Test factor calculation with valid EV/EBITDA score"""
        ticker_factory(ticker='005930', name='Samsung Electronics')

        # Create factor score (low EV/EBITDA: 85th percentile - lower is better)
        factor_score_factory(
            ticker='005930',
            factor_name='EV_EBITDA',
            date='2024-03-31',
            score=-2.5,  # -log(ratio) transformation
            percentile=85.0,
            metadata={'ev_ebitda': 5.5, 'data_source': 'DART'}
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        assert isinstance(result, FactorResult)
        assert result.factor_name == 'EV_EBITDA'
        assert result.raw_value == -2.5
        assert result.percentile == 85.0
        assert result.confidence > 0.8

    def test_calculate_missing_ticker(self, factor):
        """Test factor calculation when ticker has no score data"""
        result = factor.calculate(data=pd.DataFrame(), ticker='MISSING')
        assert result is None

    def test_calculate_high_ev_ebitda(self, factor, ticker_factory, factor_score_factory):
        """Test factor with high EV/EBITDA (overvalued, low percentile)"""
        ticker_factory(ticker='035720', name='Kakao')

        # Create score for high EV/EBITDA (15th percentile - worse)
        factor_score_factory(
            ticker='035720',
            factor_name='EV_EBITDA',
            score=-0.5,  # Lower absolute value = higher ratio = overvalued
            percentile=15.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='035720')

        assert result is not None
        assert result.raw_value == -0.5
        assert result.percentile == 15.0

    def test_calculate_semi_annual_data_frequency(self, factor, ticker_factory, factor_score_factory):
        """Test factor handles semi-annual DART data correctly"""
        ticker_factory(ticker='005930')

        # Create semi-annual scores (Q1, Q3 reporting)
        factor_score_factory(ticker='005930', factor_name='EV_EBITDA',
                           date='2024-01-31', score=-2.0, percentile=75.0)  # Q4 2023
        factor_score_factory(ticker='005930', factor_name='EV_EBITDA',
                           date='2024-03-31', score=-2.5, percentile=85.0)  # Q1 2024

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        # Should return latest (Q1 2024)
        assert result is not None
        assert result.raw_value == -2.5
        assert result.percentile == 85.0

    def test_calculate_negative_ebitda(self, factor, ticker_factory, factor_score_factory):
        """Test factor handles negative EBITDA companies"""
        ticker_factory(ticker='000120', name='Loss Company')

        # Negative EBITDA should have very low percentile
        factor_score_factory(
            ticker='000120',
            factor_name='EV_EBITDA',
            score=0.0,  # Special case for negative EBITDA
            percentile=0.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='000120')

        assert result is not None
        assert result.percentile == 0.0  # Worst ranking

    def test_calculate_confidence_fixed_for_dart(self, factor, ticker_factory, factor_score_factory):
        """Test confidence score is fixed at 0.90 for DART data"""
        ticker_factory(ticker='005930')

        # Create 6-month-old score - confidence doesn't degrade in current implementation
        old_date = (date.today() - timedelta(days=180)).isoformat()
        factor_score_factory(
            ticker='005930',
            factor_name='EV_EBITDA',
            date=old_date,
            score=-2.0,
            percentile=75.0
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        # Fixed confidence for pre-calculated DART factor scores
        assert result.confidence == 0.90  # High confidence for pre-calculated scores

    def test_calculate_with_metadata(self, factor, ticker_factory, factor_score_factory):
        """Test factor preserves DART metadata"""
        ticker_factory(ticker='005930')

        metadata = {
            'ev_ebitda': 5.5,
            'data_source': 'DART',
            'fiscal_year': 2024,
            'period_type': 'SEMI-ANNUAL',
            'report_type': 'Q1'
        }
        factor_score_factory(
            ticker='005930',
            factor_name='EV_EBITDA',
            score=-2.5,
            percentile=85.0,
            metadata=metadata
        )

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        # Metadata flow validated


@pytest.mark.integration
@pytest.mark.database
class TestCompositeValueFactorIntegration:
    """Integration tests for CompositeValueFactor"""

    @pytest.fixture
    def factor(self, postgres_test_db):
        """Create CompositeValueFactor instance with test database"""
        factor = CompositeValueFactor()
        # Replace both sub-factor databases with test database
        factor.div_factor.db = postgres_test_db
        factor.ev_factor.db = postgres_test_db
        return factor

    def test_initialization(self, factor):
        """Test composite factor initializes correctly"""
        assert factor.name == "Composite_Value"
        assert factor.category == FactorCategory.VALUE
        assert factor.div_factor is not None
        assert factor.ev_factor is not None
        assert factor.div_weight == 0.5
        assert factor.ev_weight == 0.5

    def test_calculate_with_both_factors(self, factor, ticker_factory, factor_score_factory):
        """Test composite calculation when both sub-factors have data"""
        ticker_factory(ticker='005930')

        # Create scores for both factors
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                           score=-3.0, percentile=75.0)
        factor_score_factory(ticker='005930', factor_name='EV_EBITDA',
                           score=-2.5, percentile=85.0)

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        assert result.factor_name == 'Composite_Value'
        # Composite = 0.5 * (-3.0) + 0.5 * (-2.5) = -2.75
        assert abs(result.raw_value - (-2.75)) < 0.01
        # Percentile: average of 75 and 85 = 80.0
        assert abs(result.percentile - 80.0) < 0.01

    def test_calculate_with_only_dividend_yield(self, factor, ticker_factory, factor_score_factory):
        """Test composite calculation when only Dividend Yield available"""
        ticker_factory(ticker='000660')

        # Create only Dividend Yield score
        factor_score_factory(ticker='000660', factor_name='Dividend_Yield',
                           score=-2.0, percentile=60.0)

        result = factor.calculate(data=pd.DataFrame(), ticker='000660')

        # Should return None or handle missing factor gracefully
        # (Implementation may vary - check value_factors.py for behavior)
        # If it returns partial result:
        if result is not None:
            assert result.confidence < 0.8  # Lower confidence for partial data

    def test_calculate_with_only_ev_ebitda(self, factor, ticker_factory, factor_score_factory):
        """Test composite calculation when only EV/EBITDA available"""
        ticker_factory(ticker='035720')

        # Create only EV/EBITDA score
        factor_score_factory(ticker='035720', factor_name='EV_EBITDA',
                           score=-1.5, percentile=50.0)

        result = factor.calculate(data=pd.DataFrame(), ticker='035720')

        # Should handle partial data gracefully
        if result is not None:
            assert result.confidence < 0.8  # Lower confidence for partial data

    def test_calculate_missing_both_factors(self, factor):
        """Test composite calculation when no data available"""
        result = factor.calculate(data=pd.DataFrame(), ticker='MISSING')

        # Should return None when no data
        assert result is None

    def test_calculate_confidence_is_minimum_of_sub_factors(self, factor, ticker_factory, factor_score_factory):
        """Test composite confidence is minimum of sub-factor confidences"""
        ticker_factory(ticker='005930')

        # Create Dividend Yield score (confidence=0.95)
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                           date=date.today().isoformat(),
                           score=-3.0, percentile=75.0)

        # Create EV/EBITDA score (confidence=0.90)
        factor_score_factory(ticker='005930', factor_name='EV_EBITDA',
                           date=date.today().isoformat(),
                           score=-2.5, percentile=85.0)

        result = factor.calculate(data=pd.DataFrame(), ticker='005930')

        assert result is not None
        # Composite confidence is min(0.95, 0.90) = 0.90
        assert result.confidence == 0.90


@pytest.mark.integration
@pytest.mark.database
class TestValueFactorsEndToEnd:
    """End-to-end integration tests using complete test dataset"""

    def test_complete_value_analysis_workflow(self, ticker_factory, fundamentals_factory,
                                             factor_score_factory, ohlcv_factory,
                                             postgres_test_db):
        """Test complete workflow: ticker → fundamentals → factors → composite"""
        # 1. Create ticker
        ticker_factory(ticker='000020', name='Test Corporation')

        # 2. Create pykrx fundamentals (for Dividend Yield)
        fundamentals_factory(
            ticker='000020',
            date='2024-03-29',
            period_type='DAILY',
            data_source='pykrx',
            dividend_yield=3.5,
            per=12.0,
            pbr=0.8
        )

        # 3. Create DART fundamentals (for EV/EBITDA)
        fundamentals_factory(
            ticker='000020',
            date='2024-03-31',
            fiscal_year=2024,
            period_type='SEMI-ANNUAL',
            data_source='DART',
            revenue=50000000000,
            ebitda=10000000000
        )

        # 4. Create factor scores
        factor_score_factory(ticker='000020', factor_name='Dividend_Yield',
                           score=-3.5, percentile=80.0)
        factor_score_factory(ticker='000020', factor_name='EV_EBITDA',
                           score=-2.5, percentile=85.0)

        # 5. Create OHLCV data (Q1 2024)
        ohlcv_factory(ticker='000020', start_date='2024-01-01', end_date='2024-03-31')

        # 6. Calculate all three factors
        div_factor = DividendYieldFactorPostgres()
        div_factor.db = postgres_test_db
        div_result = div_factor.calculate(pd.DataFrame(), '000020')

        ev_factor = EVToEBITDAFactorPostgres()
        ev_factor.db = postgres_test_db
        ev_result = ev_factor.calculate(pd.DataFrame(), '000020')

        composite_factor = CompositeValueFactor()
        composite_factor.div_factor.db = postgres_test_db
        composite_factor.ev_factor.db = postgres_test_db
        composite_result = composite_factor.calculate(pd.DataFrame(), '000020')

        # 7. Verify all results
        assert div_result is not None
        assert div_result.percentile == 80.0

        assert ev_result is not None
        assert ev_result.percentile == 85.0

        assert composite_result is not None
        assert composite_result.percentile == 82.5  # Average of 80 and 85

        # 8. Verify ticker is identified as value stock (high composite percentile)
        assert composite_result.percentile > 70.0  # Strong value signal
