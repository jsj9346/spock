"""
Query result formatter for Quant Platform CLI.

Provides Rich-based formatted output for query results
with support for tables, lists, and CSV export.
"""

from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
import csv
import json
from datetime import datetime, date
from decimal import Decimal
import asyncpg


class QueryFormatter:
    """
    Rich-based formatter for query results with Korean UTF-8 support.

    Features:
    - Beautiful terminal tables with borders and colors
    - Automatic column width optimization
    - Korean text rendering support
    - CSV export with UTF-8-BOM encoding (Excel compatible)
    - JSON export with pretty formatting
    - Number formatting (commas, decimal places)

    Usage:
        formatter = QueryFormatter()
        formatter.print_table(rows, title="Query Results")
        formatter.export_csv(rows, "output.csv")
        formatter.export_json(rows, "output.json")
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize formatter with Rich console.

        Args:
            console: Optional Rich Console instance. Creates new one if not provided.
        """
        self.console = console or Console()

    def print_table(
        self,
        rows: List[asyncpg.Record],
        title: Optional[str] = None,
        columns: Optional[List[str]] = None,
        show_header: bool = True,
        max_rows: Optional[int] = None
    ) -> None:
        """
        Print query results as formatted table.

        Args:
            rows: List of database records
            title: Optional table title
            columns: Optional list of column names to display (default: all)
            show_header: Whether to show column headers
            max_rows: Maximum rows to display (default: all)
        """
        if not rows:
            self.console.print("[yellow]No results found[/yellow]")
            return

        # Determine columns to display
        if columns:
            display_columns = columns
        else:
            display_columns = list(rows[0].keys())

        # Create Rich table
        table = Table(
            title=title,
            show_header=show_header,
            header_style="bold cyan",
            border_style="bright_blue",
            expand=False
        )

        # Add columns with appropriate justification
        for col in display_columns:
            # Right-justify numbers, left-justify text
            sample_value = rows[0][col]
            justify = "right" if isinstance(sample_value, (int, float)) else "left"
            table.add_column(col, justify=justify, style="white")

        # Add rows
        display_rows = rows[:max_rows] if max_rows else rows
        for row in display_rows:
            formatted_row = [self._format_value(row[col]) for col in display_columns]
            table.add_row(*formatted_row)

        # Print table
        self.console.print(table)

        # Show row count info
        if max_rows and len(rows) > max_rows:
            self.console.print(
                f"\n[dim]Showing {max_rows} of {len(rows)} rows. "
                f"Use --limit to adjust.[/dim]"
            )
        else:
            self.console.print(f"\n[dim]Total: {len(rows)} rows[/dim]")

    def print_summary(
        self,
        rows: List[asyncpg.Record],
        title: str = "Query Summary"
    ) -> None:
        """
        Print query execution summary with statistics.

        Args:
            rows: List of database records
            title: Summary panel title
        """
        if not rows:
            self.console.print("[yellow]No results to summarize[/yellow]")
            return

        summary_text = Text()
        summary_text.append(f"Total Rows: ", style="bold")
        summary_text.append(f"{len(rows):,}\n", style="cyan")

        # Get column names as list
        column_names = list(rows[0].keys())

        summary_text.append(f"Columns: ", style="bold")
        summary_text.append(f"{len(column_names)}\n", style="cyan")

        # Column names
        summary_text.append(f"Fields: ", style="bold")
        summary_text.append(", ".join(column_names), style="dim")

        panel = Panel(
            summary_text,
            title=f"[bold]{title}[/bold]",
            border_style="green",
            expand=False
        )
        self.console.print(panel)

    def export_csv(
        self,
        rows: List[asyncpg.Record],
        filepath: str,
        columns: Optional[List[str]] = None
    ) -> None:
        """
        Export query results to CSV file with UTF-8-BOM encoding (Excel compatible).

        Args:
            rows: List of database records
            filepath: Output file path
            columns: Optional list of column names to export (default: all)

        Raises:
            ValueError: If no rows to export
            IOError: If file write fails
        """
        if not rows:
            raise ValueError("No rows to export")

        # Determine columns
        if columns:
            export_columns = columns
        else:
            export_columns = list(rows[0].keys())

        try:
            # Write CSV with UTF-8-BOM for Excel compatibility
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=export_columns)
                writer.writeheader()

                for row in rows:
                    # Convert Record to dict and format values
                    row_dict = {
                        col: self._format_csv_value(row[col])
                        for col in export_columns
                    }
                    writer.writerow(row_dict)

            self.console.print(
                f"[green]✓[/green] Exported {len(rows):,} rows to [cyan]{filepath}[/cyan]"
            )

        except IOError as e:
            self.console.print(f"[red]✗[/red] Failed to write CSV: {e}")
            raise

    def export_json(
        self,
        rows: List[asyncpg.Record],
        filepath: str,
        columns: Optional[List[str]] = None,
        pretty: bool = True
    ) -> None:
        """
        Export query results to JSON file.

        Args:
            rows: List of database records
            filepath: Output file path
            columns: Optional list of column names to export (default: all)
            pretty: Whether to format JSON with indentation (default: True)

        Raises:
            ValueError: If no rows to export
            IOError: If file write fails
        """
        if not rows:
            raise ValueError("No rows to export")

        # Determine columns
        if columns:
            export_columns = columns
        else:
            export_columns = list(rows[0].keys())

        try:
            # Convert rows to JSON-serializable format
            data = []
            for row in rows:
                row_dict = {}
                for col in export_columns:
                    value = row[col]
                    # Convert non-JSON-serializable types
                    if isinstance(value, (datetime, date)):
                        row_dict[col] = value.isoformat()
                    elif isinstance(value, Decimal):
                        row_dict[col] = float(value)
                    elif value is None:
                        row_dict[col] = None
                    else:
                        row_dict[col] = value
                data.append(row_dict)

            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    json.dump(data, f, ensure_ascii=False)

            self.console.print(
                f"[green]✓[/green] Exported {len(rows):,} rows to [cyan]{filepath}[/cyan]"
            )

        except IOError as e:
            self.console.print(f"[red]✗[/red] Failed to write JSON: {e}")
            raise

    def print_error(self, message: str, title: str = "Error") -> None:
        """
        Print error message in formatted panel.

        Args:
            message: Error message
            title: Panel title
        """
        panel = Panel(
            Text(message, style="red"),
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            expand=False
        )
        self.console.print(panel)

    def print_success(self, message: str, title: str = "Success") -> None:
        """
        Print success message in formatted panel.

        Args:
            message: Success message
            title: Panel title
        """
        panel = Panel(
            Text(message, style="green"),
            title=f"[bold green]{title}[/bold green]",
            border_style="green",
            expand=False
        )
        self.console.print(panel)

    def print_warning(self, message: str, title: str = "Warning") -> None:
        """
        Print warning message in formatted panel.

        Args:
            message: Warning message
            title: Panel title
        """
        panel = Panel(
            Text(message, style="yellow"),
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="yellow",
            expand=False
        )
        self.console.print(panel)

    def _format_value(self, value: Any) -> str:
        """
        Format value for terminal display.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return "[dim]-[/dim]"
        elif isinstance(value, float):
            # Format floats with 2 decimal places
            return f"{value:,.2f}"
        elif isinstance(value, int):
            # Format integers with comma separators
            return f"{value:,}"
        elif isinstance(value, (datetime, )):
            # Format dates
            return value.strftime("%Y-%m-%d")
        else:
            # Return as string
            return str(value)

    def _format_csv_value(self, value: Any) -> str:
        """
        Format value for CSV export (plain text, no formatting codes).

        Args:
            value: Value to format

        Returns:
            Plain text string
        """
        if value is None:
            return ""
        elif isinstance(value, float):
            return f"{value:.6f}"  # Full precision for CSV
        elif isinstance(value, (datetime, )):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return str(value)


# Convenience singleton instance
formatter = QueryFormatter()
