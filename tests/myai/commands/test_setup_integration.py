"""
Integration tests for setup all-setup and uninstall commands.

These tests verify the actual behavior of the commands in a controlled
test environment without excessive mocking.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from myai.commands.setup_cli import app


class TestSetupIntegration(unittest.TestCase):
    """Integration tests for setup commands with minimal mocking."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()

        # Create a temporary directory for our test
        self.original_home = Path.home()
        self.original_cwd = Path.cwd()

        self.test_dir = Path(tempfile.mkdtemp())
        self.test_home = self.test_dir / "home"
        self.test_home.mkdir()
        self.test_project = self.test_dir / "project"
        self.test_project.mkdir()

        # Create a minimal myai package structure for testing
        self.test_package = self.test_dir / "myai_package"
        self.test_package.mkdir()
        self.test_agents_dir = self.test_package / "data" / "agents" / "default"
        self.test_agents_dir.mkdir(parents=True)

        # Create test agent files
        for category in ["engineering", "business", "security"]:
            cat_dir = self.test_agents_dir / category
            cat_dir.mkdir()
            for i in range(2):
                agent_file = cat_dir / f"{category}-agent-{i}.md"
                agent_file.write_text(f"# {category.title()} Agent {i}\n\nTest agent content.")

    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    @patch("myai.commands.setup_cli.get_config_manager")
    def test_all_setup_creates_directory_structure(self, mock_config_manager, mock_cwd, mock_home):
        """Test that all-setup creates the complete directory structure."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config manager
        config_mgr = MagicMock()
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config_mgr.get_config.return_value = config
        mock_config_manager.return_value = config_mgr

        # Create a mock registry with simple test agents
        with patch("myai.agent.registry.get_agent_registry") as mock_registry:
            registry = MagicMock()
            test_agents = []
            for name in ["lead-developer", "data-analyst", "security-expert"]:
                agent = MagicMock()
                agent.metadata.name = name
                agent.name = name
                agent.content = f"# {name.replace('-', ' ').title()}\n\nAgent content here."
                test_agents.append(agent)
            registry.list_agents.return_value = test_agents
            mock_registry.return_value = registry

            # Mock the integration manager
            with patch("myai.integrations.manager.IntegrationManager") as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = mock_manager

                # Mock the async sync operation
                async def mock_sync(*args, **kwargs):  # noqa: ARG001
                    return {"claude": {"status": "success", "synced": 3}}

                mock_manager.initialize = AsyncMock()
                mock_manager.sync_agents = AsyncMock(return_value={"claude": {"status": "success", "synced": 3}})

                # We need to mock the __file__ attribute properly
                with patch("myai.__file__", str(self.test_package / "__init__.py")):
                    # Run the command
                    result = self.runner.invoke(app, ["all-setup"])

                    # Check command succeeded
                    self.assertEqual(result.exit_code, 0, f"Command failed with output:\n{result.stdout}")

                    # Verify directory structure was created
                    myai_dir = self.test_home / ".myai"
                    self.assertTrue(myai_dir.exists(), "~/.myai directory not created")
                    self.assertTrue((myai_dir / "agents").exists(), "~/.myai/agents not created")
                    self.assertTrue((myai_dir / "config").exists(), "~/.myai/config not created")

                    # Verify MyAI directories were created
                    self.assertTrue((myai_dir / "templates").exists(), "Templates directory not created")
                    self.assertTrue((myai_dir / "tools").exists(), "Tools directory not created")
                    self.assertTrue((myai_dir / "hooks").exists(), "Hooks directory not created")

                    # Verify example hook was created
                    example_hook = myai_dir / "hooks" / "on_agent_create.sh"
                    self.assertTrue(example_hook.exists(), "Example hook not created")

                    # Verify workflow system directories were created (from invisible Agent-OS integration)
                    self.assertTrue((myai_dir / "workflows").exists(), "Workflows directory not created")
                    self.assertTrue((myai_dir / "standards").exists(), "Standards directory not created")
                    self.assertTrue((myai_dir / "commands").exists(), "Commands directory not created")

                    # Verify Claude directory structure
                    claude_dir = self.test_home / ".claude"
                    self.assertTrue(claude_dir.exists(), "~/.claude not created")
                    self.assertTrue((claude_dir / "agents").exists(), "~/.claude/agents not created")

                    # Verify project structure
                    project_claude = self.test_project / ".claude"
                    self.assertTrue(project_claude.exists(), ".claude not created in project")
                    self.assertTrue((project_claude / "agents").exists(), ".claude/agents not created in project")

                    project_cursor = self.test_project / ".cursor"
                    self.assertTrue(project_cursor.exists(), ".cursor not created in project")
                    self.assertTrue((project_cursor / "rules").exists(), ".cursor/rules not created in project")

                    # Verify no MDC files created when no agents are enabled
                    mdc_files = list((project_cursor / "rules").glob("*.mdc"))
                    # Should have no MDC files when no agents are in enabled list
                    self.assertEqual(len(mdc_files), 0, "Unexpected .mdc files created when no agents enabled")

                    # Verify no Claude agent files created when no agents are enabled
                    claude_agent_files = list((project_claude / "agents").glob("*.md"))
                    self.assertEqual(len(claude_agent_files), 0, "Unexpected .md files created when no agents enabled")

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    @patch("myai.commands.setup_cli.get_config_manager")
    def test_setup_creates_cursor_files_for_global_agents(self, mock_config_manager, mock_cwd, mock_home):
        """Test that setup creates Cursor files for globally enabled agents."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config manager with global agents enabled
        config_mgr = MagicMock()
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []  # No project agents
        # Mock the global_enabled attribute that may not exist on initial setup
        config.agents.global_enabled = ["agentos-project-manager", "agentos-spec-creator"]
        config_mgr.get_config.return_value = config
        mock_config_manager.return_value = config_mgr

        # Create test agents with global-enabled names
        with patch("myai.agent.registry.get_agent_registry") as mock_registry:
            registry = MagicMock()
            test_agents = []
            for name in ["agentos-project-manager", "agentos-spec-creator"]:
                agent = MagicMock()
                agent.metadata.name = name
                agent.metadata.display_name = name.replace("-", " ").title()
                agent.metadata.category.value = "engineering"
                agent.content = f"# {name.replace('-', ' ').title()}\n\nAgent content here."
                test_agents.append(agent)
            registry.list_agents.return_value = test_agents
            mock_registry.return_value = registry

            # Mock the integration manager
            with patch("myai.integrations.manager.IntegrationManager") as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = mock_manager
                mock_manager.initialize = AsyncMock()
                mock_manager.sync_agents = AsyncMock(return_value={"claude": {"status": "success", "synced": 2}})

                # Mock the package file path
                with patch("myai.__file__", str(self.test_package / "__init__.py")):
                    # Run the setup command
                    result = self.runner.invoke(app, ["all-setup"])

                    # Check command succeeded
                    self.assertEqual(result.exit_code, 0, f"Command failed with output:\n{result.stdout}")

                    # Verify global Claude files were created
                    claude_dir = self.test_home / ".claude" / "agents"
                    self.assertTrue(claude_dir.exists(), "~/.claude/agents directory not created")

                    global_claude_files = list(claude_dir.glob("*.md"))
                    self.assertEqual(
                        len(global_claude_files), 2, f"Expected 2 global Claude files, got {len(global_claude_files)}"
                    )

                    # Verify Cursor files were created for global agents (since Cursor has no global settings)
                    project_cursor = self.test_project / ".cursor" / "rules"
                    self.assertTrue(project_cursor.exists(), ".cursor/rules directory not created")

                    cursor_files = list(project_cursor.glob("*.mdc"))
                    self.assertEqual(
                        len(cursor_files), 2, f"Expected 2 Cursor files for global agents, got {len(cursor_files)}"
                    )

                    # Verify specific files exist
                    for name in ["agentos-project-manager", "agentos-spec-creator"]:
                        cursor_file = project_cursor / f"{name}.mdc"
                        self.assertTrue(cursor_file.exists(), f"Cursor file for global agent {name} not created")

                        # Verify file content structure
                        content = cursor_file.read_text()
                        self.assertIn(f'agent: "{name}"', content)
                        self.assertIn("@myai/agents/engineering/", content)

                    # Verify NO project Claude files were created (global agents don't need project wrappers)
                    project_claude = self.test_project / ".claude" / "agents"
                    if project_claude.exists():
                        project_claude_files = list(project_claude.glob("*.md"))
                        self.assertEqual(
                            len(project_claude_files), 0, "No project Claude files should exist for global agents"
                        )

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    def test_uninstall_removes_only_myai_files(self, mock_cwd, mock_home):
        """Test that uninstall preserves user files while removing MyAI files."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Create MyAI directory structure
        myai_dir = self.test_home / ".myai"
        myai_dir.mkdir()
        (myai_dir / "agents").mkdir()
        (myai_dir / "config").mkdir()

        # Create Claude directory with mixed files
        claude_agents = self.test_home / ".claude" / "agents"
        claude_agents.mkdir(parents=True)

        # Create MyAI agent files
        myai_agents = ["lead-developer", "data-analyst", "security-expert"]
        for agent in myai_agents:
            (claude_agents / f"{agent}.md").write_text(f"# {agent}")

        # Create user's custom files
        user_agent = claude_agents / "my-custom-agent.md"
        user_agent.write_text("# My Custom Agent")
        user_notes = claude_agents / "notes.txt"
        user_notes.write_text("User notes")

        # Create project files
        project_claude = self.test_project / ".claude" / "agents"
        project_claude.mkdir(parents=True)
        for agent in myai_agents:
            (project_claude / f"{agent}.md").write_text(f"# {agent}")
        user_project = project_claude / "project-agent.md"
        user_project.write_text("# Project Agent")

        # Create Cursor rules
        cursor_rules = self.test_project / ".cursor" / "rules"
        cursor_rules.mkdir(parents=True)
        for agent in myai_agents:
            (cursor_rules / f"{agent}.mdc").write_text("MDC content")
        user_rule = cursor_rules / "custom.mdc"
        user_rule.write_text("User rule")

        # Mock registry to return our test agents
        with patch("myai.agent.registry.get_agent_registry") as mock_registry:
            registry = MagicMock()
            test_agents = []
            for name in myai_agents:
                agent = MagicMock()
                agent.metadata.name = name
                agent.name = name
                test_agents.append(agent)
            registry.list_agents.return_value = test_agents
            mock_registry.return_value = registry

            # Run uninstall
            result = self.runner.invoke(app, ["uninstall", "--all", "--force"])
            self.assertEqual(result.exit_code, 0, f"Uninstall failed:\n{result.stdout}")

            # Verify MyAI directory was removed
            self.assertFalse(myai_dir.exists(), "~/.myai was not removed")

            # Verify user files remain
            self.assertTrue(user_agent.exists(), "User's Claude agent was removed")
            self.assertEqual(user_agent.read_text(), "# My Custom Agent")
            self.assertTrue(user_notes.exists(), "User's notes file was removed")
            self.assertTrue(user_project.exists(), "User's project agent was removed")
            self.assertTrue(user_rule.exists(), "User's Cursor rule was removed")

            # Verify MyAI files were removed
            for agent in myai_agents:
                self.assertFalse(
                    (claude_agents / f"{agent}.md").exists(), f"MyAI agent {agent} was not removed from Claude"
                )
                self.assertFalse(
                    (project_claude / f"{agent}.md").exists(), f"MyAI agent {agent} was not removed from project"
                )
                self.assertFalse(
                    (cursor_rules / f"{agent}.mdc").exists(), f"MyAI rule {agent} was not removed from Cursor"
                )

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    def test_uninstall_cleans_empty_directories(self, mock_cwd, mock_home):
        """Test that uninstall removes empty directories after file removal."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Create directories with only MyAI files
        claude_agents = self.test_home / ".claude" / "agents"
        claude_agents.mkdir(parents=True)
        (claude_agents / "lead-developer.md").write_text("# Lead")

        cursor_rules = self.test_project / ".cursor" / "rules"
        cursor_rules.mkdir(parents=True)
        (cursor_rules / "lead-developer.mdc").write_text("MDC")

        # Mock registry
        with patch("myai.agent.registry.get_agent_registry") as mock_registry:
            registry = MagicMock()
            agent = MagicMock()
            agent.metadata.name = "lead-developer"
            agent.name = "lead-developer"
            registry.list_agents.return_value = [agent]
            mock_registry.return_value = registry

            # Run uninstall
            result = self.runner.invoke(app, ["uninstall", "--claude", "--project", "--force"])
            self.assertEqual(result.exit_code, 0)

            # Verify empty directories were removed
            self.assertFalse(claude_agents.exists(), "Empty Claude agents directory not removed")
            self.assertFalse((self.test_home / ".claude").exists(), "Empty .claude directory not removed")
            self.assertFalse(cursor_rules.exists(), "Empty Cursor rules directory not removed")
            self.assertFalse((self.test_project / ".cursor").exists(), "Empty .cursor directory not removed")

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    @patch("myai.commands.setup_cli.get_config_manager")
    def test_setup_uninstall_cycle(self, mock_config_manager, mock_cwd, mock_home):
        """Test complete cycle: setup followed by uninstall."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config manager
        config_mgr = MagicMock()
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config_mgr.get_config.return_value = config
        mock_config_manager.return_value = config_mgr

        # First, run setup
        with patch("myai.__file__", str(self.test_package / "__init__.py")):
            with patch("myai.agent.registry.get_agent_registry") as mock_registry:
                registry = MagicMock()
                test_agent = MagicMock()
                test_agent.metadata.name = "test-agent"
                test_agent.name = "test-agent"
                test_agent.content = "# Test Agent"
                registry.list_agents.return_value = [test_agent]
                mock_registry.return_value = registry

                with patch("myai.integrations.manager.IntegrationManager") as mock_manager_class:
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager
                    mock_manager.initialize = AsyncMock()
                    mock_manager.sync_agents = AsyncMock(return_value={"claude": {"status": "success", "synced": 1}})

                    # Run setup
                    result = self.runner.invoke(app, ["all-setup"])
                    self.assertEqual(result.exit_code, 0, f"Setup failed:\n{result.stdout}")

                    # Verify setup worked
                    self.assertTrue((self.test_home / ".myai").exists())
                    self.assertTrue((self.test_project / ".claude").exists())
                    self.assertTrue((self.test_project / ".cursor" / "rules").exists())

                    # Add user files
                    user_file = self.test_home / ".claude" / "agents" / "user-agent.md"
                    user_file.write_text("# User Agent")

                    # Run uninstall
                    result = self.runner.invoke(app, ["uninstall", "--all", "--force"])
                    self.assertEqual(result.exit_code, 0, f"Uninstall failed:\n{result.stdout}")

                    # Verify MyAI removed but user files remain
                    self.assertFalse((self.test_home / ".myai").exists())
                    self.assertTrue(user_file.exists())

    @patch("myai.commands.setup_cli.Path.home")
    @patch("myai.commands.setup_cli.Path.cwd")
    @patch("myai.commands.setup_cli._detect_agentos")
    @patch("myai.commands.setup_cli.get_config_manager")
    def test_all_setup_with_existing_agentos(self, mock_config_manager, mock_detect, mock_cwd, mock_home):
        """Test all-setup with existing Agent-OS installation."""
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config manager
        config_mgr = MagicMock()
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config_mgr.get_config.return_value = config
        mock_config_manager.return_value = config_mgr

        # Create fake Agent-OS directory
        fake_agentos = self.test_dir / "fake-agentos"
        fake_agentos.mkdir()
        (fake_agentos / "agents").mkdir()
        (fake_agentos / "agents" / "test-agent.md").write_text("# Test Agent")
        (fake_agentos / "config.json").write_text('{"version": "0.9.0"}')

        mock_detect.return_value = fake_agentos

        # Mock the confirm dialog to say yes
        with patch("typer.confirm", return_value=True):
            with patch("myai.__file__", str(self.test_package / "__init__.py")):
                with patch("myai.agent.registry.get_agent_registry") as mock_registry:
                    registry = MagicMock()
                    # Create some test agents
                    test_agents = []
                    for name in ["test-agent"]:
                        agent = MagicMock()
                        agent.metadata.name = name
                        agent.name = name
                        agent.content = f"# {name.replace('-', ' ').title()}\n\nAgent content here."
                        test_agents.append(agent)
                    registry.list_agents.return_value = test_agents
                    mock_registry.return_value = registry

                    with patch("myai.integrations.manager.IntegrationManager") as mock_manager_class:
                        mock_manager = MagicMock()
                        mock_manager_class.return_value = mock_manager
                        mock_manager.initialize = AsyncMock()
                        mock_manager.sync_agents = AsyncMock(
                            return_value={"claude": {"status": "success", "synced": 1}}
                        )

                        # Run setup
                        result = self.runner.invoke(app, ["all-setup"])
                        if result.exit_code != 0:
                            print(f"STDOUT:\n{result.stdout}")
                            print(f"STDERR:\n{result.stderr}")
                            print(f"Exception: {result.exception}")
                        self.assertEqual(
                            result.exit_code, 0, f"Setup failed:\\n{result.stdout}\\n\\nSTDERR:\\n{result.stderr}"
                        )

                        # Verify migration happened
                        myai_dir = self.test_home / ".myai"
                        self.assertTrue((myai_dir / "agents" / "test-agent.md").exists(), "Agent not migrated")

                        # Verify backup was created
                        backup_dir = myai_dir / "backups" / "agentos-migration"
                        self.assertTrue(backup_dir.exists(), "Backup directory not created")

                        # Verify Agent-OS config was updated
                        with open(fake_agentos / "config.json") as f:
                            config = json.load(f)
                            self.assertIn("myai_integration", config)
                            self.assertTrue(config["myai_integration"]["enabled"])


if __name__ == "__main__":
    unittest.main()
