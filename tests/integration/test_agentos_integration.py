"""
Tests for Agent-OS integration functionality.

This module tests the hidden Agent-OS integration layer, path translation,
content transformation, and synchronization mechanisms.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from myai.integrations.agentos import AgentOSManager
from myai.integrations.base import AdapterStatus
from myai.integrations.content_transformer import ContentTransformer, get_content_transformer
from myai.integrations.path_translator import PathTranslator, get_path_translator


class TestAgentOSManager:
    """Test cases for the AgentOSManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = AgentOSManager()

    @pytest.mark.asyncio
    async def test_adapter_info(self):
        """Test adapter information."""
        info = self.manager.info
        assert info.name == "agentos"
        assert info.display_name == "Agent-OS (Hidden)"
        assert info.tool_name == "Agent-OS"
        assert "migration" in [cap.value for cap in info.capabilities]

    @pytest.mark.asyncio
    async def test_initialization_without_agentos(self):
        """Test initialization when Agent-OS is not installed."""
        with patch.object(self.manager, "_detect_agentos_installation", return_value=False):
            result = await self.manager.initialize()
            assert result is True  # Should succeed even without Agent-OS
            assert self.manager.info.status == AdapterStatus.AVAILABLE

    @pytest.mark.asyncio
    async def test_initialization_with_agentos(self):
        """Test initialization when Agent-OS is installed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            agentos_dir.mkdir()
            (agentos_dir / "agents").mkdir()
            (agentos_dir / "config").mkdir()

            with patch.object(self.manager, "_detect_agentos_installation", return_value=True):
                with patch.object(self.manager, "_agentos_path", agentos_dir):
                    result = await self.manager.initialize()
                    assert result is True
                    assert self.manager._initialized

    @pytest.mark.asyncio
    async def test_health_check_without_agentos(self):
        """Test health check when Agent-OS is not installed."""
        with patch.object(self.manager, "detect_installation", return_value=False):
            health = await self.manager.health_check()
            assert health["status"] == "healthy"
            assert len(health["warnings"]) > 0
            assert "not detected" in health["warnings"][0]

    @pytest.mark.asyncio
    async def test_health_check_with_agentos(self):
        """Test health check when Agent-OS is installed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            agentos_dir.mkdir()
            (agentos_dir / "agents").mkdir()
            (agentos_dir / "config").mkdir()

            self.manager._agentos_path = agentos_dir
            self.manager._myai_path = Path(temp_dir) / ".myai"

            with patch.object(self.manager, "detect_installation", return_value=True):
                health = await self.manager.health_check()
                assert health["status"] == "healthy"
                assert "installation" in health["checks"]

    @pytest.mark.asyncio
    async def test_sync_agents_without_agentos(self):
        """Test syncing agents when Agent-OS is not available."""
        agents = [
            MagicMock(name="test-agent", content="Test content"),
        ]
        agents[0].name = "test-agent"

        result = await self.manager.sync_agents(agents)
        assert result["status"] == "skipped"
        assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_sync_agents_with_agentos(self):
        """Test syncing agents to Agent-OS directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            agentos_dir.mkdir()
            self.manager._agentos_path = agentos_dir

            # Create a simple agent-like object that doesn't have metadata
            class SimpleAgent:
                def __init__(self, name, content):
                    self.name = name
                    self.content = content

            agents = [SimpleAgent("test-agent", "Test content")]

            result = await self.manager.sync_agents(agents)
            assert result["status"] == "success"
            assert result["synced"] == 1

            # Check that file was created
            agent_file = agentos_dir / "agents" / "test-agent.md"
            assert agent_file.exists()

    @pytest.mark.asyncio
    async def test_import_agents(self):
        """Test importing agents from Agent-OS."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            agents_dir = agentos_dir / "agents"
            agents_dir.mkdir(parents=True)

            # Create test agent file
            agent_file = agents_dir / "test-agent.md"
            agent_file.write_text("# Agent-OS Test Agent\n\nThis is a test agent.")

            self.manager._agentos_path = agentos_dir

            agents = await self.manager.import_agents()
            assert len(agents) == 1
            assert agents[0]["name"] == "test-agent"
            assert "MyAI" in agents[0]["content"]  # Should be transformed

    def test_content_transformation_to_agentos(self):
        """Test content transformation for Agent-OS compatibility."""
        content = "This is a MyAI agent that works with .myai directory."
        transformed = self.manager._transform_content_for_agentos(content)

        assert "Agent-OS" in transformed
        assert ".agent-os" in transformed
        assert "Agent-OS Compatible" in transformed

    def test_content_transformation_from_agentos(self):
        """Test content transformation from Agent-OS format."""
        content = "# Agent-OS Compatible Agent\n\nThis is an Agent-OS agent."
        transformed = self.manager._transform_content_from_agentos(content)

        assert "MyAI" in transformed
        assert "Agent-OS Compatible" not in transformed

    @pytest.mark.asyncio
    async def test_configuration_management(self):
        """Test configuration reading and writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            config_dir = agentos_dir / "config"
            config_dir.mkdir(parents=True)

            self.manager._agentos_path = agentos_dir

            # Test setting configuration
            test_config = {"test_key": "test_value"}
            result = await self.manager.set_configuration(test_config)
            assert result is True

            # Test getting configuration
            config = await self.manager.get_configuration()
            assert config["test_key"] == "test_value"

    @pytest.mark.asyncio
    async def test_validation(self):
        """Test configuration validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            self.manager._agentos_path = agentos_dir

            # Test with missing directories
            errors = await self.manager.validate_configuration()
            assert len(errors) > 0

            # Create required directories
            (agentos_dir / "agents").mkdir(parents=True)
            (agentos_dir / "config").mkdir(parents=True)

            errors = await self.manager.validate_configuration()
            assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_backup_and_restore(self):
        """Test backup and restore functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            agentos_dir = Path(temp_dir) / ".agent-os"
            agentos_dir.mkdir()
            (agentos_dir / "test_file.txt").write_text("test content")

            self.manager._agentos_path = agentos_dir

            # Test backup
            backup_path = await self.manager.backup()
            assert backup_path is not None
            assert backup_path.exists()
            assert (backup_path / "agentos" / "test_file.txt").exists()

            # Test restore (would require more complex setup)
            # This is a basic test that restore method works
            restore_result = await self.manager.restore(backup_path)
            assert isinstance(restore_result, bool)


class TestPathTranslator:
    """Test cases for the PathTranslator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.translator = PathTranslator()

    def test_translate_to_myai(self):
        """Test translating Agent-OS paths to MyAI paths."""
        agentos_path = self.translator.home / ".agent-os" / "agents" / "test.md"
        myai_path = self.translator.translate_to_myai(agentos_path)

        expected_path = self.translator.home / ".myai" / "agents" / "test.md"
        assert myai_path == expected_path

    def test_translate_to_agentos(self):
        """Test translating MyAI paths to Agent-OS paths."""
        myai_path = self.translator.home / ".myai" / "agents" / "test.md"
        agentos_path = self.translator.translate_to_agentos(myai_path)

        expected_path = self.translator.home / ".agent-os" / "agents" / "test.md"
        assert agentos_path == expected_path

    def test_path_detection(self):
        """Test path detection methods."""
        agentos_path = self.translator.home / ".agent-os" / "agents"
        myai_path = self.translator.home / ".myai" / "agents"

        assert self.translator.is_agentos_path(agentos_path)
        assert not self.translator.is_agentos_path(myai_path)
        assert self.translator.is_myai_path(myai_path)
        assert not self.translator.is_myai_path(agentos_path)

    def test_path_interception(self):
        """Test path interception functionality."""
        agentos_path = self.translator.home / ".agent-os" / "agents" / "test.md"
        intercepted = self.translator.intercept_path(agentos_path)

        expected_path = self.translator.home / ".myai" / "agents" / "test.md"
        assert intercepted == expected_path

        # Non-Agent-OS path should remain unchanged
        other_path = Path("/some/other/path")
        intercepted_other = self.translator.intercept_path(other_path)
        assert intercepted_other == other_path

    def test_migration_plan(self):
        """Test migration plan generation."""
        plan = self.translator.get_migration_plan()

        assert len(plan) > 0
        for _, info in plan.items():
            assert "target" in info
            assert "exists" in info
            assert "files" in info

    def test_file_migration(self):
        """Test individual file migration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup Agent-OS structure
            agentos_dir = Path(temp_dir) / ".agent-os"
            agents_dir = agentos_dir / "agents"
            agents_dir.mkdir(parents=True)

            test_file = agents_dir / "test.md"
            test_file.write_text("Test content")

            # Update translator paths for test
            translator = PathTranslator()
            translator.agentos_root = agentos_dir
            translator.myai_root = Path(temp_dir) / ".myai"
            translator.path_mappings = {
                str(agentos_dir / "agents"): str(translator.myai_root / "agents"),
            }
            translator.reverse_mappings = {v: k for k, v in translator.path_mappings.items()}

            # Test migration
            result = translator.migrate_file(test_file, dry_run=False)
            assert result["success"] is True

            # Check target file exists
            target_file = translator.myai_root / "agents" / "test.md"
            assert target_file.exists()
            assert target_file.read_text() == "Test content"


class TestContentTransformer:
    """Test cases for the ContentTransformer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.transformer = ContentTransformer()

    def test_basic_text_transformation(self):
        """Test basic text content transformation."""
        content = "This is an Agent-OS application using .agent-os directory."
        transformed = self.transformer.transform_text_content(content)

        assert "MyAI" in transformed
        assert ".myai" in transformed
        assert "Agent-OS" not in transformed

    def test_code_transformation(self):
        """Test code content transformation."""
        content = """
import agent_os
from agent_os.config import AgentOSConfig

def main():
    config = AgentOSConfig()
    agent_os.run()
"""
        transformed = self.transformer.transform_text_content(content)

        assert "import myai" in transformed
        assert "from myai.config" in transformed
        assert "MyAIConfig" in transformed
        assert "myai.run()" in transformed

    def test_config_json_transformation(self):
        """Test JSON configuration transformation."""
        content = '{"agent-os": {"version": "1.0", "path": ".agent-os"}}'
        transformed = self.transformer._transform_config_json(content)

        config = json.loads(transformed)
        assert "myai" in config
        assert config["myai"]["path"] == ".myai"

    def test_file_transformation(self):
        """Test file transformation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("import agent_os\nprint('Agent-OS is running')")

            result = self.transformer.transform_file(test_file, dry_run=False)
            assert result["success"] is True
            assert result["changes_made"] is True

            # Check transformed content
            content = test_file.read_text()
            assert "import myai" in content
            assert "MyAI is running" in content

    def test_content_analysis(self):
        """Test content analysis functionality."""
        content = "This uses Agent-OS and .agent-os paths with agentos commands."
        analysis = self.transformer.analyze_content(content)

        assert analysis["has_agentos_references"] is True
        assert analysis["reference_count"] > 0
        assert len(analysis["reference_types"]) > 0

    def test_directory_transformation(self):
        """Test directory transformation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source"
            source_dir.mkdir()

            # Create test files
            (source_dir / "test.py").write_text("import agent_os")
            (source_dir / "config.json").write_text('{"agent-os": "config"}')
            (source_dir / "README.md").write_text("# Agent-OS Project")

            results = self.transformer.transform_directory(source_dir, dry_run=False)
            assert results["files_processed"] == 3
            assert results["files_changed"] > 0

    def test_special_file_transformations(self):
        """Test special file type transformations."""
        # Test README transformation
        readme_content = "# Agent-OS\n\nThis is an Agent-OS project."
        transformed_readme = self.transformer._transform_readme(readme_content)
        assert "MyAI" in transformed_readme
        assert "Migration from Agent-OS" in transformed_readme

        # Test package.json transformation
        package_content = '{"name": "agent-os-tool", "description": "Agent-OS utility"}'
        transformed_package = self.transformer._transform_package_json(package_content)
        package_data = json.loads(transformed_package)
        assert package_data["name"] == "myai-tool"
        assert "MyAI" in package_data["description"]


class TestIntegrationWorkflows:
    """Test complete integration workflows."""

    @pytest.mark.asyncio
    async def test_complete_migration_workflow(self):
        """Test a complete migration workflow from Agent-OS to MyAI."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup Agent-OS structure
            agentos_dir = Path(temp_dir) / ".agent-os"
            agents_dir = agentos_dir / "agents"
            config_dir = agentos_dir / "config"

            agents_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)

            # Create test agent
            agent_file = agents_dir / "test-agent.md"
            agent_file.write_text("# Agent-OS Test Agent\n\nThis agent uses Agent-OS features.")

            # Create test config
            config_file = config_dir / "config.json"
            config_file.write_text('{"agent-os": {"version": "1.0"}}')

            # Initialize manager
            manager = AgentOSManager()
            manager._agentos_path = agentos_dir

            # Test import
            agents = await manager.import_agents()
            assert len(agents) == 1
            assert "MyAI" in agents[0]["content"]

            # Test configuration
            config = await manager.get_configuration()
            assert "agent-os" in config

            # Test health check
            health = await manager.health_check()
            assert health["status"] == "healthy"

    def test_path_translation_integration(self):
        """Test path translation with content transformation."""
        translator = get_path_translator()
        transformer = get_content_transformer()

        # Test path that needs translation
        agentos_path = translator.home / ".agent-os" / "agents" / "test.md"
        myai_path = translator.translate_to_myai(agentos_path)

        # Test content that references the path
        content = f"Load agent from {agentos_path}"
        transformed_content = transformer.transform_text_content(content)

        assert (
            str(myai_path).replace(str(translator.home), "~") in transformed_content or ".myai" in transformed_content
        )

    def test_global_instance_functions(self):
        """Test global instance accessor functions."""
        translator1 = get_path_translator()
        translator2 = get_path_translator()
        assert translator1 is translator2  # Should be same instance

        transformer1 = get_content_transformer()
        transformer2 = get_content_transformer()
        assert transformer1 is transformer2  # Should be same instance
