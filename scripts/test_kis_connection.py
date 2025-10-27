#!/usr/bin/env python3
"""
KIS API Connection Test Utility

Purpose: Test KIS API connectivity and diagnose connection issues
Usage: python3 scripts/test_kis_connection.py [--options]
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class KISConnectionTester:
    """Test KIS API connectivity and performance"""

    def __init__(self):
        """Initialize connection tester"""
        load_dotenv()

        self.app_key = os.getenv('KIS_APP_KEY')
        self.app_secret = os.getenv('KIS_APP_SECRET')
        self.base_url = os.getenv('KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443')

        if not all([self.app_key, self.app_secret]):
            logger.error("❌ KIS credentials not found in .env")
            logger.error("   Run: python3 scripts/validate_kis_credentials.py")
            sys.exit(1)

        self.api = KISOverseasStockAPI(
            app_key=self.app_key,
            app_secret=self.app_secret,
            base_url=self.base_url
        )

    def test_basic_connection(self) -> bool:
        """Test basic API connection"""
        logger.info("🔌 Testing Basic Connection")
        logger.info("=" * 60)

        try:
            start_time = time.time()
            token_response = self.api._get_access_token()
            latency = (time.time() - start_time) * 1000  # ms

            if token_response and 'access_token' in token_response:
                logger.info(f"✅ Connection successful")
                logger.info(f"   Latency: {latency:.0f}ms")
                logger.info(f"   Token expires in: {token_response.get('expires_in', 0)}s")
                logger.info("")
                return True
            else:
                logger.error(f"❌ Connection failed")
                logger.error(f"   Response: {token_response}")
                logger.info("")
                return False

        except Exception as e:
            logger.error(f"❌ Connection error: {str(e)}")
            logger.info("")
            return False

    def test_api_latency(self, iterations: int = 5) -> bool:
        """Test API latency with multiple requests

        Args:
            iterations: Number of test requests

        Returns:
            bool: True if average latency acceptable (<500ms)
        """
        logger.info(f"⚡ Testing API Latency ({iterations} iterations)")
        logger.info("=" * 60)

        latencies = []

        for i in range(iterations):
            try:
                start_time = time.time()

                # Test with lightweight endpoint (ticker list)
                tickers = self.api.get_tradable_tickers(exchange_code='NASD', max_count=5)

                latency = (time.time() - start_time) * 1000  # ms
                latencies.append(latency)

                status = "✅" if latency < 500 else "⚠️"
                logger.info(f"   Request {i + 1}: {status} {latency:.0f}ms")

                # Rate limiting: 20 req/sec = 50ms delay
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"   Request {i + 1}: ❌ Error - {str(e)}")

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            logger.info("")
            logger.info(f"📊 Latency Statistics:")
            logger.info(f"   Average: {avg_latency:.0f}ms")
            logger.info(f"   Min: {min_latency:.0f}ms")
            logger.info(f"   Max: {max_latency:.0f}ms")

            if avg_latency < 500:
                logger.info(f"   Status: ✅ Acceptable (<500ms)")
                logger.info("")
                return True
            else:
                logger.warning(f"   Status: ⚠️  High latency (>500ms)")
                logger.info("")
                return False
        else:
            logger.error("❌ All latency tests failed")
            logger.info("")
            return False

    def test_rate_limiting(self, duration_seconds: int = 5) -> bool:
        """Test rate limiting compliance

        Args:
            duration_seconds: Test duration in seconds

        Returns:
            bool: True if rate limit respected
        """
        logger.info(f"🚦 Testing Rate Limiting ({duration_seconds}s)")
        logger.info("=" * 60)

        request_count = 0
        start_time = time.time()

        try:
            while (time.time() - start_time) < duration_seconds:
                # Make API request
                tickers = self.api.get_tradable_tickers(exchange_code='NASD', max_count=5)
                request_count += 1

                # Rate limiting: 20 req/sec = 50ms delay
                time.sleep(0.05)

        except Exception as e:
            logger.error(f"❌ Rate limit test error: {str(e)}")
            logger.info("")
            return False

        elapsed = time.time() - start_time
        req_per_sec = request_count / elapsed

        logger.info(f"📊 Rate Limit Statistics:")
        logger.info(f"   Requests: {request_count}")
        logger.info(f"   Duration: {elapsed:.1f}s")
        logger.info(f"   Rate: {req_per_sec:.1f} req/sec")
        logger.info(f"   Limit: 20 req/sec")

        if req_per_sec <= 20:
            logger.info(f"   Status: ✅ Within limit")
            logger.info("")
            return True
        else:
            logger.warning(f"   Status: ⚠️  Exceeding limit")
            logger.info("")
            return False

    def test_market_data_collection(self, ticker: str = 'AAPL', days: int = 5) -> bool:
        """Test OHLCV data collection

        Args:
            ticker: Stock ticker to test
            days: Number of days to collect

        Returns:
            bool: True if data collection successful
        """
        logger.info(f"📈 Testing Market Data Collection")
        logger.info("=" * 60)
        logger.info(f"   Ticker: {ticker}")
        logger.info(f"   Days: {days}")
        logger.info("")

        try:
            start_time = time.time()

            # Collect OHLCV data
            ohlcv_df = self.api.get_ohlcv(
                ticker=ticker,
                exchange_code='NASD',  # Assume NASDAQ for AAPL
                days=days
            )

            elapsed = time.time() - start_time

            if ohlcv_df is not None and not ohlcv_df.empty:
                logger.info(f"✅ Data collection successful")
                logger.info(f"   Rows collected: {len(ohlcv_df)}")
                logger.info(f"   Duration: {elapsed:.2f}s")
                logger.info(f"   Date range: {ohlcv_df['date'].min()} to {ohlcv_df['date'].max()}")
                logger.info("")

                # Show sample data
                logger.info(f"📊 Sample Data (last 3 rows):")
                logger.info(ohlcv_df.tail(3).to_string(index=False))
                logger.info("")
                return True
            else:
                logger.error(f"❌ Data collection failed: Empty dataset")
                logger.info("")
                return False

        except Exception as e:
            logger.error(f"❌ Data collection error: {str(e)}")
            logger.info("")
            return False

    def test_multiple_markets(self) -> bool:
        """Test access to multiple markets"""
        logger.info(f"🌐 Testing Multiple Markets")
        logger.info("=" * 60)

        markets = [
            ('NASD', 'US (NASDAQ)'),
            ('SEHK', 'Hong Kong'),
            ('SHAA', 'China (Shanghai)'),
            ('TKSE', 'Japan (Tokyo)'),
            ('HASE', 'Vietnam (Hanoi)')
        ]

        accessible_count = 0

        for exchange_code, market_name in markets:
            try:
                tickers = self.api.get_tradable_tickers(exchange_code=exchange_code, max_count=5)

                if tickers and len(tickers) > 0:
                    logger.info(f"✅ {market_name}: Accessible ({len(tickers)} tickers)")
                    accessible_count += 1
                else:
                    logger.warning(f"⚠️  {market_name}: No tickers returned")

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {market_name}: Not accessible")
                if "해외주식 거래 권한" in str(e):
                    logger.error(f"   → Enable overseas trading permission")

        logger.info("")
        logger.info(f"📊 Market Access Summary: {accessible_count}/{len(markets)} markets accessible")
        logger.info("")

        return accessible_count > 0

    def check_token_expiration(self) -> bool:
        """Check OAuth token expiration time"""
        logger.info(f"⏰ Checking Token Expiration")
        logger.info("=" * 60)

        try:
            token_response = self.api._get_access_token()

            if token_response and 'access_token' in token_response:
                expires_in = token_response.get('expires_in', 0)
                expiration_time = datetime.now() + timedelta(seconds=expires_in)

                logger.info(f"✅ Token Status: Active")
                logger.info(f"   Expires in: {expires_in}s ({expires_in // 3600}h {(expires_in % 3600) // 60}m)")
                logger.info(f"   Expiration time: {expiration_time.strftime('%Y-%m-%d %H:%M:%S')}")

                if expires_in < 3600:
                    logger.warning(f"   ⚠️  Token expires soon (< 1 hour)")
                    logger.warning(f"   → Consider requesting new token")

                logger.info("")
                return True
            else:
                logger.error(f"❌ Failed to retrieve token")
                logger.info("")
                return False

        except Exception as e:
            logger.error(f"❌ Token check error: {str(e)}")
            logger.info("")
            return False

    def run_full_diagnostics(self) -> bool:
        """Run complete diagnostic suite

        Returns:
            bool: True if all critical tests pass
        """
        logger.info("🔬 KIS API Connection Diagnostics")
        logger.info("=" * 60)
        logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

        results = {
            'Basic Connection': self.test_basic_connection(),
            'API Latency': self.test_api_latency(iterations=5),
            'Rate Limiting': self.test_rate_limiting(duration_seconds=3),
            'Market Data': self.test_market_data_collection(ticker='AAPL', days=5),
            'Multiple Markets': self.test_multiple_markets(),
            'Token Status': self.check_token_expiration()
        }

        # Print summary
        logger.info("=" * 60)
        logger.info("📊 Diagnostic Summary")
        logger.info("=" * 60)

        passed_count = sum(1 for result in results.values() if result)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"   {test_name}: {status}")

        logger.info("")
        logger.info(f"   Total: {passed_count}/{len(results)} tests passed")
        logger.info("")

        if passed_count == len(results):
            logger.info("🎉 All diagnostics passed! KIS API connection is healthy.")
            return True
        elif passed_count >= len(results) - 2:
            logger.warning("⚠️  Some tests failed, but core functionality works.")
            return True
        else:
            logger.error("❌ Multiple tests failed. Check credentials and permissions.")
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Test KIS API connection')
    parser.add_argument('--basic', action='store_true', help='Basic connection test only')
    parser.add_argument('--latency', action='store_true', help='Latency test only')
    parser.add_argument('--rate-limit', action='store_true', help='Rate limiting test only')
    parser.add_argument('--data', action='store_true', help='Market data test only')
    parser.add_argument('--markets', action='store_true', help='Multiple markets test only')
    parser.add_argument('--check-token', action='store_true', help='Check token expiration only')
    parser.add_argument('--ticker', type=str, default='AAPL', help='Ticker for data test')
    parser.add_argument('--days', type=int, default=5, help='Days for data test')

    args = parser.parse_args()

    tester = KISConnectionTester()

    # Run specific test if flag provided
    if args.basic:
        success = tester.test_basic_connection()
    elif args.latency:
        success = tester.test_api_latency()
    elif args.rate_limit:
        success = tester.test_rate_limiting()
    elif args.data:
        success = tester.test_market_data_collection(ticker=args.ticker, days=args.days)
    elif args.markets:
        success = tester.test_multiple_markets()
    elif args.check_token:
        success = tester.check_token_expiration()
    else:
        # Run full diagnostics
        success = tester.run_full_diagnostics()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
