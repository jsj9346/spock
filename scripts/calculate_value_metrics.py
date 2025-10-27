#!/usr/bin/env python3
"""
Calculate Value metrics (P/E, P/B, EV/EBITDA) from fundamental + market data

Formulas:
- P/E Ratio = Market Cap / Net Income (Annual)
- P/B Ratio = Market Cap / Total Equity
- EV/EBITDA = (Market Cap + Total Debt - Cash) / EBITDA
- Dividend Yield = (Dividend Per Share / Close Price) * 100

Usage:
    python3 scripts/calculate_value_metrics.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_value_metrics(ticker: str, db_path: str = "./data/spock_local.db") -> dict:
    """
    Calculate value metrics from fundamental + market data

    Args:
        ticker: Stock ticker
        db_path: Database path

    Returns:
        Dict with calculated metrics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get latest fundamental record with market data
    cursor.execute("""
        SELECT
            id,
            market_cap,
            close_price,
            shares_outstanding,
            total_equity,
            total_liabilities,
            net_income,
            revenue,
            operating_profit,
            ebitda,
            cash_and_equivalents,
            dividend_per_share,
            fiscal_year
        FROM ticker_fundamentals
        WHERE ticker = ? AND market_cap IS NOT NULL AND close_price IS NOT NULL
        ORDER BY fiscal_year DESC, date DESC
        LIMIT 1
    """, (ticker,))

    result = cursor.fetchone()

    if not result:
        logger.warning(f"❌ [{ticker}] No fundamental + market data found")
        conn.close()
        return {}

    (record_id, market_cap, close_price, shares_outstanding,
     total_equity, total_liabilities, net_income, revenue, operating_profit,
     ebitda, cash_and_equivalents, dividend_per_share, fiscal_year) = result

    logger.info(f"\n📊 [{ticker}] Calculating value metrics (Fiscal Year: {fiscal_year})")
    logger.info(f"   Market Cap: {market_cap/1e12:.2f}T KRW")
    logger.info(f"   Close Price: {close_price:,.0f} KRW")
    logger.info(f"   Shares: {shares_outstanding/1e6:.2f}M")

    metrics = {}

    # 1. P/E Ratio = Market Cap / Net Income (annual)
    # Note: Net income from semi-annual report needs to be annualized
    # Fallback: Use operating profit if net income is unavailable
    earnings = net_income if net_income and net_income > 0 else operating_profit

    if earnings and earnings > 0:
        # Annualize: semi-annual * 2
        annualized_earnings = earnings * 2
        per = market_cap / annualized_earnings
        metrics['per'] = per

        if net_income and net_income > 0:
            logger.info(f"   ✅ P/E Ratio: {per:.2f} (Net Income: {annualized_earnings/1e12:.2f}T KRW annualized)")
        else:
            logger.info(f"   ✅ P/OP Ratio: {per:.2f} (Operating Profit: {annualized_earnings/1e12:.2f}T KRW annualized)")
    else:
        logger.warning(f"   ⚠️ P/E Ratio: Cannot calculate (Net Income: {net_income}, Operating Profit: {operating_profit})")

    # 2. P/B Ratio = Market Cap / Total Equity
    if total_equity and total_equity > 0:
        pbr = market_cap / total_equity
        metrics['pbr'] = pbr
        logger.info(f"   ✅ P/B Ratio: {pbr:.2f} (Equity: {total_equity/1e12:.2f}T KRW)")
    else:
        logger.warning(f"   ⚠️ P/B Ratio: Cannot calculate (Total Equity: {total_equity})")

    # 3. EV/EBITDA = (Market Cap + Total Debt - Cash) / EBITDA
    # Fallback: Use operating profit if EBITDA unavailable (EBITDA ≈ Operating Profit * 1.2)
    if total_liabilities:
        # Enterprise Value = Market Cap + Total Debt - Cash
        # Simplified: Total Debt ≈ Total Liabilities (conservative)
        cash = cash_and_equivalents if cash_and_equivalents else 0
        ev = market_cap + total_liabilities - cash

        # Calculate EBITDA proxy
        if ebitda and ebitda > 0:
            ebitda_value = ebitda
        elif operating_profit and operating_profit > 0:
            # EBITDA ≈ Operating Profit * 1.15 (typical depreciation ~13% of operating profit)
            ebitda_value = operating_profit * 1.15
        else:
            ebitda_value = None

        if ebitda_value and ebitda_value > 0:
            # Annualize (semi-annual * 2)
            annualized_ebitda = ebitda_value * 2
            ev_ebitda = ev / annualized_ebitda
            metrics['ev_ebitda'] = ev_ebitda
            metrics['ev'] = ev

            if ebitda and ebitda > 0:
                logger.info(f"   ✅ EV/EBITDA: {ev_ebitda:.2f} (EV: {ev/1e12:.2f}T KRW, EBITDA: {annualized_ebitda/1e12:.2f}T)")
            else:
                logger.info(f"   ✅ EV/EBIT: {ev_ebitda:.2f} (EV: {ev/1e12:.2f}T KRW, Estimated EBITDA: {annualized_ebitda/1e12:.2f}T)")
        else:
            logger.warning(f"   ⚠️ EV/EBITDA: Cannot calculate (No EBITDA or Operating Profit)")
    else:
        logger.warning(f"   ⚠️ EV/EBITDA: Cannot calculate (No liabilities data)")

    # 4. Dividend Yield = (Dividend Per Share / Close Price) * 100
    if dividend_per_share and close_price > 0:
        dividend_yield = (dividend_per_share / close_price) * 100
        metrics['dividend_yield'] = dividend_yield
        logger.info(f"   ✅ Dividend Yield: {dividend_yield:.2f}% (DPS: {dividend_per_share:.0f} KRW)")
    else:
        logger.warning(f"   ⚠️ Dividend Yield: No dividend data")

    # Update database
    if metrics:
        update_fields = ', '.join([f"{k} = ?" for k in metrics.keys()])
        update_values = list(metrics.values()) + [record_id]

        cursor.execute(f"""
            UPDATE ticker_fundamentals
            SET {update_fields}
            WHERE id = ?
        """, update_values)

        conn.commit()
        logger.info(f"   💾 Updated {len(metrics)} metrics in database")

    conn.close()
    return metrics

def main():
    """Calculate value metrics for 5 major Korean stocks"""

    tickers = [
        '005930',  # Samsung Electronics
        '000660',  # SK Hynix
        '035720',  # Kakao
        '051910',  # LG Chem
        '006400'   # Samsung SDI
    ]

    logger.info("="*70)
    logger.info("📊 Calculating Value Metrics from Fundamentals")
    logger.info("="*70)

    results = {}

    for ticker in tickers:
        metrics = calculate_value_metrics(ticker)
        results[ticker] = metrics

    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 VALUE METRICS CALCULATION RESULTS")
    logger.info("="*70)

    for ticker, metrics in results.items():
        if metrics:
            metric_list = ', '.join([f"{k}={v:.2f}" for k, v in metrics.items()])
            logger.info(f"{ticker}: ✅ {metric_list}")
        else:
            logger.info(f"{ticker}: ❌ No metrics calculated")

    logger.info("="*70)

    return 0

if __name__ == '__main__':
    exit(main())
