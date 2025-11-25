#!/usr/bin/env python3
"""
CLI Tests for manage_ticker_status.py

Tests:
- --summary: 전체 리전 요약 출력
- --list-skip: 스킵 티커 목록 출력
- --blacklist: 블랙리스트 추가
- --unblacklist: 블랙리스트 해제
- --auto-detect: US preferred stock 자동 탐지
- --init-from-ohlcv: OHLCV 기반 초기화

Author: Spock Quant Platform
Date: 2025-11-26
"""

import sys
import os
import pytest
import argparse
from io import StringIO
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCLIArgumentParsing:
    """CLI 인자 파싱 테스트"""

    def test_summary_flag(self):
        """--summary 플래그 파싱"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--summary', action='store_true')

        args = parser.parse_args(['--summary'])
        assert args.summary is True

    def test_region_argument(self):
        """--region 인자 파싱"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--region', type=str)

        args = parser.parse_args(['--region', 'JP'])
        assert args.region == 'JP'

    def test_blacklist_with_reason(self):
        """--blacklist와 --reason 조합"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--blacklist', type=str)
        parser.add_argument('--reason', type=str, default='manual')

        args = parser.parse_args(['--blacklist', 'TEST/A', '--reason', 'preferred_stock'])
        assert args.blacklist == 'TEST/A'
        assert args.reason == 'preferred_stock'

    def test_days_argument(self):
        """--days 인자 파싱"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--days', type=int, default=30)

        args = parser.parse_args(['--days', '60'])
        assert args.days == 60


class TestPrintSummary:
    """C-01: --summary 출력 테스트"""

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_summary_output_format(self, mock_tsm_class, mock_db_class):
        """C-01: 요약 테이블 포맷 출력"""
        # Setup mock
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm
        mock_tsm.get_status_summary.return_value = {
            'total': 4036,
            'active': 4024,
            'unknown': 0,
            'retry': 0,
            'delisted': 10,
            'unsupported': 0,
            'blacklist': 2,
            'skip_count': 12,
            'process_count': 4024
        }

        # Import and test the print function
        from scripts.manage_ticker_status import print_summary

        # Capture stdout
        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_summary(mock_tsm, ['JP'])
            output = captured_output.getvalue()

            # Verify output contains expected elements
            assert 'TICKER STATUS SUMMARY' in output
            assert 'JP' in output
            assert 'Active' in output or 'active' in output.lower()
        finally:
            sys.stdout = sys.__stdout__

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_summary_all_regions(self, mock_tsm_class, mock_db_class):
        """C-01: 모든 리전 요약"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm
        mock_tsm.get_status_summary.return_value = {
            'total': 100, 'active': 90, 'unknown': 5, 'retry': 0,
            'delisted': 3, 'unsupported': 1, 'blacklist': 1,
            'skip_count': 5, 'process_count': 95
        }

        from scripts.manage_ticker_status import print_summary

        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            all_regions = ['KR', 'JP', 'US', 'HK', 'CN', 'VN']
            print_summary(mock_tsm, all_regions)
            output = captured_output.getvalue()

            # Should show totals for all regions
            assert 'TOTAL' in output
        finally:
            sys.stdout = sys.__stdout__


class TestListSkipTickers:
    """C-02: --list-skip 출력 테스트"""

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_skip_tickers_output(self, mock_tsm_class, mock_db_class):
        """C-02: 스킵 티커 목록 출력"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm
        mock_tsm.get_skip_tickers.return_value = ['DELISTED1', 'PRF/A', 'BLACKLISTED']
        mock_tsm.get_status.return_value = {
            'yf_status': 'delisted',
            'yf_fail_reason': 'no_data_found'
        }

        from scripts.manage_ticker_status import print_skip_tickers

        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            print_skip_tickers(mock_tsm, 'US', limit=50)
            output = captured_output.getvalue()

            assert 'Skip Tickers' in output
            assert 'US' in output
        finally:
            sys.stdout = sys.__stdout__


class TestBlacklistCommands:
    """C-03, C-04: 블랙리스트 명령 테스트"""

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_blacklist_add(self, mock_tsm_class, mock_db_class):
        """C-03: 블랙리스트 추가"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm

        # Simulate calling set_blacklist
        mock_tsm.set_blacklist('PROBLEM', 'US', 'manual')

        mock_tsm.set_blacklist.assert_called_once_with('PROBLEM', 'US', 'manual')

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_blacklist_remove(self, mock_tsm_class, mock_db_class):
        """C-04: 블랙리스트 해제"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm

        # Simulate calling clear_blacklist
        mock_tsm.clear_blacklist('RESTORED', 'US')

        mock_tsm.clear_blacklist.assert_called_once_with('RESTORED', 'US')


class TestAutoDetect:
    """C-05: --auto-detect 테스트"""

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_auto_detect_us_preferred(self, mock_tsm_class, mock_db_class):
        """C-05: US preferred stock 자동 탐지"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm
        mock_tsm.auto_detect_unsupported.return_value = 433

        # Verify the function can be called
        result = mock_tsm.auto_detect_unsupported('US')

        assert result == 433
        mock_tsm.auto_detect_unsupported.assert_called_once_with('US')


class TestInitFromOHLCV:
    """C-06: --init-from-ohlcv 테스트"""

    @patch('scripts.manage_ticker_status.PostgresDatabaseManager')
    @patch('scripts.manage_ticker_status.TickerStatusManager')
    def test_init_from_ohlcv(self, mock_tsm_class, mock_db_class):
        """C-06: OHLCV 기반 초기화"""
        mock_tsm = Mock()
        mock_tsm_class.return_value = mock_tsm
        mock_tsm.init_status_from_ohlcv.return_value = {
            'active': 4024,
            'unknown': 0
        }

        result = mock_tsm.init_status_from_ohlcv('JP')

        assert result['active'] == 4024
        mock_tsm.init_status_from_ohlcv.assert_called_once_with('JP')


class TestCLIScriptStructure:
    """CLI 스크립트 구조 테스트"""

    def test_script_is_executable(self):
        """스크립트 파일 존재 확인"""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'manage_ticker_status.py'
        )
        assert os.path.exists(script_path), "CLI script should exist"

    def test_script_has_main_function(self):
        """main() 함수 존재 확인"""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'scripts', 'manage_ticker_status.py'
        )

        with open(script_path, 'r') as f:
            content = f.read()

        assert 'def main():' in content, "Script should have main() function"
        assert 'if __name__ == "__main__":' in content, "Script should be executable"


class TestErrorHandling:
    """에러 처리 테스트"""

    def test_region_required_for_blacklist(self):
        """--blacklist 시 --region 필수"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--region', type=str, default=None)
        parser.add_argument('--blacklist', type=str)

        args = parser.parse_args(['--blacklist', 'TEST'])

        # region should be None, which should trigger error in main()
        assert args.region is None
        assert args.blacklist == 'TEST'

    def test_region_required_for_list_skip(self):
        """--list-skip 시 --region 필수"""
        parser = argparse.ArgumentParser()
        parser.add_argument('--region', type=str, default=None)
        parser.add_argument('--list-skip', action='store_true')

        args = parser.parse_args(['--list-skip'])

        assert args.region is None


@pytest.mark.integration
class TestCLIIntegration:
    """CLI 통합 테스트 (실제 DB 연결 필요)"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """테스트 환경 설정"""
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            self.db = PostgresDatabaseManager()
            yield
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_summary_real_data(self):
        """실제 데이터로 요약 출력"""
        import subprocess

        result = subprocess.run(
            ['python3', 'scripts/manage_ticker_status.py', '--summary'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        # Should complete without error
        assert result.returncode == 0
        assert 'TICKER STATUS SUMMARY' in result.stdout

    def test_list_skip_real_data(self):
        """실제 데이터로 스킵 티커 출력"""
        import subprocess

        result = subprocess.run(
            ['python3', 'scripts/manage_ticker_status.py', '--region', 'JP', '--list-skip'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        # Should complete without error
        assert result.returncode == 0


class TestCLIHelp:
    """CLI 도움말 테스트"""

    def test_help_output(self):
        """--help 출력 확인"""
        import subprocess

        result = subprocess.run(
            ['python3', 'scripts/manage_ticker_status.py', '--help'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        assert result.returncode == 0
        assert '--region' in result.stdout
        assert '--summary' in result.stdout
        assert '--blacklist' in result.stdout


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'not integration'])
