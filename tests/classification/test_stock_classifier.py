"""
Unit tests for StockClassifier

Tests:
- SPAC detection patterns (Korean, English)
- Preferred stock detection (KR, US)
- Sector classification (keyword-based)
- Database UPDATE strategy
- Batch processing and error handling

Author: Spock Quant Platform
Date: 2025-11-05
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from modules.classification.stock_classifier import StockClassifier


class TestStockClassifier(unittest.TestCase):
    """Test cases for StockClassifier"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.classifier = StockClassifier(db_manager=self.db_mock)

    def test_detect_spac_direct_mention(self):
        """Test SPAC detection with direct 'SPAC' mention"""
        name = "Tiger SPAC No.1"
        ticker = "SPAC01"

        result = self.classifier._detect_spac(name, ticker)

        self.assertTrue(result)

    def test_detect_spac_korean_term(self):
        """Test SPAC detection with Korean term"""
        name = "미래에셋특수목적인수1호"
        ticker = "325550"

        result = self.classifier._detect_spac(name, ticker)

        self.assertTrue(result)

    def test_detect_spac_numbering(self):
        """Test SPAC detection with Korean numbering pattern"""
        name = "한국투자밸류제1호"
        ticker = "325560"

        result = self.classifier._detect_spac(name, ticker)

        self.assertTrue(result)

    def test_detect_spac_english_phrase(self):
        """Test SPAC detection with English phrase"""
        name = "Korea Special Purpose Acquisition Corp"
        ticker = "KSAC"

        result = self.classifier._detect_spac(name, ticker)

        self.assertTrue(result)

    def test_detect_spac_negative(self):
        """Test SPAC detection returns False for normal stock"""
        name = "삼성전자"
        ticker = "005930"

        result = self.classifier._detect_spac(name, ticker)

        self.assertFalse(result)

    def test_detect_preferred_kr_ticker_suffix(self):
        """Test preferred stock detection (KR) - ticker suffix 2-9"""
        name = "삼성전자우"
        ticker = "005932"  # Suffix 2 indicates preferred

        result = self.classifier._detect_preferred(name, ticker, 'KR')

        self.assertTrue(result)

    def test_detect_preferred_kr_name_keyword(self):
        """Test preferred stock detection (KR) - name keyword"""
        name = "현대차2우B"
        ticker = "005387"

        result = self.classifier._detect_preferred(name, ticker, 'KR')

        self.assertTrue(result)

    def test_detect_preferred_us_series_format(self):
        """Test preferred stock detection (US) - .PR format"""
        name = "Bank of America Preferred Series L"
        ticker = "BAC.PRL"

        result = self.classifier._detect_preferred(name, ticker, 'US')

        self.assertTrue(result)

    def test_detect_preferred_us_hyphen_format(self):
        """Test preferred stock detection (US) - hyphen format"""
        name = "JPMorgan Preferred Series D"
        ticker = "JPM-PD"

        result = self.classifier._detect_preferred(name, ticker, 'US')

        self.assertTrue(result)

    def test_detect_preferred_negative(self):
        """Test preferred stock detection returns False for common stock"""
        name = "삼성전자"
        ticker = "005930"  # Suffix 0 is common stock

        result = self.classifier._detect_preferred(name, ticker, 'KR')

        self.assertFalse(result)

    def test_classify_sector_technology(self):
        """Test sector classification - Technology"""
        name = "삼성전자"

        result = self.classifier._classify_sector_by_keywords(name, 'KR')

        self.assertEqual(result, 'Technology')

    def test_classify_sector_finance(self):
        """Test sector classification - Finance"""
        name = "KB금융"

        result = self.classifier._classify_sector_by_keywords(name, 'KR')

        self.assertEqual(result, 'Finance')

    def test_classify_sector_healthcare(self):
        """Test sector classification - Healthcare"""
        name = "셀트리온제약"

        result = self.classifier._classify_sector_by_keywords(name, 'KR')

        self.assertEqual(result, 'Healthcare')

    def test_classify_sector_no_match(self):
        """Test sector classification returns None for no match"""
        name = "알파종목"

        result = self.classifier._classify_sector_by_keywords(name, 'KR')

        self.assertIsNone(result)

    def test_classify_ticker_full(self):
        """Test full ticker classification workflow"""
        ticker_data = {
            'ticker': '005930',
            'name': '삼성전자',
            'exchange': 'KRX',
            'asset_type': 'STOCK'
        }

        result = self.classifier._classify_ticker(ticker_data, 'KR')

        # Verify classification results
        self.assertFalse(result['is_spac'])
        self.assertFalse(result['is_preferred'])
        self.assertEqual(result['sector'], 'Technology')
        self.assertIsNone(result['industry'])

    def test_classify_ticker_preferred(self):
        """Test classification of preferred stock"""
        ticker_data = {
            'ticker': '005932',
            'name': '삼성전자우',
            'exchange': 'KRX',
            'asset_type': 'STOCK'
        }

        result = self.classifier._classify_ticker(ticker_data, 'KR')

        self.assertFalse(result['is_spac'])
        self.assertTrue(result['is_preferred'])
        self.assertEqual(result['sector'], 'Technology')

    def test_classify_ticker_spac(self):
        """Test classification of SPAC"""
        ticker_data = {
            'ticker': '325550',
            'name': '미래에셋특수목적인수1호',
            'exchange': 'KRX',
            'asset_type': 'STOCK'
        }

        result = self.classifier._classify_ticker(ticker_data, 'KR')

        self.assertTrue(result['is_spac'])
        self.assertFalse(result['is_preferred'])

    def test_get_active_tickers_query(self):
        """Test database query for active tickers"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result
        mock_cursor.fetchall.return_value = [
            ('005930', '삼성전자', 'KRX', 'STOCK'),
            ('005932', '삼성전자우', 'KRX', 'STOCK'),
        ]

        result = self.classifier._get_active_tickers('KR')

        # Verify query was called with correct parameters
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        self.assertIn('SELECT ticker, name, exchange, asset_type', query)
        self.assertIn('FROM tickers', query)
        self.assertIn('WHERE region = %s', query)
        self.assertIn('AND is_active = TRUE', query)
        self.assertIn('AND asset_type = \'STOCK\'', query)
        self.assertEqual(params, ('KR',))

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '005930')
        self.assertEqual(result[1]['ticker'], '005932')

    def test_update_ticker_classification(self):
        """Test UPDATE query for ticker classification"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        classification = {
            'is_spac': False,
            'is_preferred': True,
            'sector': 'Technology',
            'industry': None
        }

        self.classifier._update_ticker_classification(
            '005932',
            'KR',
            classification
        )

        # Verify UPDATE query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        self.assertIn('UPDATE tickers', query)
        self.assertIn('SET', query)
        self.assertIn('is_spac = %s', query)
        self.assertIn('is_preferred = %s', query)
        self.assertIn('sector = %s', query)
        self.assertIn('industry = %s', query)
        self.assertIn('WHERE ticker = %s AND region = %s', query)

        # Verify parameters
        self.assertEqual(params, (False, True, 'Technology', None, '005932', 'KR'))

        # Verify commit was called
        mock_conn.commit.assert_called_once()

    def test_classify_region_success(self):
        """Test successful region classification workflow"""
        # Mock get_active_tickers
        with patch.object(self.classifier, '_get_active_tickers') as mock_get:
            mock_get.return_value = [
                {
                    'ticker': '005930',
                    'name': '삼성전자',
                    'exchange': 'KRX',
                    'asset_type': 'STOCK'
                },
                {
                    'ticker': '005932',
                    'name': '삼성전자우',
                    'exchange': 'KRX',
                    'asset_type': 'STOCK'
                },
                {
                    'ticker': '325550',
                    'name': '미래에셋특수목적인수1호',
                    'exchange': 'KRX',
                    'asset_type': 'STOCK'
                }
            ]

            # Mock update_ticker_classification
            with patch.object(self.classifier, '_update_ticker_classification'):
                result = self.classifier.classify_region('KR')

                # Verify results
                self.assertTrue(result['success'])
                self.assertEqual(result['classified'], 3)
                self.assertEqual(result['spac_count'], 1)
                self.assertEqual(result['preferred_count'], 1)
                self.assertEqual(result['errors'], 0)

    def test_classify_region_no_tickers(self):
        """Test region classification with no tickers"""
        # Mock empty tickers
        with patch.object(self.classifier, '_get_active_tickers') as mock_get:
            mock_get.return_value = []

            result = self.classifier.classify_region('KR')

            self.assertFalse(result['success'])
            self.assertEqual(result['classified'], 0)
            self.assertEqual(result['spac_count'], 0)
            self.assertEqual(result['preferred_count'], 0)

    def test_classify_region_with_errors(self):
        """Test region classification with errors"""
        # Mock get_active_tickers
        with patch.object(self.classifier, '_get_active_tickers') as mock_get:
            mock_get.return_value = [
                {
                    'ticker': '005930',
                    'name': '삼성전자',
                    'exchange': 'KRX',
                    'asset_type': 'STOCK'
                }
            ]

            # Mock update to raise exception
            with patch.object(self.classifier, '_update_ticker_classification',
                            side_effect=Exception("Database error")):
                result = self.classifier.classify_region('KR')

                # Should handle error gracefully
                self.assertTrue(result['success'])  # Success despite error
                self.assertEqual(result['classified'], 0)  # But no tickers classified
                self.assertEqual(result['errors'], 1)

    def test_classifier_with_no_db(self):
        """Test classifier initialization without database"""
        classifier_no_db = StockClassifier(db_manager=None)

        # Should not fail
        tickers = classifier_no_db._get_active_tickers('KR')
        self.assertEqual(tickers, [])


class TestStockClassifierIntegration(unittest.TestCase):
    """Integration tests for StockClassifier (requires database)"""

    @unittest.skip("Requires live database connection")
    def test_full_classification_kr(self):
        """Test full classification workflow for KR region"""
        classifier = StockClassifier()

        result = classifier.classify_region('KR')

        # Verify result structure
        self.assertIn('classified', result)
        self.assertIn('spac_count', result)
        self.assertIn('preferred_count', result)
        self.assertIn('success', result)
        self.assertTrue(result['success'])


if __name__ == '__main__':
    unittest.main()
