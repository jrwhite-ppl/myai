"""
Tests for the vertical formatter.
"""

import unittest
from io import StringIO

from rich.console import Console

from myai.cli.formatters import VerticalFormatter


class TestVerticalFormatter(unittest.TestCase):
    """Test vertical formatter functionality."""

    def setUp(self):
        """Set up test console."""
        self.output = StringIO()
        # Disable color and markup for testing
        self.console = Console(file=self.output, force_terminal=False, width=80, no_color=True, legacy_windows=True)
        self.formatter = VerticalFormatter(self.console)

    def test_format_simple_dict(self):
        """Test formatting a simple dictionary."""
        data = {
            "name": "test",
            "version": "1.0.0",
            "enabled": True,
        }

        self.formatter.format(data, title="Test Config")
        output = self.output.getvalue()

        self.assertIn("Test Config", output)
        self.assertIn("name:", output)
        self.assertIn("test", output)
        self.assertIn("version:", output)
        self.assertIn("1.0.0", output)
        self.assertIn("enabled:", output)
        self.assertIn("True", output)

    def test_format_nested_dict(self):
        """Test formatting nested dictionaries."""
        data = {
            "settings": {
                "debug": False,
                "cache": {
                    "enabled": True,
                    "ttl": 3600,
                },
            }
        }

        self.formatter.format(data)
        output = self.output.getvalue()

        self.assertIn("settings:", output)
        self.assertIn("debug:", output)
        self.assertIn("False", output)
        self.assertIn("cache:", output)
        self.assertIn("enabled:", output)
        self.assertIn("True", output)
        self.assertIn("ttl:", output)
        self.assertIn("3600", output)

    def test_format_with_lists(self):
        """Test formatting dictionaries with lists."""
        data = {
            "agents": ["lead-developer", "data-analyst"],
            "config": {"categories": ["engineering", "business", "security"]},
        }

        self.formatter.format(data)
        output = self.output.getvalue()

        self.assertIn("agents:", output)
        self.assertIn("lead-developer", output)
        self.assertIn("data-analyst", output)
        self.assertIn("categories:", output)
        self.assertIn("engineering", output)
        self.assertIn("business", output)

    def test_format_empty_data(self):
        """Test formatting empty data."""
        self.formatter.format({})
        output = self.output.getvalue()

        self.assertIn("No data to display", output)

    def test_format_complex_nested_structure(self):
        """Test formatting complex nested structure."""
        data = {
            "metadata": {"created": "2025-08-19", "version": "1.0.0"},
            "tools": {
                "claude": {
                    "enabled": True,
                    "settings": {"auto_sync": True, "models": ["claude-3-opus", "claude-3-sonnet"]},
                },
                "cursor": {"enabled": False},
            },
        }

        self.formatter.format(data, title="Complex Config")
        output = self.output.getvalue()

        # Check structure is preserved
        self.assertIn("metadata:", output)
        self.assertIn("tools:", output)
        self.assertIn("claude:", output)
        self.assertIn("cursor:", output)

        # Check nested values
        self.assertIn("auto_sync:", output)
        self.assertIn("models:", output)
        self.assertIn("claude-3-opus", output)


if __name__ == "__main__":
    unittest.main()
