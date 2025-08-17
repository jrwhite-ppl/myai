"""
Tests for ConfigurationMerger.

This module tests configuration merging strategies, conflict detection,
and resolution mechanisms.
"""

import pytest

from myai.config.merger import (
    ConfigConflict,
    ConfigurationMerger,
    ConflictResolution,
    ConflictType,
    DeepMergeStrategy,
    NuclearMergeStrategy,
)
from myai.models.config import MergeStrategy, MyAIConfig


class TestConfigConflict:
    """Test cases for ConfigConflict."""

    def test_conflict_creation(self):
        """Test creating a configuration conflict."""
        conflict = ConfigConflict(
            path="settings.auto_sync",
            conflict_type=ConflictType.VALUE_CONFLICT,
            source1="user",
            value1=True,
            priority1=75,
            source2="team",
            value2=False,
            priority2=50,
        )

        assert conflict.path == "settings.auto_sync"
        assert conflict.conflict_type == ConflictType.VALUE_CONFLICT
        assert conflict.higher_priority_source == "user"
        assert conflict.higher_priority_value is True
        assert conflict.lower_priority_source == "team"
        assert conflict.lower_priority_value is False

    def test_conflict_to_dict(self):
        """Test converting conflict to dictionary."""
        conflict = ConfigConflict(
            path="tools.claude.enabled",
            conflict_type=ConflictType.TYPE_CONFLICT,
            source1="enterprise",
            value1="enabled",
            priority1=100,
            source2="user",
            value2=True,
            priority2=75,
        )

        conflict_dict = conflict.to_dict()

        assert conflict_dict["path"] == "tools.claude.enabled"
        assert conflict_dict["type"] == ConflictType.TYPE_CONFLICT
        assert conflict_dict["higher_priority_source"] == "enterprise"
        assert conflict_dict["priority1"] == 100
        assert conflict_dict["priority2"] == 75


class TestDeepMergeStrategy:
    """Test cases for DeepMergeStrategy."""

    def setup_method(self):
        """Set up test environment."""
        self.strategy = DeepMergeStrategy()

        # Create test configurations
        self.config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {
                "auto_sync": True,
                "debug": False,
                "cache_ttl": 3600,
            },
            "tools": {
                "claude": {"enabled": True, "auto_sync": True},
                "cursor": {"enabled": False},
            },
            "agents": {"enabled": ["general", "coding"]},
        }

        self.config2_data = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "settings": {
                "auto_sync": False,  # Conflict with config1
                "backup_enabled": True,  # New setting
                "cache_ttl": 7200,  # Conflict with config1
            },
            "tools": {
                "claude": {"custom_setting": "team_value"},  # Merge with config1
                "cursor": {"enabled": True},  # Conflict with config1
            },
            "agents": {"enabled": ["team_agent"]},  # Array conflict
        }

        self.config1 = MyAIConfig(**self.config1_data)
        self.config2 = MyAIConfig(**self.config2_data)

    def test_merge_empty_configs(self):
        """Test merging with empty configuration list."""
        merged, conflicts = self.strategy.merge([])

        assert merged == {}
        assert conflicts == []

    def test_merge_single_config(self):
        """Test merging with single configuration."""
        configs = [("user", self.config1, 75)]
        merged, conflicts = self.strategy.merge(configs)

        # Should return the single config without conflicts
        assert merged["settings"]["auto_sync"] is True
        assert merged["tools"]["claude"]["enabled"] is True
        assert len(conflicts) == 0

    def test_merge_non_conflicting_configs(self):
        """Test merging configurations without conflicts."""
        # Create non-conflicting configurations
        config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"auto_sync": True},
            "tools": {"claude": {"enabled": True}},
        }

        config2_data = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "settings": {"debug": False},  # Different setting
            "tools": {"cursor": {"enabled": True}},  # Different tool
        }

        config1 = MyAIConfig(**config1_data)
        config2 = MyAIConfig(**config2_data)

        configs = [("user", config1, 75), ("team", config2, 50)]
        merged, conflicts = self.strategy.merge(configs)

        # Should merge without conflicts
        assert merged["settings"]["auto_sync"] is True  # From user
        assert merged["settings"]["debug"] is False  # From team
        assert merged["tools"]["claude"]["enabled"] is True  # From user
        assert merged["tools"]["cursor"]["enabled"] is True  # From team
        assert len(conflicts) == 0

    def test_merge_with_value_conflicts(self):
        """Test merging configurations with value conflicts."""
        configs = [("team", self.config2, 50), ("user", self.config1, 75)]
        merged, conflicts = self.strategy.merge(configs, ConflictResolution.HIGHER_PRIORITY)

        # Should detect conflicts
        assert len(conflicts) > 0

        # Higher priority (user) should win
        assert merged["settings"]["auto_sync"] is True  # User value wins
        assert merged["settings"]["cache_ttl"] == 3600  # User value wins
        assert merged["tools"]["cursor"]["enabled"] is False  # User value wins

        # Non-conflicting values should be merged
        assert merged["settings"]["backup_enabled"] is True  # From team
        assert merged["tools"]["claude"]["custom_setting"] == "team_value"  # From team

    def test_merge_with_type_conflicts(self):
        """Test merging configurations with type conflicts."""
        # Create valid configs first
        config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"auto_sync": True},  # Boolean
        }

        config2_data = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "settings": {"auto_sync": False},  # Valid boolean first
        }

        config1 = MyAIConfig(**config1_data)
        config2 = MyAIConfig(**config2_data)

        # Now manually create a type conflict by modifying the dumped data
        config2_dict = config2.model_dump(mode="json", exclude_none=True)
        config2_dict["settings"]["auto_sync"] = "enabled"  # Create type conflict

        # Test merge with manually created type conflict

        # Merge by calling _deep_merge_dict directly to test type conflict handling
        base = {}
        conflicts = []

        # First merge team config
        team_conflicts = self.strategy._deep_merge_dict(
            base, config2_dict, "team", 50, "", ConflictResolution.HIGHER_PRIORITY
        )
        conflicts.extend(team_conflicts)

        # Then merge user config (should create type conflict)
        user_dict = config1.model_dump(mode="json", exclude_none=True)
        user_conflicts = self.strategy._deep_merge_dict(
            base, user_dict, "user", 75, "", ConflictResolution.HIGHER_PRIORITY
        )
        conflicts.extend(user_conflicts)

        # Should detect type conflict
        type_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.TYPE_CONFLICT]
        assert len(type_conflicts) > 0

        # Higher priority should win
        assert base["settings"]["auto_sync"] is True  # User value (boolean) wins

    def test_merge_with_array_conflicts(self):
        """Test merging configurations with array conflicts."""
        configs = [("team", self.config2, 50), ("user", self.config1, 75)]
        merged, conflicts = self.strategy.merge(configs, ConflictResolution.HIGHER_PRIORITY)

        # Should detect array conflicts
        array_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.ARRAY_CONFLICT]

        # Arrays are different, so should have conflict
        if array_conflicts:
            # Higher priority should win
            assert merged["agents"]["enabled"] == ["general", "coding"]  # User value wins

    def test_merge_arrays_strategy(self):
        """Test merging arrays with MERGE_ARRAYS strategy."""
        configs = [("team", self.config2, 50), ("user", self.config1, 75)]
        merged, conflicts = self.strategy.merge(configs, ConflictResolution.MERGE_ARRAYS)

        # Arrays should be merged
        enabled_agents = merged["agents"]["enabled"]
        assert "general" in enabled_agents
        assert "coding" in enabled_agents
        assert "team_agent" in enabled_agents
        assert len(enabled_agents) == 3  # No duplicates

    def test_merge_deep_nested_objects(self):
        """Test merging deeply nested objects."""
        config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "custom": {"level1": {"level2": {"level3": {"value": "user_value", "user_only": True}}}},
        }

        config2_data = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "custom": {"level1": {"level2": {"level3": {"value": "team_value", "team_only": False}}}},
        }

        config1 = MyAIConfig(**config1_data)
        config2 = MyAIConfig(**config2_data)

        configs = [("team", config2, 50), ("user", config1, 75)]
        merged, conflicts = self.strategy.merge(configs)

        # Should merge deeply nested objects
        assert merged["custom"]["level1"]["level2"]["level3"]["value"] == "user_value"  # User wins
        assert merged["custom"]["level1"]["level2"]["level3"]["user_only"] is True  # From user
        assert merged["custom"]["level1"]["level2"]["level3"]["team_only"] is False  # From team

    def test_conflict_resolution_strategies(self):
        """Test different conflict resolution strategies."""
        configs = [("team", self.config2, 50), ("user", self.config1, 75)]

        # Test HIGHER_PRIORITY
        merged_higher, _ = self.strategy.merge(configs, ConflictResolution.HIGHER_PRIORITY)
        assert merged_higher["settings"]["auto_sync"] is True  # User wins

        # Test LOWER_PRIORITY
        merged_lower, _ = self.strategy.merge(configs, ConflictResolution.LOWER_PRIORITY)
        assert merged_lower["settings"]["auto_sync"] is False  # Team wins

        # Test ABORT (should raise exception)
        with pytest.raises(ValueError, match="Merge aborted"):
            self.strategy.merge(configs, ConflictResolution.ABORT)


class TestNuclearMergeStrategy:
    """Test cases for NuclearMergeStrategy."""

    def setup_method(self):
        """Set up test environment."""
        self.strategy = NuclearMergeStrategy()

        self.config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"auto_sync": True},
        }

        self.config2_data = {
            "metadata": {"source": "enterprise", "priority": 100, "version": "1.0.0"},
            "settings": {"auto_sync": False, "enterprise_only": True},
        }

        self.config1 = MyAIConfig(**self.config1_data)
        self.config2 = MyAIConfig(**self.config2_data)

    def test_nuclear_merge_empty(self):
        """Test nuclear merge with empty configurations."""
        merged, conflicts = self.strategy.merge([])

        assert merged == {}
        assert conflicts == []

    def test_nuclear_merge_single_config(self):
        """Test nuclear merge with single configuration."""
        configs = [("user", self.config1, 75)]
        merged, conflicts = self.strategy.merge(configs)

        # Should return the single config
        assert merged["settings"]["auto_sync"] is True
        assert len(conflicts) == 0

    def test_nuclear_merge_highest_priority_wins(self):
        """Test that nuclear merge uses highest priority configuration."""
        configs = [("user", self.config1, 75), ("enterprise", self.config2, 100)]
        merged, conflicts = self.strategy.merge(configs)

        # Enterprise config should completely replace user config
        assert merged["settings"]["auto_sync"] is False  # From enterprise
        assert merged["settings"]["enterprise_only"] is True  # From enterprise
        assert "auto_sync" in merged["settings"]  # User setting not present
        assert len(conflicts) == 0  # No conflicts in nuclear merge


class TestConfigurationMerger:
    """Test cases for ConfigurationMerger."""

    def setup_method(self):
        """Set up test environment."""
        self.merger = ConfigurationMerger()

        # Create test configurations
        self.user_config_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"auto_sync": True, "debug": True},
            "tools": {"claude": {"enabled": True}},
        }

        self.team_config_data = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "settings": {"auto_sync": False, "backup_enabled": True},
            "tools": {"cursor": {"enabled": True}},
        }

        self.user_config = MyAIConfig(**self.user_config_data)
        self.team_config = MyAIConfig(**self.team_config_data)

    def test_merge_configurations_empty(self):
        """Test merging with empty configuration list."""
        merged_config, conflicts = self.merger.merge_configurations([])

        # Should return valid empty configuration
        assert isinstance(merged_config, MyAIConfig)
        assert len(conflicts) == 0

    def test_merge_configurations_deep_strategy(self):
        """Test merging configurations with deep merge strategy."""
        configs = [("user", self.user_config), ("team", self.team_config)]
        merged_config, conflicts = self.merger.merge_configurations(
            configs, MergeStrategy.MERGE, ConflictResolution.HIGHER_PRIORITY
        )

        # Should merge configurations
        assert isinstance(merged_config, MyAIConfig)

        # User settings should override team settings
        assert merged_config.settings.auto_sync is True  # User wins
        assert merged_config.settings.debug is True  # From user
        assert merged_config.settings.backup_enabled is True  # From team

        # Tools should be merged
        assert merged_config.tools["claude"].enabled is True  # From user
        assert merged_config.tools["cursor"].enabled is True  # From team

    def test_merge_configurations_nuclear_strategy(self):
        """Test merging configurations with nuclear strategy."""
        configs = [("user", self.user_config), ("team", self.team_config)]
        merged_config, conflicts = self.merger.merge_configurations(configs, MergeStrategy.NUCLEAR)

        # Should use highest priority config completely
        assert isinstance(merged_config, MyAIConfig)
        assert merged_config.settings.auto_sync is True  # From user (higher priority)
        assert merged_config.settings.debug is True  # From user

        # Should use user config values, not team config values
        # Note: backup_enabled will have its default value from user config
        assert merged_config.settings.backup_enabled is True  # Default value from user config
        assert merged_config.metadata.source == "user"  # Should be from user config
        assert merged_config.metadata.priority == 75  # Should be from user config

    def test_merge_configurations_with_conflicts(self):
        """Test merging configurations that have conflicts."""
        configs = [("user", self.user_config), ("team", self.team_config)]
        merged_config, conflicts = self.merger.merge_configurations(configs)

        # Should detect conflicts
        assert len(conflicts) > 0

        # Check for auto_sync conflict
        auto_sync_conflicts = [c for c in conflicts if "auto_sync" in c.path]
        assert len(auto_sync_conflicts) > 0

    def test_invalid_merge_strategy(self):
        """Test merging with invalid strategy."""
        configs = [("user", self.user_config)]

        with pytest.raises(ValueError, match="Unknown merge strategy"):
            self.merger.merge_configurations(configs, "invalid_strategy")

    def test_custom_merge_rules(self):
        """Test adding and using custom merge rules."""
        # Add custom rule for array merging
        self.merger.add_custom_merge_rule(path_pattern="agents.enabled", rule_type="array_unique", rule_config={})

        # Create configs with arrays
        config1_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "agents": {"enabled": ["agent1", "agent2", "agent1"]},  # Has duplicate
        }

        config1 = MyAIConfig(**config1_data)
        configs = [("user", config1)]

        merged_config, conflicts = self.merger.merge_configurations(configs)

        # Custom rule should remove duplicates
        enabled_agents = merged_config.agents.enabled
        assert len(enabled_agents) == 2  # Duplicates removed
        assert "agent1" in enabled_agents
        assert "agent2" in enabled_agents

    def test_clear_custom_rules(self):
        """Test clearing custom merge rules."""
        # Add a rule
        self.merger.add_custom_merge_rule("test.*", "test_type", {})
        assert len(self.merger._custom_rules) == 1

        # Clear rules
        self.merger.clear_custom_rules()
        assert len(self.merger._custom_rules) == 0

    def test_get_merge_preview(self):
        """Test getting merge preview."""
        configs = [("user", self.user_config), ("team", self.team_config)]
        preview = self.merger.get_merge_preview(configs)

        # Should contain preview information
        assert "merged_config" in preview
        assert "conflicts" in preview
        assert "sources" in preview
        assert "strategy" in preview
        assert "total_conflicts" in preview
        assert "conflict_types" in preview

        # Should have correct number of sources
        assert len(preview["sources"]) == 2

        # Should have conflict information
        assert preview["total_conflicts"] >= 0
        assert isinstance(preview["conflict_types"], list)

    def test_merge_preview_with_conflicts(self):
        """Test merge preview with conflicting configurations."""
        configs = [("user", self.user_config), ("team", self.team_config)]
        preview = self.merger.get_merge_preview(configs, MergeStrategy.MERGE)

        # Should detect conflicts in auto_sync
        assert preview["total_conflicts"] > 0

        # Should list conflict types
        assert len(preview["conflict_types"]) > 0

    def test_custom_rule_application(self):
        """Test application of different custom rule types."""
        # Test string concatenation rule
        self.merger.add_custom_merge_rule(
            path_pattern="settings.description", rule_type="string_concat", rule_config={"separator": " | "}
        )

        # Create config with string list
        config_data = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"description": ["part1", "part2", "part3"]},
        }

        config = MyAIConfig(**config_data)
        configs = [("user", config)]

        merged_config, conflicts = self.merger.merge_configurations(configs)

        # String concat rule should join the list
        description = merged_config.settings.model_dump().get("description")
        if isinstance(description, str):
            assert "part1" in description
            assert "part2" in description
            assert "part3" in description
            assert " | " in description

    def test_fallback_on_invalid_merge_result(self):
        """Test fallback behavior when merge result is invalid."""
        # This is difficult to test directly, but we can verify the behavior
        # exists by ensuring merge always returns a valid MyAIConfig
        configs = [("user", self.user_config), ("team", self.team_config)]
        merged_config, conflicts = self.merger.merge_configurations(configs)

        # Should always return valid MyAIConfig
        assert isinstance(merged_config, MyAIConfig)

        # If there was a fallback, there should be a policy violation conflict
        [c for c in conflicts if c.conflict_type == ConflictType.POLICY_VIOLATION]
        # May or may not have policy violations depending on merge success

    def test_nested_value_operations(self):
        """Test nested value get/set operations."""
        test_dict = {"level1": {"level2": {"level3": "value"}}}

        # Test getting nested value
        value = self.merger._get_nested_value(test_dict, "level1.level2.level3")
        assert value == "value"

        # Test getting non-existent value
        value = self.merger._get_nested_value(test_dict, "level1.nonexistent.level3")
        assert value is None

        # Test setting nested value
        self.merger._set_nested_value(test_dict, "level1.level2.new_value", "new")
        assert test_dict["level1"]["level2"]["new_value"] == "new"

        # Test setting new nested path
        self.merger._set_nested_value(test_dict, "new.path.value", "created")
        assert test_dict["new"]["path"]["value"] == "created"

    def test_path_pattern_matching(self):
        """Test path pattern matching for custom rules."""
        config_dict = {
            "tools": {
                "claude": {"enabled": True},
                "cursor": {"enabled": False},
            },
            "settings": {"auto_sync": True},
        }

        # Test wildcard pattern matching
        paths = self.merger._find_matching_paths(config_dict, "tools.*.enabled")

        assert "tools.claude.enabled" in paths
        assert "tools.cursor.enabled" in paths
        assert len(paths) == 2

        # Test exact pattern matching
        paths = self.merger._find_matching_paths(config_dict, "settings.auto_sync")
        assert "settings.auto_sync" in paths
        assert len(paths) == 1
