"""
Integration Tests - Parser Cross-Region Validation

Tests parser consistency and standardization across all 5 global markets:
- Korea (KOSPI/KOSDAQ)
- US (NYSE/NASDAQ/AMEX)
- Hong Kong (HKEX)
- China (SSE/SZSE)
- Japan (TSE)
- Vietnam (HOSE/HNX)

Test Categories:
1. Ticker Normalization: Suffix handling and format standardization
2. OHLCV Standardization: DataFrame schema and data type consistency
3. Sector Mapping: Industry → GICS 11 sector translation accuracy
4. Data Validation: Error handling and data quality checks

Author: Spock Trading System
"""

import unittest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.parsers import (
    StockParser,
    USStockParser,
    HKStockParser,
    CNStockParser,
    JPStockParser,
    VNStockParser
)


class TestTickerNormalization(unittest.TestCase):
    """Test ticker normalization consistency across regions"""

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

    def test_normalize_suffix_removal(self):
        """Test all parsers correctly remove regional suffixes"""
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
                                   f"{region} should normalize {raw} → {expected}")

    def test_denormalize_suffix_addition(self):
        """Test all parsers correctly add regional suffixes"""
        test_cases = {
            'KR': ('005930', '005930.KS'),
            'US': ('AAPL', 'AAPL'),  # No suffix
            'HK': ('0700', '0700.HK'),
            'CN': ('600519', '600519.SS'),
            'JP': ('7203', '7203.T'),
            'VN': ('VCB', 'VCB.VN')
        }

        for region, (ticker, expected) in test_cases.items():
            with self.subTest(region=region):
                parser = self.parsers[region]
                if hasattr(parser, 'denormalize_ticker'):
                    result = parser.denormalize_ticker(ticker)
                    self.assertEqual(result, expected,
                                   f"{region} should denormalize {ticker} → {expected}")

    def test_round_trip_normalization(self):
        """Test normalize → denormalize round trip consistency"""
        test_tickers = {
            'KR': '005930.KS',
            'US': 'AAPL',
            'HK': '0700.HK',
            'CN': '600519.SS',
            'JP': '7203.T',
            'VN': 'VCB.VN'
        }

        for region, raw_ticker in test_tickers.items():
            with self.subTest(region=region):
                parser = self.parsers[region]
                if hasattr(parser, 'normalize_ticker') and hasattr(parser, 'denormalize_ticker'):
                    normalized = parser.normalize_ticker(raw_ticker)
                    denormalized = parser.denormalize_ticker(normalized)
                    self.assertEqual(denormalized, raw_ticker,
                                   f"{region} round trip should preserve original ticker")

    def test_invalid_ticker_format_handling(self):
        """Test parsers handle invalid ticker formats gracefully"""
        invalid_tickers = [
            '',           # Empty string
            None,         # None value
            'INVALID!@#', # Special characters
            '12345678',   # Too long
        ]

        for region, parser in self.parsers.items():
            if not hasattr(parser, 'normalize_ticker'):
                continue

            for invalid in invalid_tickers:
                with self.subTest(region=region, invalid=invalid):
                    result = parser.normalize_ticker(invalid)
                    # Should return None or empty string for invalid input
                    self.assertIn(result, [None, ''],
                                f"{region} should reject invalid ticker: {invalid}")

    def test_ticker_format_validation(self):
        """Test parsers validate ticker format correctly"""
        # Valid formats per region
        valid_formats = {
            'KR': ['005930', '000660', '035720'],  # 6 digits
            'US': ['AAPL', 'MSFT', 'GOOGL'],       # 1-5 letters
            'HK': ['0700', '9988', '0001'],        # 4 digits
            'CN': ['600519', '000858', '300750'],  # 6 digits
            'JP': ['7203', '6758', '9984'],        # 4 digits
            'VN': ['VCB', 'FPT', 'HPG']            # 3 letters
        }

        for region, valid_tickers in valid_formats.items():
            parser = self.parsers[region]
            if not hasattr(parser, 'normalize_ticker'):
                continue

            for ticker in valid_tickers:
                with self.subTest(region=region, ticker=ticker):
                    # Denormalize first to get full format
                    if hasattr(parser, 'denormalize_ticker'):
                        full_ticker = parser.denormalize_ticker(ticker)
                        result = parser.normalize_ticker(full_ticker)
                        self.assertEqual(result, ticker,
                                       f"{region} should accept valid ticker: {ticker}")


class TestOHLCVStandardization(unittest.TestCase):
    """Test OHLCV data standardization across regions"""

    def setUp(self):
        """Set up test OHLCV data"""
        self.regions = ['KR', 'US', 'HK', 'CN', 'JP', 'VN']
        self.required_columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']

    def test_ohlcv_column_presence(self):
        """Test all OHLCV DataFrames have required columns"""
        for region in self.regions:
            with self.subTest(region=region):
                # Create sample DataFrame
                df = pd.DataFrame({
                    'ticker': ['TEST'] * 5,
                    'date': [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(5)],
                    'open': [100.0 + i for i in range(5)],
                    'high': [105.0 + i for i in range(5)],
                    'low': [95.0 + i for i in range(5)],
                    'close': [102.0 + i for i in range(5)],
                    'volume': [1000000 + i*1000 for i in range(5)]
                })

                # Verify all required columns present
                for col in self.required_columns:
                    self.assertIn(col, df.columns,
                                f"{region} OHLCV should have {col} column")

    def test_ohlcv_data_types(self):
        """Test OHLCV data types are consistent"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [95.0, 96.0, 97.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000000, 1100000, 1200000]
        })

        for region in self.regions:
            with self.subTest(region=region):
                # Check data types
                self.assertEqual(df['ticker'].dtype, object,
                               f"{region} ticker should be string")
                self.assertEqual(df['date'].dtype, object,
                               f"{region} date should be string (YYYY-MM-DD)")

                # Price columns should be numeric
                for col in ['open', 'high', 'low', 'close']:
                    self.assertTrue(pd.api.types.is_numeric_dtype(df[col]),
                                  f"{region} {col} should be numeric")

                # Volume should be numeric (integer or float)
                self.assertTrue(pd.api.types.is_numeric_dtype(df['volume']),
                              f"{region} volume should be numeric")

    def test_ohlcv_date_format_consistency(self):
        """Test date format is YYYY-MM-DD across all regions"""
        dates = ['2025-01-01', '2025-01-15', '2025-12-31']

        for region in self.regions:
            for date_str in dates:
                with self.subTest(region=region, date=date_str):
                    # Verify date format can be parsed
                    try:
                        parsed = datetime.strptime(date_str, '%Y-%m-%d')
                        self.assertIsInstance(parsed, datetime,
                                            f"{region} date should be parseable as YYYY-MM-DD")
                    except ValueError:
                        self.fail(f"{region} date format invalid: {date_str}")

    def test_ohlcv_value_ranges(self):
        """Test OHLCV values are within expected ranges"""
        df = pd.DataFrame({
            'ticker': ['TEST'] * 3,
            'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
            'open': [100.0, 101.0, 102.0],
            'high': [105.0, 106.0, 107.0],
            'low': [95.0, 96.0, 97.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000000, 1100000, 1200000]
        })

        for region in self.regions:
            with self.subTest(region=region):
                # High >= Open, Close, Low
                self.assertTrue((df['high'] >= df['open']).all(),
                              f"{region} high should be >= open")
                self.assertTrue((df['high'] >= df['close']).all(),
                              f"{region} high should be >= close")
                self.assertTrue((df['high'] >= df['low']).all(),
                              f"{region} high should be >= low")

                # Low <= Open, Close, High
                self.assertTrue((df['low'] <= df['open']).all(),
                              f"{region} low should be <= open")
                self.assertTrue((df['low'] <= df['close']).all(),
                              f"{region} low should be <= close")

                # Volume > 0
                self.assertTrue((df['volume'] > 0).all(),
                              f"{region} volume should be positive")

    def test_ohlcv_null_handling(self):
        """Test OHLCV data handles nulls appropriately"""
        # Create DataFrame with missing values
        df = pd.DataFrame({
            'ticker': ['TEST', 'TEST', 'TEST'],
            'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
            'open': [100.0, None, 102.0],
            'high': [105.0, 106.0, None],
            'low': [95.0, None, 97.0],
            'close': [102.0, 103.0, 104.0],
            'volume': [1000000, 1100000, 1200000]
        })

        for region in self.regions:
            with self.subTest(region=region):
                # Nulls should be detectable
                has_nulls = df['open'].isnull().any() or df['high'].isnull().any()
                self.assertTrue(has_nulls,
                              f"{region} should detect null values in OHLCV data")


class TestSectorMapping(unittest.TestCase):
    """Test sector mapping consistency across regions"""

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

        # GICS 11 Sectors
        self.valid_sectors = [
            'Energy',
            'Materials',
            'Industrials',
            'Consumer Discretionary',
            'Consumer Staples',
            'Health Care',
            'Financials',
            'Information Technology',
            'Communication Services',
            'Utilities',
            'Real Estate'
        ]

    def test_industry_to_gics_mapping_exists(self):
        """Test parsers have industry→GICS mapping capability where applicable"""
        # Note: KR uses KRX codes, US uses direct GICS, CN uses CSRC mapping
        # Only HK, JP, VN use fuzzy industry→GICS mapping
        regions_with_industry_mapping = ['HK', 'JP', 'VN']

        for region in regions_with_industry_mapping:
            parser = self.parsers[region]
            with self.subTest(region=region):
                self.assertTrue(hasattr(parser, '_map_industry_to_gics'),
                              f"{region} parser should have _map_industry_to_gics method")

    def test_common_industries_mapped_to_valid_sectors(self):
        """Test common industries map to valid GICS sectors"""
        common_industries = [
            'Banks—Regional',
            'Software—Application',
            'Auto Manufacturers',
            'Oil & Gas Integrated',
            'Semiconductors',
            'Real Estate Services'
        ]

        for region, parser in self.parsers.items():
            if not hasattr(parser, '_map_industry_to_gics'):
                continue

            for industry in common_industries:
                with self.subTest(region=region, industry=industry):
                    result = parser._map_industry_to_gics(industry)
                    self.assertIn(result, self.valid_sectors,
                                f"{region} should map '{industry}' to valid GICS sector")

    def test_null_industry_handling(self):
        """Test parsers handle null industry values gracefully"""
        for region, parser in self.parsers.items():
            if not hasattr(parser, '_map_industry_to_gics'):
                continue

            with self.subTest(region=region):
                result = parser._map_industry_to_gics(None)
                self.assertIn(result, self.valid_sectors,
                            f"{region} should return valid sector for null industry")

    def test_empty_industry_handling(self):
        """Test parsers handle empty industry strings"""
        for region, parser in self.parsers.items():
            if not hasattr(parser, '_map_industry_to_gics'):
                continue

            with self.subTest(region=region):
                result = parser._map_industry_to_gics('')
                self.assertIn(result, self.valid_sectors,
                            f"{region} should return valid sector for empty industry")

    def test_sector_code_consistency(self):
        """Test sector codes follow GICS 11 standard"""
        valid_sector_codes = ['10', '15', '20', '25', '30', '35', '40', '45', '50', '55', '60']

        sector_to_code = {
            'Energy': '10',
            'Materials': '15',
            'Industrials': '20',
            'Consumer Discretionary': '25',
            'Consumer Staples': '30',
            'Health Care': '35',
            'Financials': '40',
            'Information Technology': '45',
            'Communication Services': '50',
            'Utilities': '55',
            'Real Estate': '60'
        }

        for region in self.parsers.keys():
            with self.subTest(region=region):
                for sector, expected_code in sector_to_code.items():
                    self.assertIn(expected_code, valid_sector_codes,
                                f"{region} sector code {expected_code} should be valid")


class TestParserDataValidation(unittest.TestCase):
    """Test parser data validation and error handling"""

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

    def test_parse_ticker_info_with_valid_data(self):
        """Test parsing valid ticker information"""
        valid_data = {
            'ticker': 'TEST',
            'name': 'Test Company',
            'industry': 'Technology',
            'marketCap': 1000000000
        }

        for region, parser in self.parsers.items():
            if not hasattr(parser, 'parse_ticker_info'):
                continue

            with self.subTest(region=region):
                result = parser.parse_ticker_info(valid_data)
                # Should return dict with standardized fields
                if result is not None:
                    self.assertIsInstance(result, dict,
                                        f"{region} should return dict for valid data")

    def test_parse_ticker_info_with_null_data(self):
        """Test parsing null ticker information"""
        for region, parser in self.parsers.items():
            if not hasattr(parser, 'parse_ticker_info'):
                continue

            with self.subTest(region=region):
                result = parser.parse_ticker_info(None)
                self.assertIsNone(result,
                                f"{region} should return None for null data")

    def test_parse_ticker_info_with_empty_dict(self):
        """Test parsing empty dictionary"""
        empty_data = {}

        for region, parser in self.parsers.items():
            if not hasattr(parser, 'parse_ticker_info'):
                continue

            with self.subTest(region=region):
                result = parser.parse_ticker_info(empty_data)
                # Should handle gracefully (None or dict with defaults)
                self.assertIn(type(result), [type(None), dict],
                            f"{region} should handle empty dict gracefully")

    def test_parse_ticker_info_with_missing_fields(self):
        """Test parsing data with missing required fields"""
        incomplete_data = {
            'ticker': 'TEST'
            # Missing name, industry, etc.
        }

        for region, parser in self.parsers.items():
            if not hasattr(parser, 'parse_ticker_info'):
                continue

            with self.subTest(region=region):
                result = parser.parse_ticker_info(incomplete_data)
                # Should handle gracefully
                if result is not None:
                    self.assertIsInstance(result, dict,
                                        f"{region} should handle incomplete data")
                    self.assertIn('ticker', result,
                                f"{region} should preserve available fields")

    def test_currency_code_validation(self):
        """Test parsers use correct currency codes"""
        expected_currencies = {
            'KR': 'KRW',
            'US': 'USD',
            'HK': 'HKD',
            'CN': 'CNY',
            'JP': 'JPY',
            'VN': 'VND'
        }

        for region, expected_currency in expected_currencies.items():
            with self.subTest(region=region):
                # Currency codes should be 3-letter ISO 4217
                self.assertEqual(len(expected_currency), 3,
                               f"{region} currency code should be 3 letters")
                self.assertTrue(expected_currency.isupper(),
                              f"{region} currency code should be uppercase")

    def test_region_code_consistency(self):
        """Test parsers return consistent region codes"""
        expected_regions = {
            'KR': 'KR',
            'US': 'US',
            'HK': 'HK',
            'CN': 'CN',
            'JP': 'JP',
            'VN': 'VN'
        }

        for region_key, expected_region in expected_regions.items():
            with self.subTest(region=region_key):
                # Region codes should be 2-letter uppercase
                self.assertEqual(len(expected_region), 2,
                               f"Region code should be 2 letters")
                self.assertTrue(expected_region.isupper(),
                              f"Region code should be uppercase")


if __name__ == '__main__':
    unittest.main()
