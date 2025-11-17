#!/usr/bin/env python3
"""
HK Data Quality Validation Script

Validates OHLCV data quality for HK market tickers.

Usage:
    # Validate all HK tickers
    python3 scripts/validate_hk_data_quality.py --report

    # Validate specific tier
    python3 scripts/validate_hk_data_quality.py --tier 1 --report

    # Validate specific tickers
    python3 scripts/validate_hk_data_quality.py --tickers 0700,9988,0941 --report
"""

import argparse
import logging
import sys
import os
from datetime import datetime
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_quality.hk_validator import validate_hk_market_data, HKDataQualityValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_tier_tickers(tier: int) -> list:
    """Get tickers for a specific tier"""
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

    if tier == 1:
        # HSI constituents - load from file or use hardcoded list
        if os.path.exists('data/hk_hsi_constituents.csv'):
            df = pd.read_csv('data/hk_hsi_constituents.csv')
            tickers = df['ticker'].astype(str).str.zfill(4).tolist()
        else:
            # Fallback to default HSI list
            from modules.market_adapters.hk_adapter import HKAdapter
            tickers = HKAdapter.DEFAULT_HK_TICKERS
    else:
        raise ValueError(f"Tier {tier} not yet supported. Use --tier 1 or --tickers option.")

    conn.close()
    return tickers


def main():
    parser = argparse.ArgumentParser(description='HK Data Quality Validation')
    parser.add_argument('--tier', type=int, default=None, choices=[1, 2, 3, 4],
                        help='Validate specific tier (1=HSI)')
    parser.add_argument('--tickers', type=str, default=None,
                        help='Comma-separated list of tickers to validate (e.g., 0700,9988,0941)')
    parser.add_argument('--report', action='store_true',
                        help='Generate detailed report')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path (default: reports/hk_quality_validation_YYYYMMDD.csv)')

    args = parser.parse_args()

    # Determine tickers to validate
    if args.tickers:
        tickers = [t.strip().zfill(4) for t in args.tickers.split(',')]
        logger.info(f"Validating {len(tickers)} specified tickers")
    elif args.tier:
        tickers = get_tier_tickers(args.tier)
        logger.info(f"Validating Tier {args.tier}: {len(tickers)} tickers")
    else:
        tickers = None
        logger.info("Validating all HK tickers with OHLCV data")

    # Run validation
    logger.info(f"\n{'='*60}")
    logger.info("Starting HK Data Quality Validation")
    logger.info(f"{'='*60}\n")

    results_df = validate_hk_market_data(tickers=tickers)

    # Print summary
    print("\n" + "="*60)
    print("HK Data Quality Validation Summary")
    print("="*60)
    print(f"Total tickers validated: {len(results_df)}")

    if len(results_df) > 0:
        print(f"Passed: {results_df['passed'].sum()} ({results_df['passed'].mean():.1%})")
        print(f"Failed: {(~results_df['passed']).sum()}")

        print(f"\nAverage Scores:")
        print(f"  Completeness: {results_df['completeness_score'].mean():.2%}")
        print(f"  Validity: {results_df['validity_score'].mean():.2%}")
        print(f"  Consistency: {results_df['consistency_score'].mean():.2%}")
        print(f"  Volume: {results_df['volume_score'].mean():.2%}")

        # Failed tickers
        failed_df = results_df[~results_df['passed']]
        if len(failed_df) > 0:
            print(f"\nFailed Tickers ({len(failed_df)}):")
            for idx, row in failed_df.iterrows():
                print(f"  {row['ticker']}: completeness={row['completeness_score']:.2%}, "
                      f"validity={row['validity_score']:.2%}, "
                      f"consistency={row['consistency_score']:.2%}")
    else:
        print("No tickers validated. Check if HK OHLCV data exists in database.")

    print("="*60 + "\n")

    # Save report
    if args.report and len(results_df) > 0:
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'reports/hk_quality_validation_{timestamp}.csv'

        os.makedirs('reports', exist_ok=True)
        results_df.to_csv(output_file, index=False)
        logger.info(f"✅ Report saved to: {output_file}")

        # Also save JSON for anomalies
        json_file = output_file.replace('.csv', '.json')
        results_df.to_json(json_file, orient='records', indent=2)
        logger.info(f"✅ JSON report saved to: {json_file}")

    # Exit with error code if validation failed significantly
    if len(results_df) > 0:
        pass_rate = results_df['passed'].mean()
        if pass_rate < 0.9:
            logger.warning(f"⚠️ Validation pass rate < 90% ({pass_rate:.1%}). Exiting with error code 1.")
            sys.exit(1)
        else:
            logger.info(f"✅ Validation completed successfully! Pass rate: {pass_rate:.1%}")
            sys.exit(0)
    else:
        logger.warning("⚠️ No tickers validated. Check HK OHLCV data availability.")
        sys.exit(1)


if __name__ == "__main__":
    main()
