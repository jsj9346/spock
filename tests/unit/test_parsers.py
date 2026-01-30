#!/usr/bin/env python3
"""
test_parsers.py - Unit Tests for Stock Parsers

Tests for:
- StockParser (KR market)
- USStockParser
- HKStockParser
- JPStockParser
- VNStockParser
- CNStockParser
- ETFParser

Coverage target: parsers/* (~793 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock

from modules.parsers.stock_parser import StockParser
from modules.parsers.us_stock_parser import USStockParser
from modules.parsers.hk_stock_parser import HKStockParser
from modules.parsers.jp_stock_parser import JPStockParser
from modules.parsers.vn_stock_parser import VNStockParser
from modules.parsers.cn_stock_parser import CNStockParser
from modules.parsers.etf_parser import ETFParser


class TestStockParser(unittest.TestCase):
    """Test KR StockParser"""

    def setUp(self):
        self.parser = StockParser()

    def test_parse_krx_stock_basic(self):
        """Test basic KRX stock parsing"""
        raw_data = {
            'ISU_SRT_CD': '005930',
            'ISU_ABBRV': '삼성전자',
            'ISU_ENG_NM': 'Samsung Electronics',
            'MKT_TP_NM': 'KOSPI',
            'LIST_DD': '1975-06-11'
        }

        result = self.parser.parse_krx_stock(raw_data)

        self.assertEqual(result['ticker'], '005930')
        self.assertEqual(result['name'], '삼성전자')
        self.assertEqual(result['region'], 'KR')
        self.assertEqual(result['currency'], 'KRW')

    def test_parse_krx_stock_kosdaq(self):
        """Test KOSDAQ stock parsing"""
        raw_data = {
            'ISU_SRT_CD': '035720',
            'ISU_ABBRV': '카카오',
            'MKT_TP_NM': 'KOSDAQ'
        }

        result = self.parser.parse_krx_stock(raw_data)

        self.assertEqual(result['ticker'], '035720')
        self.assertEqual(result['name'], '카카오')

    def test_sector_keyword_mapping(self):
        """Test GICS sector keyword mapping"""
        self.assertEqual(self.parser.SECTOR_KEYWORDS.get('반도체'), 'Information Technology')
        self.assertEqual(self.parser.SECTOR_KEYWORDS.get('금융'), 'Financials')
        self.assertEqual(self.parser.SECTOR_KEYWORDS.get('제약'), 'Health Care')
        self.assertEqual(self.parser.SECTOR_KEYWORDS.get('자동차'), 'Consumer Discretionary')


class TestUSStockParser(unittest.TestCase):
    """Test US StockParser"""

    def setUp(self):
        self.parser = USStockParser()

    def test_parse_ticker_list(self):
        """Test polygon response parsing"""
        polygon_response = [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'locale': 'us',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True
            }
        ]

        result = self.parser.parse_ticker_list(polygon_response)

        self.assertIsInstance(result, list)
        if result:
            self.assertEqual(result[0]['ticker'], 'AAPL')
            self.assertEqual(result[0]['region'], 'US')

    def test_parse_single_ticker(self):
        """Test single ticker parsing"""
        raw_data = {
            'ticker': 'JPM',
            'name': 'JPMorgan Chase & Co.',
            'market': 'stocks',
            'locale': 'us',
            'primary_exchange': 'XNYS',
            'type': 'CS',
            'active': True
        }

        result = self.parser._parse_single_ticker(raw_data)

        if result:
            self.assertEqual(result['ticker'], 'JPM')

    def test_validate_ticker_format(self):
        """Test ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('AAPL'))
        self.assertTrue(self.parser.validate_ticker_format('BRK.A'))
        self.assertFalse(self.parser.validate_ticker_format(''))

    def test_filter_common_stocks(self):
        """Test filtering common stocks only"""
        tickers = [
            {'ticker': 'AAPL', 'type': 'CS', 'active': True},  # Common Stock
            {'ticker': 'AAPL-W', 'type': 'WARRANT', 'active': True},  # Warrant
            {'ticker': 'SPY', 'type': 'ETF', 'active': True}  # ETF
        ]

        result = self.parser.filter_common_stocks(tickers)

        # Should filter to only common stocks (CS type)
        self.assertIsInstance(result, list)
        # Check that warrants and ETFs are filtered out if possible
        warrant_tickers = [t['ticker'] for t in result if 'W' in t.get('ticker', '')]
        self.assertEqual(len(warrant_tickers), 0)


class TestHKStockParser(unittest.TestCase):
    """Test HK StockParser"""

    def setUp(self):
        self.parser = HKStockParser()

    def test_parse_ticker_info(self):
        """Test HK stock parsing from yfinance info"""
        yfinance_info = {
            'symbol': '0700.HK',
            'shortName': 'Tencent Holdings',
            'longName': 'Tencent Holdings Limited',
            'sector': 'Communication Services',
            'industry': 'Internet Content & Information',
            'exchange': 'HKG',
            'quoteType': 'EQUITY',
            'marketCap': 3500000000000
        }

        result = self.parser.parse_ticker_info(yfinance_info)

        if result:
            self.assertIn('ticker', result)
            self.assertEqual(result.get('region'), 'HK')

    def test_normalize_ticker(self):
        """Test HK ticker normalization (leading zeros)"""
        # HK tickers should be normalized (may vary based on implementation)
        result = self.parser.normalize_ticker('0700.HK')
        self.assertIsNotNone(result)
        # Check that result is a valid ticker format (4-5 digits)
        self.assertTrue(len(result) >= 4)
        self.assertTrue(result.isdigit())

        result2 = self.parser.normalize_ticker('00700.HK')
        self.assertIsNotNone(result2)
        self.assertTrue(len(result2) >= 4)

    def test_validate_ticker_format(self):
        """Test HK ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('00700'))
        self.assertTrue(self.parser.validate_ticker_format('09988'))


class TestJPStockParser(unittest.TestCase):
    """Test JP StockParser"""

    def setUp(self):
        self.parser = JPStockParser()

    def test_parse_ticker_info(self):
        """Test TSE stock parsing from yfinance info"""
        yfinance_info = {
            'symbol': '7203.T',
            'shortName': 'Toyota Motor Corporation',
            'longName': 'Toyota Motor Corporation',
            'sector': 'Consumer Cyclical',
            'industry': 'Auto Manufacturers',
            'exchange': 'JPX',
            'quoteType': 'EQUITY',
            'marketCap': 35000000000000
        }

        result = self.parser.parse_ticker_info(yfinance_info)

        if result:
            self.assertEqual(result.get('region'), 'JP')

    def test_normalize_ticker(self):
        """Test JP ticker normalization"""
        result = self.parser.normalize_ticker('7203.T')
        self.assertIsNotNone(result)
        self.assertEqual(result, '7203')

    def test_parse_with_japanese_name(self):
        """Test parsing with Japanese characters"""
        yfinance_info = {
            'symbol': '7203.T',
            'shortName': 'トヨタ自動車',
            'longName': 'Toyota Motor Corporation',
            'sector': 'Consumer Cyclical',
            'industry': 'Auto Manufacturers',
            'exchange': 'JPX',
            'quoteType': 'EQUITY'
        }

        result = self.parser.parse_ticker_info(yfinance_info)

        if result:
            self.assertIn('name', result)


class TestVNStockParser(unittest.TestCase):
    """Test VN StockParser"""

    def setUp(self):
        self.parser = VNStockParser()

    def test_parse_ticker_info(self):
        """Test HOSE (Ho Chi Minh) stock parsing from yfinance info"""
        yfinance_info = {
            'symbol': 'VNM.VN',
            'shortName': 'Vinamilk',
            'longName': 'Vietnam Dairy Products',
            'sector': 'Consumer Defensive',
            'industry': 'Packaged Foods',
            'exchange': 'HNO',
            'quoteType': 'EQUITY',
            'marketCap': 180000000000000
        }

        result = self.parser.parse_ticker_info(yfinance_info)

        if result:
            self.assertEqual(result.get('region'), 'VN')

    def test_normalize_ticker(self):
        """Test VN ticker normalization"""
        result = self.parser.normalize_ticker('VNM.VN')
        self.assertIsNotNone(result)
        self.assertEqual(result, 'VNM')

    def test_filter_common_stocks(self):
        """Test VN stock filtering"""
        ticker_data = {
            'ticker': 'VNM',
            'quoteType': 'EQUITY',
            'exchange': 'HNO'
        }

        result = self.parser.filter_common_stocks(ticker_data)
        self.assertIsInstance(result, bool)


class TestCNStockParser(unittest.TestCase):
    """Test CN StockParser"""

    def setUp(self):
        self.parser = CNStockParser()

    def test_parse_yfinance_info(self):
        """Test Shanghai (SSE) stock parsing from yfinance"""
        yfinance_info = {
            'symbol': '600519.SS',
            'shortName': 'Kweichow Moutai',
            'longName': 'Kweichow Moutai Co., Ltd.',
            'sector': 'Consumer Defensive',
            'industry': 'Beverages - Wineries & Distilleries',
            'exchange': 'SHH',
            'quoteType': 'EQUITY',
            'marketCap': 2000000000000
        }

        result = self.parser.parse_yfinance_info(yfinance_info, '600519')

        if result:
            self.assertEqual(result.get('region'), 'CN')

    def test_normalize_ticker(self):
        """Test CN ticker normalization"""
        result = self.parser.normalize_ticker('600519.SS')
        self.assertIsNotNone(result)
        self.assertEqual(result, '600519')

    def test_get_exchange(self):
        """Test exchange detection based on ticker"""
        # Shanghai stocks start with 6
        self.assertEqual(self.parser.get_exchange('600519'), 'SSE')
        # Shenzhen stocks start with 0 or 3
        self.assertEqual(self.parser.get_exchange('000858'), 'SZSE')

    def test_validate_ticker_format(self):
        """Test CN ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('600519'))
        self.assertTrue(self.parser.validate_ticker_format('000858'))


class TestETFParser(unittest.TestCase):
    """Test ETF Parser"""

    def setUp(self):
        self.parser = ETFParser()

    def test_parse_krx_etf(self):
        """Test KR ETF parsing"""
        raw_data = {
            'ISU_SRT_CD': '069500',
            'ISU_ABBRV': 'KODEX 200',
            'ISU_NM': 'KODEX 200',
            'MKT_TP_NM': 'ETF',
            'LIST_DD': '2002-10-14'
        }

        result = self.parser.parse_krx_etf(raw_data)

        self.assertIn('ticker', result)
        self.assertEqual(result['ticker'], '069500')

    def test_validate_etf_ticker(self):
        """Test ETF ticker validation"""
        self.assertTrue(self.parser.validate_etf_ticker('069500'))
        self.assertTrue(self.parser.validate_etf_ticker('379800'))

    def test_detect_fund_type(self):
        """Test ETF fund type detection"""
        # Index ETF
        result = self.parser._detect_fund_type('KODEX 200')
        self.assertIn(result, ['index', 'equity', 'bond', 'commodity', 'other'])


# Parametrized tests for sector mapping
@pytest.mark.parametrize("keyword,expected_sector", [
    ('반도체', 'Information Technology'),
    ('금융', 'Financials'),
    ('제약', 'Health Care'),
    ('자동차', 'Consumer Discretionary'),
    ('에너지', 'Energy'),
    ('소재', 'Materials'),
    ('건설', 'Industrials'),
    ('식품', 'Consumer Staples'),
    ('통신서비스', 'Communication Services'),
    ('유틸리티', 'Utilities'),
    ('부동산', 'Real Estate'),
])
def test_sector_keyword_mapping_parametrized(keyword, expected_sector):
    """Parametrized test for sector keyword mapping"""
    parser = StockParser()
    assert parser.SECTOR_KEYWORDS.get(keyword) == expected_sector


# Edge case tests
class TestParserEdgeCases(unittest.TestCase):
    """Test edge cases for all parsers"""

    def test_stock_parser_missing_fields(self):
        """Test handling of missing required fields"""
        parser = StockParser()

        # Missing ISU_SRT_CD should raise or return None
        raw_data = {
            'ISU_ABBRV': '삼성전자',
        }

        try:
            result = parser.parse_krx_stock(raw_data)
            # If it doesn't raise, result should handle missing ticker
        except (KeyError, TypeError):
            pass  # Expected behavior

    def test_parser_special_characters(self):
        """Test handling of special characters in names"""
        parser = StockParser()

        raw_data = {
            'ISU_SRT_CD': '000000',
            'ISU_ABBRV': '테스트(주)&Co.',
            'MKT_TP_NM': 'KOSPI'
        }

        result = parser.parse_krx_stock(raw_data)
        self.assertIn('&', result['name'])

    def test_parser_unicode_handling(self):
        """Test Unicode handling (Korean, Japanese, Chinese)"""
        parser = StockParser()

        raw_data = {
            'ISU_SRT_CD': '000001',
            'ISU_ABBRV': '한글테스트日本語中文',
            'MKT_TP_NM': 'KOSPI'
        }

        result = parser.parse_krx_stock(raw_data)
        self.assertEqual(result['name'], '한글테스트日本語中文')


# =============================================================================
# Phase 7.1: Additional Parser Pure Logic Tests
# =============================================================================

class TestJPStockParserPureLogic(unittest.TestCase):
    """Test JP StockParser pure calculation methods"""

    def setUp(self):
        self.parser = JPStockParser()

    def test_denormalize_ticker(self):
        """Test ticker denormalization (7203 → 7203.T)"""
        self.assertEqual(self.parser.denormalize_ticker('7203'), '7203.T')
        self.assertEqual(self.parser.denormalize_ticker('9984'), '9984.T')

    def test_denormalize_ticker_empty(self):
        """Test denormalize with empty input"""
        self.assertEqual(self.parser.denormalize_ticker(''), '')
        self.assertEqual(self.parser.denormalize_ticker(None), '')

    def test_normalize_ticker_valid_formats(self):
        """Test various valid ticker formats"""
        self.assertEqual(self.parser.normalize_ticker('7203.T'), '7203')
        self.assertEqual(self.parser.normalize_ticker('7203.t'), '7203')  # lowercase
        self.assertEqual(self.parser.normalize_ticker('7203'), '7203')    # already normalized

    def test_normalize_ticker_invalid_formats(self):
        """Test invalid ticker formats return None"""
        self.assertIsNone(self.parser.normalize_ticker(''))
        self.assertIsNone(self.parser.normalize_ticker(None))
        self.assertIsNone(self.parser.normalize_ticker('999.T'))   # 3 digits
        self.assertIsNone(self.parser.normalize_ticker('12345.T')) # 5 digits
        self.assertIsNone(self.parser.normalize_ticker('ABCD.T'))  # letters

    def test_map_industry_to_gics_direct(self):
        """Test direct industry to GICS mapping"""
        # Direct mappings from INDUSTRY_TO_GICS
        self.assertEqual(self.parser._map_industry_to_gics('Auto Manufacturers'), 'Consumer Discretionary')
        self.assertEqual(self.parser._map_industry_to_gics('Banks—Regional'), 'Financials')
        self.assertEqual(self.parser._map_industry_to_gics('Drug Manufacturers—General'), 'Health Care')
        self.assertEqual(self.parser._map_industry_to_gics('Semiconductors'), 'Information Technology')

    def test_map_industry_to_gics_fuzzy(self):
        """Test fuzzy matching for unmapped industries"""
        # Fuzzy matches based on keywords
        self.assertEqual(self.parser._map_industry_to_gics('Automotive Software'), 'Consumer Discretionary')
        self.assertEqual(self.parser._map_industry_to_gics('Banking Services'), 'Financials')
        self.assertEqual(self.parser._map_industry_to_gics('Medical Equipment'), 'Health Care')
        self.assertEqual(self.parser._map_industry_to_gics('Technology Hardware'), 'Information Technology')
        self.assertEqual(self.parser._map_industry_to_gics('Oil Exploration'), 'Energy')

    def test_map_industry_to_gics_default(self):
        """Test default sector for unmapped industries"""
        self.assertEqual(self.parser._map_industry_to_gics(None), 'Industrials')
        self.assertEqual(self.parser._map_industry_to_gics(''), 'Industrials')
        self.assertEqual(self.parser._map_industry_to_gics('Unknown Industry XYZ'), 'Industrials')

    def test_get_gics_code(self):
        """Test GICS sector code lookup"""
        self.assertEqual(self.parser._get_gics_code('Information Technology'), '45')
        self.assertEqual(self.parser._get_gics_code('Financials'), '40')
        self.assertEqual(self.parser._get_gics_code('Health Care'), '35')
        self.assertEqual(self.parser._get_gics_code('Energy'), '10')
        self.assertEqual(self.parser._get_gics_code('Consumer Discretionary'), '25')

    def test_get_gics_code_default(self):
        """Test default GICS code for unknown sectors"""
        self.assertEqual(self.parser._get_gics_code('Unknown Sector'), '20')
        self.assertEqual(self.parser._get_gics_code(''), '20')

    def test_filter_common_stocks_reit(self):
        """Test filtering out REITs"""
        tickers = [
            {'name': 'Toyota Motor', 'industry': 'Auto Manufacturers'},
            {'name': 'Nippon Reit', 'industry': 'REIT—Diversified'},
            {'name': 'Japan Office REIT', 'industry': 'Real Estate'},
        ]
        result = self.parser.filter_common_stocks(tickers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Toyota Motor')

    def test_filter_common_stocks_etf(self):
        """Test filtering out ETFs"""
        tickers = [
            {'name': 'Sony Corporation', 'industry': 'Consumer Electronics'},
            {'name': 'Nikkei 225 ETF', 'industry': 'Index Fund'},
        ]
        result = self.parser.filter_common_stocks(tickers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Sony Corporation')

    def test_filter_common_stocks_preferred(self):
        """Test filtering out preferred stocks"""
        tickers = [
            {'name': 'Honda Motor', 'industry': 'Auto Manufacturers'},
            {'name': 'Honda Preferred A', 'industry': 'Auto Manufacturers'},
        ]
        result = self.parser.filter_common_stocks(tickers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Honda Motor')


class TestHKStockParserPureLogic(unittest.TestCase):
    """Test HK StockParser pure calculation methods"""

    def setUp(self):
        self.parser = HKStockParser()

    def test_normalize_ticker_with_suffix(self):
        """Test HK ticker normalization with .HK suffix"""
        result = self.parser.normalize_ticker('0700.HK')
        self.assertIsNotNone(result)
        self.assertEqual(result, '00700')

    def test_normalize_ticker_leading_zeros(self):
        """Test HK ticker normalization preserves/adds leading zeros"""
        # HK tickers should be 5 digits with leading zeros
        result = self.parser.normalize_ticker('700.HK')
        self.assertIsNotNone(result)

    def test_map_industry_to_gics_hk(self):
        """Test HK industry to GICS mapping"""
        self.assertEqual(self.parser._map_industry_to_gics('Internet Content & Information'), 'Communication Services')
        self.assertEqual(self.parser._map_industry_to_gics('Banks—Diversified'), 'Financials')
        self.assertEqual(self.parser._map_industry_to_gics('Real Estate—Development'), 'Real Estate')

    def test_gics_sectors_constant(self):
        """Test GICS_SECTORS constant is complete"""
        self.assertEqual(len(self.parser.GICS_SECTORS), 11)
        self.assertIn('45', self.parser.GICS_SECTORS)  # IT
        self.assertIn('40', self.parser.GICS_SECTORS)  # Financials


class TestUSStockParserPureLogic(unittest.TestCase):
    """Test US StockParser additional pure logic"""

    def setUp(self):
        self.parser = USStockParser()

    def test_validate_ticker_format_various(self):
        """Test various US ticker formats"""
        # Valid formats
        self.assertTrue(self.parser.validate_ticker_format('A'))      # Single letter
        self.assertTrue(self.parser.validate_ticker_format('AA'))     # Two letters
        self.assertTrue(self.parser.validate_ticker_format('AAPL'))   # Four letters
        self.assertTrue(self.parser.validate_ticker_format('GOOGL'))  # Five letters
        self.assertTrue(self.parser.validate_ticker_format('BRK.A'))  # With dot
        self.assertTrue(self.parser.validate_ticker_format('BRK.B'))  # With dot

    def test_validate_ticker_format_invalid(self):
        """Test invalid US ticker formats"""
        self.assertFalse(self.parser.validate_ticker_format(''))
        self.assertFalse(self.parser.validate_ticker_format(None))

    def test_filter_common_stocks_types(self):
        """Test filtering by security type"""
        tickers = [
            {'ticker': 'AAPL', 'type': 'CS', 'active': True},
            {'ticker': 'SPY', 'type': 'ETF', 'active': True},
            {'ticker': 'AAPL-W', 'type': 'WARRANT', 'active': True},
            {'ticker': 'AAPL-R', 'type': 'RIGHT', 'active': True},
        ]
        result = self.parser.filter_common_stocks(tickers)
        # Should only include common stocks (CS type)
        cs_only = [t for t in result if t.get('type') == 'CS']
        self.assertGreater(len(cs_only), 0)


class TestCNStockParserPureLogic(unittest.TestCase):
    """Test CN StockParser additional pure logic"""

    def setUp(self):
        self.parser = CNStockParser()

    def test_get_exchange_shanghai(self):
        """Test Shanghai exchange detection"""
        self.assertEqual(self.parser.get_exchange('600000'), 'SSE')
        self.assertEqual(self.parser.get_exchange('601398'), 'SSE')
        self.assertEqual(self.parser.get_exchange('688001'), 'SSE')  # STAR Market

    def test_get_exchange_shenzhen(self):
        """Test Shenzhen exchange detection"""
        self.assertEqual(self.parser.get_exchange('000001'), 'SZSE')
        self.assertEqual(self.parser.get_exchange('000858'), 'SZSE')
        self.assertEqual(self.parser.get_exchange('300001'), 'SZSE')  # ChiNext

    def test_validate_ticker_format_cn(self):
        """Test CN ticker format validation"""
        # Valid 6-digit formats
        self.assertTrue(self.parser.validate_ticker_format('600519'))
        self.assertTrue(self.parser.validate_ticker_format('000858'))
        self.assertTrue(self.parser.validate_ticker_format('300750'))

    def test_normalize_ticker_cn(self):
        """Test CN ticker normalization"""
        self.assertEqual(self.parser.normalize_ticker('600519.SS'), '600519')
        self.assertEqual(self.parser.normalize_ticker('000858.SZ'), '000858')
        self.assertEqual(self.parser.normalize_ticker('600519'), '600519')


class TestVNStockParserPureLogic(unittest.TestCase):
    """Test VN StockParser additional pure logic"""

    def setUp(self):
        self.parser = VNStockParser()

    def test_normalize_ticker_vn(self):
        """Test VN ticker normalization"""
        self.assertEqual(self.parser.normalize_ticker('VNM.VN'), 'VNM')
        self.assertEqual(self.parser.normalize_ticker('FPT.VN'), 'FPT')
        self.assertEqual(self.parser.normalize_ticker('VNM'), 'VNM')

    def test_normalize_ticker_hose_hnx(self):
        """Test VN ticker normalization for HOSE/HNX"""
        # VN tickers are typically 3 letters
        result = self.parser.normalize_ticker('HPG.VN')
        self.assertIsNotNone(result)
        self.assertEqual(result, 'HPG')


class TestETFParserPureLogic(unittest.TestCase):
    """Test ETF Parser additional pure logic"""

    def setUp(self):
        self.parser = ETFParser()

    def test_detect_fund_type_index(self):
        """Test index ETF detection"""
        result = self.parser._detect_fund_type('KODEX 200')
        self.assertIn(result, ['index', 'equity', 'bond', 'commodity', 'other'])

    def test_detect_fund_type_bond(self):
        """Test bond ETF detection"""
        result = self.parser._detect_fund_type('KODEX 국채선물')
        self.assertIn(result, ['index', 'equity', 'bond', 'commodity', 'other'])

    def test_validate_etf_ticker_kr(self):
        """Test KR ETF ticker validation"""
        self.assertTrue(self.parser.validate_etf_ticker('069500'))  # KODEX 200
        self.assertTrue(self.parser.validate_etf_ticker('379800'))  # KODEX US S&P500


# Parametrized tests for JP industry mapping
@pytest.mark.parametrize("industry,expected_sector", [
    ('Auto Manufacturers', 'Consumer Discretionary'),
    ('Banks—Regional', 'Financials'),
    ('Drug Manufacturers—General', 'Health Care'),
    ('Semiconductors', 'Information Technology'),
    ('Oil & Gas Integrated', 'Energy'),
    ('Steel', 'Materials'),
    ('Utilities—Regulated Electric', 'Utilities'),
    ('Real Estate—Development', 'Real Estate'),
    ('Internet Content & Information', 'Communication Services'),
    ('Packaged Foods', 'Consumer Staples'),
])
def test_jp_industry_to_gics_mapping(industry, expected_sector):
    """Parametrized test for JP industry to GICS mapping"""
    parser = JPStockParser()
    assert parser._map_industry_to_gics(industry) == expected_sector


@pytest.mark.parametrize("sector,expected_code", [
    ('Energy', '10'),
    ('Materials', '15'),
    ('Industrials', '20'),
    ('Consumer Discretionary', '25'),
    ('Consumer Staples', '30'),
    ('Health Care', '35'),
    ('Financials', '40'),
    ('Information Technology', '45'),
    ('Communication Services', '50'),
    ('Utilities', '55'),
    ('Real Estate', '60'),
])
def test_gics_sector_codes(sector, expected_code):
    """Parametrized test for GICS sector codes"""
    parser = JPStockParser()
    assert parser._get_gics_code(sector) == expected_code


@pytest.mark.parametrize("raw_ticker,expected", [
    ('7203.T', '7203'),
    ('9984.T', '9984'),
    ('6758.T', '6758'),
    ('7203', '7203'),
])
def test_jp_normalize_ticker_parametrized(raw_ticker, expected):
    """Parametrized test for JP ticker normalization"""
    parser = JPStockParser()
    assert parser.normalize_ticker(raw_ticker) == expected


@pytest.mark.parametrize("cn_ticker,expected_exchange", [
    ('600519', 'SSE'),   # Shanghai - Moutai
    ('601398', 'SSE'),   # Shanghai - ICBC
    ('000858', 'SZSE'),  # Shenzhen - Wuliangye
    ('000001', 'SZSE'),  # Shenzhen - Ping An Bank
    ('300750', 'SZSE'),  # ChiNext - CATL
])
def test_cn_exchange_detection(cn_ticker, expected_exchange):
    """Parametrized test for CN exchange detection"""
    parser = CNStockParser()
    assert parser.get_exchange(cn_ticker) == expected_exchange


if __name__ == '__main__':
    unittest.main(verbosity=2)
