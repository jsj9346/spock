"""
Unit Tests for USStockParser

Tests Polygon.io response parsing and data normalization.

Author: Spock Trading System
"""

import unittest
import pandas as pd
from modules.parsers.us_stock_parser import USStockParser


class TestUSStockParser(unittest.TestCase):
    """Test suite for USStockParser"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = USStockParser()

    def test_parse_ticker_list(self):
        """Test parsing Polygon.io ticker list response"""
        polygon_response = [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'locale': 'us',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True,
                'currency_name': 'usd',
                'cik': '0000320193',
                'composite_figi': 'BBG000B9XRY4'
            },
            {
                'ticker': 'MSFT',
                'name': 'Microsoft Corporation',
                'market': 'stocks',
                'locale': 'us',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True,
                'currency_name': 'usd'
            }
        ]

        result = self.parser.parse_ticker_list(polygon_response)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], 'AAPL')
        self.assertEqual(result[0]['exchange'], 'NASDAQ')
        self.assertEqual(result[0]['region'], 'US')
        self.assertEqual(result[0]['currency'], 'USD')
        self.assertEqual(result[0]['asset_type'], 'Common Stock')

    def test_parse_ticker_list_filters_non_stocks(self):
        """Test that non-stock assets are filtered out"""
        polygon_response = [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'type': 'CS',
                'active': True
            },
            {
                'ticker': 'SPY.OPT',
                'name': 'SPY Option',
                'market': 'options',  # Not a stock
                'type': 'OPT',
                'active': True
            }
        ]

        result = self.parser.parse_ticker_list(polygon_response)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticker'], 'AAPL')

    def test_parse_single_ticker(self):
        """Test parsing single ticker"""
        raw_data = {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'market': 'stocks',
            'primary_exchange': 'XNAS',
            'type': 'CS',
            'active': True,
            'currency_name': 'usd',
            'cik': '0000320193'
        }

        result = self.parser._parse_single_ticker(raw_data)

        self.assertIsNotNone(result)
        self.assertEqual(result['ticker'], 'AAPL')
        self.assertEqual(result['name'], 'Apple Inc.')
        self.assertEqual(result['exchange'], 'NASDAQ')
        self.assertEqual(result['exchange_code'], 'XNAS')
        self.assertEqual(result['asset_type'], 'Common Stock')
        self.assertEqual(result['cik'], '0000320193')

    def test_parse_ticker_details(self):
        """Test parsing ticker details response"""
        polygon_response = {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'market': 'stocks',
            'primary_exchange': 'XNAS',
            'type': 'CS',
            'active': True,
            'currency_name': 'usd',
            'description': 'Apple Inc. designs, manufactures, and markets smartphones',
            'homepage_url': 'https://www.apple.com',
            'total_employees': 164000,
            'list_date': '1980-12-12',
            'market_cap': 2800000000000,
            'share_class_shares_outstanding': 15550000000,
            'sic_code': '3571',
            'sic_description': 'ELECTRONIC COMPUTERS'
        }

        result = self.parser.parse_ticker_details(polygon_response)

        self.assertIsNotNone(result)
        self.assertEqual(result['ticker'], 'AAPL')
        self.assertEqual(result['name'], 'Apple Inc.')
        self.assertEqual(result['total_employees'], 164000)
        self.assertEqual(result['listing_date'], '1980-12-12')
        self.assertEqual(result['market_cap'], 2800000000000)
        self.assertEqual(result['sic_code'], '3571')
        self.assertEqual(result['sector'], 'Information Technology')

    def test_parse_ohlcv_data(self):
        """Test parsing OHLCV aggregates response"""
        polygon_response = [
            {
                'v': 100000000,
                'vw': 150.25,
                'o': 150.00,
                'c': 151.00,
                'h': 152.00,
                'l': 149.50,
                't': 1609459200000,
                'n': 500000,
                'date': '2021-01-01'
            },
            {
                'v': 95000000,
                'vw': 151.50,
                'o': 151.00,
                'c': 152.00,
                'h': 153.00,
                'l': 150.50,
                't': 1609545600000,
                'n': 480000,
                'date': '2021-01-02'
            }
        ]

        result = self.parser.parse_ohlcv_data(polygon_response, 'AAPL')

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]['ticker'], 'AAPL')
        self.assertEqual(result.iloc[0]['open'], 150.00)
        self.assertEqual(result.iloc[0]['close'], 151.00)
        self.assertEqual(result.iloc[0]['volume'], 100000000)

    def test_parse_ohlcv_empty_response(self):
        """Test parsing empty OHLCV response"""
        result = self.parser.parse_ohlcv_data([], 'AAPL')

        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 0)

    def test_map_sic_to_gics_energy(self):
        """Test SIC to GICS mapping for Energy sector"""
        self.assertEqual(self.parser._map_sic_to_gics('1311', ''), 'Energy')  # Oil & Gas
        self.assertEqual(self.parser._map_sic_to_gics('2911', ''), 'Energy')  # Petroleum Refining

    def test_map_sic_to_gics_technology(self):
        """Test SIC to GICS mapping for Information Technology"""
        self.assertEqual(self.parser._map_sic_to_gics('3571', 'ELECTRONIC COMPUTERS'),
                        'Information Technology')
        self.assertEqual(self.parser._map_sic_to_gics('7370', 'SOFTWARE'),
                        'Information Technology')

    def test_map_sic_to_gics_financials(self):
        """Test SIC to GICS mapping for Financials"""
        self.assertEqual(self.parser._map_sic_to_gics('6021', 'NATIONAL COMMERCIAL BANKS'),
                        'Financials')
        self.assertEqual(self.parser._map_sic_to_gics('6311', 'LIFE INSURANCE'),
                        'Financials')

    def test_map_sic_to_gics_healthcare(self):
        """Test SIC to GICS mapping for Health Care"""
        self.assertEqual(self.parser._map_sic_to_gics('2834', 'PHARMACEUTICAL PREPARATIONS'),
                        'Health Care')
        self.assertEqual(self.parser._map_sic_to_gics('8071', 'MEDICAL LABORATORIES'),
                        'Health Care')

    def test_map_sic_to_gics_consumer_discretionary(self):
        """Test SIC to GICS mapping for Consumer Discretionary"""
        self.assertEqual(self.parser._map_sic_to_gics('3711', 'MOTOR VEHICLES'),
                        'Consumer Discretionary')
        self.assertEqual(self.parser._map_sic_to_gics('5311', 'DEPARTMENT STORES'),
                        'Consumer Discretionary')

    def test_map_sic_to_gics_utilities(self):
        """Test SIC to GICS mapping for Utilities"""
        self.assertEqual(self.parser._map_sic_to_gics('4911', 'ELECTRIC SERVICES'),
                        'Utilities')

    def test_map_sic_to_gics_unknown(self):
        """Test SIC to GICS mapping for unknown codes"""
        self.assertEqual(self.parser._map_sic_to_gics('9999', ''), 'Unknown')
        self.assertEqual(self.parser._map_sic_to_gics('', ''), 'Unknown')
        self.assertEqual(self.parser._map_sic_to_gics('INVALID', ''), 'Unknown')

    def test_parse_address(self):
        """Test address parsing"""
        address_dict = {
            'address1': '1 Apple Park Way',
            'city': 'Cupertino',
            'state': 'CA',
            'postal_code': '95014'
        }

        result = self.parser._parse_address(address_dict)

        self.assertEqual(result, '1 Apple Park Way, Cupertino, CA, 95014')

    def test_parse_address_empty(self):
        """Test parsing empty address"""
        self.assertIsNone(self.parser._parse_address(None))
        self.assertIsNone(self.parser._parse_address({}))

    def test_validate_ticker_format_valid(self):
        """Test valid ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('AAPL'))
        self.assertTrue(self.parser.validate_ticker_format('MSFT'))
        self.assertTrue(self.parser.validate_ticker_format('BRK.A'))
        self.assertTrue(self.parser.validate_ticker_format('BRK.B'))
        self.assertTrue(self.parser.validate_ticker_format('A'))
        self.assertTrue(self.parser.validate_ticker_format('GOOGL'))

    def test_validate_ticker_format_invalid(self):
        """Test invalid ticker format validation"""
        self.assertFalse(self.parser.validate_ticker_format(''))
        self.assertFalse(self.parser.validate_ticker_format('123'))
        self.assertFalse(self.parser.validate_ticker_format('aapl'))  # Lowercase
        self.assertFalse(self.parser.validate_ticker_format('TOOLONG'))  # > 5 chars
        self.assertFalse(self.parser.validate_ticker_format('A@PPL'))  # Special char
        self.assertFalse(self.parser.validate_ticker_format(None))

    def test_filter_common_stocks(self):
        """Test filtering for common stocks only"""
        tickers = [
            {'ticker': 'AAPL', 'asset_type_code': 'CS', 'active': True},
            {'ticker': 'SPY', 'asset_type_code': 'ETF', 'active': True},
            {'ticker': 'BAC.PFD', 'asset_type_code': 'PFD', 'active': True},
            {'ticker': 'MSFT', 'asset_type_code': 'CS', 'active': True},
            {'ticker': 'TSLA', 'asset_type_code': 'CS', 'active': False}  # Inactive
        ]

        result = self.parser.filter_common_stocks(tickers)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], 'AAPL')
        self.assertEqual(result[1]['ticker'], 'MSFT')

    def test_enrich_with_sector(self):
        """Test enriching tickers with sector information"""
        tickers = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.'},
            {'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
            {'ticker': 'JPM', 'name': 'JPMorgan Chase'}
        ]

        sector_map = {
            'AAPL': 'Information Technology',
            'MSFT': 'Information Technology',
            'JPM': 'Financials'
        }

        result = self.parser.enrich_with_sector(tickers, sector_map)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['sector'], 'Information Technology')
        self.assertEqual(result[2]['sector'], 'Financials')

    def test_exchange_mapping(self):
        """Test exchange code mapping"""
        test_cases = [
            ('XNYS', 'NYSE'),
            ('XNAS', 'NASDAQ'),
            ('XASE', 'AMEX'),
            ('BATS', 'BATS'),
            ('ARCX', 'NYSE Arca')
        ]

        for exchange_code, expected_name in test_cases:
            raw_data = {
                'ticker': 'TEST',
                'name': 'Test Stock',
                'market': 'stocks',
                'primary_exchange': exchange_code,
                'type': 'CS',
                'active': True
            }

            result = self.parser._parse_single_ticker(raw_data)
            self.assertEqual(result['exchange'], expected_name)

    def test_asset_type_mapping(self):
        """Test asset type code mapping"""
        test_cases = [
            ('CS', 'Common Stock'),
            ('PFD', 'Preferred Stock'),
            ('ETF', 'ETF'),
            ('WARRANT', 'Warrant')
        ]

        for asset_type_code, expected_type in test_cases:
            raw_data = {
                'ticker': 'TEST',
                'name': 'Test Asset',
                'market': 'stocks',
                'type': asset_type_code,
                'active': True
            }

            result = self.parser._parse_single_ticker(raw_data)
            self.assertEqual(result['asset_type'], expected_type)


if __name__ == '__main__':
    unittest.main()
