"""
Unit tests for Claude SDK integration.
"""

from unittest.mock import Mock, patch

import pytest

from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification


class TestClaudeSDKIntegration:
    """Test Claude SDK integration functionality."""

    @patch("os.environ.get")
    def test_check_anthropic_api_key(self, mock_env_get):
        """Test checking for Anthropic API key."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        # Test successful check
        mock_env_get.return_value = "test-api-key"
        with patch("myai.integrations.claude_sdk.Anthropic"):
            integration = ClaudeSDKIntegration()
            assert integration is not None

        # Test missing API key
        mock_env_get.return_value = None
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY environment variable not set"):
            ClaudeSDKIntegration()

    def test_save_agent_file(self):
        """Test saving agent to file."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        # Create test agent
        agent = AgentSpecification(
            metadata=AgentMetadata(
                name="test-agent",
                display_name="Test Agent",
                description="A test agent",
                category=AgentCategory.ENGINEERING,
            ),
            content="Test agent content",
        )

        with patch("os.environ.get", return_value="test-key"):
            with patch("myai.integrations.claude_sdk.Anthropic"):
                integration = ClaudeSDKIntegration()

                # Mock file operations
                with patch("pathlib.Path.mkdir") as mock_mkdir:
                    with patch("pathlib.Path.write_text") as mock_write:
                        agent_file = integration._save_agent_file(agent)

                        assert str(agent_file).endswith("test-agent.md")
                        mock_mkdir.assert_called_once()
                        mock_write.assert_called_with("Test agent content")

    def test_anthropic_sdk_integration(self):
        """Test basic Anthropic SDK integration."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        with patch("os.environ.get", return_value="test-key"):
            with patch("myai.integrations.claude_sdk.Anthropic") as mock_anthropic:
                # Mock client
                mock_client = Mock()
                mock_anthropic.return_value = mock_client

                integration = ClaudeSDKIntegration()
                assert integration.client == mock_client

    def test_test_agent(self):
        """Test agent testing functionality."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        # Create agent with issues
        agent = AgentSpecification(
            metadata=AgentMetadata(
                name="test-agent",
                display_name="Test Agent",
                description="A test agent",
                category=AgentCategory.ENGINEERING,
                tools=["InvalidTool", "Task"],
            ),
            content="Short content",
        )

        with patch("os.environ.get", return_value="test-key"):
            with patch("myai.integrations.claude_sdk.Anthropic") as mock_anthropic:
                # Mock client and response
                mock_client = Mock()
                mock_response = Mock()
                mock_response.content = [Mock(text="Test response")]
                mock_response.usage.input_tokens = 100
                mock_response.usage.output_tokens = 50
                mock_client.messages.create.return_value = mock_response
                mock_anthropic.return_value = mock_client

                integration = ClaudeSDKIntegration()
                result = integration.test_agent(agent, "Test prompt")

                assert result["status"] == "completed"
                assert result["result"] == "Test response"
                assert "$" in result["cost"]
                assert result["usage"]["total_tokens"] == 150

    @patch("os.environ.get")
    def test_create_agent_with_sdk_no_api_key(self, mock_env_get):  # noqa: ARG002
        """Test create_agent_with_sdk when API key is missing."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        agent = AgentSpecification(
            metadata=AgentMetadata(
                name="test-agent",
                display_name="Test Agent",
                description="A test agent",
                category=AgentCategory.ENGINEERING,
            ),
            content="Test content",
        )

        # When HAS_CLAUDE_SDK is False
        with patch("myai.integrations.claude_sdk.HAS_CLAUDE_SDK", False):
            with patch("myai.integrations.claude_sdk.Console"):
                integration = ClaudeSDKIntegration()
                with pytest.raises(RuntimeError, match="Anthropic SDK not available"):
                    integration.create_agent_with_sdk(agent)

    def test_build_refinement_messages(self):
        """Test building refinement messages."""
        from myai.integrations.claude_sdk import ClaudeSDKIntegration

        agent = AgentSpecification(
            metadata=AgentMetadata(
                name="test-agent",
                display_name="Test Agent",
                description="A test agent",
                category=AgentCategory.ENGINEERING,
            ),
            content="Test content",
        )

        with patch("os.environ.get", return_value="test-key"):
            with patch("myai.integrations.claude_sdk.Anthropic"):
                integration = ClaudeSDKIntegration()
                messages = integration._build_refinement_messages(agent, "Make it better", [])

                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert "refinement assistant" in messages[0]["content"]
                assert messages[1]["role"] == "user"
                assert "test-agent" in messages[1]["content"]
                assert "Make it better" in messages[1]["content"]
