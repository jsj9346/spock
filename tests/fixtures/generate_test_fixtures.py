"""
Generate test fixtures for integration testing.

Extracts representative OHLCV data from production database for:
- 005930 (Samsung Electronics - KR)
- 035720 (Kakao Corp - KR)
- AAPL (Apple Inc - US)
- TSLA (Tesla Inc - US)
- 252140 (KODEX 200 ETF - KR)

Usage:
    python tests/fixtures/generate_test_fixtures.py
"""
import asyncio
import asyncpg
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


async def generate_fixtures():
    """Extract test data from production database."""
    # Connect to production database
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='quant_platform',
        user='13ruce'
    )

    # Define test tickers (all KR tickers with 2024 data)
    test_tickers = [
        ('005930', 'KR', 'Samsung Electronics'),
        ('035720', 'KR', 'Kakao Corp'),
        ('032830', 'KR', 'Samsung Life Insurance'),
        ('034020', 'KR', 'Doosan Heavy Industries'),
        ('006800', 'KR', 'Mirae Asset Securities')
    ]

    # Date range: 1 year of data (2024-01-01 to 2024-12-31)
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    fixtures_dir = Path(__file__).parent

    for ticker, region, name in test_tickers:
        print(f"Extracting data for {ticker} ({name})...")

        # Query OHLCV data
        query = """
            SELECT
                date,
                open,
                high,
                low,
                close,
                volume
            FROM ohlcv_data
            WHERE ticker = $1
              AND region = $2
              AND timeframe = '1d'
              AND date >= $3
              AND date <= $4
            ORDER BY date
        """

        rows = await conn.fetch(query, ticker, region, start_date, end_date)

        if not rows:
            print(f"  ⚠️  No data found for {ticker} in {region}")
            continue

        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

        # Save to CSV
        filename = fixtures_dir / f"ohlcv_{ticker.lower()}_2024.csv"
        df.to_csv(filename, index=False)

        print(f"  ✅ Saved {len(df)} rows to {filename.name}")

    await conn.close()
    print("\n✅ Test fixture generation complete!")


if __name__ == "__main__":
    asyncio.run(generate_fixtures())
