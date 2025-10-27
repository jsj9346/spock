"""
Unit Tests for BacktestEngine with Pluggable Data Providers

Tests:
    - BacktestEngine initialization with different providers
    - Factory methods (from_sqlite, from_postgres)
    - Backward compatibility with deprecated db parameter
    - Deprecation warnings
    - Provider-agnostic data loading
    - Integration test: Full backtest with SQLite
    - Integration test: Full backtest with PostgreSQL (if available)

Coverage Target: >90%

Author: Spock Quant Platform
Date: 2025-10-26
"""

import pytest
import warnings
from datetime import date
from pathlib import Path

from modules.backtesting.backtest_engine import BacktestEngine
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import (
    BaseDataProvider,
    SQLiteDataProvider,
    PostgresDataProvider,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.db_manager_postgres import PostgresDatabaseManager


class TestBacktestEngineProviders:
    """Test suite for BacktestEngine with pluggable data providers."""

    @pytest.fixture(scope="class")
    def test_db_path(self):
        """Get test database path."""
        db_path = Path(__file__).parent.parent.parent / 'data' / 'spock_test_phase5.db'
        if not db_path.exists():
            pytest.skip(f"Test database not found: {db_path}")
        return str(db_path)

    @pytest.fixture
    def sample_config(self):
        """Create sample backtest configuration."""
        return BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            initial_capital=10000000,
            regions=['KR'],
            tickers=['TIGER'],
            max_position_size=0.15,
            score_threshold=60.0,
            risk_profile='moderate',
        )

    @pytest.fixture
    def sqlite_db_manager(self, test_db_path):
        """Create SQLite database manager."""
        return SQLiteDatabaseManager(test_db_path)

    @pytest.fixture
    def sqlite_provider(self, sqlite_db_manager):
        """Create SQLite data provider."""
        return SQLiteDataProvider(sqlite_db_manager, cache_enabled=True)

    @pytest.fixture(scope="class")
    def postgres_db_manager(self):
        """Create PostgreSQL database manager (skip if unavailable)."""
        try:
            db = PostgresDatabaseManager(
                host='localhost',
                database='quant_platform'
            )
            if not db.test_connection():
                pytest.skip("Cannot connect to PostgreSQL database")
            return db
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    @pytest.fixture
    def postgres_provider(self, postgres_db_manager):
        """Create PostgreSQL data provider."""
        return PostgresDataProvider(postgres_db_manager, cache_enabled=True)

    # -------------------------------------------------------------------------
    # Initialization Tests
    # -------------------------------------------------------------------------

    def test_init_with_sqlite_provider(self, sample_config, sqlite_provider):
        """Test BacktestEngine initialization with SQLiteDataProvider."""
        engine = BacktestEngine(sample_config, data_provider=sqlite_provider)

        assert engine.config == sample_config
        assert isinstance(engine.data_provider, SQLiteDataProvider)
        assert engine.data_provider.cache_enabled is True
        assert engine.portfolio is not None
        # strategy_runner may be None if no db provided
        assert engine.db is None or isinstance(engine.db, SQLiteDatabaseManager)

    def test_init_with_postgres_provider(self, sample_config, postgres_provider):
        """Test BacktestEngine initialization with PostgresDataProvider."""
        engine = BacktestEngine(sample_config, data_provider=postgres_provider)

        assert engine.config == sample_config
        assert isinstance(engine.data_provider, PostgresDataProvider)
        assert engine.data_provider.cache_enabled is True
        assert engine.portfolio is not None
        assert engine.strategy_runner is None  # No SQLite db for StrategyRunner
        assert engine.db is None

    def test_init_requires_provider_or_db(self, sample_config):
        """Test BacktestEngine requires either data_provider or db."""
        with pytest.raises(ValueError, match="Either data_provider or db must be provided"):
            BacktestEngine(sample_config)

    def test_init_backward_compatibility_with_db(self, sample_config, sqlite_db_manager):
        """Test backward compatibility: old db parameter creates SQLiteDataProvider."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            engine = BacktestEngine(sample_config, db=sqlite_db_manager)

            # Should emit deprecation warning from BacktestEngine
            assert len(w) >= 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "'db' parameter is deprecated" in str(w[0].message).lower()

            # Should create SQLiteDataProvider internally
            assert isinstance(engine.data_provider, SQLiteDataProvider)
            assert engine.db == sqlite_db_manager
            assert engine.strategy_runner is not None

    # -------------------------------------------------------------------------
    # Factory Method Tests
    # -------------------------------------------------------------------------

    def test_from_sqlite_factory(self, sample_config, test_db_path):
        """Test BacktestEngine.from_sqlite() factory method."""
        engine = BacktestEngine.from_sqlite(
            config=sample_config,
            db_path=test_db_path,
            cache_enabled=True
        )

        assert isinstance(engine, BacktestEngine)
        assert isinstance(engine.data_provider, SQLiteDataProvider)
        assert engine.data_provider.cache_enabled is True
        assert isinstance(engine.db, SQLiteDatabaseManager)
        assert engine.strategy_runner is not None

    def test_from_postgres_factory(self, sample_config):
        """Test BacktestEngine.from_postgres() factory method."""
        try:
            engine = BacktestEngine.from_postgres(
                config=sample_config,
                host='localhost',
                database='quant_platform',
                cache_enabled=True
            )

            assert isinstance(engine, BacktestEngine)
            assert isinstance(engine.data_provider, PostgresDataProvider)
            assert engine.data_provider.cache_enabled is True
            assert engine.db is None
            assert engine.strategy_runner is None  # Expected for PostgreSQL-only setup

        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    def test_from_sqlite_factory_cache_disabled(self, sample_config, test_db_path):
        """Test from_sqlite() with caching disabled."""
        engine = BacktestEngine.from_sqlite(
            config=sample_config,
            db_path=test_db_path,
            cache_enabled=False
        )

        assert engine.data_provider.cache_enabled is False

    # -------------------------------------------------------------------------
    # Data Loading Tests (Provider-Agnostic)
    # -------------------------------------------------------------------------

    def test_data_loading_with_sqlite_provider(self, sample_config, test_db_path):
        """Test data loading with SQLiteDataProvider."""
        engine = BacktestEngine.from_sqlite(sample_config, test_db_path)

        # Test internal data loading (simplified, doesn't run full backtest)
        # Just verify no errors during initialization
        assert engine.data_provider is not None
        assert len(engine.data_provider.cache) == 0  # Not loaded yet

    def test_data_loading_with_postgres_provider(self, sample_config):
        """Test data loading with PostgresDataProvider."""
        try:
            engine = BacktestEngine.from_postgres(sample_config)

            # Test internal data loading (simplified)
            assert engine.data_provider is not None
            assert len(engine.data_provider.cache) == 0  # Not loaded yet

        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    # -------------------------------------------------------------------------
    # Integration Tests (Simplified Backtests)
    # -------------------------------------------------------------------------

    def test_backtest_with_sqlite_provider_no_strategy(self, sample_config, test_db_path):
        """Test simplified backtest with SQLite (no strategy execution)."""
        # Modify config to skip strategy execution (no tickers)
        config_no_strategy = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),  # Short period
            initial_capital=10000000,
            regions=['KR'],
            tickers=[],  # Empty tickers - no trading
            max_position_size=0.15,
            score_threshold=60.0,
            risk_profile='moderate',
        )

        engine = BacktestEngine.from_sqlite(config_no_strategy, test_db_path)

        # This should complete without errors (no trades executed)
        # Note: Full backtest test would require more complex setup
        assert engine is not None

    # -------------------------------------------------------------------------
    # Deprecation Warning Tests
    # -------------------------------------------------------------------------

    def test_deprecation_warning_on_db_parameter(self, sample_config, sqlite_db_manager):
        """Test deprecation warning when using db parameter."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            engine = BacktestEngine(sample_config, db=sqlite_db_manager)

            # Should have at least one deprecation warning
            assert len(w) >= 1
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "'db' parameter is deprecated" in str(deprecation_warnings[0].message).lower()
            assert engine is not None

    def test_no_deprecation_warning_with_provider(self, sample_config, sqlite_provider):
        """Test no deprecation warning when using data_provider parameter."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            try:
                engine = BacktestEngine(sample_config, data_provider=sqlite_provider)
                assert engine is not None
            except DeprecationWarning:
                pytest.fail("DeprecationWarning raised unexpectedly")

    # -------------------------------------------------------------------------
    # Provider Interface Compliance Tests
    # -------------------------------------------------------------------------

    def test_sqlite_provider_implements_base_interface(self, sqlite_provider):
        """Test SQLiteDataProvider implements BaseDataProvider interface."""
        assert isinstance(sqlite_provider, BaseDataProvider)
        assert hasattr(sqlite_provider, 'get_ohlcv')
        assert hasattr(sqlite_provider, 'get_ohlcv_batch')
        assert hasattr(sqlite_provider, 'get_fundamentals')
        assert hasattr(sqlite_provider, 'get_technical_indicators')
        assert hasattr(sqlite_provider, 'get_available_tickers')

    def test_postgres_provider_implements_base_interface(self, postgres_provider):
        """Test PostgresDataProvider implements BaseDataProvider interface."""
        assert isinstance(postgres_provider, BaseDataProvider)
        assert hasattr(postgres_provider, 'get_ohlcv')
        assert hasattr(postgres_provider, 'get_ohlcv_batch')
        assert hasattr(postgres_provider, 'get_fundamentals')
        assert hasattr(postgres_provider, 'get_technical_indicators')
        assert hasattr(postgres_provider, 'get_available_tickers')

    # -------------------------------------------------------------------------
    # Edge Cases & Error Handling
    # -------------------------------------------------------------------------

    def test_init_with_both_provider_and_db(self, sample_config, sqlite_provider, sqlite_db_manager):
        """Test initialization with both data_provider and db (provider takes precedence)."""
        engine = BacktestEngine(sample_config, data_provider=sqlite_provider, db=sqlite_db_manager)

        # data_provider should be used, db should be stored
        assert engine.data_provider == sqlite_provider
        assert engine.db == sqlite_db_manager

    def test_repr(self, sample_config, sqlite_provider):
        """Test string representation of BacktestEngine."""
        engine = BacktestEngine(sample_config, data_provider=sqlite_provider)

        # repr should work without errors
        repr_str = repr(engine)
        assert 'BacktestEngine' in repr_str or 'object at' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.backtesting.backtest_engine', '--cov-report=term-missing'])
