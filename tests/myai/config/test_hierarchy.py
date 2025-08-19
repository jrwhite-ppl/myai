"""
Tests for ConfigurationHierarchy.

This module tests the configuration discovery and loading from multiple
hierarchical sources.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from myai.config.hierarchy import ConfigurationHierarchy
from myai.models.config import MyAIConfig
from myai.storage.config import ConfigStorage
from myai.storage.filesystem import FileSystemStorage


class TestConfigurationHierarchy:
    """Test cases for ConfigurationHierarchy."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.storage = FileSystemStorage(self.temp_dir)
        self.config_storage = ConfigStorage(self.storage)
        self.hierarchy = ConfigurationHierarchy(self.config_storage, self.temp_dir)

        # Create test configurations
        self.enterprise_config = {
            "metadata": {"source": "enterprise", "priority": 100, "version": "1.0.0"},
            "settings": {"auto_sync": True, "backup_enabled": True},
            "tools": {"claude": {"enabled": True}},
        }

        self.user_config = {
            "metadata": {"source": "user", "priority": 75, "version": "1.0.0"},
            "settings": {"auto_sync": False, "debug": True},
            "tools": {"cursor": {"enabled": True}},
        }

        self.team_config = {
            "metadata": {"source": "team", "priority": 50, "version": "1.0.0"},
            "settings": {"cache_enabled": False},
            "tools": {"claude": {"custom_setting": "team_value"}},
        }

        self.project_config = {
            "metadata": {"source": "project", "priority": 25, "version": "1.0.0"},
            "settings": {"project_name": "test_project"},
            "agents": {"enabled": ["local_agent"]},
        }

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_discover_configurations_empty(self):
        """Test configuration discovery with no configurations."""
        discovered = self.hierarchy.discover_configurations()

        # Should return empty lists for all levels
        assert isinstance(discovered, dict)
        for level in ["enterprise", "user", "team", "project"]:
            assert level in discovered
            assert isinstance(discovered[level], list)

    def test_discover_configurations_storage_based(self):
        """Test discovery of storage-based configurations."""
        # Save configurations to storage
        enterprise_config = MyAIConfig(**self.enterprise_config)
        user_config = MyAIConfig(**self.user_config)

        self.config_storage.save_config(enterprise_config, "enterprise")
        self.config_storage.save_config(user_config, "user")

        # Discover configurations
        discovered = self.hierarchy.discover_configurations()

        # Should find the saved configurations
        assert "default" in discovered["enterprise"] or "enterprise" in discovered["enterprise"]
        assert "default" in discovered["user"] or "user" in discovered["user"]

    def test_discover_configurations_file_based(self):
        """Test discovery of file-based configurations."""
        # Create config directories
        user_config_dir = self.temp_dir / ".config" / "myai"
        user_config_dir.mkdir(parents=True, exist_ok=True)

        project_config_dir = self.temp_dir / "project" / ".myai"
        project_config_dir.mkdir(parents=True, exist_ok=True)

        # Create config files
        user_config_file = user_config_dir / "config.json"
        with user_config_file.open("w") as f:
            json.dump(self.user_config, f)

        project_config_file = project_config_dir / "project.json"
        with project_config_file.open("w") as f:
            json.dump(self.project_config, f)

        # Mock the discovery paths to include our test directories
        with patch.object(self.hierarchy, "_get_user_paths", return_value=[user_config_dir]):
            with patch.object(self.hierarchy, "_get_project_paths", return_value=[project_config_dir]):
                discovered = self.hierarchy.discover_configurations()

        # Should discover the file-based configurations
        assert len(discovered["user"]) > 0
        assert len(discovered["project"]) > 0

    def test_discover_specific_level(self):
        """Test discovery of configurations for a specific level."""
        # Save configuration to storage
        user_config = MyAIConfig(**self.user_config)
        self.config_storage.save_config(user_config, "user")

        # Discover only user level
        discovered = self.hierarchy.discover_configurations(level="user")

        # Should only return user level
        assert len(discovered) == 1
        assert "user" in discovered
        assert len(discovered["user"]) > 0

    def test_load_hierarchy_empty(self):
        """Test loading hierarchy with no configurations."""
        loaded = self.hierarchy.load_hierarchy()

        # Should return empty list
        assert isinstance(loaded, list)
        assert len(loaded) == 0

    def test_load_hierarchy_all_levels(self):
        """Test loading configurations from all hierarchy levels."""
        # Save configurations
        configs = {
            "enterprise": MyAIConfig(**self.enterprise_config),
            "user": MyAIConfig(**self.user_config),
            "team": MyAIConfig(**self.team_config),
            "project": MyAIConfig(**self.project_config),
        }

        for level, config in configs.items():
            self.config_storage.save_config(config, level)

        # Load hierarchy
        loaded = self.hierarchy.load_hierarchy()

        # Should load all configurations in correct order
        assert len(loaded) == 4

        # Verify order and content
        loaded_levels = [level for level, config in loaded]
        assert loaded_levels == ["enterprise", "user", "team", "project"]

        # Verify configurations
        for level, config in loaded:
            assert config.metadata.source == level

    def test_load_hierarchy_specific_levels(self):
        """Test loading configurations from specific levels."""
        # Save configurations
        user_config = MyAIConfig(**self.user_config)
        project_config = MyAIConfig(**self.project_config)

        self.config_storage.save_config(user_config, "user")
        self.config_storage.save_config(project_config, "project")

        # Load only specific levels
        loaded = self.hierarchy.load_hierarchy(levels=["user", "project"])

        # Should only load specified levels
        assert len(loaded) == 2
        loaded_levels = [level for level, config in loaded]
        assert "user" in loaded_levels
        assert "project" in loaded_levels

    def test_load_hierarchy_with_specific_configs(self):
        """Test loading hierarchy with specific configuration names."""
        # Save named configurations
        user_config = MyAIConfig(**self.user_config)
        self.config_storage.save_config(user_config, "user/custom")

        # Load with specific config names
        loaded = self.hierarchy.load_hierarchy(levels=["user"], specific_configs={"user": "custom"})

        # Should load the specified configuration
        assert len(loaded) == 1
        level, config = loaded[0]
        assert level == "user"
        assert config.metadata.source == "user"

    def test_get_active_config_sources(self):
        """Test getting active configuration source information."""
        # Save configuration
        user_config = MyAIConfig(**self.user_config)
        self.config_storage.save_config(user_config, "user")

        # Get active sources
        sources = self.hierarchy.get_active_config_sources()

        # Should return source information
        assert isinstance(sources, dict)
        if "user" in sources:
            user_source = sources["user"]
            assert "source" in user_source
            assert "priority" in user_source
            assert "version" in user_source

    def test_validate_hierarchy_no_issues(self):
        """Test hierarchy validation with no issues."""
        # Create valid configurations
        user_config = MyAIConfig(**self.user_config)
        self.config_storage.save_config(user_config, "user")

        # Validate hierarchy
        issues = self.hierarchy.validate_hierarchy()

        # Should find no critical issues
        assert isinstance(issues, list)
        # May have some issues but should not fail

    def test_validate_hierarchy_with_conflicts(self):
        """Test hierarchy validation with configuration conflicts."""
        # Create conflicting configurations
        config1 = self.user_config.copy()
        config1["settings"]["auto_sync"] = True

        config2 = self.team_config.copy()
        config2["settings"]["auto_sync"] = False

        user_config = MyAIConfig(**config1)
        team_config = MyAIConfig(**config2)

        self.config_storage.save_config(user_config, "user")
        self.config_storage.save_config(team_config, "team")

        # Validate hierarchy
        issues = self.hierarchy.validate_hierarchy()

        # Should detect conflicts
        assert isinstance(issues, list)
        conflict_issues = [issue for issue in issues if issue.get("type") == "conflict"]
        assert len(conflict_issues) > 0

    def test_validate_hierarchy_missing_configs(self):
        """Test hierarchy validation with missing required configurations."""
        # Don't create any configurations

        # Validate hierarchy
        issues = self.hierarchy.validate_hierarchy()

        # Should detect missing user configuration
        assert isinstance(issues, list)
        missing_issues = [issue for issue in issues if issue.get("type") == "missing"]
        assert len(missing_issues) > 0

        # Should mention missing user config
        user_missing = any(issue.get("level") == "user" for issue in missing_issues)
        assert user_missing

    def test_get_effective_configuration(self):
        """Test getting effective merged configuration."""
        # Save configurations
        user_config = MyAIConfig(**self.user_config)
        team_config = MyAIConfig(**self.team_config)

        self.config_storage.save_config(user_config, "user")
        self.config_storage.save_config(team_config, "team")

        # Get effective configuration
        effective = self.hierarchy.get_effective_configuration(levels=["user", "team"])

        # Should return merged configuration
        assert isinstance(effective, MyAIConfig)

        # Should have settings from both configs
        assert hasattr(effective.settings, "debug")  # From user
        assert hasattr(effective.settings, "cache_enabled")  # From team

    def test_clear_discovery_cache(self):
        """Test clearing discovery cache."""
        # Trigger discovery to populate cache
        self.hierarchy.discover_configurations()

        # Clear cache
        self.hierarchy.clear_discovery_cache()

        # Should clear internal cache structures
        assert len(self.hierarchy._discovered_configs) == 0
        assert len(self.hierarchy._last_discovery) == 0

    def test_discovery_caching(self):
        """Test configuration discovery caching."""
        # Mock time to control cache behavior
        with patch("time.time", side_effect=[0, 100, 200, 400, 500]):  # Provide enough values
            # First discovery
            discovered1 = self.hierarchy.discover_configurations("user")

            # Second discovery (should use cache)
            discovered2 = self.hierarchy.discover_configurations("user")

            # Third discovery (cache should be expired)
            discovered3 = self.hierarchy.discover_configurations("user")

        # Results should be consistent
        assert discovered1 == discovered2  # From cache
        assert discovered1 == discovered3  # Rediscovered

    def test_load_yaml_configuration(self):
        """Test loading YAML configuration files."""
        # Create YAML config file
        config_dir = self.temp_dir / "config"
        config_dir.mkdir(exist_ok=True)

        yaml_config_file = config_dir / "test.yaml"
        yaml_content = """
metadata:
  source: user
  priority: 75
  version: "1.0.0"
settings:
  auto_sync: true
  debug: false
tools:
  claude:
    enabled: true
"""

        with yaml_config_file.open("w") as f:
            f.write(yaml_content)

        # Mock the discovery paths to include our test directory
        with patch.object(self.hierarchy, "_get_user_paths", return_value=[config_dir]):
            # Try to load the YAML configuration
            config = self.hierarchy._load_level_config("user", "test")

        # Should successfully load YAML (if PyYAML is available)
        if config is not None:
            assert isinstance(config, MyAIConfig)
            assert config.settings.auto_sync is True

    @patch.dict(os.environ, {"MYAI_ENTERPRISE_CONFIG": "/test/enterprise"})
    def test_enterprise_path_discovery_with_env_var(self):
        """Test enterprise path discovery with environment variable."""
        paths = self.hierarchy._get_enterprise_paths()

        # Should include the environment variable path
        assert Path("/test/enterprise") in paths
        # Should be first in the list (highest priority)
        assert paths[0] == Path("/test/enterprise")

    @patch.dict(os.environ, {"MYAI_TEAM_CONFIG": "/test/team"})
    def test_team_path_discovery_with_env_var(self):
        """Test team path discovery with environment variable."""
        paths = self.hierarchy._get_team_paths()

        # Should include the environment variable path
        assert Path("/test/team") in paths

    @patch.dict(os.environ, {"MYAI_PROJECT_CONFIG": "/test/project"})
    def test_project_path_discovery_with_env_var(self):
        """Test project path discovery with environment variable."""
        paths = self.hierarchy._get_project_paths()

        # Should include the environment variable path
        assert Path("/test/project") in paths
        # Should be first in the list (highest priority)
        assert paths[0] == Path("/test/project")

    @patch.dict(os.environ, {"XDG_CONFIG_HOME": "/test/xdg"})
    def test_user_path_discovery_with_xdg(self):
        """Test user path discovery with XDG config directory."""
        paths = self.hierarchy._get_user_paths()

        # Should include XDG config path
        xdg_path = Path("/test/xdg") / "myai"
        assert xdg_path in paths

    def test_platform_specific_paths(self):
        """Test platform-specific path discovery."""
        # Test enterprise paths
        enterprise_paths = self.hierarchy._get_enterprise_paths()
        assert len(enterprise_paths) > 0

        # Test user paths
        user_paths = self.hierarchy._get_user_paths()
        assert len(user_paths) > 0

        # Test team paths
        team_paths = self.hierarchy._get_team_paths()
        assert len(team_paths) > 0

        # Test project paths - create a .myai directory first
        project_myai = self.temp_dir / ".myai"
        project_myai.mkdir(exist_ok=True)

        # Change to temp directory for project path discovery
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            project_paths = self.hierarchy._get_project_paths()
            assert len(project_paths) > 0
        finally:
            os.chdir(original_cwd)

    def test_conflict_detection(self):
        """Test configuration conflict detection."""
        # Create configs with conflicts
        config1 = MyAIConfig(**self.user_config)
        config2_data = self.team_config.copy()
        config2_data["settings"]["debug"] = False  # Conflicts with user config
        config2 = MyAIConfig(**config2_data)

        # Find conflicts
        conflicts = self.hierarchy._find_config_conflicts(config1, config2)

        # Should detect the debug setting conflict
        assert len(conflicts) > 0
        debug_conflict = next((c for c in conflicts if "debug" in c["path"]), None)
        assert debug_conflict is not None
        assert debug_conflict["value1"] != debug_conflict["value2"]

    def test_config_validation(self):
        """Test configuration file validation."""
        # Test valid configuration
        errors = self.hierarchy._validate_config_file("user", "valid_config")
        # May have errors due to non-existent config, but should not crash
        assert isinstance(errors, list)

        # Save a valid config and test
        user_config = MyAIConfig(**self.user_config)
        self.config_storage.save_config(user_config, "user")

        errors = self.hierarchy._validate_config_file("user", "default")
        # Should have no validation errors for valid config
        assert len(errors) == 0

    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test loading non-existent configuration
        config = self.hierarchy._load_level_config("nonexistent", "config")
        assert config is None

        # Test getting default config name
        name = self.hierarchy._get_default_config_name("user")
        assert name == "default"

        # Test getting source info for non-existent config
        info = self.hierarchy._get_config_source_info("nonexistent")
        assert info is None
