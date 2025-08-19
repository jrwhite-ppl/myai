"""
Tests for the main entry point module.
"""

import subprocess
import sys
from unittest.mock import patch


class TestMainModule:
    """Test cases for the __main__.py module."""

    def test_main_module_execution(self):
        """Test that the main module can be executed."""
        # Test that the module can be imported and executed
        with patch("myai.app.main") as mock_main:
            # Import and execute the __main__ module with __name__ == "__main__"
            import sys

            old_name = sys.modules.get("__main__", None)
            try:
                with open("src/myai/__main__.py") as f:
                    code = compile(f.read(), "src/myai/__main__.py", "exec")
                    globals_dict = {"__name__": "__main__"}
                    exec(code, globals_dict)  # noqa: S102
                mock_main.assert_called_once()
            finally:
                if old_name:
                    sys.modules["__main__"] = old_name

    def test_main_module_via_python_m(self):
        """Test that the module can be executed via python -m."""
        # This test verifies that 'python -m myai' works
        result = subprocess.run(
            [sys.executable, "-m", "myai", "--help"],  # noqa: S603
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        # Should not fail completely, even if it shows help
        assert result.returncode in [0, 2]  # 0 for success, 2 for argparse help

        # Should contain some expected output
        output = result.stdout + result.stderr
        assert any(word in output.lower() for word in ["myai", "usage", "help"])

    def test_main_module_entry_point(self):
        """Test that the main module entry point works correctly."""
        with patch("myai.app.main") as mock_main:
            # Simulate running as main module
            import importlib.util

            spec = importlib.util.spec_from_file_location("__main__", "src/myai/__main__.py")
            module = importlib.util.module_from_spec(spec)
            module.__name__ = "__main__"

            # Execute the module
            spec.loader.exec_module(module)

            # Verify main was called
            mock_main.assert_called_once()
