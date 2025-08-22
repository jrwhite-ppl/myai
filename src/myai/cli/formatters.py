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
from rich.syntax import Syntax
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
        table = Table(title=title, show_header=True, header_style="bold magenta", expand=True)

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


class VerticalFormatter(OutputFormatter):
    """Format output vertically with dynamic sizing."""

    def format(
        self,
        data: Union[Dict, List],
        title: Optional[str] = None,
        **_kwargs,
    ) -> None:
        """Format data vertically with proper nesting."""
        if not data:
            self.console.print("[dim]No data to display[/dim]")
            return

        if title:
            self.console.print(f"\n[bold magenta]{title}[/bold magenta]\n")

        if isinstance(data, dict):
            self._format_dict(data)
        else:
            # For lists, format as JSON
            json_obj = JSON(json.dumps(data, indent=2, default=str))
            self.console.print(json_obj)

    def _format_dict(self, data: Dict[str, Any], indent: int = 0) -> None:
        """Format dictionary with proper indentation and dynamic width."""
        for key, value in data.items():
            # Create formatted key
            key_str = " " * indent + f"[cyan]{key}:[/cyan]"

            if isinstance(value, dict):
                # For nested dicts, print key and recurse
                self.console.print(key_str)
                self._format_dict(value, indent + 2)
            elif isinstance(value, list):
                # For lists, use JSON formatting
                self.console.print(key_str)
                if value and all(isinstance(item, (str, int, float, bool)) for item in value):
                    # Simple list - print inline
                    list_str = " " * (indent + 2) + ", ".join(str(item) for item in value)
                    self.console.print(f"[yellow]{list_str}[/yellow]")
                else:
                    # Complex list - use JSON
                    json_str = json.dumps(value, indent=2, default=str)
                    indented_json = "\n".join(" " * (indent + 2) + line for line in json_str.split("\n"))
                    self.console.print(Syntax(indented_json, "json", theme="monokai", line_numbers=False))
            else:
                # For simple values, print on same line
                value_str = str(value)
                self.console.print(f"{key_str} [yellow]{value_str}[/yellow]")


def get_formatter(format_type: str, console: Optional[Console] = None) -> OutputFormatter:
    """Get formatter instance by type."""
    formatters: Dict[str, Type[OutputFormatter]] = {
        "table": TableFormatter,
        "json": JSONFormatter,
        "panel": PanelFormatter,
        "vertical": VerticalFormatter,
    }

    formatter_class = formatters.get(format_type.lower(), TableFormatter)
    return formatter_class(console)
