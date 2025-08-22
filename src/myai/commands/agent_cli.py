"""
Agent management CLI commands.

This module provides CLI commands for managing AI agents,
including listing, creating, editing, and managing agents.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from myai.agent.manager import AgentManager
from myai.agent.registry import get_agent_registry
from myai.agent.templates import get_template_registry
from myai.agent.validator import AgentValidator
from myai.cli.formatters import get_formatter
from myai.cli.state import AppState
from myai.config.manager import get_config_manager
from myai.models.agent import AgentCategory

# Constants
MAX_DESCRIPTION_LENGTH = 50


def _resolve_agent_name(registry, name_or_display: str) -> Optional[str]:
    """Resolve agent name from either internal name or display name.

    Args:
        registry: Agent registry instance
        name_or_display: Either the agent's internal name or display name

    Returns:
        The resolved internal agent name or None if not found
    """
    resolved_name = registry.resolve_agent_name(name_or_display)
    if not resolved_name:
        console.print(f"[red]Agent '{name_or_display}' not found[/red]")
    return resolved_name


# Create agent command group
app = typer.Typer(help="""🤖 Agent management commands

Common workflows:

1. Create a new agent:
   myai agent create my-expert --category engineering --interactive

2. List all available agents:
   myai agent list
   myai agent list --category custom  # Show only custom agents

3. Enable an agent for your project:
   myai agent enable my-expert

4. Test an agent with Claude SDK:
   myai agent test my-expert "Explain how to implement error handling"

5. Show agent details:
   myai agent show my-expert

6. Disable an agent:
   myai agent disable my-expert

Tips:
- Use --interactive flag when creating agents to refine them with Claude
- Enabled agents are automatically synced to Claude Code and Cursor
- Custom agents persist across MyAI updates
- Use 'myai agent enable <name>' to enable an agent
- Use 'myai agent disable <name>' to disable an agent
- Use 'myai agent edit <name>' to edit an agent
- Use 'myai agent delete <name>' to delete an agent
""")


def _create_agent_files(agent, *, global_scope=False):
    """Create integration files for an enabled agent.

    Args:
        agent: Agent object to create files for
        global_scope: If True, create global files. If False, create project-level files.
    """
    agent_name = agent.metadata.name

    if global_scope:
        # Create global Claude file
        claude_dir = Path.home() / ".claude" / "agents"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_file = claude_dir / f"{agent_name}.md"
        if not claude_file.exists():
            claude_file.write_text(agent.content)
    else:
        # Create project Claude file with actual content
        project_claude_dir = Path.cwd() / ".claude" / "agents"
        project_claude_dir.mkdir(parents=True, exist_ok=True)
        project_claude_file = project_claude_dir / f"{agent_name}.md"
        if not project_claude_file.exists():
            # Write the actual agent content for Claude
            project_claude_file.write_text(agent.content)

        # Create project Cursor file with actual content
        project_cursor_dir = Path.cwd() / ".cursor" / "rules"
        project_cursor_dir.mkdir(parents=True, exist_ok=True)
        cursor_file = project_cursor_dir / f"{agent_name}.mdc"
        if not cursor_file.exists():
            # Write the actual agent content for Cursor
            cursor_file.write_text(agent.content)


def _remove_agent_files(agent_name, *, global_scope=False):
    """Remove integration files for a disabled agent.

    Args:
        agent_name: Name of agent to remove files for
        global_scope: If True, remove global files. If False, remove project-level files.
    """
    if global_scope:
        # Remove global Claude file
        claude_file = Path.home() / ".claude" / "agents" / f"{agent_name}.md"
        if claude_file.exists():
            claude_file.unlink()
    else:
        # Remove project Claude file
        project_claude_file = Path.cwd() / ".claude" / "agents" / f"{agent_name}.md"
        if project_claude_file.exists():
            project_claude_file.unlink()

        # Remove project Cursor file
        cursor_file = Path.cwd() / ".cursor" / "rules" / f"{agent_name}.mdc"
        if cursor_file.exists():
            cursor_file.unlink()


console = Console()


def _update_agents_md_file() -> None:
    """Update the AGENTS.md file with the current enabled agents."""
    from pathlib import Path

    from myai.agents_md import AgentsMdManager

    try:
        # Check if we're in a project with AGENTS.md
        root_agents_md = Path.cwd() / "AGENTS.md"
        if not root_agents_md.exists():
            return

        # Use the AgentsMdManager to update just the agents section
        manager = AgentsMdManager(Path.cwd())

        # Read current content to check if it's a MyAI file
        current_content = root_agents_md.read_text(encoding="utf-8")

        # Check if this is a MyAI-generated file (has our markers or legacy format)
        if "MYAI:AGENTS" not in current_content and "Generated by MyAI" not in current_content:
            return  # Don't modify user-created AGENTS.md files

        # Update only the agents section, preserving user content
        manager.update_agents_section(root_agents_md)

    except ValueError as e:
        # User-friendly error for broken markers
        console.print("\n[yellow]⚠️  Could not update AGENTS.md automatically:[/yellow]")
        console.print(f"[yellow]{e!s}[/yellow]")
        console.print("\n[dim]The agent has been enabled, but AGENTS.md was not updated.[/dim]")
    except Exception:  # noqa: S110
        # Silently fail for other errors - AGENTS.md updates are a nice-to-have feature
        pass


@app.command()
def show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to show"),
    full: bool = typer.Option(False, "--full", help="Show complete agent content"),  # noqa: FBT001
    content: bool = typer.Option(  # noqa: FBT001
        False, "--content", help="Show agent content (deprecated: use --full)"
    ),
):
    """Show detailed information about an agent.

    Displays agent metadata and a content preview by default.
    Use --full to see the complete agent content.

    Examples:
      myai agent show python-expert       # Show overview with preview
      myai agent show python-expert --full # Show complete content

    Related commands:
      myai agent list                     # See all agents
      myai agent edit <name>              # Edit this agent
      myai agent enable <name>            # Enable this agent
    """
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # Resolve agent name (could be display name)
        resolved_name = _resolve_agent_name(registry, name)
        if not resolved_name:
            return

        agent = registry.get_agent(resolved_name)
        if not agent:
            # This should never happen if resolve_agent_name succeeded
            console.print(f"[red]Internal error: Could not load agent '{name}'[/red]")
            return

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            agent_data = agent.model_dump()
            formatter.format(agent_data)
        else:
            # Create detailed display
            metadata = agent.metadata

            # Metadata panel
            metadata_text = Text()
            metadata_text.append("Name: ", style="bold")
            metadata_text.append(f"{metadata.name}\n")
            metadata_text.append("Display Name: ", style="bold")
            metadata_text.append(f"{metadata.display_name}\n")
            metadata_text.append("Description: ", style="bold")
            metadata_text.append(f"{metadata.description}\n")
            metadata_text.append("Category: ", style="bold")
            metadata_text.append(f"{metadata.category.value}\n")
            metadata_text.append("Version: ", style="bold")
            metadata_text.append(f"{metadata.version}\n")
            metadata_text.append("Tools: ", style="bold")
            metadata_text.append(f"{', '.join(metadata.tools)}\n")
            metadata_text.append("Tags: ", style="bold")
            metadata_text.append(f"{', '.join(metadata.tags)}")

            # Add custom agent information
            if hasattr(agent, "is_custom") and agent.is_custom:
                metadata_text.append("\n\n[magenta]Custom Agent Information:[/magenta]\n")
                metadata_text.append("Source: ", style="bold")
                source = getattr(agent, "source", "unknown")
                metadata_text.append(f"{source}\n")
                if hasattr(agent, "external_path") and agent.external_path:
                    metadata_text.append("External Path: ", style="bold")
                    metadata_text.append(f"{agent.external_path}")

            panel = Panel(
                metadata_text,
                title=f"🤖 Agent: {metadata.display_name}",
                border_style="blue",
            )
            console.print(panel)

            # Always show content preview or full content
            show_full_content = full or content  # Support legacy --content flag

            if show_full_content:
                # Show complete content
                content_panel = Panel(
                    agent.content,
                    title="📝 Complete Agent Content",
                    border_style="green",
                )
                console.print(content_panel)
            else:
                # Show content preview (first 300 characters)
                preview_content = agent.content
                preview_length = 300
                if len(preview_content) > preview_length:
                    preview_content = preview_content[:preview_length] + "..."

                preview_panel = Panel(
                    f"{preview_content}\n\n[dim]Use --full to see complete content[/dim]",
                    title="📝 Content Preview",
                    border_style="cyan",
                )
                console.print(preview_panel)

    except Exception as e:
        console.print(f"[red]Error showing agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def enable(
    ctx: typer.Context,
    names: list[str] = typer.Argument(..., help="Agent name(s) to enable"),
    global_scope: bool = typer.Option(  # noqa: FBT001
        False, "--global", help="Enable agent(s) globally instead of project-level"
    ),
):
    """Enable one or more agents.

    Examples:
        # Enable a single agent for this project
        myai agent enable python-expert

        # Enable multiple agents
        myai agent enable python-expert security-analyst devops-engineer

        # Enable globally (for all projects)
        myai agent enable python-expert --global

    When enabled:
    - Creates .claude/agents/<name>.md for Claude Code
    - Creates .cursor/rules/<name>.mdc for Cursor
    - Agent becomes active in your IDE integrations
    """
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        registry = get_agent_registry()

        enabled_count = 0
        not_found = []
        enabled_agents = []

        for name in names:
            # Resolve agent name (could be display name)
            resolved_name = registry.resolve_agent_name(name)
            if not resolved_name:
                not_found.append(name)
                continue

            # Get the agent
            agent = registry.get_agent(resolved_name)
            if not agent:
                # This should never happen if resolve_agent_name succeeded
                continue

            if global_scope:
                # Handle global enablement
                if resolved_name in config.agents.global_disabled:
                    config.agents.global_disabled.remove(resolved_name)
                if resolved_name not in config.agents.global_enabled:
                    config.agents.global_enabled.append(resolved_name)
                    enabled_agents.append(agent)
                    enabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already enabled globally[/yellow]")
            else:
                # Handle project-level enablement
                if resolved_name in config.agents.disabled:
                    config.agents.disabled.remove(resolved_name)
                if resolved_name not in config.agents.enabled:
                    config.agents.enabled.append(resolved_name)
                    enabled_agents.append(agent)
                    enabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already enabled for this project[/yellow]")

        if enabled_count > 0:
            # Save config based on scope
            if global_scope:
                config_manager.set_config_value("agents.global_enabled", getattr(config.agents, "global_enabled", []))
                config_manager.set_config_value("agents.global_disabled", getattr(config.agents, "global_disabled", []))
                scope_text = "globally"
            else:
                config_manager.set_config_value("agents.enabled", config.agents.enabled)
                config_manager.set_config_value("agents.disabled", config.agents.disabled)
                scope_text = "for this project"

            # Create integration files for newly enabled agents
            for agent in enabled_agents:
                try:
                    _create_agent_files(agent, global_scope=global_scope)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to create files for {agent.metadata.name}: {e}[/yellow]")

            console.print(f"✅ Enabled {enabled_count} agent(s) {scope_text}")

            # Show what was created
            for agent in enabled_agents:
                agent_name = agent.metadata.name
                if global_scope:
                    console.print(
                        f"  [green]✓[/green] Created ~/.claude/agents/{agent_name}.md [dim](global Claude access)[/dim]"
                    )
                else:
                    console.print(
                        f"  [green]✓[/green] Created .claude/agents/{agent_name}.md [dim](project Claude access)[/dim]"
                    )
                    console.print(
                        f"  [green]✓[/green] Created .cursor/rules/{agent_name}.mdc [dim](Cursor IDE rules)[/dim]"
                    )

            # Show next steps
            console.print("\n[bold]Next steps:[/bold]")
            if global_scope:
                console.print("  • Agents are now available in Claude Code globally")
                console.print(
                    f"  • Use 'myai agent enable {enabled_agents[0].metadata.name if enabled_agents else '<name>'}' to"
                    " enable for specific projects"
                )
            else:
                console.print("  • Agents are now active in Claude Code and Cursor for this project")
                console.print("  • Check AGENTS.md for project guidelines")
                console.print("  • Use 'myai agent show <name>' to see agent details")

            # Update AGENTS.md for project-level changes
            if not global_scope:
                _update_agents_md_file()

        if not_found:
            console.print(f"[red]❌ Agent(s) not found: {', '.join(not_found)}[/red]")

    except Exception as e:
        console.print(f"[red]Error enabling agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def disable(
    ctx: typer.Context,
    names: list[str] = typer.Argument(..., help="Agent name(s) to disable"),
    global_scope: bool = typer.Option(  # noqa: FBT001
        False, "--global", help="Disable agent(s) globally instead of project-level"
    ),
):
    """Disable one or more agents."""
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        registry = get_agent_registry()

        disabled_count = 0
        not_found = []
        disabled_agents = []

        for name in names:
            # Resolve agent name (could be display name)
            resolved_name = registry.resolve_agent_name(name)
            if not resolved_name:
                not_found.append(name)
                continue

            if global_scope:
                # Handle global disabling
                if resolved_name in getattr(config.agents, "global_enabled", []):
                    config.agents.global_enabled.remove(resolved_name)
                if resolved_name not in getattr(config.agents, "global_disabled", []):
                    if not hasattr(config.agents, "global_disabled"):
                        config.agents.global_disabled = []
                    config.agents.global_disabled.append(resolved_name)
                    disabled_agents.append(resolved_name)
                    disabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already disabled globally[/yellow]")
            else:
                # Handle project-level disabling
                if resolved_name in config.agents.enabled:
                    config.agents.enabled.remove(resolved_name)
                if resolved_name not in config.agents.disabled:
                    config.agents.disabled.append(resolved_name)
                    disabled_agents.append(resolved_name)
                    disabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already disabled for this project[/yellow]")

        if disabled_count > 0:
            # Save config based on scope
            if global_scope:
                config_manager.set_config_value("agents.global_enabled", getattr(config.agents, "global_enabled", []))
                config_manager.set_config_value("agents.global_disabled", getattr(config.agents, "global_disabled", []))
                scope_text = "globally"
            else:
                config_manager.set_config_value("agents.enabled", config.agents.enabled)
                config_manager.set_config_value("agents.disabled", config.agents.disabled)
                scope_text = "for this project"

            # Remove integration files for newly disabled agents
            for agent_name in disabled_agents:
                try:
                    _remove_agent_files(agent_name, global_scope=global_scope)
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to remove files for {agent_name}: {e}[/yellow]")

            console.print(f"✅ Disabled {disabled_count} agent(s) {scope_text}")

            # Show what was removed
            for agent_name in disabled_agents:
                if global_scope:
                    console.print(
                        f"  [red]✗[/red] Removed ~/.claude/agents/{agent_name}.md [dim](no longer globally"
                        " available)[/dim]"
                    )
                else:
                    console.print(
                        f"  [red]✗[/red] Removed .claude/agents/{agent_name}.md [dim](no longer in project)[/dim]"
                    )
                    console.print(
                        f"  [red]✗[/red] Removed .cursor/rules/{agent_name}.mdc [dim](no longer in Cursor)[/dim]"
                    )

            # Show next steps
            console.print("\n[bold]Agent(s) are now inactive.[/bold]")
            if global_scope:
                console.print("  • No longer available in Claude Code globally")
                console.print(
                    f"  • Use 'myai agent enable {disabled_agents[0] if disabled_agents else '<name>'} --global' to"
                    " re-enable globally"
                )
            else:
                console.print("  • No longer active in Claude Code and Cursor for this project")
                console.print(
                    f"  • Use 'myai agent enable {disabled_agents[0] if disabled_agents else '<name>'}' to re-enable"
                )
                console.print("  • AGENTS.md updated to reflect changes")

            # Update AGENTS.md for project-level changes
            if not global_scope:
                _update_agents_md_file()

        if not_found:
            console.print(f"[red]❌ Agent(s) not found: {', '.join(not_found)}[/red]")

    except Exception as e:
        console.print(f"[red]Error disabling agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name (kebab-case, e.g., 'python-expert')"),
    display_name: Optional[str] = typer.Option(
        None, "--display-name", help="Agent display name (defaults to formatted name)"
    ),
    category: AgentCategory = typer.Option(AgentCategory.CUSTOM, "--category", "-c", help="Agent category"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template to use"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive creation mode"),  # noqa: FBT001
    use_claude_sdk: bool = typer.Option(  # noqa: FBT001
        True, "--claude-sdk/--no-claude-sdk", help="Use Claude SDK for creation"
    ),
):
    """Create a new agent.

    Examples:
        # Create a basic agent
        myai agent create my-expert --category engineering

        # Create with interactive Claude SDK refinement
        myai agent create my-expert --interactive

        # Create without Claude SDK
        myai agent create my-expert --no-claude-sdk

        # Create from a template
        myai agent create my-expert --template python-expert

    The agent will be:
    - Stored in ~/.myai/agents/custom/
    - Available immediately in 'myai agent list'
    - Ready to enable for your projects
    """
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Creating agent '{name}'...[/dim]")

    try:
        manager = AgentManager()

        if template:
            # Create from template
            template_registry = get_template_registry()
            agent_template = template_registry.get_template(template)

            if not agent_template:
                console.print(f"[red]Template '{template}' not found[/red]")
                return

            # TODO: Implement template variable collection in interactive mode
            agent = agent_template.render(
                name=name,
                display_name=display_name or name.replace("-", " ").title(),
            )

            registry = get_agent_registry()
            registry.register_agent(agent, persist=True)
            console.print(f"✅ Created agent '{name}' from template '{template}'")
        else:
            # Create basic agent
            description = "Custom agent created via CLI"
            if interactive:
                description = typer.prompt("Agent description", default=description)

            # Default display_name to formatted version of name if not provided
            if not display_name:
                display_name = name.replace("-", " ").title()

            agent = manager.create_agent_basic(
                name=name,
                display_name=display_name,
                description=description,
                category=category,
            )

            console.print(f"✅ Created agent '{name}'")

        # Use Claude SDK for enhanced agent creation
        should_use_sdk = False
        if use_claude_sdk:
            if interactive:
                should_use_sdk = True
            else:
                try:
                    should_use_sdk = typer.confirm("Would you like to refine this agent with Claude?")
                except Exception:
                    # In non-interactive environments, skip SDK
                    console.print("[dim]Skipping Claude SDK refinement in non-interactive mode[/dim]")
                    should_use_sdk = False

        if should_use_sdk:
            try:
                from myai.integrations.claude_sdk import get_claude_sdk_integration

                console.print("\n🚀 Launching Claude SDK for agent refinement...")
                console.print("[dim]This will open an interactive session to help you perfect your agent.[/dim]\n")

                sdk = get_claude_sdk_integration()

                # Run the SDK integration
                result = sdk.create_agent_with_sdk(agent, interactive=True)

                if result["status"] == "completed":
                    console.print(f"\n✅ Agent '{name}' refined successfully with Claude SDK!")
                    console.print(f"[dim]Agent file: {result.get('agent_file', 'N/A')}[/dim]")
                else:
                    console.print("\n⚠️  Claude SDK session ended")

            except Exception as e:
                import traceback

                error_msg = str(e).lower()

                if "anthropic_api_key" in error_msg or "api key" in error_msg:
                    console.print("\n[yellow]⚠️  Claude API Key Required[/yellow]")
                    console.print("[bold]To use Claude SDK for agent refinement:[/bold]")
                    console.print("1. Get an API key from: [cyan]https://console.anthropic.com/[/cyan]")
                    console.print("2. Set your API key:")
                    console.print("   [cyan]export ANTHROPIC_API_KEY='your-key-here'[/cyan]")
                    console.print("3. Or add to your shell profile (~/.bashrc or ~/.zshrc)")
                    console.print("\n[dim]Your agent was still created successfully without SDK refinement.[/dim]")
                elif "not found" in error_msg or "import" in error_msg:
                    console.print("\n[yellow]⚠️  Claude SDK Dependencies Missing[/yellow]")
                    console.print("[bold]To install required dependencies:[/bold]")
                    console.print("   [cyan]pip install anthropic[/cyan]")
                    console.print("\n[dim]Your agent was still created successfully without SDK refinement.[/dim]")
                else:
                    console.print(f"\n[yellow]Claude SDK error: {e}[/yellow]")
                    if state.is_debug():
                        console.print(f"[dim]{traceback.format_exc()}[/dim]")
                    console.print("\n[dim]Your agent was still created successfully without SDK refinement.[/dim]")

    except Exception as e:
        console.print(f"[red]Error creating agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),  # noqa: FBT001
):
    """Delete an agent and all its associated files."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # Resolve agent name (could be display name)
        resolved_name = _resolve_agent_name(registry, name)
        if not resolved_name:
            return

        agent = registry.get_agent(resolved_name)
        if not agent:
            # This should never happen if resolve_agent_name succeeded
            console.print(f"[red]Internal error: Could not load agent '{name}'[/red]")
            return

        # Allow deletion of any agent

        # Show what will be deleted
        console.print("\n[bold]The following will be deleted:[/bold]")
        console.print(f"  • Agent definition: {agent.metadata.name}")
        console.print(f"  • Display name: {agent.metadata.display_name}")
        console.print(f"  • Category: {agent.metadata.category.value}")

        # Check for integration files
        files_to_delete = []

        # Check storage location (where agent definition is stored)
        # First check if agent has a file_path attribute
        if hasattr(agent, "file_path") and agent.file_path:
            source_file = Path(agent.file_path)
            if source_file.exists():
                # Determine if it's a default agent from package
                if ".myai" in str(source_file):
                    files_to_delete.append(("Agent storage", source_file))
                else:
                    # Default agents from package shouldn't be deleted from package
                    console.print(f"[dim]Note: Default agent source at {source_file} will not be deleted[/dim]")
        else:
            # Check JSON storage locations
            storage_path = Path.home() / ".myai" / "agents"
            category_dir = agent.metadata.category.value

            # Check JSON file
            agent_storage_file = storage_path / category_dir / f"{name}.json"
            if agent_storage_file.exists():
                files_to_delete.append(("Agent storage", agent_storage_file))

            # Check markdown file
            agent_md_file = storage_path / category_dir / f"{name}.md"
            if agent_md_file.exists():
                files_to_delete.append(("Agent storage", agent_md_file))

        # Check global Claude file
        global_claude = Path.home() / ".claude" / "agents" / f"{name}.md"
        if global_claude.exists():
            files_to_delete.append(("Global Claude", global_claude))

        # Check project Claude file
        project_claude = Path.cwd() / ".claude" / "agents" / f"{name}.md"
        if project_claude.exists():
            files_to_delete.append(("Project Claude", project_claude))

        # Check project Cursor file
        project_cursor = Path.cwd() / ".cursor" / "rules" / f"{name}.mdc"
        if project_cursor.exists():
            files_to_delete.append(("Project Cursor", project_cursor))

        if files_to_delete:
            console.print("\n[bold]Integration files to be removed:[/bold]")
            for desc, path in files_to_delete:
                console.print(f"  • {desc}: {path}")

        # Show agent content preview
        console.print("\n")
        preview_line_count = 10
        preview_lines = agent.content.split("\n")[:preview_line_count]
        preview_text = "\n".join(preview_lines)
        if len(agent.content.split("\n")) > preview_line_count:
            preview_text += "\n[dim]... (truncated)[/dim]"

        preview_panel = Panel(
            preview_text,
            title=f"[bold red]Agent Content Preview - {agent.metadata.display_name}[/bold red]",
            border_style="red",
            padding=(1, 2),
            expand=True,
        )
        console.print(preview_panel)

        # Confirm deletion
        if not force:
            confirm = typer.confirm("\nAre you sure you want to delete this agent?")
            if not confirm:
                console.print("[yellow]Deletion cancelled[/yellow]")
                return

        # Remove from config if enabled/disabled
        config_manager = get_config_manager()
        config = config_manager.get_config()
        config_updated = False

        if resolved_name in config.agents.enabled:
            config.agents.enabled.remove(resolved_name)
            config_updated = True
        if resolved_name in config.agents.disabled:
            config.agents.disabled.remove(resolved_name)
            config_updated = True
        if resolved_name in getattr(config.agents, "global_enabled", []):
            config.agents.global_enabled.remove(resolved_name)
            config_updated = True
        if resolved_name in getattr(config.agents, "global_disabled", []):
            config.agents.global_disabled.remove(resolved_name)
            config_updated = True

        if config_updated:
            # Save config changes
            config_manager.set_config_value("agents.enabled", config.agents.enabled)
            config_manager.set_config_value("agents.disabled", config.agents.disabled)
            if hasattr(config.agents, "global_enabled"):
                config_manager.set_config_value("agents.global_enabled", config.agents.global_enabled)
            if hasattr(config.agents, "global_disabled"):
                config_manager.set_config_value("agents.global_disabled", config.agents.global_disabled)

        # Delete integration files
        for desc, path in files_to_delete:
            try:
                path.unlink()
                console.print(f"  [dim]Deleted {desc} file[/dim]")
            except Exception as e:
                console.print(f"  [yellow]Warning: Failed to delete {desc} file: {e}[/yellow]")

        # Delete from storage
        from myai.storage.agent import AgentStorage
        from myai.storage.filesystem import FileSystemStorage

        storage = FileSystemStorage(Path.home() / ".myai")
        agent_storage = AgentStorage(storage)

        # Try to delete the agent from storage (may not exist for default agents)
        try:
            agent_storage.delete_agent(resolved_name)
        except Exception:  # noqa: S110
            # Default agents might not be in storage
            pass

        # If this is a default agent, add it to deleted list to prevent rediscovery
        if not agent.is_custom:
            # Add to a deleted_default_agents config list
            deleted_list = getattr(config.agents, "deleted_default_agents", [])
            if resolved_name not in deleted_list:
                deleted_list.append(resolved_name)
                config_manager.set_config_value("agents.deleted_default_agents", deleted_list)
                console.print(f"[dim]Added '{name}' to deleted default agents list[/dim]")

        # Remove from registry
        registry.unregister_agent(resolved_name)

        console.print(f"\n[green]✅ Agent '{name}' deleted successfully![/green]")

        # Update AGENTS.md if needed
        if config_updated and not getattr(config.agents, "global_enabled", []):
            _update_agents_md_file()

    except Exception as e:
        console.print(f"[red]Error deleting agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def edit(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to edit"),
    editor: Optional[str] = typer.Option(None, "--editor", "-e", help="Editor to use (default: $EDITOR or vi)"),
):
    """Edit an agent's content file."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # Resolve agent name (could be display name)
        resolved_name = _resolve_agent_name(registry, name)
        if not resolved_name:
            return

        agent = registry.get_agent(resolved_name)
        if not agent:
            # This should never happen if resolve_agent_name succeeded
            console.print(f"[red]Internal error: Could not load agent '{name}'[/red]")
            return

        # Show agent context before editing
        console.print(f"\n[bold cyan]📝 Editing Agent: {agent.metadata.display_name}[/bold cyan]")
        console.print(f"[dim]Name: {agent.metadata.name}[/dim]")
        console.print(f"[dim]Category: {agent.metadata.category.value}[/dim]")
        console.print(f"[dim]Version: {agent.metadata.version}[/dim]")
        console.print(f"[dim]Tools: {', '.join(agent.metadata.tools)}[/dim]")
        if agent.metadata.tags:
            console.print(f"[dim]Tags: {', '.join(agent.metadata.tags)}[/dim]")
        console.print()

        # Create a temporary markdown file for editing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write(agent.content)
            tmp_path = tmp.name

        try:
            # Determine editor
            if editor:
                editor_cmd = editor
            else:
                # Check for available editors
                available_editors = []
                editor_options = [
                    ("nano", "Nano (simple terminal editor)", False),
                    ("vim", "Vim (advanced terminal editor)", False),
                    ("vi", "Vi (classic terminal editor)", False),
                    ("emacs", "Emacs (powerful terminal editor)", False),
                    ("code --wait", "Visual Studio Code", True),
                    ("cursor --wait", "Cursor", True),
                    ("windsurf --wait", "Windsurf", True),
                    ("kiro --wait", "Kiro", True),
                    ("subl --wait", "Sublime Text", True),
                    ("atom --wait", "Atom", True),
                    ("notepad++", "Notepad++ (Windows)", True),
                    ("notepad", "Notepad (Windows)", True),
                    ("open -e -W", "TextEdit (macOS)", True),
                    ("gedit --wait", "Gedit (Linux)", True),
                    ("custom", "Enter custom editor command", False),
                ]

                # Check which editors are available
                for cmd, desc, is_gui in editor_options:
                    if cmd == "custom":
                        # Always add custom option at the end
                        continue
                    # For commands with spaces, check the first part
                    check_cmd = cmd.split()[0]
                    if shutil.which(check_cmd):
                        available_editors.append((cmd, desc, is_gui))

                # Always add custom option
                available_editors.append(("custom", "Enter custom editor command", False))

                # Check for EDITOR environment variable
                env_editor = os.environ.get("EDITOR")
                if env_editor and shutil.which(env_editor.split()[0]):
                    # Guess if EDITOR is a GUI editor
                    gui_editors = ["code", "cursor", "windsurf", "kiro", "subl", "atom", "notepad"]
                    is_gui_env = any(gui in env_editor.lower() for gui in gui_editors)
                    available_editors.insert(0, (env_editor, f"Default editor ({env_editor})", is_gui_env))

                if not available_editors:
                    console.print("[red]No text editors found. Please install one or specify with --editor[/red]")
                    return

                # Show available editors
                console.print("\n[bold]Available editors:[/bold]")
                for i, (_, desc, _) in enumerate(available_editors, 1):
                    console.print(f"  {i}. {desc}")

                # Ask user to choose
                choice = Prompt.ask(
                    "\nSelect an editor", choices=[str(i) for i in range(1, len(available_editors) + 1)], default="1"
                )

                selected = available_editors[int(choice) - 1]
                editor_cmd = selected[0]
                is_gui = selected[2]

                # Handle custom editor option
                if editor_cmd == "custom":
                    editor_cmd = Prompt.ask("Enter editor command (e.g., 'code --wait' or 'vim')")
                    # Guess if it's a GUI editor based on known patterns
                    gui_editors = ["code", "cursor", "windsurf", "kiro", "subl", "atom", "notepad"]
                    is_gui = any(gui in editor_cmd.lower() for gui in gui_editors)

            # Open editor
            console.print(f"\n[dim]Opening agent '{name}' in editor...[/dim]")
            console.print(f"[dim]Temporary file: {tmp_path}[/dim]")

            # Handle multi-word commands
            if " " in editor_cmd:
                cmd_parts = editor_cmd.split()
                cmd_parts.append(tmp_path)
                subprocess.run(cmd_parts, check=True)  # noqa: S603
            else:
                subprocess.run([editor_cmd, tmp_path], check=True)  # noqa: S603

            # For GUI editors that don't support --wait, prompt user
            if is_gui and "--wait" not in editor_cmd and "-W" not in editor_cmd:
                console.print("\n[yellow]Note: This editor may have opened in the background.[/yellow]")
                console.print("[yellow]Edit the file and save it, then come back here.[/yellow]")
                Prompt.ask("\nPress Enter when you've finished editing and saved the file")

            # Read the edited content
            with open(tmp_path) as f:
                new_content = f.read()

            if new_content != agent.content:
                # Update the agent
                agent.content = new_content

                # Save to storage
                from myai.storage.agent import AgentStorage
                from myai.storage.filesystem import FileSystemStorage

                storage = FileSystemStorage(Path.home() / ".myai")
                agent_storage = AgentStorage(storage)
                agent_storage.save_agent(agent)

                console.print(f"[green]✅ Agent '{name}' updated successfully![/green]")

                # Update integration files if agent is enabled
                config_manager = get_config_manager()
                config = config_manager.get_config()
                if name in config.agents.enabled:
                    _create_agent_files(agent, global_scope=False)
                    console.print("[dim]Updated project integration files[/dim]")
                elif name in getattr(config.agents, "global_enabled", []):
                    _create_agent_files(agent, global_scope=True)
                    console.print("[dim]Updated global integration files[/dim]")
            else:
                console.print("[yellow]No changes made[/yellow]")

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except subprocess.CalledProcessError:
        console.print("[red]Editor exited with error[/red]")
    except Exception as e:
        console.print(f"[red]Error editing agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def validate(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None, help="Agent name to validate (or all if not specified)"),
    strict: bool = typer.Option(False, "--strict", help="Use strict validation mode"),  # noqa: FBT001
):
    """Validate agent specifications.

    This command checks agents for common issues like missing fields,
    invalid formats, and adherence to quality standards.

    Examples:
      myai agent validate                    # Validate all agents
      myai agent validate python-expert     # Validate specific agent
      myai agent validate --strict           # Use strict validation rules

    Related commands:
      myai agent show <name>              # See agent details
      myai agent create <name>            # Create a new agent
    """
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        validator = AgentValidator(strict_mode=strict)

        if name:
            # Validate specific agent
            # Resolve agent name (could be display name)
            resolved_name = _resolve_agent_name(registry, name)
            if not resolved_name:
                return

            agent = registry.get_agent(resolved_name)
            if not agent:
                # This should never happen if resolve_agent_name succeeded
                console.print(f"[red]Internal error: Could not load agent '{name}'[/red]")
                return

            console.print(f"\n[bold]🔍 Validating Agent: {agent.metadata.display_name}[/bold]")
            console.print(f"[dim]Validation mode: {'Strict' if strict else 'Normal'}[/dim]")
            console.print("[dim]Checks performed: Metadata, Content, Tools, Dependencies, Security[/dim]\n")

            errors = validator.validate_agent(agent)

            if not errors:
                console.print(f"✅ Agent '{name}' is valid")
                console.print("[dim]All validation checks passed successfully[/dim]")
            else:
                console.print(f"❌ Agent '{name}' has {len(errors)} validation errors:")
                console.print()
                for error in errors:
                    console.print(f"  [red]•[/red] [bold]{error.field}[/bold]: {error.message}")
                console.print(f"\n[dim]Tip: Use 'myai agent show {name}' to view agent details[/dim]")
        else:
            # Validate all agents
            agents = registry.list_agents()
            console.print(f"\n[bold]🔍 Validating All Agents ({len(agents)} total)[/bold]")
            console.print(f"[dim]Validation mode: {'Strict' if strict else 'Normal'}[/dim]")
            console.print("[dim]Checks performed: Metadata, Content, Tools, Dependencies, Security[/dim]\n")

            results = validator.validate_batch(agents)

            if not results:
                console.print("✅ All agents are valid")
                console.print("[dim]All validation checks passed successfully[/dim]")
            else:
                valid_count = len(agents) - len(results)
                console.print(f"[green]✅ {valid_count} agents passed validation[/green]")
                console.print(f"[red]❌ {len(results)} agents have validation errors:[/red]\n")

                for agent_name, errors in results.items():
                    console.print(f"[bold]{agent_name}[/bold] ({len(errors)} errors):")
                    for error in errors:
                        console.print(f"  [red]•[/red] [bold]{error.field}[/bold]: {error.message}")
                    console.print()

                console.print(
                    "[dim]Tip: Run 'myai agent validate <name>' for detailed validation of specific agents[/dim]"
                )

    except Exception as e:
        console.print(f"[red]Error validating agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def test(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to test"),
    prompt: str = typer.Argument(..., help="Test prompt to run"),
    use_claude_sdk: bool = typer.Option(  # noqa: FBT001
        True, "--claude-sdk/--no-claude-sdk", help="Use Claude SDK for testing"
    ),
):
    """Test an agent with a specific prompt using Claude SDK.

    This command allows you to test how an agent responds to a specific prompt.
    Requires a valid ANTHROPIC_API_KEY environment variable.

    Examples:
      myai agent test python-expert "How do I optimize Python performance?"
      myai agent test security-analyst "Review this code for vulnerabilities"

    Related commands:
      myai agent show <name>              # See agent details first
      myai agent create <name>            # Create a test agent
      myai agent enable <name>            # Enable agent for your project
    """
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # Resolve agent name (could be display name)
        resolved_name = _resolve_agent_name(registry, name)
        if not resolved_name:
            return

        agent = registry.get_agent(resolved_name)
        if not agent:
            # This should never happen if resolve_agent_name succeeded
            console.print(f"[red]Internal error: Could not load agent '{name}'[/red]")
            return

        if use_claude_sdk:
            try:
                from myai.integrations.claude_sdk import get_claude_sdk_integration

                console.print(f"\n🧪 Testing agent '{name}' with Claude SDK...")
                console.print(f"[dim]Agent: {agent.metadata.display_name} ({agent.metadata.category.value})[/dim]")
                console.print(f"[dim]Prompt: {prompt}[/dim]")
                console.print("[dim]Initializing SDK connection...[/dim]")

                sdk = get_claude_sdk_integration()

                console.print("[dim]Sending test request to Claude...[/dim]")

                # Run the test
                result = sdk.test_agent(agent, prompt)

                console.print("[dim]Processing response...[/dim]\n")

                if result["status"] == "completed":
                    console.print("[bold]Result:[/bold]")
                    console.print(result["result"])
                    console.print(f"\n[dim]Cost: {result.get('cost', 'N/A')}[/dim]")
                    console.print(f"[dim]Duration: {result['usage']['total_tokens']} tokens[/dim]")
                elif result["status"] == "error":
                    console.print(f"[red]Error: {result['error']}[/red]")
                else:
                    console.print("[yellow]No results returned[/yellow]")

            except Exception as e:
                error_msg = str(e).lower()

                if "anthropic_api_key" in error_msg or "api key" in error_msg:
                    console.print("\n[yellow]⚠️  Claude API Key Required for Testing[/yellow]")
                    console.print("[bold]To test agents with Claude SDK:[/bold]")
                    console.print("1. Get an API key from: [cyan]https://console.anthropic.com/[/cyan]")
                    console.print("2. Set your API key:")
                    console.print("   [cyan]export ANTHROPIC_API_KEY='your-key-here'[/cyan]")
                    console.print("3. Or add to your shell profile (~/.bashrc or ~/.zshrc)")
                    console.print("\n[dim]Note: Testing requires a valid API key to communicate with Claude.[/dim]")
                elif "not found" in error_msg or "import" in error_msg:
                    console.print("\n[yellow]⚠️  Claude SDK Dependencies Missing[/yellow]")
                    console.print("[bold]To install required dependencies:[/bold]")
                    console.print("   [cyan]pip install anthropic[/cyan]")
                    console.print("\n[dim]Note: Testing requires the anthropic package.[/dim]")
                else:
                    console.print(f"[yellow]Claude SDK error: {e}[/yellow]")
                    console.print("[dim]Please check your configuration and try again.[/dim]")
        else:
            console.print("[yellow]Non-SDK testing not yet implemented[/yellow]")
            console.print("[dim]Use --claude-sdk flag to test with Claude SDK[/dim]")

    except Exception as e:
        console.print(f"[red]Error testing agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def diff(
    ctx: typer.Context,
    name1: str = typer.Argument(..., help="First agent name"),
    name2: str = typer.Argument(..., help="Second agent name"),
    show_content: bool = typer.Option(False, "--content", help="Show content differences"),  # noqa: FBT001
):
    """Compare two agents and show differences.

    This command shows a side-by-side comparison of two agents, including
    their metadata (name, category, tools, tags) and optionally their content.

    Examples:
      myai agent diff python-expert java-expert        # Compare metadata
      myai agent diff python-expert java-expert --content # Include content diff

    Related commands:
      myai agent show <name>              # See individual agent details
      myai agent list                     # See all available agents
    """
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # Resolve agent names (could be display names)
        resolved_name1 = registry.resolve_agent_name(name1)
        if not resolved_name1:
            console.print(f"[red]❌ Agent '{name1}' not found[/red]")
            available_agents = [a.metadata.name for a in registry.list_agents()]
            similar_agents = [a for a in available_agents if name1.lower() in a.lower()]
            if similar_agents:
                console.print(f"[dim]Did you mean: {', '.join(similar_agents[:3])}?[/dim]")
            console.print("[dim]Use 'myai agent list' to see all available agents[/dim]")
            return

        resolved_name2 = registry.resolve_agent_name(name2)
        if not resolved_name2:
            console.print(f"[red]❌ Agent '{name2}' not found[/red]")
            available_agents = [a.metadata.name for a in registry.list_agents()]
            similar_agents = [a for a in available_agents if name2.lower() in a.lower()]
            if similar_agents:
                console.print(f"[dim]Did you mean: {', '.join(similar_agents[:3])}?[/dim]")
            console.print("[dim]Use 'myai agent list' to see all available agents[/dim]")
            return

        agent1 = registry.get_agent(resolved_name1)
        agent2 = registry.get_agent(resolved_name2)
        if not agent1 or not agent2:
            # This should never happen if resolve_agent_name succeeded
            console.print("[red]Internal error: Could not load agents[/red]")
            return

        # Compare metadata
        console.print(f"[bold]Comparing {name1} vs {name2}[/bold]")

        table = Table(title="Agent Differences", show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan")
        table.add_column(name1, style="green")
        table.add_column(name2, style="yellow")
        table.add_column("Match", style="dim")

        # Compare key fields
        fields = [
            ("Display Name", agent1.metadata.display_name, agent2.metadata.display_name),
            ("Category", agent1.metadata.category.value, agent2.metadata.category.value),
            ("Version", agent1.metadata.version, agent2.metadata.version),
            ("Tools", ", ".join(agent1.metadata.tools), ", ".join(agent2.metadata.tools)),
            ("Tags", ", ".join(agent1.metadata.tags), ", ".join(agent2.metadata.tags)),
        ]

        differences_found = False
        for field_name, val1, val2 in fields:
            match = "✅" if val1 == val2 else "❌"
            if val1 != val2:
                differences_found = True
            table.add_row(field_name, str(val1), str(val2), match)

        console.print(table)

        if show_content:
            if agent1.content != agent2.content:
                console.print(f"\n[red]Content differs between {name1} and {name2}[/red]")
                console.print("[dim]Use a text diff tool for detailed content comparison[/dim]")
            else:
                console.print(f"\n[green]Content is identical between {name1} and {name2}[/green]")

        if not differences_found and (not show_content or agent1.content == agent2.content):
            console.print(f"\n[green]✅ Agents {name1} and {name2} are identical[/green]")

    except Exception as e:
        console.print(f"[red]Error comparing agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command(name="list")
def list_agents(ctx: typer.Context):
    """List agents with detailed status.

    Shows all agents with their current status, scope, and integration files.
    Provides an overview of enabled/disabled agents and file locations."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        config_manager = get_config_manager()
        config = config_manager.get_config()

        enabled_list = config.agents.enabled
        disabled_list = config.agents.disabled
        global_enabled = getattr(config.agents, "global_enabled", [])
        global_disabled = getattr(config.agents, "global_disabled", [])

        # Get all agents
        agents = registry.list_agents()

        # Calculate summary stats
        total_agents = len(agents)
        enabled_global_count = len(global_enabled)
        enabled_project_count = len(enabled_list)

        # Print title and overview bar
        title = Text("🤖 Agent Status Report", justify="center", style="bold")
        console.print()
        console.print(title)
        console.print()

        overview_panel = Panel(
            f"Total Agents: {total_agents}  •  ✅ Enabled: {enabled_global_count + enabled_project_count}  •  "
            f"🌐 Global: {enabled_global_count}  •  📁 Project: {enabled_project_count}",
            title="📊 Overview",
            border_style="bright_blue",
            box=box.DOUBLE,
            expand=False,
        )
        console.print(overview_panel)
        console.print()

        # Create status table
        table = Table(show_header=True, header_style="bold magenta", box=box.HEAVY)
        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Scope", justify="center")
        table.add_column("Claude", justify="center")
        table.add_column("Cursor", justify="center")
        table.add_column("Windsurf", justify="center")
        table.add_column("Kiro", justify="center")

        for agent in sorted(agents, key=lambda a: a.metadata.name):
            name = agent.metadata.name

            # Determine status
            if name in global_enabled:
                status = "[green]Enabled[/green]"
                scope = "Global"
            elif name in enabled_list:
                status = "[green]Enabled[/green]"
                scope = "Project"
            elif name in global_disabled:
                status = "[red]Disabled[/red]"
                scope = "Global"
            elif name in disabled_list:
                status = "[red]Disabled[/red]"
                scope = "Project"
            else:
                status = "[dim]Available[/dim]"
                scope = "-"

            # Check file existence
            claude_global = (Path.home() / ".claude" / "agents" / f"{name}.md").exists()
            claude_project = (Path.cwd() / ".claude" / "agents" / f"{name}.md").exists()
            cursor_project = (Path.cwd() / ".cursor" / "rules" / f"{name}.mdc").exists()
            windsurf_project = (Path.cwd() / ".windsurf" / "rules" / f"{name}.md").exists()
            kiro_project = (Path.cwd() / ".kiro" / "agents" / f"{name}.md").exists()

            claude_status = "[green]✓[/green]" if (claude_global or claude_project) else "[red]✗[/red]"
            cursor_status = "[green]✓[/green]" if cursor_project else "[red]✗[/red]"
            windsurf_status = "[green]✓[/green]" if windsurf_project else "[red]✗[/red]"
            kiro_status = "[green]✓[/green]" if kiro_project else "[red]✗[/red]"

            table.add_row(
                agent.metadata.display_name,
                status,
                scope,
                claude_status,
                cursor_status,
                windsurf_status,
                kiro_status,
            )

        console.print(table)

        # Create combined box for file locations and tips
        console.print()
        file_locations = Panel(
            "[bold]File Locations:[/bold]\n"
            "  Global agents: ~/.claude/agents/\n"
            "  Project Claude: .claude/agents/\n"
            "  Project Cursor: .cursor/rules/\n"
            "  Project Windsurf: .windsurf/rules/\n"
            "  Project Kiro: .kiro/agents/",
            title="📍 File Locations",
            border_style="blue",
        )
        console.print(file_locations)

    except Exception as e:
        console.print(f"[red]Error listing agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def templates(ctx: typer.Context):
    """List available agent templates."""
    state: AppState = ctx.obj

    try:
        template_registry = get_template_registry()
        templates = template_registry.list_templates()

        if not templates:
            console.print("[dim]No templates found[/dim]")
            return

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            template_data = [
                {
                    "name": template.name,
                    "display_name": template.display_name,
                    "category": template.category.value,
                    "description": template.description,
                    "is_system": template.is_system,
                }
                for template in templates
            ]
            formatter.format(template_data)
        else:
            # Create table
            table = Table(title="📋 Available Templates", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Display Name", style="white")
            table.add_column("Category", style="green")
            table.add_column("Type", style="yellow")
            table.add_column("Description", style="dim")

            for template in templates:
                template_type = "System" if template.is_system else "User"
                description = (
                    template.description[:MAX_DESCRIPTION_LENGTH] + "..."
                    if len(template.description) > MAX_DESCRIPTION_LENGTH
                    else template.description
                )
                table.add_row(
                    template.name,
                    template.display_name,
                    template.category.value,
                    template_type,
                    description,
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing templates: {e}[/red]")
        if state.is_debug():
            raise
