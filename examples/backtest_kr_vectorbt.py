#!/usr/bin/env python3
"""
KR Market Backtesting Example using BacktestRunner + vectorbt Engine

Purpose:
    Demonstrate how to use BacktestRunner with vectorbt engine for KR market backtesting.
    This example shows a simple RSI-based momentum strategy.

Strategy:
    - Entry Signal: RSI-14 < 30 (oversold condition)
    - Exit Signal: RSI-14 > 70 (overbought condition)

Usage:
    python3 examples/backtest_kr_vectorbt.py
"""

import sys
from pathlib import Path
from datetime import date
from typing import Tuple
import pandas as pd
import numpy as np
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# Configuration
# ============================================================================

# Backtest period
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 10, 29)

# Region and tickers
REGION = 'KR'
# Sample of 20 active KR tickers for testing (vectorbt requires explicit ticker list)
TICKERS = [
    '000120', '011150', '011155', '001045', '097950',
    '000480', '000590', '005830', '016610', '000990',
    '000300', '001530', '015590', '000210', '000215',
    '375500', '37550K', '007340', '004840', '155660'
]

# RSI parameters
RSI_PERIOD = 14
RSI_OVERSOLD = 30  # Entry threshold
RSI_OVERBOUGHT = 70  # Exit threshold


# ============================================================================
# Signal Generator
# ============================================================================

def rsi_momentum_signal_generator(close: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """
    Generate RSI-based momentum signals.

    Args:
        close: Close price series (vectorbt provides this)

    Returns:
        Tuple of (entries, exits) as boolean Series

    Strategy Logic:
        - Entry: RSI-14 drops below 30 (oversold → buy opportunity)
        - Exit: RSI-14 rises above 70 (overbought → take profit)
    """
    # Calculate RSI-14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # Generate signals
    entries = rsi < RSI_OVERSOLD  # Buy when oversold
    exits = rsi > RSI_OVERBOUGHT  # Sell when overbought

    logger.debug(f"Generated signals - Entries: {entries.sum()}, Exits: {exits.sum()}")

    return entries, exits


# ============================================================================
# Main Backtest
# ============================================================================

def main():
    """Run KR market backtest with vectorbt engine."""

    logger.info("=" * 80)
    logger.info("KR Market Backtesting Example - vectorbt Engine")
    logger.info("=" * 80)

    # ========================================================================
    # Step 1: Initialize Database and Data Provider
    # ========================================================================

    logger.info("\n[1/4] Initializing database and data provider...")

    db = PostgresDatabaseManager()
    data_provider = PostgresDataProvider(
        db_manager=db,
        cache_enabled=True,  # Enable caching for better performance
        backfill_enabled=False  # Don't trigger backfills during backtest
    )

    logger.info("✅ Database and data provider initialized")

    # ========================================================================
    # Step 2: Create Backtest Configuration
    # ========================================================================

    logger.info("\n[2/4] Creating backtest configuration...")

    config = BacktestConfig(
        # Time period
        start_date=START_DATE,
        end_date=END_DATE,

        # Region and tickers
        regions=[REGION],
        tickers=TICKERS,  # None = all available tickers

        # Strategy parameters (using moderate risk profile defaults)
        score_threshold=70,
        risk_profile="moderate",

        # Position sizing
        kelly_multiplier=0.5,  # Half Kelly (conservative)
        max_position_size=0.15,  # 15% max per stock
        max_sector_exposure=0.40,  # 40% max per sector
        cash_reserve=0.20,  # 20% min cash

        # Risk management
        stop_loss_atr_multiplier=1.0,
        stop_loss_min=0.05,  # 5% min stop loss
        stop_loss_max=0.15,  # 15% max stop loss
        profit_target=0.20,  # 20% profit taking

        # Transaction costs (KR market)
        commission_rate=0.00015,  # 0.015% (KIS default for Korea)
        slippage_bps=5.0,  # 5 basis points

        # Initial capital
        initial_capital=100_000_000  # 100M KRW
    )

    logger.info(f"✅ Backtest config created:")
    logger.info(f"   Period: {START_DATE} ~ {END_DATE}")
    logger.info(f"   Region: {REGION}")
    logger.info(f"   Tickers: {len(config.tickers) if config.tickers else 'ALL'}")
    logger.info(f"   Initial Capital: {config.initial_capital:,.0f} KRW")
    logger.info(f"   Risk Profile: {config.risk_profile}")

    # ========================================================================
    # Step 3: Initialize BacktestRunner
    # ========================================================================

    logger.info("\n[3/4] Initializing BacktestRunner...")

    runner = BacktestRunner(
        config=config,
        data_provider=data_provider
    )

    logger.info("✅ BacktestRunner initialized")

    # ========================================================================
    # Step 4: Run Backtest with vectorbt Engine
    # ========================================================================

    logger.info("\n[4/4] Running backtest with vectorbt engine...")
    logger.info(f"Strategy: RSI-{RSI_PERIOD} Momentum")
    logger.info(f"  Entry: RSI < {RSI_OVERSOLD}")
    logger.info(f"  Exit: RSI > {RSI_OVERBOUGHT}")

    try:
        result = runner.run(
            engine='vectorbt',  # 100x faster than custom engine
            signal_generator=rsi_momentum_signal_generator
        )

        logger.info("✅ Backtest completed successfully!")

        # ====================================================================
        # Display Results
        # ====================================================================

        logger.info("\n" + "=" * 80)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 80)

        # Portfolio performance
        logger.info("\n📊 Portfolio Performance:")
        logger.info(f"   Total Return: {result.total_return:.2%}")
        logger.info(f"   Annual Return: {result.annual_return:.2%}")
        logger.info(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
        logger.info(f"   Max Drawdown: {result.max_drawdown:.2%}")
        logger.info(f"   Win Rate: {result.win_rate:.2%}")

        # Trading statistics
        logger.info("\n📈 Trading Statistics:")
        logger.info(f"   Total Trades: {result.total_trades}")
        winning_trades = int(result.total_trades * result.win_rate)
        losing_trades = result.total_trades - winning_trades
        logger.info(f"   Winning Trades: {winning_trades}")
        logger.info(f"   Losing Trades: {losing_trades}")
        logger.info(f"   Avg Win: {result.avg_win:.2%}")
        logger.info(f"   Avg Loss: {result.avg_loss:.2%}")
        logger.info(f"   Profit Factor: {result.profit_factor:.2f}")

        # Portfolio value
        logger.info("\n💰 Portfolio Value:")
        logger.info(f"   Initial Capital: {config.initial_capital:,.0f} KRW")
        final_value = result.equity_curve.iloc[-1] if len(result.equity_curve) > 0 else config.initial_capital
        total_profit = final_value - config.initial_capital
        logger.info(f"   Final Value: {final_value:,.0f} KRW")
        logger.info(f"   Total Profit: {total_profit:,.0f} KRW")

        # Success criteria (from CLAUDE.md)
        logger.info("\n✅ Success Criteria (CLAUDE.md):")
        logger.info(f"   Sharpe Ratio > 1.5: {'✅' if result.sharpe_ratio > 1.5 else '❌'} ({result.sharpe_ratio:.2f})")
        logger.info(f"   Max Drawdown < 15%: {'✅' if abs(result.max_drawdown) < 0.15 else '❌'} ({result.max_drawdown:.2%})")
        logger.info(f"   Win Rate > 55%: {'✅' if result.win_rate > 0.55 else '❌'} ({result.win_rate:.2%})")
        logger.info(f"   Total Trades > 100: {'✅' if result.total_trades > 100 else '❌'} ({result.total_trades})")

        logger.info("\n" + "=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # Run backtest
    result = main()
