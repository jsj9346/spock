"""
Backtest Engine

Purpose: Main orchestrator for event-driven backtesting.

Key Features:
  - Event-driven loop (day-by-day iteration)
  - Coordinate data provider, portfolio simulator, strategy runner
  - Handle multi-region backtests
  - Manage start/end date boundaries
  - Generate backtest results

Design Philosophy:
  - Event-driven architecture prevents look-ahead bias
  - Clean separation of concerns (data, portfolio, strategy)
  - Extensible for different strategies
"""

from datetime import date, timedelta
from typing import List, Dict, Optional
import logging
import time
import warnings
import pandas as pd

from modules.db_manager_sqlite import SQLiteDatabaseManager
from .backtest_config import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    PatternMetrics,
)
from .data_providers.base_data_provider import BaseDataProvider
from .historical_data_provider import HistoricalDataProvider
from .portfolio_simulator import PortfolioSimulator
from .strategy_runner import StrategyRunner, run_generate_buy_signals
from .performance_analyzer import PerformanceAnalyzer


logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Main orchestrator for backtesting with pluggable data providers.

    Attributes:
        config: Backtest configuration
        data_provider: Pluggable data provider (BaseDataProvider interface)
        portfolio: Portfolio simulator
        strategy_runner: Strategy execution engine
        db: SQLite database manager (optional, for backward compatibility)
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: Optional[BaseDataProvider] = None,
        db: Optional[SQLiteDatabaseManager] = None
    ):
        """
        Initialize backtest engine with pluggable data provider.

        Args:
            config: Backtest configuration
            data_provider: Data provider implementing BaseDataProvider interface
            db: SQLite database manager (deprecated, for backward compatibility)

        Raises:
            ValueError: If neither data_provider nor db is provided

        Examples:
            # New approach (recommended)
            >>> from modules.backtesting.data_providers import PostgresDataProvider
            >>> from modules.db_manager_postgres import PostgresDatabaseManager
            >>> db = PostgresDatabaseManager(host='localhost', database='quant_platform')
            >>> provider = PostgresDataProvider(db, cache_enabled=True)
            >>> engine = BacktestEngine(config, data_provider=provider)

            # Factory methods (recommended)
            >>> engine = BacktestEngine.from_postgres(config, host='localhost')
            >>> engine = BacktestEngine.from_sqlite(config, db_path='data/spock.db')

            # Old approach (deprecated)
            >>> from modules.db_manager_sqlite import SQLiteDatabaseManager
            >>> db = SQLiteDatabaseManager('data/spock.db')
            >>> engine = BacktestEngine(config, db=db)  # Deprecated
        """
        self.config = config

        # Handle backward compatibility with db parameter
        if data_provider is None and db is None:
            raise ValueError(
                "Either data_provider or db must be provided. "
                "Prefer data_provider for new code (db parameter is deprecated)."
            )

        if data_provider is None and db is not None:
            # Backward compatibility: Create SQLiteDataProvider from db
            warnings.warn(
                "Passing 'db' parameter is deprecated and will be removed in version 2.0. "
                "Use 'data_provider' parameter or factory methods (from_sqlite, from_postgres) instead. "
                "Example: BacktestEngine.from_sqlite(config, db_path='data/spock.db')",
                DeprecationWarning,
                stacklevel=2
            )
            from .data_providers.sqlite_data_provider import SQLiteDataProvider
            data_provider = SQLiteDataProvider(db, cache_enabled=True)
            self.db = db  # Keep db for StrategyRunner (temporary)
            logger.info("Using SQLiteDataProvider (created from deprecated 'db' parameter)")
        else:
            self.db = db  # May be None for PostgreSQL

        self.data_provider = data_provider
        self.portfolio = PortfolioSimulator(config)

        # Initialize StrategyRunner
        # Note: StrategyRunner still needs db for LayeredScoringEngine/KellyCalculator
        # This will be refactored in a future task
        if self.db is not None:
            self.strategy_runner = StrategyRunner(config, self.db)
        else:
            # For PostgreSQL: Try to extract db from data_provider
            if hasattr(data_provider, 'db') and hasattr(data_provider.db, 'db_path'):
                # PostgresDataProvider doesn't have db_path, so this will fail
                logger.warning(
                    "StrategyRunner requires SQLite db_path for LayeredScoringEngine/KellyCalculator. "
                    "Strategy execution may fail with non-SQLite providers. "
                    "This is a known limitation that will be addressed in a future refactor."
                )
                self.strategy_runner = None  # Will fail if strategy_runner is used
            else:
                logger.warning("Cannot initialize StrategyRunner without SQLite database")
                self.strategy_runner = None

        provider_type = type(data_provider).__name__
        logger.info(
            f"BacktestEngine initialized: {config} | "
            f"Provider: {provider_type} (cache_enabled={data_provider.cache_enabled})"
        )

    def run(self) -> BacktestResult:
        """
        Execute backtest and return results using pluggable data provider.

        Returns:
            BacktestResult with metrics, trades, equity curve

        Execution Flow:
            1. Load historical data (via data_provider)
            2. Iterate day-by-day (event-driven loop)
            3. For each day:
               a. Update portfolio with current prices
               b. Check exit signals (stop loss, profit target)
               c. Execute exit orders
               d. Generate buy signals (strategy runner)
               e. Execute buy orders
               f. Record daily portfolio value
            4. Calculate performance metrics
            5. Return results

        Note:
            - Works with any BaseDataProvider implementation (SQLite, PostgreSQL, etc.)
            - HistoricalDataProvider compatibility maintained via adapter pattern
        """
        start_time = time.time()
        logger.info(f"Starting backtest: {self.config.start_date} to {self.config.end_date}")

        # Step 1: Load historical data using appropriate method
        logger.info("Loading historical data...")
        if isinstance(self.data_provider, HistoricalDataProvider):
            # Legacy HistoricalDataProvider: Use load_data() method
            self.data_provider.load_data(
                tickers=self.config.tickers,
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                regions=self.config.regions,
            )
            cache_stats = self.data_provider.get_cache_stats()
            logger.info(
                f"Data loaded: {cache_stats['tickers_cached']} tickers, "
                f"{cache_stats['total_rows']} rows, "
                f"{cache_stats['memory_usage_mb']:.1f} MB"
            )
        else:
            # New BaseDataProvider: Pre-load data for all tickers
            # (BaseDataProvider doesn't have load_data() method - uses get_ohlcv_batch())
            if self.config.tickers:
                logger.info(f"Pre-loading data for {len(self.config.tickers)} tickers...")
                for region in self.config.regions:
                    _ = self.data_provider.get_ohlcv_batch(
                        tickers=self.config.tickers,
                        region=region,
                        start_date=self.config.start_date,
                        end_date=self.config.end_date
                    )
            cache_stats = self.data_provider.get_cache_stats()
            logger.info(
                f"Data loaded: {cache_stats['size']} entries cached, "
                f"{cache_stats['memory_mb']:.1f} MB"
            )

        # Step 2: Get trading days
        trading_days = self._get_trading_days()
        logger.info(f"Trading days: {len(trading_days)} days")

        # Step 3: Event-driven loop (day-by-day)
        for i, current_date in enumerate(trading_days):
            if i % 50 == 0:
                progress_pct = i / len(trading_days) * 100
                logger.info(
                    f"Progress: {i}/{len(trading_days)} days ({progress_pct:.1f}%)"
                )

            # Get universe of available tickers for this day (provider-agnostic)
            if isinstance(self.data_provider, HistoricalDataProvider):
                # Legacy HistoricalDataProvider: get_universe(date, regions)
                universe = self.data_provider.get_universe(current_date, self.config.regions)
            else:
                # New BaseDataProvider: get_available_tickers(region, start, end)
                # Use all tickers from config as universe
                universe = self.config.tickers if self.config.tickers else []

            if len(universe) == 0:
                continue

            # Get current prices
            current_prices = self._get_current_prices(universe, current_date)

            # Step 3a: Update portfolio with current prices
            self.portfolio.update_positions(current_date, current_prices)

            # Step 3b: Check exit signals
            exit_signals = self.portfolio.update_positions(current_date, current_prices)

            # Step 3c: Execute exit orders
            for ticker, exit_reason in exit_signals:
                if ticker in current_prices:
                    self.portfolio.sell(
                        ticker=ticker,
                        price=current_prices[ticker],
                        sell_date=current_date,
                        exit_reason=exit_reason,
                    )

            # Step 3d: Generate buy signals using StrategyRunner (Week 2)
            buy_signals = run_generate_buy_signals(
                self.strategy_runner, universe, current_date, current_prices
            )

            # Step 3e: Execute buy orders
            for signal in buy_signals:
                trade = self.portfolio.buy(
                    ticker=signal["ticker"],
                    region=signal["region"],
                    price=signal["price"],
                    buy_date=current_date,
                    kelly_fraction=signal["kelly_fraction"],
                    pattern_type=signal["pattern_type"],
                    entry_score=signal["entry_score"],
                    sector=signal.get("sector"),
                    atr=signal.get("atr"),
                )
                if trade is not None:
                    self.portfolio.trades.append(trade)

            # Step 3f: Record daily portfolio value
            self.portfolio.record_daily_value(current_date, current_prices)

        # Step 4: Close any remaining open positions at end
        self._close_remaining_positions(trading_days[-1])

        # Step 5: Calculate performance metrics using PerformanceAnalyzer (Week 3)
        logger.info("Calculating performance metrics...")
        equity_curve = pd.Series(self.portfolio.portfolio_values).sort_index()

        analyzer = PerformanceAnalyzer(
            trades=self.portfolio.trades,
            equity_curve=equity_curve,
            initial_capital=self.config.initial_capital,
        )

        metrics = analyzer.calculate_metrics()
        pattern_metrics = analyzer.calculate_pattern_metrics()
        region_metrics = analyzer.calculate_region_metrics()

        execution_time = time.time() - start_time
        logger.info(f"Backtest complete in {execution_time:.1f} seconds")

        result = BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self.portfolio.trades,
            equity_curve=equity_curve,
            pattern_metrics=pattern_metrics,
            region_metrics=region_metrics,
            execution_time_seconds=execution_time,
        )

        # Print summary
        self._print_summary(result)

        return result

    def _get_trading_days(self) -> List[date]:
        """
        Generate list of trading days in backtest period.

        Returns:
            List of trading days

        Note:
            Simple implementation: All days in date range
            TODO: Add market holiday filtering in Week 7 (multi-region)
        """
        trading_days = []
        current = self.config.start_date
        while current <= self.config.end_date:
            # Simple weekday check (exclude weekends)
            if current.weekday() < 5:  # 0-4 = Monday-Friday
                trading_days.append(current)
            current += timedelta(days=1)
        return trading_days

    def _get_current_prices(
        self, universe: List[str], current_date: date
    ) -> Dict[str, float]:
        """
        Get current prices for all tickers in universe (provider-agnostic).

        Args:
            universe: List of tickers
            current_date: Current date

        Returns:
            Dictionary {ticker: price}

        Note:
            Works with both HistoricalDataProvider and BaseDataProvider implementations.
        """
        prices = {}
        if isinstance(self.data_provider, HistoricalDataProvider):
            # Legacy HistoricalDataProvider: Use get_latest_price()
            for ticker in universe:
                price = self.data_provider.get_latest_price(ticker, current_date)
                if price is not None:
                    prices[ticker] = price
        else:
            # New BaseDataProvider: Use get_ohlcv() for each ticker
            for ticker in universe:
                region = self.config.regions[0] if self.config.regions else 'KR'
                df = self.data_provider.get_ohlcv(
                    ticker=ticker,
                    region=region,
                    start_date=current_date,
                    end_date=current_date,
                    timeframe='1d'
                )
                if not df.empty and 'close' in df.columns:
                    prices[ticker] = df['close'].iloc[-1]
        return prices


    def _close_remaining_positions(self, final_date: date):
        """
        Close all remaining open positions at end of backtest (provider-agnostic).

        Args:
            final_date: Final trading day

        Note:
            Works with both HistoricalDataProvider and BaseDataProvider implementations.
        """
        open_positions = self.portfolio.get_current_positions()
        if len(open_positions) == 0:
            return

        logger.info(f"Closing {len(open_positions)} remaining positions")

        for position in open_positions:
            if isinstance(self.data_provider, HistoricalDataProvider):
                # Legacy HistoricalDataProvider: Use get_latest_price()
                price = self.data_provider.get_latest_price(position.ticker, final_date)
            else:
                # New BaseDataProvider: Use get_ohlcv()
                region = position.region if hasattr(position, 'region') else 'KR'
                df = self.data_provider.get_ohlcv(
                    ticker=position.ticker,
                    region=region,
                    start_date=final_date,
                    end_date=final_date,
                    timeframe='1d'
                )
                price = df['close'].iloc[-1] if not df.empty and 'close' in df.columns else None

            if price is None:
                price = position.entry_price  # Fallback

            self.portfolio.sell(
                ticker=position.ticker,
                price=price,
                sell_date=final_date,
                exit_reason="backtest_end",
            )

    def _print_summary(self, result: BacktestResult):
        """
        Print backtest summary to console.

        Args:
            result: Backtest result
        """
        m = result.metrics

        print("\n" + "=" * 80)
        print("Spock Backtest Summary (Week 3 - Performance Analyzer)")
        print("=" * 80)
        print(f"Period: {self.config.start_date} to {self.config.end_date}")
        print(f"Initial Capital: ₩{self.config.initial_capital:,.0f}")
        print(f"Final Portfolio Value: ₩{result.final_portfolio_value:,.0f}")
        print(f"Total Profit: ₩{result.total_profit:,.0f}")
        print()
        print("Performance Metrics:")
        print(f"  Total Return:      {m.total_return:+.1%}")
        print(f"  Annualized Return: {m.annualized_return:+.1%}")
        print(f"  Sharpe Ratio:      {m.sharpe_ratio:.2f}")
        print(f"  Max Drawdown:      {m.max_drawdown:.1%}")
        print()
        print("Trading Metrics:")
        print(f"  Total Trades:      {m.total_trades}")
        print(f"  Win Rate:          {m.win_rate:.1%}")
        print(f"  Profit Factor:     {m.profit_factor:.2f}")
        print(f"  Avg Holding:       {m.avg_holding_period_days:.1f} days")
        print("=" * 80)

    # -------------------------------------------------------------------------
    # Factory Methods (Convenience Constructors)
    # -------------------------------------------------------------------------

    @classmethod
    def from_sqlite(
        cls,
        config: BacktestConfig,
        db_path: str,
        cache_enabled: bool = True
    ) -> 'BacktestEngine':
        """
        Convenience factory for creating BacktestEngine with SQLite backend.

        Args:
            config: Backtest configuration
            db_path: Path to SQLite database file
            cache_enabled: Enable data caching (default: True)

        Returns:
            BacktestEngine instance with SQLiteDataProvider

        Examples:
            >>> engine = BacktestEngine.from_sqlite(
            ...     config=config,
            ...     db_path='data/spock_test_phase5.db'
            ... )
            >>> result = engine.run()
        """
        from .data_providers.sqlite_data_provider import SQLiteDataProvider
        from modules.db_manager_sqlite import SQLiteDatabaseManager

        db = SQLiteDatabaseManager(db_path)
        provider = SQLiteDataProvider(db, cache_enabled=cache_enabled)

        logger.info(f"Created BacktestEngine with SQLite backend (db_path={db_path})")
        return cls(config, data_provider=provider, db=db)  # Keep db for StrategyRunner

    @classmethod
    def from_postgres(
        cls,
        config: BacktestConfig,
        host: str = 'localhost',
        database: str = 'quant_platform',
        port: int = 5432,
        cache_enabled: bool = True
    ) -> 'BacktestEngine':
        """
        Convenience factory for creating BacktestEngine with PostgreSQL backend.

        Args:
            config: Backtest configuration
            host: PostgreSQL host (default: 'localhost')
            database: Database name (default: 'quant_platform')
            port: PostgreSQL port (default: 5432)
            cache_enabled: Enable data caching (default: True)

        Returns:
            BacktestEngine instance with PostgresDataProvider

        Examples:
            >>> engine = BacktestEngine.from_postgres(
            ...     config=config,
            ...     host='localhost',
            ...     database='quant_platform'
            ... )
            >>> result = engine.run()

        Note:
            StrategyRunner (LayeredScoringEngine/KellyCalculator) requires SQLite db_path.
            This limitation will be addressed in a future refactor.
            For now, strategy execution may not work with PostgreSQL-only setup.
        """
        from .data_providers.postgres_data_provider import PostgresDataProvider
        from modules.db_manager_postgres import PostgresDatabaseManager

        db_manager = PostgresDatabaseManager(host=host, port=port, database=database)
        provider = PostgresDataProvider(db_manager, cache_enabled=cache_enabled)

        logger.info(
            f"Created BacktestEngine with PostgreSQL backend "
            f"(host={host}, database={database})"
        )
        return cls(config, data_provider=provider, db=None)  # No SQLite db
