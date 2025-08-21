"""Tests for MyAI CLI global options."""

import json
import unittest
import unittest.mock
from unittest.mock import patch

from typer.testing import CliRunner

from myai.app import app


class TestCLIOptions(unittest.TestCase):
    """Test the global CLI options for MyAI."""

    def setUp(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_help_option(self):
        """Test that --help shows usage information."""
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("MyAI - AI Agent and Configuration Management CLI", result.stdout)
        self.assertIn("--debug", result.stdout)
        self.assertIn("--output", result.stdout)

    def test_debug_option(self):
        """Test that --debug enables debug mode."""
        result = self.runner.invoke(app, ["--debug", "version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Debug mode enabled", result.stdout)

    def test_debug_short_option(self):
        """Test that -d enables debug mode."""
        result = self.runner.invoke(app, ["-d", "version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Debug mode enabled", result.stdout)

    def test_output_json_option(self):
        """Test that --output json produces JSON output."""
        # Mock the dependencies properly
        mock_agent = unittest.mock.MagicMock()
        mock_agent.metadata.name = "test-agent"
        mock_agent.metadata.category.value = "test"

        mock_registry = unittest.mock.MagicMock()
        mock_registry.list_agents.return_value = [mock_agent]

        mock_config = unittest.mock.MagicMock()
        mock_config.agents.enabled = []
        mock_config.agents.global_enabled = []

        mock_config_manager = unittest.mock.MagicMock()
        mock_config_manager.get_config.return_value = mock_config
        mock_config_manager.get_config_path.return_value = None

        with patch("myai.agent.registry.get_agent_registry", return_value=mock_registry), patch(
            "myai.config.manager.get_config_manager", return_value=mock_config_manager
        ):
            result = self.runner.invoke(app, ["--output", "json", "status"])
            self.assertEqual(result.exit_code, 0)
            # Verify it's valid JSON
            try:
                data = json.loads(result.stdout)
                self.assertIsInstance(data, dict)
                self.assertIn("system", data)
                self.assertIn("agents", data)
            except json.JSONDecodeError as e:
                print(f"JSON Error: {e}")
                print(f"Output was: {result.stdout}")
                self.fail("Output is not valid JSON")

    def test_output_short_option(self):
        """Test that -o json produces JSON output."""
        # Mock the dependencies properly
        mock_agent = unittest.mock.MagicMock()
        mock_agent.metadata.name = "test-agent"
        mock_agent.metadata.category.value = "test"

        mock_registry = unittest.mock.MagicMock()
        mock_registry.list_agents.return_value = [mock_agent]

        mock_config = unittest.mock.MagicMock()
        mock_config.agents.enabled = []
        mock_config.agents.global_enabled = []

        mock_config_manager = unittest.mock.MagicMock()
        mock_config_manager.get_config.return_value = mock_config
        mock_config_manager.get_config_path.return_value = None

        with patch("myai.agent.registry.get_agent_registry", return_value=mock_registry), patch(
            "myai.config.manager.get_config_manager", return_value=mock_config_manager
        ):
            result = self.runner.invoke(app, ["-o", "json", "status"])
            self.assertEqual(result.exit_code, 0)
            # Verify it's valid JSON
            try:
                json.loads(result.stdout)
            except json.JSONDecodeError:
                self.fail("Output is not valid JSON")

    def test_output_table_default(self):
        """Test that table output is the default."""
        result = self.runner.invoke(app, ["version"])
        self.assertEqual(result.exit_code, 0)
        # Table output has box drawing characters
        self.assertIn("─", result.stdout)
        self.assertIn("│", result.stdout)

    def test_combined_options(self):
        """Test that multiple options can be combined."""
        result = self.runner.invoke(app, ["--debug", "--output", "json", "version", "--short"])
        self.assertEqual(result.exit_code, 0)
        # In JSON output mode with --short, we should just get the version string
        self.assertIn("0.0.1", result.stdout)

    def test_invalid_output_format(self):
        """Test that invalid output format shows error."""
        result = self.runner.invoke(app, ["--output", "xml", "status"])
        # Should still run but use default format
        self.assertEqual(result.exit_code, 0)

    def test_no_command_shows_help(self):
        """Test that running with no command shows help."""
        result = self.runner.invoke(app, [])
        # no_args_is_help=True means exit code is not 0
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.stdout)

    def test_unknown_option_shows_error(self):
        """Test that unknown options show error."""
        result = self.runner.invoke(app, ["--unknown-option"])
        self.assertNotEqual(result.exit_code, 0)
        # Error message might be in stdout or stderr
        output = result.stdout + result.stderr
        self.assertTrue("Error" in output or "Invalid" in output or "Unknown" in output)

    def test_removed_options_not_available(self):
        """Test that removed options (verbose, config, no-color) are not available."""
        # Test --verbose
        result = self.runner.invoke(app, ["--verbose", "version"])
        self.assertNotEqual(result.exit_code, 0)

        # Test --config
        result = self.runner.invoke(app, ["--config", "/path/to/config", "version"])
        self.assertNotEqual(result.exit_code, 0)

        # Test --no-color
        result = self.runner.invoke(app, ["--no-color", "version"])
        self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
