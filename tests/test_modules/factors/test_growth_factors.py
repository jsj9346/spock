#!/usr/bin/env python3
"""
Test Growth Factors - PostgreSQL-based Tests

Tests for 3 Growth factors:
- RevenueGrowthFactor: YOY revenue growth rate
- OperatingProfitGrowthFactor: YOY operating profit growth rate
- NetIncomeGrowthFactor: YOY net income growth rate

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/test_modules/factors/test_growth_factors.py -v
"""

import pytest
from unittest.mock import Mock, patch
from datetime import date

from modules.factors.growth_factors import (
    RevenueGrowthFactor,
    OperatingProfitGrowthFactor,
    NetIncomeGrowthFactor
)
from modules.factors.factor_base import FactorCategory


# ============================================================================
# RevenueGrowthFactor Tests
# ============================================================================

class TestRevenueGrowthFactor:
    """Test RevenueGrowthFactor implementation."""

    def test_initialization(self):
        """Test RevenueGrowthFactor initialization."""
        # Given / When
        factor = RevenueGrowthFactor()

        # Then
        assert factor.name == "Revenue_Growth_YOY"
        assert factor.category == FactorCategory.GROWTH
        assert factor.lookback_days == 730  # 2 years for YOY
        assert factor.min_required_days == 1

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_success(self, mock_db_manager):
        """Test successful revenue growth calculation."""
        # Given: Mock database results
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (120_000_000, 2024, 100_000_000, 2023)  # current_revenue, current_year, previous_revenue, previous_year
        ]
        mock_db_manager.return_value = mock_db

        factor = RevenueGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == 'Revenue_Growth_YOY'
        assert result.raw_value == pytest.approx(20.0, abs=0.1)  # (120M - 100M) / 100M * 100
        assert result.confidence == 0.9
        assert result.metadata['revenue_growth_yoy'] == 20.0
        assert result.metadata['current_year'] == 2024
        assert result.metadata['previous_year'] == 2023
        assert result.metadata['current_revenue'] == 120_000_000
        assert result.metadata['previous_revenue'] == 100_000_000

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """Test calculation when no YOY data available."""
        # Given: No database results
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = RevenueGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='999999', region='KR')

        # Then
        assert result is None


# ============================================================================
# OperatingProfitGrowthFactor Tests
# ============================================================================

class TestOperatingProfitGrowthFactor:
    """Test OperatingProfitGrowthFactor implementation."""

    def test_initialization(self):
        """Test OperatingProfitGrowthFactor initialization."""
        # Given / When
        factor = OperatingProfitGrowthFactor()

        # Then
        assert factor.name == "Operating_Profit_Growth_YOY"
        assert factor.category == FactorCategory.GROWTH
        assert factor.lookback_days == 730
        assert factor.min_required_days == 1

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_success_positive(self, mock_db_manager):
        """Test successful operating profit growth calculation (positive)."""
        # Given: Mock positive profit growth
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (15_000_000, 2024, 12_000_000, 2023)  # current_op, current_year, previous_op, previous_year
        ]
        mock_db_manager.return_value = mock_db

        factor = OperatingProfitGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.raw_value == pytest.approx(25.0, abs=0.1)  # (15M - 12M) / 12M * 100
        assert result.confidence == 0.85
        assert result.metadata['op_growth_yoy'] == 25.0

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_loss_to_profit(self, mock_db_manager):
        """Test calculation when turning from loss to profit."""
        # Given: Loss to profit turnaround
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (5_000_000, 2024, -10_000_000, 2023)  # Profit after loss
        ]
        mock_db_manager.return_value = mock_db

        factor = OperatingProfitGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then
        assert result is not None
        assert result.raw_value == 200.0  # Capped at 200% for loss-to-profit
        assert result.metadata['op_growth_yoy'] == 200.0
        assert result.metadata['current_op'] == 5_000_000
        assert result.metadata['previous_op'] == -10_000_000

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_both_negative(self, mock_db_manager):
        """Test calculation when both years are negative (losses)."""
        # Given: Both years in loss
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (-5_000_000, 2024, -10_000_000, 2023)  # Smaller loss
        ]
        mock_db_manager.return_value = mock_db

        factor = OperatingProfitGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then
        assert result is not None
        # (-5M - (-10M)) / abs(-10M) * 100 = 5M / 10M * 100 = 50%
        assert result.raw_value == pytest.approx(50.0, abs=0.1)


# ============================================================================
# NetIncomeGrowthFactor Tests
# ============================================================================

class TestNetIncomeGrowthFactor:
    """Test NetIncomeGrowthFactor implementation."""

    def test_initialization(self):
        """Test NetIncomeGrowthFactor initialization."""
        # Given / When
        factor = NetIncomeGrowthFactor()

        # Then
        assert factor.name == "Net_Income_Growth_YOY"
        assert factor.category == FactorCategory.GROWTH
        assert factor.lookback_days == 730
        assert factor.min_required_days == 1

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_success(self, mock_db_manager):
        """Test successful net income growth calculation."""
        # Given: Mock net income growth
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (8_000_000, 2024, 6_000_000, 2023)  # current_ni, current_year, previous_ni, previous_year
        ]
        mock_db_manager.return_value = mock_db

        factor = NetIncomeGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.raw_value == pytest.approx(33.33, abs=0.1)  # (8M - 6M) / 6M * 100
        assert result.confidence == 0.85
        assert result.metadata['ni_growth_yoy'] == pytest.approx(33.33, abs=0.1)
        assert result.metadata['current_ni'] == 8_000_000
        assert result.metadata['previous_ni'] == 6_000_000

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_loss_to_profit(self, mock_db_manager):
        """Test calculation when turning from loss to profit."""
        # Given: Loss to profit turnaround
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (3_000_000, 2024, -8_000_000, 2023)  # Profit after loss
        ]
        mock_db_manager.return_value = mock_db

        factor = NetIncomeGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then
        assert result is not None
        assert result.raw_value == 200.0  # Capped at 200%
        assert result.metadata['ni_growth_yoy'] == 200.0

    @patch('modules.factors.growth_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """Test calculation when no YOY data available."""
        # Given: No database results
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = NetIncomeGrowthFactor()

        # When
        result = factor.calculate(data=None, ticker='999999', region='KR')

        # Then
        assert result is None
