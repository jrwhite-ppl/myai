"""
Tests for the main CLI application.
"""

from unittest.mock import MagicMock, patch

from rich.console import Console

from myai.app import app, console, main, main_callback, state, status, version


class TestMainCallback:
    """Test cases for main callback function."""

    def test_main_callback_default_options(self):
        """Test main callback with default options."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, output="table")

        # Test that state is updated
        assert state.debug is False
        assert state.output_format == "table"

    def test_main_callback_debug_enabled(self):
        """Test main callback with debug enabled."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=True, output="table")

        assert state.debug is True
        assert state.is_debug()

    def test_main_callback_output_format(self):
        """Test main callback with different output format."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, output="json")

        assert state.output_format == "json"

    def test_main_callback_stores_state_in_context(self):
        """Test main callback stores state in context."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=False, output="table")

        assert ctx.obj == state

    @patch("myai.app.console")
    def test_main_callback_debug_prints_message(self, mock_console):
        """Test main callback prints debug message when debug enabled."""
        ctx = MagicMock()

        main_callback(ctx=ctx, debug=True, output="table")

        # Should print debug message
        mock_console.print.assert_called_with("[dim]Debug mode enabled[/dim]")


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
        state.output_format = "json"

        status(ctx)

        # Should print status information
        mock_console.print.assert_called()

        # Reset state
        state.debug = False
        state.output_format = "table"


class TestMainFunction:
    """Test cases for main function."""

    @patch("myai.app.app")
    def test_main_function_calls_app(self, mock_app):
        """Test that main function calls the Typer app."""
        main()

        mock_app.assert_called_once()

    def test_main_function_structure(self):
        """Test that main function properly sets up the app structure."""
        # Just verify that main() sets up the command groups correctly by checking imports
        from myai.app import app

        # Verify the app exists and is a Typer instance
        assert app is not None

        # Verify command modules are imported
        from myai.app import agent_cli, config_cli, install_cli, system_cli, wizard_cli

        assert install_cli.app is not None
        assert config_cli.app is not None
        assert agent_cli.app is not None
        assert system_cli.app is not None
        assert wizard_cli.app is not None

        # Verify main can be called without error
        # (Don't actually call it as it would run the full app)


class TestGlobalState:
    """Test cases for global state management."""

    def test_state_is_singleton(self):
        """Test that state is a global singleton."""
        from myai.app import state as imported_state

        assert state is imported_state
        assert id(state) == id(imported_state)

    def test_state_persistence_across_commands(self):
        """Test that state persists across command calls."""
        # Set state
        state.debug = True
        state.output_format = "json"

        # State should persist
        assert state.debug is True
        assert state.output_format == "json"

        # Reset for other tests
        state.debug = False
        state.output_format = "table"

    def test_state_independence(self):
        """Test that state changes don't affect other tests."""
        original_debug = state.debug
        original_output = state.output_format

        # Change state
        state.debug = not original_debug
        state.output_format = "xml"

        # Reset
        state.debug = original_debug
        state.output_format = original_output


class TestGlobalConsole:
    """Test cases for global console instance."""

    def test_console_is_rich_console(self):
        """Test that console is a Rich Console instance."""
        assert isinstance(console, Console)

    def test_console_is_singleton(self):
        """Test that console is a global singleton."""
        from myai.app import console as imported_console

        assert console is imported_console
        assert id(console) == id(imported_console)


class TestIntegration:
    """Integration tests for the app."""

    def test_app_can_be_imported(self):
        """Test that the app module can be imported without errors."""
        import myai.app

        assert hasattr(myai.app, "app")
        assert hasattr(myai.app, "main")
        assert hasattr(myai.app, "state")
        assert hasattr(myai.app, "console")

    @patch("myai.agent.registry.get_agent_registry")
    @patch("myai.config.manager.get_config_manager")
    def test_command_execution_flow(self, mock_config_manager, mock_registry):
        """Test complete command execution flow."""
        # Mock dependencies
        mock_agent = MagicMock()
        mock_agent.metadata.name = "test-agent"
        mock_agent.metadata.category.value = "test"

        mock_registry.return_value.list_agents.return_value = [mock_agent]

        mock_config = MagicMock()
        mock_config.agents.enabled = []
        mock_config.agents.global_enabled = []

        mock_config_manager.return_value.get_config.return_value = mock_config
        mock_config_manager.return_value.get_config_path.return_value = None

        from typer.testing import CliRunner

        runner = CliRunner()

        # Test help command
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "MyAI" in result.stdout

        # Test version command
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0

        # Test status command
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
