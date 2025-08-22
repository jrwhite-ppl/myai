"""Tests for agent registry."""

import tempfile
import threading
import time
from pathlib import Path

import pytest

from myai.agent.registry import AgentRegistry, get_agent_registry
from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the AgentRegistry singleton before each test."""
    AgentRegistry._instance = None
    yield
    AgentRegistry._instance = None


@pytest.fixture
def sample_agent():
    """Create a sample agent for testing."""
    metadata = AgentMetadata(
        name="test-agent",
        display_name="Test Agent",
        version="1.0.0",
        description="A test agent",
        category=AgentCategory.ENGINEERING,
        tools=["claude", "cursor"],
        tags=["test", "sample"],
    )
    return AgentSpecification(
        metadata=metadata,
        content="This is a test agent for unit testing.",
    )


@pytest.fixture
def multiple_agents():
    """Create multiple agents for testing."""
    agents = []

    # Engineering agents
    for i in range(3):
        metadata = AgentMetadata(
            name=f"eng-agent-{i}",
            display_name=f"Engineering Agent {i}",
            version="1.0.0",
            description=f"Engineering agent {i}",
            category=AgentCategory.ENGINEERING,
            tools=["claude"] if i % 2 == 0 else ["cursor"],
            tags=["engineering", f"level-{i}"],
        )
        agents.append(AgentSpecification(metadata=metadata, content=f"Engineering agent {i} content"))

    # Business agents
    for i in range(2):
        metadata = AgentMetadata(
            name=f"biz-agent-{i}",
            display_name=f"Business Agent {i}",
            version="1.0.0",
            description=f"Business agent {i}",
            category=AgentCategory.BUSINESS,
            tools=["claude", "cursor"],
            tags=["business", "analytics"],
        )
        agents.append(AgentSpecification(metadata=metadata, content=f"Business agent {i} content"))

    return agents


class TestAgentRegistry:
    """Test AgentRegistry functionality."""

    def test_singleton_pattern(self):
        """Test that AgentRegistry follows singleton pattern."""
        registry1 = AgentRegistry()
        registry2 = AgentRegistry()
        assert registry1 is registry2

        # Test convenience function
        registry3 = get_agent_registry()
        assert registry1 is registry3

    def test_singleton_thread_safety(self):
        """Test thread-safe singleton initialization."""
        # Reset singleton for this test
        AgentRegistry._instance = None

        registries = []

        def create_registry():
            registries.append(AgentRegistry())

        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_registry)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All should be the same instance
        assert all(r is registries[0] for r in registries)

    def test_register_agent(self, temp_dir, sample_agent):
        """Test agent registration."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agent
        registry.register_agent(sample_agent)

        # Verify agent is registered
        assert sample_agent.metadata.name in registry._agents_by_name
        assert sample_agent.metadata.name in registry._enabled_agents

        # Verify indexing
        assert sample_agent.metadata.name in registry._agents_by_category[AgentCategory.ENGINEERING]
        assert sample_agent.metadata.name in registry._agents_by_tool["claude"]
        assert sample_agent.metadata.name in registry._agents_by_tool["cursor"]
        assert sample_agent.metadata.name in registry._agents_by_tag["test"]

    def test_register_duplicate_agent(self, temp_dir, sample_agent):
        """Test registering duplicate agent."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agent
        registry.register_agent(sample_agent)

        # Try to register again without overwrite
        with pytest.raises(ValueError, match="already exists"):
            registry.register_agent(sample_agent)

        # Register with overwrite
        registry.register_agent(sample_agent, overwrite=True)

    def test_get_agent(self, temp_dir, sample_agent):
        """Test getting agent by name."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agent
        registry.register_agent(sample_agent)

        # Get agent
        retrieved = registry.get_agent(sample_agent.metadata.name)
        assert retrieved is not None
        assert retrieved.metadata.name == sample_agent.metadata.name

        # Get non-existent agent
        assert registry.get_agent("non-existent") is None

    def test_agent_caching(self, temp_dir, sample_agent):
        """Test agent caching."""
        registry = AgentRegistry(base_path=temp_dir, cache_enabled=True, cache_ttl=1, auto_discover=False)

        # Register agent
        registry.register_agent(sample_agent)

        # First get should cache
        agent1 = registry.get_agent(sample_agent.metadata.name)
        assert len(registry._cache) == 1

        # Second get should use cache
        agent2 = registry.get_agent(sample_agent.metadata.name)
        assert agent1 is agent2

        # Wait for cache to expire
        time.sleep(1.1)

        # Get should refresh cache
        agent3 = registry.get_agent(sample_agent.metadata.name)
        assert agent3 is not None

    def test_list_agents(self, temp_dir, multiple_agents):
        """Test listing agents with filters."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register all agents
        for agent in multiple_agents:
            registry.register_agent(agent)

        # List all agents
        all_agents = registry.list_agents()
        assert len(all_agents) == len(multiple_agents)

        # Filter by category
        eng_agents = registry.list_agents(category=AgentCategory.ENGINEERING)
        assert len(eng_agents) == 3
        assert all(a.metadata.category == AgentCategory.ENGINEERING for a in eng_agents)

        # Filter by tool
        claude_agents = registry.list_agents(tool="claude")
        assert len(claude_agents) == 4  # 2 eng + 2 biz

        # Filter by tag
        analytics_agents = registry.list_agents(tag="analytics")
        assert len(analytics_agents) == 2

        # Multiple filters
        eng_claude = registry.list_agents(category=AgentCategory.ENGINEERING, tool="claude")
        assert len(eng_claude) == 2

    def test_search_agents(self, temp_dir, multiple_agents):
        """Test searching agents."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register all agents
        for agent in multiple_agents:
            registry.register_agent(agent)

        # Search by name
        results = registry.search_agents("eng-agent")
        assert len(results) == 3

        # Search by description
        results = registry.search_agents("business", search_fields=["description"])
        assert len(results) == 2

        # Search by content
        results = registry.search_agents("content", search_fields=["content"])
        assert len(results) == 5  # All agents have "content" in their content

        # Search by tags
        results = registry.search_agents("analytics", search_fields=["tags"])
        assert len(results) == 2

    def test_enable_disable_agent(self, temp_dir, sample_agent):
        """Test enabling and disabling agents."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agent (should be enabled by default)
        registry.register_agent(sample_agent)
        assert registry.is_enabled(sample_agent.metadata.name)

        # Disable agent
        assert registry.disable_agent(sample_agent.metadata.name)
        assert not registry.is_enabled(sample_agent.metadata.name)

        # Enable agent
        assert registry.enable_agent(sample_agent.metadata.name)
        assert registry.is_enabled(sample_agent.metadata.name)

        # Test with non-existent agent
        assert not registry.disable_agent("non-existent")
        assert not registry.enable_agent("non-existent")

    def test_discover_agents(self, temp_dir):
        """Test agent discovery from filesystem."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Create agent directory
        agents_dir = temp_dir / "agents"
        agents_dir.mkdir()

        # Create some agent files
        agent1_content = """---
name: discovered-agent-1
display_name: Discovered Agent 1
version: 1.0.0
description: First discovered agent
category: engineering
tools: [claude]
tags: [test]
---

This is the first discovered agent.
"""

        agent2_content = """---
name: discovered-agent-2
display_name: Discovered Agent 2
version: 1.0.0
description: Second discovered agent
category: business
tools: [cursor]
tags: [test]
---

This is the second discovered agent.
"""

        (agents_dir / "agent1.md").write_text(agent1_content)
        (agents_dir / "agent2.md").write_text(agent2_content)

        # Also create a non-agent markdown file
        (agents_dir / "readme.md").write_text("# Not an agent")

        # Discover agents
        discovered = registry.discover_agents([agents_dir])
        assert len(discovered) == 2
        assert "discovered-agent-1" in discovered
        assert "discovered-agent-2" in discovered

        # Verify agents are registered
        agent1 = registry.get_agent("discovered-agent-1")
        assert agent1 is not None
        assert agent1.metadata.category == AgentCategory.ENGINEERING

    def test_discovery_paths(self, temp_dir):
        """Test managing discovery paths."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Add discovery path
        new_path = temp_dir / "custom_agents"
        registry.add_discovery_path(new_path)
        assert new_path in registry._discovery_paths

        # Remove discovery path
        registry.remove_discovery_path(new_path)
        assert new_path not in registry._discovery_paths

    def test_clear_cache(self, temp_dir, sample_agent):
        """Test clearing cache."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register and get agent to populate cache
        registry.register_agent(sample_agent)
        registry.get_agent(sample_agent.metadata.name)
        assert len(registry._cache) == 1

        # Clear cache
        registry.clear_cache()
        assert len(registry._cache) == 0

    def test_refresh(self, temp_dir, sample_agent):
        """Test refreshing registry."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agent
        registry.register_agent(sample_agent)
        assert len(registry._agents_by_name) == 1

        # Refresh should clear everything
        registry.refresh()
        assert len(registry._agents_by_name) == 0
        assert len(registry._cache) == 0
        assert len(registry._enabled_agents) == 0

    def test_get_statistics(self, temp_dir, multiple_agents):
        """Test getting registry statistics."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agents
        for agent in multiple_agents:
            registry.register_agent(agent)

        stats = registry.get_statistics()
        assert stats["total_agents"] == 5
        assert stats["enabled_agents"] == 5
        assert len(stats["categories"]) == 2
        assert "claude" in stats["tools"]
        assert "cursor" in stats["tools"]
        assert "engineering" in stats["tags"]
        assert "business" in stats["tags"]

    def test_persistence(self, temp_dir, sample_agent):
        """Test agent persistence to storage."""
        # First registry instance
        registry1 = AgentRegistry(base_path=temp_dir, auto_discover=False)
        registry1.register_agent(sample_agent, persist=True)

        # Clear the singleton
        AgentRegistry._instance = None

        # New registry instance
        registry2 = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Agent should be loadable from storage
        agent = registry2.get_agent(sample_agent.metadata.name)
        assert agent is not None
        assert agent.metadata.name == sample_agent.metadata.name

    def test_list_agents_enabled_only(self, temp_dir, multiple_agents):
        """Test listing only enabled agents."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Register agents
        for agent in multiple_agents:
            registry.register_agent(agent)

        # Disable some agents
        registry.disable_agent("eng-agent-0")
        registry.disable_agent("biz-agent-0")

        # List all agents
        all_agents = registry.list_agents()
        assert len(all_agents) == 5

        # List enabled only
        enabled_agents = registry.list_agents(enabled_only=True)
        assert len(enabled_agents) == 3
        assert not any(a.metadata.name in ["eng-agent-0", "biz-agent-0"] for a in enabled_agents)

    def test_concurrent_access(self, temp_dir, multiple_agents):
        """Test concurrent access to registry."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)
        errors = []

        def register_agents():
            try:
                for agent in multiple_agents:
                    registry.register_agent(agent, overwrite=True)
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append(e)

        def list_agents():
            try:
                for _ in range(10):
                    registry.list_agents()
                    registry.search_agents("agent")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Run concurrent operations
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=register_agents))
            threads.append(threading.Thread(target=list_agents))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0

    def test_resolve_agent_name_by_internal_name(self, temp_dir):
        """Test resolving agent by internal name."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Create agent with hyphenated name
        metadata = AgentMetadata(
            name="python-expert",
            display_name="Python Expert",
            version="1.0.0",
            description="A Python expert",
            category=AgentCategory.ENGINEERING,
        )
        agent = AgentSpecification(metadata=metadata, content="Python expert content")
        registry.register_agent(agent)

        # Should resolve by internal name
        resolved = registry.resolve_agent_name("python-expert")
        assert resolved == "python-expert"

    def test_resolve_agent_name_by_display_name(self, temp_dir):
        """Test resolving agent by display name."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Create agent with hyphenated name
        metadata = AgentMetadata(
            name="python-expert",
            display_name="Python Expert",
            version="1.0.0",
            description="A Python expert",
            category=AgentCategory.ENGINEERING,
        )
        agent = AgentSpecification(metadata=metadata, content="Python expert content")
        registry.register_agent(agent)

        # Should resolve by display name
        resolved = registry.resolve_agent_name("Python Expert")
        assert resolved == "python-expert"

        # Should be case-insensitive
        resolved = registry.resolve_agent_name("python expert")
        assert resolved == "python-expert"

    def test_resolve_agent_name_not_found(self, temp_dir):
        """Test resolving non-existent agent name."""
        registry = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Should return None for non-existent agent
        resolved = registry.resolve_agent_name("non-existent")
        assert resolved is None

    def test_resolve_agent_name_from_storage(self, temp_dir):
        """Test resolving agent name when agent is only in storage."""
        # First registry instance
        registry1 = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Create and persist agent
        metadata = AgentMetadata(
            name="java-expert",
            display_name="Java Expert",
            version="1.0.0",
            description="A Java expert",
            category=AgentCategory.ENGINEERING,
        )
        agent = AgentSpecification(metadata=metadata, content="Java expert content")
        registry1.register_agent(agent, persist=True)

        # Clear the singleton
        AgentRegistry._instance = None

        # New registry instance (agent not in index yet)
        registry2 = AgentRegistry(base_path=temp_dir, auto_discover=False)

        # Should still resolve by display name from storage
        resolved = registry2.resolve_agent_name("Java Expert")
        assert resolved == "java-expert"
