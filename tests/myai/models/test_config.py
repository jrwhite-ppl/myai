"""Tests for configuration models."""

from datetime import datetime
from pathlib import Path

import pytest

from myai.models.config import (
    AgentConfig,
    ClaudeConfig,
    ConfigMetadata,
    ConfigSettings,
    ConfigSource,
    CursorConfig,
    IntegrationConfig,
    MergeStrategy,
    MyAIConfig,
    ToolConfig,
)


class TestConfigMetadata:
    """Test ConfigMetadata model."""

    def test_config_metadata_creation(self):
        """Test basic metadata creation."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)

        assert metadata.source == ConfigSource.USER
        assert metadata.priority == 50
        assert metadata.version == "1.0.0"
        assert isinstance(metadata.created, datetime)
        assert isinstance(metadata.modified, datetime)

    def test_priority_validation_enterprise(self):
        """Test priority validation for enterprise source."""
        metadata = ConfigMetadata(source=ConfigSource.ENTERPRISE, priority=50)
        assert metadata.priority == 100  # Should be forced to 100

    def test_priority_validation_project(self):
        """Test priority validation for project source."""
        metadata = ConfigMetadata(source=ConfigSource.PROJECT, priority=50)
        assert metadata.priority == 25  # Should be capped at 25

    def test_priority_validation_team(self):
        """Test priority validation for team source."""
        metadata = ConfigMetadata(source=ConfigSource.TEAM, priority=75)
        assert metadata.priority == 50  # Should be capped at 50

    def test_priority_validation_user(self):
        """Test priority validation for user source."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=100)
        assert metadata.priority == 75  # Should be capped at 75


class TestConfigSettings:
    """Test ConfigSettings model."""

    def test_default_settings(self):
        """Test default configuration settings."""
        settings = ConfigSettings()

        assert settings.merge_strategy == MergeStrategy.MERGE
        assert settings.auto_sync is True
        assert settings.backup_enabled is True
        assert settings.backup_count == 5
        assert settings.cache_enabled is True
        assert settings.cache_ttl == 3600
        assert settings.debug is False

    def test_backup_count_validation(self):
        """Test backup count validation."""
        with pytest.raises(ValueError):
            ConfigSettings(backup_count=0)  # Too low

        with pytest.raises(ValueError):
            ConfigSettings(backup_count=100)  # Too high

        settings = ConfigSettings(backup_count=10)
        assert settings.backup_count == 10

    def test_cache_ttl_validation(self):
        """Test cache TTL validation."""
        with pytest.raises(ValueError):
            ConfigSettings(cache_ttl=30)  # Too low

        with pytest.raises(ValueError):
            ConfigSettings(cache_ttl=100000)  # Too high

        settings = ConfigSettings(cache_ttl=7200)
        assert settings.cache_ttl == 7200


class TestToolConfig:
    """Test ToolConfig and subclasses."""

    def test_base_tool_config(self):
        """Test base tool configuration."""
        config = ToolConfig()

        assert config.enabled is True
        assert config.auto_sync is True
        assert config.backup_before_sync is True
        assert config.config_path is None

    def test_claude_config(self):
        """Test Claude-specific configuration."""
        config = ClaudeConfig()

        assert isinstance(config, ToolConfig)
        assert config.enabled is True
        assert config.mcp_servers == {}
        assert config.model_preferences == {}
        assert config.tool_settings == {}
        assert config.custom_instructions is None

    def test_cursor_config(self):
        """Test Cursor-specific configuration."""
        config = CursorConfig()

        assert isinstance(config, ToolConfig)
        assert config.enabled is True
        assert config.ai_model_settings == {}
        assert config.custom_rules == []
        assert config.project_specific is True


class TestAgentConfig:
    """Test AgentConfig model."""

    def test_default_agent_config(self):
        """Test default agent configuration."""
        config = AgentConfig()

        assert config.enabled == []
        assert config.disabled == []
        assert config.custom_path is None
        assert config.auto_discover is True
        assert config.categories == []

    def test_agent_config_with_data(self):
        """Test agent configuration with data."""
        config = AgentConfig(
            enabled=["lead_developer", "security_analyst"],
            disabled=["marketing_manager"],
            categories=["engineering", "security"],
        )

        assert config.enabled == ["lead_developer", "security_analyst"]
        assert config.disabled == ["marketing_manager"]
        assert config.categories == ["engineering", "security"]


class TestIntegrationConfig:
    """Test IntegrationConfig model."""

    def test_default_integration_config(self):
        """Test default integration configuration."""
        config = IntegrationConfig()

        assert config.auto_sync_interval == 300
        assert config.conflict_resolution == "interactive"
        assert config.dry_run_default is False
        assert config.sync_on_change is True

    def test_sync_interval_validation(self):
        """Test sync interval validation."""
        with pytest.raises(ValueError):
            IntegrationConfig(auto_sync_interval=30)  # Too low

        with pytest.raises(ValueError):
            IntegrationConfig(auto_sync_interval=4000)  # Too high

        config = IntegrationConfig(auto_sync_interval=600)
        assert config.auto_sync_interval == 600

    def test_conflict_resolution_validation(self):
        """Test conflict resolution validation."""
        valid_strategies = ["interactive", "auto", "manual", "abort"]

        for strategy in valid_strategies:
            config = IntegrationConfig(conflict_resolution=strategy)
            assert config.conflict_resolution == strategy

        with pytest.raises(ValueError):
            IntegrationConfig(conflict_resolution="invalid")


class TestMyAIConfig:
    """Test complete MyAI configuration."""

    def test_basic_config_creation(self):
        """Test basic configuration creation."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)
        config = MyAIConfig(metadata=metadata)

        assert config.metadata.source == ConfigSource.USER
        assert isinstance(config.settings, ConfigSettings)
        assert isinstance(config.agents, AgentConfig)
        assert isinstance(config.integrations, IntegrationConfig)
        assert "claude" in config.tools
        assert "cursor" in config.tools
        assert isinstance(config.tools["claude"], ClaudeConfig)
        assert isinstance(config.tools["cursor"], CursorConfig)

    def test_custom_tools_config(self):
        """Test configuration with custom tools."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)
        tools = {
            "claude": {"enabled": False},
            "cursor": {"project_specific": False},
            "custom_tool": {"enabled": True, "config_path": "/home/user/custom"},
        }

        config = MyAIConfig(metadata=metadata, tools=tools)

        assert isinstance(config.tools["claude"], ClaudeConfig)
        assert config.tools["claude"].enabled is False
        assert isinstance(config.tools["cursor"], CursorConfig)
        assert config.tools["cursor"].project_specific is False
        assert isinstance(config.tools["custom_tool"], ToolConfig)
        assert config.tools["custom_tool"].enabled is True

    def test_config_serialization(self):
        """Test configuration serialization."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)
        config = MyAIConfig(metadata=metadata)

        # Should be able to serialize to dict
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert "metadata" in config_dict
        assert "settings" in config_dict
        assert "tools" in config_dict
        assert "agents" in config_dict
        assert "integrations" in config_dict

    def test_config_validation(self):
        """Test configuration validation."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)

        # Valid configuration
        config = MyAIConfig(
            metadata=metadata, settings=ConfigSettings(debug=True), agents=AgentConfig(enabled=["test_agent"])
        )

        assert config.settings.debug is True
        assert config.agents.enabled == ["test_agent"]


class TestEnums:
    """Test enum classes."""

    def test_merge_strategy_enum(self):
        """Test MergeStrategy enum."""
        assert MergeStrategy.MERGE == "merge"
        assert MergeStrategy.NUCLEAR == "nuclear"

    def test_config_source_enum(self):
        """Test ConfigSource enum."""
        assert ConfigSource.ENTERPRISE == "enterprise"
        assert ConfigSource.USER == "user"
        assert ConfigSource.TEAM == "team"
        assert ConfigSource.PROJECT == "project"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_metadata_source(self):
        """Test invalid metadata source."""
        with pytest.raises(ValueError):
            ConfigMetadata(source="invalid_source", priority=50)

    def test_config_with_none_values(self):
        """Test configuration with None values."""
        metadata = ConfigMetadata(source=ConfigSource.USER, priority=50)
        config = MyAIConfig(metadata=metadata, custom={"optional_field": None})

        assert config.custom["optional_field"] is None

    def test_path_handling(self):
        """Test Path object handling in configs."""
        claude_config = ClaudeConfig(config_path=Path("/test/path"), settings_path=Path("/test/settings"))

        assert isinstance(claude_config.config_path, Path)
        assert isinstance(claude_config.settings_path, Path)
        assert str(claude_config.config_path) == "/test/path"
