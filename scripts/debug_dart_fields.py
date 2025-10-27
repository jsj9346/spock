#!/usr/bin/env python3
"""Debug script to see what fields DART API returns"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from modules.dart_api_client import DARTApiClient
from modules.mappers.kr_corporate_id_mapper import KRCorporateIDMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Initialize
    dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))
    mapper = KRCorporateIDMapper()

    # Get corp code for Samsung
    ticker = '005930'
    corp_code = mapper.get_corporate_id(ticker)

    logger.info(f"Corp code for {ticker}: {corp_code}")

    # Get metrics
    metrics = dart.get_fundamental_metrics(ticker, corp_code=corp_code)

    if metrics:
        logger.info(f"\n{'='*70}")
        logger.info(f"Fields returned by DART API: {len(metrics)}")
        logger.info(f"{'='*70}")
        for i, (key, value) in enumerate(metrics.items(), 1):
            logger.info(f"{i:2d}. {key:30s} = {value}")
        logger.info(f"{'='*70}")

        # Expected fields in database
        db_fields = [
            'ticker', 'date', 'period_type', 'fiscal_year',
            'shares_outstanding', 'market_cap', 'close_price',
            'per', 'pbr', 'psr', 'pcr', 'ev', 'ev_ebitda',
            'dividend_yield', 'dividend_per_share',
            'total_assets', 'total_liabilities', 'total_equity',
            'revenue', 'operating_profit', 'net_income', 'ebitda',
            'cogs', 'gross_profit', 'depreciation', 'interest_expense',
            'current_assets', 'current_liabilities', 'inventory',
            'accounts_receivable', 'cash_and_equivalents',
            'operating_cash_flow', 'capital_expenditure',
            'free_float_percentage', 'created_at', 'data_source'
        ]

        logger.info(f"\nExpected database fields: {len(db_fields)}")

        # Find extra fields
        extra_fields = [k for k in metrics.keys() if k not in db_fields]
        missing_fields = [k for k in db_fields if k not in metrics.keys()]

        if extra_fields:
            logger.info(f"\n⚠️ Extra fields (not in DB schema): {extra_fields}")

        if missing_fields:
            logger.info(f"\nℹ️ Missing fields (in DB but not returned): {missing_fields}")
    else:
        logger.error(f"Failed to get metrics for {ticker}")

if __name__ == '__main__':
    main()
