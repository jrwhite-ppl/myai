"""
Tests for CLI application state management.
"""

from pathlib import Path

from myai.cli.state import AppState


class TestAppState:
    """Test cases for AppState class."""

    def test_default_state(self):
        """Test default state initialization."""
        state = AppState()

        assert state.debug is False
        assert state.output_format == "table"
        assert state.context == {}

    def test_state_with_values(self):
        """Test state initialization with custom values."""
        state = AppState(debug=True, output_format="json")

        assert state.debug is True
        assert state.output_format == "json"

    def test_is_debug(self):
        """Test debug mode checking."""
        state = AppState(debug=False)
        assert not state.is_debug()

        state = AppState(debug=True)
        assert state.is_debug()

    def test_is_verbose(self):
        """Test verbose mode checking (now same as debug)."""
        # When debug is false, verbose is false
        state = AppState(debug=False)
        assert not state.is_verbose()

        # When debug is true, verbose is true
        state = AppState(debug=True)
        assert state.is_verbose()

    def test_context_management(self):
        """Test context value management."""
        state = AppState()

        # Test setting and getting context
        state.set_context("key1", "value1")
        assert state.get_context("key1") == "value1"

        # Test getting non-existent key
        assert state.get_context("nonexistent") is None

        # Test getting with default
        assert state.get_context("nonexistent", "default") == "default"

        # Test multiple values
        state.set_context("key2", {"nested": "data"})
        state.set_context("key3", [1, 2, 3])

        assert state.get_context("key2") == {"nested": "data"}
        assert state.get_context("key3") == [1, 2, 3]

        # Test context dict is updated
        assert "key1" in state.context
        assert "key2" in state.context
        assert "key3" in state.context

    def test_context_overwrite(self):
        """Test context value overwriting."""
        state = AppState()

        state.set_context("key", "original")
        assert state.get_context("key") == "original"

        state.set_context("key", "updated")
        assert state.get_context("key") == "updated"

    def test_context_default_factory(self):
        """Test that context is properly initialized as empty dict."""
        state1 = AppState()
        state2 = AppState()

        # Each instance should have its own context dict
        state1.set_context("key", "value1")
        state2.set_context("key", "value2")

        assert state1.get_context("key") == "value1"
        assert state2.get_context("key") == "value2"

        # Contexts should be independent
        assert state1.context is not state2.context

    def test_state_modification(self):
        """Test modifying state attributes after creation."""
        state = AppState()

        # Modify state attributes
        state.debug = True
        state.output_format = "json"

        assert state.debug is True
        assert state.output_format == "json"

        # Test that mode checking still works
        assert state.is_debug()
        assert state.is_verbose()  # verbose is same as debug now

    def test_context_with_various_types(self):
        """Test context with various data types."""
        state = AppState()

        # Test different data types
        test_values = [
            ("string", "test string"),
            ("integer", 42),
            ("float", 3.14),
            ("boolean", True),
            ("list", [1, 2, 3]),
            ("dict", {"nested": "value"}),
            ("none", None),
            ("path", Path("/test/path")),
        ]

        for key, value in test_values:
            state.set_context(key, value)
            assert state.get_context(key) == value
            assert state.get_context(key) is value  # Should be exact same object

    def test_state_immutability_of_defaults(self):
        """Test that modifying one instance doesn't affect others."""
        state1 = AppState()
        state2 = AppState()

        # Modify first instance
        state1.debug = True
        state1.set_context("test", "value")

        # Second instance should be unaffected
        assert state2.debug is False
        assert state2.get_context("test") is None

        # Original defaults should be preserved
        state3 = AppState()
        assert state3.debug is False
        assert state3.output_format == "table"
        assert state3.context == {}
