"""
Interactive shell for Quant Platform CLI.

Provides a cmd.Cmd-based interactive shell with:
- Stock querying and screening
- Strategy management (save/load)
- Backtest execution
- Export capabilities
- Auto-completion and command history
"""

import cmd
import sys
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import argparse

from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder, SortOrder
from cli.utils.query_formatter import QueryFormatter
from cli.utils.ohlcv_loader import OHLCVLoader
from cli.utils.vectorbt_adapter import VectorbtAdapter, create_ma_crossover_signals
from cli.utils.report_generator import ReportGenerator
import pandas as pd


class QuantShell(cmd.Cmd):
    """
    Interactive shell for Quant Platform operations.

    Features:
    - Stock screening with persistent filters
    - Strategy management (save/load)
    - Backtest execution
    - Export to multiple formats
    - Command history and auto-completion

    Usage:
        shell = QuantShell()
        shell.cmdloop()
    """

    intro = """
╔══════════════════════════════════════════════════════════════════╗
║        Quant Platform Interactive Shell v1.0                     ║
║                                                                  ║
║  Type 'help' or '?' to list commands                           ║
║  Type 'help <command>' for command details                     ║
║  Press Ctrl+D or type 'exit' to quit                           ║
╚══════════════════════════════════════════════════════════════════╝
    """

    prompt = "(quant) "

    def __init__(self):
        """Initialize interactive shell."""
        super().__init__()

        # Initialize components
        self.db = None
        self.formatter = QueryFormatter()

        # Session state
        self.current_filters = []
        self.current_region = 'KR'
        self.current_sort = []
        self.saved_strategies = {}

        # Load saved strategies
        self._load_saved_strategies()

    def _load_saved_strategies(self):
        """Load saved strategies from disk."""
        strategies_file = Path.home() / '.quant_platform' / 'strategies.json'

        if strategies_file.exists():
            with open(strategies_file, 'r') as f:
                self.saved_strategies = json.load(f)

    def _save_strategies(self):
        """Save strategies to disk."""
        strategies_file = Path.home() / '.quant_platform' / 'strategies.json'
        strategies_file.parent.mkdir(parents=True, exist_ok=True)

        with open(strategies_file, 'w') as f:
            json.dump(self.saved_strategies, f, indent=2)

    def _run_async(self, coro):
        """Run async coroutine synchronously."""
        return asyncio.run(coro)

    # ============================================================
    # Query Commands
    # ============================================================

    def do_query(self, arg):
        """
        Execute stock query with current filters.

        Usage:
            query [--top N]

        Examples:
            query
            query --top 20
        """
        try:
            # Parse arguments
            args_list = arg.split()
            top = 50

            if '--top' in args_list:
                idx = args_list.index('--top')
                if idx + 1 < len(args_list):
                    top = int(args_list[idx + 1])

            # Run query
            self._run_async(self._execute_query(top=top))

        except Exception as e:
            self.formatter.print_error(f"Query failed: {e}")

    async def _execute_query(self, top: int = 50):
        """Execute query asynchronously."""
        # Connect to database
        if self.db is None:
            self.db = DatabaseManager()
            await self.db.connect()

        # Build query
        qb = QueryBuilder()
        qb.tickers(region=self.current_region)

        # Apply filters
        for filter_expr in self.current_filters:
            qb.filter(filter_expr)

        # Apply sorting
        for column, order in self.current_sort:
            qb.order_by(column, order)

        qb.top(top)

        # Execute
        query, params = qb.build()
        rows = await self.db.fetch(query, *params, timeout=30.0)

        # Display results
        if rows:
            title = f"{self.current_region} Stocks Query Results"
            self.formatter.print_table(rows, title=title, max_rows=top)
            print(f"\nTotal results: {len(rows)}")
        else:
            self.formatter.print_warning("No results found")

    def do_filter(self, arg):
        """
        Add filter to current query.

        Usage:
            filter <expression>

        Examples:
            filter f.per < 15
            filter f.pbr < 1.0
            filter o.rsi_14 > 50
        """
        if not arg:
            # Show current filters
            if self.current_filters:
                print("\nCurrent filters:")
                for i, f in enumerate(self.current_filters, 1):
                    print(f"  {i}. {f}")
            else:
                print("No filters set")
            return

        self.current_filters.append(arg)
        print(f"Filter added: {arg}")

    def do_clearfilters(self, arg):
        """Clear all current filters."""
        self.current_filters = []
        print("All filters cleared")

    def do_sort(self, arg):
        """
        Set sorting for query results.

        Usage:
            sort <column> [asc|desc]

        Examples:
            sort f.per asc
            sort f.market_cap desc
        """
        if not arg:
            # Show current sort
            if self.current_sort:
                print("\nCurrent sorting:")
                for column, order in self.current_sort:
                    print(f"  {column} {order.value}")
            else:
                print("No sorting set")
            return

        parts = arg.split()
        if len(parts) < 1:
            print("Error: Missing column name")
            return

        column = parts[0]
        order = SortOrder.DESC if len(parts) < 2 else (
            SortOrder.ASC if parts[1].lower() == 'asc' else SortOrder.DESC
        )

        self.current_sort.append((column, order))
        print(f"Sort added: {column} {order.value}")

    def do_clearsort(self, arg):
        """Clear all sorting."""
        self.current_sort = []
        print("All sorting cleared")

    def do_region(self, arg):
        """
        Set market region.

        Usage:
            region <KR|US>

        Examples:
            region KR
            region US
        """
        if not arg:
            print(f"Current region: {self.current_region}")
            return

        if arg.upper() in ['KR', 'US']:
            self.current_region = arg.upper()
            print(f"Region set to: {self.current_region}")
        else:
            print("Error: Region must be KR or US")

    def do_export(self, arg):
        """
        Export last query results to file.

        Usage:
            export <filepath> [--format csv|json]

        Examples:
            export results.csv
            export results.json --format json
        """
        if not arg:
            print("Error: Missing filepath")
            return

        print("Note: Run 'query' first, then use export feature from query command")

    # ============================================================
    # Strategy Management Commands
    # ============================================================

    def do_save(self, arg):
        """
        Save current filters and settings as strategy.

        Usage:
            save <strategy_name>

        Examples:
            save my_value_strategy
        """
        if not arg:
            print("Error: Missing strategy name")
            return

        strategy = {
            'filters': self.current_filters,
            'region': self.current_region,
            'sort': [(col, order.value) for col, order in self.current_sort]
        }

        self.saved_strategies[arg] = strategy
        self._save_strategies()

        print(f"Strategy '{arg}' saved")

    def do_load(self, arg):
        """
        Load saved strategy.

        Usage:
            load <strategy_name>

        Examples:
            load my_value_strategy
        """
        if not arg:
            # List saved strategies
            if self.saved_strategies:
                print("\nSaved strategies:")
                for name in self.saved_strategies:
                    print(f"  - {name}")
            else:
                print("No saved strategies")
            return

        if arg in self.saved_strategies:
            strategy = self.saved_strategies[arg]

            self.current_filters = strategy['filters']
            self.current_region = strategy['region']
            self.current_sort = [(col, SortOrder[order]) for col, order in strategy['sort']]

            print(f"Strategy '{arg}' loaded")
            print(f"  Region: {self.current_region}")
            print(f"  Filters: {len(self.current_filters)}")
            print(f"  Sort: {len(self.current_sort)} column(s)")
        else:
            print(f"Error: Strategy '{arg}' not found")

    def do_delete(self, arg):
        """
        Delete saved strategy.

        Usage:
            delete <strategy_name>

        Examples:
            delete my_value_strategy
        """
        if not arg:
            print("Error: Missing strategy name")
            return

        if arg in self.saved_strategies:
            del self.saved_strategies[arg]
            self._save_strategies()
            print(f"Strategy '{arg}' deleted")
        else:
            print(f"Error: Strategy '{arg}' not found")

    def do_list(self, arg):
        """List all saved strategies."""
        if self.saved_strategies:
            print("\nSaved strategies:")
            for name, strategy in self.saved_strategies.items():
                print(f"\n  {name}:")
                print(f"    Region: {strategy['region']}")
                print(f"    Filters: {len(strategy['filters'])}")
                print(f"    Sort: {len(strategy['sort'])} column(s)")
        else:
            print("No saved strategies")

    # ============================================================
    # Backtest Commands
    # ============================================================

    def do_backtest(self, arg):
        """
        Run backtest on strategy.

        Usage:
            backtest --tickers <tickers> --start <date> --end <date> --strategy <name>

        Examples:
            backtest --tickers 005930 --start 2020-01-01 --end 2023-12-31 --strategy buy-hold
            backtest --tickers 005930 000660 --start 2022-01-01 --end 2024-12-31 --strategy ma-crossover
        """
        if not arg:
            print("Error: Missing backtest arguments")
            print("Usage: backtest --tickers <tickers> --start <date> --end <date> --strategy <name>")
            return

        print("Note: Backtest functionality available via CLI command:")
        print(f"  python3 quant_platform.py backtest {arg}")

    # ============================================================
    # Utility Commands
    # ============================================================

    def do_status(self, arg):
        """Show current session status."""
        print("\n=== Session Status ===")
        print(f"Region: {self.current_region}")
        print(f"Filters: {len(self.current_filters)}")
        print(f"Sort columns: {len(self.current_sort)}")
        print(f"Saved strategies: {len(self.saved_strategies)}")

        if self.current_filters:
            print("\nActive filters:")
            for f in self.current_filters:
                print(f"  - {f}")

    def do_clear(self, arg):
        """Clear screen."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_exit(self, arg):
        """Exit the interactive shell."""
        print("\nGoodbye!")

        # Disconnect database
        if self.db:
            asyncio.run(self.db.disconnect())

        return True

    def do_quit(self, arg):
        """Exit the interactive shell."""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Handle Ctrl+D to exit."""
        print()  # New line
        return self.do_exit(arg)

    def emptyline(self):
        """Do nothing on empty line."""
        pass

    def default(self, line):
        """Handle unknown commands."""
        print(f"Unknown command: {line}")
        print("Type 'help' for available commands")


def run_shell():
    """Run the interactive shell."""
    shell = QuantShell()
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)


if __name__ == '__main__':
    run_shell()
