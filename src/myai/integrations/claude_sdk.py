"""
Claude SDK integration for MyAI.

This module provides seamless integration with the Anthropic Python SDK,
enabling agent creation, refinement, and testing through direct API calls.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.prompt import Prompt

try:
    import anthropic
    from anthropic import Anthropic

    HAS_CLAUDE_SDK = True
except ImportError:
    HAS_CLAUDE_SDK = False
    anthropic = None
    Anthropic = None

from myai.models.agent import AgentSpecification


class ClaudeSDKIntegration:
    """Integration with Anthropic Python SDK for agent management."""

    def __init__(self):
        """Initialize Claude SDK integration."""
        self.client = None
        self.console = Console()
        if HAS_CLAUDE_SDK:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Anthropic client."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            msg = "ANTHROPIC_API_KEY environment variable not set"
            raise RuntimeError(msg)

        self.client = Anthropic(api_key=api_key)

    def create_agent_with_sdk(
        self,
        agent: AgentSpecification,
        interactive: bool = True,  # noqa: FBT001
    ) -> Dict[str, Any]:
        """
        Create/refine an agent using Anthropic Python SDK.

        Args:
            agent: Agent specification
            interactive: Whether to run in interactive mode

        Returns:
            Result from agent creation/refinement
        """
        if not HAS_CLAUDE_SDK or not self.client:
            msg = "Anthropic SDK not available. Install with: pip install anthropic"
            raise RuntimeError(msg)

        # Save initial agent file
        agent_file = self._save_agent_file(agent)

        if interactive:
            return self._interactive_agent_refinement(agent, agent_file)
        else:
            return self._automatic_agent_refinement(agent, agent_file)

    def _save_agent_file(self, agent: AgentSpecification) -> Path:
        """Save agent to a file for editing."""
        agent_file = Path.home() / ".myai" / "temp" / f"{agent.metadata.name}.md"
        agent_file.parent.mkdir(parents=True, exist_ok=True)
        agent_file.write_text(agent.content)
        return agent_file

    def _interactive_agent_refinement(
        self,
        agent: AgentSpecification,
        agent_file: Path,
    ) -> Dict[str, Any]:
        """Interactively refine an agent using the SDK."""
        self.console.print("\n[bold]🤖 Agent Refinement Assistant[/bold]")
        self.console.print(f"Working on agent: [cyan]{agent.metadata.display_name}[/cyan]\n")

        conversation_history = []
        max_iterations = 10

        for iteration in range(max_iterations):
            # Get user input
            if iteration == 0:
                user_input = Prompt.ask(
                    "\n[yellow]What would you like to improve about this agent?[/yellow]\n"
                    "(Type 'done' to finish, 'show' to see current content)"
                )
            else:
                user_input = Prompt.ask("\n[yellow]What else would you like to change?[/yellow]")

            if user_input.lower() == "done":
                break
            elif user_input.lower() == "show":
                self.console.print("\n[bold]Current Agent Content:[/bold]")
                self.console.print(agent.content)
                continue

            # Prepare the message for Claude
            messages = self._build_refinement_messages(agent, user_input, conversation_history)

            # Call Claude API
            self.console.print("\n[dim]🤔 Thinking...[/dim]")
            try:
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4096,
                    temperature=0.7,
                    messages=messages,
                )

                # Extract the refined content
                refined_content = response.content[0].text

                # Update the agent
                agent.content = refined_content
                agent_file.write_text(refined_content)

                # Show the changes
                self.console.print("\n[green]✅ Agent updated![/green]")
                self.console.print(f"[dim]Changes saved to: {agent_file}[/dim]")

                # Add to conversation history
                conversation_history.append(
                    {
                        "user": user_input,
                        "assistant": refined_content,
                    }
                )

            except Exception as e:
                self.console.print(f"\n[red]Error calling Claude API: {e}[/red]")
                break

        return {
            "status": "completed",
            "agent_file": str(agent_file),
            "iterations": len(conversation_history),
        }

    def _build_refinement_messages(
        self,
        agent: AgentSpecification,
        user_input: str,
        conversation_history: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Build messages for the refinement conversation."""
        system_prompt = (
            "You are an AI agent refinement assistant. "
            "Your job is to help users improve and refine their AI agent specifications.\n\n"
            "When refining agents:\n"
            "1. Maintain the agent's core purpose and identity\n"
            "2. Improve clarity and specificity of instructions\n"
            "3. Add helpful examples where appropriate\n"
            "4. Ensure the agent has clear guidelines for its behavior\n"
            "5. Keep the format compatible with Claude Code and Cursor\n\n"
            "Return ONLY the refined agent content (no explanations or commentary)."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Add initial context
        messages.append(
            {
                "role": "user",
                "content": f"""I have an AI agent with these specifications:

Name: {agent.metadata.name}
Display Name: {agent.metadata.display_name}
Category: {agent.metadata.category.value}
Description: {agent.metadata.description}

Current agent content:
{agent.content}

User request: {user_input}

Please provide the refined agent content.""",
            }
        )

        # Add conversation history if any
        for hist in conversation_history:
            messages.append({"role": "assistant", "content": hist["assistant"]})
            messages.append({"role": "user", "content": hist["user"]})

        return messages

    def _automatic_agent_refinement(
        self,
        agent: AgentSpecification,
        agent_file: Path,
    ) -> Dict[str, Any]:
        """Automatically refine an agent without interaction."""
        self.console.print("\n[bold]🤖 Automatic Agent Refinement[/bold]")
        self.console.print(f"Refining agent: [cyan]{agent.metadata.display_name}[/cyan]\n")

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an AI agent refinement assistant. Improve the given agent specification to be more"
                        " clear, specific, and effective."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""Please refine this AI agent specification:

{agent.content}

Make it more specific, add clear guidelines, and ensure it follows best practices for AI agents.""",
                },
            ]

            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.7,
                messages=messages,
            )

            refined_content = response.content[0].text
            agent.content = refined_content
            agent_file.write_text(refined_content)

            self.console.print("[green]✅ Agent refined successfully![/green]")

            return {
                "status": "completed",
                "agent_file": str(agent_file),
            }

        except Exception as e:
            self.console.print(f"[red]Error during automatic refinement: {e}[/red]")
            return {
                "status": "error",
                "error": str(e),
            }

    def test_agent(
        self,
        agent: AgentSpecification,
        test_prompt: str,
    ) -> Dict[str, Any]:
        """
        Test an agent with a specific prompt using the SDK.

        Args:
            agent: Agent specification
            test_prompt: Test prompt to run

        Returns:
            Test results
        """
        if not HAS_CLAUDE_SDK or not self.client:
            msg = "Anthropic SDK not available. Install with: pip install anthropic"
            raise RuntimeError(msg)

        try:
            # Prepare messages with agent as system prompt
            messages = [{"role": "system", "content": agent.content}, {"role": "user", "content": test_prompt}]

            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.7,
                messages=messages,
            )

            # Extract response content
            result_text = response.content[0].text

            # Calculate approximate cost (rough estimate)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            # Rough pricing: $3/1M input, $15/1M output for Claude 3.5 Sonnet
            estimated_cost = (input_tokens * 0.000003) + (output_tokens * 0.000015)

            return {
                "status": "completed",
                "result": result_text,
                "cost": f"${estimated_cost:.4f}",
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


def get_claude_sdk_integration() -> ClaudeSDKIntegration:
    """Get Claude SDK integration instance."""
    return ClaudeSDKIntegration()
