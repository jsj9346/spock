#!/usr/bin/env python3
"""
Test Updated DART API Parsing (Phase 2)

Purpose: Verify that updated _parse_financial_statements() method correctly:
1. Uses fnlttSinglAcntAll.json endpoint
2. Extracts all Phase 2 fields with correct account names
3. Estimates depreciation from cash flow
4. Handles NULL values for unavailable fields

Usage:
    python3 tests/test_updated_parsing.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv
import json

load_dotenv()

def test_samsung_parsing():
    """Test Samsung 2023 parsing with updated logic"""

    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    # Samsung corp_code
    SAMSUNG_CORP_CODE = '00126380'
    SAMSUNG_TICKER = '005930'

    print("="*80)
    print("🧪 Testing Updated DART API Parsing Logic")
    print("="*80)
    print(f"Ticker: {SAMSUNG_TICKER} (Samsung Electronics)")
    print(f"Corp Code: {SAMSUNG_CORP_CODE}")
    print(f"Year: 2023")
    print("="*80)

    # Use get_historical_fundamentals (which calls _parse_financial_statements)
    results = dart.get_historical_fundamentals(
        ticker=SAMSUNG_TICKER,
        corp_code=SAMSUNG_CORP_CODE,
        start_year=2023,
        end_year=2023
    )

    if not results:
        print("❌ No data returned")
        return

    metrics = results[0]

    print("\n📊 Parsed Financial Metrics:")
    print("="*80)

    # Core metrics
    print("\n🔹 Core Metrics:")
    print(f"  Revenue (영업수익):          {metrics.get('revenue', 0):>20,.0f} won")
    print(f"  Operating Profit (영업이익):  {metrics.get('operating_profit', 0):>20,.0f} won")
    print(f"  Net Income (당기순이익):      {metrics.get('net_income', 0):>20,.0f} won")

    # Manufacturing indicators
    print("\n🔹 Manufacturing Indicators:")
    print(f"  COGS (매출원가):              {metrics.get('cogs', 0):>20,.0f} won")
    print(f"  Gross Profit (매출총이익):    {metrics.get('gross_profit', 0):>20,.0f} won")
    print(f"  PP&E (유형자산):              {metrics.get('pp_e', 0):>20,.0f} won")
    print(f"  Depreciation (감가상각비):    {metrics.get('depreciation', 0):>20,.0f} won")
    print(f"  Accounts Receivable (매출채권): {metrics.get('accounts_receivable', 0):>18,.0f} won")

    # Retail/E-Commerce indicators
    print("\n🔹 Retail/E-Commerce Indicators:")
    print(f"  SG&A Expense (판매비와관리비): {metrics.get('sga_expense', 0):>18,.0f} won")
    rd_expense = metrics.get('rd_expense')
    print(f"  R&D Expense (연구개발비):     {rd_expense if rd_expense is not None else 'NULL':>20}")
    print(f"  Operating Expense:           {metrics.get('operating_expense', 0):>20,.0f} won")

    # Financial indicators
    print("\n🔹 Financial Indicators:")
    print(f"  Interest Income (금융수익):   {metrics.get('interest_income', 0):>20,.0f} won")
    print(f"  Interest Expense (금융비용):  {metrics.get('interest_expense', 0):>20,.0f} won")
    loan_portfolio = metrics.get('loan_portfolio')
    print(f"  Loan Portfolio (대출금):      {loan_portfolio if loan_portfolio is not None else 'NULL':>20}")
    nim = metrics.get('nim')
    print(f"  NIM (순이자마진):            {f'{nim:.2f}%' if nim is not None else 'NULL':>20}")

    # Common indicators
    print("\n🔹 Common Indicators:")
    print(f"  Investing CF (투자활동현금흐름): {metrics.get('investing_cf', 0):>18,.0f} won")
    print(f"  Financing CF (재무활동현금흐름): {metrics.get('financing_cf', 0):>18,.0f} won")
    print(f"  EBITDA (상각전영업이익):      {metrics.get('ebitda', 0):>20,.0f} won")
    print(f"  EBITDA Margin (%):           {metrics.get('ebitda_margin', 0):>20,.2f}%")

    # Verification
    print("\n" + "="*80)
    print("✅ Verification:")
    print("="*80)

    revenue = metrics.get('revenue', 0)
    cogs = metrics.get('cogs', 0)
    gross_profit = metrics.get('gross_profit', 0)
    depreciation = metrics.get('depreciation', 0)
    operating_profit = metrics.get('operating_profit', 0)
    ebitda = metrics.get('ebitda', 0)

    # Check 1: Revenue exists
    if revenue > 0:
        print(f"✅ Revenue collected: {revenue:,.0f} won")
    else:
        print("❌ Revenue is 0 - data issue!")

    # Check 2: Gross profit calculation
    calculated_gp = revenue - cogs if revenue > 0 and cogs > 0 else 0
    if abs(gross_profit - calculated_gp) < 1000:  # Allow small rounding difference
        print(f"✅ Gross Profit verified: {gross_profit:,.0f} = Revenue - COGS")
    else:
        print(f"⚠️ Gross Profit mismatch: {gross_profit:,.0f} vs calculated {calculated_gp:,.0f}")

    # Check 3: Depreciation estimated
    if depreciation > 0:
        print(f"✅ Depreciation estimated: {depreciation:,.0f} won")
    else:
        print("⚠️ Depreciation is 0 - estimation may have failed")

    # Check 4: EBITDA calculation
    if ebitda > 0:
        print(f"✅ EBITDA calculated: {ebitda:,.0f} won")
        if depreciation > 0:
            expected_ebitda = operating_profit + depreciation
            if abs(ebitda - expected_ebitda) < 1000:
                print(f"   ✅ EBITDA = Operating Profit + Depreciation")
            else:
                print(f"   ⚠️ EBITDA calculation mismatch")
    else:
        print("⚠️ EBITDA is 0")

    # Check 5: NULL handling
    null_fields = []
    if metrics.get('rd_expense') is None:
        null_fields.append('rd_expense')
    if metrics.get('loan_portfolio') is None:
        null_fields.append('loan_portfolio')
    if metrics.get('npl_amount') is None:
        null_fields.append('npl_amount')
    if metrics.get('nim') is None:
        null_fields.append('nim')

    if null_fields:
        print(f"✅ NULL fields correctly handled: {', '.join(null_fields)}")

    print("\n" + "="*80)
    print("✅ Test Complete")
    print("="*80)

if __name__ == '__main__':
    test_samsung_parsing()
