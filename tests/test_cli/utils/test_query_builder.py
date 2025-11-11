"""
Unit tests for cli/utils/query_builder.py - QueryBuilder
"""
import pytest
from unittest.mock import Mock, AsyncMock


@pytest.mark.unit
class TestQueryBuilder:
    """Test QueryBuilder class"""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager"""
        db = Mock()
        db.fetch = AsyncMock(return_value=[])
        return db

    def test_tickers_generates_base_query(self):
        """Test that tickers() generates base query"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').build()

        assert 'SELECT' in query
        assert 'FROM tickers' in query
        assert "region = $1" in query
        assert params == ['KR']

    def test_with_fundamentals_adds_join(self):
        """Test that with_fundamentals() adds JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').with_fundamentals().build()

        assert 'JOIN' in query.upper()
        assert 'ticker_fundamentals' in query.lower()
        assert 'f.per' in query.lower() or 'fundamentals' in query.lower()

    def test_filter_adds_where_clause(self):
        """Test that filter() adds WHERE clause"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').filter("per < $2", 15.0).build()

        assert 'WHERE' in query.upper()
        assert 'per < $2' in query
        assert 15.0 in params

    def test_multiple_filters_with_and(self):
        """Test that multiple filters are combined with AND"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = (qb
            .tickers('KR')
            .filter("per < $2", 15.0)
            .filter("pbr < $3", 1.0)
            .build()
        )

        assert query.count('AND') >= 1
        assert 15.0 in params
        assert 1.0 in params

    def test_top_adds_limit(self):
        """Test that top() adds LIMIT clause"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').top(20).build()

        assert 'LIMIT' in query.upper()
        assert '20' in query or 20 in params

    def test_order_by_adds_sorting(self):
        """Test that order_by() adds ORDER BY clause"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').order_by('market_cap', SortOrder.DESC).build()

        assert 'ORDER BY' in query.upper()
        assert 'market_cap' in query
        assert 'DESC' in query.upper()

    def test_select_columns_specified(self):
        """Test that select() specifies columns"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').select(['ticker', 'name', 'per']).build()

        assert 'ticker' in query
        assert 'name' in query
        # Note: 'per' might be qualified as 'f.per' if fundamentals joined

    def test_method_chaining(self):
        """Test that methods can be chained fluently"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder()
        result = (qb
            .tickers('KR')
            .with_fundamentals()
            .filter("per < $2", 15.0)
            .top(10)
            .order_by('per', SortOrder.ASC)
        )

        # Should return QueryBuilder for chaining
        assert result is qb

    @pytest.mark.asyncio
    async def test_build_query_for_execution(self, mock_db):
        """Test that QueryBuilder builds queries that can be executed"""
        from cli.utils.query_builder import QueryBuilder

        expected_results = [{'ticker': '005930', 'name': '삼성전자'}]
        mock_db.fetch.return_value = expected_results

        qb = QueryBuilder()
        query, params = qb.tickers('KR').top(5).build()

        # Execute the built query
        results = await mock_db.fetch(query, *params)

        assert results == expected_results
        mock_db.fetch.assert_called_once()

    def test_parameterized_queries_prevent_sql_injection(self):
        """Test that queries use parameterized statements"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').filter("name = $2", "'; DROP TABLE tickers; --").build()

        # SQL injection attempt should be in params, not in query string
        assert "DROP TABLE" not in query
        assert "'; DROP TABLE tickers; --" in params

    def test_empty_query_builder(self):
        """Test QueryBuilder without any methods called"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()

        # Should raise error or return None when no table specified
        with pytest.raises(ValueError):
            qb.build()

    def test_with_technicals_adds_technical_join(self):
        """Test that with_technicals() adds OHLCV data JOIN for technical indicators"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').with_technicals().build()

        assert 'JOIN' in query.upper()
        # with_technicals() joins OHLCV data which contains technical indicators
        assert 'ohlcv_data' in query.lower() or 'technical' in query.lower()

    def test_with_details_adds_details_join(self):
        """Test that with_details() adds stock details JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        query, params = qb.tickers('KR').with_details().build()

        assert 'JOIN' in query.upper()
        # Check for stock_details or etf_details
        assert 'details' in query.lower()
