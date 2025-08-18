"""Tests for agent manager."""

import tempfile
from pathlib import Path

import pytest

from myai.agent.manager import AgentManager
from myai.agent.registry import AgentRegistry
from myai.models.agent import AgentCategory


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
def agent_manager(temp_dir):
    """Create agent manager for testing."""
    # Create isolated registry for testing
    registry = AgentRegistry(base_path=temp_dir, auto_discover=False)
    return AgentManager(base_path=temp_dir, registry=registry)


class TestAgentManager:
    """Test AgentManager functionality."""

    def test_create_agent(self, agent_manager):
        """Test creating a new agent."""
        agent = agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            description="A test agent",
            content="This is a test agent.",
            tools=["claude", "cursor"],
            tags=["test"],
        )

        assert agent.metadata.name == "test-agent"
        assert agent.metadata.display_name == "Test Agent"
        assert agent.metadata.category == AgentCategory.ENGINEERING
        assert agent.content == "This is a test agent."

        # Verify agent is registered
        retrieved = agent_manager.registry.get_agent("test-agent")
        assert retrieved is not None

    def test_create_agent_invalid_name(self, agent_manager):
        """Test creating agent with invalid name."""
        with pytest.raises(ValueError, match="Invalid agent name"):
            agent_manager.create_agent(
                name="test agent!",  # Invalid characters
                display_name="Test Agent",
                category=AgentCategory.ENGINEERING,
            )

    def test_create_duplicate_agent(self, agent_manager):
        """Test creating duplicate agent."""
        # Create first agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Try to create duplicate
        with pytest.raises(ValueError, match="already exists"):
            agent_manager.create_agent(
                name="test-agent",
                display_name="Another Test Agent",
                category=AgentCategory.BUSINESS,
            )

    def test_update_agent(self, agent_manager):
        """Test updating an agent."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            content="Original content",
            version="1.0.0",
        )

        # Update agent
        updated = agent_manager.update_agent(
            name="test-agent",
            display_name="Updated Test Agent",
            content="Updated content",
            tags=["updated"],
        )

        assert updated.metadata.display_name == "Updated Test Agent"
        assert updated.content == "Updated content"
        assert updated.metadata.tags == ["updated"]
        assert updated.metadata.version == "1.0.1"  # Version bumped

        # Verify state tracking
        state = agent_manager.get_agent_state("test-agent")
        assert state["modified"] is True
        assert state["active_version"] == "1.0.1"
        assert "1.0.0" in state["versions"]
        assert "1.0.1" in state["versions"]

    def test_update_agent_no_version_bump(self, agent_manager):
        """Test updating agent without version bump."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            version="1.0.0",
        )

        # Update without version bump
        updated = agent_manager.update_agent(
            name="test-agent",
            description="Updated description",
            version_bump=False,
        )

        assert updated.metadata.version == "1.0.0"

    def test_update_nonexistent_agent(self, agent_manager):
        """Test updating nonexistent agent."""
        with pytest.raises(ValueError, match="not found"):
            agent_manager.update_agent(
                name="nonexistent",
                content="New content",
            )

    def test_delete_agent(self, agent_manager):
        """Test deleting an agent."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Delete agent
        assert agent_manager.delete_agent("test-agent") is True

        # Verify agent is gone
        assert agent_manager.registry.get_agent("test-agent") is None
        assert agent_manager.get_agent_state("test-agent") == {}

    def test_delete_nonexistent_agent(self, agent_manager):
        """Test deleting nonexistent agent."""
        assert agent_manager.delete_agent("nonexistent") is False

    def test_delete_agent_with_dependents(self, agent_manager):
        """Test deleting agent with dependents."""
        # Create agents
        agent_manager.create_agent(
            name="base-agent",
            display_name="Base Agent",
            category=AgentCategory.ENGINEERING,
        )
        agent_manager.create_agent(
            name="dependent-agent",
            display_name="Dependent Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Add dependency
        agent_manager.add_dependency("dependent-agent", "base-agent")

        # Try to delete base agent
        with pytest.raises(ValueError, match="has dependents"):
            agent_manager.delete_agent("base-agent")

        # Force delete
        assert agent_manager.delete_agent("base-agent", force=True) is True

    def test_copy_agent(self, agent_manager):
        """Test copying an agent."""
        # Create source agent
        source = agent_manager.create_agent(
            name="source-agent",
            display_name="Source Agent",
            category=AgentCategory.ENGINEERING,
            content="Source content",
            tools=["claude"],
            tags=["original"],
        )

        # Copy agent
        copy = agent_manager.copy_agent(
            source_name="source-agent",
            target_name="copy-agent",
            display_name="Copy Agent",
        )

        assert copy.metadata.name == "copy-agent"
        assert copy.metadata.display_name == "Copy Agent"
        assert copy.content == source.content
        assert copy.metadata.tools == source.metadata.tools
        assert copy.metadata.version == "1.0.0"

        # Verify state tracking
        state = agent_manager.get_agent_state("copy-agent")
        assert state["copied_from"] == "source-agent"

    def test_copy_nonexistent_agent(self, agent_manager):
        """Test copying nonexistent agent."""
        with pytest.raises(ValueError, match="not found"):
            agent_manager.copy_agent(
                source_name="nonexistent",
                target_name="copy",
            )

    def test_copy_to_existing_agent(self, agent_manager):
        """Test copying to existing agent name."""
        # Create agents
        agent_manager.create_agent(
            name="agent1",
            display_name="Agent 1",
            category=AgentCategory.ENGINEERING,
        )
        agent_manager.create_agent(
            name="agent2",
            display_name="Agent 2",
            category=AgentCategory.ENGINEERING,
        )

        # Try to copy to existing name
        with pytest.raises(ValueError, match="already exists"):
            agent_manager.copy_agent(
                source_name="agent1",
                target_name="agent2",
            )

    def test_export_agent(self, agent_manager, temp_dir):
        """Test exporting an agent."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            description="A test agent",
            content="This is the agent content.",
            tools=["claude"],
            tags=["test", "export"],
        )

        # Export agent
        output_path = temp_dir / "exported" / "test-agent.md"
        exported_path = agent_manager.export_agent("test-agent", output_path)

        assert exported_path.exists()
        content = exported_path.read_text()
        assert "---" in content  # Has frontmatter
        assert "name: test-agent" in content
        assert "This is the agent content." in content

    def test_export_agent_no_metadata(self, agent_manager, temp_dir):
        """Test exporting agent without metadata."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            content="Agent content only.",
        )

        # Export without metadata
        output_path = temp_dir / "test-agent-content.md"
        exported_path = agent_manager.export_agent(
            "test-agent",
            output_path,
            include_metadata=False,
        )

        content = exported_path.read_text()
        assert content == "Agent content only."

    def test_export_nonexistent_agent(self, agent_manager, temp_dir):
        """Test exporting nonexistent agent."""
        with pytest.raises(ValueError, match="not found"):
            agent_manager.export_agent(
                "nonexistent",
                temp_dir / "export.md",
            )

    def test_import_agent(self, agent_manager, temp_dir):
        """Test importing an agent from file."""
        # Create agent file
        agent_content = """---
name: imported-agent
display_name: Imported Agent
version: 1.0.0
description: An imported agent
category: business
tools: [claude, cursor]
tags: [imported, test]
---

This is an imported agent.
"""

        agent_file = temp_dir / "agent.md"
        agent_file.write_text(agent_content)

        # Import agent
        imported = agent_manager.import_agent(agent_file)

        assert imported.metadata.name == "imported-agent"
        assert imported.metadata.display_name == "Imported Agent"
        assert imported.metadata.category == AgentCategory.BUSINESS
        assert imported.content == "This is an imported agent."

        # Verify state tracking
        state = agent_manager.get_agent_state("imported-agent")
        assert state["imported_from"] == str(agent_file)

    def test_import_agent_with_name_override(self, agent_manager, temp_dir):
        """Test importing agent with name override."""
        # Create agent file
        agent_content = """---
name: original-name
display_name: Original Agent
version: 1.0.0
category: engineering
---

Agent content.
"""

        agent_file = temp_dir / "agent.md"
        agent_file.write_text(agent_content)

        # Import with name override
        imported = agent_manager.import_agent(
            agent_file,
            name="new-name",
        )

        assert imported.metadata.name == "new-name"
        assert imported.metadata.display_name == "Original Agent"

    def test_import_existing_agent(self, agent_manager, temp_dir):
        """Test importing existing agent without overwrite."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Create agent file with same name
        agent_content = """---
name: test-agent
display_name: Imported Agent
version: 2.0.0
category: business
---

Different content.
"""

        agent_file = temp_dir / "agent.md"
        agent_file.write_text(agent_content)

        # Try to import without overwrite
        with pytest.raises(ValueError, match="already exists"):
            agent_manager.import_agent(agent_file)

        # Import with overwrite
        imported = agent_manager.import_agent(agent_file, overwrite=True)
        assert imported.metadata.display_name == "Imported Agent"
        assert imported.metadata.category == AgentCategory.BUSINESS

    def test_add_dependency(self, agent_manager):
        """Test adding dependencies between agents."""
        # Create agents
        agent_manager.create_agent(
            name="base-agent",
            display_name="Base Agent",
            category=AgentCategory.ENGINEERING,
        )
        agent_manager.create_agent(
            name="dependent-agent",
            display_name="Dependent Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Add dependency
        agent_manager.add_dependency("dependent-agent", "base-agent")

        # Verify dependencies
        assert agent_manager.get_dependencies("dependent-agent") == ["base-agent"]
        assert agent_manager.get_dependents("base-agent") == ["dependent-agent"]

    def test_add_dependency_nonexistent_agent(self, agent_manager):
        """Test adding dependency with nonexistent agent."""
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
        )

        # Try to add dependency to nonexistent agent
        with pytest.raises(ValueError, match="not found"):
            agent_manager.add_dependency("test-agent", "nonexistent")

        # Try to add dependency from nonexistent agent
        with pytest.raises(ValueError, match="not found"):
            agent_manager.add_dependency("nonexistent", "test-agent")

    def test_circular_dependency_detection(self, agent_manager):
        """Test circular dependency detection."""
        # Create agents
        for name in ["agent-a", "agent-b", "agent-c"]:
            agent_manager.create_agent(
                name=name,
                display_name=f"Agent {name[-1].upper()}",
                category=AgentCategory.ENGINEERING,
            )

        # Create dependency chain: A -> B -> C
        agent_manager.add_dependency("agent-a", "agent-b")
        agent_manager.add_dependency("agent-b", "agent-c")

        # Try to create circular dependency: C -> A
        with pytest.raises(ValueError, match="circular reference"):
            agent_manager.add_dependency("agent-c", "agent-a")

    def test_remove_dependency(self, agent_manager):
        """Test removing dependencies."""
        # Create agents with dependency
        agent_manager.create_agent(
            name="base-agent",
            display_name="Base Agent",
            category=AgentCategory.ENGINEERING,
        )
        agent_manager.create_agent(
            name="dependent-agent",
            display_name="Dependent Agent",
            category=AgentCategory.ENGINEERING,
        )
        agent_manager.add_dependency("dependent-agent", "base-agent")

        # Remove dependency
        assert agent_manager.remove_dependency("dependent-agent", "base-agent") is True

        # Verify removal
        assert agent_manager.get_dependencies("dependent-agent") == []
        assert agent_manager.get_dependents("base-agent") == []

        # Try to remove non-existent dependency
        assert agent_manager.remove_dependency("dependent-agent", "base-agent") is False

    def test_get_all_dependencies(self, agent_manager):
        """Test getting transitive dependencies."""
        # Create agents
        for name in ["agent-a", "agent-b", "agent-c", "agent-d"]:
            agent_manager.create_agent(
                name=name,
                display_name=f"Agent {name[-1].upper()}",
                category=AgentCategory.ENGINEERING,
            )

        # Create dependency tree:
        # A -> B -> C
        # A -> D
        agent_manager.add_dependency("agent-a", "agent-b")
        agent_manager.add_dependency("agent-b", "agent-c")
        agent_manager.add_dependency("agent-a", "agent-d")

        # Get all dependencies
        all_deps = agent_manager.get_all_dependencies("agent-a")
        assert set(all_deps) == {"agent-b", "agent-c", "agent-d"}

        # Order should respect dependency order (C before B)
        assert all_deps.index("agent-c") < all_deps.index("agent-b")

    def test_version_tracking(self, agent_manager):
        """Test version tracking."""
        # Create agent
        agent_manager.create_agent(
            name="test-agent",
            display_name="Test Agent",
            category=AgentCategory.ENGINEERING,
            version="1.0.0",
        )

        # Update multiple times
        for i in range(1, 4):
            agent_manager.update_agent(
                name="test-agent",
                content=f"Version {i} content",
            )

        # Check versions
        versions = agent_manager.list_versions("test-agent")
        assert versions == ["1.0.0", "1.0.1", "1.0.2", "1.0.3"]
