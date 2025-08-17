"""Tests for path models."""

import os
import tempfile
from pathlib import Path

import pytest

from myai.models.path import DirectoryLayout, PathConfig


class TestPathConfig:
    """Test PathConfig model."""

    def test_default_path_config(self):
        """Test default path configuration."""
        config = PathConfig()

        assert config.myai_home == Path.home() / ".myai"
        assert config.config_dir == Path.home() / ".myai" / "config"
        assert config.agents_dir == Path.home() / ".myai" / "agents"
        assert config.templates_dir == Path.home() / ".myai" / "templates"
        assert config.cache_dir == Path.home() / ".myai" / "cache"
        assert config.logs_dir == Path.home() / ".myai" / "logs"
        assert config.backups_dir == Path.home() / ".myai" / "backups"
        assert config.claude_config == Path.home() / ".claude"
        assert config.cursor_config == Path.home() / ".cursor"

    def test_custom_path_config(self):
        """Test custom path configuration."""
        custom_home = Path("/custom/myai")
        config = PathConfig(
            myai_home=custom_home,
            project_root=Path("/project"),
        )

        assert config.myai_home == custom_home
        assert config.project_root == Path("/project")

    def test_string_path_conversion(self):
        """Test string to Path conversion."""
        config = PathConfig(myai_home="/custom/myai", agents_dir="/custom/agents")

        assert isinstance(config.myai_home, Path)
        assert isinstance(config.agents_dir, Path)
        assert str(config.myai_home) == "/custom/myai"
        assert str(config.agents_dir) == "/custom/agents"

    def test_environment_variable_expansion(self):
        """Test environment variable expansion in paths."""
        # Set test environment variable
        test_var = "MYAI_TEST_PATH"
        test_value = "/test/myai"
        os.environ[test_var] = test_value

        try:
            config = PathConfig(myai_home=f"${test_var}")
            assert str(config.myai_home) == test_value
        finally:
            # Clean up
            del os.environ[test_var]

    def test_user_home_expansion(self):
        """Test user home directory expansion."""
        config = PathConfig(myai_home="~/custom_myai")

        expected = Path.home() / "custom_myai"
        assert config.myai_home == expected

    def test_resolve_path_absolute(self):
        """Test absolute path resolution."""
        config = PathConfig()
        absolute_path = Path("/absolute/path")

        resolved = config.resolve_path(absolute_path)
        assert resolved == absolute_path

    def test_resolve_path_relative(self):
        """Test relative path resolution."""
        config = PathConfig()
        relative_path = Path("relative/path")

        resolved = config.resolve_path(relative_path)
        expected = config.myai_home / relative_path
        assert resolved == expected

    def test_resolve_path_string(self):
        """Test path resolution with string input."""
        config = PathConfig()

        resolved = config.resolve_path("config/test.json")
        expected = config.myai_home / "config" / "test.json"
        assert resolved == expected

    def test_get_config_path_global(self):
        """Test global config path."""
        config = PathConfig()

        path = config.get_config_path("global")
        expected = config.config_dir / "global.json"
        assert path == expected

        # User should be same as global
        user_path = config.get_config_path("user")
        assert user_path == expected

    def test_get_config_path_project(self):
        """Test project config path."""
        config = PathConfig()

        # Without project_config set
        path = config.get_config_path("project")
        expected = Path.cwd() / ".myai" / "config.json"
        assert path == expected

        # With project_config set
        custom_project = Path("/custom/project/config.json")
        config.project_config = custom_project
        path = config.get_config_path("project")
        assert path == custom_project

    def test_get_config_path_team(self):
        """Test team config path."""
        config = PathConfig()

        path = config.get_config_path("team.engineering")
        expected = config.config_dir / "teams" / "engineering.json"
        assert path == expected

    def test_get_config_path_enterprise(self):
        """Test enterprise config path."""
        config = PathConfig()

        path = config.get_config_path("enterprise.acme")
        expected = config.config_dir / "enterprise" / "acme.json"
        assert path == expected

    def test_get_config_path_invalid(self):
        """Test invalid config path."""
        config = PathConfig()

        with pytest.raises(ValueError):
            config.get_config_path("invalid_level")

    def test_ensure_directories(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config = PathConfig(myai_home=temp_path / "myai")

            # Directories shouldn't exist yet
            assert not config.myai_home.exists()

            # Create directories
            config.ensure_directories()

            # Check all directories exist
            assert config.myai_home.exists()
            assert config.config_dir.exists()
            assert config.agents_dir.exists()
            assert config.templates_dir.exists()
            assert config.cache_dir.exists()
            assert config.logs_dir.exists()
            assert config.backups_dir.exists()
            assert (config.config_dir / "teams").exists()
            assert (config.config_dir / "enterprise").exists()
            assert (config.agents_dir / "default").exists()
            assert (config.agents_dir / "custom").exists()

            # Check permissions on sensitive directories
            assert oct(config.config_dir.stat().st_mode)[-3:] == "700"
            assert oct(config.cache_dir.stat().st_mode)[-3:] == "700"
            assert oct(config.logs_dir.stat().st_mode)[-3:] == "700"
            assert oct(config.backups_dir.stat().st_mode)[-3:] == "700"


class TestDirectoryLayout:
    """Test DirectoryLayout model."""

    def test_basic_layout_creation(self):
        """Test basic layout creation."""
        layout = DirectoryLayout(
            name="test_layout",
            description="Test layout",
            structure={
                "config": {
                    "settings.json": "{}",
                },
                "data": {},
            },
        )

        assert layout.name == "test_layout"
        assert layout.description == "Test layout"
        assert "config" in layout.structure
        assert "data" in layout.structure

    def test_create_structure(self):
        """Test structure creation."""
        layout = DirectoryLayout(
            name="test",
            description="Test layout",
            structure={
                "config": {
                    "settings.json": '{"test": true}',
                    "subdir": {
                        "nested.json": "{}",
                    },
                },
                "empty_dir": {},
                "single_file.txt": "content here",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "test_structure"
            created_paths = layout.create_structure(base_path)

            # Check directories were created
            assert (base_path / "config").exists()
            assert (base_path / "config").is_dir()
            assert (base_path / "config" / "subdir").exists()
            assert (base_path / "empty_dir").exists()

            # Check files were created with content
            settings_file = base_path / "config" / "settings.json"
            assert settings_file.exists()
            assert settings_file.read_text() == '{"test": true}'

            nested_file = base_path / "config" / "subdir" / "nested.json"
            assert nested_file.exists()
            assert nested_file.read_text() == "{}"

            single_file = base_path / "single_file.txt"
            assert single_file.exists()
            assert single_file.read_text() == "content here"

            # Check return value contains created paths
            assert len(created_paths) > 0
            assert base_path / "config" in created_paths
            assert settings_file in created_paths

    def test_create_structure_existing_files(self):
        """Test structure creation with existing files."""
        layout = DirectoryLayout(
            name="test",
            description="Test layout",
            structure={
                "existing_file.txt": "new content",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            existing_file = base_path / "existing_file.txt"

            # Create existing file
            existing_file.write_text("original content")

            # Create structure (should not overwrite)
            created_paths = layout.create_structure(base_path)

            # File should still have original content
            assert existing_file.read_text() == "original content"

            # File should not be in created_paths
            assert existing_file not in created_paths

    def test_get_default_layout(self):
        """Test default layout generation."""
        layout = DirectoryLayout.get_default_layout()

        assert layout.name == "default"
        assert "config" in layout.structure
        assert "agents" in layout.structure
        assert "templates" in layout.structure
        assert "cache" in layout.structure
        assert "logs" in layout.structure
        assert "backups" in layout.structure

        # Check nested structure
        config_structure = layout.structure["config"]
        assert "global.json" in config_structure
        assert "teams" in config_structure
        assert "enterprise" in config_structure

        agents_structure = layout.structure["agents"]
        assert "default" in agents_structure
        assert "custom" in agents_structure

        # Check agent categories
        default_agents = agents_structure["default"]
        expected_categories = ["engineering", "business", "marketing", "finance", "legal", "security", "leadership"]
        for category in expected_categories:
            assert category in default_agents

    def test_get_project_layout(self):
        """Test project layout generation."""
        layout = DirectoryLayout.get_project_layout()

        assert layout.name == "project"
        assert ".myai" in layout.structure

        myai_structure = layout.structure[".myai"]
        assert "config.json" in myai_structure
        assert "agents" in myai_structure
        assert "overrides" in myai_structure

    def test_create_default_layout(self):
        """Test creating default layout structure."""
        layout = DirectoryLayout.get_default_layout()

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "myai_default"
            layout.create_structure(base_path)

            # Check main directories
            assert (base_path / "config").exists()
            assert (base_path / "agents").exists()
            assert (base_path / "templates").exists()

            # Check config files
            assert (base_path / "config" / "global.json").exists()
            assert (base_path / "config" / "teams").exists()
            assert (base_path / "config" / "enterprise").exists()

            # Check agent directories
            agent_categories = ["engineering", "business", "marketing", "finance", "legal", "security", "leadership"]
            for category in agent_categories:
                assert (base_path / "agents" / "default" / category).exists()

            assert (base_path / "agents" / "custom").exists()

            # Check template files
            assert (base_path / "templates" / "config.json").exists()
            assert (base_path / "templates" / "agent.md").exists()

    def test_create_project_layout(self):
        """Test creating project layout structure."""
        layout = DirectoryLayout.get_project_layout()

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "project"
            layout.create_structure(base_path)

            # Check project structure
            assert (base_path / ".myai").exists()
            assert (base_path / ".myai" / "config.json").exists()
            assert (base_path / ".myai" / "agents").exists()
            assert (base_path / ".myai" / "overrides").exists()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_path_config_with_none_values(self):
        """Test path config with None values."""
        config = PathConfig(project_root=None, project_config=None, claude_config=None, cursor_config=None)

        assert config.project_root is None
        assert config.project_config is None
        assert config.claude_config is None
        assert config.cursor_config is None

    def test_empty_directory_layout(self):
        """Test empty directory layout."""
        layout = DirectoryLayout(name="empty", description="Empty layout", structure={})

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "empty"
            created_paths = layout.create_structure(base_path)

            assert len(created_paths) == 0
            # Base path itself shouldn't be created if structure is empty

    def test_complex_nested_structure(self):
        """Test complex nested directory structure."""
        layout = DirectoryLayout(
            name="complex",
            description="Complex nested structure",
            structure={
                "level1": {
                    "level2": {
                        "level3": {
                            "deep_file.txt": "deep content",
                            "level4": {},
                        },
                        "file2.json": "{}",
                    },
                    "file1.txt": "content",
                },
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "complex"
            created_paths = layout.create_structure(base_path)

            # Check deep nesting
            deep_file = base_path / "level1" / "level2" / "level3" / "deep_file.txt"
            assert deep_file.exists()
            assert deep_file.read_text() == "deep content"

            # Check empty deep directory
            deep_dir = base_path / "level1" / "level2" / "level3" / "level4"
            assert deep_dir.exists()
            assert deep_dir.is_dir()

            assert len(created_paths) > 0
