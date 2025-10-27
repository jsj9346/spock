"""
MarketFilterManager Multi-Market Validation Tests
Task 1.3: Validate MarketFilterManager multi-market support

Test Coverage:
1. Configuration Loading (all 6 markets)
2. Currency Conversion Integration
3. Filter Threshold Validation
4. Market-Specific Rule Handling
5. ExchangeRateManager Integration
6. Cross-Market Consistency

Author: Spock Trading System
Created: 2025-10-16
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, Mock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.market_filter_manager import MarketFilterManager, MarketFilterConfig, FilterResult
from modules.exchange_rate_manager import ExchangeRateManager


class TestMarketFilterManagerValidation(unittest.TestCase):
    """Validation tests for MarketFilterManager multi-market support"""

    def setUp(self):
        """Setup test environment"""
        self.manager = MarketFilterManager(config_dir='config/market_filters')
        self.rate_manager = ExchangeRateManager(db_manager=None)

    # ===================================
    # Test 1: Configuration Loading
    # ===================================

    def test_all_markets_loaded(self):
        """Test all 6 market configurations are loaded"""
        expected_markets = {'KR', 'US', 'HK', 'CN', 'JP', 'VN'}
        loaded_markets = set(self.manager.get_supported_regions())

        self.assertEqual(loaded_markets, expected_markets,
                        f"Expected markets: {expected_markets}, got: {loaded_markets}")

        print(f"✅ Test 1: All 6 markets loaded - PASSED")
        print(f"   Loaded: {', '.join(sorted(loaded_markets))}")

    # ===================================
    # Test 2: Configuration Structure Validation
    # ===================================

    def test_config_structure(self):
        """Test all configs have required structure"""
        required_attrs = [
            'region', 'market_name', 'currency',
            'default_exchange_rate', 'stage0_filters'
        ]

        for region in self.manager.get_supported_regions():
            config = self.manager.get_config(region)
            self.assertIsNotNone(config, f"Config not loaded for {region}")

            for attr in required_attrs:
                self.assertTrue(hasattr(config, attr),
                              f"{region} config missing attribute: {attr}")

        print(f"✅ Test 2: Configuration structure validation - PASSED")

    # ===================================
    # Test 3: Currency Settings Validation
    # ===================================

    def test_currency_settings(self):
        """Test currency and exchange rate settings"""
        expected_currencies = {
            'KR': ('KRW', 1.0),
            'US': ('USD', 1300.0),
            'HK': ('HKD', 170.0),
            'CN': ('CNY', 180.0),
            'JP': ('JPY', 10.0),
            'VN': ('VND', 0.055),
        }

        for region, (expected_currency, expected_rate) in expected_currencies.items():
            config = self.manager.get_config(region)
            self.assertEqual(config.currency, expected_currency,
                           f"{region} currency mismatch")
            self.assertEqual(config.default_exchange_rate, expected_rate,
                           f"{region} exchange rate mismatch")

        print(f"✅ Test 3: Currency settings validation - PASSED")

    # ===================================
    # Test 4: Threshold Normalization
    # ===================================

    def test_threshold_normalization(self):
        """Test all markets normalize to ₩100B market cap / ₩10B trading value"""
        target_market_cap = 100_000_000_000  # ₩100B
        target_trading_value = 10_000_000_000  # ₩10B

        print(f"\n🎯 Target thresholds:")
        print(f"   Market Cap: ₩{target_market_cap:,} (₩100B)")
        print(f"   Trading Value: ₩{target_trading_value:,} (₩10B)")
        print()

        for region in self.manager.get_supported_regions():
            config = self.manager.get_config(region)

            # Check market cap threshold
            market_cap_krw = config.get_min_market_cap_krw()
            market_cap_accuracy = (market_cap_krw / target_market_cap) * 100

            self.assertAlmostEqual(market_cap_krw, target_market_cap, delta=target_market_cap * 0.02,
                                  msg=f"{region} market cap threshold not within ±2% of ₩100B")

            # Check trading value threshold
            trading_value_krw = config.get_min_trading_value_krw()
            trading_value_accuracy = (trading_value_krw / target_trading_value) * 100

            self.assertAlmostEqual(trading_value_krw, target_trading_value, delta=target_trading_value * 0.02,
                                  msg=f"{region} trading value threshold not within ±2% of ₩10B")

            print(f"  [{region}] Market Cap: ₩{market_cap_krw:,} ({market_cap_accuracy:.2f}%)")
            print(f"        Trading Value: ₩{trading_value_krw:,} ({trading_value_accuracy:.2f}%)")

        print(f"\n✅ Test 4: Threshold normalization - PASSED")

    # ===================================
    # Test 5: Currency Conversion Consistency
    # ===================================

    def test_currency_conversion_consistency(self):
        """Test currency conversion matches ExchangeRateManager"""
        test_amount = 1000  # Local currency

        for region in self.manager.get_supported_regions():
            if region == 'KR':
                continue  # KRW is base currency

            config = self.manager.get_config(region)
            currency = config.currency

            # MarketFilterConfig conversion
            krw_from_config = config.convert_to_krw(test_amount)

            # ExchangeRateManager conversion
            krw_from_rate_mgr = self.rate_manager.convert_to_krw(test_amount, currency)

            self.assertEqual(krw_from_config, krw_from_rate_mgr,
                           f"{region} conversion mismatch: {krw_from_config} vs {krw_from_rate_mgr}")

        print(f"✅ Test 5: Currency conversion consistency - PASSED")

    # ===================================
    # Test 6: Market-Specific Rules
    # ===================================

    def test_market_specific_rules(self):
        """Test market-specific exclusion rules"""
        test_cases = [
            # US: Penny stock exclusion
            ('US', {'ticker': 'PENNY', 'price_local': 0.50, 'asset_type': 'STOCK'},
             True, 'penny_stock'),

            # US: Regular stock (should pass exclusion)
            ('US', {'ticker': 'AAPL', 'price_local': 150.0, 'asset_type': 'STOCK'},
             False, ''),

            # CN: Non-Stock Connect exclusion
            ('CN', {'ticker': '600000', 'is_stock_connect': False, 'asset_type': 'STOCK'},
             True, 'not_stock_connect'),

            # CN: Stock Connect (should pass)
            ('CN', {'ticker': '600519', 'is_stock_connect': True, 'asset_type': 'STOCK'},
             False, ''),

            # Common: ETF exclusion (need proper price to avoid penny stock check)
            ('US', {'ticker': 'SPY', 'asset_type': 'ETF', 'price_local': 400.0},
             True, 'etf'),

            # Common: Delisting exclusion (need proper price to avoid penny stock check)
            ('US', {'ticker': 'DELIST', 'is_delisting': True, 'asset_type': 'STOCK', 'price_local': 10.0},
             True, 'delisting'),
        ]

        for region, ticker_data, should_exclude, expected_reason in test_cases:
            config = self.manager.get_config(region)
            is_excluded, reason = config.should_exclude_ticker(ticker_data)

            self.assertEqual(is_excluded, should_exclude,
                           f"{region} {ticker_data.get('ticker')}: Expected exclude={should_exclude}, got={is_excluded}")

            if should_exclude:
                self.assertEqual(reason, expected_reason,
                               f"{region} {ticker_data.get('ticker')}: Wrong exclusion reason")

        print(f"✅ Test 6: Market-specific rules - PASSED")

    # ===================================
    # Test 7: Stage 0 Filter Application
    # ===================================

    def test_stage0_filter_application(self):
        """Test Stage 0 filter application across markets"""
        test_stocks = {
            'US': {
                'ticker': 'AAPL',
                'asset_type': 'STOCK',
                'market_cap_local': 3_000_000_000_000,  # $3T
                'trading_value_local': 100_000_000,  # $100M/day
                'price_local': 150.0,
            },
            'HK': {
                'ticker': '0700',
                'asset_type': 'STOCK',
                'market_cap_local': 3_000_000_000_000,  # HK$3T
                'trading_value_local': 5_000_000_000,  # HK$5B/day
                'price_local': 300.0,
            },
            'CN': {
                'ticker': '600519',
                'asset_type': 'STOCK',
                'is_stock_connect': True,
                'market_cap_local': 2_500_000_000_000,  # ¥2.5T
                'trading_value_local': 10_000_000_000,  # ¥10B/day
                'price_local': 1800.0,
            },
            'JP': {
                'ticker': '7203',
                'asset_type': 'STOCK',
                'market_cap_local': 30_000_000_000_000,  # ¥30T
                'trading_value_local': 100_000_000_000,  # ¥100B/day
                'price_local': 2500.0,
            },
            'VN': {
                'ticker': 'VCB',
                'asset_type': 'STOCK',
                'market_cap_local': 500_000_000_000_000,  # ₫500T
                'trading_value_local': 5_000_000_000_000,  # ₫5T/day
                'price_local': 90_000,
            },
        }

        for region, ticker_data in test_stocks.items():
            result = self.manager.apply_stage0_filter(region, ticker_data)

            self.assertTrue(result.passed,
                          f"{region} {ticker_data['ticker']} failed: {result.reason}")

            self.assertIn('market_cap_krw', result.normalized_data,
                         f"{region} missing normalized data")

            # Verify KRW values are populated
            self.assertGreater(result.normalized_data['market_cap_krw'], 0)
            self.assertGreater(result.normalized_data['trading_value_krw'], 0)

        print(f"✅ Test 7: Stage 0 filter application - PASSED")

    # ===================================
    # Test 8: Filter Result Data Structure
    # ===================================

    def test_filter_result_normalized_data(self):
        """Test FilterResult normalized data structure"""
        required_fields = [
            'market_cap_krw', 'trading_value_krw', 'current_price_krw',
            'market_cap_local', 'trading_value_local', 'current_price_local',
            'currency', 'exchange_rate_to_krw', 'exchange_rate_date', 'exchange_rate_source'
        ]

        # Test with US market
        ticker_data = {
            'ticker': 'TEST',
            'asset_type': 'STOCK',
            'market_cap_local': 100_000_000_000,  # $100B
            'trading_value_local': 10_000_000_000,  # $10B/day
            'price_local': 100.0,
        }

        result = self.manager.apply_stage0_filter('US', ticker_data)

        for field in required_fields:
            self.assertIn(field, result.normalized_data,
                         f"Missing field in normalized data: {field}")

        print(f"✅ Test 8: Filter result normalized data - PASSED")

    # ===================================
    # Test 9: Exchange Rate Updates
    # ===================================

    def test_exchange_rate_updates(self):
        """Test dynamic exchange rate updates"""
        # Get initial USD rate
        us_config = self.manager.get_config('US')
        initial_rate = us_config.get_exchange_rate()
        self.assertEqual(initial_rate, 1300.0, "Initial USD rate should be 1300")

        # Update rate
        new_rate = 1350.0
        self.manager.update_exchange_rate('US', new_rate, source='test')

        # Verify update
        updated_rate = us_config.get_exchange_rate()
        self.assertEqual(updated_rate, new_rate, "Rate not updated")

        # Test conversion with new rate
        test_amount = 100  # $100
        krw_amount = us_config.convert_to_krw(test_amount)
        expected_krw = int(test_amount * new_rate)  # 135,000

        self.assertEqual(krw_amount, expected_krw,
                        f"Conversion with updated rate failed: {krw_amount} vs {expected_krw}")

        # Reset to default
        self.manager.update_exchange_rate('US', 1300.0, source='test')

        print(f"✅ Test 9: Exchange rate updates - PASSED")

    # ===================================
    # Test 10: Price Range Validation
    # ===================================

    def test_price_range_validation(self):
        """Test price range thresholds"""
        test_cases = [
            # US: Below $5 minimum (₩6,500)
            ('US', {'ticker': 'LOW', 'asset_type': 'STOCK',
                   'market_cap_local': 100_000_000_000, 'trading_value_local': 10_000_000_000,
                   'price_local': 3.0},
             False, 'price_too_low'),

            # US: Above $5 minimum
            ('US', {'ticker': 'OK', 'asset_type': 'STOCK',
                   'market_cap_local': 100_000_000_000, 'trading_value_local': 10_000_000_000,
                   'price_local': 10.0},
             True, ''),
        ]

        for region, ticker_data, should_pass, expected_reason in test_cases:
            result = self.manager.apply_stage0_filter(region, ticker_data)

            self.assertEqual(result.passed, should_pass,
                           f"{region} {ticker_data['ticker']}: Expected pass={should_pass}, got={result.passed}")

            if not should_pass:
                self.assertIn(expected_reason, result.reason,
                            f"{region} {ticker_data['ticker']}: Wrong failure reason")

        print(f"✅ Test 10: Price range validation - PASSED")

    # ===================================
    # Test 11: Zero Value Filtering
    # ===================================

    def test_zero_value_filtering(self):
        """Test filtering of zero market cap/trading value (delisted stocks)"""
        test_cases = [
            # Zero market cap
            ('US', {'ticker': 'DELIST1', 'asset_type': 'STOCK',
                   'market_cap_local': 0, 'trading_value_local': 1000000,
                   'price_local': 10.0},
             False, 'market_cap_zero'),

            # Zero trading value
            ('US', {'ticker': 'DELIST2', 'asset_type': 'STOCK',
                   'market_cap_local': 100_000_000, 'trading_value_local': 0,
                   'price_local': 10.0},
             False, 'trading_value_zero'),
        ]

        for region, ticker_data, should_pass, expected_reason in test_cases:
            result = self.manager.apply_stage0_filter(region, ticker_data)

            self.assertEqual(result.passed, should_pass)
            if not should_pass:
                self.assertIn(expected_reason, result.reason)

        print(f"✅ Test 11: Zero value filtering - PASSED")

    # ===================================
    # Test 12: Get All Exchange Rates
    # ===================================

    def test_get_all_exchange_rates(self):
        """Test retrieving all exchange rates"""
        all_rates = self.manager.get_all_exchange_rates()

        expected_markets = {'KR', 'US', 'HK', 'CN', 'JP', 'VN'}
        self.assertEqual(set(all_rates.keys()), expected_markets,
                        "Missing markets in exchange rates")

        # Verify rates match defaults
        expected_rates = {
            'KR': 1.0, 'US': 1300.0, 'HK': 170.0,
            'CN': 180.0, 'JP': 10.0, 'VN': 0.055
        }

        for region, expected_rate in expected_rates.items():
            self.assertEqual(all_rates[region], expected_rate,
                           f"{region} rate mismatch")

        print(f"✅ Test 12: Get all exchange rates - PASSED")

    # ===================================
    # Test 13: Config Not Found Handling
    # ===================================

    def test_config_not_found(self):
        """Test handling of non-existent market config"""
        result = self.manager.apply_stage0_filter('XX', {})

        self.assertFalse(result.passed, "Should fail for unknown region")
        self.assertEqual(result.reason, 'no_config_for_XX')
        self.assertEqual(result.normalized_data, {})

        print(f"✅ Test 13: Config not found handling - PASSED")

    # ===================================
    # Test 14: Cross-Market Consistency
    # ===================================

    def test_cross_market_consistency(self):
        """Test same stock value is filtered consistently across markets"""
        # $100B market cap, $10B trading value in different currencies
        base_market_cap_krw = 130_000_000_000_000  # ₩130T
        base_trading_value_krw = 13_000_000_000_000  # ₩13T

        stocks = {
            'US': {
                'market_cap_local': base_market_cap_krw / 1300,  # $100B
                'trading_value_local': base_trading_value_krw / 1300,  # $10B
                'price_local': 100.0,
            },
            'HK': {
                'market_cap_local': base_market_cap_krw / 170,  # HK$765B
                'trading_value_local': base_trading_value_krw / 170,  # HK$76.5B
                'price_local': 100.0,
            },
            'CN': {
                'market_cap_local': base_market_cap_krw / 180,  # ¥722B
                'trading_value_local': base_trading_value_krw / 180,  # ¥72.2B
                'price_local': 100.0,
                'is_stock_connect': True,
            },
            'JP': {
                'market_cap_local': base_market_cap_krw / 10,  # ¥13T
                'trading_value_local': base_trading_value_krw / 10,  # ¥1.3T
                'price_local': 1000.0,
            },
            'VN': {
                'market_cap_local': base_market_cap_krw / 0.055,  # ₫2.36Q
                'trading_value_local': base_trading_value_krw / 0.055,  # ₫236T
                'price_local': 100_000,
            },
        }

        # All should pass (well above thresholds)
        for region, ticker_data in stocks.items():
            ticker_data.update({'ticker': 'TEST', 'asset_type': 'STOCK'})
            result = self.manager.apply_stage0_filter(region, ticker_data)

            self.assertTrue(result.passed,
                          f"{region} should pass with ₩130T market cap")

            # Verify KRW normalization is consistent (±5% tolerance)
            market_cap_krw = result.normalized_data['market_cap_krw']
            accuracy = abs(market_cap_krw - base_market_cap_krw) / base_market_cap_krw

            self.assertLess(accuracy, 0.05,
                          f"{region} KRW conversion accuracy: {accuracy*100:.2f}% (>5%)")

        print(f"✅ Test 14: Cross-market consistency - PASSED")

    # ===================================
    # Test 15: Config Reload
    # ===================================

    def test_config_reload(self):
        """Test configuration reload"""
        initial_count = len(self.manager.get_supported_regions())

        # Reload configs
        self.manager.reload_configs()

        reloaded_count = len(self.manager.get_supported_regions())

        self.assertEqual(initial_count, reloaded_count,
                        "Config count changed after reload")

        print(f"✅ Test 15: Config reload - PASSED")


def run_validation_tests():
    """Run all validation tests and generate report"""
    print("=" * 60)
    print("MarketFilterManager Multi-Market Validation Tests")
    print("Task 1.3: Validate MarketFilterManager multi-market support")
    print("=" * 60)
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMarketFilterManagerValidation)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print()
    print("=" * 60)
    print("Validation Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print()
        print("✅ All validation tests passed!")
        print("🎉 Task 1.3 COMPLETE: MarketFilterManager validated for multi-market support")
        return 0
    else:
        print()
        print("❌ Some validation tests failed")
        return 1


if __name__ == '__main__':
    exit_code = run_validation_tests()
    sys.exit(exit_code)
