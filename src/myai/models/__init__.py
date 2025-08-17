"""
MyAI data models and schemas.

This package contains all the data models and schemas used by MyAI,
including configuration models, agent specifications, and validation schemas.
"""

from myai.models.agent import (
    AgentCategory,
    AgentMetadata,
    AgentSpecification,
)
from myai.models.config import (
    AgentConfig,
    ClaudeConfig,
    ConfigMetadata,
    ConfigSettings,
    CursorConfig,
    IntegrationConfig,
    MyAIConfig,
    ToolConfig,
)
from myai.models.path import (
    DirectoryLayout,
    PathConfig,
)

__all__ = [
    # Configuration models
    "ConfigMetadata",
    "ConfigSettings",
    "ToolConfig",
    "ClaudeConfig",
    "CursorConfig",
    "AgentConfig",
    "IntegrationConfig",
    "MyAIConfig",
    # Agent models
    "AgentMetadata",
    "AgentSpecification",
    "AgentCategory",
    # Path models
    "PathConfig",
    "DirectoryLayout",
]
