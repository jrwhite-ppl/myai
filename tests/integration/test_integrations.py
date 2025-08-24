"""
Integration tests for tool adapters.

This module provides comprehensive tests for the integration framework
and individual tool adapters like Claude and Cursor.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from myai.integrations.base import (
    AbstractAdapter,
    AdapterCapability,
    AdapterInfo,
    AdapterStatus,
    get_adapter_registry,
)
from myai.integrations.claude import ClaudeAdapter
from myai.integrations.cursor import CursorAdapter
from myai.integrations.factory import get_adapter_factory
from myai.integrations.manager import IntegrationManager


class MockAdapter(AbstractAdapter):
    """Mock adapter for testing."""

    def __init__(self, name: str = "mock", config: Dict[str, Any] | None = None):
        super().__init__(name, config)
        self._status = AdapterStatus.CONFIGURED  # Changed to configured for tests
        self._installed = True
        self._health_status = "healthy"
        self._config = {}
        self._agents = []

    @property
    def info(self) -> AdapterInfo:
        return AdapterInfo(
            name=self.name,
            display_name="Mock Adapter",
            description="Mock adapter for testing",
            version="1.0.0",
            tool_name="Mock Tool",
            capabilities={AdapterCapability.READ_CONFIG, AdapterCapability.SYNC_AGENTS},
            status=self._status,
        )

    async def initialize(self) -> bool:
        self._status = AdapterStatus.CONFIGURED if self._installed else AdapterStatus.ERROR
        return self._installed

    async def detect_installation(self) -> bool:
        return self._installed

    async def get_status(self) -> AdapterStatus:
        return self._status

    async def health_check(self) -> Dict[str, Any]:
        return {"status": self._health_status, "timestamp": "2023-01-01T00:00:00"}

    async def get_configuration(self) -> Dict[str, Any]:
        return self._config.copy()

    async def set_configuration(self, config: Dict[str, Any]) -> bool:
        self._config.update(config)
        return True

    async def sync_agents(self, agents: List[Any], *, dry_run: bool = False) -> Dict[str, Any]:
        if not dry_run:
            self._agents = agents.copy()
        return {
            "status": "success",
            "synced": len(agents),
            "errors": [],
            "dry_run": dry_run,
        }

    async def import_agents(self) -> List[Any]:
        return self._agents.copy()

    async def validate_configuration(self) -> List[str]:
        return []

    async def cleanup(self) -> bool:
        return True


@pytest.fixture
def mock_adapter():
    """Fixture providing a mock adapter."""
    return MockAdapter()


@pytest.fixture
def temp_config_dir():
    """Fixture providing a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestAdapterRegistry:
    """Tests for the adapter registry."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = get_adapter_registry()
        registry.clear()

    def test_register_adapter_class(self):
        """Test registering an adapter class."""
        registry = get_adapter_registry()
        registry.register_adapter_class("test_mock", MockAdapter)

        assert "test_mock" in registry.list_adapters()

    def test_create_adapter(self):
        """Test creating an adapter instance."""
        registry = get_adapter_registry()
        registry.register_adapter_class("test_mock", MockAdapter)

        adapter = registry.create_adapter("test_mock")
        assert isinstance(adapter, MockAdapter)
        assert adapter.name == "test_mock"

    def test_get_adapter(self):
        """Test getting an adapter instance."""
        registry = get_adapter_registry()
        registry.register_adapter_class("test_mock", MockAdapter)

        created_adapter = registry.create_adapter("test_mock")
        retrieved_adapter = registry.get_adapter("test_mock")

        assert retrieved_adapter is created_adapter

    def test_list_active_adapters(self):
        """Test listing active adapters."""
        registry = get_adapter_registry()
        registry.register_adapter_class("test_mock", MockAdapter)

        assert "test_mock" not in registry.list_active_adapters()

        registry.create_adapter("test_mock")
        assert "test_mock" in registry.list_active_adapters()

    def test_remove_adapter(self):
        """Test removing an adapter instance."""
        registry = get_adapter_registry()
        registry.register_adapter_class("test_mock", MockAdapter)

        registry.create_adapter("test_mock")
        assert "test_mock" in registry.list_active_adapters()

        success = registry.remove_adapter("test_mock")
        assert success
        assert "test_mock" not in registry.list_active_adapters()


class TestAdapterFactory:
    """Tests for the adapter factory."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = get_adapter_registry()
        registry.clear()

    def test_create_adapter(self):
        """Test creating adapters through the factory."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        adapter = factory.create_adapter("test_mock")
        assert isinstance(adapter, MockAdapter)

    def test_create_adapter_with_config(self):
        """Test creating adapter with configuration."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        config = {"test_key": "test_value"}
        adapter = factory.create_adapter("test_mock", config)
        assert adapter.config == config

    @pytest.mark.asyncio
    async def test_discover_adapters(self):
        """Test adapter discovery."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        discovered = await factory.discover_adapters()
        assert "test_mock" in discovered
        assert discovered["test_mock"]["status"] == "configured"

    @pytest.mark.asyncio
    async def test_initialize_adapter(self):
        """Test adapter initialization through factory."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        adapter = await factory.initialize_adapter("test_mock")
        assert isinstance(adapter, MockAdapter)
        assert adapter._status == AdapterStatus.CONFIGURED

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        """Test health check on all adapters."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await factory.initialize_adapter("test_mock")
        results = await factory.health_check_all()

        assert "test_mock" in results
        assert results["test_mock"]["status"] == "healthy"


class TestIntegrationManager:
    """Tests for the integration manager."""

    @pytest.fixture
    def manager(self):
        """Fixture providing an integration manager."""
        return IntegrationManager()

    @pytest.mark.asyncio
    async def test_initialize_adapters(self, manager):
        """Test initializing adapters."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        results = await manager.initialize(["test_mock"])

        assert results["test_mock"] is True
        assert "test_mock" in manager.list_adapters()

    @pytest.mark.asyncio
    async def test_get_adapter_status(self, manager):
        """Test getting adapter status."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await manager.initialize(["test_mock"])
        status = await manager.get_adapter_status("test_mock")

        assert "test_mock" in status
        assert status["test_mock"]["status"] == "configured"

    @pytest.mark.asyncio
    async def test_sync_agents(self, manager):
        """Test syncing agents through manager."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await manager.initialize(["test_mock"])

        agents = [{"name": "test_agent", "content": "test content"}]
        results = await manager.sync_agents(agents, ["test_mock"])

        assert "test_mock" in results
        assert results["test_mock"]["synced"] == 1

    @pytest.mark.asyncio
    async def test_import_agents(self, manager):
        """Test importing agents through manager."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await manager.initialize(["test_mock"])

        # First sync some agents
        agents = [{"name": "test_agent", "content": "test content"}]
        await manager.sync_agents(agents, ["test_mock"])

        # Then import them back
        imported = await manager.import_agents(["test_mock"])

        assert "test_mock" in imported
        assert len(imported["test_mock"]) == 1
        assert imported["test_mock"][0]["name"] == "test_agent"

    @pytest.mark.asyncio
    async def test_validate_configurations(self, manager):
        """Test validating configurations."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await manager.initialize(["test_mock"])
        results = await manager.validate_configurations(["test_mock"])

        assert "test_mock" in results
        assert results["test_mock"] == []  # No errors for mock adapter

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup."""
        factory = get_adapter_factory()
        factory.register_adapter_class("test_mock", MockAdapter)

        await manager.initialize(["test_mock"])
        assert len(manager.list_adapters()) == 1

        results = await manager.cleanup()
        assert results["test_mock"] is True
        assert len(manager.list_adapters()) == 0


class TestClaudeAdapter:
    """Tests for the Claude adapter."""

    def test_adapter_info(self):
        """Test adapter information."""
        adapter = ClaudeAdapter()
        info = adapter.info

        assert info.name == "claude"
        assert info.display_name == "Claude Code"
        assert info.tool_name == "Claude Code"
        assert AdapterCapability.SYNC_AGENTS in info.capabilities

    @pytest.mark.asyncio
    async def test_detect_installation_mock(self):
        """Test installation detection with mocking."""
        adapter = ClaudeAdapter()

        with patch.object(adapter, "_detect_installation_paths") as mock_paths:
            mock_paths.return_value = [Path("/mock/path")]

            with patch("pathlib.Path.exists") as mock_exists:
                mock_exists.return_value = True

                result = await adapter.detect_installation()
                assert result is True

    @pytest.mark.asyncio
    async def test_sync_agents(self, temp_config_dir):
        """Test syncing agents to Claude."""
        adapter = ClaudeAdapter()

        # Mock config path
        adapter._config_paths = [temp_config_dir]

        # Create agents directory
        agents_dir = temp_config_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        # Create a proper mock agent
        mock_agent = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.name = "test-agent"
        mock_agent.metadata = mock_metadata
        mock_agent.content = "Test content"

        # Mock the to_markdown method to return proper content
        mock_agent.to_markdown.return_value = "Test content"

        agents = [mock_agent]

        result = await adapter.sync_agents(agents)

        # Print result for debugging
        if result["status"] != "success":
            print(f"Sync failed with result: {result}")

        assert result["status"] == "success"
        assert result["synced"] == 1

        # Check if agent file was created
        agent_file = temp_config_dir / "agents" / "test-agent.md"
        assert agent_file.exists()
        assert agent_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_import_agents(self, temp_config_dir):
        """Test importing agents from Claude."""
        adapter = ClaudeAdapter()

        # Mock config path
        adapter._config_paths = [temp_config_dir]

        # Create test agent file
        agents_dir = temp_config_dir / "agents"
        agents_dir.mkdir()

        agent_file = agents_dir / "test-agent.md"
        agent_file.write_text("Test agent content")

        agents = await adapter.import_agents()

        assert len(agents) == 1
        assert agents[0]["name"] == "test-agent"
        assert agents[0]["content"] == "Test agent content"
        assert agents[0]["source"] == "claude"

    @pytest.mark.asyncio
    async def test_configuration_management(self, temp_config_dir):
        """Test configuration get/set operations."""
        adapter = ClaudeAdapter()

        # Mock config path
        adapter._config_paths = [temp_config_dir]

        # Test setting configuration
        test_config = {"theme": "dark", "auto_save": True}
        success = await adapter.set_configuration(test_config)
        assert success is True

        # Test getting configuration
        config = await adapter.get_configuration()
        assert config["theme"] == "dark"
        assert config["auto_save"] is True


class TestCursorAdapter:
    """Tests for the Cursor adapter."""

    def test_adapter_info(self):
        """Test adapter information."""
        adapter = CursorAdapter()
        info = adapter.info

        assert info.name == "cursor"
        assert info.display_name == "Cursor AI"
        assert info.tool_name == "Cursor"
        assert AdapterCapability.SYNC_AGENTS in info.capabilities

    @pytest.mark.asyncio
    async def test_sync_agents(self, temp_config_dir):
        """Test syncing agents to Cursor as rules."""
        adapter = CursorAdapter()

        # Mock rules directory and current working directory check
        adapter._rules_directory = temp_config_dir

        # Patch Path.cwd() to return a non-home directory
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = temp_config_dir  # Not home directory

            # Create proper mock agent
            mock_agent = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.name = "test-agent"
            mock_metadata.display_name = "Test Agent"
            mock_metadata.description = "Test agent for code review"
            mock_metadata.tags = []
            mock_metadata.tools = ["Read", "Write"]
            mock_metadata.color = None
            # Mock category to have a value attribute
            mock_category = MagicMock()
            mock_category.value = "engineering"
            mock_metadata.category = mock_category
            mock_agent.metadata = mock_metadata
            mock_agent.content = "Test instructions for code review"

            agents = [mock_agent]

            result = await adapter.sync_agents(agents)

        assert result["status"] == "success"
        assert result["synced"] == 1

        # Check if rule file was created (now using .mdc format in rules subdirectory)
        rule_file = temp_config_dir / "rules" / "test-agent.mdc"
        assert rule_file.exists()

        content = rule_file.read_text()
        # For project-level rules, content should be a minimal wrapper
        assert "test-agent" in content
        assert "MyAI Agent" in content
        assert "~/.myai/agents/" in content

        # Check that project-level message is included
        assert "message" in result
        assert "project .cursor/ directory" in result["message"]

    @pytest.mark.asyncio
    async def test_import_agents(self, temp_config_dir):
        """Test importing agents from Cursor rules."""
        adapter = CursorAdapter()

        # Mock rules directory
        adapter._rules_directory = temp_config_dir

        # Create test rule file in rules subdirectory (MDC format)
        rules_dir = temp_config_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_file = rules_dir / "test-agent.mdc"
        rule_content = """---
description: Test Agent for unit testing
globs: []
alwaysApply: false
---

# Test Agent
# Category: engineering
# Generated by MyAI

## Instructions

Follow coding best practices."""
        rule_file.write_text(rule_content)

        agents = await adapter.import_agents()

        assert len(agents) == 1
        assert agents[0]["name"] == "test-agent"
        assert agents[0]["content"] == rule_content
        assert agents[0]["source"] == "cursor"
        assert agents[0]["category"] == "engineering"

    def test_generate_cursor_rules(self):
        """Test generating Cursor rules format."""
        adapter = CursorAdapter()

        result = adapter._generate_project_cursor_rules("test-agent", "Follow best practices for Python", "engineering")

        # For project-level rules, we just return the content as-is
        assert result == "Follow best practices for Python"

    @pytest.mark.asyncio
    async def test_configuration_management(self, temp_config_dir):
        """Test configuration get/set operations."""
        adapter = CursorAdapter()

        # Mock paths
        adapter._config_paths = [temp_config_dir]
        rules_dir = temp_config_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)  # Create rules directory
        adapter._rules_directory = rules_dir

        # Test setting configuration
        test_config = {
            "settings": {"workbench.colorTheme": "dark"},
            "rules": {"python-style": "Follow PEP 8 standards"},
        }

        success = await adapter.set_configuration(test_config)
        assert success is True

        # Check settings file
        settings_file = temp_config_dir / "settings.json"
        assert settings_file.exists()

        # Check rule file
        rule_file = temp_config_dir / "rules" / "python-style.cursorrules"
        assert rule_file.exists()

        # Test getting configuration
        config = await adapter.get_configuration()
        assert "settings" in config
        assert "rules" in config
        assert config["settings"]["workbench.colorTheme"] == "dark"
        assert config["rules"]["python-style"] == "Follow PEP 8 standards"


class TestAdapterIntegration:
    """Integration tests for adapters working together."""

    @pytest.mark.asyncio
    async def test_migration_between_adapters(self, temp_config_dir):
        """Test migrating agents between adapters."""
        # Setup Claude adapter with some agents
        claude_adapter = ClaudeAdapter()
        claude_adapter._config_paths = [temp_config_dir / "claude"]

        agents_dir = temp_config_dir / "claude" / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "test-agent.md").write_text("Claude agent content")

        # Setup Cursor adapter
        cursor_adapter = CursorAdapter()
        cursor_adapter._rules_directory = temp_config_dir / "cursor"

        # Import from Claude
        claude_agents = await claude_adapter.import_agents()
        assert len(claude_agents) == 1

        # Sync to Cursor with mocked cwd
        with patch("pathlib.Path.cwd") as mock_cwd:
            mock_cwd.return_value = temp_config_dir  # Not home directory
            result = await cursor_adapter.sync_agents(claude_agents)
            assert result["synced"] == 1

        # Verify rule file was created (now using .mdc format in rules subdirectory)
        rule_file = temp_config_dir / "cursor" / "rules" / "test-agent.mdc"
        assert rule_file.exists()

    @pytest.mark.asyncio
    async def test_adapter_health_monitoring(self):
        """Test health monitoring across multiple adapters."""
        manager = IntegrationManager()

        factory = get_adapter_factory()
        factory.register_adapter_class("mock1", MockAdapter)
        factory.register_adapter_class("mock2", MockAdapter)

        # Initialize adapters
        await manager.initialize(["mock1", "mock2"])

        # Perform health checks
        health_results = await manager.health_check()

        assert len(health_results) == 2
        assert health_results["mock1"]["status"] == "healthy"
        assert health_results["mock2"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_parallel_sync_operations(self):
        """Test parallel sync operations to multiple adapters."""
        manager = IntegrationManager()

        factory = get_adapter_factory()
        factory.register_adapter_class("mock1", MockAdapter)
        factory.register_adapter_class("mock2", MockAdapter)

        # Initialize adapters
        await manager.initialize(["mock1", "mock2"])

        # Sync agents to both adapters
        agents = [{"name": "test-agent", "content": "Test content"}]
        results = await manager.sync_agents(agents)

        assert len(results) == 2
        assert results["mock1"]["synced"] == 1
        assert results["mock2"]["synced"] == 1

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        manager = IntegrationManager()

        # Create a mock adapter that fails initialization
        class FailingAdapter(MockAdapter):
            async def initialize(self) -> bool:
                return False

        factory = get_adapter_factory()
        factory.register_adapter_class("failing", FailingAdapter)
        factory.register_adapter_class("working", MockAdapter)

        # Try to initialize both adapters
        results = await manager.initialize(["failing", "working"])

        assert results["failing"] is False
        assert results["working"] is True

        # Only the working adapter should be active
        assert len(manager.list_adapters()) == 1
        assert "working" in manager.list_adapters()


if __name__ == "__main__":
    pytest.main([__file__])
