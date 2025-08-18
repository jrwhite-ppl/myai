"""
Configuration manager for MyAI.

This module provides centralized configuration management with hierarchical
configuration loading, caching, validation, and real-time watching.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from myai.config.hierarchy import ConfigurationHierarchy
from myai.config.merger import ConfigurationMerger, ConflictResolution
from myai.config.watcher import ConfigurationWatcher
from myai.models.config import ConfigSource, MyAIConfig
from myai.storage.config import ConfigStorage
from myai.storage.filesystem import FileSystemStorage


class ConfigurationManager:
    """
    Centralized configuration manager with hierarchical loading and caching.

    Implements singleton pattern to ensure consistent configuration access
    across the application. Provides caching, lazy loading, and automatic
    configuration watching for real-time updates.
    """

    _instance: Optional["ConfigurationManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "ConfigurationManager":  # noqa: ARG003
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        base_path: Optional[Path] = None,
        *,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        auto_watch: bool = True,
    ):
        """
        Initialize configuration manager.

        Args:
            base_path: Base path for configuration storage
            cache_enabled: Whether to enable configuration caching
            cache_ttl: Cache time-to-live in seconds
            auto_watch: Whether to automatically watch for config changes
        """
        # Prevent re-initialization of singleton
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Storage setup
        self.base_path = base_path or Path.home() / ".myai"
        self._storage = FileSystemStorage(self.base_path)
        self._config_storage = ConfigStorage(self._storage)

        # Configuration hierarchy and merging
        self._hierarchy = ConfigurationHierarchy(self._config_storage, self.base_path)
        self._merger = ConfigurationMerger()

        # Cache settings
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        # Configuration hierarchy
        self._hierarchy_levels = ["enterprise", "user", "team", "project"]
        self._config_paths: Dict[str, Optional[Path]] = {}

        # Watching and change detection
        self._auto_watch = auto_watch
        self._watchers: Set[Callable] = set()
        self._config_watcher = ConfigurationWatcher()
        self._config_watcher.add_handler(self._handle_config_change)

        # Initialize default configuration paths
        self._initialize_config_paths()

        # Start watching if enabled
        if self._auto_watch:
            self.start_watching()

    def get_config(
        self,
        levels: Optional[List[str]] = None,
        *,
        refresh_cache: bool = False,
    ) -> MyAIConfig:
        """
        Get merged configuration from specified levels.

        Args:
            levels: Configuration levels to merge (defaults to all)
            refresh_cache: Force cache refresh

        Returns:
            Merged configuration
        """
        if levels is None:
            levels = self._hierarchy_levels.copy()

        cache_key = ",".join(levels)

        # Check cache first
        if self._cache_enabled and not refresh_cache:
            cached_config = self._get_from_cache(cache_key)
            if cached_config is not None:
                return cached_config

        # Load and merge configurations
        merged_config = self._config_storage.merge_configs(levels)

        # Cache the result
        if self._cache_enabled:
            self._set_cache(cache_key, merged_config)

        return merged_config

    def get_config_value(
        self,
        path: str,
        default: Any = None,
        levels: Optional[List[str]] = None,
    ) -> Any:
        """
        Get a specific configuration value using dot notation.

        Args:
            path: Configuration path (e.g., "settings.auto_sync")
            default: Default value if path not found
            levels: Configuration levels to search

        Returns:
            Configuration value or default
        """
        config = self.get_config(levels)
        return self._get_nested_value(config.model_dump(), path, default)

    def set_config_value(
        self,
        path: str,
        value: Any,
        level: str = "user",
        *,
        create_missing: bool = True,
    ) -> None:
        """
        Set a specific configuration value using dot notation.

        Args:
            path: Configuration path (e.g., "settings.auto_sync")
            value: Value to set
            level: Configuration level to modify
            create_missing: Whether to create missing intermediate objects
        """
        # Load existing config for the level
        existing_config = self._config_storage.load_config(level)

        if existing_config is None:
            if not create_missing:
                msg = f"Configuration level '{level}' does not exist"
                raise ValueError(msg)

            # Create default config for this level
            from myai.models.config import ConfigMetadata, ConfigSettings

            metadata = ConfigMetadata(
                source=ConfigSource(level),
                priority=self._get_default_priority(level),
            )
            existing_config = MyAIConfig(
                metadata=metadata,
                settings=ConfigSettings(),
            )

        # Update the configuration
        config_dict = existing_config.model_dump()
        self._set_nested_value(config_dict, path, value, create_missing=create_missing)

        # Validate and save
        updated_config = MyAIConfig(**config_dict)
        self._config_storage.save_config(updated_config, level)

        # Invalidate cache
        self._invalidate_cache()

        # Notify watchers
        self._notify_watchers("config_changed", {"level": level, "path": path, "value": value})

    def load_config_from_file(self, file_path: Path, level: str = "user") -> None:
        """
        Load configuration from a file.

        Args:
            file_path: Path to configuration file
            level: Configuration level to load into
        """
        self._config_storage.import_config(level, file_path)
        self._invalidate_cache()
        self._notify_watchers("config_loaded", {"level": level, "file": str(file_path)})

    def save_config_to_file(self, file_path: Path, level: str = "user") -> None:
        """
        Save configuration to a file.

        Args:
            file_path: Destination file path
            level: Configuration level to save
        """
        self._config_storage.export_config(level, file_path)

    def delete_config_level(self, level: str) -> bool:
        """
        Delete entire configuration level.

        Args:
            level: Configuration level to delete

        Returns:
            True if deleted, False if not found
        """
        result = self._config_storage.delete_config(level)
        if result:
            self._invalidate_cache()
            self._notify_watchers("config_deleted", {"level": level})
        return result

    def list_config_levels(self) -> List[str]:
        """Get list of available configuration levels."""
        return self._config_storage.list_configs()

    def validate_config(self, config_data: Dict[str, Any]) -> List[str]:
        """
        Validate configuration data.

        Args:
            config_data: Configuration data to validate

        Returns:
            List of validation error messages
        """
        return self._config_storage.validate_config(config_data)

    def get_config_history(self, level: str) -> List[Dict[str, Any]]:
        """
        Get configuration change history for a level.

        Args:
            level: Configuration level

        Returns:
            List of backup metadata
        """
        return self._config_storage.get_config_history(level)

    def restore_config(self, level: str, backup_id: str) -> bool:
        """
        Restore configuration from backup.

        Args:
            level: Configuration level
            backup_id: Backup identifier

        Returns:
            True if restored successfully
        """
        result = self._config_storage.restore_config(level, backup_id)
        if result:
            self._invalidate_cache()
            self._notify_watchers("config_restored", {"level": level, "backup_id": backup_id})
        return result

    def set_config_path(self, level: str, path: Optional[Path]) -> None:
        """
        Set custom path for a configuration level.

        Args:
            level: Configuration level
            path: Custom path (None to use default)
        """
        self._config_paths[level] = path
        self._invalidate_cache()

    def get_config_path(self, level: str) -> Optional[Path]:
        """
        Get path for a configuration level.

        Args:
            level: Configuration level

        Returns:
            Path to configuration file or None if using storage
        """
        return self._config_paths.get(level)

    def add_watcher(self, callback: Callable) -> None:
        """
        Add configuration change watcher.

        Args:
            callback: Function to call on config changes
                     Signature: callback(event: str, data: dict)
        """
        self._watchers.add(callback)

    def remove_watcher(self, callback: Callable) -> None:
        """
        Remove configuration change watcher.

        Args:
            callback: Watcher function to remove
        """
        self._watchers.discard(callback)

    def start_watching(self) -> None:
        """Start configuration file watching."""
        if not self._auto_watch:
            return

        # Add configuration directories to watch
        self._setup_watched_paths()
        self._config_watcher.start()

    def stop_watching(self) -> None:
        """Stop configuration file watching."""
        self._config_watcher.stop()

    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
        self._notify_watchers("cache_cleared", {})

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "enabled": self._cache_enabled,
            "ttl": self._cache_ttl,
            "entries": len(self._cache),
            "size_bytes": sum(len(str(config).encode()) for config in self._cache.values()),
            "oldest_entry": min(self._cache_timestamps.values()) if self._cache_timestamps else None,
            "newest_entry": max(self._cache_timestamps.values()) if self._cache_timestamps else None,
        }

    def discover_configurations(self, level: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Discover available configurations at specified level(s).

        Args:
            level: Specific level to discover (None for all levels)

        Returns:
            Dictionary mapping levels to lists of configuration names
        """
        return self._hierarchy.discover_configurations(level)

    def get_configuration_conflicts(
        self,
        levels: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get configuration conflicts in the hierarchy.

        Args:
            levels: Configuration levels to check (defaults to all)

        Returns:
            List of conflict dictionaries
        """
        if levels is None:
            levels = self._hierarchy_levels.copy()

        # Load configurations for each level
        configs = []
        for level in levels:
            config = self._config_storage.load_config(level)
            if config is not None:
                configs.append((level, config))

        min_configs_for_conflict = 2
        if len(configs) < min_configs_for_conflict:
            return []  # No conflicts possible with less than 2 configs

        # Check for conflicts using merger
        _, conflicts = self._merger.merge_configurations(configs)
        return [conflict.to_dict() for conflict in conflicts]

    def get_merge_preview(
        self,
        levels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get preview of configuration merge result.

        Args:
            levels: Configuration levels to merge (defaults to all)

        Returns:
            Dictionary with merge preview information
        """
        if levels is None:
            levels = self._hierarchy_levels.copy()

        # Load configurations for each level
        configs = []
        for level in levels:
            config = self._config_storage.load_config(level)
            if config is not None:
                configs.append((level, config))

        return self._merger.get_merge_preview(configs)

    def validate_hierarchy(self) -> List[Dict[str, str]]:
        """
        Validate the configuration hierarchy for issues.

        Returns:
            List of validation issues found
        """
        return self._hierarchy.validate_hierarchy()

    def get_active_config_sources(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about active configuration sources.

        Returns:
            Dictionary with source information for each level
        """
        return self._hierarchy.get_active_config_sources()

    def resolve_configuration_conflicts(
        self,
        resolution: ConflictResolution = ConflictResolution.HIGHER_PRIORITY,
        levels: Optional[List[str]] = None,
    ) -> MyAIConfig:
        """
        Resolve configuration conflicts and return merged config.

        Args:
            resolution: Conflict resolution strategy
            levels: Configuration levels to merge (defaults to all)

        Returns:
            Merged configuration with conflicts resolved
        """
        if levels is None:
            levels = self._hierarchy_levels.copy()

        # Load configurations for each level
        configs = []
        for level in levels:
            config = self._config_storage.load_config(level)
            if config is not None:
                configs.append((level, config))

        merged_config, _ = self._merger.merge_configurations(configs, conflict_resolution=resolution)
        return merged_config

    def add_merge_rule(
        self,
        path_pattern: str,
        rule_type: str,
        rule_config: Dict[str, Any],
    ) -> None:
        """
        Add custom merge rule for specific configuration paths.

        Args:
            path_pattern: Pattern to match configuration paths (supports wildcards)
            rule_type: Type of custom rule (e.g., "array_unique", "string_concat")
            rule_config: Configuration for the rule
        """
        self._merger.add_custom_merge_rule(path_pattern, rule_type, rule_config)

    def clear_merge_rules(self) -> None:
        """Clear all custom merge rules."""
        self._merger.clear_custom_rules()

    def _initialize_config_paths(self) -> None:
        """Initialize default configuration paths."""
        self._config_paths = {
            "enterprise": None,  # Use storage
            "user": None,  # Use storage
            "team": None,  # Use storage
            "project": None,  # Use storage
        }

    def _get_from_cache(self, cache_key: str) -> Optional[MyAIConfig]:
        """Get configuration from cache if valid."""
        if cache_key not in self._cache:
            return None

        # Check cache expiry
        cached_time = self._cache_timestamps.get(cache_key)
        if cached_time is None:
            return None

        if (datetime.now(timezone.utc) - cached_time).total_seconds() > self._cache_ttl:
            # Cache expired
            self._cache.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
            return None

        try:
            config_data = self._cache[cache_key]
            return MyAIConfig(**config_data)
        except Exception:
            # Cache corruption, remove entry
            self._cache.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
            return None

    def _set_cache(self, cache_key: str, config: MyAIConfig) -> None:
        """Set configuration in cache."""
        self._cache[cache_key] = config.model_dump()
        self._cache_timestamps[cache_key] = datetime.now(timezone.utc)

    def _invalidate_cache(self) -> None:
        """Invalidate all cached configurations."""
        self._cache.clear()
        self._cache_timestamps.clear()

    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any) -> Any:
        """Get nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def _set_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any,
        *,
        create_missing: bool,
    ) -> None:
        """Set nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                if not create_missing:
                    msg = f"Path '{path}' does not exist"
                    raise ValueError(msg)
                current[key] = {}
            elif not isinstance(current[key], dict):
                if not create_missing:
                    msg = f"Path '{path}' conflicts with existing non-dict value"
                    raise ValueError(msg)
                current[key] = {}

            current = current[key]

        current[keys[-1]] = value

    def _get_default_priority(self, level: str) -> int:
        """Get default priority for configuration level."""
        priority_map = {
            "enterprise": 100,
            "user": 75,
            "team": 50,
            "project": 25,
        }
        return priority_map.get(level, 50)

    def _setup_watched_paths(self) -> None:
        """Set up paths to watch for configuration changes."""
        # Watch the base configuration directory
        config_dir = self.base_path / "config"
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)

        self._config_watcher.add_path(config_dir, recursive=True, file_patterns=["*.json", "*.yaml", "*.yml", "*.toml"])

        # Watch user config directory
        user_config_dir = Path.home() / ".config" / "myai"
        if user_config_dir.exists():
            self._config_watcher.add_path(
                user_config_dir, recursive=True, file_patterns=["*.json", "*.yaml", "*.yml", "*.toml"]
            )

        # Watch project-specific config in current directory
        project_config = Path.cwd() / ".myai"
        if project_config.exists():
            if project_config.is_file():
                self._config_watcher.add_path(project_config)
            else:
                self._config_watcher.add_path(
                    project_config, recursive=True, file_patterns=["*.json", "*.yaml", "*.yml", "*.toml"]
                )

        # Watch specific config files if set
        for _level, config_path in self._config_paths.items():
            if config_path and config_path.exists():
                self._config_watcher.add_path(config_path)

    def _handle_config_change(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle configuration file change events."""
        file_path = Path(event_data["path"])

        # Invalidate cache when config files change
        self._invalidate_cache()

        # Determine which configuration level was affected
        affected_level = self._determine_config_level(file_path)

        # Notify watchers
        notification_data = {
            "event_type": event_type,
            "file_path": str(file_path),
            "level": affected_level,
            "timestamp": event_data.get("timestamp"),
        }

        self._notify_watchers("config_file_changed", notification_data)

    def _determine_config_level(self, file_path: Path) -> Optional[str]:
        """Determine which configuration level a file path belongs to."""
        file_path_str = str(file_path.resolve())

        # Check if it's a specific config file we're tracking
        for level, config_path in self._config_paths.items():
            if config_path and str(config_path.resolve()) == file_path_str:
                return level

        # Check by path patterns
        if "enterprise" in file_path_str or "/etc/myai" in file_path_str:
            return "enterprise"
        elif file_path.is_relative_to(Path.home()):
            return "user"
        elif ".myai" in file_path.name or file_path.is_relative_to(Path.cwd()):
            return "project"
        elif "team" in file_path_str:
            return "team"

        return None

    def _notify_watchers(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all watchers of configuration changes."""
        for callback in self._watchers.copy():  # Copy to avoid modification during iteration
            try:
                callback(event, data)
            except Exception:
                # Remove broken watchers
                self._watchers.discard(callback)

    def validate_configuration(self) -> List[str]:
        """
        Validate the current configuration.

        Returns:
            List of validation error messages
        """
        issues = []

        try:
            # Get merged configuration
            config = self.get_config()

            # Validate tools configuration
            if hasattr(config, "tools"):
                tools = config.tools
                claude_config = tools.get("claude")
                if claude_config and hasattr(claude_config, "model") and not claude_config.model:
                    issues.append("Claude configuration missing model")

                cursor_config = tools.get("cursor")
                if cursor_config and hasattr(cursor_config, "rules_path") and cursor_config.rules_path:
                    rules_path = Path(cursor_config.rules_path)
                    if not rules_path.parent.exists():
                        issues.append(f"Cursor rules directory does not exist: {rules_path.parent}")

            # Validate paths configuration
            if hasattr(config, "paths"):
                paths = config.paths
                if paths.agents_dir:
                    agents_path = Path(paths.agents_dir)
                    if not agents_path.exists():
                        issues.append(f"Agents directory does not exist: {agents_path}")

                if paths.config_dir:
                    config_path = Path(paths.config_dir)
                    if not config_path.exists():
                        issues.append(f"Config directory does not exist: {config_path}")

        except Exception as e:
            issues.append(f"Configuration validation error: {e}")

        return issues

    def reset_configuration(self, level: str) -> None:
        """
        Reset configuration at the specified level to defaults.

        Args:
            level: Configuration level to reset (user, project, team)
        """
        if level not in self._config_paths:
            msg = f"Invalid configuration level: {level}"
            raise ValueError(msg)

        config_path = self._config_paths[level]
        if not config_path:
            msg = f"No configuration file set for level: {level}"
            raise ValueError(msg)

        try:
            # Remove the configuration file
            if config_path.exists():
                config_path.unlink()

            # Clear cached configuration for this level
            # Note: Cache is managed by _invalidate_cache() call below

            # Invalidate merged cache
            self._invalidate_cache()

            # Create default configuration if it's the user level
            if level == "user":
                from myai.models.config import ConfigMetadata, ConfigSettings

                metadata = ConfigMetadata(
                    source=ConfigSource(level),
                    priority=self._get_default_priority(level),
                )
                default_config = MyAIConfig(
                    metadata=metadata,
                    settings=ConfigSettings(),
                )
                self._config_storage.save_config(default_config, level)

        except Exception as e:
            msg = f"Failed to reset {level} configuration: {e}"
            raise RuntimeError(msg) from e


# Convenience function for getting the singleton instance
def get_config_manager() -> ConfigurationManager:
    """Get the singleton ConfigurationManager instance."""
    return ConfigurationManager()
