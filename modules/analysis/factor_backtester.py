"""
Factor Backtester - Simplified Wrapper for Factor Strategy Backtesting

Provides high-level methods for backtesting factor-based strategies using
the validated backtesting engines (vectorbt + custom).

**Implementation Status**: ✅ Complete (Task 6.2.2)

**Current Limitation**:
The vectorbt adapter currently supports only single-ticker backtests due to
vectorbt/portfolio multi-ticker implementation pending (see WEEK5_TEST_FAILURE_ANALYSIS.md).
Once multi-ticker support is added to vectorbt_adapter.py, the FactorBacktester
will work correctly for portfolio-level factor strategies.

**Workaround**:
For multi-ticker factor strategies, use BacktestRunner with custom engine directly
until vectorbt adapter gains full multi-ticker support.

Usage:
    from modules.analysis.factor_backtester import FactorBacktester
    from modules.factors.factor_combiner import OptimizationCombiner

    # Initialize backtester
    backtester = FactorBacktester()

    # Backtest single factor (vectorbt - 100x faster)
    result = backtester.backtest_single_factor(
        factor_name='12M_Momentum',
        start_date='2023-01-01',
        end_date='2024-12-31'
    )

    # Backtest multi-factor combination
    combiner = OptimizationCombiner()
    combiner.fit(start_date='2022-01-01', end_date='2023-12-31')

    result = backtester.backtest_multi_factor(
        combiner=combiner,
        start_date='2024-01-01',
        end_date='2024-12-31'
    )
"""

from typing import Literal, Union, Dict, Any
from datetime import date, datetime
from dataclasses import dataclass, asdict
from loguru import logger

from modules.backtesting.backtest_runner import BacktestRunner, ComparisonResult
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtResult
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.factors.factor_combiner import FactorCombinerBase
from modules.analysis.factor_strategy import (
    create_factor_signal_generator,
    create_single_factor_signal_generator
)


@dataclass
class FactorBacktestResult:
    """Structured result from factor backtesting."""

    # Strategy metadata
    strategy_type: str  # 'single_factor' or 'multi_factor'

    # Backtest period
    start_date: str
    end_date: str

    # Performance metrics
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float

    # Engine information
    engine: str  # 'custom', 'vectorbt', or 'both'
    execution_time: float

    # Optional fields
    factor_name: str = None  # For single-factor strategies
    factor_weights: Dict[str, float] = None  # For multi-factor strategies
    consistency_score: float = None  # If engine='both'
    speedup_factor: float = None  # If engine='both'
    raw_result: Any = None  # Store original result for detailed analysis

    def __str__(self) -> str:
        """Human-readable summary."""
        strategy_desc = (
            f"{self.factor_name}" if self.strategy_type == 'single_factor'
            else f"{len(self.factor_weights)} factors"
        )

        return (
            f"FactorBacktestResult({strategy_desc})\n"
            f"  Period: {self.start_date} to {self.end_date}\n"
            f"  Return: {self.total_return:+.2%}\n"
            f"  Sharpe: {self.sharpe_ratio:.3f}\n"
            f"  Max DD: {self.max_drawdown:.2%}\n"
            f"  Trades: {self.total_trades} (win rate: {self.win_rate:.1%})\n"
            f"  Engine: {self.engine} ({self.execution_time:.2f}s)\n"
            + (f"  Consistency: {self.consistency_score:.1%}\n" if self.consistency_score else "")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV export."""
        return asdict(self)


class FactorBacktester:
    """
    High-level wrapper for factor strategy backtesting.

    Simplifies the workflow of backtesting factor-based strategies by
    providing convenient methods that handle:
    - Signal generator creation
    - BacktestRunner configuration
    - Result processing and formatting

    Example:
        >>> backtester = FactorBacktester()
        >>>
        >>> # Test single factor
        >>> result = backtester.backtest_single_factor(
        ...     factor_name='12M_Momentum',
        ...     start_date='2023-01-01',
        ...     end_date='2024-12-31'
        ... )
        >>> print(f"Sharpe Ratio: {result.sharpe_ratio:.3f}")
        >>>
        >>> # Test multi-factor combination
        >>> from modules.factors.factor_combiner import OptimizationCombiner
        >>> combiner = OptimizationCombiner()
        >>> combiner.fit(start_date='2022-01-01', end_date='2023-12-31')
        >>>
        >>> result = backtester.backtest_multi_factor(
        ...     combiner=combiner,
        ...     start_date='2024-01-01',
        ...     end_date='2024-12-31',
        ...     engine='both'
        ... )
    """

    def __init__(
        self,
        region: str = 'KR',
        initial_capital: float = 10_000_000,
        max_position_size: float = 0.15,
        commission_rate: float = 0.00015,
        slippage_bps: float = 5.0,
        db_host: str = 'localhost',
        db_name: str = 'quant_platform'
    ):
        """
        Initialize FactorBacktester.

        Args:
            region: Market region (default: 'KR')
            initial_capital: Starting capital (default: 10M KRW)
            max_position_size: Maximum position size as fraction (default: 15%)
            commission_rate: Commission rate (default: 0.015% = 15 bps)
            slippage_bps: Slippage in basis points (default: 5 bps)
            db_host: PostgreSQL host (default: 'localhost')
            db_name: Database name (default: 'quant_platform')
        """
        self.region = region
        self.initial_capital = initial_capital
        self.max_position_size = max_position_size
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps

        # Initialize database connection
        self.db_manager = PostgresDatabaseManager(
            host=db_host,
            database=db_name
        )

        # Initialize data provider
        self.data_provider = PostgresDataProvider(
            db_manager=self.db_manager,
            cache_enabled=True
        )

        logger.info(
            f"FactorBacktester initialized: region={region}, "
            f"capital={initial_capital:,.0f}, max_pos={max_position_size:.1%}"
        )

    def backtest_single_factor(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        threshold: float = 70.0,
        holding_period: int = 21,
        tickers: list = None
    ) -> FactorBacktestResult:
        """
        Backtest single-factor strategy using vectorbt engine (100x faster).

        Tests a strategy that selects stocks based on a single factor score,
        holding the top N stocks with scores above the threshold.

        Note:
            This method uses vectorbt engine only for maximum research speed.
            For production validation with custom engine, use BacktestRunner directly.

        Args:
            factor_name: Name of factor to test (e.g., '12M_Momentum')
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            top_n: Number of stocks to hold (default: 10)
            threshold: Minimum factor score (0-100, default: 70)
            holding_period: Days to hold positions (default: 21)
            tickers: Optional list of tickers (default: auto-detect from data)

        Returns:
            FactorBacktestResult with performance metrics

        Example:
            >>> backtester = FactorBacktester()
            >>> result = backtester.backtest_single_factor(
            ...     factor_name='12M_Momentum',
            ...     start_date='2023-01-01',
            ...     end_date='2024-12-31'
            ... )
            >>> print(f"Sharpe: {result.sharpe_ratio:.3f}")
        """
        logger.info(
            f"Backtesting single factor: {factor_name} "
            f"({start_date} to {end_date})"
        )

        # Auto-detect tickers with factor scores if not provided
        if tickers is None:
            tickers = self._get_tickers_with_factor_scores(
                factor_name,
                start_date,
                end_date
            )
            logger.info(f"Auto-detected {len(tickers)} tickers with {factor_name} scores")

            if len(tickers) == 0:
                raise ValueError(
                    f"No tickers found with {factor_name} scores in date range "
                    f"{start_date} to {end_date}"
                )

        # WORKAROUND: VectorbtAdapter currently supports only single-ticker backtests
        # Once multi-ticker support is added, remove this limitation
        if len(tickers) > 1:
            logger.warning(
                f"VectorbtAdapter multi-ticker support pending. "
                f"Using first ticker only: {tickers[0]}"
            )
            tickers = [tickers[0]]

        # Create configuration
        config = BacktestConfig(
            start_date=self._parse_date(start_date),
            end_date=self._parse_date(end_date),
            initial_capital=self.initial_capital,
            regions=[self.region],
            tickers=tickers,
            max_position_size=self.max_position_size,
            score_threshold=threshold,
            risk_profile='moderate',
            commission_rate=self.commission_rate,
            slippage_bps=self.slippage_bps
        )

        # Create vectorbt-compatible signal generator
        # Note: create_vectorbt_factor_signal_generator() generates all signals upfront
        # for the entire period, unlike the event-driven create_factor_signal_generator()
        from modules.analysis.factor_strategy import create_vectorbt_factor_signal_generator
        signal_generator = create_vectorbt_factor_signal_generator(
            factor_name=factor_name,
            threshold=threshold,
            region=self.region
        )

        # Run backtest with vectorbt (100x faster)
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter
        adapter = VectorbtAdapter(config, self.data_provider, signal_generator=signal_generator)
        raw_result = adapter.run()

        # Process results
        return self._process_result(
            raw_result=raw_result,
            strategy_type='single_factor',
            factor_name=factor_name,
            start_date=start_date,
            end_date=end_date,
            engine='vectorbt'
        )

    def backtest_multi_factor(
        self,
        combiner: FactorCombinerBase,
        start_date: str,
        end_date: str,
        top_n: int = 10,
        threshold: float = 70.0,
        holding_period: int = 21,
        rebalance_freq: int = 21,
        tickers: list = None
    ) -> FactorBacktestResult:
        """
        Backtest multi-factor combination strategy using vectorbt engine (100x faster).

        Tests a strategy that selects stocks based on composite factor scores
        from multiple factors combined using the provided combiner.

        Note:
            This method uses vectorbt engine only for maximum research speed.
            For production validation with custom engine, use BacktestRunner directly.

        Args:
            combiner: FactorCombinerBase instance (EqualWeight, Optimization, etc.)
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            top_n: Number of stocks to hold (default: 10)
            threshold: Minimum composite score (0-100, default: 70)
            holding_period: Days to hold positions (default: 21)
            rebalance_freq: Days between rebalances (default: 21)
            tickers: Optional list of tickers (default: auto-detect from data)

        Returns:
            FactorBacktestResult with performance metrics

        Example:
            >>> from modules.factors.factor_combiner import OptimizationCombiner
            >>> combiner = OptimizationCombiner()
            >>> combiner.fit(start_date='2022-01-01', end_date='2023-12-31')
            >>>
            >>> backtester = FactorBacktester()
            >>> result = backtester.backtest_multi_factor(
            ...     combiner=combiner,
            ...     start_date='2024-01-01',
            ...     end_date='2024-12-31'
            ... )
        """
        logger.info(
            f"Backtesting multi-factor strategy ({combiner.__class__.__name__}) "
            f"({start_date} to {end_date})"
        )

        # Auto-detect tickers if not provided
        if tickers is None:
            tickers = self._get_available_tickers(start_date, end_date)
            logger.info(f"Auto-detected {len(tickers)} tickers")

        # WORKAROUND: VectorbtAdapter currently supports only single-ticker backtests
        # Once multi-ticker support is added, remove this limitation
        if len(tickers) > 1:
            logger.warning(
                f"VectorbtAdapter multi-ticker support pending. "
                f"Using first ticker only: {tickers[0]}"
            )
            tickers = [tickers[0]]

        # Create configuration
        config = BacktestConfig(
            start_date=self._parse_date(start_date),
            end_date=self._parse_date(end_date),
            initial_capital=self.initial_capital,
            regions=[self.region],
            tickers=tickers,
            max_position_size=self.max_position_size,
            score_threshold=threshold,
            risk_profile='moderate',
            commission_rate=self.commission_rate,
            slippage_bps=self.slippage_bps
        )

        # Create signal generator
        signal_generator = create_factor_signal_generator(
            factor_combiner=combiner,
            top_n=top_n,
            threshold=threshold,
            holding_period=holding_period,
            rebalance_freq=rebalance_freq
        )

        # Run backtest with vectorbt (100x faster)
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter
        adapter = VectorbtAdapter(config, self.data_provider, signal_generator=signal_generator)
        raw_result = adapter.run()

        # Extract factor weights if available
        factor_weights = None
        if hasattr(combiner, 'optimal_weights'):
            factor_weights = combiner.optimal_weights
        elif hasattr(combiner, 'get_optimal_weights'):
            factor_weights = combiner.get_optimal_weights()

        # Process results
        return self._process_result(
            raw_result=raw_result,
            strategy_type='multi_factor',
            factor_weights=factor_weights,
            start_date=start_date,
            end_date=end_date,
            engine='vectorbt'
        )

    def _get_available_tickers(
        self,
        start_date: str,
        end_date: str,
        min_coverage_pct: float = 0.8
    ) -> list:
        """
        Get tickers with sufficient data coverage in the date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_coverage_pct: Minimum data coverage percentage (default: 0.8 = 80%)

        Returns:
            List of ticker symbols with sufficient data
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import os

        conn = psycopg2.connect(
            dbname="quant_platform",
            user=os.getenv("USER", "13ruce"),
            host="localhost",
            port=5432
        )

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First, get the maximum data points (to calculate coverage)
                max_query = """
                SELECT MAX(cnt) as max_data_points
                FROM (
                    SELECT COUNT(*) as cnt
                    FROM ohlcv_data
                    WHERE region = %s
                      AND date >= %s::date
                      AND date <= %s::date
                    GROUP BY ticker
                ) t;
                """

                cur.execute(max_query, (self.region, start_date, end_date))
                max_row = cur.fetchone()
                max_data_points = max_row['max_data_points'] if max_row else 0

                if max_data_points == 0:
                    logger.warning(f"No data found for region {self.region} in date range")
                    return []

                # Calculate minimum required data points
                min_data_points = int(max_data_points * min_coverage_pct)

                # Query tickers with sufficient coverage
                query = """
                SELECT ticker, COUNT(*) as data_points
                FROM ohlcv_data
                WHERE region = %s
                  AND date >= %s::date
                  AND date <= %s::date
                GROUP BY ticker
                HAVING COUNT(*) >= %s
                ORDER BY ticker;
                """

                cur.execute(query, (self.region, start_date, end_date, min_data_points))
                rows = cur.fetchall()

                tickers = [row['ticker'] for row in rows]

                logger.info(
                    f"Auto-detected {len(tickers)} tickers with >={min_coverage_pct:.0%} "
                    f"coverage ({min_data_points}/{max_data_points} data points)"
                )

                return tickers

        finally:
            conn.close()

    def _get_tickers_with_factor_scores(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        min_coverage_pct: float = 0.8
    ) -> list:
        """
        Get tickers with sufficient factor scores AND ohlcv data in the date range.

        Args:
            factor_name: Factor name to check (e.g., '12M_Momentum')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            min_coverage_pct: Minimum data coverage percentage (default: 0.8 = 80%)

        Returns:
            List of ticker symbols with sufficient factor scores and price data
        """
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import os

        conn = psycopg2.connect(
            dbname="quant_platform",
            user=os.getenv("USER", "13ruce"),
            host="localhost",
            port=5432
        )

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First, get the maximum data points (to calculate coverage)
                max_query = """
                SELECT MAX(cnt) as max_data_points
                FROM (
                    SELECT COUNT(*) as cnt
                    FROM ohlcv_data
                    WHERE region = %s
                      AND date >= %s::date
                      AND date <= %s::date
                    GROUP BY ticker
                ) t;
                """

                cur.execute(max_query, (self.region, start_date, end_date))
                max_row = cur.fetchone()
                max_data_points = max_row['max_data_points'] if max_row else 0

                if max_data_points == 0:
                    logger.warning(f"No data found for region {self.region} in date range")
                    return []

                # Calculate minimum required data points
                min_data_points = int(max_data_points * min_coverage_pct)

                # Query tickers with sufficient factor scores AND ohlcv data
                query = """
                SELECT
                    f.ticker,
                    COUNT(DISTINCT f.date) as factor_count,
                    COUNT(DISTINCT o.date) as ohlcv_count
                FROM factor_scores f
                INNER JOIN ohlcv_data o ON f.ticker = o.ticker AND f.region = o.region
                WHERE f.region = %s
                  AND f.factor_name = %s
                  AND f.date >= %s::date
                  AND f.date <= %s::date
                  AND o.date >= %s::date
                  AND o.date <= %s::date
                GROUP BY f.ticker
                HAVING COUNT(DISTINCT o.date) >= %s
                   AND COUNT(DISTINCT f.date) >= %s
                ORDER BY f.ticker;
                """

                cur.execute(query, (
                    self.region,
                    factor_name,
                    start_date,
                    end_date,
                    start_date,
                    end_date,
                    min_data_points,
                    min_data_points
                ))
                rows = cur.fetchall()

                tickers = [row['ticker'] for row in rows]

                logger.info(
                    f"Found {len(tickers)} tickers with {factor_name} scores and >={min_coverage_pct:.0%} "
                    f"data coverage ({min_data_points}/{max_data_points} points)"
                )

                return tickers

        finally:
            conn.close()

    def _parse_date(self, date_str: str) -> date:
        """Parse date string to date object."""
        return datetime.strptime(date_str, '%Y-%m-%d').date()

    def _process_result(
        self,
        raw_result: Union[Dict[str, Any], VectorbtResult, ComparisonResult],
        strategy_type: str,
        start_date: str,
        end_date: str,
        engine: str,
        factor_name: str = None,
        factor_weights: Dict[str, float] = None
    ) -> FactorBacktestResult:
        """
        Process raw backtest result into FactorBacktestResult.

        Handles different result types from BacktestRunner:
        - Dict (custom engine)
        - VectorbtResult (vectorbt engine)
        - ComparisonResult (both engines)
        """
        # Extract metrics based on result type
        if isinstance(raw_result, ComparisonResult):
            # Use vectorbt metrics (faster, for research)
            return FactorBacktestResult(
                strategy_type=strategy_type,
                factor_name=factor_name,
                factor_weights=factor_weights,
                start_date=start_date,
                end_date=end_date,
                total_return=raw_result.vectorbt_total_return,
                sharpe_ratio=raw_result.vectorbt_sharpe_ratio,
                max_drawdown=raw_result.vectorbt_max_drawdown,
                total_trades=raw_result.vectorbt_total_trades,
                win_rate=0.0,  # Not available in comparison
                engine=engine,
                execution_time=raw_result.vectorbt_execution_time,
                consistency_score=raw_result.consistency_score,
                speedup_factor=raw_result.speedup_factor,
                raw_result=raw_result
            )

        elif isinstance(raw_result, VectorbtResult):
            # vectorbt result
            return FactorBacktestResult(
                strategy_type=strategy_type,
                factor_name=factor_name,
                factor_weights=factor_weights,
                start_date=start_date,
                end_date=end_date,
                total_return=raw_result.total_return,
                sharpe_ratio=raw_result.sharpe_ratio,
                max_drawdown=raw_result.max_drawdown,
                total_trades=raw_result.total_trades,
                win_rate=raw_result.win_rate,
                engine=engine,
                execution_time=raw_result.execution_time,
                raw_result=raw_result
            )

        elif isinstance(raw_result, dict):
            # Custom engine result
            metrics = raw_result.get('metrics', {})
            return FactorBacktestResult(
                strategy_type=strategy_type,
                factor_name=factor_name,
                factor_weights=factor_weights,
                start_date=start_date,
                end_date=end_date,
                total_return=metrics.get('total_return', 0.0),
                sharpe_ratio=metrics.get('sharpe_ratio', 0.0),
                max_drawdown=metrics.get('max_drawdown', 0.0),
                total_trades=len(raw_result.get('trades', [])),
                win_rate=metrics.get('win_rate', 0.0),
                engine=engine,
                execution_time=raw_result.get('execution_time_seconds', 0.0),
                raw_result=raw_result
            )

        else:
            raise ValueError(f"Unknown result type: {type(raw_result)}")


if __name__ == '__main__':
    """Test FactorBacktester."""
    import sys
    sys.path.insert(0, '/Users/13ruce/spock')

    from modules.factors.factor_combiner import EqualWeightCombiner

    print("Testing FactorBacktester...")

    # Initialize
    backtester = FactorBacktester()

    # Test single-factor backtest (use date range with complete factor data)
    print("\n1. Testing single-factor backtest (12M_Momentum)...")
    try:
        result = backtester.backtest_single_factor(
            factor_name='12M_Momentum',
            start_date='2024-01-01',
            end_date='2024-10-15',  # Use earlier date to ensure factor data availability
            top_n=5
        )
        print(result)
    except Exception as e:
        print(f"Single-factor test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test multi-factor backtest
    print("\n2. Testing multi-factor backtest (Equal Weight)...")
    try:
        combiner = EqualWeightCombiner()
        result = backtester.backtest_multi_factor(
            combiner=combiner,
            start_date='2024-01-01',
            end_date='2024-10-15',  # Use earlier date to ensure factor data availability
            top_n=5
        )
        print(result)
    except Exception as e:
        print(f"Multi-factor test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n✅ FactorBacktester test completed!")
