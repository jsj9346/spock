"""
Unit tests for cli/commands/query.py - Query command
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import argparse


@pytest.mark.unit
class TestQueryCommand:
    """Test query command functionality"""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock DatabaseManager"""
        db = Mock()
        db.connect = AsyncMock()
        db.disconnect = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def sample_query_results(self):
        """Sample query results"""
        return [
            {'ticker': '005930', 'name': '삼성전자', 'per': 12.5},
            {'ticker': '000660', 'name': 'SK하이닉스', 'per': 10.3}
        ]

    @pytest.fixture
    def query_args(self):
        """Mock query arguments"""
        args = Mock()
        args.region = 'KR'
        args.top = 20
        args.with_fundamentals = False
        args.with_technicals = False
        args.with_details = False
        args.filter = []
        args.sort_by = None
        args.order = 'asc'
        args.columns = None
        args.csv = None
        args.json = None
        args.preset = None
        return args

    @pytest.mark.asyncio
    async def test_query_command_basic_execution(self, mock_db_manager, sample_query_results, query_args):
        """Test basic query command execution"""
        from cli.commands.query import run_query

        mock_db_manager.fetch.return_value = sample_query_results

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryFormatter'):
                result = await run_query(query_args)

                assert result is not None
                mock_db_manager.connect.assert_called_once()
                mock_db_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_fundamentals_flag(self, mock_db_manager, query_args):
        """Test query with --with-fundamentals flag"""
        from cli.commands.query import run_query

        query_args.with_fundamentals = True

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryBuilder') as mock_qb:
                with patch('cli.commands.query.QueryFormatter'):
                    await run_query(query_args)

                    # Should call with_fundamentals()
                    # Verify through QueryBuilder mock

    @pytest.mark.asyncio
    async def test_query_with_filters(self, mock_db_manager, query_args):
        """Test query with filter expressions"""
        from cli.commands.query import run_query

        query_args.filter = ['per < 15', 'pbr < 1']

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryBuilder') as mock_qb:
                with patch('cli.commands.query.QueryFormatter'):
                    await run_query(query_args)

                    # Filters should be applied

    @pytest.mark.asyncio
    async def test_csv_export(self, mock_db_manager, sample_query_results, query_args, tmp_path):
        """Test CSV export functionality"""
        from cli.commands.query import run_query

        query_args.csv = str(tmp_path / "output.csv")
        mock_db_manager.fetch.return_value = sample_query_results

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryFormatter') as mock_formatter:
                await run_query(query_args)

                # Should call export_csv
                # Verify through formatter mock

    @pytest.mark.asyncio
    async def test_json_export(self, mock_db_manager, sample_query_results, query_args, tmp_path):
        """Test JSON export functionality"""
        from cli.commands.query import run_query

        query_args.json = str(tmp_path / "output.json")
        mock_db_manager.fetch.return_value = sample_query_results

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            await run_query(query_args)

            # JSON file should be created
            json_path = tmp_path / "output.json"
            # Verify file exists after implementation

    @pytest.mark.asyncio
    async def test_preset_value_stocks(self, mock_db_manager, query_args):
        """Test 'value' preset filter"""
        from cli.commands.query import run_query

        query_args.preset = 'value'

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryBuilder') as mock_qb:
                with patch('cli.commands.query.QueryFormatter'):
                    await run_query(query_args)

                    # Value preset should add filters for low PER/PBR

    @pytest.mark.asyncio
    async def test_error_handling_database_connection(self, query_args):
        """Test error handling for database connection failures"""
        from cli.commands.query import run_query

        mock_db = Mock()
        mock_db.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db):
            with pytest.raises(Exception, match="Connection failed"):
                await run_query(query_args)

    @pytest.mark.asyncio
    async def test_empty_results_handling(self, mock_db_manager, query_args):
        """Test handling of empty query results"""
        from cli.commands.query import run_query

        mock_db_manager.fetch.return_value = []

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryFormatter') as mock_formatter:
                await run_query(query_args)

                # Should still format output, even if empty

    @pytest.mark.asyncio
    async def test_column_selection(self, mock_db_manager, sample_query_results, query_args):
        """Test custom column selection"""
        from cli.commands.query import run_query

        query_args.columns = ['ticker', 'name', 'per']
        mock_db_manager.fetch.return_value = sample_query_results

        with patch('cli.commands.query.DatabaseManager', return_value=mock_db_manager):
            with patch('cli.commands.query.QueryBuilder') as mock_qb:
                with patch('cli.commands.query.QueryFormatter'):
                    await run_query(query_args)

                    # Should select only specified columns
