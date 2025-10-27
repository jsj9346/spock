#!/usr/bin/env python3
"""
Debug script to investigate DART API net_income = 0 issue

Fetches actual DART API responses to examine:
1. Field names used for net_income
2. Multiple occurrences of same account
3. Differences between annual vs semi-annual reports
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.dart_api_client import DARTApiClient
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

def debug_ticker_net_income(ticker: str, year: int, reprt_code: str):
    """
    Debug net_income parsing for a specific ticker

    Args:
        ticker: Ticker symbol (e.g., '005930')
        year: Fiscal year (e.g., 2024)
        reprt_code: Report code ('11011'=Annual, '11012'=Semi-annual)
    """
    load_dotenv()
    dart_api_key = os.getenv('DART_API_KEY')

    if not dart_api_key:
        logger.error("DART_API_KEY not found in environment")
        return

    client = DARTApiClient(dart_api_key)

    # Get company code from ticker
    corp_code = client._get_corp_code_from_ticker(ticker)
    if not corp_code:
        logger.error(f"Could not find corp_code for ticker {ticker}")
        return

    logger.info(f"\n{'='*70}")
    logger.info(f"Debugging: {ticker} | Year: {year} | Report: {reprt_code}")
    logger.info(f"{'='*70}\n")

    # Fetch financial statements
    try:
        response = client._fetch_financial_statements(corp_code, year, reprt_code)

        if response.get('status') != '000':
            logger.error(f"API error: {response.get('message')}")
            return

        items = response.get('list', [])
        logger.info(f"Total items returned: {len(items)}")

        # Find all occurrences of net_income related fields
        net_income_fields = [
            '당기순이익(손실)',
            '당기순이익',
            '당기순손실',
            '반기순이익',
            '반기순이익(손실)',
            '분기순이익',
            '분기순이익(손실)'
        ]

        logger.info(f"\n{'='*70}")
        logger.info("Searching for net_income related fields:")
        logger.info(f"{'='*70}\n")

        found_items = []
        for item in items:
            account_nm = item.get('account_nm', '')
            if any(field in account_nm for field in net_income_fields):
                amount = item.get('thstrm_amount', '0').replace(',', '')
                found_items.append({
                    'account_nm': account_nm,
                    'amount': amount,
                    'sj_div': item.get('sj_div', ''),  # 재무제표 구분 (BS, IS, CIS, CF, SCE)
                    'sj_nm': item.get('sj_nm', '')     # 재무제표명
                })

        if found_items:
            logger.info(f"Found {len(found_items)} occurrences:\n")
            for i, item in enumerate(found_items, 1):
                logger.info(f"  [{i}] {item['account_nm']:<25} | Amount: {item['amount']:>20} | Statement: {item['sj_div']:<5} ({item['sj_nm']})")
        else:
            logger.warning("❌ No net_income fields found!")

        # Show what FIRST occurrence logic would select
        logger.info(f"\n{'='*70}")
        logger.info("FIRST occurrence logic (current implementation):")
        logger.info(f"{'='*70}\n")

        item_lookup = {}
        for item in items:
            account_name = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0').replace(',', '')

            if account_name not in item_lookup:
                try:
                    item_lookup[account_name] = float(amount)
                except (ValueError, TypeError):
                    pass

        net_income = item_lookup.get('당기순이익(손실)', 0) or item_lookup.get('당기순이익', 0)
        logger.info(f"Selected net_income: {net_income:,.0f}")

        # Show revenue and operating_profit for context
        revenue = (item_lookup.get('영업수익', 0) or
                   item_lookup.get('매출액', 0) or
                   item_lookup.get('수익(매출액)', 0) or
                   item_lookup.get('매출', 0))
        operating_profit = (item_lookup.get('영업이익', 0) or
                           item_lookup.get('영업이익(손실)', 0))

        logger.info(f"Revenue: {revenue:,.0f}")
        logger.info(f"Operating Profit: {operating_profit:,.0f}")

        # Show all Income Statement items for reference
        logger.info(f"\n{'='*70}")
        logger.info("All Income Statement (IS) items:")
        logger.info(f"{'='*70}\n")

        is_items = [item for item in items if item.get('sj_div') == 'IS']
        for item in is_items[:20]:  # Show first 20
            account_nm = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0')
            logger.info(f"  {account_nm:<40} | {amount:>20}")

    except Exception as e:
        logger.exception(f"Error debugging {ticker}: {e}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Debug DART API net_income parsing')
    parser.add_argument('--ticker', default='005930', help='Ticker symbol (default: 005930 Samsung)')
    parser.add_argument('--year', type=int, default=2025, help='Fiscal year (default: 2025)')
    parser.add_argument('--report', default='11012',
                       choices=['11011', '11012', '11013', '11014'],
                       help='Report code (11011=Annual, 11012=Semi-annual, 11013=Q1, 11014=Q3)')

    args = parser.parse_args()

    debug_ticker_net_income(args.ticker, args.year, args.report)
