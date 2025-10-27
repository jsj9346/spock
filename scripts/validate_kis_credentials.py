#!/usr/bin/env python3
"""
KIS API Credential Validation Script

Purpose: Validate KIS API credentials and test connectivity
Usage: python3 scripts/validate_kis_credentials.py [--verbose]
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from modules.db_manager_sqlite import SQLiteDatabaseManager


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class KISCredentialValidator:
    """Validate KIS API credentials and test connectivity"""

    def __init__(self, verbose: bool = False):
        """Initialize validator"""
        self.verbose = verbose
        self.env_path = project_root / '.env'
        self.checks_passed = 0
        self.checks_total = 0

    def validate_all(self) -> bool:
        """Run all validation checks

        Returns:
            bool: True if all checks pass, False otherwise
        """
        logger.info("🔍 Validating KIS API credentials...")
        logger.info("")

        # Step 1: Environment file check
        if not self._check_env_file():
            return False

        # Step 2: Load credentials
        app_key, app_secret, base_url = self._load_credentials()
        if not all([app_key, app_secret, base_url]):
            return False

        # Step 3: Test API connection
        if not self._test_api_connection(app_key, app_secret, base_url):
            return False

        # Step 4: Test market data access
        if not self._test_market_access(app_key, app_secret):
            return False

        # Print summary
        logger.info("")
        logger.info("=" * 60)
        if self.checks_passed == self.checks_total:
            logger.info(f"🎉 All validation checks passed! ({self.checks_passed}/{self.checks_total})")
            logger.info("")
            logger.info("✅ Your KIS API credentials are configured correctly")
            logger.info("✅ Ready for deployment: python3 scripts/deploy_us_adapter.py --full")
            return True
        else:
            logger.info(f"❌ Validation failed: {self.checks_passed}/{self.checks_total} checks passed")
            logger.info("")
            logger.info("📖 See troubleshooting guide: docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md")
            return False

    def _check_env_file(self) -> bool:
        """Check if .env file exists"""
        self.checks_total += 1

        if self.env_path.exists():
            logger.info(f"✅ Environment file exists: {self.env_path}")
            self.checks_passed += 1
            return True
        else:
            logger.error(f"❌ Environment file not found: {self.env_path}")
            logger.error("   → Create .env file with KIS credentials")
            logger.error("   → See: docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md")
            return False

    def _load_credentials(self) -> tuple:
        """Load credentials from .env file

        Returns:
            tuple: (app_key, app_secret, base_url)
        """
        load_dotenv()

        app_key = os.getenv('KIS_APP_KEY')
        app_secret = os.getenv('KIS_APP_SECRET')
        base_url = os.getenv('KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443')

        # Check APP_KEY
        self.checks_total += 1
        if app_key:
            masked_key = f"{app_key[:4]}{'*' * (len(app_key) - 8)}{app_key[-4:]}" if len(app_key) > 8 else "***"
            logger.info(f"✅ APP_KEY loaded: {masked_key} ({len(app_key)} chars)")
            if len(app_key) != 20:
                logger.warning(f"   ⚠️  APP_KEY should be 20 characters (current: {len(app_key)})")
            self.checks_passed += 1
        else:
            logger.error("❌ APP_KEY not found in .env")
            logger.error("   → Add: KIS_APP_KEY=your_app_key")
            return None, None, None

        # Check APP_SECRET
        self.checks_total += 1
        if app_secret:
            masked_secret = f"{app_secret[:4]}{'*' * (len(app_secret) - 8)}{app_secret[-4:]}" if len(app_secret) > 8 else "***"
            logger.info(f"✅ APP_SECRET loaded: {masked_secret} ({len(app_secret)} chars)")
            if len(app_secret) != 40:
                logger.warning(f"   ⚠️  APP_SECRET should be 40 characters (current: {len(app_secret)})")
            self.checks_passed += 1
        else:
            logger.error("❌ APP_SECRET not found in .env")
            logger.error("   → Add: KIS_APP_SECRET=your_app_secret")
            return None, None, None

        # Check BASE_URL
        self.checks_total += 1
        if base_url:
            logger.info(f"✅ BASE_URL loaded: {base_url}")
            self.checks_passed += 1
        else:
            logger.warning("⚠️  BASE_URL not found, using default")
            base_url = 'https://openapi.koreainvestment.com:9443'

        logger.info("")
        return app_key, app_secret, base_url

    def _test_api_connection(self, app_key: str, app_secret: str, base_url: str) -> bool:
        """Test KIS API connection by requesting OAuth token

        Args:
            app_key: KIS APP_KEY
            app_secret: KIS APP_SECRET
            base_url: KIS API base URL

        Returns:
            bool: True if connection successful
        """
        logger.info("📡 Testing KIS API connection...")

        try:
            api = KISOverseasStockAPI(
                app_key=app_key,
                app_secret=app_secret,
                base_url=base_url
            )

            # Request OAuth token (returns token string directly)
            self.checks_total += 1
            token = api._get_access_token()

            if token and isinstance(token, str) and len(token) > 0:
                logger.info("✅ OAuth token obtained successfully")

                # Check token expiration from API object
                if api.token_expires_at:
                    expires_in = int((api.token_expires_at - datetime.now()).total_seconds())
                    logger.info(f"✅ Token expires in: {expires_in} seconds ({expires_in // 3600} hours)")

                    if expires_in < 3600:
                        logger.warning(f"   ⚠️  Token expires soon (< 1 hour)")

                self.checks_passed += 1
                logger.info("")
                return True
            else:
                logger.error("❌ Failed to obtain OAuth token")
                logger.error(f"   Token: {token[:20] if token else 'None'}...")
                logger.error("   → Check APP_KEY and APP_SECRET are correct")
                logger.error("   → Verify API access is approved in KIS portal")
                logger.info("")
                return False

        except Exception as e:
            logger.error(f"❌ API connection test failed: {str(e)}")
            logger.error("   → Check network connectivity")
            logger.error("   → Verify BASE_URL is correct")
            if self.verbose:
                logger.exception("Full error:")
            logger.info("")
            return False

    def _test_market_access(self, app_key: str, app_secret: str) -> bool:
        """Test market data access for different regions

        Args:
            app_key: KIS APP_KEY
            app_secret: KIS APP_SECRET

        Returns:
            bool: True if at least one market accessible
        """
        logger.info("📊 Testing market data access...")

        api = KISOverseasStockAPI(
            app_key=app_key,
            app_secret=app_secret
        )

        markets_tested = 0
        markets_accessible = 0

        # Test US market
        try:
            self.checks_total += 1
            markets_tested += 1

            # Try to get ticker list for NASDAQ
            tickers = api.get_tradable_tickers(exchange_code='NASD', max_count=5)

            if tickers and len(tickers) > 0:
                logger.info(f"✅ US market data: Accessible ({len(tickers)} sample tickers)")
                self.checks_passed += 1
                markets_accessible += 1
            else:
                logger.warning("⚠️  US market data: No tickers returned")
                logger.warning("   → May indicate overseas trading not enabled")
        except Exception as e:
            logger.error(f"❌ US market data: Not accessible")
            logger.error(f"   Error: {str(e)}")
            if "해외주식 거래 권한" in str(e) or "overseas" in str(e).lower():
                logger.error("   → Enable overseas trading in KIS HTS")
                logger.error("   → Menu: 해외주식 → 해외주식 신청")

        # Test Hong Kong market (optional)
        try:
            markets_tested += 1

            tickers = api.get_tradable_tickers(exchange_code='SEHK', max_count=5)

            if tickers and len(tickers) > 0:
                logger.info(f"✅ Hong Kong market data: Accessible ({len(tickers)} sample tickers)")
                markets_accessible += 1
        except Exception as e:
            if self.verbose:
                logger.warning(f"⚠️  Hong Kong market data: {str(e)}")

        # Test China market (optional)
        try:
            markets_tested += 1

            tickers = api.get_tradable_tickers(exchange_code='SHAA', max_count=5)

            if tickers and len(tickers) > 0:
                logger.info(f"✅ China market data: Accessible ({len(tickers)} sample tickers)")
                markets_accessible += 1
        except Exception as e:
            if self.verbose:
                logger.warning(f"⚠️  China market data: {str(e)}")

        logger.info("")

        # At least one market must be accessible
        if markets_accessible > 0:
            logger.info(f"✅ Market access validated: {markets_accessible}/{markets_tested} markets accessible")
            return True
        else:
            logger.error(f"❌ No markets accessible: {markets_accessible}/{markets_tested}")
            logger.error("   → Enable overseas trading permission")
            logger.error("   → See: docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md")
            return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate KIS API credentials')
    parser.add_argument('--verbose', action='store_true', help='Show detailed error messages')
    parser.add_argument('--check-token', action='store_true', help='Check token expiration time')

    args = parser.parse_args()

    # Run validation
    validator = KISCredentialValidator(verbose=args.verbose)
    success = validator.validate_all()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
