"""
Application state management for MyAI CLI.

This module provides global state management for the CLI application,
including configuration options and runtime settings.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AppState:
    """Global application state for CLI commands."""

    # Debug and logging options
    debug: bool = False
    verbose: bool = False

    # Configuration options
    config_path: Optional[Path] = None

    # Output formatting
    output_format: str = "table"  # table, json

    # Runtime data
    context: Dict[str, Any] = field(default_factory=dict)

    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self.debug

    def is_verbose(self) -> bool:
        """Check if verbose mode is enabled."""
        return self.verbose or self.debug

    def set_context(self, key: str, value: Any) -> None:
        """Set context value."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value."""
        return self.context.get(key, default)
