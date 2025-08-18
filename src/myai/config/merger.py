"""
Configuration merging and conflict resolution for MyAI.

This module provides advanced configuration merging with multiple strategies,
conflict detection, and resolution mechanisms for hierarchical configurations.
"""

import fnmatch
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from myai.models.config import ConfigSource, MergeStrategy, MyAIConfig


class ConflictType(str, Enum):
    """Types of configuration conflicts."""

    VALUE_CONFLICT = "value_conflict"  # Different values for same key
    TYPE_CONFLICT = "type_conflict"  # Different types for same key
    ARRAY_CONFLICT = "array_conflict"  # Conflicting array operations
    POLICY_VIOLATION = "policy_violation"  # Violates merge policy


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""

    HIGHER_PRIORITY = "higher_priority"  # Use higher priority value
    LOWER_PRIORITY = "lower_priority"  # Use lower priority value
    MERGE_ARRAYS = "merge_arrays"  # Merge array values
    INTERACTIVE = "interactive"  # Prompt user for resolution
    ABORT = "abort"  # Abort merge on conflict


class ConfigConflict:
    """Represents a configuration conflict."""

    def __init__(
        self,
        path: str,
        conflict_type: ConflictType,
        source1: str,
        value1: Any,
        priority1: int,
        source2: str,
        value2: Any,
        priority2: int,
        message: Optional[str] = None,
    ):
        self.path = path
        self.conflict_type = conflict_type
        self.source1 = source1
        self.value1 = value1
        self.priority1 = priority1
        self.source2 = source2
        self.value2 = value2
        self.priority2 = priority2
        self.message = message or f"Conflict at {path}"

        # Determine which source has higher priority
        self.higher_priority_source = source1 if priority1 > priority2 else source2
        self.higher_priority_value = value1 if priority1 > priority2 else value2
        self.lower_priority_source = source2 if priority1 > priority2 else source1
        self.lower_priority_value = value2 if priority1 > priority2 else value1

    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary representation."""
        return {
            "path": self.path,
            "type": self.conflict_type,
            "source1": self.source1,
            "value1": str(self.value1),
            "priority1": self.priority1,
            "source2": self.source2,
            "value2": str(self.value2),
            "priority2": self.priority2,
            "higher_priority_source": self.higher_priority_source,
            "higher_priority_value": str(self.higher_priority_value),
            "message": self.message,
        }


class MergeStrategyBase(ABC):
    """Base class for configuration merge strategies."""

    @abstractmethod
    def merge(
        self,
        configs: List[Tuple[str, MyAIConfig, int]],
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHER_PRIORITY,
    ) -> Tuple[Dict[str, Any], List[ConfigConflict]]:
        """
        Merge configurations using this strategy.

        Args:
            configs: List of (source, config, priority) tuples
            conflict_resolution: How to resolve conflicts

        Returns:
            Tuple of (merged_dict, conflicts_found)
        """
        pass


class DeepMergeStrategy(MergeStrategyBase):
    """Deep merge strategy that recursively merges nested dictionaries."""

    def merge(
        self,
        configs: List[Tuple[str, MyAIConfig, int]],
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHER_PRIORITY,
    ) -> Tuple[Dict[str, Any], List[ConfigConflict]]:
        """Perform deep merge of configurations."""
        if not configs:
            return {}, []

        # Sort by priority (lowest first, so higher priority overwrites)
        sorted_configs = sorted(configs, key=lambda x: x[2])

        merged: Dict[str, Any] = {}
        conflicts: List[ConfigConflict] = []

        for source, config, priority in sorted_configs:
            config_dict = config.model_dump(mode="json", exclude_none=True)
            new_conflicts = self._deep_merge_dict(merged, config_dict, source, priority, "", conflict_resolution)
            conflicts.extend(new_conflicts)

        return merged, conflicts

    def _deep_merge_dict(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
        source: str,
        priority: int,
        path_prefix: str,
        conflict_resolution: ConflictResolution,
    ) -> List[ConfigConflict]:
        """Recursively merge dictionaries."""
        conflicts = []

        for key, value in override.items():
            current_path = f"{path_prefix}.{key}" if path_prefix else key

            # Special handling for metadata - take highest priority without conflicts
            if current_path.startswith("metadata.") and key in base:
                base[key] = value  # Override metadata fields with higher priority
                continue

            if key not in base:
                base[key] = value
            else:
                existing_value = base[key]

                # Check for type conflicts
                if type(existing_value) != type(value):
                    conflict = ConfigConflict(
                        path=current_path,
                        conflict_type=ConflictType.TYPE_CONFLICT,
                        source1="previous",
                        value1=existing_value,
                        priority1=0,  # Unknown priority for base
                        source2=source,
                        value2=value,
                        priority2=priority,
                        message=f"Type conflict at {current_path}: {type(existing_value)} vs {type(value)}",
                    )
                    conflicts.append(conflict)

                    # Resolve conflict
                    base[key] = self._resolve_conflict(conflict, conflict_resolution)

                elif isinstance(value, dict) and isinstance(existing_value, dict):
                    # Recursively merge dictionaries
                    nested_conflicts = self._deep_merge_dict(
                        existing_value, value, source, priority, current_path, conflict_resolution
                    )
                    conflicts.extend(nested_conflicts)

                elif isinstance(value, list) and isinstance(existing_value, list):
                    # Handle array merging
                    merged_array, array_conflicts = self._merge_arrays(
                        existing_value, value, current_path, source, priority, conflict_resolution
                    )
                    base[key] = merged_array
                    conflicts.extend(array_conflicts)

                elif existing_value != value:
                    # Value conflict
                    conflict = ConfigConflict(
                        path=current_path,
                        conflict_type=ConflictType.VALUE_CONFLICT,
                        source1="previous",
                        value1=existing_value,
                        priority1=0,  # Unknown priority for base
                        source2=source,
                        value2=value,
                        priority2=priority,
                        message=f"Value conflict at {current_path}: {existing_value} vs {value}",
                    )
                    conflicts.append(conflict)

                    # Resolve conflict
                    base[key] = self._resolve_conflict(conflict, conflict_resolution)

        return conflicts

    def _merge_arrays(
        self,
        existing: List[Any],
        new: List[Any],
        path: str,
        source: str,
        priority: int,
        conflict_resolution: ConflictResolution,
    ) -> Tuple[List[Any], List[ConfigConflict]]:
        """Merge two arrays based on conflict resolution strategy."""
        conflicts: List[ConfigConflict] = []

        if conflict_resolution == ConflictResolution.MERGE_ARRAYS:
            # Merge arrays, avoiding duplicates
            merged = existing.copy()
            for item in new:
                if item not in merged:
                    merged.append(item)
            return merged, conflicts
        else:
            # Check if arrays are different
            if existing != new:
                conflict = ConfigConflict(
                    path=path,
                    conflict_type=ConflictType.ARRAY_CONFLICT,
                    source1="previous",
                    value1=existing,
                    priority1=0,
                    source2=source,
                    value2=new,
                    priority2=priority,
                    message=f"Array conflict at {path}",
                )
                conflicts.append(conflict)

                resolved_value = self._resolve_conflict(conflict, conflict_resolution)
                return resolved_value, conflicts

            return existing, conflicts

    def _resolve_conflict(
        self,
        conflict: ConfigConflict,
        resolution: ConflictResolution,
    ) -> Any:
        """Resolve a configuration conflict based on strategy."""
        if resolution == ConflictResolution.HIGHER_PRIORITY:
            return conflict.higher_priority_value
        elif resolution == ConflictResolution.LOWER_PRIORITY:
            return conflict.lower_priority_value
        elif resolution == ConflictResolution.MERGE_ARRAYS:
            if isinstance(conflict.value1, list) and isinstance(conflict.value2, list):
                merged = conflict.value1.copy()
                for item in conflict.value2:
                    if item not in merged:
                        merged.append(item)
                return merged
            else:
                return conflict.higher_priority_value
        elif resolution == ConflictResolution.INTERACTIVE:
            # Use the interactive resolver
            from myai.config.interactive_resolver import InteractiveMode, get_interactive_resolver

            resolver = get_interactive_resolver(InteractiveMode.CLI)
            # Create unique session ID (unused but kept for potential future use)
            _session_id = resolver.__class__.__module__.replace(".", "_") + "_session"
            from myai.config.interactive_resolver import ConflictResolutionSession

            session_obj = ConflictResolutionSession(InteractiveMode.CLI)
            return resolver.resolve_conflict(conflict, session_obj)
        elif resolution == ConflictResolution.ABORT:
            msg = f"Merge aborted due to conflict: {conflict.message}"
            raise ValueError(msg)
        else:
            return conflict.higher_priority_value


class NuclearMergeStrategy(MergeStrategyBase):
    """Nuclear merge strategy that completely replaces configurations."""

    def merge(
        self,
        configs: List[Tuple[str, MyAIConfig, int]],
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHER_PRIORITY,  # noqa: ARG002
    ) -> Tuple[Dict[str, Any], List[ConfigConflict]]:
        """Perform nuclear merge (complete replacement)."""
        if not configs:
            return {}, []

        # Find highest priority configuration
        highest_priority_config = max(configs, key=lambda x: x[2])
        source, config, priority = highest_priority_config

        return config.model_dump(mode="json", exclude_none=True), []


class ConfigurationMerger:
    """Main configuration merger with multiple strategies."""

    def __init__(self):
        """Initialize merger with available strategies."""
        self._strategies = {
            MergeStrategy.MERGE: DeepMergeStrategy(),
            MergeStrategy.NUCLEAR: NuclearMergeStrategy(),
        }

        self._custom_rules: List[Dict[str, Any]] = []

    def merge_configurations(
        self,
        configs: List[Tuple[str, MyAIConfig]],
        strategy: MergeStrategy = MergeStrategy.MERGE,
        conflict_resolution: ConflictResolution = ConflictResolution.HIGHER_PRIORITY,
    ) -> Tuple[MyAIConfig, List[ConfigConflict]]:
        """
        Merge multiple configurations using specified strategy.

        Args:
            configs: List of (source_name, config) tuples
            strategy: Merge strategy to use
            conflict_resolution: How to resolve conflicts

        Returns:
            Tuple of (merged_config, conflicts_found)
        """
        if not configs:
            # Return empty configuration
            from myai.models.config import ConfigMetadata, ConfigSettings

            empty_config = MyAIConfig(
                metadata=ConfigMetadata(source=ConfigSource.USER, priority=50),
                settings=ConfigSettings(),
            )
            return empty_config, []

        # Convert to (source, config, priority) tuples
        configs_with_priority = [(source, config, config.metadata.priority) for source, config in configs]

        # Get merge strategy
        merge_strategy = self._strategies.get(strategy)
        if merge_strategy is None:
            msg = f"Unknown merge strategy: {strategy}"
            raise ValueError(msg)

        # Perform merge
        merged_dict, conflicts = merge_strategy.merge(configs_with_priority, conflict_resolution)

        # Apply custom merge rules
        self._apply_custom_rules(merged_dict, configs_with_priority)

        # Create merged configuration
        try:
            merged_config = MyAIConfig(**merged_dict)
        except Exception as e:
            # If merge result is invalid, fall back to highest priority config
            highest_priority = max(configs, key=lambda x: x[1].metadata.priority)
            merged_config = highest_priority[1]
            conflicts.append(
                ConfigConflict(
                    path="root",
                    conflict_type=ConflictType.POLICY_VIOLATION,
                    source1="merge_result",
                    value1="invalid",
                    priority1=0,
                    source2="fallback",
                    value2="highest_priority",
                    priority2=100,
                    message=f"Merge result invalid, falling back: {e!s}",
                )
            )

        return merged_config, conflicts

    def add_custom_merge_rule(
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
        self._custom_rules.append(
            {
                "pattern": path_pattern,
                "type": rule_type,
                "config": rule_config,
            }
        )

    def clear_custom_rules(self) -> None:
        """Clear all custom merge rules."""
        self._custom_rules.clear()

    def get_merge_preview(
        self,
        configs: List[Tuple[str, MyAIConfig]],
        strategy: MergeStrategy = MergeStrategy.MERGE,
    ) -> Dict[str, Any]:
        """
        Get preview of merge result without applying it.

        Args:
            configs: List of (source_name, config) tuples
            strategy: Merge strategy to use

        Returns:
            Dictionary with merge preview information
        """
        merged_config, conflicts = self.merge_configurations(configs, strategy, ConflictResolution.HIGHER_PRIORITY)

        return {
            "merged_config": merged_config.model_dump(mode="json"),
            "conflicts": [conflict.to_dict() for conflict in conflicts],
            "sources": [
                {
                    "name": source,
                    "priority": config.metadata.priority,
                    "source_type": config.metadata.source,
                }
                for source, config in configs
            ],
            "strategy": strategy,
            "total_conflicts": len(conflicts),
            "conflict_types": list({c.conflict_type for c in conflicts}),
        }

    def _apply_custom_rules(
        self,
        merged_dict: Dict[str, Any],
        configs: List[Tuple[str, MyAIConfig, int]],
    ) -> None:
        """Apply custom merge rules to merged configuration."""

        for rule in self._custom_rules:
            pattern = rule["pattern"]
            rule_type = rule["type"]
            rule_config = rule["config"]

            # Find matching paths in merged config
            matching_paths = self._find_matching_paths(merged_dict, pattern)

            for path in matching_paths:
                if rule_type == "array_unique":
                    self._apply_array_unique_rule(merged_dict, path)
                elif rule_type == "string_concat":
                    self._apply_string_concat_rule(merged_dict, path, rule_config)
                elif rule_type == "priority_override":
                    self._apply_priority_override_rule(merged_dict, path, rule_config, configs)

    def _find_matching_paths(self, config_dict: Dict[str, Any], pattern: str) -> List[str]:
        """Find configuration paths matching a pattern."""

        def get_all_paths(data: Dict[str, Any], prefix: str = "") -> List[str]:
            paths = []
            for key, value in data.items():
                current_path = f"{prefix}.{key}" if prefix else key
                paths.append(current_path)

                if isinstance(value, dict):
                    paths.extend(get_all_paths(value, current_path))

            return paths

        all_paths = get_all_paths(config_dict)
        return [path for path in all_paths if fnmatch.fnmatch(path, pattern)]

    def _apply_array_unique_rule(self, config_dict: Dict[str, Any], path: str) -> None:
        """Apply array unique rule to ensure no duplicates."""
        value = self._get_nested_value(config_dict, path)
        if isinstance(value, list):
            unique_value = list(dict.fromkeys(value))  # Preserve order
            self._set_nested_value(config_dict, path, unique_value)

    def _apply_string_concat_rule(
        self,
        config_dict: Dict[str, Any],
        path: str,
        rule_config: Dict[str, Any],
    ) -> None:
        """Apply string concatenation rule."""
        separator = rule_config.get("separator", " ")
        value = self._get_nested_value(config_dict, path)

        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            concatenated = separator.join(value)
            self._set_nested_value(config_dict, path, concatenated)

    def _apply_priority_override_rule(
        self,
        config_dict: Dict[str, Any],
        path: str,
        rule_config: Dict[str, Any],
        configs: List[Tuple[str, MyAIConfig, int]],
    ) -> None:
        """Apply priority override rule for specific sources."""
        preferred_source = rule_config.get("preferred_source")
        if not preferred_source:
            return

        # Find value from preferred source
        for source, config, _priority in configs:
            if source == preferred_source:
                config_dict_source = config.model_dump(mode="json")
                source_value = self._get_nested_value(config_dict_source, path)
                if source_value is not None:
                    self._set_nested_value(config_dict, path, source_value)
                break

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def merge_configurations_interactively(
        self,
        configs: List[Tuple[str, MyAIConfig]],
        strategy: MergeStrategy = MergeStrategy.MERGE,
        interactive_mode: str = "cli",
        **kwargs: Any,
    ) -> Tuple[MyAIConfig, List[ConfigConflict], Dict[str, Any]]:
        """
        Merge configurations with interactive conflict resolution.

        Args:
            configs: List of (source_name, config) tuples
            strategy: Merge strategy to use
            interactive_mode: Interactive resolution mode ('cli', 'batch', 'auto')
            **kwargs: Additional arguments for interactive resolver

        Returns:
            Tuple of (merged_config, unresolved_conflicts, resolution_details)
        """
        from myai.config.interactive_resolver import (
            InteractiveMode,
            resolve_conflicts_interactively,
        )

        # First, perform merge with automatic conflict detection
        merged_config, conflicts = self.merge_configurations(configs, strategy, ConflictResolution.HIGHER_PRIORITY)

        if not conflicts:
            # No conflicts - return merged config
            return merged_config, [], {}

        # Resolve conflicts interactively
        mode_map = {
            "cli": InteractiveMode.CLI,
            "batch": InteractiveMode.BATCH,
            "auto": InteractiveMode.AUTO,
            "web": InteractiveMode.WEB,
        }

        mode = mode_map.get(interactive_mode, InteractiveMode.CLI)
        resolutions = resolve_conflicts_interactively(conflicts, mode, **kwargs)

        # Apply resolutions to merged config
        merged_dict = merged_config.model_dump()
        for path, resolved_value in resolutions.items():
            self._set_nested_value(merged_dict, path, resolved_value)

        # Create new config with resolved values
        resolved_config = MyAIConfig.model_validate(merged_dict)

        # Find any unresolved conflicts
        unresolved = [c for c in conflicts if c.path not in resolutions]

        resolution_details = {
            "total_conflicts": len(conflicts),
            "resolved_conflicts": len(resolutions),
            "unresolved_conflicts": len(unresolved),
            "interactive_mode": interactive_mode,
            "resolutions": {path: str(value) for path, value in resolutions.items()},
        }

        return resolved_config, unresolved, resolution_details

    def preview_conflicts(
        self,
        configs: List[Tuple[str, MyAIConfig]],
        strategy: MergeStrategy = MergeStrategy.MERGE,
    ) -> Dict[str, Any]:
        """
        Preview conflicts that would occur during merge without resolving them.

        Args:
            configs: List of (source_name, config) tuples
            strategy: Merge strategy to use

        Returns:
            Dictionary with conflict preview information
        """
        _merged_config, conflicts = self.merge_configurations(configs, strategy, ConflictResolution.HIGHER_PRIORITY)

        conflict_summary: Dict[str, List[Dict[str, Any]]] = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type
            if conflict_type not in conflict_summary:
                conflict_summary[conflict_type] = []
            conflict_summary[conflict_type].append(conflict.to_dict())

        conflict_threshold_for_batch = 5
        return {
            "total_conflicts": len(conflicts),
            "conflict_types": list(conflict_summary.keys()),
            "conflicts_by_type": conflict_summary,
            "needs_interactive_resolution": len(conflicts) > 0,
            "suggested_mode": "cli" if len(conflicts) < conflict_threshold_for_batch else "batch",
        }
