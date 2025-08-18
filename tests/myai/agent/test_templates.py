"""Tests for agent template system."""

import tempfile
from pathlib import Path

import pytest

from myai.agent.templates import AgentTemplate, TemplateRegistry, get_template_registry
from myai.models.agent import AgentCategory, AgentSpecification


class TestAgentTemplate:
    """Test AgentTemplate functionality."""

    def test_template_creation(self):
        """Test creating a basic template."""
        template = AgentTemplate(
            name="test-template",
            display_name="Test Template",
            category=AgentCategory.ENGINEERING,
            description="A test template",
            content_template="Hello ${name}, you are ${role}!",
            default_variables={"role": "developer"},
            tools=["claude"],
            tags=["test"],
        )

        assert template.name == "test-template"
        assert template.display_name == "Test Template"
        assert template.required_variables == {"name", "role"}
        assert template.default_variables == {"role": "developer"}

    def test_variable_extraction(self):
        """Test variable extraction from template."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            category=AgentCategory.CUSTOM,
            description="Test",
            content_template="""
            Simple: $var1
            Braced: ${var2}
            Repeated: $var1 and ${var1}
            Escaped: $$notavar
            Complex: ${var_with_underscore}
            """,
        )

        expected_vars = {"var1", "var2", "var_with_underscore"}
        assert template.required_variables == expected_vars

    def test_variable_validation(self):
        """Test variable validation."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            category=AgentCategory.CUSTOM,
            description="Test",
            content_template="Need ${required} and ${optional}",
            default_variables={"optional": "default"},
        )

        # Missing required variable
        missing = template.validate_variables({})
        assert missing == ["required"]

        # All variables provided
        missing = template.validate_variables({"required": "value"})
        assert missing == []

        # Extra variables are ok
        missing = template.validate_variables({"required": "value", "extra": "ignored"})
        assert missing == []

    def test_template_rendering(self):
        """Test rendering template to agent specification."""
        template = AgentTemplate(
            name="test-template",
            display_name="Test Template",
            category=AgentCategory.BUSINESS,
            description="Template description",
            content_template="You are ${role} working on ${project}.",
            default_variables={"role": "analyst"},
            tools=["claude", "browser"],
            tags=["template", "test"],
        )

        # Render with all variables
        agent = template.render(
            name="my-agent",
            display_name="My Agent",
            variables={"project": "data analysis"},
        )

        assert agent.metadata.name == "my-agent"
        assert agent.metadata.display_name == "My Agent"
        assert agent.metadata.category == AgentCategory.BUSINESS
        assert agent.content == "You are analyst working on data analysis."
        assert agent.metadata.tools == ["claude", "browser"]
        assert agent.metadata.tags == ["template", "test"]
        assert not agent.is_template

    def test_rendering_with_missing_variables(self):
        """Test rendering fails with missing required variables."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            category=AgentCategory.CUSTOM,
            description="Test",
            content_template="Need ${required}",
        )

        with pytest.raises(ValueError, match="Missing required variables: required"):
            template.render("agent", "Agent")

    def test_rendering_with_custom_metadata(self):
        """Test rendering with custom metadata overrides."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            category=AgentCategory.ENGINEERING,
            description="Template desc",
            content_template="Template content with enough characters",
            tools=["claude"],
            tags=["template"],
        )

        agent = template.render(
            name="custom-agent",
            display_name="Custom Agent",
            description="Custom description",
            tools=["cursor", "terminal"],
            tags=["custom", "override"],
        )

        assert agent.metadata.description == "Custom description"
        assert agent.metadata.tools == ["cursor", "terminal"]
        assert agent.metadata.tags == ["custom", "override"]

    def test_to_specification(self):
        """Test converting template to agent specification."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            category=AgentCategory.CUSTOM,
            description="Test template",
            content_template="Template content",
            default_variables={"var": "value"},
        )

        spec = template.to_specification()

        assert spec.metadata.name == "template-test"
        assert spec.metadata.display_name == "Template: Test"
        assert spec.content == "Template content"
        assert spec.is_template
        assert spec.template_variables == {"var": "value"}
        assert "template" in spec.metadata.tags


class TestTemplateRegistry:
    """Test TemplateRegistry functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def registry(self, temp_dir):
        """Create template registry for testing."""
        return TemplateRegistry(base_path=temp_dir, auto_discover=False)

    def test_default_templates(self, registry):
        """Test default templates are registered."""
        templates = registry.list_templates(include_system=True)
        template_names = [t.name for t in templates]

        assert "engineering-base" in template_names
        assert "business-analyst" in template_names
        assert "security-expert" in template_names
        assert "custom-specialist" in template_names

        # Check they are system templates
        for name in ["engineering-base", "business-analyst", "security-expert", "custom-specialist"]:
            template = registry.get_template(name)
            assert template is not None
            assert template.is_system

    def test_register_and_get_template(self, registry):
        """Test registering and retrieving templates."""
        template = AgentTemplate(
            name="my-template",
            display_name="My Template",
            category=AgentCategory.CUSTOM,
            description="Test",
            content_template="Template content with enough characters",
        )

        registry.register_template(template, persist=False)

        # Retrieve template
        retrieved = registry.get_template("my-template")
        assert retrieved is not None
        assert retrieved.name == "my-template"
        assert not retrieved.is_system

    def test_list_templates_with_filtering(self, registry):
        """Test listing templates with category filter."""
        # Add custom template
        template = AgentTemplate(
            name="custom-test",
            display_name="Custom Test",
            category=AgentCategory.MARKETING,
            description="Test",
            content_template="Template content with enough characters",
        )
        registry.register_template(template, persist=False)

        # List all templates
        all_templates = registry.list_templates()
        assert len(all_templates) >= 5  # 4 system + 1 custom

        # List only engineering templates
        eng_templates = registry.list_templates(category=AgentCategory.ENGINEERING)
        assert all(t.category == AgentCategory.ENGINEERING for t in eng_templates)
        assert len(eng_templates) >= 1

        # List only marketing templates
        marketing_templates = registry.list_templates(category=AgentCategory.MARKETING)
        assert len(marketing_templates) == 1
        assert marketing_templates[0].name == "custom-test"

    def test_system_template_protection(self, registry):
        """Test that system templates cannot be deleted."""
        with pytest.raises(ValueError, match="Cannot delete system template"):
            registry.delete_template("engineering-base")

    def test_delete_user_template(self, registry):
        """Test deleting user templates."""
        # Create and register template
        template = AgentTemplate(
            name="deletable",
            display_name="Deletable",
            category=AgentCategory.CUSTOM,
            description="Test",
            content_template="Template content with enough characters",
        )
        registry.register_template(template)

        # Verify it exists
        assert registry.get_template("deletable") is not None

        # Delete it
        assert registry.delete_template("deletable")

        # Verify it's gone
        assert registry.get_template("deletable") is None

        # Try to delete non-existent
        assert not registry.delete_template("nonexistent")

    def test_create_from_agent(self, registry):
        """Test creating template from existing agent."""
        # Create source agent
        from myai.models.agent import AgentMetadata

        metadata = AgentMetadata(
            name="source-agent",
            display_name="Source Agent",
            description="Source description",
            category=AgentCategory.ENGINEERING,
            tools=["claude"],
            tags=["source"],
        )

        agent = AgentSpecification(
            metadata=metadata,
            content="This is the [role value] working on [project value].",
        )

        # Create template from agent
        template = registry.create_from_agent(
            agent,
            "derived-template",
            variables_to_extract=["role", "project"],
        )

        assert template.name == "derived-template"
        assert template.category == AgentCategory.ENGINEERING
        assert "${role}" in template.content_template
        assert "${project}" in template.content_template
        assert "role" in template.required_variables
        assert "project" in template.required_variables

    def test_template_discovery(self, registry, temp_dir):
        """Test discovering templates from storage."""
        # Create a template agent in storage
        from myai.models.agent import AgentMetadata
        from myai.storage.agent import AgentStorage
        from myai.storage.filesystem import FileSystemStorage

        storage = FileSystemStorage(temp_dir)
        agent_storage = AgentStorage(storage)

        # Create template agent
        metadata = AgentMetadata(
            name="discovered-template",
            display_name="Discovered Template",
            description="Test",
            category=AgentCategory.CUSTOM,
            tags=["template"],
        )

        template_agent = AgentSpecification(
            metadata=metadata,
            content="Template content with ${variable}",
            is_template=True,
            template_variables={"variable": "default"},
        )

        agent_storage.save_agent(template_agent)

        # Discover templates
        discovered = registry.discover_templates()

        assert "discovered-template" in discovered

        # Verify template is available
        template = registry.get_template("discovered-template")
        assert template is not None
        assert template.name == "discovered-template"
        assert "variable" in template.required_variables

    def test_get_template_registry_function(self):
        """Test convenience function returns TemplateRegistry."""
        registry = get_template_registry()
        assert isinstance(registry, TemplateRegistry)

        # Should have default templates
        templates = registry.list_templates(include_system=True)
        assert len(templates) >= 4  # At least 4 default templates


class TestDefaultTemplates:
    """Test the default system templates work correctly."""

    @pytest.fixture
    def registry(self):
        """Get template registry with defaults."""
        return TemplateRegistry(auto_discover=False)

    def test_engineering_template(self, registry):
        """Test engineering template renders correctly."""
        template = registry.get_template("engineering-base")
        assert template is not None

        agent = template.render(
            name="backend-engineer",
            display_name="Backend Engineer",
            variables={
                "agent_role": "a backend engineer",
                "specialty": "API development and microservices",
                "tools_list": "- Python/FastAPI\n- PostgreSQL\n- Redis\n- Docker",
                "guidelines": "- RESTful API design\n- Database optimization\n- Caching strategies",
            },
        )

        assert agent.metadata.name == "backend-engineer"
        assert agent.metadata.category == AgentCategory.ENGINEERING
        assert "backend engineer" in agent.content
        assert "API development" in agent.content
        assert "Python/FastAPI" in agent.content
        assert agent.metadata.tools == ["claude", "cursor", "terminal"]

    def test_business_template(self, registry):
        """Test business analyst template."""
        template = registry.get_template("business-analyst")
        assert template is not None

        agent = template.render(
            name="market-analyst",
            display_name="Market Analyst",
            variables={
                "agent_role": "a market research analyst",
                "specialty": "competitive analysis and market trends",
                "framework": "- Competitive analysis\n- Market segmentation\n- Trend analysis",
                "metrics": "- Market size and growth\n- Competitive positioning\n- Customer segments",
            },
        )

        assert agent.metadata.name == "market-analyst"
        assert agent.metadata.category == AgentCategory.BUSINESS
        assert "market research analyst" in agent.content
        assert "competitive analysis" in agent.content

    def test_security_template(self, registry):
        """Test security expert template."""
        template = registry.get_template("security-expert")
        assert template is not None

        agent = template.render(
            name="appsec-expert",
            display_name="AppSec Expert",
            variables={
                "agent_role": "an application security expert",
                "specialty": "secure code review and vulnerability assessment",
                "framework": "- OWASP ASVS\n- Secure coding guidelines\n- Threat modeling",
                "responsibilities": "- Code security review\n- Vulnerability scanning\n- Security training",
                "tools": "- SAST tools\n- Dependency scanners\n- Security linters",
            },
        )

        assert agent.metadata.name == "appsec-expert"
        assert agent.metadata.category == AgentCategory.SECURITY
        assert "application security expert" in agent.content
        assert "OWASP" in agent.content

    def test_custom_template(self, registry):
        """Test custom specialist template."""
        template = registry.get_template("custom-specialist")
        assert template is not None

        agent = template.render(
            name="data-scientist",
            display_name="Data Scientist",
            variables={
                "agent_role": "a data science expert",
                "specialty": "machine learning and predictive analytics",
                "overview": "Specializing in ML model development and data insights",
                "principles": "- Data-driven decision making\n- Reproducible research\n- Ethical AI",
                "methodology": "- Exploratory data analysis\n- Feature engineering\n- Model validation",
                "success_criteria": "- Model accuracy and performance\n- Business impact\n- Interpretability",
            },
        )

        assert agent.metadata.name == "data-scientist"
        assert agent.metadata.category == AgentCategory.CUSTOM
        assert "data science expert" in agent.content
        assert "machine learning" in agent.content
