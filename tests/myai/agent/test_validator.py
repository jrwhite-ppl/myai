"""Tests for agent validator."""

import pytest

from myai.agent.validator import AgentValidationError, AgentValidator
from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification


class TestAgentValidator:
    """Test AgentValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return AgentValidator()

    @pytest.fixture
    def strict_validator(self):
        """Create strict validator for testing."""
        return AgentValidator(strict_mode=True)

    @pytest.fixture
    def valid_agent(self):
        """Create a valid agent specification."""
        metadata = AgentMetadata(
            name="valid-agent",
            display_name="Valid Agent",
            description="This is a valid agent for testing purposes",
            version="1.0.0",
            category=AgentCategory.ENGINEERING,
            tools=["claude", "terminal"],
            tags=["test", "valid"],
        )

        content = """# Valid Agent

## Overview
This is a comprehensive agent that follows all guidelines and best practices.

## Guidelines
- Always write clean code
- Follow security best practices
- Document your decisions

## Instructions
You should focus on quality and maintainability. Remember to test your code."""

        return AgentSpecification(metadata=metadata, content=content)

    def test_valid_agent_passes(self, validator, valid_agent):
        """Test that a valid agent passes validation."""
        errors = validator.validate_agent(valid_agent)
        assert errors == []

    def test_name_validation(self, validator):
        """Test agent name validation rules."""
        # Invalid characters - should fail at Pydantic level
        with pytest.raises(ValueError, match="Agent name must contain only alphanumeric"):
            metadata = AgentMetadata(
                name="Invalid Name!",
                display_name="Test",
                description="Test description for validation",
                category=AgentCategory.CUSTOM,
            )

        # Test valid names that should pass
        valid_names = ["my-agent", "agent-123", "test-agent-name", "agent123"]
        for name in valid_names:
            metadata = AgentMetadata(
                name=name,
                display_name="Test",
                description="Test description for validation",
                category=AgentCategory.CUSTOM,
            )
            agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
            errors = validator.validate_agent(agent)
            name_errors = [e for e in errors if e.field == "name"]
            assert name_errors == []

        # Test our custom validator catches additional rules
        metadata = AgentMetadata(
            name="a-",  # Ends with hyphen - should fail custom validation
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)
        assert any("must start and end with alphanumeric" in e.message for e in errors)

    def test_description_validation(self, validator):
        """Test description validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Too short",  # Less than 20 chars
            category=AgentCategory.CUSTOM,
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)

        assert any("at least 20 characters" in e.message for e in errors)

        # Too long
        metadata.description = "x" * 501
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)

        assert any("not exceed 500 characters" in e.message for e in errors)

    def test_version_validation(self, validator):
        """Test version format validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            version="invalid",
            category=AgentCategory.CUSTOM,
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)

        assert any("semantic versioning" in e.message for e in errors)

        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "0.0.1", "1.0.0-beta", "1.0.0-alpha1"]
        for version in valid_versions:
            metadata.version = version
            agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
            errors = validator.validate_agent(agent)
            version_errors = [e for e in errors if e.field == "version"]
            assert version_errors == []

    def test_tag_validation(self, validator):
        """Test tag validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
            tags=["Valid-Tag!", "TOO_LONG_" + "x" * 30],
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)

        tag_errors = [e for e in errors if e.field == "tags"]
        assert len(tag_errors) >= 2
        assert any("lowercase alphanumeric with hyphens" in e.message for e in tag_errors)
        assert any("exceeds maximum length" in e.message for e in tag_errors)

    def test_content_validation(self, validator):
        """Test content validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )

        # Too short content should fail at Pydantic level
        with pytest.raises(ValueError, match="String should have at least 10 characters"):
            agent = AgentSpecification(metadata=metadata, content="Too short")

        # Test our validator catches short content (less than 50 chars)
        agent = AgentSpecification(metadata=metadata, content="Short but valid content")
        errors = validator.validate_agent(agent)
        assert any("at least 50 characters" in e.message for e in errors)

        # Placeholder content - use pattern that matches our validator
        agent = AgentSpecification(metadata=metadata, content="TODO\n" + "x" * 50)
        errors = validator.validate_agent(agent)
        assert any("placeholder text" in e.message for e in errors)

    def test_security_validation(self, validator):
        """Test security validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )

        # Unsafe patterns
        unsafe_contents = [
            "__import__('os').system('rm -rf /')",
            "import subprocess; subprocess.call(['ls'])",
            "os.system('rm -rf /')",
            "<script>alert('xss')</script>",
        ]

        for content in unsafe_contents:
            agent = AgentSpecification(metadata=metadata, content=content + "x" * 50)
            errors = validator.validate_agent(agent)
            assert any("unsafe pattern" in e.message for e in errors)

        # Exposed secrets
        secret_contents = [
            "API_KEY='sk-1234567890abcdef' is required",
            "password: 'super-secret-password-123'",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...",
        ]

        for content in secret_contents:
            agent = AgentSpecification(metadata=metadata, content=content + "x" * 50)
            errors = validator.validate_agent(agent)
            assert any("exposed secrets" in e.message for e in errors)

    def test_tool_validation(self, validator, strict_validator):
        """Test tool validation."""
        # Invalid tool name should fail at Pydantic level
        with pytest.raises(ValueError, match="Tool names must be alphanumeric"):
            metadata = AgentMetadata(
                name="test-agent",
                display_name="Test",
                description="Test description for validation",
                category=AgentCategory.CUSTOM,
                tools=["claude", "Invalid-Tool!", "custom-tool"],
            )

        # Test strict mode with unknown tools
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
            tools=["claude", "custom-tool"],
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")

        # Normal mode - should pass
        errors = validator.validate_agent(agent)
        tool_errors = [e for e in errors if e.field == "tools"]
        assert len(tool_errors) == 0

        # Strict mode - should flag unknown tool
        errors = strict_validator.validate_agent(agent)
        tool_errors = [e for e in errors if e.field == "tools"]
        assert any("Unknown tool" in e.message for e in tool_errors)

        # Incompatible tools
        metadata.tools = ["cursor", "vscode"]  # Can't use both editors
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)
        assert any("Incompatible tools" in e.message for e in errors)

    def test_dependency_validation(self, validator):
        """Test dependency validation."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )

        # Invalid dependency name should fail at Pydantic level
        with pytest.raises(ValueError, match="Dependency names must be alphanumeric"):
            agent = AgentSpecification(
                metadata=metadata,
                content="Test content that is long enough",
                dependencies=["valid-dep", "Invalid-Dep!", "test-agent"],
            )

        # Test self-dependency
        agent = AgentSpecification(
            metadata=metadata,
            content="Test content that is long enough",
            dependencies=["test-agent"],  # Self dependency
        )
        errors = validator.validate_agent(agent, validate_dependencies=True)
        assert any("cannot depend on itself" in e.message for e in errors)

        # Validate with existing agents
        existing = {"valid-dep", "other-agent"}
        agent.dependencies = ["valid-dep", "missing-agent"]
        errors = validator.validate_agent(agent, existing_agents=existing)
        assert any("does not exist" in e.message for e in errors)

    def test_quality_validation_strict_mode(self, strict_validator):
        """Test quality validation in strict mode."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.ENGINEERING,
        )

        # Low quality content
        poor_content = "This is a basic agent. It does things. " * 5  # No structure
        agent = AgentSpecification(metadata=metadata, content=poor_content)
        errors = strict_validator.validate_agent(agent)

        quality_errors = [e for e in errors if "quality issues" in e.message]
        assert len(quality_errors) > 0
        assert any("missing section headers" in e.message for e in quality_errors)

        # Engineering agent with short content
        agent = AgentSpecification(
            metadata=metadata,
            content="Short engineering agent content that lacks detail",
        )
        errors = strict_validator.validate_agent(agent)
        assert any("should have more detailed content" in e.message for e in errors)

    def test_parameter_validation(self, validator):
        """Test model parameter validation."""
        # Parameters out of range should fail at Pydantic level
        with pytest.raises(ValueError, match="less than or equal to"):
            metadata = AgentMetadata(
                name="test-agent",
                display_name="Test",
                description="Test description for validation",
                category=AgentCategory.CUSTOM,
                temperature=3.0,  # Too high
                max_tokens=200000,  # Too high
            )

        # Test valid parameters
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
            temperature=1.5,
            max_tokens=50000,
        )
        agent = AgentSpecification(metadata=metadata, content="Test content that is long enough")
        errors = validator.validate_agent(agent)

        # Should have no parameter errors
        param_errors = [e for e in errors if e.field in ["temperature", "max_tokens"]]
        assert len(param_errors) == 0

    def test_batch_validation(self, validator):
        """Test validating multiple agents together."""
        agents = []

        # Agent 1 - valid
        metadata1 = AgentMetadata(
            name="agent1",
            display_name="Agent 1",
            description="First agent for batch validation",
            category=AgentCategory.CUSTOM,
        )
        agents.append(
            AgentSpecification(
                metadata=metadata1,
                content="Valid content for agent 1 with enough length to pass validation",
                dependencies=["agent2"],
            )
        )

        # Agent 2 - has errors (description too short)
        metadata2 = AgentMetadata(
            name="agent2",
            display_name="Agent 2",
            description="Short",  # Too short (less than 20 chars)
            category=AgentCategory.CUSTOM,
        )
        agents.append(
            AgentSpecification(
                metadata=metadata2,
                content="Valid content but has TODO placeholder text in it which should trigger validation error",
                dependencies=["agent3"],
            )
        )

        # Agent 3 - creates circular dependency
        metadata3 = AgentMetadata(
            name="agent3",
            display_name="Agent 3",
            description="Third agent for batch validation",
            category=AgentCategory.CUSTOM,
        )
        agents.append(
            AgentSpecification(
                metadata=metadata3,
                content="Valid content for agent 3 with enough length to pass basic validation",
                dependencies=["agent1"],  # Creates cycle: 1->2->3->1
            )
        )

        results = validator.validate_batch(agents, check_circular_deps=True)

        # Agent 1 should have circular dependency error
        assert "agent1" in results
        assert any("Circular dependency" in e.message for e in results["agent1"])

        # Agent 2 should have description error
        assert "agent2" in results
        assert any("at least 20 characters" in e.message for e in results["agent2"])

        # Agent 3 might have circular dependency error
        if "agent3" in results:
            assert any("Circular dependency" in e.message for e in results["agent3"])

    def test_suggest_fixes(self, validator):
        """Test fix suggestions for errors."""
        errors = [
            AgentValidationError("must start and end with alphanumeric", "name"),
            AgentValidationError("must be at least 50 characters", "content"),
            AgentValidationError("placeholder text", "content"),
            AgentValidationError("exposed secrets", "content"),
        ]

        suggestions = validator.suggest_fixes(errors)

        assert len(suggestions) == 4
        assert any("lowercase letters" in s for s in suggestions["must start and end with alphanumeric"])
        assert any("descriptive content" in s for s in suggestions["must be at least 50 characters"])
        assert any("Replace placeholder" in s for s in suggestions["placeholder text"])
        assert any("environment variables" in s for s in suggestions["exposed secrets"])

    def test_validation_error_attributes(self):
        """Test AgentValidationError attributes."""
        error = AgentValidationError(
            "Test error message",
            field="test_field",
            agent_name="test-agent",
        )

        assert error.message == "Test error message"
        assert error.field == "test_field"
        assert error.agent_name == "test-agent"
        assert str(error) == "Test error message"


class TestValidatorEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.fixture
    def validator(self):
        """Create validator for testing."""
        return AgentValidator()

    def test_empty_agent(self, validator):
        """Test validation of agent with minimal fields."""
        metadata = AgentMetadata(
            name="empty",
            display_name="Empty",
            description="x" * 20,  # Minimum valid
            category=AgentCategory.CUSTOM,
        )
        agent = AgentSpecification(
            metadata=metadata,
            content="x" * 50,  # Minimum valid
        )

        errors = validator.validate_agent(agent)
        assert errors == []  # Should be valid

    def test_special_characters_in_content(self, validator):
        """Test that special characters don't trigger false positives."""
        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )

        # Content with special chars but safe
        content = """
        # Agent with Special Characters

        Use `$$` for currency and ${variable} for templates.
        Code example: `result = a + b`
        Math: x² + y² = z²

        Don't use eval() or exec() in production!
        """

        agent = AgentSpecification(metadata=metadata, content=content)
        errors = validator.validate_agent(agent)

        # Should not have security errors for these patterns
        security_errors = [e for e in errors if "unsafe" in e.message or "secrets" in e.message]
        assert security_errors == []

    def test_url_validation_strict_mode(self):
        """Test URL validation in strict mode."""
        validator = AgentValidator(strict_mode=True)

        metadata = AgentMetadata(
            name="test-agent",
            display_name="Test",
            description="Test description for validation",
            category=AgentCategory.CUSTOM,
        )

        # Allowed URLs
        allowed_content = """
        See documentation at https://github.com/example/repo
        Check https://docs.python.org for details
        Answer on https://stackoverflow.com/questions/123
        """

        agent = AgentSpecification(metadata=metadata, content=allowed_content)
        errors = validator.validate_agent(agent)
        url_errors = [e for e in errors if "external URL" in e.message]
        assert url_errors == []

        # Disallowed URLs
        disallowed_content = """
        Send data to https://external-api.com/collect
        Download from https://sketchy-site.ru/malware
        """

        agent = AgentSpecification(metadata=metadata, content=disallowed_content)
        errors = validator.validate_agent(agent)
        url_errors = [e for e in errors if "external URL" in e.message]
        assert len(url_errors) >= 2
