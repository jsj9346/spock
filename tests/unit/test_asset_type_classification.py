"""
Unit Tests for Asset Type Classification

Tests the classify_asset_type() method in CN and HK stock parsers.
Ensures correct classification of STOCK, ETF, MUTUALFUND, and INDEX types.

Test Coverage:
- CN ETF detection (ticker patterns: 51xxxx, 52xxxx, 15xxxx)
- CN Stock detection (normal stocks)
- CN Fund detection (keywords: 基金, FUND)
- HK ETF detection (keywords: ETF, TRACKER, ISHARES, SPDR)
- HK Stock detection (normal stocks)
- HK Fund detection (keywords: FUND, INVESTMENT FUND)
- Edge cases (NULL/missing fields)
- quoteType override (EQUITY, ETF, MUTUALFUND)
"""

import pytest
from modules.parsers.cn_stock_parser import CNStockParser
from modules.parsers.hk_stock_parser import HKStockParser


class TestCNAssetTypeClassification:
    """Test CN asset type classification logic"""

    @pytest.fixture
    def parser(self):
        """Create CN parser instance"""
        return CNStockParser()

    def test_cn_etf_by_ticker_pattern_51xxxx(self, parser):
        """Test CN ETF detection via 51xxxx ticker pattern (Shanghai ETF)"""
        ticker_info = {'ticker': '510050', 'name': 'China 50 ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "510050 should be classified as ETF (51xxxx pattern)"

    def test_cn_etf_by_ticker_pattern_52xxxx(self, parser):
        """Test CN ETF detection via 52xxxx ticker pattern (Innovation ETF)"""
        ticker_info = {'ticker': '520001', 'name': 'Innovation ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "520001 should be classified as ETF (52xxxx pattern)"

    def test_cn_etf_by_ticker_pattern_15xxxx(self, parser):
        """Test CN ETF detection via 15xxxx ticker pattern (Shenzhen ETF)"""
        ticker_info = {'ticker': '159901', 'name': 'Shenzhen 100 ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "159901 should be classified as ETF (15xxxx pattern)"

    def test_cn_etf_by_name_keyword(self, parser):
        """Test CN ETF detection via name keyword"""
        ticker_info = {'ticker': '600000', 'name': 'China ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains 'ETF')"

    def test_cn_etf_by_name_chinese_keyword(self, parser):
        """Test CN ETF detection via Chinese keyword '指数'"""
        ticker_info = {'ticker': '600000', 'name': '中国指数基金'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains '指数')"

    def test_cn_stock_normal(self, parser):
        """Test CN stock detection (normal stock)"""
        ticker_info = {'ticker': '600519', 'name': '贵州茅台'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "600519 should be classified as STOCK (normal stock)"

    def test_cn_stock_by_quote_type(self, parser):
        """Test CN stock detection via quoteType=EQUITY"""
        ticker_info = {'ticker': '000001', 'name': 'Ping An Bank', 'quoteType': 'EQUITY'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Should be classified as STOCK (quoteType=EQUITY)"

    def test_cn_fund_by_name_keyword(self, parser):
        """Test CN mutual fund detection via keyword '基金'"""
        ticker_info = {'ticker': '600000', 'name': 'China 基金'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'MUTUALFUND', "Should be classified as MUTUALFUND (name contains '基金')"

    def test_cn_quote_type_override(self, parser):
        """Test quoteType override (takes precedence over name)"""
        ticker_info = {'ticker': '600000', 'name': 'Some Name', 'quoteType': 'ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "quoteType should override name-based classification"

    def test_cn_edge_case_empty_name(self, parser):
        """Test edge case: empty name (should default to STOCK)"""
        ticker_info = {'ticker': '600000', 'name': ''}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Empty name should default to STOCK"

    def test_cn_edge_case_missing_fields(self, parser):
        """Test edge case: missing name and quoteType"""
        ticker_info = {'ticker': '600000'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Missing fields should default to STOCK"


class TestHKAssetTypeClassification:
    """Test HK asset type classification logic"""

    @pytest.fixture
    def parser(self):
        """Create HK parser instance"""
        return HKStockParser()

    def test_hk_etf_by_quote_type(self, parser):
        """Test HK ETF detection via quoteType"""
        ticker_info = {'ticker': '02800', 'name': 'Tracker Fund', 'quoteType': 'ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (quoteType=ETF)"

    def test_hk_etf_by_name_tracker(self, parser):
        """Test HK ETF detection via 'TRACKER' keyword"""
        ticker_info = {'ticker': '02800', 'name': 'Tracker Fund of Hong Kong'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains 'TRACKER')"

    def test_hk_etf_by_name_ishares(self, parser):
        """Test HK ETF detection via 'ISHARES' keyword"""
        ticker_info = {'ticker': '03008', 'name': 'iShares Core CSI 300'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains 'ISHARES')"

    def test_hk_etf_by_name_spdr(self, parser):
        """Test HK ETF detection via 'SPDR' keyword"""
        ticker_info = {'ticker': '02828', 'name': 'SPDR S&P 500 ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains 'SPDR')"

    def test_hk_etf_by_name_vanguard(self, parser):
        """Test HK ETF detection via 'VANGUARD' keyword"""
        ticker_info = {'ticker': '03140', 'name': 'Vanguard FTSE ETF'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "Should be classified as ETF (name contains 'VANGUARD')"

    def test_hk_stock_normal(self, parser):
        """Test HK stock detection (normal stock)"""
        ticker_info = {'ticker': '00700', 'name': 'Tencent Holdings'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "00700 should be classified as STOCK (normal stock)"

    def test_hk_stock_by_quote_type(self, parser):
        """Test HK stock detection via quoteType=EQUITY"""
        ticker_info = {'ticker': '09988', 'name': 'Alibaba Group', 'quoteType': 'EQUITY'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Should be classified as STOCK (quoteType=EQUITY)"

    def test_hk_fund_by_quote_type(self, parser):
        """Test HK mutual fund detection via quoteType"""
        ticker_info = {'ticker': '00091', 'name': 'HK Equity Fund', 'quoteType': 'MUTUALFUND'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'MUTUALFUND', "Should be classified as MUTUALFUND (quoteType)"

    def test_hk_fund_by_name_keyword(self, parser):
        """Test HK mutual fund detection via 'FUND' keyword (excluding TRACKER FUND)"""
        ticker_info = {'ticker': '00091', 'name': 'Investment Fund'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'MUTUALFUND', "Should be classified as MUTUALFUND (name contains 'FUND')"

    def test_hk_fund_tracker_fund_exception(self, parser):
        """Test that 'TRACKER FUND' is classified as ETF, not MUTUALFUND"""
        ticker_info = {'ticker': '02800', 'name': 'Tracker Fund'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'ETF', "'TRACKER FUND' should be ETF, not MUTUALFUND"

    def test_hk_quote_type_override(self, parser):
        """Test quoteType override (takes precedence over name)"""
        ticker_info = {'ticker': '00001', 'name': 'Some Fund Name', 'quoteType': 'EQUITY'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "quoteType=EQUITY should override fund keyword in name"

    def test_hk_edge_case_empty_name(self, parser):
        """Test edge case: empty name (should default to STOCK)"""
        ticker_info = {'ticker': '00700', 'name': ''}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Empty name should default to STOCK"

    def test_hk_edge_case_missing_fields(self, parser):
        """Test edge case: missing name and quoteType"""
        ticker_info = {'ticker': '00700'}
        result = parser.classify_asset_type(ticker_info)
        assert result == 'STOCK', "Missing fields should default to STOCK"


class TestClassificationRobustness:
    """Test robustness and edge cases across both parsers"""

    @pytest.fixture
    def cn_parser(self):
        return CNStockParser()

    @pytest.fixture
    def hk_parser(self):
        return HKStockParser()

    def test_case_insensitive_classification(self, cn_parser, hk_parser):
        """Test that classification is case-insensitive"""
        # CN test
        cn_info = {'ticker': '600000', 'name': 'china etf'}  # lowercase
        assert cn_parser.classify_asset_type(cn_info) == 'ETF'

        # HK test
        hk_info = {'ticker': '00001', 'name': 'tracker fund'}  # lowercase
        assert hk_parser.classify_asset_type(hk_info) == 'ETF'

    def test_partial_keyword_match(self, cn_parser, hk_parser):
        """Test that keywords are matched within longer strings"""
        # CN test
        cn_info = {'ticker': '600000', 'name': 'Some ETF Name'}
        assert cn_parser.classify_asset_type(cn_info) == 'ETF'

        # HK test
        hk_info = {'ticker': '00001', 'name': 'Some ISHARES ETF'}
        assert hk_parser.classify_asset_type(hk_info) == 'ETF'

    def test_index_classification(self, cn_parser, hk_parser):
        """Test INDEX classification via quoteType"""
        # CN test
        cn_info = {'ticker': '000300', 'name': 'CSI 300', 'quoteType': 'INDEX'}
        assert cn_parser.classify_asset_type(cn_info) == 'INDEX'

        # HK test
        hk_info = {'ticker': '02828', 'name': 'Hang Seng Index', 'quoteType': 'INDEX'}
        assert hk_parser.classify_asset_type(hk_info) == 'INDEX'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
