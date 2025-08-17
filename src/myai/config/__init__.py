"""
Configuration management package for MyAI.

This package provides centralized configuration management with hierarchical
configuration loading, caching, validation, and real-time watching.
"""

from myai.config.hierarchy import ConfigurationHierarchy
from myai.config.manager import ConfigurationManager, get_config_manager
from myai.config.merger import ConfigurationMerger, ConflictResolution, ConflictType

__all__ = [
    "ConfigurationManager",
    "get_config_manager",
    "ConfigurationHierarchy",
    "ConfigurationMerger",
    "ConflictResolution",
    "ConflictType",
]
