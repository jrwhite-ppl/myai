"""Tests for agent storage implementation."""

import tempfile
from pathlib import Path

import pytest

from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification
from myai.storage.agent import AgentStorage
from myai.storage.base import StorageError
from myai.storage.filesystem import FileSystemStorage


class TestAgentStorage:
    """Test agent storage implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """Create filesystem storage instance."""
        return FileSystemStorage(temp_dir)

    @pytest.fixture
    def agent_storage(self, storage):
        """Create agent storage instance."""
        return AgentStorage(storage)

    @pytest.fixture
    def sample_agent(self):
        """Create sample agent specification."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="A test agent for unit testing",
            category=AgentCategory.ENGINEERING,
            tags=["test", "automation"],
            tools=["claude", "terminal"],
        )

        return AgentSpecification(
            metadata=metadata, content="You are a helpful test agent.", dependencies=["base_agent"]
        )

    def test_save_and_load_agent(self, agent_storage, sample_agent):
        """Test saving and loading agent."""
        agent_storage.save_agent(sample_agent)

        loaded = agent_storage.load_agent("test_agent", "engineering")
        assert loaded is not None
        assert loaded.metadata.name == "test_agent"
        assert loaded.metadata.display_name == "Test Agent"
        assert loaded.content == "You are a helpful test agent."

    def test_load_agent_any_category(self, agent_storage, sample_agent):
        """Test loading agent without specifying category."""
        agent_storage.save_agent(sample_agent)

        # Should find agent in any category
        loaded = agent_storage.load_agent("test_agent")
        assert loaded is not None
        assert loaded.metadata.name == "test_agent"

    def test_load_nonexistent_agent(self, agent_storage):
        """Test loading nonexistent agent returns None."""
        result = agent_storage.load_agent("nonexistent")
        assert result is None

    def test_list_agents(self, agent_storage, sample_agent):
        """Test listing agents."""
        assert agent_storage.list_agents() == []

        agent_storage.save_agent(sample_agent)

        # Create another agent in different category
        metadata2 = AgentMetadata(
            name="business_agent",
            display_name="Business Agent",
            description="A business agent",
            category=AgentCategory.BUSINESS,
        )
        agent2 = AgentSpecification(metadata=metadata2, content="You are a business expert.")
        agent_storage.save_agent(agent2)

        # List all agents
        all_agents = agent_storage.list_agents()
        assert sorted(all_agents) == ["business_agent", "test_agent"]

        # List by category
        engineering_agents = agent_storage.list_agents("engineering")
        assert engineering_agents == ["test_agent"]

        business_agents = agent_storage.list_agents("business")
        assert business_agents == ["business_agent"]

    def test_list_categories(self, agent_storage, sample_agent):
        """Test listing categories."""
        assert agent_storage.list_categories() == []

        agent_storage.save_agent(sample_agent)

        categories = agent_storage.list_categories()
        assert categories == ["engineering"]

    def test_get_agents_by_category(self, agent_storage, sample_agent):
        """Test getting all agents in a category."""
        agent_storage.save_agent(sample_agent)

        agents = agent_storage.get_agents_by_category("engineering")
        assert len(agents) == 1
        assert agents[0].metadata.name == "test_agent"

        # Empty category
        empty_agents = agent_storage.get_agents_by_category("marketing")
        assert empty_agents == []

    def test_search_agents(self, agent_storage, sample_agent):
        """Test searching agents by various criteria."""
        agent_storage.save_agent(sample_agent)

        # Search by query
        results = agent_storage.search_agents(query="test")
        assert len(results) == 1
        assert results[0].metadata.name == "test_agent"

        # Search by tags
        results = agent_storage.search_agents(tags=["test"])
        assert len(results) == 1

        results = agent_storage.search_agents(tags=["nonexistent"])
        assert len(results) == 0

        # Search by tools
        results = agent_storage.search_agents(tools=["claude"])
        assert len(results) == 1

        results = agent_storage.search_agents(tools=["nonexistent"])
        assert len(results) == 0

        # Search by category
        results = agent_storage.search_agents(category="engineering")
        assert len(results) == 1

        results = agent_storage.search_agents(category="business")
        assert len(results) == 0

    def test_delete_agent(self, agent_storage, sample_agent):
        """Test deleting agent."""
        agent_storage.save_agent(sample_agent)
        assert agent_storage.load_agent("test_agent") is not None

        # Delete by category
        assert agent_storage.delete_agent("test_agent", "engineering") is True
        assert agent_storage.load_agent("test_agent") is None

        # Delete nonexistent
        assert agent_storage.delete_agent("test_agent", "engineering") is False

    def test_delete_agent_any_category(self, agent_storage, sample_agent):
        """Test deleting agent without specifying category."""
        agent_storage.save_agent(sample_agent)

        # Delete without specifying category
        assert agent_storage.delete_agent("test_agent") is True
        assert agent_storage.load_agent("test_agent") is None

    def test_move_agent(self, agent_storage, sample_agent):
        """Test moving agent between categories."""
        agent_storage.save_agent(sample_agent)

        # Move from engineering to business
        assert agent_storage.move_agent("test_agent", "engineering", "business") is True

        # Should not be in engineering anymore
        assert agent_storage.load_agent("test_agent", "engineering") is None

        # Should be in business
        moved_agent = agent_storage.load_agent("test_agent", "business")
        assert moved_agent is not None
        assert moved_agent.metadata.category == AgentCategory.BUSINESS

    def test_move_nonexistent_agent(self, agent_storage):
        """Test moving nonexistent agent returns False."""
        assert agent_storage.move_agent("nonexistent", "engineering", "business") is False

    def test_copy_agent(self, agent_storage, sample_agent):
        """Test copying agent with new name."""
        agent_storage.save_agent(sample_agent)

        # Copy agent
        assert agent_storage.copy_agent("test_agent", "copied_agent", "engineering") is True

        # Original should still exist
        original = agent_storage.load_agent("test_agent", "engineering")
        assert original is not None

        # Copy should exist with new name
        copy = agent_storage.load_agent("copied_agent", "engineering")
        assert copy is not None
        assert copy.metadata.name == "copied_agent"
        assert "Copy of" in copy.metadata.display_name

    def test_copy_nonexistent_agent(self, agent_storage):
        """Test copying nonexistent agent returns False."""
        assert agent_storage.copy_agent("nonexistent", "copy", "engineering") is False

    def test_export_agent(self, agent_storage, sample_agent, temp_dir):
        """Test exporting agent to markdown file."""
        agent_storage.save_agent(sample_agent)

        export_path = temp_dir / "exported_agent.md"
        agent_storage.export_agent("test_agent", export_path, "engineering")

        assert export_path.exists()

        # Verify content
        content = export_path.read_text()
        assert "test_agent" in content
        assert "Test Agent" in content
        assert "You are a helpful test agent." in content

    def test_export_nonexistent_agent(self, agent_storage, temp_dir):
        """Test exporting nonexistent agent raises error."""
        export_path = temp_dir / "nonexistent.md"

        with pytest.raises(StorageError):
            agent_storage.export_agent("nonexistent", export_path)

    def test_import_agent(self, agent_storage, temp_dir):
        """Test importing agent from markdown file."""
        # Create markdown file
        markdown_content = """---
name: imported_agent
display_name: Imported Agent
description: An imported agent
category: engineering
tags: ["imported", "test"]
tools: ["claude"]
version: 1.0.0
---

You are an imported agent for testing."""

        import_path = temp_dir / "import_agent.md"
        import_path.write_text(markdown_content)

        # Import
        imported_agent = agent_storage.import_agent(import_path)

        assert imported_agent.metadata.name == "imported_agent"
        assert imported_agent.metadata.display_name == "Imported Agent"
        assert "imported" in imported_agent.metadata.tags

        # Should be saved in storage
        loaded = agent_storage.load_agent("imported_agent", "engineering")
        assert loaded is not None

    def test_import_agent_with_category_override(self, agent_storage, temp_dir):
        """Test importing agent with category override."""
        markdown_content = """---
name: override_agent
display_name: Override Agent
description: An agent with category override
category: engineering
---

Content here."""

        import_path = temp_dir / "override_agent.md"
        import_path.write_text(markdown_content)

        # Import with category override
        imported_agent = agent_storage.import_agent(import_path, "business")

        assert imported_agent.metadata.category == AgentCategory.BUSINESS

        # Should be saved in business category
        loaded = agent_storage.load_agent("override_agent", "business")
        assert loaded is not None

    def test_get_agent_dependencies(self, agent_storage, sample_agent):
        """Test getting agent dependencies."""
        # Create dependency agent
        dep_metadata = AgentMetadata(
            name="base_agent",
            display_name="Base Agent",
            description="Base agent dependency",
            category=AgentCategory.ENGINEERING,
        )
        dep_agent = AgentSpecification(metadata=dep_metadata, content="Base agent content.")
        agent_storage.save_agent(dep_agent)

        # Save main agent (depends on base_agent)
        agent_storage.save_agent(sample_agent)

        # Get dependencies
        deps = agent_storage.get_agent_dependencies("test_agent", "engineering")
        assert len(deps) == 1
        assert deps[0].metadata.name == "base_agent"

    def test_get_dependencies_nonexistent_agent(self, agent_storage):
        """Test getting dependencies for nonexistent agent."""
        deps = agent_storage.get_agent_dependencies("nonexistent")
        assert deps == []

    def test_validate_agent(self, agent_storage):
        """Test agent validation."""
        # Valid agent data
        valid_data = {
            "metadata": {
                "name": "valid_agent",
                "display_name": "Valid Agent",
                "description": "A valid agent",
                "category": "engineering",
            },
            "content": "Valid agent content.",
        }
        errors = agent_storage.validate_agent(valid_data)
        assert errors == []

        # Invalid agent data
        invalid_data = {
            "metadata": {
                "name": "",  # Invalid empty name
                "display_name": "Invalid Agent",
                "description": "An invalid agent",
                "category": "invalid_category",  # Invalid category
            },
            "content": "",  # Invalid empty content
        }
        errors = agent_storage.validate_agent(invalid_data)
        assert len(errors) > 0

    def test_agent_backup_on_save(self, agent_storage, sample_agent):
        """Test that saving creates backup of existing agent."""
        # Save initial agent
        agent_storage.save_agent(sample_agent)

        # Modify and save again
        sample_agent.content = "Modified content"
        agent_storage.save_agent(sample_agent)

        # Should have created backup (if storage supports it)
        if hasattr(agent_storage.storage, "list_backups"):
            key = "agents/engineering/test_agent"
            backups = agent_storage.storage.list_backups(key)
            assert len(backups) >= 1

    def test_matches_criteria(self, agent_storage, sample_agent):
        """Test the internal _matches_criteria method."""
        # Test query matching
        assert agent_storage._matches_criteria(sample_agent, "test", None, None) is True
        assert agent_storage._matches_criteria(sample_agent, "nonexistent", None, None) is False

        # Test tag matching
        assert agent_storage._matches_criteria(sample_agent, "", ["test"], None) is True
        assert agent_storage._matches_criteria(sample_agent, "", ["nonexistent"], None) is False

        # Test tool matching
        assert agent_storage._matches_criteria(sample_agent, "", None, ["claude"]) is True
        assert agent_storage._matches_criteria(sample_agent, "", None, ["nonexistent"]) is False
