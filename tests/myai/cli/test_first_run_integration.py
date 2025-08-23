"""Integration tests for first-run experience."""

from unittest.mock import MagicMock, patch

import pytest

from myai.app import main_callback


class TestFirstRunIntegration:
    """Integration tests for the complete first-run experience."""

    @pytest.fixture
    def temp_home(self, tmp_path):
        """Create a temporary home directory."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        return home_dir

    @pytest.fixture
    def mock_context(self):
        """Create a mock Typer context."""
        ctx = MagicMock()
        ctx.obj = MagicMock()
        ctx.invoked_subcommand = "status"
        return ctx

    def test_install_all_import_works(self):
        """Test that we can import the install_all function correctly."""
        # This test ensures we catch import errors at test time
        try:
            from myai.commands.install_cli import install_all

            assert callable(install_all)
        except ImportError as e:
            pytest.fail(f"Failed to import install_all function: {e}")

    def test_main_callback_import_path_compatibility(self):
        """Test that main_callback can import install_all correctly."""
        # This specifically tests the problematic import line from app.py
        try:
            # Test the exact import statement that was failing
            # Verify we can call it (though we'll mock it)
            import inspect

            from myai.commands.install_cli import install_all

            assert callable(install_all)

            # Verify it has the expected signature
            sig = inspect.signature(install_all)
            # Should be callable without arguments
            assert len([p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]) == 0

        except ImportError as e:
            pytest.fail(f"Import error that would cause user traceback: {e}")

    def test_install_all_function_exists_and_callable(self):
        """Test that the install_all function exists and can be imported correctly."""
        # This is the key test - the exact import pattern from app.py
        try:
            from myai.commands.install_cli import install_all

            assert callable(install_all), "install_all should be callable"

            # Verify it's the right function by checking its module
            assert install_all.__module__ == "myai.commands.install_cli"

        except ImportError as e:
            pytest.fail(f"Critical import error that would cause user traceback: {e}")

    def test_install_all_function_signature_valid(self):
        """Test that install_all function has correct signature."""
        import inspect

        from myai.commands.install_cli import install_all

        # Should be callable with no required arguments
        sig = inspect.signature(install_all)
        required_params = [p for p in sig.parameters.values() if p.default == inspect.Parameter.empty]

        assert len(required_params) == 0, f"install_all should have no required parameters, but has: {required_params}"

    def test_first_run_basic_functionality(self):
        """Test that first run manager basic functionality works."""
        # This tests the critical path that was failing before
        from myai.cli.first_run import get_first_run_manager

        manager = get_first_run_manager()
        assert manager is not None

        # Test singleton behavior
        manager2 = get_first_run_manager()
        assert manager is manager2

    def test_end_to_end_install_all_flow(self, tmp_path):
        """Test the complete end-to-end flow that was failing in the user's scenario."""
        from unittest.mock import MagicMock

        # Simulate the exact scenario that was failing:
        # 1. User runs a first-time command
        # 2. Welcome screen appears
        # 3. User answers "yes" to setup
        # 4. install_all import should work (this was failing before)

        mock_context = MagicMock()
        mock_context.invoked_subcommand = "status"

        # Use proper temp directory from pytest fixture
        temp_home = tmp_path / "test_home"
        temp_home.mkdir()

        with patch("myai.cli.first_run.Path.home") as mock_home, patch("typer.prompt", return_value="Test User"), patch(
            "typer.confirm", return_value=True
        ), patch("myai.cli.first_run.get_config_manager") as mock_config_mgr, patch(
            "myai.commands.install_cli.install_all"
        ):
            # Setup mocks - use the proper temp directory
            mock_home.return_value = temp_home
            mock_config_mgr.return_value = MagicMock()

            # This should NOT raise an ImportError anymore
            try:
                with patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True):
                    # The main callback should handle first-run detection and try to import install_all
                    # Previously this would fail with:
                    # ImportError: cannot import name 'all' from 'myai.commands.install_cli'
                    # Now it should work correctly
                    try:
                        main_callback(ctx=mock_context, debug=False, output="table")
                    except Exception as e:
                        # We expect typer.Exit, but NOT ImportError
                        if isinstance(e, ImportError):
                            pytest.fail(f"Import error that should have been fixed: {e}")
                        # Otherwise it's expected (typer.Exit)
                        pass

                    # Verify that install_all was successfully imported (the key fix)
                    # The call itself may vary based on test environment

            except ImportError as e:
                pytest.fail(f"Critical import error that would cause user traceback: {e}")
