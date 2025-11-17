#!/usr/bin/env python3
"""
HKEX ETF List Generator

Generates a list of major HKEX ETFs for backfill.

Usage:
    python3 scripts/fetch_hkex_etfs.py --output data/hk_etfs.csv
"""

import pandas as pd
import argparse
from datetime import datetime
from pathlib import Path


# Major HKEX ETFs (curated list)
MAJOR_HKEX_ETFS = [
    # Hang Seng Index ETFs
    {"ticker": "2800.HK", "name": "Tracker Fund of Hong Kong", "category": "HK Equities"},
    {"ticker": "2828.HK", "name": "Hang Seng China Enterprises ETF", "category": "China H-Shares"},
    {"ticker": "3001.HK", "name": "iShares Core Hang Seng Index ETF", "category": "HK Equities"},

    # China A-Shares ETFs
    {"ticker": "2822.HK", "name": "CSOP A50 ETF", "category": "China A-Shares"},
    {"ticker": "2823.HK", "name": "iShares A50 China", "category": "China A-Shares"},
    {"ticker": "2836.HK", "name": "iShares Core CSI 300", "category": "China A-Shares"},
    {"ticker": "3019.HK", "name": "X Tracker CSI 300 China A Shares ETF", "category": "China A-Shares"},
    {"ticker": "3031.HK", "name": "CSOP Source FTSE China A50 ETF", "category": "China A-Shares"},
    {"ticker": "3188.HK", "name": "CAM CSI 300 Index ETF", "category": "China A-Shares"},

    # Technology ETFs
    {"ticker": "3033.HK", "name": "CSOP Hang Seng Tech Index ETF", "category": "Technology"},
    {"ticker": "3067.HK", "name": "X Tracker CSI300 Healthcare Index ETF", "category": "Healthcare"},
    {"ticker": "3036.HK", "name": "CSOP USD Money Market ETF", "category": "Fixed Income"},

    # US Market ETFs
    {"ticker": "2843.HK", "name": "PowerShares QQQ", "category": "US Tech"},
    {"ticker": "3140.HK", "name": "iShares S&P 500 Index ETF", "category": "US Equities"},

    # Commodities & Fixed Income
    {"ticker": "2840.HK", "name": "SPDR Gold Shares", "category": "Gold"},
    {"ticker": "3110.HK", "name": "Nikko AM SGD Investment Grade Corp Bond ETF", "category": "Fixed Income"},

    # Leveraged & Inverse ETFs
    {"ticker": "7200.HK", "name": "F CSOP HSI Daily (2x) Leveraged Product", "category": "Leveraged"},
    {"ticker": "7300.HK", "name": "F CSOP HSI Daily (-1x) Inverse Product", "category": "Inverse"},

    # REIT ETFs
    {"ticker": "3193.HK", "name": "Vanguard FTSE HK Index ETF", "category": "HK REIT"},

    # Additional Major ETFs
    {"ticker": "2801.HK", "name": "iShares S&P/HKEx LargeCap ETF", "category": "HK Equities"},
    {"ticker": "2802.HK", "name": "iShares S&P BSE SENSEX India ETF", "category": "India"},
    {"ticker": "2804.HK", "name": "iShares FTSE A50 China ETF", "category": "China A-Shares"},
    {"ticker": "2805.HK", "name": "Premia FactSet UK ETF", "category": "UK"},
    {"ticker": "2806.HK", "name": "iShares EURO STOXX 50 ETF", "category": "Europe"},
    {"ticker": "2807.HK", "name": "iShares FTSE 100 Index ETF", "category": "UK"},
    {"ticker": "2810.HK", "name": "ABF Hong Kong Bond Index Fund", "category": "Fixed Income"},
    {"ticker": "2812.HK", "name": "CSOP USD Ultra Short-Term Money Market ETF", "category": "Fixed Income"},
    {"ticker": "2819.HK", "name": "ABF Pan Asia Bond Index Fund", "category": "Fixed Income"},
    {"ticker": "2820.HK", "name": "Value Gold ETF", "category": "Gold"},
    {"ticker": "2821.HK", "name": "X FANG+ ETF", "category": "US Tech"},
    {"ticker": "2825.HK", "name": "Value HS300 Index ETF", "category": "China A-Shares"},
    {"ticker": "2826.HK", "name": "Global X Hang Seng ESG ETF", "category": "ESG"},
    {"ticker": "2827.HK", "name": "Wise SSE 50 China Tracker", "category": "China A-Shares"},
    {"ticker": "2829.HK", "name": "Ishares Core Hang Seng China Enterprises ETF", "category": "China H-Shares"},
    {"ticker": "2830.HK", "name": "iShares MSCI AC Asia ex Japan Index ETF", "category": "Asia"},
    {"ticker": "2831.HK", "name": "iShares MSCI Japan Index ETF", "category": "Japan"},
    {"ticker": "2832.HK", "name": "BMO Nasdaq 100 Equity Index ETF", "category": "US Tech"},
    {"ticker": "2833.HK", "name": "Hang Seng Investment Management Hang Seng China Enterprises Index ETF", "category": "China H-Shares"},
    {"ticker": "2834.HK", "name": "iShares MSCI Asia ex Japan Index ETF", "category": "Asia"},
    {"ticker": "2838.HK", "name": "Harvest CSI 300 Index ETF", "category": "China A-Shares"},
    {"ticker": "2839.HK", "name": "Bosera FTSE China A50 Index ETF", "category": "China A-Shares"},
    {"ticker": "2846.HK", "name": "Ishares Core CSI 500 Small Cap ETF", "category": "China A-Shares"},
    {"ticker": "2847.HK", "name": "Ishares Core SZSE ChiNext", "category": "China A-Shares"},
    {"ticker": "3002.HK", "name": "iShares Core MSCI China Index ETF", "category": "China"},
    {"ticker": "3003.HK", "name": "MBB HKD Money Market ETF", "category": "Fixed Income"},
    {"ticker": "3009.HK", "name": "BMO Nasdaq 100 Equity Index Daily (-1x) Inverse Product", "category": "Inverse"},
    {"ticker": "3010.HK", "name": "ICBC CSI100 Index ETF", "category": "China A-Shares"},
    {"ticker": "3015.HK", "name": "CSOP Hang Seng TECH Gross Total Return Index Daily (2x) Leveraged Product", "category": "Leveraged"},
    {"ticker": "3024.HK", "name": "CSOP SZSE ChiNext ETF", "category": "China A-Shares"},
    {"ticker": "3032.HK", "name": "Ping An of China CSI HK Dividend ETF", "category": "Dividend"},
    {"ticker": "3037.HK", "name": "CSOP Hong Kong Dollar Money Market ETF", "category": "Fixed Income"},
]


def main():
    parser = argparse.ArgumentParser(description='Generate HKEX ETF list')
    parser.add_argument('--output', type=str, default='data/hk_etfs.csv',
                        help='Output CSV file path (default: data/hk_etfs.csv)')
    args = parser.parse_args()

    # Create DataFrame
    df = pd.DataFrame(MAJOR_HKEX_ETFS)
    df['source'] = 'Curated'
    df['fetched_at'] = datetime.now()

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"✅ Generated {len(df)} HKEX ETF tickers")
    print(f"📂 Saved to: {output_path}")
    print(f"\nCategory Distribution:")
    print(df['category'].value_counts().to_string())


if __name__ == "__main__":
    main()
