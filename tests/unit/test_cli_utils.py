#!/usr/bin/env python3
"""
test_cli_utils.py - Unit Tests for CLI Utilities

Tests for:
- QueryBuilder: Fluent SQL query construction
- OutputFormatter: Value formatting, JSON serialization

Coverage target: cli/utils/* (~400 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
from datetime import datetime, date
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch


class TestSortOrder(unittest.TestCase):
    """Test SortOrder enum"""

    def test_sort_order_values(self):
        """Test SortOrder enum has correct values"""
        from cli.utils.query_builder import SortOrder

        self.assertEqual(SortOrder.ASC.value, "ASC")
        self.assertEqual(SortOrder.DESC.value, "DESC")

    def test_sort_order_enum_members(self):
        """Test SortOrder has exactly two members"""
        from cli.utils.query_builder import SortOrder

        members = list(SortOrder)
        self.assertEqual(len(members), 2)
        self.assertIn(SortOrder.ASC, members)
        self.assertIn(SortOrder.DESC, members)


class TestQueryBuilderInit(unittest.TestCase):
    """Test QueryBuilder initialization"""

    def test_initialization(self):
        """Test QueryBuilder initial state"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()

        self.assertEqual(qb._base_table, "")
        self.assertEqual(qb._columns, ["*"])
        self.assertEqual(qb._filters, [])
        self.assertEqual(qb._params, [])
        self.assertEqual(qb._order_by, [])
        self.assertIsNone(qb._limit)
        self.assertEqual(qb._region, "KR")
        self.assertEqual(qb._joins, [])
        self.assertEqual(qb._param_counter, 0)


class TestQueryBuilderTickers(unittest.TestCase):
    """Test QueryBuilder.tickers() method"""

    def test_tickers_default_region(self):
        """Test tickers() with default region"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers()

        self.assertEqual(qb._base_table, "tickers")
        self.assertEqual(qb._region, "KR")
        self.assertIn("t.ticker", qb._columns)
        self.assertIn("t.name", qb._columns)

    def test_tickers_custom_region(self):
        """Test tickers() with custom region"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers(region="US")

        self.assertEqual(qb._region, "US")

    def test_tickers_method_chaining(self):
        """Test tickers() returns self for chaining"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        result = qb.tickers()

        self.assertIs(result, qb)


class TestQueryBuilderSelect(unittest.TestCase):
    """Test QueryBuilder.select() method"""

    def test_select_custom_columns(self):
        """Test select() sets custom columns"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().select(["t.ticker", "t.name"])

        self.assertEqual(qb._columns, ["t.ticker", "t.name"])

    def test_select_method_chaining(self):
        """Test select() returns self for chaining"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        result = qb.select(["col1"])

        self.assertIs(result, qb)


class TestQueryBuilderFilter(unittest.TestCase):
    """Test QueryBuilder.filter() method"""

    def test_filter_single_param(self):
        """Test filter() with single parameter"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter("per < $1", 15.0)

        self.assertEqual(len(qb._filters), 1)
        self.assertIn("per < $1", qb._filters[0])
        self.assertEqual(qb._params, [15.0])

    def test_filter_multiple_params(self):
        """Test filter() with multiple parameters"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter("per < $1 AND pbr < $2", 15.0, 1.5)

        self.assertEqual(len(qb._params), 2)
        self.assertEqual(qb._params[0], 15.0)
        self.assertEqual(qb._params[1], 1.5)

    def test_filter_param_renumbering(self):
        """Test filter() renumbers parameters correctly"""
        from cli.utils.query_builder import QueryBuilder

        qb = (QueryBuilder()
              .tickers()
              .filter("per < $1", 15.0)
              .filter("pbr < $1", 1.5))

        # Second filter's $1 should become $2
        self.assertEqual(qb._params, [15.0, 1.5])
        self.assertIn("$1", qb._filters[0])
        self.assertIn("$2", qb._filters[1])

    def test_filter_method_chaining(self):
        """Test filter() returns self for chaining"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers()
        result = qb.filter("per < $1", 10)

        self.assertIs(result, qb)


class TestQueryBuilderFilterDict(unittest.TestCase):
    """Test QueryBuilder.filter_dict() method"""

    def test_filter_dict_single_filter(self):
        """Test filter_dict() with single filter"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter_dict({"region": "KR"})

        self.assertEqual(len(qb._filters), 1)
        self.assertIn("region = $1", qb._filters[0])
        self.assertEqual(qb._params, ["KR"])

    def test_filter_dict_multiple_filters(self):
        """Test filter_dict() with multiple filters"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter_dict({
            "region": "KR",
            "asset_type": "STOCK"
        })

        self.assertEqual(len(qb._filters), 2)
        self.assertEqual(len(qb._params), 2)

    def test_filter_dict_empty(self):
        """Test filter_dict() with empty dict"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter_dict({})

        self.assertEqual(qb._filters, [])
        self.assertEqual(qb._params, [])


class TestQueryBuilderOrderBy(unittest.TestCase):
    """Test QueryBuilder.order_by() method"""

    def test_order_by_desc(self):
        """Test order_by() with DESC"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder().tickers().order_by("market_cap", SortOrder.DESC)

        self.assertEqual(len(qb._order_by), 1)
        self.assertEqual(qb._order_by[0], ("market_cap", SortOrder.DESC))

    def test_order_by_asc(self):
        """Test order_by() with ASC"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder().tickers().order_by("per", SortOrder.ASC)

        self.assertEqual(qb._order_by[0], ("per", SortOrder.ASC))

    def test_order_by_multiple(self):
        """Test order_by() with multiple columns"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = (QueryBuilder()
              .tickers()
              .order_by("per", SortOrder.ASC)
              .order_by("pbr", SortOrder.ASC))

        self.assertEqual(len(qb._order_by), 2)

    def test_order_by_default_direction(self):
        """Test order_by() defaults to DESC"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder().tickers().order_by("market_cap")

        self.assertEqual(qb._order_by[0][1], SortOrder.DESC)


class TestQueryBuilderLimit(unittest.TestCase):
    """Test QueryBuilder.top() and limit() methods"""

    def test_top(self):
        """Test top() sets limit"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().top(10)

        self.assertEqual(qb._limit, 10)

    def test_limit_alias(self):
        """Test limit() is alias for top()"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().limit(20)

        self.assertEqual(qb._limit, 20)


class TestQueryBuilderBuild(unittest.TestCase):
    """Test QueryBuilder.build() method"""

    def test_build_simple_query(self):
        """Test build() generates simple query"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers()
        query, params = qb.build()

        self.assertIn("SELECT", query)
        self.assertIn("FROM tickers t", query)
        self.assertIn("WHERE", query)
        self.assertIn("t.region = $1", query)
        self.assertIn("t.is_active = true", query)
        self.assertEqual(params[-1], "KR")

    def test_build_with_filter(self):
        """Test build() includes filters"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().filter("per < $1", 15.0)
        query, params = qb.build()

        self.assertIn("per <", query)
        self.assertIn(15.0, params)

    def test_build_with_order(self):
        """Test build() includes ORDER BY"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = QueryBuilder().tickers().order_by("market_cap", SortOrder.DESC)
        query, params = qb.build()

        self.assertIn("ORDER BY market_cap DESC", query)

    def test_build_with_limit(self):
        """Test build() includes LIMIT"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().top(10)
        query, params = qb.build()

        self.assertIn("LIMIT 10", query)

    def test_build_no_base_table_raises(self):
        """Test build() raises without base table"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()

        with self.assertRaises(ValueError) as ctx:
            qb.build()

        self.assertIn("Base table not specified", str(ctx.exception))


class TestQueryBuilderJoins(unittest.TestCase):
    """Test QueryBuilder JOIN methods"""

    def test_with_fundamentals(self):
        """Test with_fundamentals() adds JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().with_fundamentals()

        self.assertEqual(len(qb._joins), 1)
        self.assertIn("ticker_fundamentals", qb._joins[0])
        self.assertIn("f.per", qb._columns)
        self.assertIn("f.pbr", qb._columns)

    def test_with_fundamentals_no_duplicate(self):
        """Test with_fundamentals() doesn't duplicate JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().with_fundamentals().with_fundamentals()

        self.assertEqual(len(qb._joins), 1)

    def test_with_technicals(self):
        """Test with_technicals() adds JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().with_technicals()

        self.assertEqual(len(qb._joins), 1)
        self.assertIn("ohlcv_data", qb._joins[0])
        self.assertIn("o.close", qb._columns)
        self.assertIn("o.rsi_14", qb._columns)

    def test_with_details(self):
        """Test with_details() adds JOIN"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().with_details()

        self.assertEqual(len(qb._joins), 1)
        self.assertIn("stock_details", qb._joins[0])
        self.assertIn("sd.sector", qb._columns)
        self.assertIn("sd.industry", qb._columns)


class TestQueryBuilderReset(unittest.TestCase):
    """Test QueryBuilder.reset() method"""

    def test_reset(self):
        """Test reset() clears state"""
        from cli.utils.query_builder import QueryBuilder

        qb = (QueryBuilder()
              .tickers()
              .filter("per < $1", 15.0)
              .top(10)
              .reset())

        self.assertEqual(qb._base_table, "")
        self.assertEqual(qb._filters, [])
        self.assertEqual(qb._params, [])
        self.assertIsNone(qb._limit)


class TestQueryBuilderStr(unittest.TestCase):
    """Test QueryBuilder.__str__() method"""

    def test_str_complete_query(self):
        """Test __str__() shows complete query"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder().tickers().top(5)
        result = str(qb)

        self.assertIn("Query:", result)
        self.assertIn("Params:", result)
        self.assertIn("SELECT", result)

    def test_str_incomplete_query(self):
        """Test __str__() handles incomplete query"""
        from cli.utils.query_builder import QueryBuilder

        qb = QueryBuilder()
        result = str(qb)

        self.assertIn("incomplete", result)


# =============================================================================
# OutputFormatter Tests
# =============================================================================

class TestOutputFormatterInit(unittest.TestCase):
    """Test OutputFormatter initialization"""

    def test_init_default(self):
        """Test OutputFormatter default initialization"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter()

        self.assertEqual(formatter.output_format, 'table')

    def test_init_json_format(self):
        """Test OutputFormatter with JSON format"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter(output_format='json')

        self.assertEqual(formatter.output_format, 'json')

    def test_init_color_disabled(self):
        """Test OutputFormatter with color disabled"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter(color_enabled=False)

        self.assertIsNotNone(formatter.console)


class TestOutputFormatterFormatValue(unittest.TestCase):
    """Test OutputFormatter._format_value() method"""

    def setUp(self):
        """Set up formatter instance"""
        from cli.utils.output_formatter import OutputFormatter
        self.formatter = OutputFormatter()

    def test_format_value_none(self):
        """Test _format_value() with None"""
        result = self.formatter._format_value(None)

        self.assertIn("N/A", result)

    def test_format_value_bool_true(self):
        """Test _format_value() with True"""
        result = self.formatter._format_value(True)

        self.assertIn("Yes", result)

    def test_format_value_bool_false(self):
        """Test _format_value() with False"""
        result = self.formatter._format_value(False)

        self.assertIn("No", result)

    def test_format_value_int(self):
        """Test _format_value() with integer"""
        result = self.formatter._format_value(42)

        self.assertEqual(result, "42")

    def test_format_value_float(self):
        """Test _format_value() with float"""
        result = self.formatter._format_value(3.14159)

        self.assertEqual(result, "3.1416")

    def test_format_value_decimal(self):
        """Test _format_value() with Decimal"""
        result = self.formatter._format_value(Decimal("2.7182"))

        self.assertEqual(result, "2.7182")

    def test_format_value_datetime(self):
        """Test _format_value() with datetime"""
        dt = datetime(2024, 10, 15, 12, 30, 0)
        result = self.formatter._format_value(dt)

        self.assertIn("2024-10-15", result)

    def test_format_value_date(self):
        """Test _format_value() with date"""
        d = date(2024, 10, 15)
        result = self.formatter._format_value(d)

        self.assertEqual(result, "2024-10-15")

    def test_format_value_string(self):
        """Test _format_value() with string"""
        result = self.formatter._format_value("hello")

        self.assertEqual(result, "hello")


class TestOutputFormatterJsonSerializer(unittest.TestCase):
    """Test OutputFormatter._json_serializer() method"""

    def setUp(self):
        """Set up formatter instance"""
        from cli.utils.output_formatter import OutputFormatter
        self.formatter = OutputFormatter()

    def test_json_serializer_datetime(self):
        """Test _json_serializer() with datetime"""
        dt = datetime(2024, 10, 15, 12, 30, 0)
        result = self.formatter._json_serializer(dt)

        self.assertEqual(result, "2024-10-15T12:30:00")

    def test_json_serializer_date(self):
        """Test _json_serializer() with date"""
        d = date(2024, 10, 15)
        result = self.formatter._json_serializer(d)

        self.assertEqual(result, "2024-10-15")

    def test_json_serializer_decimal(self):
        """Test _json_serializer() with Decimal"""
        result = self.formatter._json_serializer(Decimal("3.14159"))

        self.assertEqual(result, 3.14159)
        self.assertIsInstance(result, float)

    def test_json_serializer_other(self):
        """Test _json_serializer() with other types"""
        result = self.formatter._json_serializer([1, 2, 3])

        self.assertEqual(result, "[1, 2, 3]")


class TestOutputFormatterMessages(unittest.TestCase):
    """Test OutputFormatter message methods"""

    def setUp(self):
        """Set up formatter with JSON output"""
        from cli.utils.output_formatter import OutputFormatter
        self.formatter = OutputFormatter(output_format='json')

    @patch('builtins.print')
    def test_print_success_json(self, mock_print):
        """Test print_success() in JSON mode"""
        self.formatter.print_success("Operation completed")

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("success", call_args)

    @patch('builtins.print')
    def test_print_error_json(self, mock_print):
        """Test print_error() in JSON mode"""
        self.formatter.print_error("Operation failed", "Details here")

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("error", call_args)

    @patch('builtins.print')
    def test_print_warning_json(self, mock_print):
        """Test print_warning() in JSON mode"""
        self.formatter.print_warning("Warning message")

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("warning", call_args)

    @patch('builtins.print')
    def test_print_info_json(self, mock_print):
        """Test print_info() in JSON mode"""
        self.formatter.print_info("Info message")

        mock_print.assert_called_once()
        call_args = mock_print.call_args[0][0]
        self.assertIn("info", call_args)


class TestOutputFormatterPrintTable(unittest.TestCase):
    """Test OutputFormatter.print_table() method"""

    def test_print_table_empty_data(self):
        """Test print_table() with empty data shows warning"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter()
        # Should not raise, just print warning
        formatter.print_table([])

    def test_print_table_json_mode(self):
        """Test print_table() delegates to print_json in JSON mode"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter(output_format='json')

        with patch.object(formatter, 'print_json') as mock_json:
            formatter.print_table([{"a": 1}])
            mock_json.assert_called_once_with([{"a": 1}])


class TestOutputFormatterPrintKeyValue(unittest.TestCase):
    """Test OutputFormatter.print_key_value() method"""

    def test_print_key_value_json_mode(self):
        """Test print_key_value() delegates to print_json in JSON mode"""
        from cli.utils.output_formatter import OutputFormatter

        formatter = OutputFormatter(output_format='json')

        with patch.object(formatter, 'print_json') as mock_json:
            formatter.print_key_value({"key": "value"})
            mock_json.assert_called_once_with({"key": "value"})


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("region,expected", [
    ("KR", "KR"),
    ("US", "US"),
    ("JP", "JP"),
    ("HK", "HK"),
    ("CN", "CN"),
])
def test_query_builder_regions(region, expected):
    """Test QueryBuilder supports various regions"""
    from cli.utils.query_builder import QueryBuilder

    qb = QueryBuilder().tickers(region=region)
    assert qb._region == expected


@pytest.mark.parametrize("limit,expected", [
    (1, 1),
    (10, 10),
    (100, 100),
    (1000, 1000),
])
def test_query_builder_limits(limit, expected):
    """Test QueryBuilder supports various limits"""
    from cli.utils.query_builder import QueryBuilder

    qb = QueryBuilder().tickers().top(limit)
    assert qb._limit == expected


@pytest.mark.parametrize("value,expected_contains", [
    (None, "N/A"),
    (True, "Yes"),
    (False, "No"),
    (42, "42"),
    (3.14159, "3.1416"),
    ("text", "text"),
])
def test_format_value_parametrized(value, expected_contains):
    """Test _format_value() with various types"""
    from cli.utils.output_formatter import OutputFormatter

    formatter = OutputFormatter()
    result = formatter._format_value(value)
    assert expected_contains in result


@pytest.mark.parametrize("order,expected_value", [
    ("ASC", "ASC"),
    ("DESC", "DESC"),
])
def test_sort_order_enum_values(order, expected_value):
    """Test SortOrder enum values"""
    from cli.utils.query_builder import SortOrder

    assert SortOrder[order].value == expected_value


@pytest.mark.parametrize("columns", [
    ["t.ticker"],
    ["t.ticker", "t.name"],
    ["t.ticker", "t.name", "t.region"],
    ["*"],
])
def test_query_builder_column_selection(columns):
    """Test QueryBuilder with various column selections"""
    from cli.utils.query_builder import QueryBuilder

    qb = QueryBuilder().select(columns)
    assert qb._columns == columns


# =============================================================================
# Integration Tests
# =============================================================================

class TestQueryBuilderIntegration(unittest.TestCase):
    """Integration tests for QueryBuilder"""

    def test_full_query_chain(self):
        """Test complete query building chain"""
        from cli.utils.query_builder import QueryBuilder, SortOrder

        qb = (QueryBuilder()
              .tickers(region="US")
              .select(["t.ticker", "t.name", "f.per", "f.pbr"])
              .with_fundamentals()
              .filter("f.per < $1", 15.0)
              .filter("f.pbr < $1", 1.5)
              .order_by("f.per", SortOrder.ASC)
              .order_by("f.pbr", SortOrder.ASC)
              .top(20))

        query, params = qb.build()

        # Verify query structure
        self.assertIn("SELECT t.ticker, t.name, f.per, f.pbr", query)
        self.assertIn("FROM tickers t", query)
        self.assertIn("ticker_fundamentals", query)
        self.assertIn("ORDER BY f.per ASC, f.pbr ASC", query)
        self.assertIn("LIMIT 20", query)

        # Verify params
        self.assertIn(15.0, params)
        self.assertIn(1.5, params)
        self.assertIn("US", params)

    def test_multiple_joins(self):
        """Test query with multiple JOINs"""
        from cli.utils.query_builder import QueryBuilder

        qb = (QueryBuilder()
              .tickers()
              .with_fundamentals()
              .with_technicals()
              .with_details())

        query, _ = qb.build()

        self.assertIn("ticker_fundamentals", query)
        self.assertIn("ohlcv_data", query)
        self.assertIn("stock_details", query)
        self.assertEqual(len(qb._joins), 3)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions"""

    @patch('cli.utils.output_formatter.console')
    def test_print_success_function(self, mock_console):
        """Test module-level print_success()"""
        from cli.utils.output_formatter import print_success

        print_success("Test message")

        mock_console.print.assert_called_once()

    @patch('cli.utils.output_formatter.console')
    def test_print_error_function(self, mock_console):
        """Test module-level print_error()"""
        from cli.utils.output_formatter import print_error

        print_error("Error message", "Details")

        # Called twice: once for error, once for details
        self.assertEqual(mock_console.print.call_count, 2)

    @patch('cli.utils.output_formatter.console')
    def test_print_warning_function(self, mock_console):
        """Test module-level print_warning()"""
        from cli.utils.output_formatter import print_warning

        print_warning("Warning message")

        mock_console.print.assert_called_once()

    @patch('cli.utils.output_formatter.console')
    def test_print_info_function(self, mock_console):
        """Test module-level print_info()"""
        from cli.utils.output_formatter import print_info

        print_info("Info message")

        mock_console.print.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
