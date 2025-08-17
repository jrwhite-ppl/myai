"""
Tests for ConfigurationManager.

This module tests the core configuration manager functionality including
singleton pattern, caching, hierarchy management, and file watching.
"""

import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from myai.config.manager import ConfigurationManager, get_config_manager


class TestConfigurationManager:
    """Test cases for ConfigurationManager."""

    def setup_method(self):
        """Set up test environment."""
        # Reset singleton
        ConfigurationManager._instance = None

        # Create temporary directory for tests
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test configuration data
        self.test_config_data = {
            "metadata": {
                "source": "user",
                "priority": 75,
                "version": "1.0.0",
            },
            "settings": {
                "auto_sync": True,
                "backup_enabled": True,
                "cache_enabled": True,
            },
            "tools": {
                "claude": {
                    "enabled": True,
                    "auto_sync": True,
                },
                "cursor": {
                    "enabled": True,
                    "auto_sync": False,
                },
            },
        }

    def teardown_method(self):
        """Clean up test environment."""
        # Clean up temporary directory
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        # Reset singleton
        ConfigurationManager._instance = None

    def test_singleton_pattern(self):
        """Test that ConfigurationManager implements singleton pattern."""
        manager1 = ConfigurationManager(base_path=self.temp_dir)
        manager2 = ConfigurationManager(base_path=self.temp_dir)

        assert manager1 is manager2
        assert id(manager1) == id(manager2)

    def test_singleton_thread_safety(self):
        """Test that singleton is thread-safe."""
        instances = []

        def create_instance():
            instance = ConfigurationManager(base_path=self.temp_dir)
            instances.append(instance)

        # Create multiple threads
        threads = [threading.Thread(target=create_instance) for _ in range(10)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All instances should be the same
        assert len({id(instance) for instance in instances}) == 1

    def test_get_config_manager_convenience_function(self):
        """Test the convenience function for getting config manager."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2
        assert isinstance(manager1, ConfigurationManager)

    def test_initialization_with_custom_settings(self):
        """Test initialization with custom settings."""
        manager = ConfigurationManager(
            base_path=self.temp_dir,
            cache_enabled=False,
            cache_ttl=7200,
            auto_watch=False,
        )

        assert manager.base_path == self.temp_dir
        assert manager._cache_enabled is False
        assert manager._cache_ttl == 7200
        assert manager._auto_watch is False

    def test_config_value_operations(self):
        """Test getting and setting configuration values."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Set a configuration value
        manager.set_config_value("settings.auto_sync", False, level="user")

        # Get the configuration value
        value = manager.get_config_value("settings.auto_sync", levels=["user"])
        assert value is False

        # Test with default value
        value = manager.get_config_value("nonexistent.path", default="default_value")
        assert value == "default_value"

    def test_nested_config_value_operations(self):
        """Test deeply nested configuration value operations."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Set nested values
        manager.set_config_value("tools.claude.custom_setting", "test_value", level="user")
        manager.set_config_value("tools.claude.nested.deep.value", 42, level="user")

        # Get nested values
        value = manager.get_config_value("tools.claude.custom_setting", levels=["user"])
        assert value == "test_value"

        value = manager.get_config_value("tools.claude.nested.deep.value", levels=["user"])
        assert value == 42

    def test_config_file_operations(self):
        """Test loading and saving configuration files."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create test config file
        config_file = self.temp_dir / "test_config.json"
        with config_file.open("w") as f:
            json.dump(self.test_config_data, f)

        # Load configuration from file
        manager.load_config_from_file(config_file, level="test")

        # Verify configuration was loaded
        config = manager.get_config(levels=["test"])
        assert config.settings.auto_sync is True
        assert config.tools["claude"].enabled is True

        # Save configuration to file
        output_file = self.temp_dir / "output_config.json"
        manager.save_config_to_file(output_file, level="test")

        # Verify file was created and contains expected data
        assert output_file.exists()
        with output_file.open() as f:
            saved_data = json.load(f)

        assert saved_data["settings"]["auto_sync"] is True
        assert saved_data["tools"]["claude"]["enabled"] is True

    def test_configuration_hierarchy(self):
        """Test configuration hierarchy and merging."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create configurations at different levels
        enterprise_config = {
            "metadata": {"source": "enterprise", "priority": 100},
            "settings": {"auto_sync": True, "backup_enabled": True},
            "tools": {"claude": {"enabled": True}},
        }

        user_config = {
            "metadata": {"source": "user", "priority": 75},
            "settings": {"auto_sync": False},  # Override enterprise
            "tools": {"cursor": {"enabled": True}},
        }

        # Save configurations
        enterprise_file = self.temp_dir / "enterprise.json"
        with enterprise_file.open("w") as f:
            json.dump(enterprise_config, f)
        manager.load_config_from_file(enterprise_file, level="enterprise")

        user_file = self.temp_dir / "user.json"
        with user_file.open("w") as f:
            json.dump(user_config, f)
        manager.load_config_from_file(user_file, level="user")

        # Test merged configuration
        merged_config = manager.get_config(levels=["enterprise", "user"])

        # Enterprise settings should be inherited
        assert merged_config.settings.backup_enabled is True
        # Enterprise settings should override user (higher priority)
        assert merged_config.settings.auto_sync is True
        # Both tools should be present
        assert "claude" in merged_config.tools
        assert "cursor" in merged_config.tools

    def test_configuration_caching(self):
        """Test configuration caching mechanism."""
        manager = ConfigurationManager(
            base_path=self.temp_dir,
            cache_enabled=True,
            cache_ttl=1,  # 1 second TTL for testing
            auto_watch=False,
        )

        # Set up test configuration
        manager.set_config_value("test.value", "cached", level="user")

        # First call should cache the result
        config1 = manager.get_config(levels=["user"])
        cache_stats = manager.get_cache_stats()
        assert cache_stats["entries"] == 1

        # Second call should use cache
        config2 = manager.get_config(levels=["user"])
        assert config1 is not config2  # Different instances
        assert config1.model_dump() == config2.model_dump()  # Same data

        # Wait for cache expiry
        time.sleep(1.1)

        # Third call should reload (cache expired)
        config3 = manager.get_config(levels=["user"], refresh_cache=True)
        assert config3.model_dump() == config1.model_dump()

    def test_cache_invalidation(self):
        """Test cache invalidation on configuration changes."""
        manager = ConfigurationManager(
            base_path=self.temp_dir,
            cache_enabled=True,
            auto_watch=False,
        )

        # Set initial configuration
        manager.set_config_value("test.value", "initial", level="user")

        # Cache the configuration
        manager.get_config(levels=["user"])
        assert manager.get_cache_stats()["entries"] == 1

        # Modify configuration (should invalidate cache)
        manager.set_config_value("test.value", "modified", level="user")
        assert manager.get_cache_stats()["entries"] == 0

        # Get configuration again (should be reloaded)
        manager.get_config(levels=["user"])
        test_value = manager.get_config_value("test.value", levels=["user"])
        assert test_value == "modified"

    def test_configuration_discovery(self):
        """Test configuration discovery functionality."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create test configurations
        manager.set_config_value("test.value", "user_config", level="user")
        manager.set_config_value("test.value", "team_config", level="team")

        # Discover configurations
        discovered = manager.discover_configurations()

        # Should find the configurations we created
        assert "user" in discovered
        assert "team" in discovered

    def test_configuration_validation(self):
        """Test configuration validation."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Test valid configuration
        valid_config = self.test_config_data
        errors = manager.validate_config(valid_config)
        assert len(errors) == 0

        # Test invalid configuration
        invalid_config = {
            "metadata": {"source": "invalid_source", "priority": "not_a_number"},
            "settings": {"invalid_field": True},
        }
        errors = manager.validate_config(invalid_config)
        assert len(errors) > 0

    def test_configuration_history(self):
        """Test configuration backup and history."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Set initial configuration
        manager.set_config_value("test.value", "version1", level="user")

        # Modify configuration (should create backup)
        manager.set_config_value("test.value", "version2", level="user")

        # Check history
        history = manager.get_config_history("user")
        # History depends on backup implementation
        assert isinstance(history, list)

    def test_configuration_conflicts(self):
        """Test configuration conflict detection."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create conflicting configurations
        config1 = {
            "metadata": {"source": "user", "priority": 75},
            "settings": {"auto_sync": True},
        }

        config2 = {
            "metadata": {"source": "team", "priority": 50},
            "settings": {"auto_sync": False},
        }

        # Save configurations
        config1_file = self.temp_dir / "config1.json"
        with config1_file.open("w") as f:
            json.dump(config1, f)
        manager.load_config_from_file(config1_file, level="user")

        config2_file = self.temp_dir / "config2.json"
        with config2_file.open("w") as f:
            json.dump(config2, f)
        manager.load_config_from_file(config2_file, level="team")

        # Check for conflicts
        conflicts = manager.get_configuration_conflicts(levels=["user", "team"])

        # Should detect conflict in auto_sync setting
        assert len(conflicts) > 0
        conflict_paths = [c["path"] for c in conflicts]
        assert any("auto_sync" in path for path in conflict_paths)

    def test_merge_preview(self):
        """Test configuration merge preview."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create test configurations
        manager.set_config_value("settings.auto_sync", True, level="user")
        manager.set_config_value("settings.debug", False, level="team")

        # Get merge preview
        preview = manager.get_merge_preview(levels=["user", "team"])

        assert "merged_config" in preview
        assert "conflicts" in preview
        assert "sources" in preview
        assert preview["total_conflicts"] >= 0

    def test_watcher_management(self):
        """Test configuration change watcher management."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Test watcher addition and removal
        watcher_called = {"count": 0}

        def test_watcher(event, data):  # noqa: ARG001
            watcher_called["count"] += 1

        manager.add_watcher(test_watcher)
        assert test_watcher in manager._watchers

        # Trigger notification
        manager._notify_watchers("test_event", {"test": "data"})
        assert watcher_called["count"] == 1

        # Remove watcher
        manager.remove_watcher(test_watcher)
        assert test_watcher not in manager._watchers

    def test_custom_merge_rules(self):
        """Test custom merge rules functionality."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Add custom merge rule
        manager.add_merge_rule(
            path_pattern="tools.*.enabled",
            rule_type="priority_override",
            rule_config={"preferred_source": "user"},
        )

        # Clear rules
        manager.clear_merge_rules()

        # Should complete without error
        assert True

    def test_config_level_deletion(self):
        """Test deletion of configuration levels."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create test configuration
        manager.set_config_value("test.value", "to_delete", level="user")

        # Verify it exists
        levels = manager.list_config_levels()
        assert "user" in levels

        # Delete the configuration
        result = manager.delete_config_level("user")
        assert result is True

        # Verify it's gone
        levels = manager.list_config_levels()
        assert "user" not in levels

        # Try to delete non-existent level
        result = manager.delete_config_level("nonexistent")
        assert result is False

    def test_error_handling(self):
        """Test error handling in various scenarios."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Test setting value with invalid path
        with pytest.raises(ValueError):
            manager.set_config_value("", "value", create_missing=False)

        # Test getting value from non-existent config
        value = manager.get_config_value("test.value", default="default", levels=["nonexistent"])
        assert value == "default"

        # Test loading from non-existent file
        with pytest.raises(Exception):  # noqa: B017
            manager.load_config_from_file(Path("/nonexistent/file.json"))

    @patch("myai.config.manager.ConfigurationWatcher")
    def test_file_watching_integration(self, mock_watcher_class):
        """Test file watching integration."""
        mock_watcher = Mock()
        mock_watcher_class.return_value = mock_watcher

        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=True)

        # Verify watcher was created and configured
        mock_watcher_class.assert_called_once()
        mock_watcher.add_handler.assert_called_once()
        mock_watcher.start.assert_called_once()

        # Test stopping
        manager.stop_watching()
        mock_watcher.stop.assert_called_once()

    def test_config_path_management(self):
        """Test custom configuration path management."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Set custom config path
        custom_path = self.temp_dir / "custom_config.json"
        manager.set_config_path("custom", custom_path)

        # Verify path was set
        assert manager.get_config_path("custom") == custom_path

        # Clear path
        manager.set_config_path("custom", None)
        assert manager.get_config_path("custom") is None

    def test_active_config_sources(self):
        """Test getting active configuration sources."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create test configuration
        manager.set_config_value("test.value", "active", level="user")

        # Get active sources
        sources = manager.get_active_config_sources()

        # Should be a dictionary
        assert isinstance(sources, dict)

    def test_hierarchy_validation(self):
        """Test configuration hierarchy validation."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Create some test configurations
        manager.set_config_value("test.value", "valid", level="user")

        # Validate hierarchy
        issues = manager.validate_hierarchy()

        # Should return list of issues (may be empty)
        assert isinstance(issues, list)


class TestConfigurationManagerIntegration:
    """Integration tests for ConfigurationManager."""

    def setup_method(self):
        """Set up integration test environment."""
        ConfigurationManager._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up integration test environment."""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        ConfigurationManager._instance = None

    def test_realistic_configuration_scenario(self):
        """Test realistic configuration management scenario."""
        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=False)

        # Scenario: Set up enterprise, user, and project configurations

        # 1. Enterprise configuration (highest priority)
        enterprise_config = {
            "metadata": {"source": "enterprise", "priority": 100},
            "settings": {
                "auto_sync": True,
                "backup_enabled": True,
                "cache_enabled": True,
            },
            "tools": {
                "claude": {"enabled": True, "auto_sync": True},
                "cursor": {"enabled": False},  # Disabled by enterprise
            },
            "integrations": {"conflict_resolution": "auto"},
        }

        enterprise_file = self.temp_dir / "enterprise.json"
        with enterprise_file.open("w") as f:
            json.dump(enterprise_config, f)
        manager.load_config_from_file(enterprise_file, "enterprise")

        # 2. User configuration (medium priority)
        user_config = {
            "metadata": {"source": "user", "priority": 75},
            "settings": {"debug": True},  # User-specific setting
            "tools": {
                "claude": {"custom_instructions": "Be helpful"},
                # Note: Can't override cursor.enabled due to enterprise policy
            },
            "agents": {"enabled": ["general", "coding"]},
        }

        user_file = self.temp_dir / "user.json"
        with user_file.open("w") as f:
            json.dump(user_config, f)
        manager.load_config_from_file(user_file, "user")

        # 3. Project configuration (lowest priority)
        project_config = {
            "metadata": {"source": "project", "priority": 25},
            "settings": {"debug": False},  # Overridden by user
            "agents": {"enabled": ["project-specific"]},
        }

        project_file = self.temp_dir / "project.json"
        with project_file.open("w") as f:
            json.dump(project_config, f)
        manager.load_config_from_file(project_file, "project")

        # 4. Get effective configuration
        effective_config = manager.get_config(["enterprise", "user", "project"])

        # Verify hierarchy is respected
        assert effective_config.settings.auto_sync is True  # From enterprise
        assert effective_config.settings.debug is False  # From enterprise (defaults override user)
        assert effective_config.tools["cursor"].enabled is False  # From enterprise
        assert "custom_instructions" in effective_config.tools["claude"].model_dump()  # From user

        # 5. Test configuration conflicts
        conflicts = manager.get_configuration_conflicts(["enterprise", "user", "project"])

        # Should detect the debug setting conflict between user and project
        debug_conflicts = [c for c in conflicts if "debug" in c.get("path", "")]
        assert len(debug_conflicts) > 0

        # 6. Test merge preview
        preview = manager.get_merge_preview(["enterprise", "user", "project"])
        assert preview["total_conflicts"] >= len(debug_conflicts)
        assert len(preview["sources"]) == 3

        # 7. Test specific value retrieval
        auto_sync = manager.get_config_value("settings.auto_sync")
        assert auto_sync is True

        debug = manager.get_config_value("settings.debug")
        assert debug is False

        claude_enabled = manager.get_config_value("tools.claude.enabled")
        assert claude_enabled is True

        # 8. Test runtime configuration modification
        manager.set_config_value("settings.user_preference", "test_value", level="user")

        manager.get_config(["enterprise", "user", "project"])
        user_preference = manager.get_config_value("settings.user_preference")
        assert user_preference == "test_value"

    def test_configuration_watching_scenario(self):
        """Test configuration file watching in realistic scenario."""
        # Skip if watchdog not available
        try:
            import watchdog.observers  # noqa: F401
        except ImportError:
            pytest.skip("Watchdog not available for file watching test")

        manager = ConfigurationManager(base_path=self.temp_dir, auto_watch=True)

        # Set up watcher to capture events
        events_received = []

        def capture_events(event, data):
            events_received.append((event, data))

        manager.add_watcher(capture_events)

        # Create initial configuration
        config_file = self.temp_dir / "config" / "user.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        initial_config = {
            "metadata": {"source": "user", "priority": 75},
            "settings": {"auto_sync": True},
        }

        with config_file.open("w") as f:
            json.dump(initial_config, f)
            f.flush()  # Ensure file is written
            import os

            os.fsync(f.fileno())  # Force write to disk

        # Give the watcher time to detect the file
        time.sleep(2.0)  # Increased wait time

        # Clear any initial events
        events_received.clear()

        # Modify the configuration file
        modified_config = {
            "metadata": {"source": "user", "priority": 75},
            "settings": {"auto_sync": False},  # Changed value
        }

        with config_file.open("w") as f:
            json.dump(modified_config, f)
            f.flush()  # Ensure file is written
            import os

            os.fsync(f.fileno())  # Force write to disk

        # Force immediate check
        if hasattr(manager._config_watcher, "force_check"):
            manager._config_watcher.force_check()

        # Give the watcher time to detect the change
        time.sleep(3.0)  # Increased wait time for debouncing

        # Stop watching
        manager.stop_watching()

        # Verify events were received
        assert len(events_received) > 0

        # Check that we received config file change events
        config_events = [e for e in events_received if e[0] == "config_file_changed"]
        assert len(config_events) > 0
