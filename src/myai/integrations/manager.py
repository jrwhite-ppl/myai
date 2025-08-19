"""
Integration manager for coordinating tool adapters.

This module provides high-level management of tool integrations,
including lifecycle management, synchronization, and health monitoring.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from myai.integrations.base import AbstractAdapter, AdapterStatus
from myai.integrations.factory import get_adapter_factory


class IntegrationManager:
    """High-level manager for tool integrations."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self.factory = get_adapter_factory()
        self._adapters: Dict[str, AbstractAdapter] = {}
        self._last_sync: Dict[str, datetime] = {}
        self._sync_in_progress = False

    async def initialize(self, adapter_types: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Initialize specified adapters or discover and initialize all available ones.

        Args:
            adapter_types: List of adapter types to initialize. If None, discover all.

        Returns:
            Dictionary mapping adapter names to initialization success status.
        """
        results = {}

        if adapter_types is None:
            # Discover all available adapters
            discovered = await self.factory.discover_adapters()
            adapter_types = [name for name, info in discovered.items() if "error" not in info]

        for adapter_type in adapter_types:
            try:
                adapter = await self.factory.initialize_adapter(adapter_type)
                self._adapters[adapter_type] = adapter
                results[adapter_type] = True
            except Exception as e:
                results[adapter_type] = False
                # Log error (implement logging later)
                print(f"Failed to initialize {adapter_type}: {e}")

        return results

    async def get_adapter_status(self, adapter_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get status of adapters.

        Args:
            adapter_name: Specific adapter to check, or None for all.

        Returns:
            Dictionary mapping adapter names to their status information.
        """
        results = {}

        adapters_to_check = [adapter_name] if adapter_name else list(self._adapters.keys())

        for name in adapters_to_check:
            if name in self._adapters:
                adapter = self._adapters[name]
                try:
                    status = await adapter.get_status()
                    info = adapter.info
                    results[name] = {
                        "status": status.value,
                        "display_name": info.display_name,
                        "tool_name": info.tool_name,
                        "tool_version": info.tool_version,
                        "capabilities": [cap.value for cap in info.capabilities],
                        "last_sync": self._last_sync.get(name),
                        "config_path": str(info.config_path) if info.config_path else None,
                    }
                except Exception as e:
                    results[name] = {
                        "status": "error",
                        "error": str(e),
                    }

        return results

    async def health_check(self, adapter_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on adapters.

        Args:
            adapter_name: Specific adapter to check, or None for all.

        Returns:
            Dictionary mapping adapter names to health check results.
        """
        results = {}

        adapters_to_check = [adapter_name] if adapter_name else list(self._adapters.keys())

        for name in adapters_to_check:
            if name in self._adapters:
                adapter = self._adapters[name]
                try:
                    health = await adapter.health_check()
                    results[name] = health
                except Exception as e:
                    results[name] = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

        return results

    async def sync_agents(
        self, agents: List[Any], adapter_names: Optional[List[str]] = None, *, dry_run: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        Sync agents to specified adapters.

        Args:
            agents: List of agents to sync.
            adapter_names: Specific adapters to sync to, or None for all.
            dry_run: If True, perform a dry run without making changes.

        Returns:
            Dictionary mapping adapter names to sync results.
        """
        if self._sync_in_progress:
            msg = "Sync operation already in progress"
            raise RuntimeError(msg)

        self._sync_in_progress = True
        results = {}

        try:
            adapters_to_sync = adapter_names or list(self._adapters.keys())

            # Sync to each adapter
            for name in adapters_to_sync:
                if name in self._adapters:
                    adapter = self._adapters[name]
                    try:
                        # Check adapter status first
                        status = await adapter.get_status()
                        if status not in [AdapterStatus.CONFIGURED, AdapterStatus.CONNECTED, AdapterStatus.AVAILABLE]:
                            results[name] = {
                                "status": "skipped",
                                "reason": f"Adapter status: {status.value}",
                                "synced": 0,
                                "errors": [],
                            }
                            continue

                        # Perform sync
                        sync_result = await adapter.sync_agents(agents, dry_run=dry_run)
                        results[name] = sync_result

                        if not dry_run:
                            self._last_sync[name] = datetime.now(timezone.utc)

                    except Exception as e:
                        results[name] = {
                            "status": "error",
                            "error": str(e),
                            "synced": 0,
                            "errors": [str(e)],
                        }

        finally:
            self._sync_in_progress = False

        return results

    async def import_agents(self, adapter_names: Optional[List[str]] = None) -> Dict[str, List[Any]]:
        """
        Import agents from specified adapters.

        Args:
            adapter_names: Specific adapters to import from, or None for all.

        Returns:
            Dictionary mapping adapter names to imported agents.
        """
        results = {}

        adapters_to_import = adapter_names or list(self._adapters.keys())

        for name in adapters_to_import:
            if name in self._adapters:
                adapter = self._adapters[name]
                try:
                    agents = await adapter.import_agents()
                    results[name] = agents
                except Exception as e:
                    results[name] = []
                    # Log error
                    print(f"Failed to import from {name}: {e}")

        return results

    async def validate_configurations(self, adapter_names: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        Validate configurations for specified adapters.

        Args:
            adapter_names: Specific adapters to validate, or None for all.

        Returns:
            Dictionary mapping adapter names to validation errors.
        """
        results = {}

        adapters_to_validate = adapter_names or list(self._adapters.keys())

        for name in adapters_to_validate:
            if name in self._adapters:
                adapter = self._adapters[name]
                try:
                    errors = await adapter.validate_configuration()
                    results[name] = errors
                except Exception as e:
                    results[name] = [f"Validation failed: {e}"]

        return results

    async def backup_configurations(self, adapter_names: Optional[List[str]] = None) -> Dict[str, Optional[Path]]:
        """
        Create backups of adapter configurations.

        Args:
            adapter_names: Specific adapters to backup, or None for all.

        Returns:
            Dictionary mapping adapter names to backup file paths.
        """
        results = {}

        adapters_to_backup = adapter_names or list(self._adapters.keys())

        for name in adapters_to_backup:
            if name in self._adapters:
                adapter = self._adapters[name]
                try:
                    backup_path = await adapter.backup()
                    results[name] = backup_path
                except Exception as e:
                    results[name] = None
                    # Log error
                    print(f"Failed to backup {name}: {e}")

        return results

    async def restore_configurations(
        self, backup_paths: Dict[str, Path], adapter_names: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Restore adapter configurations from backups.

        Args:
            backup_paths: Dictionary mapping adapter names to backup file paths.
            adapter_names: Specific adapters to restore, or None for all in backup_paths.

        Returns:
            Dictionary mapping adapter names to restore success status.
        """
        results = {}

        adapters_to_restore = adapter_names or list(backup_paths.keys())

        for name in adapters_to_restore:
            if name in self._adapters and name in backup_paths:
                adapter = self._adapters[name]
                backup_path = backup_paths[name]
                try:
                    success = await adapter.restore(backup_path)
                    results[name] = success
                except Exception as e:
                    results[name] = False
                    # Log error
                    print(f"Failed to restore {name}: {e}")

        return results

    async def migrate_between_adapters(self, source_adapter: str, target_adapter: str) -> Dict[str, Any]:
        """
        Migrate configuration and agents from one adapter to another.

        Args:
            source_adapter: Name of source adapter to migrate from.
            target_adapter: Name of target adapter to migrate to.

        Returns:
            Dictionary containing migration results.
        """
        if source_adapter not in self._adapters:
            return {"status": "error", "error": f"Source adapter '{source_adapter}' not found"}

        if target_adapter not in self._adapters:
            return {"status": "error", "error": f"Target adapter '{target_adapter}' not found"}

        source = self._adapters[source_adapter]
        target = self._adapters[target_adapter]

        try:
            result = await target.migrate_from(source)
            return {"status": "success", "source": source_adapter, "target": target_adapter, **result}
        except Exception as e:
            return {"status": "error", "source": source_adapter, "target": target_adapter, "error": str(e)}

    async def cleanup(self) -> Dict[str, bool]:
        """
        Clean up all adapters and resources.

        Returns:
            Dictionary mapping adapter names to cleanup success status.
        """
        results = {}

        for name, adapter in self._adapters.items():
            try:
                success = await adapter.cleanup()
                results[name] = success
            except Exception:
                results[name] = False

        self._adapters.clear()
        self._last_sync.clear()

        return results

    def get_adapter(self, name: str) -> Optional[AbstractAdapter]:
        """Get a specific adapter instance."""
        return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        """List all active adapter names."""
        return list(self._adapters.keys())

    @property
    def sync_in_progress(self) -> bool:
        """Check if sync operation is in progress."""
        return self._sync_in_progress


# Global integration manager instance
_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager(config_path: Optional[Path] = None) -> IntegrationManager:
    """Get the global integration manager instance."""
    global _integration_manager  # noqa: PLW0603
    if _integration_manager is None:
        _integration_manager = IntegrationManager(config_path)
    return _integration_manager
