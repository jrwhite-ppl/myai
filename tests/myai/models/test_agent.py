"""Tests for agent models."""

from datetime import datetime
from pathlib import Path

import pytest

from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification


class TestAgentCategory:
    """Test AgentCategory enum."""

    def test_agent_categories(self):
        """Test all agent categories exist."""
        expected_categories = [
            "engineering",
            "business",
            "marketing",
            "finance",
            "legal",
            "security",
            "leadership",
            "custom",
        ]

        for category in expected_categories:
            assert hasattr(AgentCategory, category.upper())
            assert getattr(AgentCategory, category.upper()).value == category


class TestAgentMetadata:
    """Test AgentMetadata model."""

    def test_basic_metadata_creation(self):
        """Test basic metadata creation."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="A test agent for testing purposes",
            category=AgentCategory.ENGINEERING,
        )

        assert metadata.name == "test_agent"
        assert metadata.display_name == "Test Agent"
        assert metadata.description == "A test agent for testing purposes"
        assert metadata.category == AgentCategory.ENGINEERING
        assert metadata.version == "1.0.0"
        assert isinstance(metadata.created, datetime)
        assert isinstance(metadata.modified, datetime)

    def test_name_validation(self):
        """Test agent name validation."""
        # Valid names
        valid_names = ["test_agent", "test-agent", "testagent", "test123"]
        for name in valid_names:
            metadata = AgentMetadata(name=name, display_name="Test", description="Test", category=AgentCategory.CUSTOM)
            assert metadata.name == name.lower()

        # Invalid names
        invalid_names = ["test agent", "test.agent", "test@agent", ""]
        for name in invalid_names:
            with pytest.raises(ValueError):
                AgentMetadata(name=name, display_name="Test", description="Test", category=AgentCategory.CUSTOM)

    def test_tags_validation(self):
        """Test tags validation."""
        # Valid tags
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            tags=["python", "ai", "automation"],
        )
        assert metadata.tags == ["python", "ai", "automation"]

        # Too many tags
        with pytest.raises(ValueError):
            AgentMetadata(
                name="test_agent",
                display_name="Test Agent",
                description="Test description",
                category=AgentCategory.ENGINEERING,
                tags=["tag" + str(i) for i in range(25)],  # More than 20 tags
            )

        # Invalid tag (too long)
        with pytest.raises(ValueError):
            AgentMetadata(
                name="test_agent",
                display_name="Test Agent",
                description="Test description",
                category=AgentCategory.ENGINEERING,
                tags=["a" * 51],  # More than 50 characters
            )

    def test_tools_validation(self):
        """Test tools validation."""
        # Valid tools
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            tools=["claude", "cursor", "vscode"],
        )
        assert metadata.tools == ["claude", "cursor", "vscode"]

        # Custom tool
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            tools=["custom_tool"],
        )
        assert metadata.tools == ["custom_tool"]

        # Invalid tool name
        with pytest.raises(ValueError):
            AgentMetadata(
                name="test_agent",
                display_name="Test Agent",
                description="Test description",
                category=AgentCategory.ENGINEERING,
                tools=["invalid tool"],  # Space not allowed
            )

    def test_optional_fields(self):
        """Test optional metadata fields."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            author="test@example.com",
        )

        assert metadata.model == "gpt-4"
        assert metadata.temperature == 0.7
        assert metadata.max_tokens == 2000
        assert metadata.author == "test@example.com"

    def test_temperature_validation(self):
        """Test temperature validation."""
        # Valid temperatures
        for temp in [0.0, 0.5, 1.0, 2.0]:
            metadata = AgentMetadata(
                name="test_agent",
                display_name="Test Agent",
                description="Test description",
                category=AgentCategory.ENGINEERING,
                temperature=temp,
            )
            assert metadata.temperature == temp

        # Invalid temperatures
        for temp in [-0.1, 2.1]:
            with pytest.raises(ValueError):
                AgentMetadata(
                    name="test_agent",
                    display_name="Test Agent",
                    description="Test description",
                    category=AgentCategory.ENGINEERING,
                    temperature=temp,
                )

    def test_max_tokens_validation(self):
        """Test max_tokens validation."""
        # Valid values
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            max_tokens=1000,
        )
        assert metadata.max_tokens == 1000

        # Invalid values
        for tokens in [0, 100001]:
            with pytest.raises(ValueError):
                AgentMetadata(
                    name="test_agent",
                    display_name="Test Agent",
                    description="Test description",
                    category=AgentCategory.ENGINEERING,
                    max_tokens=tokens,
                )


class TestAgentSpecification:
    """Test AgentSpecification model."""

    def test_basic_specification_creation(self):
        """Test basic specification creation."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
        )

        spec = AgentSpecification(metadata=metadata, content="This is the agent content.")

        assert spec.metadata.name == "test_agent"
        assert spec.content == "This is the agent content."
        assert spec.is_template is False
        assert spec.template_variables == {}
        assert spec.dependencies == []

    def test_content_validation(self):
        """Test content validation."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
        )

        # Valid content
        spec = AgentSpecification(metadata=metadata, content="This is valid content that is long enough.")
        assert len(spec.content) >= 10

        # Invalid content (too short)
        with pytest.raises(ValueError):
            AgentSpecification(metadata=metadata, content="Short")

    def test_dependencies_validation(self):
        """Test dependencies validation."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
        )

        # Valid dependencies
        spec = AgentSpecification(
            metadata=metadata, content="Agent content here.", dependencies=["other_agent", "another-agent"]
        )
        assert spec.dependencies == ["other_agent", "another-agent"]

        # Invalid dependency name
        with pytest.raises(ValueError):
            AgentSpecification(
                metadata=metadata,
                content="Agent content here.",
                dependencies=["invalid dependency"],  # Space not allowed
            )

    def test_get_frontmatter(self):
        """Test frontmatter extraction."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            tags=["test", "example"],
            tools=["claude"],
            author="test@example.com",
        )

        spec = AgentSpecification(metadata=metadata, content="Agent content here.")

        frontmatter = spec.get_frontmatter()

        assert frontmatter["name"] == "test_agent"
        assert frontmatter["display_name"] == "Test Agent"
        assert frontmatter["description"] == "Test description"
        assert frontmatter["category"] == "engineering"
        assert frontmatter["tags"] == ["test", "example"]
        assert frontmatter["tools"] == ["claude"]
        assert frontmatter["author"] == "test@example.com"
        assert "created" in frontmatter
        assert "modified" in frontmatter

    def test_to_markdown(self):
        """Test markdown conversion."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
            tags=["test"],
        )

        spec = AgentSpecification(metadata=metadata, content="# Agent Content\n\nThis is the agent content.")

        markdown = spec.to_markdown()

        assert markdown.startswith("---")
        assert "name: test_agent" in markdown
        assert "display_name: Test Agent" in markdown
        assert "category: engineering" in markdown
        assert "tags: ['test']" in markdown
        assert markdown.endswith("# Agent Content\n\nThis is the agent content.")

    def test_from_markdown_basic(self):
        """Test basic markdown parsing."""
        markdown_content = """---
name: test_agent
display_name: Test Agent
description: Test description
category: engineering
tags: ['test', 'example']
---

# Test Agent

This is the agent content."""

        spec = AgentSpecification.from_markdown(markdown_content)

        assert spec.metadata.name == "test_agent"
        assert spec.metadata.display_name == "Test Agent"
        assert spec.metadata.description == "Test description"
        assert spec.metadata.category == AgentCategory.ENGINEERING
        assert spec.metadata.tags == ["test", "example"]
        assert spec.content == "# Test Agent\n\nThis is the agent content."

    def test_from_markdown_no_frontmatter(self):
        """Test markdown parsing without frontmatter."""
        markdown_content = "# Simple Agent\n\nThis is a simple agent without frontmatter."

        spec = AgentSpecification.from_markdown(markdown_content)

        assert spec.metadata.name == "unnamed_agent"
        assert spec.metadata.display_name == "Unnamed Agent"
        assert spec.metadata.description == "No description provided"
        assert spec.metadata.category == AgentCategory.CUSTOM
        assert spec.content == "# Simple Agent\n\nThis is a simple agent without frontmatter."

    def test_from_markdown_with_file_path(self):
        """Test markdown parsing with file path."""
        markdown_content = """---
name: test_agent
display_name: Test Agent
description: Test description
category: engineering
---

Agent content here."""

        file_path = Path("/test/agents/test_agent.md")
        spec = AgentSpecification.from_markdown(markdown_content, file_path=file_path)

        assert spec.file_path == file_path
        assert spec.metadata.name == "test_agent"

    def test_roundtrip_conversion(self):
        """Test markdown to spec to markdown conversion."""
        original_markdown = """---
name: roundtrip_agent
display_name: Roundtrip Agent
description: Test roundtrip conversion
category: engineering
version: 1.0.0
tags: ['test', 'roundtrip']
tools: ['claude']
---

# Roundtrip Agent

This agent tests roundtrip conversion."""

        # Parse from markdown
        spec = AgentSpecification.from_markdown(original_markdown)

        # Convert back to markdown
        converted_markdown = spec.to_markdown()

        # Parse again
        spec2 = AgentSpecification.from_markdown(converted_markdown)

        # Should be equivalent
        assert spec.metadata.name == spec2.metadata.name
        assert spec.metadata.display_name == spec2.metadata.display_name
        assert spec.metadata.description == spec2.metadata.description
        assert spec.metadata.category == spec2.metadata.category
        assert spec.metadata.tags == spec2.metadata.tags
        assert spec.metadata.tools == spec2.metadata.tools
        assert spec.content.strip() == spec2.content.strip()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_frontmatter(self):
        """Test invalid frontmatter handling."""
        invalid_markdown = """---
name: test_agent
display_name: Test Agent
# Missing closing ---
Agent content here."""

        with pytest.raises(ValueError):
            AgentSpecification.from_markdown(invalid_markdown)

    def test_empty_content(self):
        """Test empty content handling."""
        metadata = AgentMetadata(
            name="test_agent",
            display_name="Test Agent",
            description="Test description",
            category=AgentCategory.ENGINEERING,
        )

        with pytest.raises(ValueError):
            AgentSpecification(metadata=metadata, content="")

    def test_template_specification(self):
        """Test template agent specification."""
        metadata = AgentMetadata(
            name="template_agent",
            display_name="Template Agent",
            description="A template agent",
            category=AgentCategory.CUSTOM,
        )

        spec = AgentSpecification(
            metadata=metadata,
            content="Template content with {{variable}}",
            is_template=True,
            template_variables={"variable": "default_value"},
        )

        assert spec.is_template is True
        assert spec.template_variables == {"variable": "default_value"}
        assert "{{variable}}" in spec.content
