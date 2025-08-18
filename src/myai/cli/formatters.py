"""
Output formatters for MyAI CLI.

This module provides various output formatting options including tables,
JSON, and other formats for CLI command results.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table


class OutputFormatter(ABC):
    """Base class for output formatters."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize formatter with optional console."""
        self.console = console or Console()

    @abstractmethod
    def format(self, data: Any, **kwargs) -> None:
        """Format and output data."""
        pass


class TableFormatter(OutputFormatter):
    """Format output as Rich tables."""

    def format(
        self, data: Union[List[Dict], Dict], title: Optional[str] = None, columns: Optional[List[str]] = None, **_kwargs
    ) -> None:
        """Format data as a table."""
        if not data:
            self.console.print("[dim]No data to display[/dim]")
            return

        # Convert single dict to list
        if isinstance(data, dict):
            data = [data]

        # Create table
        table = Table(title=title, show_header=True, header_style="bold magenta")

        # Determine columns
        if not columns and data:
            columns = list(data[0].keys())

        # Add columns to table
        for col in columns or []:
            table.add_column(col, style="cyan", no_wrap=True)

        # Add rows
        for row in data:
            values = [str(row.get(col, "")) for col in columns or []]
            table.add_row(*values)

        self.console.print(table)


class JSONFormatter(OutputFormatter):
    """Format output as JSON."""

    def format(self, data: Any, pretty: bool = True, **_kwargs) -> None:  # noqa: FBT001
        """Format data as JSON."""
        if pretty:
            # Use Rich's JSON formatter for syntax highlighting
            json_obj = JSON(json.dumps(data, indent=2, default=str))
            self.console.print(json_obj)
        else:
            # Plain JSON output
            json_str = json.dumps(data, default=str)
            self.console.print(json_str)


class PanelFormatter(OutputFormatter):
    """Format output as Rich panels."""

    def format(
        self,
        data: Any,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        border_style: str = "blue",
        **_kwargs,
    ) -> None:
        """Format data as a panel."""
        content = str(data) if not isinstance(data, str) else data

        panel = Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style=border_style,
        )

        self.console.print(panel)


def get_formatter(format_type: str, console: Optional[Console] = None) -> OutputFormatter:
    """Get formatter instance by type."""
    formatters: Dict[str, Type[OutputFormatter]] = {
        "table": TableFormatter,
        "json": JSONFormatter,
        "panel": PanelFormatter,
    }

    formatter_class = formatters.get(format_type.lower(), TableFormatter)
    return formatter_class(console)
