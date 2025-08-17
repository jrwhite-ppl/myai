"""Tests for input validation framework."""

import re
import tempfile
from pathlib import Path

import pytest

from myai.security.validation import (
    CommandValidationError,
    InputValidator,
    PathValidationError,
    ValidationConfig,
    ValidationError,
)


class TestInputValidator:
    """Test InputValidator class."""

    @pytest.fixture
    def validator(self):
        """Create InputValidator instance."""
        return InputValidator()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_validate_path_basic(self, validator, temp_dir):
        """Test basic path validation."""
        valid_path = temp_dir / "test.txt"
        valid_path.write_text("content")

        result = validator.validate_path(valid_path)
        assert result == valid_path.resolve()

    def test_validate_path_string_input(self, validator, temp_dir):
        """Test path validation with string input."""
        valid_path = temp_dir / "test.txt"
        valid_path.write_text("content")

        result = validator.validate_path(str(valid_path))
        assert result == valid_path.resolve()

    def test_validate_path_must_exist_success(self, validator, temp_dir):
        """Test path validation requiring existing file."""
        existing_file = temp_dir / "existing.txt"
        existing_file.write_text("content")

        result = validator.validate_path(existing_file, must_exist=True)
        assert result == existing_file.resolve()

    def test_validate_path_must_exist_failure(self, validator, temp_dir):
        """Test path validation requiring existing file fails."""
        nonexistent = temp_dir / "nonexistent.txt"

        with pytest.raises(PathValidationError, match="Path does not exist"):
            validator.validate_path(nonexistent, must_exist=True)

    def test_validate_path_relative_required(self, validator):
        """Test path validation requiring relative path."""
        relative_path = Path("relative/file.txt")

        result = validator.validate_path(relative_path, must_be_relative=True)
        assert result.is_absolute()  # Should be resolved to absolute

    def test_validate_path_absolute_required(self, validator, temp_dir):
        """Test path validation requiring absolute path."""
        result = validator.validate_path(temp_dir, must_be_absolute=True)
        assert result.is_absolute()

    def test_validate_path_relative_fails_absolute_check(self, validator):
        """Test relative path fails absolute requirement."""
        relative_path = Path("relative/file.txt")

        with pytest.raises(PathValidationError, match="Path must be absolute"):
            validator.validate_path(relative_path, must_be_absolute=True)

    def test_validate_path_absolute_fails_relative_check(self, validator, temp_dir):
        """Test absolute path fails relative requirement."""
        with pytest.raises(PathValidationError, match="Path must be relative"):
            validator.validate_path(temp_dir, must_be_relative=True)

    def test_validate_path_allowed_parents(self, validator, temp_dir):
        """Test path validation with allowed parents."""
        allowed_parent = temp_dir / "allowed"
        allowed_parent.mkdir()

        test_file = allowed_parent / "test.txt"
        test_file.write_text("content")

        result = validator.validate_path(test_file, allowed_parents=[allowed_parent])
        assert result == test_file.resolve()

    def test_validate_path_disallowed_parent(self, validator, temp_dir):
        """Test path validation fails with disallowed parent."""
        allowed_parent = temp_dir / "allowed"
        disallowed_parent = temp_dir / "disallowed"

        allowed_parent.mkdir()
        disallowed_parent.mkdir()

        test_file = disallowed_parent / "test.txt"
        test_file.write_text("content")

        with pytest.raises(PathValidationError, match="Path not under allowed parents"):
            validator.validate_path(test_file, allowed_parents=[allowed_parent])

    def test_validate_path_dangerous_patterns(self, validator):
        """Test path validation rejects dangerous patterns."""
        dangerous_paths = [
            "../../../etc/passwd",
            "~/sensitive/file",
            "${HOME}/file",
            "`whoami`/file",
            "file|rm -rf /",
            "file;dangerous",
            "file&background",
            "file>output",
            "file<input",
        ]

        for dangerous_path in dangerous_paths:
            with pytest.raises(PathValidationError, match="Dangerous pattern"):
                validator.validate_path(dangerous_path)

    def test_validate_path_null_byte(self, validator):
        """Test path validation rejects null bytes."""
        with pytest.raises(PathValidationError, match="Null byte detected"):
            validator.validate_path("file\x00name.txt")

    def test_validate_path_too_long(self, validator):
        """Test path validation rejects overly long paths."""
        long_path = "a" * (validator.MAX_PATH_LENGTH + 1)

        with pytest.raises(PathValidationError, match="Path too long"):
            validator.validate_path(long_path)

    def test_validate_path_filename_too_long(self, validator):
        """Test path validation rejects overly long filenames."""
        long_filename = "a" * (validator.MAX_FILENAME_LENGTH + 1) + ".txt"

        with pytest.raises(PathValidationError, match="Filename too long"):
            validator.validate_path(long_filename)

    def test_validate_filename_basic(self, validator):
        """Test basic filename validation."""
        result = validator.validate_filename("test.txt")
        assert result == "test.txt"

    def test_validate_filename_empty(self, validator):
        """Test filename validation rejects empty filename."""
        with pytest.raises(ValidationError, match="Filename cannot be empty"):
            validator.validate_filename("")

    def test_validate_filename_too_long(self, validator):
        """Test filename validation rejects overly long filename."""
        long_filename = "a" * (validator.MAX_FILENAME_LENGTH + 1)

        with pytest.raises(ValidationError, match="Filename too long"):
            validator.validate_filename(long_filename)

    def test_validate_filename_dangerous_chars(self, validator):
        """Test filename validation rejects dangerous characters."""
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00"]

        for char in dangerous_chars:
            with pytest.raises(ValidationError, match="Dangerous characters"):
                validator.validate_filename(f"file{char}name.txt")

    def test_validate_filename_reserved_names(self, validator):
        """Test filename validation rejects reserved names."""
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]

        for name in reserved_names:
            with pytest.raises(ValidationError, match="Reserved filename"):
                validator.validate_filename(name)

            # Test case-insensitive
            with pytest.raises(ValidationError, match="Reserved filename"):
                validator.validate_filename(name.lower())

    def test_validate_filename_hidden_allowed(self, validator):
        """Test filename validation allows hidden files when permitted."""
        result = validator.validate_filename(".hidden", allow_hidden=True)
        assert result == ".hidden"

    def test_validate_filename_hidden_disallowed(self, validator):
        """Test filename validation rejects hidden files when not permitted."""
        with pytest.raises(ValidationError, match="Hidden files not allowed"):
            validator.validate_filename(".hidden", allow_hidden=False)

    def test_validate_command_basic(self, validator):
        """Test basic command validation."""
        result = validator.validate_command("ls -la")
        assert result == "ls -la"

    def test_validate_command_empty(self, validator):
        """Test command validation rejects empty command."""
        with pytest.raises(CommandValidationError, match="Command cannot be empty"):
            validator.validate_command("")

        with pytest.raises(CommandValidationError, match="Command cannot be empty"):
            validator.validate_command("   ")

    def test_validate_command_too_long(self, validator):
        """Test command validation rejects overly long command."""
        long_command = "echo " + "a" * validator.MAX_COMMAND_LENGTH

        with pytest.raises(CommandValidationError, match="Command too long"):
            validator.validate_command(long_command)

    def test_validate_command_dangerous_patterns(self, validator):
        """Test command validation rejects dangerous patterns."""
        dangerous_commands = [
            "ls; rm -rf /",
            "ls && dangerous",
            "ls | dangerous",
            "ls `whoami`",
            "ls $(whoami)",
            "ls > /etc/passwd",
            "ls < /etc/passwd",
            "sudo rm file",
            "su root",
            "rm -rf /",
            "chmod 777 file",
        ]

        for cmd in dangerous_commands:
            with pytest.raises(CommandValidationError, match="Dangerous pattern"):
                validator.validate_command(cmd)

    def test_validate_command_allowed_commands(self, validator):
        """Test command validation with allowed commands list."""
        allowed = {"ls", "cat", "echo"}

        # Should allow commands in the list
        result = validator.validate_command("ls -la", allowed_commands=allowed)
        assert result == "ls -la"

        # Should reject commands not in the list
        with pytest.raises(CommandValidationError, match="Command not allowed"):
            validator.validate_command("rm file", allowed_commands=allowed)

    def test_validate_configuration_basic(self, validator):
        """Test basic configuration validation."""
        config = {"setting1": "value1", "setting2": {"nested": "value2"}}

        result = validator.validate_configuration(config)
        assert result == config

    def test_validate_configuration_not_dict(self, validator):
        """Test configuration validation rejects non-dict."""
        with pytest.raises(ValidationError, match="Configuration must be a dictionary"):
            validator.validate_configuration("not a dict")

    def test_validate_configuration_too_many_items(self, validator):
        """Test configuration validation rejects too many items."""
        # Create config with too many items
        large_config = {f"key{i}": f"value{i}" for i in range(1001)}

        with pytest.raises(ValidationError, match="Too many configuration items"):
            validator.validate_configuration(large_config, max_items=1000)

    def test_validate_configuration_too_deep(self, validator):
        """Test configuration validation rejects overly deep nesting."""
        # Create deeply nested config
        deep_config = {}
        current = deep_config
        for _i in range(15):
            current["level"] = {}
            current = current["level"]

        with pytest.raises(ValidationError, match="Configuration too deeply nested"):
            validator.validate_configuration(deep_config, max_depth=10)

    def test_validate_url_basic(self, validator):
        """Test basic URL validation."""
        valid_urls = [
            "http://example.com",
            "https://example.com",
            "https://api.example.com/v1/endpoint",
            "http://localhost:8080",
            "https://192.168.1.1:3000",
        ]

        for url in valid_urls:
            result = validator.validate_url(url)
            assert result == url

    def test_validate_url_empty(self, validator):
        """Test URL validation rejects empty URL."""
        with pytest.raises(ValidationError, match="URL cannot be empty"):
            validator.validate_url("")

    def test_validate_url_invalid_format(self, validator):
        """Test URL validation rejects invalid formats."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                validator.validate_url(url)

    def test_validate_url_dangerous_protocols(self, validator):
        """Test URL validation rejects dangerous protocols."""
        dangerous_urls = [
            "ftp://example.com",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/plain,dangerous",
        ]

        for url in dangerous_urls:
            with pytest.raises(ValidationError):
                validator.validate_url(url)

    def test_sanitize_string_basic(self, validator):
        """Test basic string sanitization."""
        result = validator.sanitize_string("normal text")
        assert result == "normal text"

    def test_sanitize_string_empty(self, validator):
        """Test string sanitization with empty string."""
        result = validator.sanitize_string("")
        assert result == ""

    def test_sanitize_string_control_chars(self, validator):
        """Test string sanitization removes control characters."""
        text_with_control = "text\x00with\x01control\x1fchars"
        result = validator.sanitize_string(text_with_control)
        assert result == "textwithcontrolchars"

    def test_sanitize_string_max_length(self, validator):
        """Test string sanitization respects max length."""
        long_text = "a" * 100
        result = validator.sanitize_string(long_text, max_length=50)
        assert len(result) == 50
        assert result == "a" * 50

    def test_sanitize_string_allowed_chars(self, validator):
        """Test string sanitization with allowed characters."""
        text = "abc123!@#"
        allowed_pattern = re.compile(r"[a-zA-Z0-9]")

        result = validator.sanitize_string(text, allowed_chars=allowed_pattern)
        assert result == "abc123"

    def test_validate_file_extension_safe(self, validator):
        """Test file extension validation allows safe extensions."""
        safe_paths = [
            Path("file.json"),
            Path("file.yml"),
            Path("file.yaml"),
            Path("file.md"),
            Path("file.txt"),
            Path("file.conf"),
            Path("file.toml"),
        ]

        for path in safe_paths:
            # Should not raise exception
            validator._validate_file_extension(path)

    def test_validate_file_extension_blocked(self, validator):
        """Test file extension validation blocks dangerous extensions."""
        dangerous_paths = [
            Path("file.exe"),
            Path("file.dll"),
            Path("file.so"),
            Path("file.scr"),
            Path("file.com"),
            Path("file.vbs"),
        ]

        for path in dangerous_paths:
            with pytest.raises(PathValidationError, match="Blocked file extension"):
                validator._validate_file_extension(path)

    def test_validate_file_extension_unknown(self, validator):
        """Test file extension validation warns about unknown extensions."""
        unknown_path = Path("file.unknown")

        with pytest.raises(PathValidationError, match="Potentially unsafe file extension"):
            validator._validate_file_extension(unknown_path)

    def test_validate_file_extension_no_extension(self, validator):
        """Test file extension validation allows files without extensions."""
        no_ext_path = Path("file")

        # Should not raise exception
        validator._validate_file_extension(no_ext_path)


class TestValidationConfig:
    """Test ValidationConfig model."""

    def test_default_config(self):
        """Test default validation configuration."""
        config = ValidationConfig()

        assert config.strict_mode is True
        assert config.max_path_length == 4096
        assert config.max_filename_length == 255
        assert config.max_command_length == 8192
        assert ".json" in config.allowed_extensions
        assert ".exe" in config.blocked_extensions

    def test_custom_config(self):
        """Test custom validation configuration."""
        config = ValidationConfig(
            strict_mode=False,
            max_path_length=1000,
            allowed_extensions=[".txt", ".md"],
            blocked_extensions=[".exe", ".bat"],
            dangerous_patterns=["custom_pattern"],
        )

        assert config.strict_mode is False
        assert config.max_path_length == 1000
        assert config.allowed_extensions == [".txt", ".md"]
        assert config.blocked_extensions == [".exe", ".bat"]
        assert config.dangerous_patterns == ["custom_pattern"]


class TestValidationIntegration:
    """Integration tests for input validation."""

    @pytest.fixture
    def validator(self):
        """Create InputValidator instance."""
        return InputValidator()

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_validate_myai_config_path(self, validator, temp_dir):
        """Test validating typical MyAI configuration paths."""
        myai_dir = temp_dir / ".myai"
        config_dir = myai_dir / "config"
        config_file = config_dir / "global.json"

        config_file.parent.mkdir(parents=True)
        config_file.write_text("{}")

        # Should validate successfully
        result = validator.validate_path(config_file, must_exist=True, allowed_parents=[myai_dir])
        assert result == config_file.resolve()

    def test_validate_agent_file_path(self, validator, temp_dir):
        """Test validating agent file paths."""
        agents_dir = temp_dir / ".myai" / "agents"
        agent_file = agents_dir / "engineering" / "developer.md"

        agent_file.parent.mkdir(parents=True)
        agent_file.write_text("# Developer Agent")

        # Should validate successfully
        result = validator.validate_path(agent_file, must_exist=True, allowed_parents=[agents_dir])
        assert result == agent_file.resolve()

    def test_comprehensive_input_validation(self, validator):
        """Test comprehensive input validation scenario."""
        # Validate a complex configuration
        config = {
            "metadata": {"version": "1.0.0", "created_by": "user@example.com"},
            "settings": {"debug": False, "backup_count": 5, "nested": {"deep": {"value": "test"}}},
        }

        # Should validate successfully
        result = validator.validate_configuration(config)
        assert result == config

        # Validate related command
        command = "myai config set settings.debug true"
        cmd_result = validator.validate_command(command, allowed_commands={"myai"})
        assert cmd_result == command

        # Validate URL
        url = "https://api.myai.example.com/v1/config"
        url_result = validator.validate_url(url)
        assert url_result == url
