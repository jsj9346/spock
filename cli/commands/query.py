"""
Query command for Quant Platform CLI.

Provides stock screening and data retrieval with filters,
sorting, and export capabilities.
"""

import asyncio
import argparse
from typing import List, Optional
import sys

from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder, SortOrder
from cli.utils.query_formatter import QueryFormatter


# Filter presets for common screening strategies
FILTER_PRESETS = {
    'value-stocks': {
        'description': 'Value stocks (low PER, low PBR)',
        'filters': ['f.per < 15', 'f.pbr < 1.0', 'f.market_cap > 1000000000000'],
        'requires': ['with_fundamentals'],
        'sort': [('f.per', SortOrder.ASC), ('f.pbr', SortOrder.ASC)],
    },
    'growth-stocks': {
        'description': 'Growth stocks (high market cap growth potential)',
        'filters': ['f.per > 20', 'f.pbr > 2.0', 'o.rsi_14 > 50'],
        'requires': ['with_fundamentals', 'with_technicals'],
        'sort': [('f.market_cap', SortOrder.DESC)],
    },
    'dividend-stocks': {
        'description': 'Dividend stocks (high dividend yield)',
        'filters': ['f.dividend_yield > 3.0', 'f.market_cap > 1000000000000'],
        'requires': ['with_fundamentals'],
        'sort': [('f.dividend_yield', SortOrder.DESC)],
    },
    'momentum-stocks': {
        'description': 'Momentum stocks (strong uptrend)',
        'filters': ['o.rsi_14 > 60', 'o.macd > 0', 'o.close > o.ma20'],
        'requires': ['with_technicals'],
        'sort': [('o.rsi_14', SortOrder.DESC)],
    },
    'undervalued-quality': {
        'description': 'Undervalued quality stocks (low PER, high market cap)',
        'filters': ['f.per < 20', 'f.per > 5', 'f.market_cap > 5000000000000'],
        'requires': ['with_fundamentals'],
        'sort': [('f.per', SortOrder.ASC), ('f.market_cap', SortOrder.DESC)],
    },
}


async def query_command(args: argparse.Namespace) -> int:
    """
    Execute stock query command with filters and formatting.

    Args:
        args: Parsed command line arguments with following attributes:
            - region: Market region (KR, US)
            - preset: Preset filter strategy (value-stocks, growth-stocks, etc.)
            - filters: List of filter expressions
            - top: Maximum number of results
            - sort_by: List of columns to sort by (supports multiple)
            - order: Default sort order (asc, desc) when not specified in column
            - columns: Columns to display
            - with_fundamentals: Include fundamental data
            - with_technicals: Include technical indicators
            - with_details: Include sector/industry info
            - csv: CSV export file path
            - json: JSON export file path
            - json_compact: Export JSON in compact format
            - summary: Show query summary

    Returns:
        Exit code (0 for success, 1 for error)

    Examples:
        # Basic query - top 10 active stocks
        query --top 10

        # Value stocks with filters
        query --with-fundamentals --filter "f.per < 15" --filter "f.pbr < 1" --top 20

        # Export to CSV
        query --with-fundamentals --top 100 --csv value_stocks.csv

        # Export to JSON (pretty-formatted)
        query --with-fundamentals --top 100 --json value_stocks.json

        # Export to JSON (compact)
        query --with-fundamentals --top 100 --json value_stocks.json --json-compact

        # Custom columns
        query --with-fundamentals --columns ticker name per pbr market_cap --top 20

        # Multiple sort columns (sort by PER ascending, then PBR ascending)
        query --with-fundamentals --sort-by f.per:asc --sort-by f.pbr:asc --top 20

        # Use preset filters (value stocks)
        query --preset value-stocks --top 20

        # Use preset + additional filters
        query --preset dividend-stocks --filter "sd.sector = '은행'" --top 20
    """
    db = DatabaseManager()
    formatter = QueryFormatter()

    try:
        # Connect to database
        await db.connect()

        # Apply preset if specified
        preset_filters = []
        preset_sort = []
        if args.preset:
            if args.preset not in FILTER_PRESETS:
                formatter.print_error(
                    f"Unknown preset: {args.preset}\n"
                    f"Available presets: {', '.join(FILTER_PRESETS.keys())}"
                )
                return 1

            preset = FILTER_PRESETS[args.preset]
            preset_filters = preset['filters']
            preset_sort = preset['sort']

            # Auto-enable required flags
            for requirement in preset['requires']:
                if requirement == 'with_fundamentals':
                    args.with_fundamentals = True
                elif requirement == 'with_technicals':
                    args.with_technicals = True
                elif requirement == 'with_details':
                    args.with_details = True

            formatter.console.print(
                f"[cyan]Using preset:[/cyan] [bold]{args.preset}[/bold] - {preset['description']}"
            )

        # Build query
        qb = QueryBuilder()
        qb.tickers(region=args.region)

        # Add joins based on flags
        if args.with_fundamentals:
            qb.with_fundamentals()

        if args.with_technicals:
            qb.with_technicals()

        if args.with_details:
            qb.with_details()

        # Add preset filters first
        for filter_expr in preset_filters:
            parts = filter_expr.split()
            if len(parts) == 3:
                column, operator, value = parts
                try:
                    param_value = float(value)
                except ValueError:
                    param_value = value
                qb.filter(f"{column} {operator} $1", param_value)

        # Add user filters (override preset if needed)
        if args.filters:
            for filter_expr in args.filters:
                # Parse filter expression (e.g., "per < 15" or "pbr < 1.0")
                try:
                    # Simple parsing for now - can be enhanced later
                    if '<' in filter_expr or '>' in filter_expr or '=' in filter_expr:
                        # Add filter with automatic parameter handling
                        parts = filter_expr.split()
                        if len(parts) == 3:
                            column, operator, value = parts
                            try:
                                # Try to convert value to float
                                param_value = float(value)
                            except ValueError:
                                # Keep as string
                                param_value = value

                            qb.filter(f"{column} {operator} $1", param_value)
                        else:
                            # Complex expression - pass through as-is
                            qb.filter(filter_expr)
                    else:
                        formatter.print_warning(
                            f"Invalid filter format: {filter_expr}\n"
                            f"Expected format: 'column operator value' (e.g., 'f.per < 15')"
                        )
                        return 1

                except Exception as e:
                    formatter.print_error(f"Failed to parse filter '{filter_expr}': {e}")
                    return 1

        # Add sorting (preset sorts first, then user-specified)
        # Apply preset sorts first
        for column, order in preset_sort:
            qb.order_by(column, order)

        # Add user-specified sorts (override or extend preset)
        if args.sort_by:
            for sort_spec in args.sort_by:
                # Parse sort specification: "column" or "column:asc" or "column:desc"
                if ':' in sort_spec:
                    column, order_str = sort_spec.split(':', 1)
                    order = SortOrder.ASC if order_str.lower() == 'asc' else SortOrder.DESC
                else:
                    # Use default order from --order flag
                    column = sort_spec
                    order = SortOrder.DESC if args.order.lower() == 'desc' else SortOrder.ASC
                qb.order_by(column, order)

        # Add limit
        if args.top:
            qb.top(args.top)

        # Build and execute query
        query, params = qb.build()

        # Execute query with timeout
        try:
            rows = await db.fetch(query, *params, timeout=30.0)
        except asyncio.TimeoutError:
            formatter.print_error("Query timeout (30s). Try reducing --top or simplifying filters.")
            return 1
        except Exception as e:
            formatter.print_error(f"Query execution failed: {e}")
            return 1

        # Handle no results
        if not rows:
            formatter.print_warning("No results found matching your criteria.")
            return 0

        # Export to CSV if requested
        if args.csv:
            try:
                columns = args.columns if args.columns else None
                formatter.export_csv(rows, args.csv, columns=columns)
            except Exception as e:
                formatter.print_error(f"CSV export failed: {e}")
                return 1

        # Export to JSON if requested
        if args.json:
            try:
                columns = args.columns if args.columns else None
                pretty = not args.json_compact
                formatter.export_json(rows, args.json, columns=columns, pretty=pretty)
            except Exception as e:
                formatter.print_error(f"JSON export failed: {e}")
                return 1

        # Show summary if requested
        if args.summary:
            formatter.print_summary(rows, title="Query Results Summary")
            print()

        # Display results
        if not (args.csv or args.json) or args.summary:  # Show table unless only export
            columns = args.columns if args.columns else None
            max_rows = args.top if args.top and args.top <= 100 else 100

            title = f"{args.region} Stocks Query Results"
            if args.with_fundamentals:
                title += " (with Fundamentals)"
            if args.with_technicals:
                title += " (with Technicals)"

            formatter.print_table(
                rows,
                title=title,
                columns=columns,
                max_rows=max_rows
            )

        return 0

    except ConnectionError as e:
        formatter.print_error(f"Database connection failed: {e}")
        return 1

    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Disconnect from database
        await db.disconnect()


def add_query_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add query command arguments to argument parser.

    Args:
        parser: Argument parser to add arguments to
    """
    parser.add_argument(
        '--region',
        type=str,
        default='KR',
        choices=['KR', 'US'],
        help='Market region (default: KR)'
    )

    parser.add_argument(
        '--preset',
        type=str,
        choices=list(FILTER_PRESETS.keys()),
        help='Apply a preset filter strategy. '
             'Available: value-stocks, growth-stocks, dividend-stocks, '
             'momentum-stocks, undervalued-quality'
    )

    parser.add_argument(
        '--filter',
        dest='filters',
        action='append',
        help='Filter expression (e.g., "f.per < 15"). Can be used multiple times. '
             'Additional filters when using --preset will be added on top of preset filters.'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=50,
        help='Maximum number of results (default: 50)'
    )

    parser.add_argument(
        '--sort-by',
        action='append',
        type=str,
        dest='sort_by',
        help='Column to sort by. Can be used multiple times for multi-column sorting. '
             'Format: "column" or "column:asc" or "column:desc" '
             '(e.g., "f.per:asc", "f.pbr:asc")'
    )

    parser.add_argument(
        '--order',
        type=str,
        default='desc',
        choices=['asc', 'desc'],
        help='Sort order (default: desc)'
    )

    parser.add_argument(
        '--columns',
        nargs='+',
        help='Columns to display (space-separated list)'
    )

    parser.add_argument(
        '--with-fundamentals',
        action='store_true',
        help='Include fundamental data (PER, PBR, market cap, etc.)'
    )

    parser.add_argument(
        '--with-technicals',
        action='store_true',
        help='Include technical indicators (MA, RSI, MACD, etc.)'
    )

    parser.add_argument(
        '--with-details',
        action='store_true',
        help='Include sector and industry information'
    )

    parser.add_argument(
        '--csv',
        type=str,
        help='Export results to CSV file (UTF-8-BOM encoding for Excel)'
    )

    parser.add_argument(
        '--json',
        type=str,
        help='Export results to JSON file'
    )

    parser.add_argument(
        '--json-compact',
        action='store_true',
        help='Export JSON in compact format (no indentation)'
    )

    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show query execution summary'
    )


def run_query_sync(args: argparse.Namespace) -> int:
    """
    Synchronous wrapper for query_command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    return asyncio.run(query_command(args))


if __name__ == '__main__':
    # Standalone testing
    parser = argparse.ArgumentParser(description='Stock query command')
    add_query_arguments(parser)
    args = parser.parse_args()
    sys.exit(run_query_sync(args))
