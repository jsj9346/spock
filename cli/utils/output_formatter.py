"""
Output Formatter for Quant Platform CLI

Provides beautiful terminal output using Rich library with:
- Formatted tables
- Progress bars
- Success/error messages
- JSON output mode
- Colored console output

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text
from rich import box

# Global console instance
console = Console()


class OutputFormatter:
    """Format and display CLI output"""

    def __init__(self, output_format: str = 'table', color_enabled: bool = True):
        """
        Initialize output formatter

        Args:
            output_format: Output format (table, json, csv)
            color_enabled: Enable colored output
        """
        self.output_format = output_format
        self.console = Console(color_system='auto' if color_enabled else None)

    def print_table(self, data: List[Dict[str, Any]], title: Optional[str] = None,
                    columns: Optional[List[str]] = None):
        """
        Print data as formatted table

        Args:
            data: List of dictionaries
            title: Optional table title
            columns: Optional column order (defaults to first row keys)
        """
        if self.output_format == 'json':
            self.print_json(data)
            return

        if not data:
            self.print_warning("No data to display")
            return

        # Create table
        table = Table(
            title=title,
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )

        # Determine columns
        if columns is None:
            columns = list(data[0].keys())

        # Add columns
        for col in columns:
            table.add_column(col.replace('_', ' ').title(), style="white")

        # Add rows
        for row in data:
            table.add_row(*[self._format_value(row.get(col)) for col in columns])

        self.console.print(table)

    def print_key_value(self, data: Dict[str, Any], title: Optional[str] = None):
        """
        Print key-value pairs

        Args:
            data: Dictionary of key-value pairs
            title: Optional title
        """
        if self.output_format == 'json':
            self.print_json(data)
            return

        # Create table
        table = Table(
            title=title,
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2)
        )

        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for key, value in data.items():
            table.add_row(
                key.replace('_', ' ').title(),
                self._format_value(value)
            )

        self.console.print(table)

    def print_success(self, message: str):
        """
        Print success message

        Args:
            message: Success message
        """
        if self.output_format == 'json':
            self.print_json({"status": "success", "message": message})
        else:
            self.console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str, details: Optional[str] = None):
        """
        Print error message

        Args:
            message: Error message
            details: Optional error details
        """
        if self.output_format == 'json':
            error_data = {"status": "error", "message": message}
            if details:
                error_data["details"] = details
            self.print_json(error_data)
        else:
            self.console.print(f"[red]✗[/red] {message}", style="bold red")
            if details:
                self.console.print(f"  {details}", style="dim")

    def print_warning(self, message: str):
        """
        Print warning message

        Args:
            message: Warning message
        """
        if self.output_format == 'json':
            self.print_json({"status": "warning", "message": message})
        else:
            self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str):
        """
        Print info message

        Args:
            message: Info message
        """
        if self.output_format == 'json':
            self.print_json({"status": "info", "message": message})
        else:
            self.console.print(f"[blue]ℹ[/blue] {message}")

    def print_json(self, data: Any):
        """
        Print data as JSON

        Args:
            data: Data to print as JSON
        """
        print(json.dumps(data, indent=2, default=self._json_serializer))

    def print_panel(self, content: str, title: Optional[str] = None, style: str = "cyan"):
        """
        Print content in a panel

        Args:
            content: Panel content
            title: Optional panel title
            style: Panel style
        """
        if self.output_format == 'json':
            self.print_json({"title": title, "content": content})
        else:
            panel = Panel(
                content,
                title=title,
                border_style=style,
                padding=(1, 2)
            )
            self.console.print(panel)

    def create_progress(self, description: str = "Processing...") -> Progress:
        """
        Create progress bar

        Args:
            description: Progress description

        Returns:
            Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )

    def _format_value(self, value: Any) -> str:
        """
        Format value for display

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return "[dim]N/A[/dim]"
        elif isinstance(value, bool):
            return "[green]Yes[/green]" if value else "[red]No[/red]"
        elif isinstance(value, (int, float, Decimal)):
            if isinstance(value, float) or isinstance(value, Decimal):
                return f"{value:.4f}"
            return str(value)
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        else:
            return str(value)

    def _json_serializer(self, obj: Any) -> Any:
        """
        JSON serializer for non-standard types

        Args:
            obj: Object to serialize

        Returns:
            Serialized value
        """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return str(obj)


# Convenience functions
def print_success(message: str):
    """Print success message"""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str, details: Optional[str] = None):
    """Print error message"""
    console.print(f"[red]✗[/red] {message}", style="bold red")
    if details:
        console.print(f"  {details}", style="dim")


def print_warning(message: str):
    """Print warning message"""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """Print info message"""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_panel(content: str, title: Optional[str] = None, style: str = "cyan"):
    """Print content in a panel"""
    panel = Panel(
        content,
        title=title,
        border_style=style,
        padding=(1, 2)
    )
    console.print(panel)


def print_key_value(data: Dict[str, Any], title: Optional[str] = None):
    """Print key-value pairs"""
    formatter = OutputFormatter()
    formatter.print_key_value(data, title)
