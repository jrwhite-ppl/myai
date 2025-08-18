"""
Adapter factory for creating and managing tool adapters.

This module provides a factory pattern implementation for creating
and managing different types of tool adapters.
"""

from typing import Any, Dict, List, Optional, Type

from myai.integrations.base import AbstractAdapter, AdapterError, get_adapter_registry


class AdapterFactory:
    """Factory for creating and managing adapter instances."""

    def __init__(self):
        self.registry = get_adapter_registry()

    def create_adapter(
        self, adapter_type: str, config: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AbstractAdapter:
        """
        Create an adapter instance.

        Args:
            adapter_type: Type of adapter to create (e.g., 'claude', 'cursor').
            config: Optional configuration dictionary.
            **kwargs: Additional arguments to pass to adapter constructor.

        Returns:
            Created adapter instance.

        Raises:
            AdapterError: If adapter type is not found or creation fails.
        """
        try:
            # Merge config with kwargs
            final_config = config or {}
            final_config.update(kwargs)

            return self.registry.create_adapter(adapter_type, final_config)
        except ValueError as e:
            msg = f"Failed to create adapter: {e}"
            raise AdapterError(msg, adapter_type) from e

    def get_adapter(self, adapter_type: str) -> Optional[AbstractAdapter]:
        """
        Get an existing adapter instance.

        Args:
            adapter_type: Type of adapter to retrieve.

        Returns:
            Adapter instance if found, None otherwise.
        """
        return self.registry.get_adapter(adapter_type)

    def list_available_adapters(self) -> List[str]:
        """
        List all available adapter types.

        Returns:
            List of available adapter type names.
        """
        return self.registry.list_adapters()

    def list_active_adapters(self) -> List[str]:
        """
        List all active adapter instances.

        Returns:
            List of active adapter names.
        """
        return self.registry.list_active_adapters()

    def register_adapter_class(self, name: str, adapter_class: Type[AbstractAdapter]) -> None:
        """
        Register a new adapter class.

        Args:
            name: Name to register the adapter under.
            adapter_class: Adapter class to register.
        """
        self.registry.register_adapter_class(name, adapter_class)

    async def discover_adapters(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available tool adapters on the system.

        Returns:
            Dictionary mapping adapter names to their discovery information.
        """
        discovered = {}

        for adapter_name in self.list_available_adapters():
            try:
                adapter = self.create_adapter(adapter_name)

                # Check if tool is installed
                is_installed = await adapter.detect_installation()

                if is_installed:
                    # Get adapter info
                    info = adapter.info
                    discovered[adapter_name] = {
                        "name": info.name,
                        "display_name": info.display_name,
                        "description": info.description,
                        "tool_name": info.tool_name,
                        "tool_version": info.tool_version,
                        "status": info.status.value,
                        "capabilities": [cap.value for cap in info.capabilities],
                        "config_path": str(info.config_path) if info.config_path else None,
                        "installation_path": str(info.installation_path) if info.installation_path else None,
                    }

                # Clean up adapter
                await adapter.cleanup()

            except Exception as e:
                discovered[adapter_name] = {
                    "name": adapter_name,
                    "error": str(e),
                    "status": "error",
                }

        return discovered

    async def initialize_adapter(self, adapter_type: str, config: Optional[Dict[str, Any]] = None) -> AbstractAdapter:
        """
        Create and initialize an adapter.

        Args:
            adapter_type: Type of adapter to create.
            config: Optional configuration dictionary.

        Returns:
            Initialized adapter instance.

        Raises:
            AdapterError: If adapter creation or initialization fails.
        """
        adapter = self.create_adapter(adapter_type, config)

        try:
            success = await adapter.initialize()
            if not success:
                msg = "Failed to initialize adapter"
                raise AdapterError(msg, adapter_type)
            return adapter
        except Exception as e:
            msg = f"Adapter initialization failed: {e}"
            raise AdapterError(msg, adapter_type) from e

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on all active adapters.

        Returns:
            Dictionary mapping adapter names to their health check results.
        """
        results = {}

        for adapter_name in self.list_active_adapters():
            adapter = self.get_adapter(adapter_name)
            if adapter:
                try:
                    health = await adapter.health_check()
                    results[adapter_name] = health
                except Exception as e:
                    results[adapter_name] = {
                        "status": "error",
                        "error": str(e),
                    }

        return results

    async def cleanup_all(self) -> Dict[str, bool]:
        """
        Clean up all active adapters.

        Returns:
            Dictionary mapping adapter names to cleanup success status.
        """
        results = {}

        for adapter_name in self.list_active_adapters():
            adapter = self.get_adapter(adapter_name)
            if adapter:
                try:
                    success = await adapter.cleanup()
                    results[adapter_name] = success
                except Exception:
                    results[adapter_name] = False
                finally:
                    self.registry.remove_adapter(adapter_name)

        return results


# Global factory instance
_adapter_factory = AdapterFactory()


def get_adapter_factory() -> AdapterFactory:
    """Get the global adapter factory instance."""
    return _adapter_factory
