"""
Configuration hierarchy loader for MyAI.

This module provides configuration discovery and loading from multiple
hierarchical sources including enterprise, user, team, and project levels.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from myai.models.config import MyAIConfig
from myai.storage.config import ConfigStorage


class ConfigurationHierarchy:
    """
    Manages configuration hierarchy discovery and loading.

    Handles loading configurations from multiple sources in priority order:
    1. Enterprise (highest priority)
    2. User
    3. Team
    4. Project (lowest priority)
    """

    def __init__(self, storage: ConfigStorage, base_path: Optional[Path] = None):
        """
        Initialize configuration hierarchy.

        Args:
            storage: Configuration storage implementation
            base_path: Base path for configuration files
        """
        self.storage = storage
        self.base_path = base_path or Path.home() / ".myai"

        # Configuration discovery paths
        self._discovery_paths: Dict[str, List[Path]] = {
            "enterprise": self._get_enterprise_paths(),
            "user": self._get_user_paths(),
            "team": self._get_team_paths(),
            "project": self._get_project_paths(),
        }

        # Cache for discovered configurations
        self._discovered_configs: Dict[str, List[str]] = {}
        self._last_discovery: Dict[str, float] = {}
        self._discovery_cache_ttl = 300  # 5 minutes

    def discover_configurations(self, level: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Discover available configurations at specified level(s).

        Args:
            level: Specific level to discover (None for all levels)

        Returns:
            Dictionary mapping levels to lists of configuration names
        """
        import time

        levels_to_discover = [level] if level else ["enterprise", "user", "team", "project"]
        result = {}

        for config_level in levels_to_discover:
            # Check cache first
            cache_key = config_level
            last_check = self._last_discovery.get(cache_key, 0)

            if time.time() - last_check < self._discovery_cache_ttl:
                if cache_key in self._discovered_configs:
                    result[config_level] = self._discovered_configs[cache_key]
                    continue

            # Discover configurations for this level
            discovered = self._discover_level_configs(config_level)
            result[config_level] = discovered

            # Update cache
            self._discovered_configs[cache_key] = discovered
            self._last_discovery[cache_key] = time.time()

        return result

    def load_hierarchy(
        self,
        levels: Optional[List[str]] = None,
        specific_configs: Optional[Dict[str, str]] = None,
    ) -> List[Tuple[str, MyAIConfig]]:
        """
        Load configuration hierarchy in priority order.

        Args:
            levels: Specific levels to load (None for all)
            specific_configs: Specific config names for each level

        Returns:
            List of (level, config) tuples in priority order
        """
        if levels is None:
            levels = ["enterprise", "user", "team", "project"]

        loaded_configs = []

        for level in levels:
            # Determine which config to load for this level
            config_name = None
            if specific_configs and level in specific_configs:
                config_name = specific_configs[level]
            else:
                # Use default config name for this level
                config_name = self._get_default_config_name(level)

            # Load configuration
            config = self._load_level_config(level, config_name)
            if config is not None:
                loaded_configs.append((level, config))

        return loaded_configs

    def get_active_config_sources(self) -> Dict[str, Dict[str, str]]:
        """
        Get information about active configuration sources.

        Returns:
            Dictionary with source information for each level
        """
        sources = {}

        for level in ["enterprise", "user", "team", "project"]:
            config_info = self._get_config_source_info(level)
            if config_info:
                sources[level] = config_info

        return sources

    def validate_hierarchy(self) -> List[Dict[str, str]]:
        """
        Validate the configuration hierarchy for issues.

        Returns:
            List of validation issues found
        """
        issues = []

        # Check for configuration conflicts
        loaded_configs = self.load_hierarchy()

        for i, (level1, config1) in enumerate(loaded_configs):
            for level2, config2 in loaded_configs[i + 1 :]:
                conflicts = self._find_config_conflicts(config1, config2)
                for conflict in conflicts:
                    issues.append(
                        {
                            "type": "conflict",
                            "level1": level1,
                            "level2": level2,
                            "path": conflict["path"],
                            "value1": str(conflict["value1"]),
                            "value2": str(conflict["value2"]),
                            "message": f"Conflicting values at {conflict['path']}",
                        }
                    )

        # Check for missing required configurations
        required_levels = ["user"]  # At least user config should exist
        discovered = self.discover_configurations()

        for level in required_levels:
            if level not in discovered or not discovered[level]:
                issues.append({"type": "missing", "level": level, "message": f"No {level} configuration found"})

        # Check for invalid configuration files
        for level, configs in discovered.items():
            for config_name in configs:
                validation_errors = self._validate_config_file(level, config_name)
                for error in validation_errors:
                    issues.append({"type": "validation", "level": level, "config": config_name, "message": error})

        return issues

    def get_effective_configuration(
        self,
        levels: Optional[List[str]] = None,
    ) -> MyAIConfig:
        """
        Get the effective merged configuration from hierarchy.

        Args:
            levels: Specific levels to include (None for all)

        Returns:
            Merged configuration
        """
        if levels is None:
            levels = ["enterprise", "user", "team", "project"]

        return self.storage.merge_configs(levels)

    def clear_discovery_cache(self) -> None:
        """Clear the configuration discovery cache."""
        self._discovered_configs.clear()
        self._last_discovery.clear()

    def _discover_level_configs(self, level: str) -> List[str]:
        """Discover configurations for a specific level."""
        discovered = set()

        # Check storage-based configurations
        try:
            storage_configs = self.storage.list_configs()
            level_prefix = f"{level}/"
            for config_key in storage_configs:
                if config_key.startswith(level_prefix):
                    config_name = config_key[len(level_prefix) :]
                    discovered.add(config_name)
                elif config_key == level:
                    discovered.add("default")
        except Exception:  # noqa: S110
            pass  # Storage might not be accessible - intentional silent failure

        # Check file-based configurations
        # Get paths dynamically to support mocking in tests
        if level == "enterprise":
            search_paths = self._get_enterprise_paths()
        elif level == "user":
            search_paths = self._get_user_paths()
        elif level == "team":
            search_paths = self._get_team_paths()
        elif level == "project":
            search_paths = self._get_project_paths()
        else:
            search_paths = []
        for search_path in search_paths:
            if not search_path.exists():
                continue

            try:
                for config_file in search_path.rglob("*.json"):
                    if config_file.is_file():
                        # Use relative path as config name
                        relative_path = config_file.relative_to(search_path)
                        config_name = str(relative_path.with_suffix(""))
                        discovered.add(config_name)

                for config_file in search_path.rglob("*.yaml"):
                    if config_file.is_file():
                        relative_path = config_file.relative_to(search_path)
                        config_name = str(relative_path.with_suffix(""))
                        discovered.add(config_name)
            except Exception:  # noqa: S112
                continue  # Skip inaccessible paths - intentional silent failure

        return sorted(discovered)

    def _load_level_config(self, level: str, config_name: Optional[str]) -> Optional[MyAIConfig]:
        """Load configuration for a specific level and name."""
        if config_name is None:
            config_name = "default"

        # Try loading from storage first
        storage_key = f"{level}/{config_name}" if config_name != "default" else level
        try:
            config = self.storage.load_config(storage_key)
            if config is not None:
                return config
        except Exception:  # noqa: S110
            pass  # Try other methods - intentional silent failure

        # Try loading from file system
        search_paths = self._discovery_paths.get(level, [])
        for search_path in search_paths:
            config_file = search_path / f"{config_name}.json"
            if config_file.exists():
                try:
                    self.storage.import_config(storage_key, config_file)
                    return self.storage.load_config(storage_key)
                except Exception:  # noqa: S112
                    continue  # Skip invalid configs - intentional silent failure

            config_file = search_path / f"{config_name}.yaml"
            if config_file.exists():
                try:
                    # Convert YAML to JSON and import
                    import json
                    import tempfile

                    import yaml  # type: ignore[import]

                    with config_file.open() as f:
                        yaml_data = yaml.safe_load(f)

                    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                        json.dump(yaml_data, f)
                        temp_path = Path(f.name)

                    try:
                        self.storage.import_config(storage_key, temp_path)
                        return self.storage.load_config(storage_key)
                    finally:
                        temp_path.unlink()
                except Exception:  # noqa: S112
                    continue  # Skip invalid configs - intentional silent failure

        return None

    def _get_default_config_name(self, level: str) -> str:  # noqa: ARG002
        """Get default configuration name for a level."""
        return "default"

    def _get_config_source_info(self, level: str) -> Optional[Dict[str, str]]:
        """Get information about configuration source for a level."""
        config = self._load_level_config(level, None)
        if config is None:
            return None

        return {
            "source": config.metadata.source,
            "priority": str(config.metadata.priority),
            "version": config.metadata.version,
            "created": config.metadata.created.isoformat(),
            "modified": config.metadata.modified.isoformat(),
        }

    def _find_config_conflicts(self, config1: MyAIConfig, config2: MyAIConfig) -> List[Dict[str, Any]]:
        """Find conflicts between two configurations."""
        conflicts: List[Dict[str, Any]] = []

        dict1 = config1.model_dump()
        dict2 = config2.model_dump()

        self._compare_dicts(dict1, dict2, "", conflicts)

        return conflicts

    def _compare_dicts(self, dict1: dict, dict2: dict, path: str, conflicts: List[Dict[str, Any]]) -> None:
        """Recursively compare dictionaries for conflicts."""
        all_keys = set(dict1.keys()) | set(dict2.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key

            if key in dict1 and key in dict2:
                value1 = dict1[key]
                value2 = dict2[key]

                if isinstance(value1, dict) and isinstance(value2, dict):
                    self._compare_dicts(value1, value2, current_path, conflicts)
                elif value1 != value2:
                    conflicts.append(
                        {
                            "path": current_path,
                            "value1": value1,
                            "value2": value2,
                        }
                    )

    def _validate_config_file(self, level: str, config_name: str) -> List[str]:
        """Validate a configuration file."""
        try:
            config = self._load_level_config(level, config_name)
            if config is None:
                return [f"Could not load configuration: {config_name}"]

            # Validate using storage
            config_dict = config.model_dump()
            return self.storage.validate_config(config_dict)
        except Exception as e:
            return [f"Validation error: {e!s}"]

    def _get_enterprise_paths(self) -> List[Path]:
        """Get paths to search for enterprise configurations."""
        paths = []

        # System-wide enterprise config locations
        if os.name == "nt":  # Windows
            paths.extend(
                [
                    Path("C:/ProgramData/MyAI/config"),
                    Path(os.environ.get("ALLUSERSPROFILE", "C:/ProgramData")) / "MyAI" / "config",
                ]
            )
        else:  # Unix-like
            paths.extend(
                [
                    Path("/etc/myai/config"),
                    Path("/usr/local/etc/myai/config"),
                    Path("/opt/myai/config"),
                ]
            )

        # Environment variable override
        enterprise_path = os.environ.get("MYAI_ENTERPRISE_CONFIG")
        if enterprise_path:
            paths.insert(0, Path(enterprise_path))

        return paths

    def _get_user_paths(self) -> List[Path]:
        """Get paths to search for user configurations."""
        paths = [
            self.base_path / "config",
            Path.home() / ".config" / "myai",
        ]

        # XDG config directory
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            paths.append(Path(xdg_config) / "myai")

        return paths

    def _get_team_paths(self) -> List[Path]:
        """Get paths to search for team configurations."""
        paths = []

        # Team configuration can come from shared locations
        team_config_path = os.environ.get("MYAI_TEAM_CONFIG")
        if team_config_path:
            paths.append(Path(team_config_path))

        # Network drives (common in enterprise environments)
        if os.name == "nt":  # Windows
            for drive in ["P:", "S:", "T:"]:  # Common shared drives
                team_path = Path(drive) / "myai" / "team-config"
                if team_path.exists():
                    paths.append(team_path)

        # Local team config fallback
        paths.append(self.base_path / "team-config")

        return paths

    def _get_project_paths(self) -> List[Path]:
        """Get paths to search for project configurations."""
        paths = []

        # Look for project config in current directory and parents
        current_dir = Path.cwd()
        for parent in [current_dir, *list(current_dir.parents)]:
            project_config = parent / ".myai"
            if project_config.exists():
                paths.append(project_config)

            # Also check for .myai.json or .myai directory
            for config_file in [".myai.json", ".myai.yaml"]:
                if (parent / config_file).exists():
                    paths.append(parent)
                    break

        # Environment variable override
        project_path = os.environ.get("MYAI_PROJECT_CONFIG")
        if project_path:
            paths.insert(0, Path(project_path))

        return paths
