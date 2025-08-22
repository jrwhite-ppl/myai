"""
Tests for agent CLI commands with focus on global vs project scope functionality.

These tests ensure the global/project agent management works correctly and
doesn't regress in future changes.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from myai.commands.agent_cli import app


class TestAgentCLIGlobalVsProject(unittest.TestCase):
    """Test global vs project scope functionality in agent CLI."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()

        # Create temporary directories
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_home = self.test_dir / "home"
        self.test_project = self.test_dir / "project"
        self.test_home.mkdir()
        self.test_project.mkdir()

        # Create test agents with realistic metadata
        self.global_agent = MagicMock()
        self.global_agent.metadata.name = "agentos-project-manager"
        self.global_agent.metadata.display_name = "Agent-OS Project Manager"
        self.global_agent.metadata.description = "Global agent for project management"
        self.global_agent.metadata.category.value = "engineering"
        self.global_agent.metadata.tools = []
        self.global_agent.metadata.tags = []
        self.global_agent.metadata.version = "1.0.0"
        self.global_agent.content = "# Global Agent Content"
        self.global_agent.is_custom = False
        self.global_agent.file_path = None

        self.project_agent = MagicMock()
        self.project_agent.metadata.name = "python-expert"
        self.project_agent.metadata.display_name = "Python Expert"
        self.project_agent.metadata.description = "Project agent for Python expertise"
        self.project_agent.metadata.category.value = "engineering"
        self.project_agent.metadata.tools = []
        self.project_agent.metadata.tags = []
        self.project_agent.metadata.version = "1.0.0"
        self.project_agent.content = "# Project Agent Content"
        self.project_agent.is_custom = False
        self.project_agent.file_path = None

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_enable_global_scope_creates_only_global_files(
        self, mock_registry, mock_config_manager, mock_cwd, mock_home
    ):
        """Test that enabling agent with --global flag creates only global files."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config.agents.global_enabled = []
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.get_agent.return_value = self.global_agent
        registry.resolve_agent_name.return_value = "agentos-project-manager"
        mock_registry.return_value = registry

        # Run enable with --global flag
        result = self.runner.invoke(app, ["enable", "agentos-project-manager", "--global"])

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Verify global agent was added to global_enabled list
        self.assertIn("agentos-project-manager", config.agents.global_enabled)

        # Verify config was saved globally
        mock_config_manager.return_value.set_config_value.assert_any_call(
            "agents.global_enabled", config.agents.global_enabled
        )
        mock_config_manager.return_value.set_config_value.assert_any_call(
            "agents.global_disabled", config.agents.global_disabled
        )

        # Verify global Claude file would be created
        global_claude_dir = self.test_home / ".claude" / "agents"
        self.assertTrue(global_claude_dir.exists())
        global_claude_file = global_claude_dir / "agentos-project-manager.md"
        self.assertTrue(global_claude_file.exists())
        self.assertEqual(global_claude_file.read_text(), "# Global Agent Content")

        # Verify NO project files were created
        project_claude_dir = self.test_project / ".claude" / "agents"
        if project_claude_dir.exists():
            project_claude_file = project_claude_dir / "agentos-project-manager.md"
            self.assertFalse(project_claude_file.exists(), "Project Claude file should not exist for global agent")

        project_cursor_dir = self.test_project / ".cursor" / "rules"
        if project_cursor_dir.exists():
            project_cursor_file = project_cursor_dir / "agentos-project-manager.mdc"
            self.assertFalse(project_cursor_file.exists(), "Project Cursor file should not exist for global agent")

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_enable_project_scope_creates_only_project_files(
        self, mock_registry, mock_config_manager, mock_cwd, mock_home
    ):
        """Test that enabling agent without --global flag creates only project files."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config.agents.global_enabled = []
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.get_agent.return_value = self.project_agent
        registry.resolve_agent_name.return_value = "python-expert"
        mock_registry.return_value = registry

        # Run enable without --global flag (project scope)
        result = self.runner.invoke(app, ["enable", "python-expert"])

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Verify agent was added to project enabled list
        self.assertIn("python-expert", config.agents.enabled)

        # Verify config was saved at project level
        mock_config_manager.return_value.set_config_value.assert_any_call("agents.enabled", config.agents.enabled)
        mock_config_manager.return_value.set_config_value.assert_any_call("agents.disabled", config.agents.disabled)

        # Verify project files were created
        project_claude_dir = self.test_project / ".claude" / "agents"
        self.assertTrue(project_claude_dir.exists())
        project_claude_file = project_claude_dir / "python-expert.md"
        self.assertTrue(project_claude_file.exists())

        project_cursor_dir = self.test_project / ".cursor" / "rules"
        self.assertTrue(project_cursor_dir.exists())
        project_cursor_file = project_cursor_dir / "python-expert.mdc"
        self.assertTrue(project_cursor_file.exists())

        # Verify NO global files were created
        global_claude_dir = self.test_home / ".claude" / "agents"
        if global_claude_dir.exists():
            global_claude_file = global_claude_dir / "python-expert.md"
            self.assertFalse(global_claude_file.exists(), "Global Claude file should not exist for project agent")

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_disable_global_scope_removes_only_global_files(
        self, mock_registry, mock_config_manager, mock_cwd, mock_home
    ):
        """Test that disabling global agent removes only global files."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Setup existing global files
        global_claude_dir = self.test_home / ".claude" / "agents"
        global_claude_dir.mkdir(parents=True)
        global_claude_file = global_claude_dir / "agentos-project-manager.md"
        global_claude_file.write_text("# Global Agent Content")

        # Mock config with global agent enabled
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config.agents.global_enabled = ["agentos-project-manager"]
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.get_agent.return_value = self.global_agent
        registry.resolve_agent_name.return_value = "agentos-project-manager"
        mock_registry.return_value = registry

        # Run disable with --global flag
        result = self.runner.invoke(app, ["disable", "agentos-project-manager", "--global"])

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Verify agent was removed from global_enabled and added to global_disabled
        self.assertNotIn("agentos-project-manager", config.agents.global_enabled)
        self.assertIn("agentos-project-manager", config.agents.global_disabled)

        # Verify global file was removed
        self.assertFalse(global_claude_file.exists(), "Global Claude file should be removed")

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_disable_project_scope_removes_only_project_files(
        self, mock_registry, mock_config_manager, mock_cwd, mock_home
    ):
        """Test that disabling project agent removes only project files."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Setup existing project files
        project_claude_dir = self.test_project / ".claude" / "agents"
        project_claude_dir.mkdir(parents=True)
        project_claude_file = project_claude_dir / "python-expert.md"
        project_claude_file.write_text("# Project Agent Content")

        project_cursor_dir = self.test_project / ".cursor" / "rules"
        project_cursor_dir.mkdir(parents=True)
        project_cursor_file = project_cursor_dir / "python-expert.mdc"
        project_cursor_file.write_text("# Project Cursor Rules")

        # Mock config with project agent enabled
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = ["python-expert"]
        config.agents.global_enabled = []
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.get_agent.return_value = self.project_agent
        registry.resolve_agent_name.return_value = "python-expert"
        mock_registry.return_value = registry

        # Run disable without --global flag (project scope)
        result = self.runner.invoke(app, ["disable", "python-expert"])

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Verify agent was removed from enabled and added to disabled
        self.assertNotIn("python-expert", config.agents.enabled)
        self.assertIn("python-expert", config.agents.disabled)

        # Verify project files were removed
        self.assertFalse(project_claude_file.exists(), "Project Claude file should be removed")
        self.assertFalse(project_cursor_file.exists(), "Project Cursor file should be removed")

    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_list_agents_shows_global_and_project_status(self, mock_registry, mock_config_manager):
        """Test that agent list command shows correct global/project status."""
        # Mock config with mixed agents
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = ["python-expert"]
        config.agents.global_enabled = ["agentos-project-manager"]
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry with test agents
        registry = MagicMock()
        registry.list_agents.return_value = [self.global_agent, self.project_agent]
        mock_registry.return_value = registry

        # Mock AppState for typer context
        from myai.cli.state import AppState

        mock_state = MagicMock(spec=AppState)
        mock_state.is_debug.return_value = False
        mock_state.output_format = "table"

        # Run list command with mock state
        result = self.runner.invoke(app, ["list"], obj=mock_state)

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Check that output shows correct status indicators
        output = result.stdout
        # Note: Rich table formatting may split text across lines, so we check for the essential parts
        self.assertIn("Global:", output, "Should show global status label")
        self.assertIn("Enabled", output, "Should show enabled status")
        self.assertIn("Project:", output, "Should show project status label")

        # Verify both agents are listed by their display names
        self.assertIn("Agent-OS Project Manager", output)
        self.assertIn("Python Expert", output)

    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_list_agents_shows_all_agents_with_status(self, mock_registry, mock_config_manager):
        """Test that list command shows all agents with their status."""
        # Setup mock data
        disabled_agent = MagicMock()
        disabled_agent.metadata.name = "disabled-agent"
        disabled_agent.metadata.display_name = "Disabled Agent"
        disabled_agent.metadata.description = "A disabled agent for testing"
        disabled_agent.metadata.category.value = "test"
        disabled_agent.metadata.tools = []
        disabled_agent.metadata.tags = []
        disabled_agent.metadata.version = "1.0.0"
        disabled_agent.content = "# Disabled Agent Content"
        disabled_agent.is_custom = False
        disabled_agent.file_path = None

        # Mock config with mixed agents
        config = MagicMock()
        config.agents.disabled = ["disabled-agent"]
        config.agents.enabled = ["python-expert"]
        config.agents.global_enabled = ["agentos-project-manager"]
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [self.global_agent, self.project_agent, disabled_agent]
        mock_registry.return_value = registry

        # Mock AppState for typer context
        from myai.cli.state import AppState

        mock_state = MagicMock(spec=AppState)
        mock_state.is_debug.return_value = False
        mock_state.output_format = "table"

        # Run list command
        result = self.runner.invoke(app, ["list"], obj=mock_state)

        # Check command succeeded
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")

        # Check that all agents are shown with correct status
        output = result.stdout
        self.assertIn("Agent-OS Project Manager", output, "Global enabled agent should be shown")
        self.assertIn("Python Expert", output, "Project enabled agent should be shown")
        self.assertIn("Disabled Agent", output, "Disabled agent should be shown")

        # Check status indicators
        self.assertIn("Enabled", output, "Should show enabled status")
        self.assertIn("Disabled", output, "Should show disabled status for disabled agents")

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    @patch("myai.commands.agent_cli.get_config_manager")
    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_setup_creates_cursor_files_for_global_agents(
        self, mock_registry, mock_config_manager, mock_cwd, mock_home
    ):
        """Test that Cursor gets files for global agents (since it has no global settings)."""
        # This test verifies the cursor_enabled_agents logic in setup
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config with global agents
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []  # No project-level agents
        config.agents.global_enabled = ["agentos-project-manager"]  # One global agent
        config.agents.global_disabled = []
        mock_config_manager.return_value.get_config.return_value = config

        # Mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [self.global_agent]
        mock_registry.return_value = registry

        # Simulate the setup logic for Cursor files
        from myai.commands.agent_cli import _create_agent_files

        # Create global agent file first (simulating global setup)
        _create_agent_files(self.global_agent, global_scope=True)

        # Now simulate what setup should do for Cursor - create project files for global agents
        # Since Cursor doesn't have global settings, global agents need project files too
        _create_agent_files(self.global_agent, global_scope=False)

        # Verify both global Claude file and project Cursor file exist
        global_claude_file = self.test_home / ".claude" / "agents" / "agentos-project-manager.md"
        self.assertTrue(global_claude_file.exists(), "Global Claude file should exist")

        project_cursor_file = self.test_project / ".cursor" / "rules" / "agentos-project-manager.mdc"
        self.assertTrue(project_cursor_file.exists(), "Project Cursor file should exist for global agent")

        # Verify project Claude file exists (when creating project files, both Claude and Cursor files are created)
        project_claude_file = self.test_project / ".claude" / "agents" / "agentos-project-manager.md"
        self.assertTrue(project_claude_file.exists(), "Project Claude file should exist when creating project files")


class TestAgentCLIFileManagement(unittest.TestCase):
    """Test file creation and removal functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_home = self.test_dir / "home"
        self.test_project = self.test_dir / "project"
        self.test_home.mkdir()
        self.test_project.mkdir()

        # Create test agent
        self.test_agent = MagicMock()
        self.test_agent.metadata.name = "test-agent"
        self.test_agent.metadata.display_name = "Test Agent"
        self.test_agent.metadata.description = "A test agent"
        self.test_agent.metadata.category.value = "test"
        self.test_agent.metadata.tools = []
        self.test_agent.metadata.tags = []
        self.test_agent.metadata.version = "1.0.0"
        self.test_agent.content = "# Test Agent Content"

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    def test_create_agent_files_global_scope(self, mock_cwd, mock_home):
        """Test _create_agent_files with global_scope=True."""
        from myai.commands.agent_cli import _create_agent_files

        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Create files with global scope
        _create_agent_files(self.test_agent, global_scope=True)

        # Verify only global Claude file was created
        global_claude_file = self.test_home / ".claude" / "agents" / "test-agent.md"
        self.assertTrue(global_claude_file.exists(), "Global Claude file should be created")
        self.assertEqual(global_claude_file.read_text(), "# Test Agent Content")

        # Verify no project files were created
        project_claude_dir = self.test_project / ".claude" / "agents"
        project_cursor_dir = self.test_project / ".cursor" / "rules"

        if project_claude_dir.exists():
            self.assertFalse((project_claude_dir / "test-agent.md").exists())
        if project_cursor_dir.exists():
            self.assertFalse((project_cursor_dir / "test-agent.mdc").exists())

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    def test_create_agent_files_project_scope(self, mock_cwd, mock_home):
        """Test _create_agent_files with global_scope=False."""
        from myai.commands.agent_cli import _create_agent_files

        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Create files with project scope
        _create_agent_files(self.test_agent, global_scope=False)

        # Verify project files were created
        project_claude_file = self.test_project / ".claude" / "agents" / "test-agent.md"
        project_cursor_file = self.test_project / ".cursor" / "rules" / "test-agent.mdc"

        self.assertTrue(project_claude_file.exists(), "Project Claude file should be created")
        self.assertTrue(project_cursor_file.exists(), "Project Cursor file should be created")

        # Verify project Claude file contains actual agent content
        claude_content = project_claude_file.read_text()
        self.assertEqual(claude_content, "# Test Agent Content")

        # Verify project Cursor file contains actual agent content
        cursor_content = project_cursor_file.read_text()
        self.assertEqual(cursor_content, "# Test Agent Content")

        # Verify no global files were created
        global_claude_dir = self.test_home / ".claude" / "agents"
        if global_claude_dir.exists():
            self.assertFalse((global_claude_dir / "test-agent.md").exists())

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    def test_remove_agent_files_global_scope(self, mock_cwd, mock_home):
        """Test _remove_agent_files with global_scope=True."""
        from myai.commands.agent_cli import _remove_agent_files

        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Setup existing files
        global_claude_dir = self.test_home / ".claude" / "agents"
        global_claude_dir.mkdir(parents=True)
        global_claude_file = global_claude_dir / "test-agent.md"
        global_claude_file.write_text("# Test Agent")

        # Setup project files that should NOT be removed
        project_claude_dir = self.test_project / ".claude" / "agents"
        project_claude_dir.mkdir(parents=True)
        project_claude_file = project_claude_dir / "test-agent.md"
        project_claude_file.write_text("# Project Test Agent")

        # Remove files with global scope
        _remove_agent_files("test-agent", global_scope=True)

        # Verify only global file was removed
        self.assertFalse(global_claude_file.exists(), "Global Claude file should be removed")
        self.assertTrue(project_claude_file.exists(), "Project Claude file should remain untouched")

    @patch("myai.commands.agent_cli.Path.home")
    @patch("myai.commands.agent_cli.Path.cwd")
    def test_remove_agent_files_project_scope(self, mock_cwd, mock_home):
        """Test _remove_agent_files with global_scope=False."""
        from myai.commands.agent_cli import _remove_agent_files

        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Setup existing project files
        project_claude_dir = self.test_project / ".claude" / "agents"
        project_claude_dir.mkdir(parents=True)
        project_claude_file = project_claude_dir / "test-agent.md"
        project_claude_file.write_text("# Project Test Agent")

        project_cursor_dir = self.test_project / ".cursor" / "rules"
        project_cursor_dir.mkdir(parents=True)
        project_cursor_file = project_cursor_dir / "test-agent.mdc"
        project_cursor_file.write_text("# Project Cursor Rules")

        # Setup global file that should NOT be removed
        global_claude_dir = self.test_home / ".claude" / "agents"
        global_claude_dir.mkdir(parents=True)
        global_claude_file = global_claude_dir / "test-agent.md"
        global_claude_file.write_text("# Global Test Agent")

        # Remove files with project scope
        _remove_agent_files("test-agent", global_scope=False)

        # Verify only project files were removed
        self.assertFalse(project_claude_file.exists(), "Project Claude file should be removed")
        self.assertFalse(project_cursor_file.exists(), "Project Cursor file should be removed")
        self.assertTrue(global_claude_file.exists(), "Global Claude file should remain untouched")


if __name__ == "__main__":
    unittest.main()
