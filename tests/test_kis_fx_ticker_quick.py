"""
Quick KIS FX Ticker Format Discovery

Test various FX ticker formats against the correct KIS API endpoint:
/uapi/overseas-price/v1/quotations/inquire-daily-chartprice

with fid_cond_mrkt_div_code="X" (exchange rate)

Author: SuperClaude
Date: 2025-10-23
"""

import os
import logging
import requests
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load credentials
app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')

if not app_key or not app_secret:
    logger.error("KIS credentials not found")
    exit(1)

# Get OAuth token
token_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
token_response = requests.post(
    token_url,
    headers={"content-type": "application/json"},
    json={
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
)
access_token = token_response.json()['access_token']
logger.info(f"✅ OAuth token acquired")

# Test ticker format candidates
TEST_TICKERS = [
    # USD base (standard FX notation)
    'USD/KRW', 'USDKRW', 'USD.KRW',

    # FRX prefix (some APIs use this)
    'FRX.USDKRW', 'FRX/USDKRW',

    # With exchange codes
    'USD', 'KRW',

    # Bloomberg-style
    'USDKRW Curncy',

    # Just currency pairs
    'KRWUSD', 'KRW/USD',
]

# API endpoint
url = "https://openapi.koreainvestment.com:9443/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

headers = {
    "content-type": "application/json; charset=utf-8",
    "authorization": f"Bearer {access_token}",
    "appkey": app_key,
    "appsecret": app_secret,
    "tr_id": "FHKST03030100",
}

logger.info("\n" + "=" * 80)
logger.info("KIS FX TICKER FORMAT DISCOVERY")
logger.info("=" * 80)

successful_tickers = []

for ticker in TEST_TICKERS:
    params = {
        "FID_COND_MRKT_DIV_CODE": "X",  # X: FX exchange rate
        "FID_INPUT_ISCD": ticker,
        "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",  # D: Daily
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()

        rt_cd = data.get('rt_cd')
        msg1 = data.get('msg1', '')

        if rt_cd == '0':
            output = data.get('output2', [])
            logger.info(f"✅ {ticker:20s} | SUCCESS | {len(output)} rows | msg: {msg1}")
            successful_tickers.append(ticker)

            # Show sample data
            if output:
                sample = output[0]
                logger.info(f"   Sample: {sample}")
        else:
            logger.warning(f"❌ {ticker:20s} | FAILED  | rt_cd: {rt_cd} | msg: {msg1}")

        # Rate limiting
        import time
        time.sleep(0.5)

    except Exception as e:
        logger.error(f"❌ {ticker:20s} | ERROR   | {e}")

logger.info("\n" + "=" * 80)
logger.info("RESULTS")
logger.info("=" * 80)

if successful_tickers:
    logger.info(f"✅ {len(successful_tickers)} ticker format(s) work:")
    for ticker in successful_tickers:
        logger.info(f"   - {ticker}")
else:
    logger.warning("❌ No valid ticker formats found")
    logger.warning("   This may indicate:")
    logger.warning("   1. KIS API doesn't support FX data through this endpoint")
    logger.warning("   2. Different endpoint is required for FX data")
    logger.warning("   3. FX access requires special permissions")

logger.info("=" * 80)
