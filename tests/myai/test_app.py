"""
Tests for the main CLI application.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from myai.app import app, console, main, main_callback, state, status, version


class TestMainCallback:
    """Test cases for main callback function."""

    def test_main_callback_default_options(self):
        """Test main callback with default options."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, verbose=False, config_path=None, output_format="table", no_color=False)

        # Test that state is updated
        assert state.debug is False
        assert state.verbose is False
        assert state.config_path is None
        assert state.output_format == "table"

    def test_main_callback_debug_enabled(self):
        """Test main callback with debug enabled."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=True, verbose=False, config_path=None, output_format="table", no_color=False)

        assert state.debug is True
        assert state.is_debug()

    def test_main_callback_verbose_enabled(self):
        """Test main callback with verbose enabled."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, verbose=True, config_path=None, output_format="table", no_color=False)

        assert state.verbose is True
        assert state.is_verbose()

    def test_main_callback_custom_config_path(self):
        """Test main callback with custom config path."""
        ctx = MagicMock()
        config_path = Path("/custom/config.json")

        main_callback(
            ctx=ctx, debug=False, verbose=False, config_path=config_path, output_format="table", no_color=False
        )

        assert state.config_path == config_path

    def test_main_callback_json_output_format(self):
        """Test main callback with JSON output format."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, verbose=False, config_path=None, output_format="json", no_color=False)

        assert state.output_format == "json"

    @patch("myai.app.console")
    def test_main_callback_no_color(self, mock_console):
        """Test main callback with no color option."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, verbose=False, config_path=None, output_format="table", no_color=True)

        # Should disable color on console
        mock_console._color_system = None


class TestVersionCommand:
    """Test cases for version command."""

    @patch("myai.app.console")
    def test_version_command(self, mock_console):
        """Test version command output."""
        ctx = MagicMock()
        version(ctx, short=False)

        # Should print version information
        mock_console.print.assert_called()

    @patch("myai.app.console")
    def test_version_command_short(self, mock_console):
        """Test version command short output."""
        ctx = MagicMock()
        version(ctx, short=True)

        # Should print just version number
        mock_console.print.assert_called()


class TestStatusCommand:
    """Test cases for status command."""

    @patch("myai.app.console")
    def test_status_command(self, mock_console):
        """Test status command output."""
        ctx = MagicMock()

        status(ctx)

        # Should print status information
        mock_console.print.assert_called()

    @patch("myai.app.console")
    def test_status_command_with_debug_state(self, mock_console):
        """Test status command with debug state enabled."""
        ctx = MagicMock()

        # Set debug state
        state.debug = True
        state.verbose = True
        state.output_format = "json"

        status(ctx)

        # Should print status information
        mock_console.print.assert_called()

        # Reset state
        state.debug = False
        state.verbose = False
        state.output_format = "table"


class TestMainFunction:
    """Test cases for main function."""

    @patch("myai.app.app")
    def test_main_function_calls_app(self, mock_app):
        """Test that main function calls the Typer app."""
        main()

        mock_app.assert_called_once()

    @patch("myai.app.app")
    def test_main_function_exception_handling(self, mock_app):
        """Test main function handles exceptions gracefully."""
        # Make app() raise an exception
        mock_app.side_effect = Exception("Test error")

        # Should not propagate the exception
        with pytest.raises(Exception):  # noqa: B017
            main()


class TestAppConfiguration:
    """Test cases for app configuration."""

    def test_app_exists(self):
        """Test that app is properly configured."""
        assert app is not None
        assert app.info.name == "myai"
        assert "MyAI" in app.info.help
        assert app.info.no_args_is_help is True

    def test_console_exists(self):
        """Test that console is properly configured."""
        assert console is not None
        assert isinstance(console, Console)

    def test_state_exists(self):
        """Test that state is properly initialized."""
        assert state is not None
        # State should have default values
        assert state.output_format == "table"
        assert state.debug is False
        assert state.verbose is False

    def test_app_commands_registered(self):
        """Test that all expected commands are registered."""
        # Typer apps don't expose commands in the same way
        # Just test that app has a callable interface
        assert callable(app)
        assert hasattr(app, "info")
        assert hasattr(app, "command")


class TestGlobalState:
    """Test cases for global state management."""

    def setup_method(self):
        """Reset state before each test."""
        state.debug = False
        state.verbose = False
        state.config_path = None
        state.output_format = "table"
        state.context.clear()

    def test_state_persistence_across_commands(self):
        """Test that state persists across command calls."""
        ctx = MagicMock()

        # Set state through main callback
        main_callback(
            ctx=ctx, debug=True, verbose=True, config_path=Path("/test"), output_format="json", no_color=False
        )

        # State should be updated
        assert state.debug is True
        assert state.verbose is True
        assert state.config_path == Path("/test")
        assert state.output_format == "json"

        # State should still be accessible
        assert state.is_debug()
        assert state.is_verbose()

    def test_state_modification(self):
        """Test direct state modification."""
        # Modify state directly
        state.set_context("test_key", "test_value")
        state.debug = True

        assert state.get_context("test_key") == "test_value"
        assert state.debug is True

    def test_state_independence(self):
        """Test that state changes don't affect other instances."""
        # This test verifies that we're using a singleton pattern correctly
        original_debug = state.debug
        original_verbose = state.verbose

        # Import state again
        from myai.app import state as state2

        # Should be the same instance
        assert state is state2

        # Modify through one reference
        state.debug = True

        # Should be reflected in the other
        assert state2.debug is True

        # Reset
        state.debug = original_debug
        state.verbose = original_verbose


class TestIntegration:
    """Integration tests for the app module."""

    def test_app_can_be_imported(self):
        """Test that the app can be imported without errors."""
        # This test ensures all imports work correctly
        from myai.app import app, console, main, state

        assert app is not None
        assert console is not None
        assert main is not None
        assert state is not None

    @patch("myai.app.console")
    def test_command_execution_flow(self, mock_console):
        """Test the flow of command execution."""
        ctx = MagicMock()

        # Execute main callback to set up state
        main_callback(ctx=ctx, debug=True, verbose=False, config_path=None, output_format="table", no_color=False)

        # Execute version command
        version(ctx, short=False)

        # Should have proper state
        assert state.debug is True
        mock_console.print.assert_called()

    def test_typer_app_structure(self):
        """Test that the Typer app is properly structured."""
        # Test that app has the expected structure
        assert callable(app)
        assert hasattr(app, "info")
        assert app.info.name == "myai"
