"""
spock_refresh.py Equity Backfill Gap Analysis 통합 테스트

spock_refresh.py의 run_equity_backfill() 함수에 통합된 gap analysis 기능을
검증합니다. 주요 검증 항목:
- Gap analysis pre-scan 실행
- Gap-aware command building
- Graceful fallback (gap analysis 실패 시)
- Legacy mode 지원

작성자: Quant Platform Development Team
날짜: 2025-11-11
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import date

# Project root 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.backfill.data_structures import GapAnalysisResult, BackfillStats
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.db_manager_postgres import PostgresDatabaseManager


class TestSpockRefreshEquityBackfill:
    """spock_refresh.py equity backfill gap analysis 통합 테스트"""

    # ========================================================================
    # Fixture Setup
    # ========================================================================

    @pytest.fixture
    def mock_db(self):
        """Mock PostgresDatabaseManager"""
        db = Mock(spec=PostgresDatabaseManager)
        return db

    @pytest.fixture
    def mock_gap_analyzer(self):
        """Mock GapAnalyzer with realistic results"""
        analyzer = Mock(spec=GapAnalyzer)

        # Mock gap analysis result (typical scenario)
        gap_result = Mock(spec=GapAnalysisResult)
        gap_result.get_summary.return_value = {
            'total_analyzed': 100,
            'complete': 60,
            'needs_backfill': 40,
            'fully_missing': 25,
            'partially_missing': 15,
            'efficiency_gain_pct': 60.0,
            'api_calls_saved': 60
        }

        analyzer.analyze_gaps.return_value = gap_result
        return analyzer

    @pytest.fixture
    def mock_equity_status(self):
        """Mock get_equity_backfill_status() return value"""
        return {
            'total': 1000,
            'with_equity': 900,
            'without_equity': 100,
            'coverage_pct': 90.0
        }

    # ========================================================================
    # Gap-Aware Mode 테스트
    # ========================================================================

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    @patch('builtins.print')
    def test_gap_aware_mode_pre_scan(
        self,
        mock_print,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status,
        mock_db,
        mock_gap_analyzer
    ):
        """Gap-aware 모드에서 pre-scan이 실행되는지 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status
        mock_db_class.return_value = mock_db
        mock_analyzer_class.return_value = mock_gap_analyzer
        mock_subprocess.return_value = Mock(returncode=0)

        # Import function (after mocks are set up)
        from spock_refresh import run_equity_backfill

        # Execute with gap analysis enabled
        run_equity_backfill(limit=50, dry_run=True, use_gap_analysis=True)

        # Verify gap analyzer was created
        mock_analyzer_class.assert_called_once_with(mock_db)

        # Verify analyze_gaps was called with correct parameters
        mock_gap_analyzer.analyze_gaps.assert_called_once()
        call_kwargs = mock_gap_analyzer.analyze_gaps.call_args[1]

        assert call_kwargs['table'] == 'ticker_fundamentals'
        assert call_kwargs['target_columns'] == ['capital_stock', 'capital_surplus', 'retained_earnings']
        assert call_kwargs['region'] == 'KR'
        assert call_kwargs['asset_type'] == 'STOCK'
        assert isinstance(call_kwargs['backfill_start_date'], date)
        assert call_kwargs['limit'] == 50

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    def test_gap_aware_command_building(
        self,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status,
        mock_db,
        mock_gap_analyzer
    ):
        """Gap-aware 모드에서 command에 올바른 플래그가 추가되는지 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status
        mock_db_class.return_value = mock_db
        mock_analyzer_class.return_value = mock_gap_analyzer
        mock_subprocess.return_value = Mock(returncode=0)

        from spock_refresh import run_equity_backfill

        # Execute
        run_equity_backfill(limit=10, dry_run=True, use_gap_analysis=True)

        # Verify subprocess.run was called with gap analysis flags
        mock_subprocess.assert_called_once()
        cmd_args = mock_subprocess.call_args[0][0]

        assert '--use-gap-analysis' in cmd_args
        assert '--target-columns' in cmd_args

        # Verify target columns follow --target-columns flag
        target_idx = cmd_args.index('--target-columns')
        assert cmd_args[target_idx + 1] == 'capital_stock'
        assert cmd_args[target_idx + 2] == 'capital_surplus'
        assert cmd_args[target_idx + 3] == 'retained_earnings'

    # ========================================================================
    # Legacy Mode 테스트
    # ========================================================================

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    def test_legacy_mode_no_gap_analysis(
        self,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status
    ):
        """Legacy 모드에서 gap analysis가 실행되지 않는지 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status
        mock_subprocess.return_value = Mock(returncode=0)

        from spock_refresh import run_equity_backfill

        # Execute with gap analysis disabled
        run_equity_backfill(limit=10, dry_run=True, use_gap_analysis=False)

        # Verify GapAnalyzer was NOT created
        mock_analyzer_class.assert_not_called()

        # Verify subprocess.run was called WITHOUT gap analysis flags
        mock_subprocess.assert_called_once()
        cmd_args = mock_subprocess.call_args[0][0]

        assert '--use-gap-analysis' not in cmd_args
        assert '--target-columns' not in cmd_args

    # ========================================================================
    # Graceful Fallback 테스트
    # ========================================================================

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    @patch('builtins.print')
    def test_gap_analysis_failure_fallback(
        self,
        mock_print,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status,
        mock_db
    ):
        """Gap analysis 실패 시 graceful fallback 동작 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status
        mock_db_class.return_value = mock_db

        # Mock gap analyzer to raise exception
        mock_analyzer = Mock(spec=GapAnalyzer)
        mock_analyzer.analyze_gaps.side_effect = Exception("Database connection error")
        mock_analyzer_class.return_value = mock_analyzer

        mock_subprocess.return_value = Mock(returncode=0)

        from spock_refresh import run_equity_backfill

        # Execute (should not raise exception)
        run_equity_backfill(limit=10, dry_run=True, use_gap_analysis=True)

        # Verify subprocess.run was called WITHOUT gap analysis flags (fallback)
        mock_subprocess.assert_called_once()
        cmd_args = mock_subprocess.call_args[0][0]

        assert '--use-gap-analysis' not in cmd_args
        assert '--target-columns' not in cmd_args

        # Verify warning message was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('Gap analysis failed' in str(call) for call in print_calls)

    # ========================================================================
    # Command Building 세부 검증
    # ========================================================================

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    def test_command_building_with_all_parameters(
        self,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status,
        mock_db,
        mock_gap_analyzer
    ):
        """모든 파라미터가 command에 올바르게 반영되는지 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status
        mock_db_class.return_value = mock_db
        mock_analyzer_class.return_value = mock_gap_analyzer
        mock_subprocess.return_value = Mock(returncode=0)

        from spock_refresh import run_equity_backfill

        # Execute with specific parameters
        run_equity_backfill(limit=25, dry_run=True, rate_limit=2.0, use_gap_analysis=True)

        # Verify command
        mock_subprocess.assert_called_once()
        cmd_args = mock_subprocess.call_args[0][0]

        # Check basic flags
        assert sys.executable in cmd_args
        assert 'scripts/backfill_fundamentals_dart.py' in cmd_args

        # Check limit
        limit_idx = cmd_args.index('--limit')
        assert cmd_args[limit_idx + 1] == '25'

        # Check rate-limit
        rate_idx = cmd_args.index('--rate-limit')
        assert cmd_args[rate_idx + 1] == '2.0'

        # Check dry-run flag
        assert '--dry-run' in cmd_args

        # Check gap analysis flags
        assert '--use-gap-analysis' in cmd_args
        assert '--target-columns' in cmd_args

    # ========================================================================
    # Edge Cases
    # ========================================================================

    @patch('spock_refresh.get_equity_backfill_status')
    def test_no_remaining_tickers(self, mock_status_func):
        """남은 ticker가 없을 때 early return 검증"""
        # Mock status with no remaining tickers
        mock_status_func.return_value = {
            'total': 1000,
            'with_equity': 1000,
            'without_equity': 0,
            'coverage_pct': 100.0
        }

        from spock_refresh import run_equity_backfill

        # Execute (should return early)
        result = run_equity_backfill(limit=10, dry_run=True, use_gap_analysis=True)

        # Function should return None (early exit)
        assert result is None

    @patch('spock_refresh.get_equity_backfill_status')
    def test_database_connection_failure(self, mock_status_func):
        """Database 연결 실패 시 early return 검증"""
        # Mock status to return None (connection failure)
        mock_status_func.return_value = None

        from spock_refresh import run_equity_backfill

        # Execute (should return early)
        result = run_equity_backfill(limit=10, dry_run=True, use_gap_analysis=True)

        # Function should return None (early exit)
        assert result is None

    @patch('spock_refresh.get_equity_backfill_status')
    @patch('spock_refresh.GapAnalyzer')
    @patch('spock_refresh.PostgresDatabaseManager')
    @patch('spock_refresh.subprocess.run')
    def test_limit_exceeds_remaining(
        self,
        mock_subprocess,
        mock_db_class,
        mock_analyzer_class,
        mock_status_func,
        mock_equity_status,
        mock_db,
        mock_gap_analyzer
    ):
        """Limit이 remaining보다 클 때 actual_limit 조정 검증"""
        # Mock setup
        mock_status_func.return_value = mock_equity_status  # 100 remaining
        mock_db_class.return_value = mock_db
        mock_analyzer_class.return_value = mock_gap_analyzer
        mock_subprocess.return_value = Mock(returncode=0)

        from spock_refresh import run_equity_backfill

        # Execute with limit > remaining
        run_equity_backfill(limit=500, dry_run=True, use_gap_analysis=True)

        # Verify analyze_gaps was called with actual_limit = remaining (100)
        call_kwargs = mock_gap_analyzer.analyze_gaps.call_args[1]
        assert call_kwargs['limit'] == 100  # Should be capped at remaining


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
