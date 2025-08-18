"""
Base adapter interface and registry for tool integrations.

This module defines the core interfaces that all tool adapters must implement,
providing a consistent API for managing external tool integrations.
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel


class AdapterStatus(Enum):
    """Adapter status enumeration."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


class AdapterCapability(Enum):
    """Adapter capability enumeration."""

    READ_CONFIG = "read_config"
    WRITE_CONFIG = "write_config"
    SYNC_AGENTS = "sync_agents"
    DETECT_CHANGES = "detect_changes"
    BACKUP_RESTORE = "backup_restore"
    VALIDATION = "validation"
    MIGRATION = "migration"


class AdapterInfo(BaseModel):
    """Adapter information and metadata."""

    name: str
    display_name: str
    description: str
    version: str
    tool_name: str
    tool_version: Optional[str] = None
    capabilities: Set[AdapterCapability] = set()
    status: AdapterStatus = AdapterStatus.UNKNOWN
    config_path: Optional[Path] = None
    installation_path: Optional[Path] = None
    last_sync: Optional[str] = None
    error_message: Optional[str] = None


class AdapterError(Exception):
    """Base exception for adapter-related errors."""

    def __init__(self, message: str, adapter_name: str = "", error_code: Optional[str] = None):
        self.adapter_name = adapter_name
        self.error_code = error_code
        super().__init__(message)


class AdapterConfigError(AdapterError):
    """Exception for adapter configuration errors."""

    pass


class AdapterConnectionError(AdapterError):
    """Exception for adapter connection errors."""

    pass


class AbstractAdapter(ABC):
    """
    Abstract base class for all tool adapters.

    This class defines the interface that all tool adapters must implement
    to provide consistent integration with external tools.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._info: Optional[AdapterInfo] = None
        self._initialized = False

    @property
    @abstractmethod
    def info(self) -> AdapterInfo:
        """Get adapter information and status."""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the adapter.

        Returns:
            True if initialization was successful, False otherwise.
        """
        pass

    @abstractmethod
    async def detect_installation(self) -> bool:
        """
        Detect if the target tool is installed.

        Returns:
            True if the tool is detected, False otherwise.
        """
        pass

    @abstractmethod
    async def get_status(self) -> AdapterStatus:
        """
        Get the current status of the adapter.

        Returns:
            Current adapter status.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the adapter.

        Returns:
            Dictionary containing health check results.
        """
        pass

    @abstractmethod
    async def get_configuration(self) -> Dict[str, Any]:
        """
        Get the current tool configuration.

        Returns:
            Dictionary containing the tool's configuration.
        """
        pass

    @abstractmethod
    async def set_configuration(self, config: Dict[str, Any]) -> bool:
        """
        Set the tool configuration.

        Args:
            config: Configuration dictionary to apply.

        Returns:
            True if configuration was applied successfully, False otherwise.
        """
        pass

    @abstractmethod
    async def sync_agents(self, agents: List[Any], *, dry_run: bool = False) -> Dict[str, Any]:
        """
        Sync agents to the target tool.

        Args:
            agents: List of agents to sync.
            dry_run: If True, perform a dry run without making changes.

        Returns:
            Dictionary containing sync results.
        """
        pass

    @abstractmethod
    async def import_agents(self) -> List[Any]:
        """
        Import agents from the target tool.

        Returns:
            List of imported agents.
        """
        pass

    @abstractmethod
    async def validate_configuration(self) -> List[str]:
        """
        Validate the current configuration.

        Returns:
            List of validation errors, empty if valid.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """
        Clean up adapter resources.

        Returns:
            True if cleanup was successful, False otherwise.
        """
        pass

    # Optional methods with default implementations

    async def backup(self) -> Optional[Path]:
        """
        Create a backup of the tool's configuration.

        Returns:
            Path to the backup file, or None if not supported.
        """
        return None

    async def restore(self, backup_path: Path) -> bool:
        """
        Restore configuration from a backup.

        Args:
            backup_path: Path to the backup file.

        Returns:
            True if restoration was successful, False otherwise.
        """
        _ = backup_path  # Mark as intentionally unused
        return False

    async def get_version_info(self) -> Optional[str]:
        """
        Get version information for the target tool.

        Returns:
            Version string, or None if not available.
        """
        return None

    async def migrate_from(self, source_adapter: "AbstractAdapter") -> Dict[str, Any]:
        """
        Migrate configuration and agents from another adapter.

        Args:
            source_adapter: Source adapter to migrate from.

        Returns:
            Dictionary containing migration results.
        """
        _ = source_adapter  # Mark as intentionally unused
        return {"migrated": 0, "errors": [], "warnings": []}


class AdapterRegistry:
    """Registry for managing adapter instances."""

    def __init__(self):
        self._adapters: Dict[str, AbstractAdapter] = {}
        self._adapter_classes: Dict[str, type] = {}

    def register_adapter_class(self, name: str, adapter_class: type) -> None:
        """Register an adapter class."""
        if not issubclass(adapter_class, AbstractAdapter):
            msg = "Adapter class must inherit from AbstractAdapter"
            raise ValueError(msg)
        self._adapter_classes[name] = adapter_class

    def create_adapter(self, name: str, config: Optional[Dict[str, Any]] = None) -> AbstractAdapter:
        """Create an adapter instance."""
        if name not in self._adapter_classes:
            msg = f"Unknown adapter: {name}"
            raise ValueError(msg)

        adapter_class = self._adapter_classes[name]
        adapter = adapter_class(name, config)
        self._adapters[name] = adapter
        return adapter

    def get_adapter(self, name: str) -> Optional[AbstractAdapter]:
        """Get an adapter instance."""
        return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        """List all registered adapter names."""
        return list(self._adapter_classes.keys())

    def list_active_adapters(self) -> List[str]:
        """List all active adapter instances."""
        return list(self._adapters.keys())

    def remove_adapter(self, name: str) -> bool:
        """Remove an adapter instance."""
        if name in self._adapters:
            del self._adapters[name]
            return True
        return False

    def clear(self) -> None:
        """Clear all adapters."""
        self._adapters.clear()


# Global adapter registry instance
_adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry instance."""
    return _adapter_registry
