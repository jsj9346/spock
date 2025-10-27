#!/usr/bin/env python3
"""
Week 3: Define KR Stock Universe
KOSPI 200 + KOSDAQ 150 ticker selection for historical backfill

Selection Criteria:
- KOSPI 200: Top 200 by market cap
- KOSDAQ 150: Top 150 by liquidity + market cap
- Exclusions: SPACs, preferred stocks, delisting stocks

Output: data/kr_universe_week3.csv

Usage:
    python3 scripts/week3_define_universe.py
    python3 scripts/week3_define_universe.py --kospi 200 --kosdaq 150
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    logger.warning("pykrx not installed. Install with: pip install pykrx")
    PYKRX_AVAILABLE = False

from modules.db_manager_postgres import PostgresDatabaseManager


class KRUniverseDefiner:
    """Define Korean stock universe for backtesting"""

    def __init__(self):
        """Initialize universe definer"""
        try:
            self.db = PostgresDatabaseManager()
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            self.db = None
        self.exclusion_keywords = [
            'SPAC', '스팩', '우선주', 'P', '1우', '2우', '3우',
            '정리매매', '관리종목'
        ]

    def get_kospi_200(self, reference_date: str = None) -> pd.DataFrame:
        """
        Get KOSPI 200 constituents using pykrx

        Args:
            reference_date: YYYYMMDD format (default: yesterday)

        Returns:
            DataFrame with columns: ticker, name, market_cap, exchange
        """
        if not PYKRX_AVAILABLE:
            raise RuntimeError("pykrx required for universe definition")

        if reference_date is None:
            reference_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        logger.info(f"Fetching KOSPI 200 constituents for {reference_date}")

        try:
            # Get KOSPI market data
            kospi_tickers = stock.get_market_ticker_list(reference_date, market="KOSPI")

            # Get market cap for all KOSPI stocks
            market_caps = []
            for ticker in kospi_tickers:
                try:
                    cap = stock.get_market_cap_by_ticker(reference_date, market="KOSPI")
                    if ticker in cap.index:
                        market_caps.append({
                            'ticker': ticker,
                            'name': stock.get_market_ticker_name(ticker),
                            'market_cap': cap.loc[ticker, '시가총액'],
                            'exchange': 'KOSPI'
                        })
                except Exception as e:
                    logger.warning(f"Failed to get market cap for {ticker}: {e}")
                    continue

            df = pd.DataFrame(market_caps)

            # Filter exclusions
            df = self._filter_exclusions(df)

            # Sort by market cap and take top 200
            df = df.sort_values('market_cap', ascending=False).head(200)

            logger.info(f"Selected {len(df)} KOSPI tickers (target: 200)")
            return df

        except Exception as e:
            logger.error(f"Error fetching KOSPI 200: {e}")
            raise

    def get_kosdaq_150(self, reference_date: str = None) -> pd.DataFrame:
        """
        Get KOSDAQ 150 constituents based on liquidity + market cap

        Args:
            reference_date: YYYYMMDD format (default: yesterday)

        Returns:
            DataFrame with columns: ticker, name, market_cap, exchange
        """
        if not PYKRX_AVAILABLE:
            raise RuntimeError("pykrx required for universe definition")

        if reference_date is None:
            reference_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        logger.info(f"Fetching KOSDAQ 150 constituents for {reference_date}")

        try:
            # Get KOSDAQ market data
            kosdaq_tickers = stock.get_market_ticker_list(reference_date, market="KOSDAQ")

            # Get trading value (liquidity proxy) and market cap
            candidates = []
            for ticker in kosdaq_tickers:
                try:
                    # Get 1-month average trading value
                    start_date = (datetime.strptime(reference_date, '%Y%m%d') - timedelta(days=30)).strftime('%Y%m%d')
                    ohlcv = stock.get_market_ohlcv_by_date(start_date, reference_date, ticker)

                    if ohlcv.empty:
                        continue

                    avg_trading_value = (ohlcv['종가'] * ohlcv['거래량']).mean()

                    # Get market cap
                    cap = stock.get_market_cap_by_ticker(reference_date, market="KOSDAQ")

                    if ticker in cap.index:
                        candidates.append({
                            'ticker': ticker,
                            'name': stock.get_market_ticker_name(ticker),
                            'market_cap': cap.loc[ticker, '시가총액'],
                            'avg_trading_value': avg_trading_value,
                            'exchange': 'KOSDAQ'
                        })
                except Exception as e:
                    logger.warning(f"Failed to process KOSDAQ ticker {ticker}: {e}")
                    continue

            df = pd.DataFrame(candidates)

            # Filter exclusions
            df = self._filter_exclusions(df)

            # Score: 60% market cap + 40% liquidity
            df['market_cap_rank'] = df['market_cap'].rank(ascending=False, pct=True)
            df['liquidity_rank'] = df['avg_trading_value'].rank(ascending=False, pct=True)
            df['composite_score'] = 0.6 * df['market_cap_rank'] + 0.4 * df['liquidity_rank']

            # Sort by composite score and take top 150
            df = df.sort_values('composite_score', ascending=False).head(150)

            # Clean up scoring columns
            df = df[['ticker', 'name', 'market_cap', 'exchange']]

            logger.info(f"Selected {len(df)} KOSDAQ tickers (target: 150)")
            return df

        except Exception as e:
            logger.error(f"Error fetching KOSDAQ 150: {e}")
            raise

    def _filter_exclusions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter out excluded stocks

        Args:
            df: DataFrame with 'name' column

        Returns:
            Filtered DataFrame
        """
        initial_count = len(df)

        # Filter by name keywords
        for keyword in self.exclusion_keywords:
            df = df[~df['name'].str.contains(keyword, na=False)]

        # Filter delisted stocks (if delisting_date column exists)
        if 'delisting_date' in df.columns:
            df = df[df['delisting_date'].isna()]

        filtered_count = initial_count - len(df)
        logger.info(f"Filtered {filtered_count} exclusions ({len(df)} remaining)")

        return df

    def save_universe(self, universe: pd.DataFrame, output_path: str):
        """
        Save universe to CSV

        Args:
            universe: DataFrame with ticker list
            output_path: Output CSV path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Add metadata
        universe['created_at'] = datetime.now()
        universe['data_source'] = 'pykrx'

        universe.to_csv(output_path, index=False)
        logger.info(f"Universe saved to: {output_path}")
        logger.info(f"Total tickers: {len(universe)}")

    def validate_against_db(self, universe: pd.DataFrame):
        """
        Validate universe tickers exist in database

        Args:
            universe: DataFrame with ticker list
        """
        if self.db is None:
            logger.warning("No database connection - skipping validation")
            return

        logger.info("Validating universe against database...")

        tickers = universe['ticker'].tolist()
        placeholders = ','.join(['%s'] * len(tickers))
        query = f"""
        SELECT ticker, name, exchange
        FROM tickers
        WHERE ticker IN ({placeholders})
        AND region = 'KR'
        """

        db_tickers_list = self.db.execute_query(query, tuple(tickers))
        db_ticker_set = set([row['ticker'] for row in db_tickers_list])

        if len(db_ticker_set) < len(tickers):
            missing = set(tickers) - db_ticker_set
            logger.warning(f"Missing {len(missing)} tickers in database: {list(missing)[:10]}")
        else:
            logger.info(f"✅ All {len(tickers)} tickers found in database")


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Define KR stock universe')
    parser.add_argument('--kospi', type=int, default=200, help='KOSPI ticker count')
    parser.add_argument('--kosdaq', type=int, default=150, help='KOSDAQ ticker count')
    parser.add_argument('--reference-date', type=str, help='Reference date (YYYYMMDD)')
    parser.add_argument('--output', type=str, default='data/kr_universe_week3.csv',
                       help='Output CSV path')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("KR STOCK UNIVERSE DEFINITION")
    logger.info("=" * 80)
    logger.info(f"Target: KOSPI {args.kospi} + KOSDAQ {args.kosdaq}")

    # Initialize definer
    definer = KRUniverseDefiner()

    # Get KOSPI constituents
    kospi_df = definer.get_kospi_200(args.reference_date)
    logger.info(f"KOSPI: {len(kospi_df)} tickers")

    # Get KOSDAQ constituents
    kosdaq_df = definer.get_kosdaq_150(args.reference_date)
    logger.info(f"KOSDAQ: {len(kosdaq_df)} tickers")

    # Combine universe
    universe = pd.concat([kospi_df, kosdaq_df], ignore_index=True)

    # Save to CSV
    definer.save_universe(universe, args.output)

    # Summary
    print("\n" + "=" * 80)
    print("UNIVERSE SUMMARY")
    print("=" * 80)
    print(f"Total Tickers:    {len(universe):>6,}")
    print(f"  KOSPI:          {len(kospi_df):>6,}")
    print(f"  KOSDAQ:         {len(kosdaq_df):>6,}")
    print(f"\nOutput: {args.output}")
    print("=" * 80)

    logger.info("✅ Universe definition completed successfully")


if __name__ == '__main__':
    main()
