"""
Unit tests for DatabaseUpdateOrchestrator (Phase 1 enhancements)

Tests:
- New step execution (ticker_refresh, fx_tracking, classification, etf_data)
- Retry logic with exponential backoff
- Rich UI integration
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
import time

from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator


class TestOrchestratorPhase1(unittest.TestCase):
    """Test cases for Phase 1 Orchestrator enhancements"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.orchestrator = DatabaseUpdateOrchestrator(self.db_mock, config={})

    def test_new_step_order(self):
        """Test that new steps are in correct order"""
        expected_steps = [
            'tickers',
            'ticker_refresh',
            'fx_tracking',
            'ohlcv',
            'fundamentals',
            'classification',
            'dividend',
            'etf_data',
            'quarterly'
        ]

        self.assertEqual(self.orchestrator.STEP_ORDER, expected_steps)

    def test_execute_with_retry_success_first_attempt(self):
        """Test retry logic succeeds on first attempt"""
        # Mock executor that succeeds immediately
        mock_executor = Mock(return_value={'success': True, 'data': 'test'})

        result = self.orchestrator._execute_with_retry(
            mock_executor,
            step='test_step',
            regions=['KR'],
            max_retries=3
        )

        # Should call executor only once
        mock_executor.assert_called_once_with(['KR'])

        # Should return success result
        self.assertEqual(result, {'success': True, 'data': 'test'})

    def test_execute_with_retry_success_second_attempt(self):
        """Test retry logic succeeds on second attempt"""
        # Mock executor that fails first time, succeeds second time
        mock_executor = Mock(side_effect=[
            Exception("First attempt failed"),
            {'success': True, 'data': 'test'}
        ])

        result = self.orchestrator._execute_with_retry(
            mock_executor,
            step='test_step',
            regions=['KR'],
            max_retries=3
        )

        # Should call executor twice
        self.assertEqual(mock_executor.call_count, 2)

        # Should return success result
        self.assertEqual(result, {'success': True, 'data': 'test'})

    def test_execute_with_retry_all_attempts_fail(self):
        """Test retry logic fails after max attempts"""
        # Mock executor that always fails
        mock_executor = Mock(side_effect=Exception("Always fails"))

        with self.assertRaises(Exception) as context:
            self.orchestrator._execute_with_retry(
                mock_executor,
                step='test_step',
                regions=['KR'],
                max_retries=3
            )

        # Should call executor 3 times
        self.assertEqual(mock_executor.call_count, 3)

        # Should raise the exception
        self.assertIn("Always fails", str(context.exception))

    @patch('time.sleep')  # Mock sleep to speed up test
    def test_execute_with_retry_exponential_backoff(self, mock_sleep):
        """Test retry logic uses exponential backoff"""
        # Mock executor that fails twice, succeeds third time
        mock_executor = Mock(side_effect=[
            Exception("First fail"),
            Exception("Second fail"),
            {'success': True}
        ])

        result = self.orchestrator._execute_with_retry(
            mock_executor,
            step='test_step',
            regions=['KR'],
            max_retries=3
        )

        # Verify exponential backoff delays: 5s, 10s
        expected_calls = [call(5), call(10)]
        mock_sleep.assert_has_calls(expected_calls)

        # Should succeed on third attempt
        self.assertEqual(result, {'success': True})

    def test_refresh_tickers_kr(self):
        """Test ticker refresh for KR region"""
        # Mock TickerRefresher (lazy import)
        with patch('modules.ticker_refresh.ticker_refresher.TickerRefresher') as mock_refresher_class:
            mock_refresher = Mock()
            mock_refresher.refresh_region.return_value = {
                'new': 5,
                'updated': 3,
                'delisted': 1,
                'errors': 0
            }
            mock_refresher_class.return_value = mock_refresher

            result = self.orchestrator._refresh_tickers(['KR'], incremental=True)

            # Verify TickerRefresher was called
            mock_refresher.refresh_region.assert_called_once_with('KR', incremental=True)

            # Verify result
            self.assertEqual(result['KR']['new'], 5)
            self.assertEqual(result['KR']['updated'], 3)
            self.assertEqual(result['KR']['delisted'], 1)

    def test_track_exchange_rates(self):
        """Test FX tracking"""
        # Mock FXTracker (lazy import)
        with patch('modules.fx_tracking.fx_tracker.FXTracker') as mock_tracker_class:
            mock_tracker = Mock()
            mock_tracker.update_exchange_rates.return_value = {
                'updated': 4,
                'signals': 2,
                'success': True
            }
            mock_tracker_class.return_value = mock_tracker

            result = self.orchestrator._track_exchange_rates(['KR'], dry_run=False)

            # Verify FXTracker was called
            mock_tracker.update_exchange_rates.assert_called_once()

            # Verify result
            self.assertEqual(result['updated'], 4)
            self.assertEqual(result['signals'], 2)
            self.assertTrue(result['success'])

    def test_get_currencies_for_regions_kr(self):
        """Test currency mapping for KR region"""
        currencies = self.orchestrator._get_currencies_for_regions(['KR'])

        # Should return KR-relevant currencies
        expected_currencies = {'USD', 'JPY', 'CNY', 'EUR'}
        self.assertEqual(set(currencies), expected_currencies)

    def test_get_currencies_for_regions_multiple(self):
        """Test currency mapping for multiple regions"""
        currencies = self.orchestrator._get_currencies_for_regions(['KR', 'US'])

        # Should return union of currencies
        expected_currencies = {'USD', 'JPY', 'CNY', 'EUR', 'KRW'}
        self.assertEqual(set(currencies), expected_currencies)

    def test_classify_stocks_kr(self):
        """Test stock classification for KR region"""
        # Mock StockClassifier (lazy import)
        with patch('modules.classification.stock_classifier.StockClassifier') as mock_classifier_class:
            mock_classifier = Mock()
            mock_classifier.classify_region.return_value = {
                'classified': 100,
                'spac_count': 5,
                'preferred_count': 10,
                'success': True
            }
            mock_classifier_class.return_value = mock_classifier

            result = self.orchestrator._classify_stocks(['KR'])

            # Verify StockClassifier was called
            mock_classifier.classify_region.assert_called_once()

            # Verify result
            self.assertEqual(result['KR']['classified'], 100)
            self.assertEqual(result['KR']['spac_count'], 5)
            self.assertEqual(result['KR']['preferred_count'], 10)

    def test_update_etf_data_kr(self):
        """Test ETF data update for KR region"""
        # Mock ETFUpdater (lazy import)
        with patch('modules.etf_update.etf_updater.ETFUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater.update_region.return_value = {
                'etf_count': 200,
                'holdings_updated': 180,
                'success': True
            }
            mock_updater_class.return_value = mock_updater

            result = self.orchestrator._update_etf_data(['KR'], incremental=True)

            # Verify ETFUpdater was called
            mock_updater.update_region.assert_called_once_with(
                'KR',
                incremental=True,
                update_holdings=True
            )

            # Verify result
            self.assertEqual(result['KR']['etf_count'], 200)
            self.assertEqual(result['KR']['holdings_updated'], 180)

    @patch('modules.orchestration.orchestrator.RICH_AVAILABLE', True)
    @patch('modules.orchestration.orchestrator.Console')
    @patch('modules.orchestration.orchestrator.Progress')
    def test_run_steps_with_rich_ui(self, mock_progress_class, mock_console_class):
        """Test pipeline execution with Rich UI"""
        # Initialize start_time to avoid TypeError in _print_rich_summary
        self.orchestrator.stats['start_time'] = datetime.now()

        # Mock Progress context manager
        mock_progress = MagicMock()
        mock_progress_class.return_value.__enter__.return_value = mock_progress
        mock_progress.add_task.return_value = 0

        # Mock Console
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        # Mock step executor
        with patch.object(self.orchestrator, '_execute_step', return_value={'success': True}):
            with patch.object(self.orchestrator, 'checkpoint_manager'):
                self.orchestrator._run_steps_with_rich_ui(
                    steps=['ticker_refresh'],
                    regions=['KR'],
                    dry_run=False,
                    incremental=True
                )

        # Verify Progress was used
        mock_progress.add_task.assert_called_once()
        self.assertGreater(mock_progress.update.call_count, 0)

        # Verify completion message
        self.assertGreater(mock_console.print.call_count, 0)

    def test_run_steps_basic(self):
        """Test pipeline execution without Rich UI"""
        # Mock step executor
        with patch.object(self.orchestrator, '_execute_step', return_value={'success': True}):
            with patch.object(self.orchestrator, 'checkpoint_manager'):
                self.orchestrator._run_steps_basic(
                    steps=['ticker_refresh'],
                    regions=['KR'],
                    dry_run=False,
                    incremental=True
                )

        # Verify step was added to stats
        self.assertEqual(len(self.orchestrator.stats['steps_completed']), 1)
        self.assertEqual(self.orchestrator.stats['steps_completed'][0], 'ticker_refresh')


class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests for Orchestrator (requires mocked dependencies)"""

    @unittest.skip("Integration test - requires full dependency mocking")
    def test_full_pipeline_with_new_steps(self):
        """Test full pipeline execution with new steps"""
        # This would require mocking all dependencies
        pass


if __name__ == '__main__':
    unittest.main()
