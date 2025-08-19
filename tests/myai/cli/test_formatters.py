"""
Tests for CLI output formatters.
"""

from io import StringIO

import pytest
from rich.console import Console

from myai.cli.formatters import (
    JSONFormatter,
    OutputFormatter,
    PanelFormatter,
    TableFormatter,
    get_formatter,
)


class MockFormatter(OutputFormatter):
    """Mock formatter for testing base class."""

    def format(self, data, **_kwargs):
        """Mock format implementation."""
        self.console.print(f"Mock: {data}")


class TestOutputFormatter:
    """Test cases for base OutputFormatter class."""

    def test_formatter_init_default_console(self):
        """Test formatter initialization with default console."""
        formatter = MockFormatter()
        assert formatter.console is not None
        assert isinstance(formatter.console, Console)

    def test_formatter_init_custom_console(self):
        """Test formatter initialization with custom console."""
        custom_console = Console()
        formatter = MockFormatter(console=custom_console)
        assert formatter.console is custom_console

    def test_abstract_base_class(self):
        """Test that OutputFormatter is abstract."""
        with pytest.raises(TypeError):
            OutputFormatter()


class TestTableFormatter:
    """Test cases for TableFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console(file=StringIO(), width=100)
        self.formatter = TableFormatter(console=self.console)

    def test_format_empty_data(self):
        """Test formatting empty data."""
        self.formatter.format([])
        output = self.console.file.getvalue()
        assert "No data to display" in output

    def test_format_single_dict(self):
        """Test formatting a single dictionary."""
        data = {"name": "test", "value": 123}
        self.formatter.format(data)
        output = self.console.file.getvalue()
        assert "test" in output
        assert "123" in output

    def test_format_list_of_dicts(self):
        """Test formatting a list of dictionaries."""
        data = [{"name": "item1", "value": 100}, {"name": "item2", "value": 200}]
        self.formatter.format(data)
        output = self.console.file.getvalue()
        assert "item1" in output
        assert "item2" in output
        assert "100" in output
        assert "200" in output

    def test_format_with_title(self):
        """Test formatting with a table title."""
        data = [{"name": "test", "value": 123}]
        self.formatter.format(data, title="Test Table")
        output = self.console.file.getvalue()
        assert "Test Table" in output

    def test_format_with_custom_columns(self):
        """Test formatting with custom column specification."""
        data = [{"name": "test", "value": 123, "extra": "ignored"}]
        self.formatter.format(data, columns=["name", "value"])
        output = self.console.file.getvalue()
        assert "test" in output
        assert "123" in output
        # Extra column should not be displayed
        assert "extra" not in output or "ignored" not in output

    def test_format_missing_column_data(self):
        """Test formatting when some rows are missing column data."""
        data = [{"name": "item1", "value": 100}, {"name": "item2"}]  # Missing value
        self.formatter.format(data)
        output = self.console.file.getvalue()
        assert "item1" in output
        assert "item2" in output

    def test_format_non_dict_data(self):
        """Test formatting with non-dictionary data should raise error."""
        data = ["string1", "string2"]
        # This should fail since table formatter expects dict data
        with pytest.raises(AttributeError):
            self.formatter.format(data)


class TestJSONFormatter:
    """Test cases for JSONFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console(file=StringIO(), width=100)
        self.formatter = JSONFormatter(console=self.console)

    def test_format_pretty_json(self):
        """Test formatting as pretty JSON."""
        data = {"name": "test", "value": 123, "nested": {"key": "value"}}
        self.formatter.format(data, pretty=True)
        output = self.console.file.getvalue()

        # Should contain formatted JSON elements
        assert "test" in output
        assert "123" in output
        assert "nested" in output

    def test_format_compact_json(self):
        """Test formatting as compact JSON."""
        data = {"name": "test", "value": 123}
        self.formatter.format(data, pretty=False)
        output = self.console.file.getvalue()

        # Should contain JSON data
        assert "test" in output
        assert "123" in output

    def test_format_list_data(self):
        """Test formatting list data as JSON."""
        data = [{"item": 1}, {"item": 2}]
        self.formatter.format(data)
        output = self.console.file.getvalue()

        # Should contain array elements
        assert output.strip()  # Should have content

    def test_format_complex_data(self):
        """Test formatting complex nested data."""
        data = {"config": {"tools": ["tool1", "tool2"], "settings": {"debug": True, "timeout": 30}}}
        self.formatter.format(data)
        output = self.console.file.getvalue()

        # Should handle complex structures
        assert output.strip()  # Should have content


class TestPanelFormatter:
    """Test cases for PanelFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console(file=StringIO(), width=100)
        self.formatter = PanelFormatter(console=self.console)

    def test_format_string_content(self):
        """Test formatting string content in a panel."""
        data = "This is test content"
        self.formatter.format(data, title="Test Panel")
        output = self.console.file.getvalue()

        assert "This is test content" in output
        assert "Test Panel" in output

    def test_format_dict_content(self):
        """Test formatting dictionary content in a panel."""
        data = {"key1": "value1", "key2": "value2"}
        self.formatter.format(data, title="Data Panel")
        output = self.console.file.getvalue()

        assert "Data Panel" in output
        # Should contain key-value pairs
        assert output.strip()  # Should have content

    def test_format_with_styling(self):
        """Test formatting with custom styling."""
        data = "Styled content"
        self.formatter.format(data, title="Styled Panel", style="red")
        output = self.console.file.getvalue()

        assert "Styled content" in output
        assert "Styled Panel" in output

    def test_format_without_title(self):
        """Test formatting without a title."""
        data = "Content without title"
        self.formatter.format(data)
        output = self.console.file.getvalue()

        assert "Content without title" in output


class TestGetFormatter:
    """Test cases for get_formatter function."""

    def test_get_table_formatter(self):
        """Test getting table formatter."""
        formatter = get_formatter("table")
        assert isinstance(formatter, TableFormatter)

    def test_get_json_formatter(self):
        """Test getting JSON formatter."""
        formatter = get_formatter("json")
        assert isinstance(formatter, JSONFormatter)

    def test_get_panel_formatter(self):
        """Test getting panel formatter."""
        formatter = get_formatter("panel")
        assert isinstance(formatter, PanelFormatter)

    def test_get_formatter_case_insensitive(self):
        """Test getting formatter with case-insensitive type."""
        formatter1 = get_formatter("TABLE")
        formatter2 = get_formatter("Table")
        formatter3 = get_formatter("table")

        assert all(isinstance(f, TableFormatter) for f in [formatter1, formatter2, formatter3])

    def test_get_formatter_unknown_type(self):
        """Test getting formatter with unknown type defaults to table."""
        formatter = get_formatter("unknown")
        assert isinstance(formatter, TableFormatter)

    def test_get_formatter_with_console(self):
        """Test getting formatter with custom console."""
        custom_console = Console()
        formatter = get_formatter("table", console=custom_console)
        assert formatter.console is custom_console

    def test_get_formatter_empty_type(self):
        """Test getting formatter with empty type."""
        formatter = get_formatter("")
        assert isinstance(formatter, TableFormatter)


class TestFormatterIntegration:
    """Integration tests for formatters."""

    def test_formatter_with_agent_data(self):
        """Test formatters with agent-like data structure."""
        agent_data = [
            {"name": "test_agent", "category": "engineering", "version": "1.0.0", "enabled": True},
            {"name": "another_agent", "category": "business", "version": "2.1.0", "enabled": False},
        ]

        # Test table formatter
        console = Console(file=StringIO())
        table_formatter = TableFormatter(console=console)
        table_formatter.format(agent_data, title="Agents")
        table_output = console.file.getvalue()

        assert "test_agent" in table_output
        assert "engineering" in table_output
        assert "Agents" in table_output

        # Test JSON formatter
        console = Console(file=StringIO())
        json_formatter = JSONFormatter(console=console)
        json_formatter.format(agent_data)
        json_output = console.file.getvalue()

        assert "test_agent" in json_output
        assert "engineering" in json_output

    def test_formatter_with_config_data(self):
        """Test formatters with configuration-like data."""
        config_data = {
            "tools": {
                "claude": {"model": "sonnet", "enabled": True},
                "cursor": {"rules_path": "/path/to/rules", "enabled": False},
            },
            "paths": {"agents_dir": "/home/user/agents", "config_dir": "/home/user/.myai"},
        }

        # Test panel formatter
        console = Console(file=StringIO())
        panel_formatter = PanelFormatter(console=console)
        panel_formatter.format(config_data, title="Configuration")
        panel_output = console.file.getvalue()

        assert "Configuration" in panel_output

        # Test JSON formatter
        console = Console(file=StringIO())
        json_formatter = JSONFormatter(console=console)
        json_formatter.format(config_data)
        json_output = console.file.getvalue()

        assert "claude" in json_output
        assert "cursor" in json_output
