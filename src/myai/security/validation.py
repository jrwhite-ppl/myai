"""
Input validation framework for MyAI.

This module provides comprehensive input validation for paths, commands,
configuration data, and other user inputs to prevent security vulnerabilities.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Set, Union

from pydantic import BaseModel


class ValidationError(Exception):
    """Exception raised for validation failures."""

    pass


class PathValidationError(ValidationError):
    """Exception raised for path validation failures."""

    pass


class CommandValidationError(ValidationError):
    """Exception raised for command validation failures."""

    pass


class InputValidator:
    """Comprehensive input validator for security-critical operations."""

    def __init__(self):
        """Initialize the input validator."""
        # Dangerous path patterns
        self._dangerous_patterns = [
            r"\.\.+",  # Directory traversal
            r"~[^/]*",  # User home references
            r"\$\{.*\}",  # Variable substitution
            r"`.*`",  # Command substitution
            r"\|",  # Pipe operations
            r";",  # Command chaining
            r"&",  # Background execution
            r">",  # Redirection
            r"<",  # Input redirection
        ]

        # Compile patterns for performance
        self._compiled_patterns = [re.compile(pattern) for pattern in self._dangerous_patterns]

        # Allowed file extensions
        self._safe_extensions = {
            ".json",
            ".yml",
            ".yaml",
            ".md",
            ".txt",
            ".conf",
            ".cfg",
            ".ini",
            ".toml",
            ".py",
            ".sh",
            ".bat",
            ".ps1",
        }

        # Blocked file extensions
        self._blocked_extensions = {
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".scr",
            ".com",
            ".pif",
            ".cmd",
            ".vbs",
            ".js",
            ".jar",
            ".class",
        }

        # Maximum lengths
        self.MAX_PATH_LENGTH = 4096
        self.MAX_FILENAME_LENGTH = 255
        self.MAX_COMMAND_LENGTH = 8192
        self.MAX_CONFIG_SIZE = 10 * 1024 * 1024  # 10MB

    def validate_path(
        self,
        path: Union[str, Path],
        *,
        must_exist: bool = False,
        must_be_relative: bool = False,
        must_be_absolute: bool = False,
        allowed_parents: Optional[List[Path]] = None,
    ) -> Path:
        """
        Validate a file or directory path.

        Args:
            path: Path to validate
            must_exist: Whether the path must exist
            must_be_relative: Whether the path must be relative
            must_be_absolute: Whether the path must be absolute
            allowed_parents: List of allowed parent directories

        Returns:
            Validated Path object

        Raises:
            PathValidationError: If validation fails
        """
        # Convert to Path object
        if isinstance(path, str):
            path_obj = Path(path)
        else:
            path_obj = path

        path_str = str(path_obj)

        # Check length limits
        if len(path_str) > self.MAX_PATH_LENGTH:
            msg = f"Path too long: {len(path_str)} > {self.MAX_PATH_LENGTH}"
            raise PathValidationError(msg)

        if len(path_obj.name) > self.MAX_FILENAME_LENGTH:
            msg = f"Filename too long: {len(path_obj.name)} > {self.MAX_FILENAME_LENGTH}"
            raise PathValidationError(msg)

        # Check for dangerous patterns
        for pattern in self._compiled_patterns:
            if pattern.search(path_str):
                msg = f"Dangerous pattern detected in path: {path_str}"
                raise PathValidationError(msg)

        # Check for null bytes
        if "\x00" in path_str:
            msg = f"Null byte detected in path: {path_str}"
            raise PathValidationError(msg)

        # Check relative/absolute requirements
        if must_be_relative and path_obj.is_absolute():
            msg = f"Path must be relative: {path_str}"
            raise PathValidationError(msg)

        if must_be_absolute and not path_obj.is_absolute():
            msg = f"Path must be absolute: {path_str}"
            raise PathValidationError(msg)

        # Resolve path to normalize it
        try:
            if path_obj.is_absolute():
                resolved_path = path_obj.resolve()
            else:
                # For relative paths, resolve from current directory
                resolved_path = (Path.cwd() / path_obj).resolve()
        except OSError as e:
            msg = f"Failed to resolve path {path_str}: {e}"
            raise PathValidationError(msg) from e

        # Check if path exists when required
        if must_exist and not resolved_path.exists():
            msg = f"Path does not exist: {path_str}"
            raise PathValidationError(msg)

        # Check allowed parents
        if allowed_parents:
            parent_allowed = False
            for allowed_parent in allowed_parents:
                try:
                    resolved_path.relative_to(allowed_parent.resolve())
                    parent_allowed = True
                    break
                except ValueError:
                    continue

            if not parent_allowed:
                msg = f"Path not under allowed parents: {path_str}"
                raise PathValidationError(msg)

        # Check file extension if it's a file
        if resolved_path.is_file() or (not resolved_path.exists() and path_obj.suffix):
            self._validate_file_extension(path_obj)

        return resolved_path

    def validate_filename(self, filename: str, *, allow_hidden: bool = True) -> str:
        """
        Validate a filename.

        Args:
            filename: Filename to validate
            allow_hidden: Whether to allow hidden files (starting with .)

        Returns:
            Validated filename

        Raises:
            ValidationError: If validation fails
        """
        if not filename:
            msg = "Filename cannot be empty"
            raise ValidationError(msg)

        if len(filename) > self.MAX_FILENAME_LENGTH:
            msg = f"Filename too long: {len(filename)} > {self.MAX_FILENAME_LENGTH}"
            raise ValidationError(msg)

        # Check for dangerous characters
        dangerous_chars = set('<>:"|?*\x00')
        if any(char in filename for char in dangerous_chars):
            msg = f"Dangerous characters in filename: {filename}"
            raise ValidationError(msg)

        # Check for reserved names (Windows)
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if filename.upper() in reserved_names:
            msg = f"Reserved filename: {filename}"
            raise ValidationError(msg)

        # Check hidden files
        if not allow_hidden and filename.startswith("."):
            msg = f"Hidden files not allowed: {filename}"
            raise ValidationError(msg)

        return filename

    def validate_command(self, command: str, allowed_commands: Optional[Set[str]] = None) -> str:
        """
        Validate a command string.

        Args:
            command: Command to validate
            allowed_commands: Set of allowed command names

        Returns:
            Validated command

        Raises:
            CommandValidationError: If validation fails
        """
        if not command or not command.strip():
            msg = "Command cannot be empty"
            raise CommandValidationError(msg)

        if len(command) > self.MAX_COMMAND_LENGTH:
            msg = f"Command too long: {len(command)} > {self.MAX_COMMAND_LENGTH}"
            raise CommandValidationError(msg)

        # Check for dangerous patterns
        dangerous_patterns = [
            r"[;&|`$()]",  # Command injection
            r">\s*[/\\]",  # File redirection
            r"<\s*[/\\]",  # Input redirection
            r"\|\s*\w+",  # Piping
            r"sudo|su\s",  # Privilege escalation
            r"rm\s+-rf",  # Destructive commands
            r"chmod\s+777",  # Dangerous permissions
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                msg = f"Dangerous pattern in command: {command}"
                raise CommandValidationError(msg)

        # Extract command name
        command_parts = command.strip().split()
        if not command_parts:
            msg = "No command found"
            raise CommandValidationError(msg)

        command_name = command_parts[0].lower()

        # Check against allowed commands
        if allowed_commands and command_name not in allowed_commands:
            msg = f"Command not allowed: {command_name}"
            raise CommandValidationError(msg)

        return command

    def validate_configuration(
        self, config_data: Dict[str, Any], max_depth: int = 10, max_items: int = 1000
    ) -> Dict[str, Any]:
        """
        Validate configuration data.

        Args:
            config_data: Configuration dictionary to validate
            max_depth: Maximum nesting depth
            max_items: Maximum number of items

        Returns:
            Validated configuration

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(config_data, dict):
            msg = "Configuration must be a dictionary"
            raise ValidationError(msg)

        # Check size limits
        total_items = self._count_dict_items(config_data)
        if total_items > max_items:
            msg = f"Too many configuration items: {total_items} > {max_items}"
            raise ValidationError(msg)

        # Check depth
        actual_depth = self._get_dict_depth(config_data)
        if actual_depth > max_depth:
            msg = f"Configuration too deeply nested: {actual_depth} > {max_depth}"
            raise ValidationError(msg)

        # Validate individual values
        self._validate_config_values(config_data)

        return config_data

    def validate_url(self, url: str) -> str:
        """
        Validate a URL.

        Args:
            url: URL to validate

        Returns:
            Validated URL

        Raises:
            ValidationError: If validation fails
        """
        if not url or not url.strip():
            msg = "URL cannot be empty"
            raise ValidationError(msg)

        # Basic URL pattern
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(url):
            msg = f"Invalid URL format: {url}"
            raise ValidationError(msg)

        # Block dangerous protocols
        if not url.lower().startswith(("http://", "https://")):
            msg = f"Only HTTP/HTTPS URLs allowed: {url}"
            raise ValidationError(msg)

        return url

    def sanitize_string(
        self, text: str, max_length: Optional[int] = None, allowed_chars: Optional[Pattern] = None
    ) -> str:
        """
        Sanitize a string by removing dangerous characters.

        Args:
            text: Text to sanitize
            max_length: Maximum allowed length
            allowed_chars: Regex pattern for allowed characters

        Returns:
            Sanitized string
        """
        if not text:
            return ""

        # Remove null bytes and control characters
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Apply character filter if provided
        if allowed_chars:
            sanitized = "".join(char for char in sanitized if allowed_chars.match(char))

        # Truncate if needed
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized

    def _validate_file_extension(self, path: Path) -> None:
        """Validate file extension."""
        extension = path.suffix.lower()

        if extension in self._blocked_extensions:
            msg = f"Blocked file extension: {extension}"
            raise PathValidationError(msg)

        # Allow files without extensions or with safe extensions
        if extension and extension not in self._safe_extensions:
            msg = f"Potentially unsafe file extension: {extension}"
            raise PathValidationError(msg)

    def _count_dict_items(self, data: Dict[str, Any], depth: int = 0) -> int:
        """Count total items in nested dictionary."""
        count = len(data)

        for value in data.values():
            if isinstance(value, dict):
                count += self._count_dict_items(value, depth + 1)
            elif isinstance(value, list):
                count += len(value)

        return count

    def _get_dict_depth(self, data: Dict[str, Any], depth: int = 0) -> int:
        """Get maximum depth of nested dictionary."""
        if not isinstance(data, dict):
            return depth

        max_depth = depth
        for value in data.values():
            if isinstance(value, dict):
                max_depth = max(max_depth, self._get_dict_depth(value, depth + 1))

        return max_depth

    def _validate_config_values(self, data: Dict[str, Any]) -> None:
        """Validate configuration values recursively."""
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                msg = f"Configuration key must be string: {type(key)}"
                raise ValidationError(msg)

            max_key_length = 100
            if len(key) > max_key_length:
                msg = f"Configuration key too long: {len(key)}"
                raise ValidationError(msg)

            # Validate value based on type
            if isinstance(value, str):
                max_string_length = 10000  # 10KB limit for string values
                if len(value) > max_string_length:
                    msg = f"Configuration value too long: {len(value)}"
                    raise ValidationError(msg)
            elif isinstance(value, dict):
                self._validate_config_values(value)
            elif isinstance(value, list):
                max_list_length = 1000
                if len(value) > max_list_length:
                    msg = f"Configuration list too long: {len(value)}"
                    raise ValidationError(msg)


class ValidationConfig(BaseModel):
    """Configuration for input validation."""

    strict_mode: bool = True
    max_path_length: int = 4096
    max_filename_length: int = 255
    max_command_length: int = 8192
    allowed_extensions: List[str] = []
    blocked_extensions: List[str] = []
    dangerous_patterns: List[str] = []

    def __init__(self, **data):
        """Initialize with default values."""
        if "allowed_extensions" not in data:
            data["allowed_extensions"] = [".json", ".yml", ".yaml", ".md", ".txt", ".conf", ".cfg", ".ini", ".toml"]
        if "blocked_extensions" not in data:
            data["blocked_extensions"] = [".exe", ".dll", ".so", ".dylib", ".scr", ".com", ".pif", ".cmd", ".vbs"]
        super().__init__(**data)
