#!/usr/bin/env python3
"""
HSI Constituents Fetcher

Fetches Hang Seng Index constituent list from reliable sources.

Data Sources (priority order):
1. Wikipedia HSI page (most up-to-date)
2. Hardcoded list of major HSI stocks (fallback)

Usage:
    python3 scripts/fetch_hsi_constituents.py --output data/hk_hsi_constituents.csv
"""

import argparse
import logging
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HSIConstituentsFetcher:
    """Fetch Hang Seng Index constituents"""

    # Fallback: Major HSI constituents (as of 2024)
    FALLBACK_HSI_TICKERS = [
        # Technology & Internet
        {'ticker': '0700', 'name': 'Tencent Holdings', 'sector': 'Technology'},
        {'ticker': '9988', 'name': 'Alibaba Group', 'sector': 'Technology'},
        {'ticker': '3690', 'name': 'Meituan', 'sector': 'Consumer Services'},
        {'ticker': '1810', 'name': 'Xiaomi Corporation', 'sector': 'Technology'},
        {'ticker': '9618', 'name': 'JD.com', 'sector': 'Consumer Services'},
        {'ticker': '9999', 'name': 'NetEase', 'sector': 'Technology'},
        {'ticker': '9961', 'name': 'Trip.com Group', 'sector': 'Consumer Services'},

        # Financials
        {'ticker': '0005', 'name': 'HSBC Holdings', 'sector': 'Financials'},
        {'ticker': '0388', 'name': 'Hong Kong Exchanges', 'sector': 'Financials'},
        {'ticker': '0011', 'name': 'Hang Seng Bank', 'sector': 'Financials'},
        {'ticker': '1299', 'name': 'AIA Group', 'sector': 'Financials'},
        {'ticker': '2318', 'name': 'Ping An Insurance', 'sector': 'Financials'},
        {'ticker': '2628', 'name': 'China Life Insurance', 'sector': 'Financials'},
        {'ticker': '1398', 'name': 'ICBC', 'sector': 'Financials'},
        {'ticker': '0939', 'name': 'China Construction Bank', 'sector': 'Financials'},
        {'ticker': '3988', 'name': 'Bank of China', 'sector': 'Financials'},
        {'ticker': '1288', 'name': 'Agricultural Bank of China', 'sector': 'Financials'},

        # Telecommunications
        {'ticker': '0941', 'name': 'China Mobile', 'sector': 'Telecommunications'},
        {'ticker': '0762', 'name': 'China Unicom', 'sector': 'Telecommunications'},
        {'ticker': '0728', 'name': 'China Telecom', 'sector': 'Telecommunications'},

        # Energy
        {'ticker': '0883', 'name': 'CNOOC', 'sector': 'Energy'},
        {'ticker': '0386', 'name': 'China Petroleum & Chemical', 'sector': 'Energy'},
        {'ticker': '0857', 'name': 'PetroChina', 'sector': 'Energy'},
        {'ticker': '2688', 'name': 'ENN Energy Holdings', 'sector': 'Energy'},

        # Real Estate & Construction
        {'ticker': '1109', 'name': 'China Resources Land', 'sector': 'Real Estate'},
        {'ticker': '0016', 'name': 'Sun Hung Kai Properties', 'sector': 'Real Estate'},
        {'ticker': '0012', 'name': 'Henderson Land Development', 'sector': 'Real Estate'},
        {'ticker': '0688', 'name': 'China Overseas Land', 'sector': 'Real Estate'},
        {'ticker': '1997', 'name': 'Wharf Real Estate', 'sector': 'Real Estate'},

        # Consumer Goods
        {'ticker': '1211', 'name': 'BYD Company', 'sector': 'Consumer Goods'},
        {'ticker': '0175', 'name': 'Geely Automobile', 'sector': 'Consumer Goods'},
        {'ticker': '2382', 'name': 'Sunny Optical Technology', 'sector': 'Technology'},
        {'ticker': '0291', 'name': 'China Resources Beer', 'sector': 'Consumer Goods'},

        # Healthcare
        {'ticker': '2269', 'name': 'Wuxi Biologics', 'sector': 'Healthcare'},
        {'ticker': '6618', 'name': 'JD Health International', 'sector': 'Healthcare'},
        {'ticker': '1093', 'name': 'CSPC Pharmaceutical', 'sector': 'Healthcare'},
        {'ticker': '1177', 'name': 'Sino Biopharmaceutical', 'sector': 'Healthcare'},

        # Utilities
        {'ticker': '0002', 'name': 'CLP Holdings', 'sector': 'Utilities'},
        {'ticker': '0003', 'name': 'Hong Kong & China Gas', 'sector': 'Utilities'},
        {'ticker': '0006', 'name': 'Power Assets Holdings', 'sector': 'Utilities'},

        # Materials & Industrials
        {'ticker': '0968', 'name': 'Xinyi Solar Holdings', 'sector': 'Materials'},
        {'ticker': '1038', 'name': 'CK Infrastructure', 'sector': 'Industrials'},
        {'ticker': '0669', 'name': 'Techtronic Industries', 'sector': 'Industrials'},
        {'ticker': '0772', 'name': 'China Literature', 'sector': 'Media'},

        # Retail & Services
        {'ticker': '0027', 'name': 'Galaxy Entertainment', 'sector': 'Consumer Services'},
        {'ticker': '0020', 'name': 'Wheelock and Company', 'sector': 'Conglomerates'},
        {'ticker': '0288', 'name': 'WH Group', 'sector': 'Consumer Goods'},
    ]

    def fetch_from_wikipedia(self) -> pd.DataFrame:
        """
        Fetch HSI constituents from Wikipedia

        Returns:
            DataFrame with columns: ticker, name, sector
        """
        try:
            url = "https://en.wikipedia.org/wiki/Hang_Seng_Index"
            logger.info(f"Fetching HSI constituents from Wikipedia: {url}")

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the constituents table
            # Wikipedia structure: Look for table with class 'wikitable sortable'
            tables = soup.find_all('table', {'class': 'wikitable'})

            if not tables:
                logger.warning("No wikitable found on Wikipedia page")
                return None

            # Parse the first relevant table
            for table in tables:
                headers = [th.text.strip() for th in table.find_all('th')]

                # Check if this is the constituents table
                if 'Code' in headers or 'Stock code' in headers:
                    rows = []
                    for tr in table.find_all('tr')[1:]:  # Skip header
                        cells = tr.find_all('td')
                        if len(cells) >= 3:
                            ticker = cells[0].text.strip()
                            name = cells[1].text.strip()
                            sector = cells[2].text.strip() if len(cells) > 2 else 'Unknown'

                            # Clean ticker (remove ".HK" suffix if present)
                            ticker = ticker.replace('.HK', '').strip()

                            # Validate ticker format (4-digit numeric)
                            if ticker.isdigit() and len(ticker) == 4:
                                rows.append({
                                    'ticker': ticker,
                                    'name': name,
                                    'sector': sector
                                })

                    if rows:
                        df = pd.DataFrame(rows)
                        logger.info(f"✅ Fetched {len(df)} HSI constituents from Wikipedia")
                        return df

            logger.warning("Could not find constituents table in Wikipedia")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch from Wikipedia: {e}")
            return None

    def get_fallback_list(self) -> pd.DataFrame:
        """
        Return hardcoded fallback HSI list

        Returns:
            DataFrame with columns: ticker, name, sector
        """
        logger.info("Using fallback HSI constituent list")
        df = pd.DataFrame(self.FALLBACK_HSI_TICKERS)
        logger.info(f"✅ Loaded {len(df)} HSI constituents from fallback list")
        return df

    def fetch(self) -> pd.DataFrame:
        """
        Fetch HSI constituents with fallback strategy

        Returns:
            DataFrame with columns: ticker, name, sector
        """
        # Try Wikipedia first
        df = self.fetch_from_wikipedia()

        # Fallback to hardcoded list
        if df is None or df.empty:
            logger.warning("Wikipedia fetch failed, using fallback list")
            df = self.get_fallback_list()

        # Add metadata
        df['source'] = 'Wikipedia' if df is not None else 'Fallback'
        df['fetched_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Ensure ticker format (4-digit with leading zeros)
        df['ticker'] = df['ticker'].apply(lambda x: x.zfill(4))

        return df


def main():
    parser = argparse.ArgumentParser(description='Fetch HSI constituents')
    parser.add_argument('--output', type=str, required=True,
                        help='Output CSV file path (e.g., data/hk_hsi_constituents.csv)')
    parser.add_argument('--format', type=str, default='csv', choices=['csv', 'json'],
                        help='Output format (default: csv)')

    args = parser.parse_args()

    # Fetch constituents
    fetcher = HSIConstituentsFetcher()
    df = fetcher.fetch()

    # Save to file
    if args.format == 'csv':
        df.to_csv(args.output, index=False)
        logger.info(f"✅ Saved {len(df)} HSI constituents to: {args.output}")
    elif args.format == 'json':
        df.to_json(args.output, orient='records', indent=2)
        logger.info(f"✅ Saved {len(df)} HSI constituents to: {args.output}")

    # Print summary
    print("\n" + "="*60)
    print("HSI Constituents Fetch Summary")
    print("="*60)
    print(f"Total constituents: {len(df)}")
    print(f"Output file: {args.output}")
    print(f"Sample tickers: {', '.join(df['ticker'].head(10).tolist())}")
    print(f"\nSector distribution:")
    print(df['sector'].value_counts().to_string())
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
