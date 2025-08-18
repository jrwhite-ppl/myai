"""
Tests for environment variable parser.
"""

import os
import tempfile
from pathlib import Path

import pytest

from myai.config.env_parser import CircularReferenceError, EnvParser


class TestEnvParser:
    """Test cases for the EnvParser class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a test environment
        self.test_env = {
            "TEST_VAR": "test_value",
            "HOME": "/home/user",
            "USER": "testuser",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "API_KEY": "secret123",
            "DEBUG": "true",
        }
        self.parser = EnvParser(env_vars=self.test_env.copy(), load_dotenv=False)

    def test_simple_variable_expansion(self):
        """Test simple $VAR expansion."""
        result = self.parser.expand("Hello $USER")
        assert result == "Hello testuser"

        result = self.parser.expand("$HOME/config")
        assert result == "/home/user/config"

    def test_brace_variable_expansion(self):
        """Test ${VAR} expansion."""
        result = self.parser.expand("Hello ${USER}")
        assert result == "Hello testuser"

        result = self.parser.expand("${HOME}/config")
        assert result == "/home/user/config"

    def test_default_value_expansion(self):
        """Test ${VAR:-default} expansion."""
        result = self.parser.expand("${MISSING_VAR:-default_value}")
        assert result == "default_value"

        result = self.parser.expand("${USER:-fallback}")
        assert result == "testuser"  # Uses actual value, not default

        result = self.parser.expand("${EMPTY_VAR:-/default/path}")
        assert result == "/default/path"

    def test_complex_expansion(self):
        """Test complex variable expansion scenarios."""
        result = self.parser.expand("Database: ${DATABASE_URL}")
        assert result == "Database: postgresql://user:pass@localhost/db"

        result = self.parser.expand("Config at ${HOME}/config/${USER}.json")
        assert result == "Config at /home/user/config/testuser.json"

        result = self.parser.expand("Debug mode: ${DEBUG:-false}")
        assert result == "Debug mode: true"

    def test_recursive_expansion(self):
        """Test recursive variable expansion."""
        # Add recursive variables to test env
        self.parser.set_env_var("BASE_PATH", "$HOME/myai")
        self.parser.set_env_var("CONFIG_PATH", "${BASE_PATH}/config")

        result = self.parser.expand("$CONFIG_PATH")
        assert result == "/home/user/myai/config"

    def test_circular_reference_detection(self):
        """Test circular reference detection."""
        self.parser.set_env_var("VAR_A", "$VAR_B")
        self.parser.set_env_var("VAR_B", "$VAR_A")

        with pytest.raises(CircularReferenceError) as exc_info:
            self.parser.expand("$VAR_A")

        assert "VAR_A" in exc_info.value.variables
        assert "VAR_B" in exc_info.value.variables

    def test_dict_expansion(self):
        """Test expansion of dictionary values."""
        config = {
            "database": {
                "url": "$DATABASE_URL",
                "debug": "${DEBUG:-false}",
            },
            "paths": {
                "home": "$HOME",
                "config": "${HOME}/config",
            },
        }

        result = self.parser.expand(config)
        expected = {
            "database": {
                "url": "postgresql://user:pass@localhost/db",
                "debug": "true",
            },
            "paths": {
                "home": "/home/user",
                "config": "/home/user/config",
            },
        }

        assert result == expected

    def test_list_expansion(self):
        """Test expansion of list values."""
        config = [
            "$HOME/bin",
            "${HOME}/config",
            "${MISSING:-/default}",
            "literal_value",
        ]

        result = self.parser.expand(config)
        expected = [
            "/home/user/bin",
            "/home/user/config",
            "/default",
            "literal_value",
        ]

        assert result == expected

    def test_mixed_expansion(self):
        """Test expansion of mixed data structures."""
        config = {
            "users": ["$USER", "${USER:-unknown}"],
            "paths": {
                "home": "$HOME",
                "config": "${HOME}/config",
            },
            "settings": {
                "debug": "${DEBUG:-false}",
                "api_url": "https://api.example.com",
                "timeout": 30,
            },
        }

        result = self.parser.expand(config)

        assert result["users"] == ["testuser", "testuser"]
        assert result["paths"]["home"] == "/home/user"
        assert result["paths"]["config"] == "/home/user/config"
        assert result["settings"]["debug"] == "true"
        assert result["settings"]["api_url"] == "https://api.example.com"
        assert result["settings"]["timeout"] == 30

    def test_validation_success(self):
        """Test successful validation."""
        text = "Config at ${HOME}/config with ${USER} user"
        result = self.parser.validate_expansion(text)

        assert result["valid"] is True
        assert result["missing_vars"] == []
        assert result["circular_refs"] == []
        assert result["expanded"] == "Config at /home/user/config with testuser user"

    def test_validation_missing_vars(self):
        """Test validation with missing variables."""
        text = "Missing: $MISSING_VAR and ${ANOTHER_MISSING}"
        result = self.parser.validate_expansion(text)

        assert result["valid"] is False
        assert "MISSING_VAR" in result["missing_vars"]
        assert "ANOTHER_MISSING" in result["missing_vars"]

    def test_validation_with_defaults(self):
        """Test validation with default values."""
        text = "Has default: ${MISSING:-default} and ${USER:-fallback}"
        result = self.parser.validate_expansion(text)

        assert result["valid"] is True
        assert result["missing_vars"] == []
        assert result["expanded"] == "Has default: default and testuser"

    def test_validation_circular_references(self):
        """Test validation with circular references."""
        self.parser.set_env_var("CIRCULAR_A", "$CIRCULAR_B")
        self.parser.set_env_var("CIRCULAR_B", "$CIRCULAR_A")

        text = "Circular: $CIRCULAR_A"
        result = self.parser.validate_expansion(text)

        assert result["valid"] is False
        assert "CIRCULAR_A" in result["circular_refs"]
        assert "CIRCULAR_B" in result["circular_refs"]

    def test_env_var_management(self):
        """Test environment variable management methods."""
        # Test getting env vars
        env_vars = self.parser.get_env_vars()
        assert env_vars["TEST_VAR"] == "test_value"
        assert env_vars["USER"] == "testuser"

        # Test setting env var
        self.parser.set_env_var("NEW_VAR", "new_value")
        assert self.parser.get_env_vars()["NEW_VAR"] == "new_value"

        # Test updating multiple vars
        self.parser.update_env_vars({"VAR1": "value1", "VAR2": "value2"})
        env_vars = self.parser.get_env_vars()
        assert env_vars["VAR1"] == "value1"
        assert env_vars["VAR2"] == "value2"

    def test_no_expansion_needed(self):
        """Test strings that don't need expansion."""
        result = self.parser.expand("No variables here")
        assert result == "No variables here"

        result = self.parser.expand("")
        assert result == ""

        result = self.parser.expand("Has $ but no variables")
        assert result == "Has $ but no variables"

    def test_edge_cases(self):
        """Test edge cases and special scenarios."""
        # Empty variable name
        result = self.parser.expand("$")
        assert result == "$"

        # Invalid variable name (starts with number)
        result = self.parser.expand("$123VAR")
        assert result == "$123VAR"

        # Nested braces (should not expand inner)
        result = self.parser.expand("${HOME${USER}}")
        # This should not cause errors but may not expand as expected
        assert isinstance(result, str)

        # Multiple expansions in one string
        result = self.parser.expand("$USER at $HOME using $TEST_VAR")
        assert result == "testuser at /home/user using test_value"


class TestEnvParserWithDotenv:
    """Test environment parser with .env file support."""

    def test_dotenv_loading(self):
        """Test loading variables from .env files."""
        # Create a temporary directory and .env file
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            env_file = tmp_path / ".env"

            # Create .env file with test variables
            env_content = """
# Test environment variables
TEST_VAR=from_dotenv
DATABASE_URL=postgresql://localhost/test
API_KEY="secret_key_with_quotes"
MULTILINE_VAR=line1\\nline2
EMPTY_VAR=
# Comment line
QUOTED_VAR='single_quoted_value'
            """.strip()

            env_file.write_text(env_content)

            # Change to the directory and create parser
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                parser = EnvParser(load_dotenv=True)

                # Test that variables were loaded
                env_vars = parser.get_env_vars()
                assert env_vars["TEST_VAR"] == "from_dotenv"
                assert env_vars["DATABASE_URL"] == "postgresql://localhost/test"
                assert env_vars["API_KEY"] == "secret_key_with_quotes"
                assert env_vars["QUOTED_VAR"] == "single_quoted_value"

                # Test expansion with dotenv variables
                result = parser.expand("Database: $DATABASE_URL")
                assert result == "Database: postgresql://localhost/test"

            finally:
                os.chdir(original_cwd)

    def test_dotenv_precedence(self):
        """Test that system environment variables take precedence over .env."""
        # Create a temporary directory and .env file
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            env_file = tmp_path / ".env"

            # Create .env file
            env_file.write_text("TEST_PRECEDENCE=from_dotenv")

            # Set system environment variable
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)

                # Create parser with system env taking precedence
                system_env = {"TEST_PRECEDENCE": "from_system"}
                parser = EnvParser(env_vars=system_env, load_dotenv=True)

                # System env should win
                assert parser.get_env_vars()["TEST_PRECEDENCE"] == "from_system"

            finally:
                os.chdir(original_cwd)
