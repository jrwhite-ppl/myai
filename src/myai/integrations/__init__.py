"""
Integration framework for MyAI tool adapters.

This module provides the foundation for integrating with external tools
like Claude Code, Cursor, Agent-OS, and others.
"""

from myai.integrations.base import AbstractAdapter, AdapterError, AdapterRegistry
from myai.integrations.factory import AdapterFactory
from myai.integrations.manager import IntegrationManager


# Register built-in adapters
def register_builtin_adapters():
    """Register all built-in adapters."""
    try:
        from myai.integrations.claude import register_claude_adapter

        register_claude_adapter()
    except ImportError:
        pass  # Optional dependency

    try:
        from myai.integrations.cursor import register_cursor_adapter

        register_cursor_adapter()
    except ImportError:
        pass  # Optional dependency

    try:
        from myai.integrations.agentos import register_agentos_adapter

        register_agentos_adapter()
    except ImportError:
        pass  # Optional dependency


# Auto-register adapters when module is imported
register_builtin_adapters()

__all__ = [
    "AbstractAdapter",
    "AdapterError",
    "AdapterRegistry",
    "AdapterFactory",
    "IntegrationManager",
]
