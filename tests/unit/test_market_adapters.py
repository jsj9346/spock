#!/usr/bin/env python3
"""
test_market_adapters.py - Unit Tests for Market Adapters Module

Tests for:
- BaseMarketAdapter: Lot size validation/defaults (no DB dependency)
- TickerValidator: Ticker format validation and normalization
- BaseSectorMapper & GICSSectorMapper: GICS sector classification
- MarketCalendar: Trading hours, holidays, market status

Coverage target: market_adapters/* (~800 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time, timedelta


# ============================================================
# TickerValidator Tests
# ============================================================

class TestTickerValidatorKR(unittest.TestCase):
    """Test Korean ticker validation"""

    def test_validate_kr_valid_ticker(self):
        """Test valid Korean ticker (6-digit)"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("005930", "KR"))
        self.assertTrue(TickerValidator.validate("000660", "KR"))
        self.assertTrue(TickerValidator.validate("123456", "KR"))

    def test_validate_kr_invalid_ticker(self):
        """Test invalid Korean ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("AAPL", "KR"))  # Non-numeric
        self.assertFalse(TickerValidator.validate("1234567", "KR"))  # 7 digits
        # Note: "12345" (5 digits) is valid because it gets zero-padded to "012345"

    def test_normalize_kr_pad_zeros(self):
        """Test Korean ticker zero padding"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertEqual(TickerValidator.normalize("5930", "KR"), "005930")
        self.assertEqual(TickerValidator.normalize("660", "KR"), "000660")


class TestTickerValidatorUS(unittest.TestCase):
    """Test US ticker validation"""

    def test_validate_us_valid_ticker(self):
        """Test valid US tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("AAPL", "US"))
        self.assertTrue(TickerValidator.validate("MSFT", "US"))
        self.assertTrue(TickerValidator.validate("A", "US"))  # Single letter
        self.assertTrue(TickerValidator.validate("BRK.B", "US"))  # With suffix

    def test_validate_us_invalid_ticker(self):
        """Test invalid US tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("005930", "US"))  # Numeric
        self.assertFalse(TickerValidator.validate("TOOLONG", "US"))  # >5 chars

    def test_normalize_us_uppercase(self):
        """Test US ticker uppercase normalization"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertEqual(TickerValidator.normalize("aapl", "US"), "AAPL")
        self.assertEqual(TickerValidator.normalize("brk.b", "US"), "BRK.B")


class TestTickerValidatorCN(unittest.TestCase):
    """Test Chinese ticker validation"""

    def test_validate_cn_valid_ticker(self):
        """Test valid Chinese tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("600000.SS", "CN"))
        self.assertTrue(TickerValidator.validate("000001.SZ", "CN"))
        self.assertTrue(TickerValidator.validate("600519.SH", "CN"))

    def test_validate_cn_invalid_ticker(self):
        """Test invalid Chinese tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("600000", "CN"))  # No suffix
        self.assertFalse(TickerValidator.validate("600000.XX", "CN"))  # Invalid suffix

    def test_normalize_cn_missing_suffix(self):
        """Test Chinese ticker normalization fails without suffix"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertIsNone(TickerValidator.normalize("600000", "CN"))


class TestTickerValidatorHK(unittest.TestCase):
    """Test Hong Kong ticker validation"""

    def test_validate_hk_valid_ticker(self):
        """Test valid HK tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("0700.HK", "HK"))
        self.assertTrue(TickerValidator.validate("09988.HK", "HK"))

    def test_normalize_hk_add_suffix(self):
        """Test HK ticker adds .HK suffix"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertEqual(TickerValidator.normalize("700", "HK"), "0700.HK")


class TestTickerValidatorJP(unittest.TestCase):
    """Test Japanese ticker validation"""

    def test_validate_jp_valid_ticker(self):
        """Test valid Japanese tickers (4-digit)"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("7203", "JP"))
        self.assertTrue(TickerValidator.validate("6758", "JP"))

    def test_normalize_jp_pad_zeros(self):
        """Test Japanese ticker zero padding"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertEqual(TickerValidator.normalize("203", "JP"), "0203")


class TestTickerValidatorVN(unittest.TestCase):
    """Test Vietnamese ticker validation"""

    def test_validate_vn_valid_ticker(self):
        """Test valid Vietnamese tickers (3-letter)"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertTrue(TickerValidator.validate("VNM", "VN"))
        self.assertTrue(TickerValidator.validate("FPT", "VN"))

    def test_validate_vn_invalid_ticker(self):
        """Test invalid Vietnamese tickers"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("VNMX", "VN"))  # 4 letters
        self.assertFalse(TickerValidator.validate("VN", "VN"))    # 2 letters


class TestTickerValidatorCommon(unittest.TestCase):
    """Test common TickerValidator methods"""

    def test_validate_empty_ticker(self):
        """Test validation with empty ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("", "KR"))
        self.assertFalse(TickerValidator.validate(None, "KR"))

    def test_validate_unknown_region(self):
        """Test validation with unknown region"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertFalse(TickerValidator.validate("AAPL", "XX"))

    def test_normalize_empty_ticker(self):
        """Test normalization with empty ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        self.assertIsNone(TickerValidator.normalize("", "KR"))
        self.assertIsNone(TickerValidator.normalize(None, "KR"))

    def test_extract_components_us(self):
        """Test extracting components from US ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        result = TickerValidator.extract_components("BRK.B", "US")

        self.assertEqual(result['code'], "BRK")
        self.assertEqual(result['suffix'], "B")
        self.assertEqual(result['region'], "US")

    def test_extract_components_cn(self):
        """Test extracting components from Chinese ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        result = TickerValidator.extract_components("600000.SS", "CN")

        self.assertEqual(result['code'], "600000")
        self.assertEqual(result['suffix'], "SS")
        self.assertIn("Shanghai", result['exchange'])

    def test_get_exchange_from_ticker(self):
        """Test getting exchange from ticker"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        exchange = TickerValidator.get_exchange_from_ticker("600000.SS", "CN")
        self.assertIn("Shanghai", exchange)

    def test_validate_batch(self):
        """Test batch validation"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        tickers = ["005930", "AAPL", "12345", "000660"]
        result = TickerValidator.validate_batch(tickers, "KR")

        # "12345" is valid because it gets padded to "012345"
        self.assertEqual(result['valid_count'], 3)
        self.assertEqual(result['invalid_count'], 1)
        self.assertIn("005930", result['valid'])
        self.assertIn("AAPL", result['invalid'])

    def test_get_region_info(self):
        """Test getting region validation info"""
        from modules.market_adapters.validators.ticker_validator import TickerValidator

        info = TickerValidator.get_region_info("KR")

        self.assertEqual(info['region'], "KR")
        self.assertIsNotNone(info['pattern'])
        self.assertIsNotNone(info['rules'])


# ============================================================
# BaseSectorMapper Tests
# ============================================================

class TestBaseSectorMapper(unittest.TestCase):
    """Test BaseSectorMapper abstract class methods"""

    def test_gics_sectors_constant(self):
        """Test GICS_SECTORS contains 11 sectors"""
        from modules.market_adapters.sector_mappers.base_mapper import BaseSectorMapper

        self.assertEqual(len(BaseSectorMapper.GICS_SECTORS), 11)
        self.assertIn('45', BaseSectorMapper.GICS_SECTORS)  # IT
        self.assertEqual(BaseSectorMapper.GICS_SECTORS['45'], 'Information Technology')

    def test_validate_gics_code_valid(self):
        """Test validating valid GICS codes"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()

        self.assertTrue(mapper.validate_gics_code('10'))  # Energy
        self.assertTrue(mapper.validate_gics_code('45'))  # IT
        self.assertTrue(mapper.validate_gics_code('60'))  # Real Estate

    def test_validate_gics_code_invalid(self):
        """Test validating invalid GICS codes"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()

        self.assertFalse(mapper.validate_gics_code('99'))
        self.assertFalse(mapper.validate_gics_code(''))
        self.assertFalse(mapper.validate_gics_code('XX'))

    def test_get_gics_sector_name(self):
        """Test getting GICS sector name from code"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()

        self.assertEqual(mapper.get_gics_sector_name('45'), 'Information Technology')
        self.assertEqual(mapper.get_gics_sector_name('40'), 'Financials')
        self.assertIsNone(mapper.get_gics_sector_name('99'))

    def test_get_fallback_mapping(self):
        """Test fallback mapping returns Industrials"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()
        fallback = mapper.get_fallback_mapping()

        self.assertEqual(fallback['sector'], 'Industrials')
        self.assertEqual(fallback['sector_code'], '20')

    def test_normalize_sector_name(self):
        """Test sector name normalization"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()

        self.assertEqual(mapper._normalize_sector_name("  IT  "), "IT")
        self.assertEqual(mapper._normalize_sector_name(""), "")
        self.assertEqual(mapper._normalize_sector_name(None), "")

    def test_get_mapping_stats_empty(self):
        """Test mapping stats with no data"""
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

        mapper = GICSSectorMapper()
        stats = mapper.get_mapping_stats()

        self.assertEqual(stats['total_mappings'], 0)


# ============================================================
# GICSSectorMapper Tests
# ============================================================

class TestGICSSectorMapper(unittest.TestCase):
    """Test GICSSectorMapper"""

    def setUp(self):
        from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper
        self.mapper = GICSSectorMapper()

    def test_map_by_code_level1(self):
        """Test mapping by 2-digit GICS code (Level 1)"""
        result = self.mapper.map_to_gics(None, "45")

        self.assertEqual(result['sector'], 'Information Technology')
        self.assertEqual(result['sector_code'], '45')

    def test_map_by_code_level2(self):
        """Test mapping by 4-digit GICS code (Level 2)"""
        result = self.mapper.map_to_gics(None, "4510")

        self.assertEqual(result['sector'], 'Information Technology')
        self.assertEqual(result['sector_code'], '45')
        self.assertIsNotNone(result['industry'])

    def test_map_by_code_level3(self):
        """Test mapping by 6-digit GICS code (Level 3)"""
        result = self.mapper.map_to_gics(None, "451020")

        self.assertEqual(result['sector'], 'Information Technology')
        self.assertEqual(result['sector_code'], '45')

    def test_map_by_name_exact(self):
        """Test mapping by exact sector name"""
        result = self.mapper.map_to_gics("Information Technology", None)

        self.assertEqual(result['sector'], 'Information Technology')
        self.assertEqual(result['sector_code'], '45')

    def test_map_by_name_partial(self):
        """Test mapping by partial sector name"""
        result = self.mapper.map_to_gics("Technology", None)

        self.assertEqual(result['sector'], 'Information Technology')

    def test_map_invalid_code(self):
        """Test mapping with invalid code returns fallback"""
        result = self.mapper.map_to_gics(None, "99")

        self.assertEqual(result['sector'], 'Industrials')  # Fallback

    def test_map_no_input(self):
        """Test mapping with no input returns fallback"""
        result = self.mapper.map_to_gics(None, None)

        self.assertEqual(result['sector'], 'Industrials')  # Fallback

    def test_validate_gics_structure_level1(self):
        """Test GICS structure validation for Level 1"""
        result = self.mapper.validate_gics_structure("45")

        self.assertTrue(result['valid'])
        self.assertEqual(result['level'], 1)
        self.assertEqual(result['sector_code'], '45')

    def test_validate_gics_structure_level4(self):
        """Test GICS structure validation for Level 4"""
        result = self.mapper.validate_gics_structure("45102010")

        self.assertTrue(result['valid'])
        self.assertEqual(result['level'], 4)
        self.assertEqual(result['sector_code'], '45')
        self.assertEqual(result['sub_industry_code'], '45102010')

    def test_validate_gics_structure_invalid(self):
        """Test GICS structure validation for invalid code"""
        result = self.mapper.validate_gics_structure("abc")

        self.assertFalse(result['valid'])

    def test_validate_gics_structure_short_code(self):
        """Test GICS structure validation for too short code"""
        result = self.mapper.validate_gics_structure("1")

        self.assertFalse(result['valid'])


# ============================================================
# MarketCalendar Tests
# ============================================================

class TestMarketCalendarInit(unittest.TestCase):
    """Test MarketCalendar initialization"""

    def test_init_kr(self):
        """Test KR market calendar initialization"""
        from modules.market_adapters.calendars.market_calendar import MarketCalendar

        calendar = MarketCalendar("KR")

        self.assertEqual(calendar.region, "KR")
        self.assertEqual(calendar.config['timezone'], 'Asia/Seoul')

    def test_init_us(self):
        """Test US market calendar initialization"""
        from modules.market_adapters.calendars.market_calendar import MarketCalendar

        calendar = MarketCalendar("US")

        self.assertEqual(calendar.region, "US")
        self.assertEqual(calendar.config['timezone'], 'America/New_York')

    def test_init_invalid_region(self):
        """Test initialization with invalid region raises error"""
        from modules.market_adapters.calendars.market_calendar import MarketCalendar

        with self.assertRaises(ValueError):
            MarketCalendar("XX")


class TestMarketCalendarTradingDays(unittest.TestCase):
    """Test trading day calculations"""

    def setUp(self):
        from modules.market_adapters.calendars.market_calendar import MarketCalendar
        self.calendar = MarketCalendar("KR")

    def test_is_trading_day_weekday(self):
        """Test weekday is a trading day"""
        # Wednesday, December 11, 2024
        wednesday = datetime(2024, 12, 11, 10, 0)
        self.assertTrue(self.calendar.is_trading_day(wednesday))

    def test_is_trading_day_saturday(self):
        """Test Saturday is not a trading day"""
        # Saturday, December 14, 2024
        saturday = datetime(2024, 12, 14, 10, 0)
        self.assertFalse(self.calendar.is_trading_day(saturday))

    def test_is_trading_day_sunday(self):
        """Test Sunday is not a trading day"""
        # Sunday, December 15, 2024
        sunday = datetime(2024, 12, 15, 10, 0)
        self.assertFalse(self.calendar.is_trading_day(sunday))

    def test_is_trading_day_with_holiday(self):
        """Test holiday is not a trading day"""
        # Add a holiday
        self.calendar.holidays = ['2024-12-25']

        christmas = datetime(2024, 12, 25, 10, 0)
        self.assertFalse(self.calendar.is_trading_day(christmas))

    def test_get_next_trading_day_from_friday(self):
        """Test next trading day from Friday is Monday"""
        # Friday, December 13, 2024
        friday = datetime(2024, 12, 13, 10, 0)
        next_day = self.calendar.get_next_trading_day(friday)

        # Should be Monday, December 16, 2024
        self.assertEqual(next_day.weekday(), 0)  # Monday

    def test_get_previous_trading_day_from_monday(self):
        """Test previous trading day from Monday is Friday"""
        # Monday, December 16, 2024
        monday = datetime(2024, 12, 16, 10, 0)
        prev_day = self.calendar.get_previous_trading_day(monday)

        # Should be Friday, December 13, 2024
        self.assertEqual(prev_day.weekday(), 4)  # Friday

    def test_get_trading_days_between(self):
        """Test getting trading days between dates"""
        # Monday to Friday
        start = datetime(2024, 12, 9)
        end = datetime(2024, 12, 13)

        trading_days = self.calendar.get_trading_days_between(start, end)

        # Should be 5 trading days (Mon-Fri)
        self.assertEqual(len(trading_days), 5)


class TestMarketCalendarTradingHours(unittest.TestCase):
    """Test trading hours calculations"""

    def setUp(self):
        from modules.market_adapters.calendars.market_calendar import MarketCalendar
        self.kr_calendar = MarketCalendar("KR")
        self.cn_calendar = MarketCalendar("CN")  # Has lunch break

    def test_get_trading_hours_kr(self):
        """Test KR trading hours"""
        open_time, close_time = self.kr_calendar.get_trading_hours()

        self.assertEqual(open_time, time(9, 0))
        self.assertEqual(close_time, time(15, 30))

    def test_is_market_open_during_trading(self):
        """Test market is open during trading hours"""
        # Wednesday 10:00 AM (during trading)
        during_trading = datetime(2024, 12, 11, 10, 0)
        self.assertTrue(self.kr_calendar.is_market_open(during_trading))

    def test_is_market_open_before_open(self):
        """Test market is closed before open"""
        # Wednesday 8:00 AM (before open)
        before_open = datetime(2024, 12, 11, 8, 0)
        self.assertFalse(self.kr_calendar.is_market_open(before_open))

    def test_is_market_open_after_close(self):
        """Test market is closed after close"""
        # Wednesday 4:00 PM (after close)
        after_close = datetime(2024, 12, 11, 16, 0)
        self.assertFalse(self.kr_calendar.is_market_open(after_close))

    def test_is_market_open_during_lunch_break(self):
        """Test market is closed during lunch break (CN)"""
        # Wednesday 12:30 PM (during lunch break)
        during_lunch = datetime(2024, 12, 11, 12, 30)
        self.assertFalse(self.cn_calendar.is_market_open(during_lunch))

    def test_get_trading_sessions_no_break(self):
        """Test trading sessions for market without lunch break"""
        sessions = self.kr_calendar.get_trading_sessions()

        self.assertEqual(len(sessions), 1)  # Single session

    def test_get_trading_sessions_with_break(self):
        """Test trading sessions for market with lunch break"""
        sessions = self.cn_calendar.get_trading_sessions()

        self.assertEqual(len(sessions), 2)  # Morning + Afternoon


class TestMarketCalendarStatus(unittest.TestCase):
    """Test market status methods"""

    def setUp(self):
        from modules.market_adapters.calendars.market_calendar import MarketCalendar
        self.calendar = MarketCalendar("KR")

    def test_get_time_until_close_when_open(self):
        """Test time until close when market is open"""
        # Wednesday 10:00 AM (market open)
        during_trading = datetime(2024, 12, 11, 10, 0)
        time_until_close = self.calendar.get_time_until_close(during_trading)

        self.assertIsNotNone(time_until_close)
        self.assertEqual(time_until_close.seconds, 5.5 * 3600)  # 5.5 hours

    def test_get_time_until_close_when_closed(self):
        """Test time until close returns None when market is closed"""
        # Saturday (market closed)
        saturday = datetime(2024, 12, 14, 10, 0)
        time_until_close = self.calendar.get_time_until_close(saturday)

        self.assertIsNone(time_until_close)

    def test_get_time_until_open_when_closed(self):
        """Test time until open when market is closed"""
        # Wednesday 8:00 AM (before open)
        before_open = datetime(2024, 12, 11, 8, 0)
        time_until_open = self.calendar.get_time_until_open(before_open)

        self.assertIsNotNone(time_until_open)
        self.assertEqual(time_until_open.seconds, 1 * 3600)  # 1 hour

    def test_get_time_until_open_when_open(self):
        """Test time until open returns None when market is open"""
        during_trading = datetime(2024, 12, 11, 10, 0)
        time_until_open = self.calendar.get_time_until_open(during_trading)

        self.assertIsNone(time_until_open)

    def test_get_market_status_open(self):
        """Test market status when open"""
        during_trading = datetime(2024, 12, 11, 10, 0)
        status = self.calendar.get_market_status(during_trading)

        self.assertTrue(status['is_open'])
        self.assertTrue(status['is_trading_day'])
        self.assertIn('OPEN', status['status_message'])

    def test_get_market_status_closed_weekend(self):
        """Test market status on weekend"""
        saturday = datetime(2024, 12, 14, 10, 0)
        status = self.calendar.get_market_status(saturday)

        self.assertFalse(status['is_open'])
        self.assertFalse(status['is_trading_day'])
        self.assertIn('CLOSED', status['status_message'])

    def test_calendar_repr(self):
        """Test calendar string representation"""
        repr_str = repr(self.calendar)

        self.assertIn('KR', repr_str)
        self.assertIn('MarketCalendar', repr_str)


# ============================================================
# BaseMarketAdapter Tests (Lot Size Validation)
# ============================================================

class TestBaseMarketAdapterLotSize(unittest.TestCase):
    """Test BaseMarketAdapter lot size validation"""

    def setUp(self):
        """Create a concrete implementation for testing"""
        from modules.market_adapters.base_adapter import BaseMarketAdapter

        class TestAdapter(BaseMarketAdapter):
            def scan_stocks(self, force_refresh=False):
                return []
            def scan_etfs(self, force_refresh=False):
                return []
            def collect_stock_ohlcv(self, tickers=None, days=250):
                return 0
            def collect_etf_ohlcv(self, tickers=None, days=250):
                return 0

        mock_db = Mock()
        self.adapter = TestAdapter(mock_db, 'KR')

    def test_validate_lot_size_none(self):
        """Test None lot size is valid"""
        self.assertTrue(self.adapter._validate_lot_size(None, 'KR'))

    def test_validate_lot_size_zero(self):
        """Test zero lot size is invalid"""
        self.assertFalse(self.adapter._validate_lot_size(0, 'KR'))

    def test_validate_lot_size_negative(self):
        """Test negative lot size is invalid"""
        self.assertFalse(self.adapter._validate_lot_size(-1, 'KR'))

    def test_validate_lot_size_kr(self):
        """Test KR lot size (only 1 allowed)"""
        self.assertTrue(self.adapter._validate_lot_size(1, 'KR'))
        self.assertFalse(self.adapter._validate_lot_size(100, 'KR'))

    def test_validate_lot_size_us(self):
        """Test US lot size (only 1 allowed)"""
        self.assertTrue(self.adapter._validate_lot_size(1, 'US'))
        self.assertFalse(self.adapter._validate_lot_size(100, 'US'))

    def test_validate_lot_size_cn(self):
        """Test CN lot size (only 100 allowed)"""
        self.assertTrue(self.adapter._validate_lot_size(100, 'CN'))
        self.assertFalse(self.adapter._validate_lot_size(1, 'CN'))

    def test_validate_lot_size_hk(self):
        """Test HK lot size (100-2000 range)"""
        self.assertTrue(self.adapter._validate_lot_size(100, 'HK'))
        self.assertTrue(self.adapter._validate_lot_size(500, 'HK'))
        self.assertTrue(self.adapter._validate_lot_size(2000, 'HK'))
        self.assertFalse(self.adapter._validate_lot_size(50, 'HK'))
        self.assertFalse(self.adapter._validate_lot_size(3000, 'HK'))

    def test_validate_lot_size_jp(self):
        """Test JP lot size (1-10000 range)"""
        self.assertTrue(self.adapter._validate_lot_size(1, 'JP'))
        self.assertTrue(self.adapter._validate_lot_size(100, 'JP'))
        self.assertTrue(self.adapter._validate_lot_size(10000, 'JP'))
        self.assertFalse(self.adapter._validate_lot_size(20000, 'JP'))

    def test_validate_lot_size_vn(self):
        """Test VN lot size (only 100 allowed)"""
        self.assertTrue(self.adapter._validate_lot_size(100, 'VN'))
        self.assertFalse(self.adapter._validate_lot_size(1, 'VN'))

    def test_get_default_lot_size_kr(self):
        """Test default lot size for KR"""
        self.assertEqual(self.adapter._get_default_lot_size('KR'), 1)

    def test_get_default_lot_size_us(self):
        """Test default lot size for US"""
        self.assertEqual(self.adapter._get_default_lot_size('US'), 1)

    def test_get_default_lot_size_cn(self):
        """Test default lot size for CN"""
        self.assertEqual(self.adapter._get_default_lot_size('CN'), 100)

    def test_get_default_lot_size_hk(self):
        """Test default lot size for HK"""
        self.assertEqual(self.adapter._get_default_lot_size('HK'), 500)

    def test_get_default_lot_size_jp(self):
        """Test default lot size for JP"""
        self.assertEqual(self.adapter._get_default_lot_size('JP'), 100)

    def test_get_default_lot_size_vn(self):
        """Test default lot size for VN"""
        self.assertEqual(self.adapter._get_default_lot_size('VN'), 100)

    def test_get_default_lot_size_unknown(self):
        """Test default lot size for unknown region"""
        self.assertEqual(self.adapter._get_default_lot_size('XX'), 1)


# ============================================================
# Parametrized Tests
# ============================================================

@pytest.mark.parametrize("ticker,region,expected", [
    ("005930", "KR", True),
    ("AAPL", "US", True),
    ("600000.SS", "CN", True),
    ("0700.HK", "HK", True),
    ("7203", "JP", True),
    ("VNM", "VN", True),
    ("INVALID", "KR", False),
    ("005930", "US", False),
])
def test_ticker_validation_parametrized(ticker, region, expected):
    """Test ticker validation across regions"""
    from modules.market_adapters.validators.ticker_validator import TickerValidator

    result = TickerValidator.validate(ticker, region)
    assert result == expected


@pytest.mark.parametrize("code,sector_name", [
    ("10", "Energy"),
    ("15", "Materials"),
    ("20", "Industrials"),
    ("25", "Consumer Discretionary"),
    ("30", "Consumer Staples"),
    ("35", "Health Care"),
    ("40", "Financials"),
    ("45", "Information Technology"),
    ("50", "Communication Services"),
    ("55", "Utilities"),
    ("60", "Real Estate"),
])
def test_gics_sector_codes(code, sector_name):
    """Test all GICS sector codes"""
    from modules.market_adapters.sector_mappers.gics_mapper import GICSSectorMapper

    mapper = GICSSectorMapper()
    result = mapper.map_to_gics(None, code)

    assert result['sector'] == sector_name
    assert result['sector_code'] == code


@pytest.mark.parametrize("region,open_time,close_time", [
    ("KR", time(9, 0), time(15, 30)),
    ("US", time(9, 30), time(16, 0)),
    ("CN", time(9, 30), time(15, 0)),
    ("HK", time(9, 30), time(16, 0)),
    ("JP", time(9, 0), time(15, 0)),
    ("VN", time(9, 0), time(14, 45)),
])
def test_trading_hours_by_region(region, open_time, close_time):
    """Test trading hours for each region"""
    from modules.market_adapters.calendars.market_calendar import MarketCalendar

    calendar = MarketCalendar(region)
    actual_open, actual_close = calendar.get_trading_hours()

    assert actual_open == open_time
    assert actual_close == close_time


@pytest.mark.parametrize("region,lot_size,expected", [
    ("KR", 1, True),
    ("KR", 100, False),
    ("US", 1, True),
    ("CN", 100, True),
    ("CN", 1, False),
    ("HK", 500, True),
    ("HK", 99, False),
    ("JP", 100, True),
    ("VN", 100, True),
])
def test_lot_size_validation_parametrized(region, lot_size, expected):
    """Test lot size validation across regions"""
    from modules.market_adapters.base_adapter import BaseMarketAdapter

    class TestAdapter(BaseMarketAdapter):
        def scan_stocks(self, force_refresh=False): return []
        def scan_etfs(self, force_refresh=False): return []
        def collect_stock_ohlcv(self, tickers=None, days=250): return 0
        def collect_etf_ohlcv(self, tickers=None, days=250): return 0

    adapter = TestAdapter(Mock(), region)
    result = adapter._validate_lot_size(lot_size, region)

    assert result == expected


if __name__ == '__main__':
    unittest.main(verbosity=2)
