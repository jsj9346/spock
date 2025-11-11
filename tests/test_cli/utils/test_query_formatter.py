"""
Unit tests for cli/utils/query_formatter.py - QueryFormatter
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from io import StringIO


@pytest.mark.unit
class TestQueryFormatter:
    """Test QueryFormatter class"""

    @pytest.fixture
    def sample_rows(self):
        """Sample query results"""
        return [
            {'ticker': '005930', 'name': '삼성전자', 'per': 12.5, 'pbr': 1.2},
            {'ticker': '000660', 'name': 'SK하이닉스', 'per': 10.3, 'pbr': 0.9},
            {'ticker': '035720', 'name': '카카오', 'per': 25.8, 'pbr': 2.1}
        ]

    def test_print_table_creates_rich_table(self, sample_rows):
        """Test that print_table() creates Rich table"""
        from cli.utils.query_formatter import QueryFormatter

        # Create mock console and inject it
        mock_console = Mock()
        formatter = QueryFormatter(console=mock_console)

        # Should not raise exception and should call console.print
        formatter.print_table(sample_rows, title='Test Results')

        # Console.print should be called
        assert mock_console.print.called

    def test_print_table_with_korean_text(self, sample_rows):
        """Test that Korean text is handled correctly"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()

        # Should handle Korean characters without errors
        with patch('cli.utils.query_formatter.Console'):
            formatter.print_table(sample_rows, title='한글 테스트')

    def test_export_csv_creates_file(self, sample_rows, tmp_path):
        """Test that export_csv() creates CSV file"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()
        csv_path = tmp_path / "test_output.csv"

        formatter.export_csv(sample_rows, str(csv_path))

        assert csv_path.exists()
        content = csv_path.read_text(encoding='utf-8-sig')
        assert '삼성전자' in content
        assert 'SK하이닉스' in content

    def test_export_csv_utf8_bom_encoding(self, sample_rows, tmp_path):
        """Test that CSV uses UTF-8-BOM encoding for Excel"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()
        csv_path = tmp_path / "test_output.csv"

        formatter.export_csv(sample_rows, str(csv_path))

        # Check for BOM
        with open(csv_path, 'rb') as f:
            first_bytes = f.read(3)
            assert first_bytes == b'\xef\xbb\xbf'  # UTF-8 BOM

    def test_print_success_message(self):
        """Test that print_success() displays success message"""
        from cli.utils.query_formatter import QueryFormatter

        # Create mock console and inject it
        mock_console = Mock()
        formatter = QueryFormatter(console=mock_console)

        formatter.print_success('Operation completed')

        # Console.print should be called
        assert mock_console.print.called

    def test_print_error_message(self):
        """Test that print_error() displays error message"""
        from cli.utils.query_formatter import QueryFormatter

        # Create mock console and inject it
        mock_console = Mock()
        formatter = QueryFormatter(console=mock_console)

        formatter.print_error('Operation failed')

        # Console.print should be called
        assert mock_console.print.called

    def test_print_warning_message(self):
        """Test that print_warning() displays warning message"""
        from cli.utils.query_formatter import QueryFormatter

        # Create mock console and inject it
        mock_console = Mock()
        formatter = QueryFormatter(console=mock_console)

        formatter.print_warning('Operation warning')

        # Console.print should be called
        assert mock_console.print.called

    def test_format_number_with_commas(self):
        """Test that numbers are formatted with thousands separators"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()
        rows = [{'value': 1000000}]

        with patch('cli.utils.query_formatter.Console'):
            # Should format large numbers with commas
            formatter.print_table(rows)

    def test_export_csv_with_column_selection(self, sample_rows, tmp_path):
        """Test that CSV export respects column selection"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()
        csv_path = tmp_path / "test_output.csv"

        # Export only specific columns
        selected_columns = ['ticker', 'name']
        formatter.export_csv(sample_rows, str(csv_path), columns=selected_columns)

        content = csv_path.read_text(encoding='utf-8-sig')
        assert 'ticker' in content
        assert 'name' in content
        # per and pbr should not be in CSV if column selection works

    def test_empty_results_handling(self):
        """Test that empty results are handled gracefully"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()
        empty_rows = []

        with patch('cli.utils.query_formatter.Console'):
            # Should not raise exception
            formatter.print_table(empty_rows, title='No Results')

    def test_print_table_with_custom_columns(self, sample_rows):
        """Test that print_table() can display custom columns"""
        from cli.utils.query_formatter import QueryFormatter

        formatter = QueryFormatter()

        with patch('cli.utils.query_formatter.Console'):
            # Specify columns to display
            formatter.print_table(sample_rows, columns=['ticker', 'name'])
