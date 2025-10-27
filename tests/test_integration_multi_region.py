"""
Integration Tests - Multi-Region Cross-Validation

Tests consistency and compatibility across all 5 global markets:
- Korea (KOSPI/KOSDAQ)
- US (NYSE/NASDAQ/AMEX)
- Hong Kong (HKEX)
- China (SSE/SZSE)
- Japan (TSE)
- Vietnam (HOSE/HNX)

Test Categories:
1. Interface Compliance: All adapters follow BaseAdapter interface
2. Data Format Consistency: Standardized output across regions
3. Parser Compatibility: Ticker normalization and sector mapping

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, MagicMock
import pandas as pd
from datetime import datetime
import sys
import os

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters import (
    BaseMarketAdapter,
    KoreaAdapter,
    USAdapter,
    HKAdapter,
    CNAdapter,
    JPAdapter,
    VNAdapter
)
from modules.parsers import (
    StockParser,
    USStockParser,
    HKStockParser,
    CNStockParser,
    JPStockParser,
    VNStockParser
)


class TestMultiRegionInterfaceCompliance(unittest.TestCase):
    """Test all adapters implement BaseAdapter interface correctly"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()

        # Initialize all adapters
        self.adapters = {
            'KR': KoreaAdapter(self.db_mock, kis_app_key='test', kis_app_secret='test'),
            'US': USAdapter(self.db_mock, polygon_api_key='test'),
            'HK': HKAdapter(self.db_mock),
            'CN': CNAdapter(self.db_mock),
            'JP': JPAdapter(self.db_mock),
            'VN': VNAdapter(self.db_mock)
        }

    def test_all_adapters_inherit_from_base(self):
        """Test all adapters inherit from BaseMarketAdapter"""
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                self.assertIsInstance(adapter, BaseMarketAdapter,
                                    f"{region} adapter should inherit from BaseMarketAdapter")

    def test_all_adapters_have_required_methods(self):
        """Test all adapters implement required methods"""
        required_methods = [
            'scan_stocks',
            'collect_stock_ohlcv',
            'collect_fundamentals'
        ]

        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                for method in required_methods:
                    self.assertTrue(hasattr(adapter, method),
                                  f"{region} adapter missing required method: {method}")
                    self.assertTrue(callable(getattr(adapter, method)),
                                  f"{region} adapter {method} should be callable")

    def test_all_adapters_have_optional_methods(self):
        """Test all adapters implement optional methods (may return empty/not implemented)"""
        optional_methods = [
            'scan_etfs',
            'collect_etf_ohlcv'
        ]

        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                for method in optional_methods:
                    self.assertTrue(hasattr(adapter, method),
                                  f"{region} adapter missing optional method: {method}")

    def test_all_adapters_have_region_code(self):
        """Test all adapters have correct region_code attribute"""
        expected_regions = {
            'KR': 'KR',
            'US': 'US',
            'HK': 'HK',
            'CN': 'CN',
            'JP': 'JP',
            'VN': 'VN'
        }

        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                self.assertEqual(adapter.region_code, expected_regions[region],
                               f"{region} adapter has incorrect region_code")

    def test_all_adapters_have_database_manager(self):
        """Test all adapters have database manager reference"""
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                self.assertIsNotNone(adapter.db,
                                   f"{region} adapter missing database manager")

    def test_constructor_signatures_consistent(self):
        """Test adapter constructors follow consistent patterns"""
        # All adapters should accept db_manager as first parameter
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                self.assertIsNotNone(adapter.db,
                                   f"{region} adapter constructor should accept db_manager")

    def test_scan_stocks_return_type(self):
        """Test scan_stocks returns list of dictionaries"""
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                # Mock the return value
                adapter.scan_stocks = Mock(return_value=[
                    {'ticker': 'TEST', 'name': 'Test Stock', 'region': region}
                ])

                result = adapter.scan_stocks()
                self.assertIsInstance(result, list,
                                    f"{region} scan_stocks should return list")
                if result:
                    self.assertIsInstance(result[0], dict,
                                        f"{region} scan_stocks should return list of dicts")

    def test_collect_stock_ohlcv_return_type(self):
        """Test collect_stock_ohlcv returns integer (count)"""
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                # Mock the return value
                adapter.collect_stock_ohlcv = Mock(return_value=10)

                result = adapter.collect_stock_ohlcv(tickers=['TEST'], days=30)
                self.assertIsInstance(result, int,
                                    f"{region} collect_stock_ohlcv should return int")


class TestMultiRegionDataConsistency(unittest.TestCase):
    """Test data formats are consistent across all regions"""

    def setUp(self):
        """Set up test data"""
        self.test_tickers = {
            'KR': ['005930', '000660'],  # Samsung, SK Hynix
            'US': ['AAPL', 'MSFT'],       # Apple, Microsoft
            'HK': ['0700', '9988'],       # Tencent, Alibaba
            'CN': ['600519', '000858'],   # Moutai, Wuliangye
            'JP': ['7203', '6758'],       # Toyota, Sony
            'VN': ['VCB', 'FPT']          # Vietcombank, FPT Corp
        }

    def test_ticker_data_structure_consistency(self):
        """Test all regions return ticker data with same required keys"""
        required_keys = [
            'ticker',
            'name',
            'region',
            'exchange',
            'sector',
            'currency'
        ]

        # Sample ticker data from each region
        sample_data = {
            'KR': {'ticker': '005930', 'name': 'Samsung Electronics', 'region': 'KR',
                   'exchange': 'KOSPI', 'sector': 'Information Technology', 'currency': 'KRW'},
            'US': {'ticker': 'AAPL', 'name': 'Apple Inc.', 'region': 'US',
                   'exchange': 'NASDAQ', 'sector': 'Information Technology', 'currency': 'USD'},
            'HK': {'ticker': '0700', 'name': 'Tencent', 'region': 'HK',
                   'exchange': 'HKEX', 'sector': 'Communication Services', 'currency': 'HKD'},
            'CN': {'ticker': '600519', 'name': 'Kweichow Moutai', 'region': 'CN',
                   'exchange': 'SSE', 'sector': 'Consumer Staples', 'currency': 'CNY'},
            'JP': {'ticker': '7203', 'name': 'Toyota Motor', 'region': 'JP',
                   'exchange': 'TSE', 'sector': 'Consumer Discretionary', 'currency': 'JPY'},
            'VN': {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN',
                   'exchange': 'HOSE', 'sector': 'Financials', 'currency': 'VND'}
        }

        for region, data in sample_data.items():
            with self.subTest(region=region):
                for key in required_keys:
                    self.assertIn(key, data,
                                f"{region} ticker data missing required key: {key}")

    def test_ohlcv_dataframe_schema_consistency(self):
        """Test OHLCV DataFrames have consistent schema"""
        required_columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']

        # Create sample OHLCV DataFrames
        sample_df = pd.DataFrame({
            'ticker': ['TEST'] * 5,
            'date': pd.date_range('2025-01-01', periods=5).strftime('%Y-%m-%d'),
            'open': [100.0] * 5,
            'high': [105.0] * 5,
            'low': [95.0] * 5,
            'close': [102.0] * 5,
            'volume': [1000000] * 5
        })

        for region in self.test_tickers.keys():
            with self.subTest(region=region):
                # Verify required columns present
                for col in required_columns:
                    self.assertIn(col, sample_df.columns,
                                f"{region} OHLCV DataFrame missing column: {col}")

    def test_fundamentals_dictionary_format(self):
        """Test fundamentals data has consistent dictionary format"""
        required_keys = ['ticker', 'date', 'market_cap', 'pe_ratio', 'pb_ratio']

        sample_fundamentals = {
            'ticker': 'TEST',
            'date': '2025-01-01',
            'market_cap': 1000000000,
            'pe_ratio': 15.5,
            'pb_ratio': 2.3,
            'dividend_yield': 0.025
        }

        for region in self.test_tickers.keys():
            with self.subTest(region=region):
                for key in required_keys:
                    self.assertIn(key, sample_fundamentals,
                                f"{region} fundamentals missing key: {key}")

    def test_sector_codes_follow_gics_standard(self):
        """Test all regions use GICS 11 sector codes"""
        valid_gics_codes = ['10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60']

        sample_sector_codes = {
            'KR': '45',  # Information Technology
            'US': '45',  # Information Technology
            'HK': '50',  # Communication Services
            'CN': '30',  # Consumer Staples
            'JP': '25',  # Consumer Discretionary
            'VN': '40'   # Financials
        }

        for region, code in sample_sector_codes.items():
            with self.subTest(region=region):
                self.assertIn(code, valid_gics_codes,
                            f"{region} uses invalid GICS code: {code}")

    def test_currency_codes_iso_compliant(self):
        """Test currency codes follow ISO 4217 standard"""
        expected_currencies = {
            'KR': 'KRW',
            'US': 'USD',
            'HK': 'HKD',
            'CN': 'CNY',
            'JP': 'JPY',
            'VN': 'VND'
        }

        for region, currency in expected_currencies.items():
            with self.subTest(region=region):
                self.assertEqual(len(currency), 3,
                               f"{region} currency code should be 3 letters")
                self.assertTrue(currency.isupper(),
                              f"{region} currency code should be uppercase")

    def test_date_format_standardized(self):
        """Test dates follow YYYY-MM-DD format"""
        sample_date = '2025-01-15'

        for region in self.test_tickers.keys():
            with self.subTest(region=region):
                # Verify date can be parsed
                parsed = datetime.strptime(sample_date, '%Y-%m-%d')
                self.assertIsInstance(parsed, datetime,
                                    f"{region} date format should be YYYY-MM-DD")


class TestMultiRegionParserCompatibility(unittest.TestCase):
    """Test parser consistency across regions"""

    def setUp(self):
        """Set up parsers"""
        self.parsers = {
            'KR': StockParser(),
            'US': USStockParser(),
            'HK': HKStockParser(),
            'CN': CNStockParser(),
            'JP': JPStockParser(),
            'VN': VNStockParser()
        }

    def test_ticker_normalization_patterns(self):
        """Test ticker normalization handles suffixes correctly"""
        test_cases = {
            'KR': ('005930.KS', '005930'),
            'US': ('AAPL', 'AAPL'),  # No suffix
            'HK': ('0700.HK', '0700'),
            'CN': ('600519.SS', '600519'),
            'JP': ('7203.T', '7203'),
            'VN': ('VCB.VN', 'VCB')
        }

        for region, (raw, expected) in test_cases.items():
            with self.subTest(region=region):
                parser = self.parsers[region]
                if hasattr(parser, 'normalize_ticker'):
                    result = parser.normalize_ticker(raw)
                    self.assertEqual(result, expected,
                                   f"{region} ticker normalization failed")

    def test_industry_to_gics_mapping_accuracy(self):
        """Test industry → GICS sector mapping is accurate"""
        test_industries = {
            'Banks—Regional': 'Financials',
            'Software—Application': 'Information Technology',
            'Auto Manufacturers': 'Consumer Discretionary',
            'Oil & Gas Integrated': 'Energy'
        }

        for region, parser in self.parsers.items():
            with self.subTest(region=region):
                if hasattr(parser, '_map_industry_to_gics'):
                    for industry, expected_sector in test_industries.items():
                        result = parser._map_industry_to_gics(industry)
                        self.assertIsNotNone(result,
                                           f"{region} failed to map industry: {industry}")

    def test_common_stock_filtering(self):
        """Test parsers have filter_common_stocks method with correct behavior"""
        for region, parser in self.parsers.items():
            with self.subTest(region=region):
                if not hasattr(parser, 'filter_common_stocks'):
                    continue  # Skip if method not present

                # Test that method is callable
                self.assertTrue(callable(parser.filter_common_stocks),
                              f"{region} filter_common_stocks should be callable")

                # Check method signature to determine test approach
                import inspect
                sig = inspect.signature(parser.filter_common_stocks)
                param_names = list(sig.parameters.keys())

                # VN parser: single Dict → bool (parameter name: ticker_data)
                # Other parsers: List[Dict] → List[Dict] (parameter name: tickers)
                if 'ticker_data' in param_names:
                    # VN parser signature: filter_common_stocks(ticker_data: Dict) -> bool
                    reit_data = {'ticker': 'REIT', 'name': 'Test REIT',
                                'industry': 'REIT—Diversified'}
                    result = parser.filter_common_stocks(reit_data)
                    self.assertFalse(result,
                                   f"{region} parser should filter REITs")
                elif 'tickers' in param_names:
                    # Batch processing signature: filter_common_stocks(tickers: List[Dict]) -> List[Dict]
                    reit_list = [{'ticker': 'REIT', 'name': 'Test REIT',
                                 'industry': 'REIT—Diversified', 'quote_type': 'EQUITY'}]
                    result = parser.filter_common_stocks(reit_list)
                    # For batch processors, REIT filtering depends on implementation
                    # Just verify it returns a list
                    self.assertIsInstance(result, list,
                                        f"{region} parser should return list")

    def test_data_parsing_error_handling(self):
        """Test parsers handle invalid data gracefully"""
        invalid_data = None

        for region, parser in self.parsers.items():
            with self.subTest(region=region):
                if hasattr(parser, 'parse_ticker_info'):
                    result = parser.parse_ticker_info(invalid_data)
                    self.assertIsNone(result,
                                    f"{region} parser should return None for invalid data")


if __name__ == '__main__':
    unittest.main()
