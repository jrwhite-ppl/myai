"""
Tests for the agent test-activation command.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from myai.commands.agent_cli import app


class TestAgentTestActivation:
    """Test agent test-activation command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

        # Create mock agents
        self.mock_code_reviewer = MagicMock()
        self.mock_code_reviewer.metadata.name = "code-reviewer"
        self.mock_code_reviewer.metadata.display_name = "Code Reviewer"
        self.mock_code_reviewer.metadata.description = "Expert code review specialist"
        self.mock_code_reviewer.metadata.tags = ["review", "code-quality"]
        self.mock_code_reviewer.metadata.tools = ["Read", "Write"]
        self.mock_code_reviewer.metadata.category = MagicMock()
        self.mock_code_reviewer.metadata.category.value = "engineering"
        self.mock_code_reviewer.content = "I activate when you need code reviewed"

        self.mock_python_expert = MagicMock()
        self.mock_python_expert.metadata.name = "python-expert"
        self.mock_python_expert.metadata.display_name = "Python Expert"
        self.mock_python_expert.metadata.description = "Python development specialist"
        self.mock_python_expert.metadata.tags = ["python", "development"]
        self.mock_python_expert.metadata.tools = ["Read", "Write", "Edit"]
        self.mock_python_expert.metadata.category = MagicMock()
        self.mock_python_expert.metadata.category.value = "engineering"
        self.mock_python_expert.content = "I help with Python development"

        self.mock_security_analyst = MagicMock()
        self.mock_security_analyst.metadata.name = "security-analyst"
        self.mock_security_analyst.metadata.display_name = "Security Analyst"
        self.mock_security_analyst.metadata.description = "Security and vulnerability analysis"
        self.mock_security_analyst.metadata.tags = ["security", "vulnerability"]
        self.mock_security_analyst.metadata.tools = ["Read", "Grep"]
        self.mock_security_analyst.metadata.category = MagicMock()
        self.mock_security_analyst.metadata.category.value = "security"
        self.mock_security_analyst.content = "I analyze security vulnerabilities"

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_exact_match(self, mock_registry):
        """Test activation with exact agent name match."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test exact match
        result = self.runner.invoke(app, ["test-activation", "hey code reviewer"])

        assert result.exit_code == 0
        assert "Code Reviewer (code-reviewer) - 100% match" in result.stdout
        assert "1 agent(s) would likely activate" in result.stdout

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_keyword_match(self, mock_registry):
        """Test activation with keyword matching."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test keyword match with lower threshold
        result = self.runner.invoke(app, ["test-activation", "help with Python code", "--threshold", "30"])

        assert result.exit_code == 0
        # Python expert should match
        assert "Python Expert" in result.stdout
        assert "python" in result.stdout.lower()

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_no_match(self, mock_registry):
        """Test activation with no matches."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test no match
        result = self.runner.invoke(app, ["test-activation", "help with cooking recipes"])

        assert result.exit_code == 0
        assert "No agents would activate" in result.stdout
        assert "Try using more specific keywords" in result.stdout

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_show_all(self, mock_registry):
        """Test activation with --all flag."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test with --all flag
        result = self.runner.invoke(app, ["test-activation", "analyze", "--all"])

        assert result.exit_code == 0
        # All agents should be shown, including low scores
        assert "Code Reviewer" in result.stdout
        assert "Python Expert" in result.stdout
        assert "Security Analyst" in result.stdout

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_custom_threshold(self, mock_registry):
        """Test activation with custom threshold."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test with low threshold
        result = self.runner.invoke(app, ["test-activation", "code", "--threshold", "20"])

        assert result.exit_code == 0
        # More agents should match with lower threshold
        assert "Code Reviewer" in result.stdout

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_multiple_matches(self, mock_registry):
        """Test activation with multiple matching agents."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [
            self.mock_code_reviewer,
            self.mock_python_expert,
            self.mock_security_analyst,
        ]
        mock_registry.return_value = registry

        # Test phrase that matches multiple agents
        result = self.runner.invoke(app, ["test-activation", "review Python code for security"])

        assert result.exit_code == 0
        # Multiple agents should match
        output = result.stdout.lower()
        assert "match" in output  # Should show match scores

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_shows_examples(self, mock_registry):
        """Test that activation shows example phrases."""
        # Setup mock registry
        registry = MagicMock()
        registry.list_agents.return_value = [self.mock_code_reviewer]
        mock_registry.return_value = registry

        # Test that examples are shown
        result = self.runner.invoke(app, ["test-activation", "code review"])

        assert result.exit_code == 0
        assert "Try:" in result.stdout
        assert "Hey Code Reviewer" in result.stdout

    @patch("myai.commands.agent_cli.get_agent_registry")
    def test_test_activation_error_handling(self, mock_registry):
        """Test error handling in test-activation."""
        # Setup mock registry to raise an error
        mock_registry.side_effect = RuntimeError("Registry error")

        # Test error handling
        result = self.runner.invoke(app, ["test-activation", "test phrase"])

        assert result.exit_code == 1
        assert "Error testing activation" in result.stdout
