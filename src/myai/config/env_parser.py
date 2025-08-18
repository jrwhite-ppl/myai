"""
Environment variable parser for MyAI configuration.

This module provides advanced environment variable expansion with support for:
- ${VAR} and $VAR syntax
- Default values: ${VAR:-default}
- Recursive expansion
- .env file loading
- Circular reference detection
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected in environment variables."""

    def __init__(self, variables: Set[str]):
        self.variables = variables
        super().__init__(f"Circular reference detected in variables: {', '.join(sorted(variables))}")


class EnvParser:
    """Advanced environment variable parser with support for complex syntax."""

    # Regex patterns for variable matching
    VAR_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")  # $VAR
    BRACE_PATTERN = re.compile(r"\$\{([^}]+)\}")  # ${VAR} or ${VAR:-default}
    DEFAULT_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?::-(.*))?$")  # VAR or VAR:-default

    def __init__(self, env_vars: Optional[Dict[str, str]] = None, *, load_dotenv: bool = True):
        """
        Initialize environment variable parser.

        Args:
            env_vars: Custom environment variables to use (defaults to os.environ)
            load_dotenv: Whether to load .env files automatically
        """
        self.env_vars = env_vars if env_vars is not None else dict(os.environ)

        if load_dotenv:
            self._load_env_files()

    def _load_env_files(self) -> None:
        """Load environment variables from .env files."""
        # Look for .env files in current directory and parent directories
        current_dir = Path.cwd()
        for path in [current_dir, *current_dir.parents]:
            env_file = path / ".env"
            if env_file.exists():
                self._load_env_file(env_file)
                break

        # Also check for MyAI-specific .env files
        myai_home = Path.home() / ".myai"
        for env_file in [myai_home / ".env", myai_home / "config" / ".env"]:
            if env_file.exists():
                self._load_env_file(env_file)

    def _load_env_file(self, env_file: Path) -> None:
        """Load variables from a single .env file."""
        try:
            content = env_file.read_text(encoding="utf-8")
            for raw_line in content.splitlines():
                line = raw_line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=VALUE format
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    # Only set if not already in environment
                    if key not in self.env_vars:
                        self.env_vars[key] = value

        except Exception as e:
            # Don't fail silently, but don't crash the application
            print(f"Warning: Could not load .env file {env_file}: {e}")

    def expand(self, value: Any) -> Any:
        """
        Expand environment variables in a value.

        Args:
            value: Value to expand (string, dict, list, or other)

        Returns:
            Expanded value with environment variables substituted

        Raises:
            CircularReferenceError: If circular references are detected
        """
        if isinstance(value, str):
            return self._expand_string(value)
        elif isinstance(value, dict):
            return {k: self.expand(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.expand(item) for item in value]
        else:
            return value

    def _expand_string(self, text: str, visited: Optional[Set[str]] = None) -> str:
        """
        Expand environment variables in a string with circular reference detection.

        Args:
            text: String to expand
            visited: Set of variables currently being expanded (for circular detection)

        Returns:
            Expanded string
        """
        if visited is None:
            visited = set()

        original_text = text

        # Track whether we made any substitutions
        changed = True
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            # Expand ${VAR} and ${VAR:-default} patterns
            for match in self.BRACE_PATTERN.finditer(text):
                full_match = match.group(0)
                var_expr = match.group(1)

                # Check for circular reference
                if var_expr in visited:
                    raise CircularReferenceError(visited | {var_expr})

                # Parse variable name and default value
                default_match = self.DEFAULT_PATTERN.match(var_expr)
                if default_match:
                    var_name = default_match.group(1)
                    default_value = default_match.group(2) or ""
                else:
                    var_name = var_expr
                    default_value = ""

                # Get variable value
                if var_name in self.env_vars:
                    var_value = self.env_vars[var_name]

                    # Recursively expand the value
                    new_visited = visited | {var_name}
                    var_value = self._expand_string(var_value, new_visited)
                else:
                    var_value = default_value

                # Substitute in text
                text = text.replace(full_match, var_value)
                changed = True

            # Expand $VAR patterns (without braces)
            for match in self.VAR_PATTERN.finditer(text):
                full_match = match.group(0)
                var_name = match.group(1)

                # Skip if this is part of a ${} expression
                start_pos = match.start()
                if start_pos > 0 and text[start_pos - 1] == "{":
                    continue

                # Check for circular reference
                if var_name in visited:
                    raise CircularReferenceError(visited | {var_name})

                # Get variable value
                if var_name in self.env_vars:
                    var_value = self.env_vars[var_name]

                    # Recursively expand the value
                    new_visited = visited | {var_name}
                    var_value = self._expand_string(var_value, new_visited)

                    # Substitute in text
                    text = text.replace(full_match, var_value)
                    changed = True

        # If we hit max iterations, warn about potential issues
        if iteration >= max_iterations:
            print(f"Warning: Maximum expansion iterations reached for: {original_text}")

        return text

    def validate_expansion(self, text: str) -> Dict[str, Any]:
        """
        Validate that all variables in a string can be expanded.

        Args:
            text: String to validate

        Returns:
            Dictionary with validation results:
            - valid: boolean indicating if all variables can be resolved
            - missing_vars: list of missing variable names
            - circular_refs: list of variables involved in circular references
            - expanded: the expanded string if valid
        """
        result: Dict[str, Any] = {"valid": True, "missing_vars": [], "circular_refs": [], "expanded": text}

        try:
            # Find all variables in the text
            all_vars = set()

            # Find ${VAR} patterns
            for match in self.BRACE_PATTERN.finditer(text):
                var_expr = match.group(1)
                default_match = self.DEFAULT_PATTERN.match(var_expr)
                if default_match:
                    var_name = default_match.group(1)
                else:
                    var_name = var_expr
                all_vars.add(var_name)

            # Find $VAR patterns
            for match in self.VAR_PATTERN.finditer(text):
                var_name = match.group(1)
                all_vars.add(var_name)

            # Check for missing variables
            for var_name in all_vars:
                if var_name not in self.env_vars:
                    # Check if it has a default value in ${VAR:-default} format
                    has_default = False
                    for match in self.BRACE_PATTERN.finditer(text):
                        var_expr = match.group(1)
                        default_match = self.DEFAULT_PATTERN.match(var_expr)
                        if default_match and default_match.group(1) == var_name and default_match.group(2) is not None:
                            has_default = True
                            break

                    if not has_default:
                        result["missing_vars"].append(var_name)
                        result["valid"] = False

            # Try expansion to check for circular references
            if result["valid"]:
                result["expanded"] = self._expand_string(text)

        except CircularReferenceError as e:
            result["valid"] = False
            result["circular_refs"] = list(e.variables)

        return result

    def get_env_vars(self) -> Dict[str, str]:
        """Get all available environment variables."""
        return self.env_vars.copy()

    def set_env_var(self, key: str, value: str) -> None:
        """Set an environment variable."""
        self.env_vars[key] = value

    def update_env_vars(self, variables: Dict[str, str]) -> None:
        """Update multiple environment variables."""
        self.env_vars.update(variables)


# Global instance for convenience
_default_parser: Optional[EnvParser] = None


def get_env_parser(*, reload: bool = False) -> EnvParser:
    """Get the global environment parser instance."""
    global _default_parser  # noqa: PLW0603
    if _default_parser is None or reload:
        _default_parser = EnvParser()
    return _default_parser


def expand_env_vars(value: Any) -> Any:
    """Convenience function to expand environment variables using the default parser."""
    return get_env_parser().expand(value)
