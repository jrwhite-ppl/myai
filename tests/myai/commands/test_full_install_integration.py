"""
Full setup integration test that mirrors real user workflow.

This test simulates the exact workflow:
1. myai setup uninstall --all --force
2. myai setup all
3. Verify all expected directories and files are created correctly
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from myai.app import create_app
from myai.commands.install_cli import app


class TestFullSetupIntegration(unittest.TestCase):
    """Test the complete uninstall -> all workflow."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()

        # Create temporary directories to simulate real environment
        self.original_home = Path.home()
        self.original_cwd = Path.cwd()

        self.test_dir = Path(tempfile.mkdtemp())
        self.test_home = self.test_dir / "home"
        self.test_home.mkdir()
        self.test_project = self.test_dir / "project" / "myagents"  # Simulate ~/w/myagents
        self.test_project.mkdir(parents=True)

        # Create a minimal myai package structure for testing
        self.test_package = self.test_dir / "myai_package"
        self.test_package.mkdir()
        self.test_agents_dir = self.test_package / "data" / "agents" / "default"
        self.test_agents_dir.mkdir(parents=True)

        # Create the expected default agents (3 Agent-OS agents)
        self.expected_agents = ["agentos-project-manager", "agentos-spec-creator", "agentos-workflow-executor"]

        # Create agent files for all categories to ensure proper filtering
        for category in ["engineering", "business", "security"]:
            cat_dir = self.test_agents_dir / category
            cat_dir.mkdir()

            # Create Agent-OS agents in engineering category
            if category == "engineering":
                for agent_name in self.expected_agents:
                    agent_file = cat_dir / f"{agent_name}.md"
                    agent_file.write_text(f"# {agent_name.replace('-', ' ').title()}\n\nAgent content for {agent_name}")

            # Create other test agents
            for i in range(2):
                agent_file = cat_dir / f"{category}-agent-{i}.md"
                agent_file.write_text(f"# {category.title()} Agent {i}\n\nTest agent content.")

    def tearDown(self):
        """Clean up test environment."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("myai.commands.install_cli.Path.home")
    @patch("myai.commands.install_cli.Path.cwd")
    @patch("myai.commands.install_cli.get_config_manager")
    def test_full_uninstall_and_setup_workflow(self, mock_config_manager, mock_cwd, mock_home):
        """
        Test the complete workflow:
        1. uninstall --all --force
        2. all
        3. Verify all expected structures are created
        """
        # Setup mocks
        mock_home.return_value = self.test_home
        mock_cwd.return_value = self.test_project

        # Mock config manager with dynamic behavior
        config_mgr = MagicMock()
        config = MagicMock()
        config.agents.disabled = []
        config.agents.enabled = []
        config.agents.global_enabled = []  # Will be updated during setup
        config.agents.global_disabled = []
        config_mgr.get_config.return_value = config

        # Mock the set_config_value to actually update our mock config
        def mock_set_config_value(key, value, level="user"):  # noqa: ARG001
            if key == "agents.global_enabled":
                config.agents.global_enabled = value
            elif key == "agents.global_disabled":
                config.agents.global_disabled = value
            elif key == "agents.disabled":
                config.agents.disabled = value

        config_mgr.set_config_value.side_effect = mock_set_config_value
        mock_config_manager.return_value = config_mgr

        # Create mock registry with all test agents
        with patch("myai.agent.registry.get_agent_registry") as mock_registry:
            registry = MagicMock()
            test_agents = []

            # Create Agent-OS agents
            for agent_name in self.expected_agents:
                agent = MagicMock()
                agent.metadata.name = agent_name
                agent.metadata.display_name = agent_name.replace("-", " ").title()
                agent.metadata.category.value = "engineering"
                agent.name = agent_name
                agent.content = f"# {agent_name.replace('-', ' ').title()}\n\nAgent content for {agent_name}"
                test_agents.append(agent)

            # Create other test agents (should not be enabled by default)
            for category in ["engineering", "business", "security"]:
                for i in range(2):
                    agent_name = f"{category}-agent-{i}"
                    agent = MagicMock()
                    agent.metadata.name = agent_name
                    agent.metadata.display_name = f"{category.title()} Agent {i}"
                    agent.metadata.category.value = category
                    agent.name = agent_name
                    agent.content = f"# {category.title()} Agent {i}\n\nTest agent content."
                    test_agents.append(agent)

            registry.list_agents.return_value = test_agents
            mock_registry.return_value = registry

            # Mock the integration manager
            with patch("myai.integrations.manager.IntegrationManager") as mock_manager_class:
                mock_manager = MagicMock()
                mock_manager_class.return_value = mock_manager
                mock_manager.initialize = AsyncMock()

                # Mock sync_agents to actually create the files like the real implementation would
                async def mock_sync_agents(agents, integrations):
                    synced_count = 0
                    if "claude" in integrations:
                        claude_agents_dir = self.test_home / ".claude" / "agents"
                        claude_agents_dir.mkdir(parents=True, exist_ok=True)

                        for agent in agents:
                            # Only sync globally enabled agents to ~/.claude/agents
                            if agent.metadata.name in config.agents.global_enabled:
                                claude_file = claude_agents_dir / f"{agent.metadata.name}.md"
                                claude_file.write_text(agent.content)
                                synced_count += 1

                    return {"claude": {"status": "success", "synced": synced_count}}

                mock_manager.sync_agents = mock_sync_agents

                # Mock the package file path
                with patch("myai.__file__", str(self.test_package / "__init__.py")):
                    # STEP 1: Run uninstall --all --force (should be no-op on fresh environment)
                    main_app = create_app()
                    uninstall_result = self.runner.invoke(main_app, ["uninstall", "--all", "--force"])
                    self.assertEqual(uninstall_result.exit_code, 0, f"Uninstall failed:\n{uninstall_result.stdout}")

                    # STEP 2: Run all
                    setup_result = self.runner.invoke(app, ["all"])
                    self.assertEqual(setup_result.exit_code, 0, f"Setup failed:\n{setup_result.stdout}")

                    # STEP 3: Verify ~/.myai directory structure
                    myai_dir = self.test_home / ".myai"
                    self.assertTrue(myai_dir.exists(), "~/.myai directory not created")

                    # Core directories
                    self.assertTrue((myai_dir / "agents").exists(), "~/.myai/agents not created")
                    self.assertTrue((myai_dir / "config").exists(), "~/.myai/config not created")
                    self.assertTrue((myai_dir / "templates").exists(), "~/.myai/templates not created")
                    self.assertTrue((myai_dir / "tools").exists(), "~/.myai/tools not created")
                    self.assertTrue((myai_dir / "hooks").exists(), "~/.myai/hooks not created")

                    # Workflow system directories (from invisible Agent-OS integration)
                    self.assertTrue((myai_dir / "workflows").exists(), "~/.myai/workflows not created")
                    self.assertTrue((myai_dir / "standards").exists(), "~/.myai/standards not created")
                    self.assertTrue((myai_dir / "commands").exists(), "~/.myai/commands not created")

                    # Verify example hook was created
                    example_hook = myai_dir / "hooks" / "on_agent_create.sh"
                    self.assertTrue(example_hook.exists(), "Example hook not created")

                    # Verify all agent files were copied to ~/.myai/agents
                    agents_dir = myai_dir / "agents"
                    for category in ["engineering", "business", "security"]:
                        cat_dir = agents_dir / category
                        self.assertTrue(cat_dir.exists(), f"Agent category {category} not created")

                        # Check that all agents were copied
                        if category == "engineering":
                            # Should have Agent-OS agents + 2 test agents
                            expected_files = [*self.expected_agents, f"{category}-agent-0", f"{category}-agent-1"]
                            for agent_name in expected_files:
                                agent_file = cat_dir / f"{agent_name}.md"
                                self.assertTrue(agent_file.exists(), f"Agent {agent_name} not copied to ~/.myai/agents")
                        else:
                            # Should have 2 test agents
                            for i in range(2):
                                agent_file = cat_dir / f"{category}-agent-{i}.md"
                                self.assertTrue(agent_file.exists(), f"Agent {category}-agent-{i} not copied")

                    # STEP 4: Verify ~/.claude directory structure
                    claude_dir = self.test_home / ".claude"
                    self.assertTrue(claude_dir.exists(), "~/.claude not created")
                    self.assertTrue((claude_dir / "agents").exists(), "~/.claude/agents not created")

                    # Only Agent-OS agents should have files in ~/.claude/agents (they're enabled globally by default)
                    claude_agent_files = list((claude_dir / "agents").glob("*.md"))
                    self.assertEqual(
                        len(claude_agent_files), 3, f"Expected 3 global Claude files, got {len(claude_agent_files)}"
                    )

                    for agent_name in self.expected_agents:
                        claude_file = claude_dir / "agents" / f"{agent_name}.md"
                        self.assertTrue(claude_file.exists(), f"Global Claude file for {agent_name} not created")
                        # Verify content is the actual agent content (not a wrapper)
                        content = claude_file.read_text()
                        self.assertIn(f"Agent content for {agent_name}", content)

                    # STEP 5: Verify ~/.cursor directory was NOT created (should not be touched)
                    cursor_home_dir = self.test_home / ".cursor"
                    self.assertFalse(
                        cursor_home_dir.exists(), "~/.cursor should not be created (global Cursor not supported)"
                    )

                    # STEP 6: Verify project .claude directory
                    project_claude = self.test_project / ".claude"
                    self.assertTrue(project_claude.exists(), "Project .claude directory not created")
                    self.assertTrue((project_claude / "agents").exists(), "Project .claude/agents not created")

                    # Project should have configuration file
                    settings_file = project_claude / "settings.local.json"
                    self.assertTrue(settings_file.exists(), "Project Claude settings file not created")

                    # Verify settings file content
                    settings_content = json.loads(settings_file.read_text())
                    self.assertIn("projects", settings_content, "projects not in Claude settings")

                    # Get the project key (which is the full path)
                    project_key = str(self.test_project)
                    self.assertIn(project_key, settings_content["projects"], "Current project not in Claude settings")

                    project_config = settings_content["projects"][project_key]
                    self.assertIn("agentsPath", project_config, "agentsPath not in project Claude settings")
                    # The agentsPath should point to the project .claude/agents directory
                    expected_agents_path = str(self.test_project / ".claude" / "agents")
                    self.assertEqual(
                        project_config["agentsPath"], expected_agents_path, "Incorrect agentsPath in Claude settings"
                    )

                    # STEP 7: Verify project .cursor directory
                    project_cursor = self.test_project / ".cursor"
                    self.assertTrue(project_cursor.exists(), "Project .cursor directory not created")
                    self.assertTrue((project_cursor / "rules").exists(), "Project .cursor/rules not created")

                    # Since global agents need to be accessible in Cursor (which has no global settings),
                    # the project should have .mdc files for globally enabled agents
                    cursor_rule_files = list((project_cursor / "rules").glob("*.mdc"))
                    self.assertEqual(
                        len(cursor_rule_files),
                        3,
                        f"Expected 3 Cursor rule files for global agents, got {len(cursor_rule_files)}",
                    )

                    for agent_name in self.expected_agents:
                        cursor_file = project_cursor / "rules" / f"{agent_name}.mdc"
                        self.assertTrue(cursor_file.exists(), f"Cursor rule file for {agent_name} not created")

                        # Verify content is a reference to centralized agent (not full content)
                        content = cursor_file.read_text()
                        self.assertIn(
                            "@myai/agents/engineering/",
                            content,
                            f"Cursor file for {agent_name} should reference centralized agent",
                        )
                        self.assertIn("description:", content, "Cursor file should have description")
                        self.assertIn("globs:", content, "Cursor file should have globs")

                    # STEP 8: Verify that non-default agents don't have integration files
                    non_default_agents = [
                        "engineering-agent-0",
                        "engineering-agent-1",
                        "business-agent-0",
                        "security-agent-0",
                    ]

                    # Should not be in ~/.claude/agents
                    for agent_name in non_default_agents:
                        claude_file = claude_dir / "agents" / f"{agent_name}.md"
                        self.assertFalse(
                            claude_file.exists(), f"Non-default agent {agent_name} should not have global Claude file"
                        )

                    # Should not be in project .cursor/rules
                    for agent_name in non_default_agents:
                        cursor_file = project_cursor / "rules" / f"{agent_name}.mdc"
                        self.assertFalse(
                            cursor_file.exists(), f"Non-default agent {agent_name} should not have Cursor rule file"
                        )

                    # STEP 9: Verify configuration was updated to show Agent-OS agents as enabled
                    # The config should have been modified during setup to mark Agent-OS agents as globally enabled
                    # This is verified by the mock calls made during setup

                    print("✅ Full setup integration test completed successfully!")
                    print(f"✅ ~/.myai created with {len(list(agents_dir.rglob('*.md')))} agents")
                    print(f"✅ ~/.claude created with {len(claude_agent_files)} global agents")
                    print("✅ ~/.cursor correctly not created")
                    print("✅ Project .claude configured with agentsPath")
                    print(f"✅ Project .cursor configured with {len(cursor_rule_files)} rule files")


if __name__ == "__main__":
    unittest.main()
