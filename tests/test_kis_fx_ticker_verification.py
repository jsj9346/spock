"""
KIS API FX Ticker Verification Tests

Purpose: Verify KIS API supports FX (exchange rate) data retrieval
- Test FX ticker codes (FRX.KRWUSD, FRX.CNYUSD, etc.)
- Validate fid_cond_mrkt_div_code="X" for FX market
- Verify OHLC data quality and format
- Document confirmed ticker codes for production

Target Markets:
- KRW/USD (Korean Won)
- CNY/USD (Chinese Yuan)
- HKD/USD (Hong Kong Dollar)
- JPY/USD (Japanese Yen)
- VND/USD (Vietnamese Dong)

Test Strategy:
1. Basic connectivity test
2. Individual ticker code verification
3. OHLC data format validation
4. Data quality checks (non-zero, reasonable ranges)
5. Historical data availability test (1 year)

Author: SuperClaude Quant Platform
Date: 2025-10-23
"""

import pytest
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KISFXTickerVerifier:
    """
    KIS API FX Ticker Verification Class

    Verifies FX ticker codes and data quality for production deployment
    """

    # FX ticker code candidates to test
    FX_TICKER_CANDIDATES = {
        'KRW': ['FRX.KRWUSD', 'KRWUSD', 'FRX.USDKRW', 'USDKRW'],
        'CNY': ['FRX.CNYUSD', 'CNYUSD', 'FRX.USDCNY', 'USDCNY'],
        'HKD': ['FRX.HKDUSD', 'HKDUSD', 'FRX.USDHKD', 'USDHKD'],
        'JPY': ['FRX.JPYUSD', 'JPYUSD', 'FRX.USDJPY', 'USDJPY'],
        'VND': ['FRX.VNDUSD', 'VNDUSD', 'FRX.USDVND', 'USDVND'],
    }

    def __init__(self, app_key: str, app_secret: str, base_url: str = 'https://openapi.koreainvestment.com:9443'):
        """
        Initialize FX ticker verifier

        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            base_url: API base URL (default: production)
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url
        self.access_token = None
        self.verified_tickers = {}

    def _get_access_token(self) -> str:
        """Get or refresh OAuth 2.0 access token"""
        import requests

        if self.access_token:
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.access_token = data['access_token']
            logger.info("✅ OAuth token acquired successfully")
            return self.access_token
        except Exception as e:
            logger.error(f"❌ Token acquisition failed: {e}")
            raise

    def test_fx_ticker(self, ticker: str, days: int = 5) -> Dict:
        """
        Test a single FX ticker code

        Args:
            ticker: FX ticker code to test
            days: Number of days to retrieve (default: 5)

        Returns:
            Dict with test results: {
                'ticker': str,
                'success': bool,
                'error': str or None,
                'data_rows': int,
                'date_range': (start, end),
                'sample_data': DataFrame,
                'data_quality': Dict
            }
        """
        import requests

        logger.info(f"🔍 Testing FX ticker: {ticker}")

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days * 2)  # Extra buffer for weekends

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010100",
        }

        params = {
            "fid_cond_mrkt_div_code": "X",  # X: FX (환율)
            "fid_input_iscd": ticker,
            "fid_input_date_1": start_date.strftime("%Y%m%d"),
            "fid_input_date_2": end_date.strftime("%Y%m%d"),
            "fid_period_div_code": "D",  # D: Daily
            "fid_org_adj_prc": "0",
        }

        result = {
            'ticker': ticker,
            'success': False,
            'error': None,
            'data_rows': 0,
            'date_range': None,
            'sample_data': None,
            'data_quality': None
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check API response status
            rt_cd = data.get('rt_cd')
            msg1 = data.get('msg1', '')

            if rt_cd != '0':
                result['error'] = f"API Error: {msg1} (rt_cd: {rt_cd})"
                logger.error(f"❌ {ticker}: {result['error']}")
                return result

            # Parse OHLCV data
            ohlcv_list = data.get('output2', [])
            if not ohlcv_list:
                result['error'] = "No data returned (output2 empty)"
                logger.warning(f"⚠️ {ticker}: {result['error']}")
                return result

            # Convert to DataFrame
            df = pd.DataFrame(ohlcv_list)

            # Rename columns (KIS uses Korean column names)
            column_mapping = {
                'stck_bsop_date': 'date',
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'stck_clpr': 'close',
                'acml_vol': 'volume',
            }

            df = df.rename(columns=column_mapping)

            # Convert numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Convert date column
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

            # Sort by date ascending
            df = df.sort_values('date').reset_index(drop=True)

            # Analyze data quality
            data_quality = self._analyze_data_quality(df)

            result['success'] = True
            result['data_rows'] = len(df)
            result['date_range'] = (df['date'].min(), df['date'].max())
            result['sample_data'] = df.head(10)
            result['data_quality'] = data_quality

            logger.info(f"✅ {ticker}: Retrieved {len(df)} rows from {result['date_range'][0]} to {result['date_range'][1]}")

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"❌ {ticker}: Exception - {e}")

        return result

    def _analyze_data_quality(self, df: pd.DataFrame) -> Dict:
        """
        Analyze FX data quality

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with quality metrics
        """
        quality = {
            'total_rows': len(df),
            'non_zero_close': (df['close'] > 0).sum(),
            'close_range': (df['close'].min(), df['close'].max()),
            'avg_close': df['close'].mean(),
            'zero_volume_pct': (df['volume'] == 0).sum() / len(df) * 100 if len(df) > 0 else 0,
            'missing_data_pct': df[['open', 'high', 'low', 'close']].isna().sum().sum() / (len(df) * 4) * 100 if len(df) > 0 else 0,
            'ohlc_consistency': self._check_ohlc_consistency(df),
        }

        return quality

    def _check_ohlc_consistency(self, df: pd.DataFrame) -> Dict:
        """
        Check OHLC consistency (High >= Low, High >= Open/Close, Low <= Open/Close)

        Args:
            df: DataFrame with OHLC data

        Returns:
            Dict with consistency check results
        """
        if df.empty:
            return {'valid': 0, 'invalid': 0, 'valid_pct': 0.0}

        # Check: High >= Low
        valid_high_low = df['high'] >= df['low']

        # Check: High >= Open and High >= Close
        valid_high_open = df['high'] >= df['open']
        valid_high_close = df['high'] >= df['close']

        # Check: Low <= Open and Low <= Close
        valid_low_open = df['low'] <= df['open']
        valid_low_close = df['low'] <= df['close']

        # All checks must pass
        all_valid = valid_high_low & valid_high_open & valid_high_close & valid_low_open & valid_low_close

        valid_count = all_valid.sum()
        invalid_count = len(df) - valid_count

        return {
            'valid': int(valid_count),
            'invalid': int(invalid_count),
            'valid_pct': round(valid_count / len(df) * 100, 2) if len(df) > 0 else 0.0
        }

    def verify_all_currencies(self, test_days: int = 30) -> Dict:
        """
        Verify FX ticker codes for all target currencies

        Args:
            test_days: Number of days to test (default: 30)

        Returns:
            Dict with verification results for all currencies
        """
        logger.info("=" * 80)
        logger.info("🔬 Starting KIS API FX Ticker Verification")
        logger.info("=" * 80)

        results = {}

        for currency, candidates in self.FX_TICKER_CANDIDATES.items():
            logger.info(f"\n📊 Testing currency: {currency}")
            currency_results = []

            for ticker in candidates:
                result = self.test_fx_ticker(ticker, days=test_days)
                currency_results.append(result)

                if result['success']:
                    logger.info(f"   ✅ {ticker}: VERIFIED - {result['data_rows']} rows, quality: {result['data_quality']['ohlc_consistency']['valid_pct']:.1f}%")

                    # Store first successful ticker as verified
                    if currency not in self.verified_tickers:
                        self.verified_tickers[currency] = ticker
                else:
                    logger.warning(f"   ❌ {ticker}: FAILED - {result['error']}")

            results[currency] = currency_results

        return results

    def generate_report(self, results: Dict) -> str:
        """
        Generate verification report

        Args:
            results: Verification results from verify_all_currencies()

        Returns:
            Formatted report string
        """
        report = []
        report.append("\n" + "=" * 80)
        report.append("KIS API FX TICKER VERIFICATION REPORT")
        report.append("=" * 80)
        report.append(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Summary
        total_currencies = len(results)
        verified_currencies = len(self.verified_tickers)

        report.append("SUMMARY:")
        report.append(f"  Total Currencies Tested: {total_currencies}")
        report.append(f"  Successfully Verified: {verified_currencies}")
        report.append(f"  Verification Rate: {verified_currencies / total_currencies * 100:.1f}%")
        report.append("")

        # Verified Tickers
        report.append("VERIFIED TICKER CODES (Production-Ready):")
        for currency, ticker in self.verified_tickers.items():
            report.append(f"  {currency:3s} → {ticker}")
        report.append("")

        # Detailed Results
        report.append("DETAILED TEST RESULTS:")
        for currency, currency_results in results.items():
            report.append(f"\n{currency} (Korean Won → USD):")

            for result in currency_results:
                ticker = result['ticker']
                if result['success']:
                    quality = result['data_quality']
                    report.append(f"  ✅ {ticker:15s} | Rows: {result['data_rows']:3d} | "
                                f"Quality: {quality['ohlc_consistency']['valid_pct']:5.1f}% | "
                                f"Range: {result['date_range'][0].strftime('%Y-%m-%d')} - {result['date_range'][1].strftime('%Y-%m-%d')}")
                    report.append(f"     Close Range: {quality['close_range'][0]:.4f} - {quality['close_range'][1]:.4f} | "
                                f"Avg: {quality['avg_close']:.4f}")
                else:
                    report.append(f"  ❌ {ticker:15s} | Error: {result['error']}")

        report.append("")
        report.append("=" * 80)
        report.append("RECOMMENDATIONS:")

        if verified_currencies == total_currencies:
            report.append("  ✅ All currencies verified successfully")
            report.append("  ✅ Ready for Phase 1-C: FX Data Collector Development")
        else:
            report.append(f"  ⚠️ {total_currencies - verified_currencies} currencies failed verification")
            report.append("  🔧 Action Required: Investigate failed ticker codes")

        report.append("=" * 80)

        return "\n".join(report)


# ============================================================================
# Pytest Test Cases
# ============================================================================

@pytest.fixture(scope="module")
def kis_credentials():
    """Load KIS API credentials from environment"""
    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        pytest.skip("KIS API credentials not found in environment variables")

    return {
        'app_key': app_key,
        'app_secret': app_secret
    }


@pytest.fixture(scope="module")
def fx_verifier(kis_credentials):
    """Create FX ticker verifier instance"""
    return KISFXTickerVerifier(
        app_key=kis_credentials['app_key'],
        app_secret=kis_credentials['app_secret']
    )


class TestKISFXTickerVerification:
    """KIS FX Ticker Verification Test Suite"""

    def test_oauth_token_acquisition(self, fx_verifier):
        """Test 1: Verify OAuth token acquisition"""
        logger.info("Test 1: OAuth Token Acquisition")

        token = fx_verifier._get_access_token()
        assert token is not None, "Failed to acquire OAuth token"
        assert len(token) > 0, "OAuth token is empty"

        logger.info(f"✅ OAuth token acquired: {token[:20]}...")

    def test_krw_usd_ticker(self, fx_verifier):
        """Test 2: Verify KRW/USD ticker code"""
        logger.info("Test 2: KRW/USD Ticker Verification")

        # Test most likely ticker format
        result = fx_verifier.test_fx_ticker('FRX.KRWUSD', days=30)

        assert result['success'], f"KRW/USD ticker failed: {result['error']}"
        assert result['data_rows'] > 0, "No data rows returned"
        assert result['data_quality']['ohlc_consistency']['valid_pct'] >= 95.0, "OHLC data quality too low"

        logger.info(f"✅ KRW/USD verified: {result['data_rows']} rows, "
                   f"{result['data_quality']['ohlc_consistency']['valid_pct']:.1f}% quality")

    def test_all_currencies_verification(self, fx_verifier):
        """Test 3: Comprehensive verification of all target currencies"""
        logger.info("Test 3: All Currencies Verification")

        results = fx_verifier.verify_all_currencies(test_days=30)

        # Check that at least 80% of currencies are verified
        verified_count = len(fx_verifier.verified_tickers)
        total_count = len(fx_verifier.FX_TICKER_CANDIDATES)
        success_rate = verified_count / total_count * 100

        assert success_rate >= 80.0, f"Verification rate too low: {success_rate:.1f}%"

        logger.info(f"✅ {verified_count}/{total_count} currencies verified ({success_rate:.1f}%)")

    def test_data_quality_krw(self, fx_verifier):
        """Test 4: Data quality validation for KRW/USD"""
        logger.info("Test 4: KRW/USD Data Quality Validation")

        result = fx_verifier.test_fx_ticker('FRX.KRWUSD', days=30)

        assert result['success'], f"Failed to retrieve data: {result['error']}"

        quality = result['data_quality']

        # Quality checks
        assert quality['non_zero_close'] == quality['total_rows'], "Some close prices are zero"
        assert quality['missing_data_pct'] == 0.0, f"Missing data detected: {quality['missing_data_pct']:.2f}%"
        assert quality['ohlc_consistency']['valid_pct'] >= 99.0, "OHLC consistency check failed"

        # Reasonable range check (KRW/USD typically 0.0007 - 0.0009)
        min_close, max_close = quality['close_range']
        assert 0.0005 <= min_close <= 0.0015, f"KRW/USD close price out of expected range: {min_close}"
        assert 0.0005 <= max_close <= 0.0015, f"KRW/USD close price out of expected range: {max_close}"

        logger.info(f"✅ Data quality validated: {quality['ohlc_consistency']['valid_pct']:.1f}% consistency")

    def test_historical_data_availability(self, fx_verifier):
        """Test 5: Historical data availability (1 year)"""
        logger.info("Test 5: Historical Data Availability (1 year)")

        result = fx_verifier.test_fx_ticker('FRX.KRWUSD', days=365)

        assert result['success'], f"Failed to retrieve historical data: {result['error']}"
        assert result['data_rows'] >= 200, f"Insufficient historical data: {result['data_rows']} rows (expected >= 200 trading days)"

        date_range = result['date_range']
        days_covered = (date_range[1] - date_range[0]).days

        assert days_covered >= 300, f"Date range too short: {days_covered} days (expected >= 300 calendar days)"

        logger.info(f"✅ Historical data verified: {result['data_rows']} rows covering {days_covered} days")


# ============================================================================
# Main Execution (for direct script run)
# ============================================================================

if __name__ == '__main__':
    # Load credentials from environment
    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        logger.error("❌ KIS API credentials not found in environment variables")
        logger.error("   Set KIS_APP_KEY and KIS_APP_SECRET before running")
        exit(1)

    # Create verifier
    verifier = KISFXTickerVerifier(app_key, app_secret)

    # Run verification
    results = verifier.verify_all_currencies(test_days=30)

    # Generate and display report
    report = verifier.generate_report(results)
    print(report)

    # Save report to file
    report_path = f"logs/fx_ticker_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    os.makedirs("logs", exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(report)

    logger.info(f"\n📄 Report saved to: {report_path}")

    # Exit with appropriate code
    verified_count = len(verifier.verified_tickers)
    total_count = len(verifier.FX_TICKER_CANDIDATES)

    if verified_count == total_count:
        logger.info("\n✅ ALL CURRENCIES VERIFIED - Ready for Phase 1-C")
        exit(0)
    else:
        logger.warning(f"\n⚠️ {total_count - verified_count} currencies failed - Manual investigation required")
        exit(1)
