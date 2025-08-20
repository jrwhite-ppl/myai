"""
Configuration data models for MyAI.

This module contains all the pydantic models for MyAI configuration management,
including hierarchical configuration, tool settings, and validation schemas.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Priority constants for different configuration sources
ENTERPRISE_PRIORITY = 100
USER_MAX_PRIORITY = 75
TEAM_MAX_PRIORITY = 50
PROJECT_MAX_PRIORITY = 25


class MergeStrategy(str, Enum):
    """Configuration merge strategies."""

    MERGE = "merge"  # Deep merge with conflict resolution
    NUCLEAR = "nuclear"  # Complete override


class ConfigSource(str, Enum):
    """Configuration source levels."""

    ENTERPRISE = "enterprise"  # Highest priority (readonly)
    USER = "user"  # User-specific settings
    TEAM = "team"  # Team-specific settings
    PROJECT = "project"  # Project-specific settings (lowest priority)


class ConfigMetadata(BaseModel):
    """Metadata for configuration files."""

    created: datetime = Field(default_factory=datetime.now)
    modified: datetime = Field(default_factory=datetime.now)
    source: ConfigSource
    priority: int = Field(ge=0, le=100)
    version: str = Field(default="1.0.0")
    checksum: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v, info):
        """Validate priority based on source."""
        if info.data:
            source = info.data.get("source")
            if source == ConfigSource.ENTERPRISE and v != ENTERPRISE_PRIORITY:
                return ENTERPRISE_PRIORITY
            elif source == ConfigSource.PROJECT and v > PROJECT_MAX_PRIORITY:
                return PROJECT_MAX_PRIORITY
            elif source == ConfigSource.TEAM and v > TEAM_MAX_PRIORITY:
                return TEAM_MAX_PRIORITY
            elif source == ConfigSource.USER and v > USER_MAX_PRIORITY:
                return USER_MAX_PRIORITY
        return v


class ConfigSettings(BaseModel):
    """Core configuration settings."""

    merge_strategy: MergeStrategy = MergeStrategy.MERGE
    auto_sync: bool = True
    backup_enabled: bool = True
    backup_count: int = Field(default=5, ge=1, le=50)
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, ge=60, le=86400)  # 1 minute to 24 hours
    debug: bool = False

    model_config = ConfigDict(use_enum_values=True, extra="allow")


class ToolConfig(BaseModel):
    """Base class for tool-specific configurations."""

    enabled: bool = True
    auto_sync: bool = True
    config_path: Optional[Path] = None
    backup_before_sync: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class ClaudeConfig(ToolConfig):
    """Claude Code specific configuration."""

    settings_path: Optional[Path] = None
    agents_path: Optional[Path] = None
    mcp_servers: Dict[str, Any] = Field(default_factory=dict)
    custom_instructions: Optional[str] = None
    model_preferences: Dict[str, Any] = Field(default_factory=dict)
    tool_settings: Dict[str, Any] = Field(default_factory=dict)


class CursorConfig(ToolConfig):
    """Cursor specific configuration."""

    rules_path: Optional[Path] = None
    cursor_directory: Optional[Path] = None
    ai_model_settings: Dict[str, Any] = Field(default_factory=dict)
    custom_rules: List[str] = Field(default_factory=list)
    project_specific: bool = True


class AgentConfig(BaseModel):
    """Agent configuration settings."""

    enabled: List[str] = Field(default_factory=list)
    disabled: List[str] = Field(default_factory=list)
    global_enabled: List[str] = Field(default_factory=list)
    global_disabled: List[str] = Field(default_factory=list)
    custom_path: Optional[Path] = None
    auto_discover: bool = True
    categories: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class IntegrationConfig(BaseModel):
    """Integration and sync configuration."""

    auto_sync_interval: int = Field(default=300, ge=60, le=3600)  # 1 minute to 1 hour
    conflict_resolution: str = Field(default="interactive")
    dry_run_default: bool = False
    sync_on_change: bool = True

    @field_validator("conflict_resolution")
    @classmethod
    def validate_conflict_resolution(cls, v):
        """Validate conflict resolution strategy."""
        valid_strategies = ["interactive", "auto", "manual", "abort"]
        if v not in valid_strategies:
            msg = f"Invalid conflict resolution strategy: {v}"
            raise ValueError(msg)
        return v


class MyAIConfig(BaseModel):
    """Complete MyAI configuration."""

    metadata: ConfigMetadata
    settings: ConfigSettings = Field(default_factory=ConfigSettings)
    tools: Dict[str, Union[ClaudeConfig, CursorConfig, ToolConfig]] = Field(default_factory=dict)
    agents: AgentConfig = Field(default_factory=AgentConfig)
    integrations: IntegrationConfig = Field(default_factory=IntegrationConfig)
    custom: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        """Initialize with default tool configs if not provided."""
        if "tools" not in data:
            data["tools"] = {
                "claude": ClaudeConfig(),
                "cursor": CursorConfig(),
            }
        super().__init__(**data)

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True, extra="allow")

    @field_validator("tools", mode="before")
    @classmethod
    def validate_tools(cls, v):
        """Validate and instantiate tool configs."""
        if not isinstance(v, dict):
            return v

        validated_tools: Dict[str, Union[ClaudeConfig, CursorConfig, ToolConfig]] = {}
        for tool_name, tool_config in v.items():
            if isinstance(tool_config, dict):
                if tool_name == "claude":
                    validated_tools[tool_name] = ClaudeConfig(**tool_config)
                elif tool_name == "cursor":
                    validated_tools[tool_name] = CursorConfig(**tool_config)
                else:
                    validated_tools[tool_name] = ToolConfig(**tool_config)
            else:
                validated_tools[tool_name] = tool_config
        return validated_tools
