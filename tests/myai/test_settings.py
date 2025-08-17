import unittest
from unittest.mock import patch

from pydantic import ValidationError

from myai.settings import Settings, settings


class TestSettings(unittest.TestCase):
    """Test cases for the Settings class."""

    def setUp(self):
        """Set up test fixtures."""
        self.settings = Settings()

    def test_settings_default_values(self):
        """Test that settings have correct default values."""
        self.assertFalse(self.settings.debug)

    def test_settings_debug_true(self):
        """Test setting debug to True."""
        with patch.dict("os.environ", {"DEBUG": "true"}):
            settings_instance = Settings()
            self.assertTrue(settings_instance.debug)

    def test_settings_debug_false(self):
        """Test setting debug to False."""
        with patch.dict("os.environ", {"DEBUG": "false"}):
            settings_instance = Settings()
            self.assertFalse(settings_instance.debug)

    def test_settings_debug_invalid_value(self):
        """Test that invalid debug values raise validation error."""
        with patch.dict("os.environ", {"DEBUG": "invalid"}):
            with self.assertRaises(ValidationError):
                Settings()

    def test_settings_no_environment_variables(self):
        """Test settings with no environment variables."""
        with patch.dict("os.environ", {}, clear=True):
            settings_instance = Settings()
            self.assertFalse(settings_instance.debug)

    def test_settings_instance_creation(self):
        """Test that settings instance can be created."""
        self.assertIsInstance(self.settings, Settings)
        self.assertIsInstance(self.settings.debug, bool)

    def test_settings_attributes(self):
        """Test that settings has the expected attributes."""
        self.assertTrue(hasattr(self.settings, "debug"))

    def test_settings_repr(self):
        """Test the string representation of settings."""
        repr_str = repr(self.settings)
        self.assertIn("Settings", repr_str)
        self.assertIn("debug", repr_str)


class TestGlobalSettings(unittest.TestCase):
    """Test cases for the global settings instance."""

    def test_global_settings_instance(self):
        """Test that global settings is an instance of Settings."""
        self.assertIsInstance(settings, Settings)

    def test_global_settings_debug_default(self):
        """Test that global settings debug defaults to False."""
        self.assertFalse(settings.debug)

    def test_global_settings_singleton_behavior(self):
        """Test that global settings behaves like a singleton."""
        from myai.settings import settings as settings2

        self.assertIs(settings, settings2)


class TestSettingsIntegration(unittest.TestCase):
    """Integration tests for settings with environment variables."""

    def test_settings_with_environment_variables(self):
        """Test settings with various environment variable combinations."""
        test_cases = [
            ({"DEBUG": "true"}, True),
            ({"DEBUG": "false"}, False),
            ({"DEBUG": "1"}, True),
            ({"DEBUG": "0"}, False),
            ({}, False),  # No environment variables
        ]

        for env_vars, expected_debug in test_cases:
            with self.subTest(env_vars=env_vars, expected_debug=expected_debug):
                with patch.dict("os.environ", env_vars, clear=True):
                    settings_instance = Settings()
                    self.assertEqual(settings_instance.debug, expected_debug)

    def test_settings_case_sensitivity(self):
        """Test that settings are case insensitive (pydantic-settings default behavior)."""
        with patch.dict("os.environ", {"debug": "true"}):  # lowercase
            settings_instance = Settings()
            self.assertTrue(settings_instance.debug)  # pydantic-settings is case-insensitive

        with patch.dict("os.environ", {"DEBUG": "true"}):  # uppercase
            settings_instance = Settings()
            self.assertTrue(settings_instance.debug)


if __name__ == "__main__":
    unittest.main()
