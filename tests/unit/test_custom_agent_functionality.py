"""
Unit tests for custom agent functionality.

Tests the core functionality of custom agents without integration complexities.
"""

import asyncio
from pathlib import Path

import pytest

from myai.agent.registry import AgentRegistry
from myai.integrations.manager import IntegrationManager
from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification


@pytest.fixture
def isolated_registry():
    """Provide an isolated registry for tests that need to modify global state."""
    original_instance = getattr(AgentRegistry, "_instance", None)
    AgentRegistry._instance = None
    try:
        yield
    finally:
        if original_instance is not None:
            AgentRegistry._instance = original_instance
        else:
            AgentRegistry._instance = None


def test_custom_agent_registration(isolated_registry):
    """Test registering custom agents in the registry."""
    # Use isolated registry fixture to ensure clean test state
    assert isolated_registry is None  # Fixture yields None but provides isolation
    registry = AgentRegistry(auto_discover=False)

    # Create a custom agent
    custom_agent = AgentSpecification(
        metadata=AgentMetadata(
            name="custom-test-agent",
            display_name="Custom Test Agent",
            description="A custom agent for testing",
            category=AgentCategory.CUSTOM,
            version="1.0.0",
        ),
        content="# Custom Test Agent\n\nThis is a custom agent.",
        is_custom=True,
        source="claude",
        external_path=Path("/custom/path/agent.md"),
    )

    # Register the agent
    registry.register_agent(custom_agent, persist=False)

    # Verify it's registered
    retrieved = registry.get_agent("custom-test-agent")
    assert retrieved is not None
    assert retrieved.is_custom is True
    assert retrieved.source == "claude"
    assert retrieved.external_path == Path("/custom/path/agent.md")

    # Verify it's tracked as custom
    assert registry.is_custom("custom-test-agent") is True

    # Verify it appears in custom agents list
    custom_agents = registry.get_custom_agents()
    assert len(custom_agents) == 1
    assert custom_agents[0].metadata.name == "custom-test-agent"

    # Verify it appears in source-specific list
    claude_agents = registry.get_agents_by_source("claude")
    assert len(claude_agents) == 1
    assert claude_agents[0].metadata.name == "custom-test-agent"


def test_custom_agent_preservation_on_refresh(isolated_registry):
    """Test that custom agents are preserved during registry refresh."""
    # Use isolated registry fixture to ensure clean test state
    assert isolated_registry is None  # Fixture yields None but provides isolation
    registry = AgentRegistry(auto_discover=False)

    # Register a regular agent
    regular_agent = AgentSpecification(
        metadata=AgentMetadata(
            name="regular-agent",
            display_name="Regular Agent",
            description="A regular MyAI agent",
            category=AgentCategory.ENGINEERING,
            version="1.0.0",
        ),
        content="# Regular Agent",
    )
    registry.register_agent(regular_agent, persist=False)

    # Register a custom agent
    custom_agent = AgentSpecification(
        metadata=AgentMetadata(
            name="custom-agent",
            display_name="Custom Agent",
            description="A custom imported agent",
            category=AgentCategory.CUSTOM,
            version="1.0.0",
        ),
        content="# Custom Agent",
        is_custom=True,
        source="user",
    )
    registry.register_agent(custom_agent, persist=False)

    # Refresh the registry
    registry.refresh()

    # Regular agent should be gone
    assert registry.get_agent("regular-agent") is None

    # Custom agent should be preserved
    custom_retrieved = registry.get_agent("custom-agent")
    assert custom_retrieved is not None
    assert custom_retrieved.is_custom is True
    assert custom_retrieved.source == "user"


def test_integration_manager_import_agents(isolated_registry):
    """Test the import_agents functionality directly."""
    # Fixture provides isolated registry context
    assert isolated_registry is None  # Fixture yields None but provides isolation

    # Create mock raw agent data with frontmatter to ensure consistent parsing
    raw_agents = [
        {
            "name": "imported-agent",
            "content": """---
name: imported-agent
display_name: Imported Agent
description: This agent was imported from an external source
category: custom
---

# Imported Agent

This agent was imported from an external source.

## Skills
- Custom functionality
- External integration
""",
            "source": "claude",
            "file_path": "/path/to/agent.md",
        }
    ]

    # Mock adapter
    class MockAdapter:
        async def import_agents(self):
            return raw_agents

    # Test the import logic
    async def test_import():
        manager = IntegrationManager()
        await manager.initialize()  # Initialize the manager
        manager._adapters = {"claude": MockAdapter()}

        results = await manager.import_agents(["claude"])

        # Should have imported the agent
        assert "claude" in results
        assert len(results["claude"]) == 1

        # Check that agent was registered
        from myai.agent.registry import get_agent_registry

        registry = get_agent_registry()

        # Debug: List all agents
        all_agents = registry.list_agents()
        print(f"All agents after import: {[a.metadata.name for a in all_agents]}")

        # Look for our imported agent
        custom_agents = registry.get_custom_agents()
        print(f"Custom agents: {[a.metadata.name for a in custom_agents]}")

        # The imported agent should be in the registry
        imported = registry.get_agent("imported-agent")
        assert imported is not None, "Imported agent not found in registry"

        print(f"Imported agent name: {imported.metadata.name}")
        assert imported.is_custom is True
        assert imported.source == "claude"
        assert str(imported.external_path) == "/path/to/agent.md"

    # Run the async test
    asyncio.run(test_import())


def test_custom_agent_not_persisted(isolated_registry):
    """Test that custom agents with external paths are not persisted."""
    # Use isolated registry fixture to ensure clean test state
    assert isolated_registry is None  # Fixture yields None but provides isolation
    registry = AgentRegistry(auto_discover=False)

    # Mock the agent storage save method
    saved_agents = []
    original_save = registry._agent_storage.save_agent

    def mock_save(agent):
        saved_agents.append(agent)
        return original_save(agent)

    registry._agent_storage.save_agent = mock_save

    # Register a regular agent with persist=True
    regular_agent = AgentSpecification(
        metadata=AgentMetadata(
            name="regular-persist",
            display_name="Regular Persist Agent",
            description="Should be persisted",
            category=AgentCategory.ENGINEERING,
            version="1.0.0",
        ),
        content="# Regular Agent",
    )
    registry.register_agent(regular_agent, persist=True)

    # Register a custom agent with external path with persist=True
    custom_agent = AgentSpecification(
        metadata=AgentMetadata(
            name="custom-no-persist",
            display_name="Custom No Persist Agent",
            description="Should not be persisted",
            category=AgentCategory.CUSTOM,
            version="1.0.0",
        ),
        content="# Custom Agent",
        is_custom=True,
        source="claude",
        external_path=Path("/external/agent.md"),
    )
    registry.register_agent(custom_agent, persist=True)

    # Regular agent should be saved
    assert len(saved_agents) == 1
    assert saved_agents[0].metadata.name == "regular-persist"

    # Custom agent should not be saved
    assert not any(a.metadata.name == "custom-no-persist" for a in saved_agents)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
