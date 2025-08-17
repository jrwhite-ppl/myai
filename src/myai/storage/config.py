"""
Configuration storage implementation for MyAI.

This module provides specialized storage for MyAI configuration files
with validation, merging, and hierarchical configuration support.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from myai.models.config import ConfigSource, MyAIConfig
from myai.storage.base import Storage, StorageError


class ConfigStorage:
    """Specialized storage for MyAI configuration files."""

    def __init__(self, storage: Storage):
        """
        Initialize configuration storage.

        Args:
            storage: Underlying storage implementation
        """
        self.storage = storage

    def save_config(self, config: MyAIConfig, level: str = "user") -> None:
        """
        Save a configuration at the specified level.

        Args:
            config: MyAI configuration to save
            level: Configuration level (user, team, project, enterprise)
        """
        try:
            # Validate configuration before saving
            config_dict = config.model_dump(mode="json", exclude_none=True)

            # Create backup before saving
            key = self._get_config_key(level)
            if self.storage.exists(key):
                self.storage.backup(key)

            # Save configuration
            self.storage.write(key, config_dict)

        except ValidationError as e:
            msg = f"Configuration validation failed: {e}"
            raise StorageError(msg) from e

    def load_config(self, level: str = "user") -> Optional[MyAIConfig]:
        """
        Load configuration from the specified level.

        Args:
            level: Configuration level to load

        Returns:
            MyAI configuration or None if not found
        """
        key = self._get_config_key(level)
        data = self.storage.read(key)

        if data is None:
            return None

        try:
            # Remove metadata before validation
            config_data = {k: v for k, v in data.items() if not k.startswith("_")}
            return MyAIConfig(**config_data)
        except ValidationError as e:
            msg = f"Invalid configuration at {level}: {e}"
            raise StorageError(msg) from e

    def merge_configs(self, levels: List[str]) -> MyAIConfig:
        """
        Merge configurations from multiple levels.

        Args:
            levels: List of configuration levels in priority order (highest first)

        Returns:
            Merged configuration
        """
        merged_data: Dict[str, Any] = {}

        # Load all configs first, then sort by priority (lowest to highest)
        configs_to_merge = []
        for level in levels:
            config = self.load_config(level)
            if config is not None:
                configs_to_merge.append((config.metadata.priority, config))

        # Sort by priority (lowest first, so higher priority overwrites)
        configs_to_merge.sort(key=lambda x: x[0])

        # Process configs in priority order
        for _priority, config in configs_to_merge:
            config_dict = config.model_dump(mode="json", exclude_none=True)
            merged_data = self._deep_merge(merged_data, config_dict)

        if not merged_data:
            # Create default configuration if no configs found
            from myai.models.config import ConfigMetadata, ConfigSettings

            merged_data = {
                "metadata": ConfigMetadata(source=ConfigSource.USER, priority=75).model_dump(mode="json"),
                "settings": ConfigSettings().model_dump(mode="json"),
            }

        try:
            return MyAIConfig(**merged_data)
        except ValidationError as e:
            msg = f"Failed to create merged configuration: {e}"
            raise StorageError(msg) from e

    def list_configs(self) -> List[str]:
        """List all available configuration levels."""
        prefix = "config/"
        keys = self.storage.list_keys(prefix)
        return [key[len(prefix) :] for key in keys if key.startswith(prefix)]

    def delete_config(self, level: str) -> bool:
        """
        Delete configuration at the specified level.

        Args:
            level: Configuration level to delete

        Returns:
            True if deleted, False if not found
        """
        key = self._get_config_key(level)

        # Create backup before deletion
        if self.storage.exists(key):
            self.storage.backup(key)
            return self.storage.delete(key)

        return False

    def validate_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate configuration data and return any errors.

        Args:
            config_data: Configuration data to validate

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            MyAIConfig(**config_data)
        except ValidationError as e:
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"{field}: {error['msg']}")

        return errors

    def get_config_history(self, level: str) -> List[Dict[str, Any]]:
        """
        Get the backup history for a configuration level.

        Args:
            level: Configuration level

        Returns:
            List of backup metadata
        """
        key = self._get_config_key(level)

        if not hasattr(self.storage, "list_backups"):
            return []

        backups = self.storage.list_backups(key)
        history = []

        for backup_id in backups:
            # Parse backup timestamp from ID
            try:
                timestamp_str = backup_id.split("_")[0] + backup_id.split("_")[1]
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                history.append(
                    {
                        "backup_id": backup_id,
                        "timestamp": timestamp.isoformat(),
                        "level": level,
                    }
                )
            except (ValueError, IndexError):
                pass  # Skip malformed backup IDs

        return history

    def restore_config(self, level: str, backup_id: str) -> bool:
        """
        Restore configuration from backup.

        Args:
            level: Configuration level
            backup_id: Backup identifier

        Returns:
            True if restored successfully
        """
        key = self._get_config_key(level)

        if not hasattr(self.storage, "restore"):
            return False

        return self.storage.restore(key, backup_id)

    def export_config(self, level: str, file_path: Path) -> None:
        """
        Export configuration to a file.

        Args:
            level: Configuration level to export
            file_path: Destination file path
        """
        config = self.load_config(level)
        if config is None:
            msg = f"No configuration found at level: {level}"
            raise StorageError(msg)

        config_dict = config.model_dump(mode="json", exclude_none=True)

        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        except OSError as e:
            msg = f"Failed to export configuration: {e}"
            raise StorageError(msg) from e

    def import_config(self, level: str, file_path: Path) -> None:
        """
        Import configuration from a file.

        Args:
            level: Configuration level to import to
            file_path: Source file path
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                config_dict = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            msg = f"Failed to import configuration: {e}"
            raise StorageError(msg) from e

        # Validate before importing
        errors = self.validate_config(config_dict)
        if errors:
            msg = f"Invalid configuration: {'; '.join(errors)}"
            raise StorageError(msg)

        config = MyAIConfig(**config_dict)
        self.save_config(config, level)

    def _get_config_key(self, level: str) -> str:
        """Get the storage key for a configuration level."""
        return f"config/{level}"

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform deep merge of two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
