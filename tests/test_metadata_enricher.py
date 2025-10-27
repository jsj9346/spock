"""
Unit Tests for Stock Metadata Enricher

Tests the hybrid KIS + yfinance metadata enrichment system.

Test Coverage:
    - KIS sector code mapping (instant classification)
    - yfinance API fallback (rate limiting, retry logic)
    - Cache management (24-hour TTL, LRU eviction)
    - Rate limiting (1 req/sec token bucket)
    - Circuit breaker (5 consecutive failures)
    - Ticker normalization (US, HK, CN, JP, VN)
    - Batch processing (100 stocks/batch)
    - Database bulk updates
    - SPAC detection
    - Preferred stock detection

Author: Spock Testing Team
Created: 2025-10-17
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
import time
import json
from pathlib import Path

# Import module under test
from modules.stock_metadata_enricher import (
    StockMetadataEnricher,
    EnrichmentCache,
    RateLimiter,
    RetryHandler,
    EnrichmentResult,
    BatchEnrichmentResult,
    MappingNotFoundError,
    YFinanceError,
    RateLimitError,
    TickerNotFoundError
)


class TestEnrichmentCache(unittest.TestCase):
    """Test EnrichmentCache 24-hour TTL cache."""

    def setUp(self):
        """Set up test cache."""
        self.cache = EnrichmentCache(ttl_hours=24, max_entries=100)

    def test_cache_set_and_get(self):
        """Test basic cache set and get."""
        result = EnrichmentResult(
            ticker='AAPL',
            region='US',
            sector='Information Technology',
            success=True
        )

        key = 'US:AAPL:730'
        self.cache.set(key, result)

        cached = self.cache.get(key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.ticker, 'AAPL')
        self.assertEqual(cached.sector, 'Information Technology')

    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get('nonexistent:key')
        self.assertIsNone(result)

    def test_cache_expiration(self):
        """Test cache entries expire after TTL."""
        cache = EnrichmentCache(ttl_hours=0.0001)  # ~0.36 seconds

        result = EnrichmentResult(
            ticker='AAPL',
            region='US',
            sector='Information Technology',
            success=True
        )

        key = 'US:AAPL:730'
        cache.set(key, result)

        # Should be cached immediately
        cached = cache.get(key)
        self.assertIsNotNone(cached)

        # Wait for expiration
        time.sleep(0.5)

        # Should be expired
        cached = cache.get(key)
        self.assertIsNone(cached)

    def test_cache_lru_eviction(self):
        """Test LRU eviction when max_entries reached."""
        cache = EnrichmentCache(ttl_hours=24, max_entries=3)

        # Add 3 entries
        for i in range(3):
            result = EnrichmentResult(
                ticker=f'TICK{i}',
                region='US',
                success=True
            )
            cache.set(f'US:TICK{i}:0', result)

        # All 3 should be cached
        self.assertIsNotNone(cache.get('US:TICK0:0'))
        self.assertIsNotNone(cache.get('US:TICK1:0'))
        self.assertIsNotNone(cache.get('US:TICK2:0'))

        # Add 4th entry (should evict oldest)
        result = EnrichmentResult(ticker='TICK3', region='US', success=True)
        cache.set('US:TICK3:0', result)

        # TICK0 should be evicted
        self.assertIsNone(cache.get('US:TICK0:0'))
        self.assertIsNotNone(cache.get('US:TICK1:0'))
        self.assertIsNotNone(cache.get('US:TICK2:0'))
        self.assertIsNotNone(cache.get('US:TICK3:0'))

    def test_cache_clear(self):
        """Test cache clear removes all entries."""
        result = EnrichmentResult(ticker='AAPL', region='US', success=True)
        self.cache.set('US:AAPL:730', result)

        self.assertIsNotNone(self.cache.get('US:AAPL:730'))

        self.cache.clear()

        self.assertIsNone(self.cache.get('US:AAPL:730'))


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter token bucket implementation."""

    def test_rate_limiter_basic(self):
        """Test basic rate limiting (1 req/sec)."""
        limiter = RateLimiter(rate=2.0, burst=2)  # 2 req/sec for faster test

        start = time.time()

        # First 2 requests should be immediate (burst)
        limiter.acquire()
        limiter.acquire()

        # 3rd request should wait ~0.5 seconds
        limiter.acquire()

        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.4)  # Allow some tolerance

    def test_rate_limiter_burst_capacity(self):
        """Test burst capacity allows immediate requests."""
        limiter = RateLimiter(rate=1.0, burst=5)

        start = time.time()

        # All 5 burst requests should be immediate
        for _ in range(5):
            limiter.acquire()

        elapsed = time.time() - start
        self.assertLess(elapsed, 0.5)  # Should be nearly instant


class TestRetryHandler(unittest.TestCase):
    """Test RetryHandler exponential backoff and circuit breaker."""

    def setUp(self):
        """Set up test retry handler."""
        self.handler = RetryHandler(
            max_attempts=3,
            initial_delay=0.1,
            backoff_multiplier=2.0,
            max_delay=1.0,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=2
        )

    def test_retry_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        # Attempt 0: 0.1s
        delay0 = self.handler.get_delay(0)
        self.assertEqual(delay0, 0.1)

        # Attempt 1: 0.2s
        delay1 = self.handler.get_delay(1)
        self.assertEqual(delay1, 0.2)

        # Attempt 2: 0.4s
        delay2 = self.handler.get_delay(2)
        self.assertEqual(delay2, 0.4)

    def test_retry_max_delay(self):
        """Test max delay cap."""
        # Attempt 10 should be capped at max_delay (1.0s)
        delay = self.handler.get_delay(10)
        self.assertEqual(delay, 1.0)

    def test_circuit_breaker_opens(self):
        """Test circuit breaker opens after threshold failures."""
        # Record 5 consecutive failures
        for _ in range(5):
            self.handler.record_failure()

        # Circuit should be open
        self.assertTrue(self.handler.is_circuit_open())

    def test_circuit_breaker_closes_on_success(self):
        """Test circuit breaker closes on success."""
        # Record 3 failures
        for _ in range(3):
            self.handler.record_failure()

        # Record success
        self.handler.record_success()

        # Circuit should remain closed
        self.assertFalse(self.handler.is_circuit_open())
        self.assertEqual(self.handler.consecutive_failures, 0)

    def test_circuit_breaker_timeout(self):
        """Test circuit breaker resets after timeout."""
        handler = RetryHandler(
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=1  # 1 second timeout
        )

        # Trip circuit breaker
        for _ in range(5):
            handler.record_failure()

        self.assertTrue(handler.is_circuit_open())

        # Wait for timeout
        time.sleep(1.5)

        # Should transition to half-open
        self.assertFalse(handler.is_circuit_open())


class TestStockMetadataEnricher(unittest.TestCase):
    """Test StockMetadataEnricher main functionality."""

    def setUp(self):
        """Set up test enricher with mocked dependencies."""
        self.mock_db = Mock()
        self.mock_kis_api = Mock()

        # Create test mapping file
        self.test_mapping = {
            'metadata': {'version': '1.0'},
            'mapping': {
                '0': {
                    'gics_sector': None,
                    'fallback_required': True
                },
                '730': {
                    'gics_sector': 'Information Technology',
                    'description': 'Technology Hardware'
                },
                '610': {
                    'gics_sector': 'Financials',
                    'description': 'Banks'
                }
            }
        }

        # Mock mapping file loading
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data=json.dumps(self.test_mapping))):
                self.enricher = StockMetadataEnricher(
                    db_manager=self.mock_db,
                    kis_api_client=self.mock_kis_api,
                    rate_limit=10.0,  # Faster for testing
                    batch_size=10
                )

    def test_load_sector_mapping(self):
        """Test KIS sector mapping file loading."""
        mapping = self.enricher.sector_mapping

        self.assertIn('730', mapping)
        self.assertEqual(mapping['730']['gics_sector'], 'Information Technology')

        self.assertIn('610', mapping)
        self.assertEqual(mapping['610']['gics_sector'], 'Financials')

    def test_normalize_ticker_us(self):
        """Test US ticker normalization (no change)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('AAPL', 'US')
        self.assertEqual(ticker, 'AAPL')

    def test_normalize_ticker_hk(self):
        """Test Hong Kong ticker normalization (add .HK)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('0700', 'HK')
        self.assertEqual(ticker, '0700.HK')

    def test_normalize_ticker_cn_shanghai(self):
        """Test China Shanghai ticker normalization (add .SS)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('600519', 'CN')
        self.assertEqual(ticker, '600519.SS')

    def test_normalize_ticker_cn_shenzhen(self):
        """Test China Shenzhen ticker normalization (add .SZ)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('000858', 'CN')
        self.assertEqual(ticker, '000858.SZ')

    def test_normalize_ticker_jp(self):
        """Test Japan ticker normalization (add .T)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('7203', 'JP')
        self.assertEqual(ticker, '7203.T')

    def test_normalize_ticker_vn(self):
        """Test Vietnam ticker normalization (no change)."""
        ticker = self.enricher._normalize_ticker_for_yfinance('VCB', 'VN')
        self.assertEqual(ticker, 'VCB')

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_fetch_yfinance_data_success(self, mock_yf_ticker):
        """Test successful yfinance data fetch."""
        # Mock yfinance response
        mock_info = {
            'symbol': 'AAPL',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
            'industryKey': 'consumer-electronics',
            'quoteType': 'EQUITY',
            'longBusinessSummary': 'Apple Inc. designs and manufactures consumer electronics.'
        }

        mock_ticker_instance = Mock()
        mock_ticker_instance.info = mock_info
        mock_yf_ticker.return_value = mock_ticker_instance

        # Fetch data
        data = self.enricher._fetch_yfinance_data('AAPL', 'US')

        self.assertIsNotNone(data)
        self.assertEqual(data['sector'], 'Technology')
        self.assertEqual(data['industry'], 'Consumer Electronics')
        self.assertFalse(data['is_spac'])
        self.assertFalse(data['is_preferred'])

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_fetch_yfinance_spac_detection(self, mock_yf_ticker):
        """Test SPAC detection from business summary."""
        mock_info = {
            'symbol': 'SPAC',
            'sector': 'Financials',
            'industry': 'Shell Companies',
            'quoteType': 'EQUITY',
            'longBusinessSummary': 'This is a Special Purpose Acquisition Company (SPAC) formed to acquire businesses.'
        }

        mock_ticker_instance = Mock()
        mock_ticker_instance.info = mock_info
        mock_yf_ticker.return_value = mock_ticker_instance

        data = self.enricher._fetch_yfinance_data('SPAC', 'US')

        self.assertTrue(data['is_spac'])

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_fetch_yfinance_preferred_detection(self, mock_yf_ticker):
        """Test preferred stock detection."""
        mock_info = {
            'symbol': 'BAC-PL',
            'sector': 'Financials',
            'industry': 'Banks',
            'quoteType': 'Preferred Stock',
            'longBusinessSummary': 'Bank of America preferred stock.'
        }

        mock_ticker_instance = Mock()
        mock_ticker_instance.info = mock_info
        mock_yf_ticker.return_value = mock_ticker_instance

        data = self.enricher._fetch_yfinance_data('BAC-PL', 'US')

        self.assertTrue(data['is_preferred'])

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_fetch_yfinance_ticker_not_found(self, mock_yf_ticker):
        """Test yfinance ticker not found (404)."""
        mock_ticker_instance = Mock()
        mock_ticker_instance.info = {}  # Empty info indicates not found
        mock_yf_ticker.return_value = mock_ticker_instance

        with self.assertRaises(TickerNotFoundError):
            self.enricher._fetch_yfinance_data('INVALID', 'US')

    def test_enrich_single_stock_kis_mapping_success(self):
        """Test enrichment using KIS sector code mapping (instant)."""
        # Enrich with KIS mappable sector code
        result = self.enricher.enrich_single_stock(
            ticker='AAPL',
            region='US',
            sector_code='730'  # IT sector
        )

        # Should use KIS mapping (no yfinance call)
        self.assertTrue(result.success)
        self.assertEqual(result.sector, 'Information Technology')
        self.assertEqual(result.data_source, 'kis_mapping')
        self.assertEqual(self.enricher.metrics['kis_mapping_hits'], 1)

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_enrich_single_stock_yfinance_fallback(self, mock_yf_ticker):
        """Test enrichment fallback to yfinance for sector_code=0."""
        # Mock yfinance response
        mock_info = {
            'symbol': 'SPAC',
            'sector': 'Financials',
            'industry': 'Shell Companies',
            'quoteType': 'EQUITY',
            'longBusinessSummary': 'A SPAC company.'
        }

        mock_ticker_instance = Mock()
        mock_ticker_instance.info = mock_info
        mock_yf_ticker.return_value = mock_ticker_instance

        # Enrich with sector_code=0 (fallback to yfinance)
        result = self.enricher.enrich_single_stock(
            ticker='SPAC',
            region='US',
            sector_code='0'
        )

        self.assertTrue(result.success)
        self.assertEqual(result.sector, 'Financials')
        self.assertEqual(result.industry, 'Shell Companies')
        self.assertEqual(result.data_source, 'yfinance')
        self.assertEqual(self.enricher.metrics['yfinance_api_calls'], 1)

    def test_enrich_single_stock_cache_hit(self):
        """Test cache hit skips enrichment."""
        # Pre-populate cache
        cached_result = EnrichmentResult(
            ticker='AAPL',
            region='US',
            sector='Information Technology',
            sector_code='730',
            data_source='kis_mapping',
            success=True
        )

        cache_key = 'US:AAPL:730'
        self.enricher.cache.set(cache_key, cached_result)

        # Enrich (should hit cache)
        result = self.enricher.enrich_single_stock(
            ticker='AAPL',
            region='US',
            sector_code='730'
        )

        self.assertTrue(result.success)
        self.assertEqual(result.sector, 'Information Technology')
        self.assertEqual(self.enricher.metrics['cache_hits'], 1)

    def test_enrich_single_stock_force_refresh(self):
        """Test force_refresh bypasses cache."""
        # Pre-populate cache
        cached_result = EnrichmentResult(
            ticker='AAPL',
            region='US',
            sector='OLD',
            success=True
        )

        self.enricher.cache.set('US:AAPL:730', cached_result)

        # Enrich with force_refresh (should bypass cache)
        result = self.enricher.enrich_single_stock(
            ticker='AAPL',
            region='US',
            sector_code='730',
            force_refresh=True
        )

        # Should use KIS mapping, not cached value
        self.assertEqual(result.sector, 'Information Technology')
        self.assertEqual(self.enricher.metrics['cache_misses'], 1)

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    def test_enrich_batch(self, mock_yf_ticker):
        """Test batch enrichment processing."""
        # Mock yfinance responses
        mock_infos = {
            'AAPL': {'symbol': 'AAPL', 'sector': 'Technology', 'industry': 'Consumer Electronics', 'quoteType': 'EQUITY', 'longBusinessSummary': ''},
            'MSFT': {'symbol': 'MSFT', 'sector': 'Technology', 'industry': 'Software', 'quoteType': 'EQUITY', 'longBusinessSummary': ''},
            'JPM': {'symbol': 'JPM', 'sector': 'Financials', 'industry': 'Banks', 'quoteType': 'EQUITY', 'longBusinessSummary': ''}
        }

        def mock_ticker_factory(ticker):
            mock_ticker_instance = Mock()
            mock_ticker_instance.info = mock_infos.get(ticker, {})
            return mock_ticker_instance

        mock_yf_ticker.side_effect = mock_ticker_factory

        # Batch enrich
        tickers = ['AAPL', 'MSFT', 'JPM']
        sector_codes = {'AAPL': '730', 'MSFT': '730', 'JPM': '610'}

        result = self.enricher.enrich_batch(
            tickers=tickers,
            region='US',
            sector_codes=sector_codes
        )

        self.assertEqual(result.total, 3)
        self.assertEqual(result.successful, 3)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(result.results), 3)

    def test_update_database_batch(self):
        """Test database bulk update."""
        # Mock bulk_update_stock_details
        self.mock_db.bulk_update_stock_details = Mock(return_value=3)

        # Prepare enrichment results
        updates = [
            {
                'ticker': 'AAPL',
                'region': 'US',
                'sector': 'Information Technology',
                'industry': 'Consumer Electronics',
                'industry_code': 'GICS45203010',
                'is_spac': False,
                'is_preferred': False,
                'enriched_at': datetime.now()
            },
            {
                'ticker': 'MSFT',
                'region': 'US',
                'sector': 'Information Technology',
                'industry': 'Software',
                'is_spac': False,
                'is_preferred': False,
                'enriched_at': datetime.now()
            },
            {
                'ticker': 'JPM',
                'region': 'US',
                'sector': 'Financials',
                'industry': 'Banks',
                'is_spac': False,
                'is_preferred': False,
                'enriched_at': datetime.now()
            }
        ]

        # Call _update_database_batch
        updated_count = self.enricher._update_database_batch(updates)

        # Verify
        self.assertEqual(updated_count, 3)
        self.mock_db.bulk_update_stock_details.assert_called_once_with(updates)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios."""

    @patch('modules.stock_metadata_enricher.yf.Ticker')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('builtins.open')
    def test_hybrid_enrichment_workflow(self, mock_open, mock_path, mock_yf_ticker):
        """Test complete hybrid enrichment workflow."""
        # Mock mapping file
        test_mapping = {
            'metadata': {'version': '1.0'},
            'mapping': {
                '0': {'gics_sector': None, 'fallback_required': True},
                '730': {'gics_sector': 'Information Technology'}
            }
        }

        mock_open.return_value = unittest.mock.mock_open(read_data=json.dumps(test_mapping))()

        # Mock database
        mock_db = Mock()
        mock_db.bulk_update_stock_details = Mock(return_value=2)

        # Mock yfinance (for sector_code=0 fallback)
        mock_info = {
            'symbol': 'SPAC',
            'sector': 'Financials',
            'industry': 'Shell Companies',
            'quoteType': 'EQUITY',
            'longBusinessSummary': ''
        }

        mock_ticker_instance = Mock()
        mock_ticker_instance.info = mock_info
        mock_yf_ticker.return_value = mock_ticker_instance

        # Create enricher
        enricher = StockMetadataEnricher(
            db_manager=mock_db,
            rate_limit=10.0,
            batch_size=10
        )

        # Enrich 2 stocks: 1 with KIS mapping, 1 with yfinance fallback
        tickers = ['AAPL', 'SPAC']
        sector_codes = {'AAPL': '730', 'SPAC': '0'}

        result = enricher.enrich_batch(
            tickers=tickers,
            region='US',
            sector_codes=sector_codes
        )

        # Verify
        self.assertEqual(result.total, 2)
        self.assertEqual(result.successful, 2)

        # AAPL should use KIS mapping
        aapl_result = next(r for r in result.results if r.ticker == 'AAPL')
        self.assertEqual(aapl_result.sector, 'Information Technology')
        self.assertEqual(aapl_result.data_source, 'kis_mapping')

        # SPAC should use yfinance
        spac_result = next(r for r in result.results if r.ticker == 'SPAC')
        self.assertEqual(spac_result.sector, 'Financials')
        self.assertEqual(spac_result.data_source, 'yfinance')


# ============================================================================
# Test Runner
# ============================================================================

def run_tests():
    """Run all tests and generate report."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEnrichmentCache))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestStockMetadataEnricher))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Generate summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("="*70)

    return result


if __name__ == '__main__':
    run_tests()
