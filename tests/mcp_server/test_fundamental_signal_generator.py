#!/usr/bin/env python3
"""
Unit Tests for FundamentalSignalGenerator

Tests fundamental screening logic, annual rebalancing, and signal generation.

Author: Spock MCP Server
Date: 2025-11-02
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.strategies.signal_generators import (
    FundamentalSignalGenerator,
    SignalGeneratorFactory
)


class TestFundamentalSignalGenerator:
    """Test suite for FundamentalSignalGenerator"""

    @pytest.fixture
    def sample_params(self):
        """Default strategy parameters"""
        return {
            'roe_min': 15.0,
            'debt_to_equity_max': 100.0,
            'net_income_growth_min': 10.0,
            'revenue_growth_min': 10.0,
            'top_n': 10,
            'rebalance_freq_days': 252,
            'region': 'KR'
        }

    @pytest.fixture
    def sample_close_prices(self):
        """Sample close price series"""
        dates = pd.date_range(start='2023-01-01', periods=500, freq='D')
        prices = pd.Series(
            data=np.random.uniform(10000, 15000, size=len(dates)),
            index=dates,
            name='005930'
        )
        return prices

    def test_initialization(self, sample_params):
        """Test FundamentalSignalGenerator initialization"""
        generator = FundamentalSignalGenerator(sample_params)

        assert generator.parameters == sample_params
        assert generator._last_rebalance_date is None
        assert len(generator._current_holdings) == 0

    def test_factory_registration(self):
        """Test that fundamental_quality_growth is registered in factory"""
        strategies = SignalGeneratorFactory.list_strategies()

        assert 'fundamental_quality_growth' in strategies
        assert 'momentum' in strategies
        assert 'value' in strategies
        assert 'momentum_value' in strategies

    def test_factory_create(self, sample_params):
        """Test creating generator through factory"""
        generator = SignalGeneratorFactory.create(
            'fundamental_quality_growth',
            sample_params
        )

        assert isinstance(generator, FundamentalSignalGenerator)
        assert generator.parameters == sample_params

    def test_should_rebalance_initial(self, sample_params, sample_close_prices):
        """Test rebalancing on first call"""
        generator = FundamentalSignalGenerator(sample_params)
        current_date = sample_close_prices.index[-1]

        should_rebalance = generator._should_rebalance(current_date, 252)

        assert should_rebalance is True

    def test_should_rebalance_too_early(self, sample_params, sample_close_prices):
        """Test no rebalancing before frequency threshold"""
        generator = FundamentalSignalGenerator(sample_params)
        generator._last_rebalance_date = sample_close_prices.index[-1]

        # Check 100 days later (less than 252)
        current_date = sample_close_prices.index[-1] + timedelta(days=100)

        should_rebalance = generator._should_rebalance(current_date, 252)

        assert should_rebalance is False

    def test_should_rebalance_after_frequency(self, sample_params, sample_close_prices):
        """Test rebalancing after frequency threshold"""
        generator = FundamentalSignalGenerator(sample_params)
        generator._last_rebalance_date = sample_close_prices.index[0]

        # Check 300 days later (more than 252)
        current_date = sample_close_prices.index[-1]

        should_rebalance = generator._should_rebalance(current_date, 252)

        assert should_rebalance is True

    @patch('psycopg2.connect')
    def test_screen_ticker_passes(self, mock_connect, sample_params):
        """Test ticker that passes all screening criteria"""
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930',  # ticker
            2023,      # fiscal_year
            20.0,      # ROE (passes: >= 15%)
            80.0,      # Debt-to-Equity (passes: <= 100%)
            15.0,      # Net Income Growth (passes: >= 10%)
            12.0       # Revenue Growth (passes: >= 10%)
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='005930',
            as_of_date=pd.Timestamp('2024-01-01'),
            params=sample_params
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('psycopg2.connect')
    def test_screen_ticker_fails_roe(self, mock_connect, sample_params):
        """Test ticker that fails ROE criterion"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '000660',
            2023,
            10.0,  # ROE (fails: < 15%)
            80.0,  # Debt-to-Equity (passes)
            15.0,  # Net Income Growth (passes)
            12.0   # Revenue Growth (passes)
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='000660',
            as_of_date=pd.Timestamp('2024-01-01'),
            params=sample_params
        )

        assert result is False

    @patch('psycopg2.connect')
    def test_screen_ticker_fails_debt(self, mock_connect, sample_params):
        """Test ticker that fails debt-to-equity criterion"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '035420',
            2023,
            20.0,  # ROE (passes)
            150.0,  # Debt-to-Equity (fails: > 100%)
            15.0,  # Net Income Growth (passes)
            12.0   # Revenue Growth (passes)
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='035420',
            as_of_date=pd.Timestamp('2024-01-01'),
            params=sample_params
        )

        assert result is False

    @patch('psycopg2.connect')
    def test_screen_ticker_no_data(self, mock_connect, sample_params):
        """Test ticker with no fundamental data"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='999999',
            as_of_date=pd.Timestamp('2024-01-01'),
            params=sample_params
        )

        assert result is False

    @patch('psycopg2.connect')
    def test_generate_signals_entry(self, mock_connect, sample_params, sample_close_prices):
        """Test entry signal generation for ticker that passes screening"""
        # Mock database to return passing fundamental data
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2023, 20.0, 80.0, 15.0, 12.0
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        entries, exits = generator.generate_signals(sample_close_prices)

        # First rebalance should generate entry signal
        assert entries.sum() > 0
        assert exits.sum() == 0
        assert '005930' in generator._current_holdings

    @patch('psycopg2.connect')
    def test_generate_signals_no_entry_on_fail(self, mock_connect, sample_params, sample_close_prices):
        """Test no entry signal for ticker that fails screening"""
        # Mock database to return failing fundamental data (low ROE)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2023, 10.0, 80.0, 15.0, 12.0
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        entries, exits = generator.generate_signals(sample_close_prices)

        # Should not generate entry signal
        assert entries.sum() == 0
        assert exits.sum() == 0
        assert len(generator._current_holdings) == 0

    @patch('psycopg2.connect')
    def test_generate_signals_exit(self, mock_connect, sample_params, sample_close_prices):
        """Test exit signal generation when ticker no longer passes screening"""
        # First call: ticker passes (generates entry)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2023, 20.0, 80.0, 15.0, 12.0
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        generator = FundamentalSignalGenerator(sample_params)
        entries1, exits1 = generator.generate_signals(sample_close_prices)

        assert entries1.sum() > 0
        assert '005930' in generator._current_holdings

        # Second call (300 days later): ticker fails (generates exit)
        future_prices = sample_close_prices.copy()
        future_prices.index = future_prices.index + timedelta(days=300)

        mock_cursor.fetchone.return_value = (
            '005930', 2023, 10.0, 80.0, 15.0, 12.0  # Low ROE
        )

        entries2, exits2 = generator.generate_signals(future_prices)

        assert exits2.sum() > 0
        assert '005930' not in generator._current_holdings

    @patch('psycopg2.connect')
    def test_flexible_mode_with_null_growth(self, mock_connect, sample_params, sample_close_prices):
        """Test flexible mode passes with NULL YOY growth"""
        # Mock database to return fundamentals with NULL growth
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2025, 20.0, 80.0, None, None  # YOY growth = NULL
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Flexible mode (default): require_growth=False
        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='005930',
            as_of_date=pd.Timestamp('2025-01-01'),
            params=sample_params
        )

        # Should pass (ROE + Debt OK, growth NULL is acceptable)
        assert result is True

    @patch('psycopg2.connect')
    def test_strict_mode_requires_all(self, mock_connect, sample_params):
        """Test strict mode fails with NULL YOY growth"""
        # Mock database to return fundamentals with NULL growth
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2025, 20.0, 80.0, None, None  # YOY growth = NULL
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Strict mode: require_growth=True
        strict_params = {**sample_params, 'require_growth': True}
        generator = FundamentalSignalGenerator(strict_params)
        result = generator._screen_ticker(
            ticker='005930',
            as_of_date=pd.Timestamp('2025-01-01'),
            params=strict_params
        )

        # Should fail (YOY growth is NULL and required)
        assert result is False

    @patch('psycopg2.connect')
    def test_flexible_mode_bonus_growth(self, mock_connect, sample_params):
        """Test flexible mode with valid YOY growth (bonus)"""
        # Mock database to return full fundamentals
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2025, 20.0, 80.0, 15.0, 12.0  # All criteria met
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Flexible mode
        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='005930',
            as_of_date=pd.Timestamp('2025-01-01'),
            params=sample_params
        )

        # Should pass (all criteria met)
        assert result is True

    @patch('psycopg2.connect')
    def test_flexible_mode_low_growth_fails(self, mock_connect, sample_params):
        """Test flexible mode fails when YOY growth is present but too low"""
        # Mock database to return low growth
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            '005930', 2025, 20.0, 80.0, 5.0, 5.0  # Growth present but < threshold
        )

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Flexible mode
        generator = FundamentalSignalGenerator(sample_params)
        result = generator._screen_ticker(
            ticker='005930',
            as_of_date=pd.Timestamp('2025-01-01'),
            params=sample_params
        )

        # Should fail (growth present but doesn't meet threshold)
        assert result is False

    def test_callable_interface(self, sample_params, sample_close_prices):
        """Test that generator is callable (vectorbt compatibility)"""
        generator = FundamentalSignalGenerator(sample_params)

        # Should be callable
        assert callable(generator)

        # Test calling with mock (to avoid DB dependency)
        with patch.object(generator, '_screen_ticker', return_value=False):
            entries, exits = generator(sample_close_prices)

            assert isinstance(entries, pd.Series)
            assert isinstance(exits, pd.Series)
            assert len(entries) == len(sample_close_prices)
            assert len(exits) == len(sample_close_prices)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
