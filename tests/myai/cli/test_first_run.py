"""Tests for the first-run detection and welcome screen."""

import os
from unittest.mock import MagicMock, patch

import pytest

from myai.cli.first_run import FirstRunManager, get_first_run_manager


class TestFirstRunManager:
    """Test the FirstRunManager functionality."""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create a temporary home directory."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        return home_dir

    @pytest.fixture
    def first_run_manager(self, temp_home):
        """Create a FirstRunManager with a temporary home."""
        with patch("myai.cli.first_run.Path.home", return_value=temp_home):
            manager = FirstRunManager()
            # Override storage to use temp home
            from myai.storage.filesystem import FileSystemStorage

            manager.storage = FileSystemStorage(base_path=temp_home / ".myai")
            return manager

    def test_has_run_before_initially_false(self, first_run_manager):
        """Test that has_run_before returns False on first check."""
        assert not first_run_manager.has_run_before()

    def test_mark_first_run_complete(self, first_run_manager):
        """Test marking first run as complete."""
        assert not first_run_manager.has_run_before()
        first_run_manager.mark_first_run_complete()
        assert first_run_manager.has_run_before()

    def test_should_show_welcome_first_time(self, first_run_manager):
        """Test should_show_welcome returns True for first run."""
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), patch(
            "sys.argv", ["myai", "status"]
        ):
            assert first_run_manager.should_show_welcome()

    def test_should_show_welcome_after_complete(self, first_run_manager):
        """Test should_show_welcome returns False after marking complete."""
        first_run_manager.mark_first_run_complete()
        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), patch(
            "sys.argv", ["myai", "status"]
        ):
            assert not first_run_manager.should_show_welcome()

    def test_should_show_welcome_in_any_environment(self, first_run_manager):
        """Test should_show_welcome works in both interactive and non-interactive environments."""
        with patch("sys.stdin.isatty", return_value=False), patch("sys.argv", ["myai", "status"]):
            assert first_run_manager.should_show_welcome()

        with patch("sys.stdout.isatty", return_value=False), patch("sys.argv", ["myai", "status"]):
            assert first_run_manager.should_show_welcome()

    def test_should_show_welcome_ci_environment(self, first_run_manager):
        """Test should_show_welcome returns False in CI environment."""
        with patch.dict(os.environ, {"CI": "true"}), patch("sys.stdin.isatty", return_value=True), patch(
            "sys.stdout.isatty", return_value=True
        ):
            assert not first_run_manager.should_show_welcome()

        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch("sys.stdin.isatty", return_value=True), patch(
            "sys.stdout.isatty", return_value=True
        ):
            assert not first_run_manager.should_show_welcome()

    def test_should_show_welcome_json_output(self, first_run_manager):
        """Test should_show_welcome returns False with JSON output."""
        with patch("sys.argv", ["myai", "--output", "json", "status"]), patch(
            "sys.stdin.isatty", return_value=True
        ), patch("sys.stdout.isatty", return_value=True):
            assert not first_run_manager.should_show_welcome()

    def test_should_show_welcome_skip_commands(self, first_run_manager):
        """Test should_show_welcome returns False only for version commands."""
        # Only version commands should be skipped now
        test_commands = [
            ["myai", "version"],
            ["myai", "--version"],
        ]

        for argv in test_commands:
            with patch("sys.argv", argv):
                assert not first_run_manager.should_show_welcome()

        # Help commands should NOT be skipped (they should show welcome on first run)
        help_commands = [
            ["myai", "--help"],
            ["myai", "-h"],
        ]

        for argv in help_commands:
            with patch("sys.argv", argv):
                assert first_run_manager.should_show_welcome()

    def test_should_show_welcome_for_any_command_first_run(self, first_run_manager):
        """Test should_show_welcome returns True for ANY command on first run."""
        test_commands = [
            ["myai", "status"],
            ["myai", "agent", "list"],
            ["myai", "install", "all"],
            ["myai", "uninstall", "--all"],
        ]

        for argv in test_commands:
            with patch("sys.argv", argv), patch("sys.stdin.isatty", return_value=True), patch(
                "sys.stdout.isatty", return_value=True
            ):
                assert first_run_manager.should_show_welcome()

    def test_should_show_logo_for_status(self, first_run_manager):
        """Test should_show_logo returns True for status command."""
        with patch("sys.argv", ["myai", "status"]):
            assert first_run_manager.should_show_logo()

    def test_should_show_logo_not_for_other_commands(self, first_run_manager):
        """Test should_show_logo returns False for non-status commands."""
        with patch("sys.argv", ["myai", "agent", "list"]):
            assert not first_run_manager.should_show_logo()

    def test_should_show_logo_not_with_json_output(self, first_run_manager):
        """Test should_show_logo returns False with JSON output."""
        with patch("sys.argv", ["myai", "--output", "json", "status"]):
            assert not first_run_manager.should_show_logo()

    def test_display_logo(self, first_run_manager, capsys):
        """Test logo display."""
        first_run_manager.display_logo()
        captured = capsys.readouterr()
        # Check that the ASCII art logo is displayed
        assert "███╗   ███╗██╗   ██╗ █████╗ ██╗" in captured.out
        assert "████╗ ████║╚██╗ ██╔╝██╔══██╗██║" in captured.out
        assert "╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝" in captured.out

    @patch("typer.prompt")
    @patch("typer.confirm")
    def test_run_welcome_setup_with_install(self, mock_confirm, mock_prompt, first_run_manager, capsys):
        """Test successful welcome setup with install all."""
        mock_prompt.return_value = "Test User"
        mock_confirm.return_value = True  # User chooses to install

        with patch("myai.cli.first_run.get_config_manager") as mock_config_mgr, patch(
            "sys.stdin.isatty", return_value=True
        ), patch("sys.stdout.isatty", return_value=True):
            mock_config_mgr.return_value = MagicMock()

            result = first_run_manager.run_welcome_setup()
            assert result == "install_all"  # Should return install_all signal
            assert first_run_manager.has_run_before()

            # Verify that set_config_value was called if name was provided
            mock_config_mgr.return_value.set_config_value.assert_called_once_with(
                "user.name", "Test User", level="user"
            )

            # Verify logo was displayed as part of welcome
            captured = capsys.readouterr()
            assert "███╗   ███╗██╗   ██╗ █████╗ ██╗" in captured.out

    @patch("typer.prompt")
    @patch("typer.confirm")
    def test_run_welcome_setup_without_install(self, mock_confirm, mock_prompt, first_run_manager, capsys):
        """Test successful welcome setup without install all."""
        mock_prompt.return_value = "Test User"
        mock_confirm.return_value = False  # User chooses not to install

        with patch("myai.cli.first_run.get_config_manager") as mock_config_mgr, patch(
            "sys.stdin.isatty", return_value=True
        ), patch("sys.stdout.isatty", return_value=True):
            mock_config_mgr.return_value = MagicMock()

            result = first_run_manager.run_welcome_setup()
            assert result is True  # Should return True (completed without install)
            assert first_run_manager.has_run_before()

            # Verify logo was displayed as part of welcome
            captured = capsys.readouterr()
            assert "███╗   ███╗██╗   ██╗ █████╗ ██╗" in captured.out

    @patch("typer.prompt")
    def test_run_welcome_setup_keyboard_interrupt(self, mock_prompt, first_run_manager):
        """Test setup cancelled by user in interactive mode."""
        mock_prompt.side_effect = KeyboardInterrupt()

        with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
            result = first_run_manager.run_welcome_setup()
            assert result is False
            # Should still mark as complete to avoid annoyance
            assert first_run_manager.has_run_before()

    def test_get_first_run_manager_singleton(self):
        """Test that get_first_run_manager returns singleton."""
        manager1 = get_first_run_manager()
        manager2 = get_first_run_manager()
        assert manager1 is manager2
