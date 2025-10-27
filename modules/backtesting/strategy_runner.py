"""
Strategy Runner

Purpose: Execute trading strategies for backtesting with signal generation.

Key Features:
  - Integrate LayeredScoringEngine for stock scoring
  - Generate buy/sell signals based on score thresholds
  - Calculate position sizes using KellyCalculator
  - Multi-region strategy execution
  - Pattern-based signal generation

Design Philosophy:
  - Strategy-agnostic architecture
  - Pluggable scoring engines
  - Evidence-based signal generation
  - Risk-adjusted position sizing
"""

from datetime import date
from typing import List, Dict, Optional
import logging
import asyncio

from modules.layered_scoring_engine import LayeredScoringEngine, ScoringResult
from modules.kelly_calculator import KellyCalculator, PatternType, RiskLevel, KellyResult
from modules.db_manager_sqlite import SQLiteDatabaseManager
from .backtest_config import BacktestConfig


logger = logging.getLogger(__name__)


class StrategyRunner:
    """
    Execute trading strategies with scoring and position sizing.

    Attributes:
        config: Backtest configuration
        db: SQLite database manager
        scoring_engine: LayeredScoringEngine for stock analysis
        kelly_calculator: KellyCalculator for position sizing
    """

    def __init__(self, config: BacktestConfig, db: SQLiteDatabaseManager):
        """
        Initialize strategy runner.

        Args:
            config: Backtest configuration
            db: SQLite database manager
        """
        self.config = config
        self.db = db

        # Initialize LayeredScoringEngine
        self.scoring_engine = LayeredScoringEngine(db_path=db.db_path)
        logger.info("LayeredScoringEngine initialized")

        # Initialize KellyCalculator with config risk profile
        risk_level_map = {
            "conservative": RiskLevel.CONSERVATIVE,
            "moderate": RiskLevel.MODERATE,
            "aggressive": RiskLevel.AGGRESSIVE,
        }
        risk_level = risk_level_map.get(self.config.risk_profile, RiskLevel.MODERATE)

        self.kelly_calculator = KellyCalculator(
            db_path=db.db_path,
            risk_level=risk_level,
            max_single_position=self.config.max_position_size * 100,  # Convert to percentage
            max_total_allocation=100.0,  # Portfolio-wide allocation
        )
        logger.info(f"KellyCalculator initialized (risk_level={risk_level.value})")

    async def generate_buy_signals(
        self,
        universe: List[str],
        current_date: date,
        current_prices: Dict[str, float],
    ) -> List[Dict]:
        """
        Generate buy signals for stocks in universe.

        Args:
            universe: List of available tickers
            current_date: Current date
            current_prices: Current prices {ticker: price}

        Returns:
            List of buy signal dictionaries

        Signal Generation Logic:
            1. Score all tickers in universe using LayeredScoringEngine
            2. Filter by score_threshold
            3. Calculate Kelly position sizes
            4. Generate buy signals with position sizing

        Example:
            >>> signals = await strategy_runner.generate_buy_signals(
            ...     universe=['005930', '000660'],
            ...     current_date=date(2023, 6, 15),
            ...     current_prices={'005930': 70000, '000660': 140000}
            ... )
            >>> # [
            >>> #   {
            >>> #     'ticker': '005930',
            >>> #     'region': 'KR',
            >>> #     'price': 70000,
            >>> #     'kelly_fraction': 0.5,
            >>> #     'pattern_type': 'Stage2',
            >>> #     'entry_score': 75,
            >>> #     'sector': 'Information Technology',
            >>> #     'atr': 2000
            >>> #   }
            >>> # ]
        """
        buy_signals = []

        logger.info(
            f"Generating buy signals for {len(universe)} tickers on {current_date}"
        )

        # Step 1: Score all tickers in universe
        scoring_tasks = []
        for ticker in universe:
            if ticker in current_prices:
                # Create async scoring task
                # Note: LayeredScoringEngine.analyze_ticker() only takes ticker parameter
                task = self.scoring_engine.analyze_ticker(ticker=ticker)
                scoring_tasks.append((ticker, task))

        # Execute scoring in parallel
        scored_results: List[tuple[str, Optional[ScoringResult]]] = []
        for ticker, task in scoring_tasks:
            try:
                result = await task
                scored_results.append((ticker, result))
            except Exception as e:
                logger.error(f"Scoring failed for {ticker}: {e}")
                scored_results.append((ticker, None))

        # Step 2: Filter by score_threshold
        qualified_tickers = []
        for ticker, result in scored_results:
            if result is None:
                continue

            if result.total_score >= self.config.score_threshold:
                qualified_tickers.append((ticker, result))
                logger.debug(
                    f"{ticker}: Score {result.total_score:.1f} >= {self.config.score_threshold} (qualified)"
                )
            else:
                logger.debug(
                    f"{ticker}: Score {result.total_score:.1f} < {self.config.score_threshold} (skipped)"
                )

        logger.info(
            f"Qualified tickers: {len(qualified_tickers)}/{len(scored_results)} "
            f"(threshold: {self.config.score_threshold})"
        )

        # Step 3: Calculate Kelly position sizes for qualified tickers
        for ticker, scoring_result in qualified_tickers:
            try:
                # Detect pattern type from scoring result
                pattern_type = self._detect_pattern_from_score(scoring_result)

                # Calculate Kelly position size
                kelly_result = self.kelly_calculator.calculate_position_with_gpt(
                    ticker=ticker,
                    detected_pattern=pattern_type,
                    quality_score=scoring_result.total_score,
                    risk_level=self.kelly_calculator.risk_level,
                    use_gpt=False,  # Disable GPT for backtesting (speed)
                )

                # Skip if final position is 0 (quality too low)
                if kelly_result.final_position_pct <= 0:
                    logger.debug(f"{ticker}: Position size 0%, skipping")
                    continue

                # Get ATR from database for stop loss calculation
                atr = self._get_atr(ticker, current_date)

                # Get sector from database
                sector = self._get_sector(ticker)

                # Create buy signal
                buy_signal = {
                    "ticker": ticker,
                    "region": self.config.regions[0],  # Default to first region
                    "price": current_prices[ticker],
                    "kelly_fraction": kelly_result.final_position_pct / 100.0,  # Convert % to fraction
                    "pattern_type": pattern_type.value,
                    "entry_score": int(scoring_result.total_score),
                    "sector": sector,
                    "atr": atr,
                }

                buy_signals.append(buy_signal)

                logger.info(
                    f"BUY SIGNAL: {ticker} @ {current_prices[ticker]:,.0f} "
                    f"(score={scoring_result.total_score:.1f}, "
                    f"pattern={pattern_type.value}, "
                    f"kelly={kelly_result.final_position_pct:.2f}%)"
                )

            except Exception as e:
                logger.error(f"Kelly calculation failed for {ticker}: {e}")
                continue

        logger.info(f"Generated {len(buy_signals)} buy signals")
        return buy_signals

    def _detect_pattern_from_score(self, scoring_result: ScoringResult) -> PatternType:
        """
        Detect pattern type from LayeredScoringEngine scoring result.

        Args:
            scoring_result: ScoringResult from LayeredScoringEngine

        Returns:
            PatternType enum

        Detection Logic:
            - Use module scores and details from scoring_result
            - Prioritize: Stage 1→2 > VCP > Cup & Handle > Stage 2 Continuation
            - Default to Stage 2 Continuation for high scores
        """
        # Extract layer scores
        layer_scores = scoring_result.layer_scores

        # Structural layer (Stage 2 detection)
        structural_score = layer_scores.get("structural", 0.0)

        # Micro layer (Pattern detection)
        micro_score = layer_scores.get("micro", 0.0)

        # Macro layer (Volume analysis)
        macro_score = layer_scores.get("macro", 0.0)

        # High structural score + high micro score → Stage 1→2 transition
        if structural_score >= 35 and micro_score >= 25:
            logger.debug(
                f"Pattern detected: STAGE_1_TO_2 (structural={structural_score}, micro={micro_score})"
            )
            return PatternType.STAGE_1_TO_2

        # High micro score + moderate structural → VCP or Cup & Handle
        if micro_score >= 20 and structural_score >= 25:
            # Differentiate between VCP and Cup & Handle based on total score
            if scoring_result.total_score >= 80:
                logger.debug(
                    f"Pattern detected: VCP_BREAKOUT (micro={micro_score}, total={scoring_result.total_score})"
                )
                return PatternType.VCP_BREAKOUT
            else:
                logger.debug(
                    f"Pattern detected: CUP_HANDLE (micro={micro_score}, total={scoring_result.total_score})"
                )
                return PatternType.CUP_HANDLE

        # High macro score → 60-day high breakout
        if macro_score >= 20 and structural_score >= 20:
            logger.debug(
                f"Pattern detected: HIGH_60D_BREAKOUT (macro={macro_score}, structural={structural_score})"
            )
            return PatternType.HIGH_60D_BREAKOUT

        # Moderate scores → Stage 2 continuation
        if structural_score >= 20:
            logger.debug(
                f"Pattern detected: STAGE_2_CONTINUATION (structural={structural_score})"
            )
            return PatternType.STAGE_2_CONTINUATION

        # Low scores → MA200 breakout (conservative)
        logger.debug(
            f"Pattern detected: MA200_BREAKOUT (fallback, total={scoring_result.total_score})"
        )
        return PatternType.MA200_BREAKOUT

    def _get_atr(self, ticker: str, current_date: date) -> Optional[float]:
        """
        Get ATR from database for ticker.

        Args:
            ticker: Stock ticker
            current_date: Current date

        Returns:
            ATR value or None
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT atr
                FROM ohlcv_data
                WHERE ticker = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
            """
            cursor.execute(query, (ticker, current_date.isoformat()))
            result = cursor.fetchone()

            conn.close()

            if result and result[0]:
                return float(result[0])
            return None

        except Exception as e:
            logger.warning(f"Failed to get ATR for {ticker}: {e}")
            return None

    def _get_sector(self, ticker: str) -> Optional[str]:
        """
        Get sector from database for ticker.

        Args:
            ticker: Stock ticker

        Returns:
            Sector name or None
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT sector
                FROM tickers
                WHERE ticker = ?
                LIMIT 1
            """
            cursor.execute(query, (ticker,))
            result = cursor.fetchone()

            conn.close()

            if result and result[0]:
                return result[0]
            return None

        except Exception as e:
            logger.warning(f"Failed to get sector for {ticker}: {e}")
            return None


# Async wrapper for BacktestEngine integration
def run_generate_buy_signals(
    strategy_runner: StrategyRunner,
    universe: List[str],
    current_date: date,
    current_prices: Dict[str, float],
) -> List[Dict]:
    """
    Synchronous wrapper for generate_buy_signals (for BacktestEngine).

    Args:
        strategy_runner: StrategyRunner instance
        universe: List of available tickers
        current_date: Current date
        current_prices: Current prices

    Returns:
        List of buy signal dictionaries
    """
    # Run async function in event loop
    # Note: asyncio.get_event_loop() is deprecated in Python 3.12+
    # Use asyncio.run() for new event loop, or get_running_loop() for existing
    try:
        # Check if there's a running loop (will raise if not)
        loop = asyncio.get_running_loop()
        # If we get here, loop is running - can't use run_until_complete
        # This shouldn't happen in BacktestEngine context, but handle it
        import nest_asyncio
        nest_asyncio.apply()
        return asyncio.run(
            strategy_runner.generate_buy_signals(universe, current_date, current_prices)
        )
    except RuntimeError:
        # No running loop - create new one with asyncio.run()
        return asyncio.run(
            strategy_runner.generate_buy_signals(universe, current_date, current_prices)
        )
