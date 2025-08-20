"""
Agent management CLI commands.

This module provides CLI commands for managing AI agents,
including listing, creating, editing, and managing agents.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
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

# Create agent command group
app = typer.Typer(help="🤖 Agent management commands")


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
        # Create project Claude file (lightweight wrapper)
        project_claude_dir = Path.cwd() / ".claude" / "agents"
        project_claude_dir.mkdir(parents=True, exist_ok=True)
        project_claude_file = project_claude_dir / f"{agent_name}.md"
        if not project_claude_file.exists():
            wrapper_content = f"""---
agent: "{agent_name}"
source: "~/.myai/agents"
---

# {agent.metadata.display_name}

@myai/agents/{agent.metadata.category.value if agent.metadata.category else 'default'}/{agent_name}.md
"""
            project_claude_file.write_text(wrapper_content)

        # Create project Cursor file
        project_cursor_dir = Path.cwd() / ".cursor" / "rules"
        project_cursor_dir.mkdir(parents=True, exist_ok=True)
        cursor_file = project_cursor_dir / f"{agent_name}.mdc"
        if not cursor_file.exists():
            mdc_content = f"""---
description: "Cursor rules for {agent.metadata.display_name}"
globs:
alwaysApply: false
version: 1.0
encoding: UTF-8
---

# {agent.metadata.display_name}

@myai/agents/{agent.metadata.category.value if agent.metadata.category else 'default'}/{agent_name}.md
"""
            cursor_file.write_text(mdc_content)


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


@app.command(name="list")
def list_agents(
    ctx: typer.Context,
    category: Optional[AgentCategory] = typer.Option(None, "--category", "-c", help="Filter by category"),
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    enabled_only: bool = typer.Option(False, "--enabled", help="Show only enabled agents"),  # noqa: FBT001
    all_agents: bool = typer.Option(False, "--all", help="Show all agents including disabled"),  # noqa: FBT001
):
    """List available agents."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Loading agents...[/dim]")

    try:
        registry = get_agent_registry()
        config_manager = get_config_manager()
        config = config_manager.get_config()

        # Get enabled/disabled lists from config
        enabled_list = config.agents.enabled
        disabled_list = config.agents.disabled
        global_enabled_list = getattr(config.agents, "global_enabled", [])
        global_disabled_list = getattr(config.agents, "global_disabled", [])

        agents = registry.list_agents(category=category.value if category else None, tool=tool, tag=tag)

        # Filter based on enabled/disabled status
        if not all_agents:
            # By default, show all agents except explicitly disabled ones (global or project)
            agents = [
                a
                for a in agents
                if a.metadata.name not in disabled_list and a.metadata.name not in global_disabled_list
            ]

        if enabled_only:
            # Show only explicitly enabled agents (global or project)
            agents = [a for a in agents if a.metadata.name in enabled_list or a.metadata.name in global_enabled_list]

        if not agents:
            console.print("[dim]No agents found[/dim]")
            return

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            agent_data = [
                {
                    "name": agent.metadata.name,
                    "display_name": agent.metadata.display_name,
                    "category": agent.metadata.category.value,
                    "tools": agent.metadata.tools,
                    "tags": agent.metadata.tags,
                    "version": agent.metadata.version,
                }
                for agent in agents
            ]
            formatter.format(agent_data)
        else:
            # Create table
            table = Table(title="🤖 Available Agents", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Display Name", style="white")
            table.add_column("Category", style="green")
            table.add_column("Tools", style="yellow")
            table.add_column("Status", style="blue")
            table.add_column("Version", style="dim")

            for agent in agents:
                # Determine status - show both global and project status
                global_status = ""
                project_status = ""

                if agent.metadata.name in global_disabled_list:
                    global_status = "[red]Global: Disabled[/red]"
                elif agent.metadata.name in global_enabled_list:
                    global_status = "[green]Global: Enabled[/green]"

                if agent.metadata.name in disabled_list:
                    project_status = "[red]Project: Disabled[/red]"
                elif agent.metadata.name in enabled_list:
                    project_status = "[green]Project: Enabled[/green]"

                # Combine statuses
                if global_status and project_status:
                    status = f"{global_status}, {project_status}"
                elif global_status:
                    status = global_status
                elif project_status:
                    status = project_status
                else:
                    status = "[dim]Default[/dim]"

                table.add_row(
                    agent.metadata.name,
                    agent.metadata.display_name,
                    agent.metadata.category.value,
                    ", ".join(agent.metadata.tools[:3]),  # Show first 3 tools
                    status,
                    agent.metadata.version,
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to show"),
    content: bool = typer.Option(False, "--content", help="Show agent content"),  # noqa: FBT001
):
    """Show detailed information about an agent."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        agent = registry.get_agent(name)

        if not agent:
            console.print(f"[red]Agent '{name}' not found[/red]")
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

            panel = Panel(
                metadata_text,
                title=f"🤖 Agent: {metadata.display_name}",
                border_style="blue",
            )
            console.print(panel)

            if content:
                content_panel = Panel(
                    agent.content,
                    title="📝 Agent Content",
                    border_style="green",
                )
                console.print(content_panel)

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
    """Enable one or more agents."""
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()
        registry = get_agent_registry()

        enabled_count = 0
        not_found = []
        enabled_agents = []

        for name in names:
            # Check if agent exists
            agent = registry.get_agent(name)
            if not agent:
                not_found.append(name)
                continue

            if global_scope:
                # Handle global enablement
                if name in config.agents.global_disabled:
                    config.agents.global_disabled.remove(name)
                if name not in config.agents.global_enabled:
                    config.agents.global_enabled.append(name)
                    enabled_agents.append(agent)
                    enabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already enabled globally[/yellow]")
            else:
                # Handle project-level enablement
                if name in config.agents.disabled:
                    config.agents.disabled.remove(name)
                if name not in config.agents.enabled:
                    config.agents.enabled.append(name)
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

            console.print(f"✅ Enabled {enabled_count} agent(s) {scope_text} and created integration files")

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
            # Check if agent exists
            agent = registry.get_agent(name)
            if not agent:
                not_found.append(name)
                continue

            if global_scope:
                # Handle global disabling
                if name in getattr(config.agents, "global_enabled", []):
                    config.agents.global_enabled.remove(name)
                if name not in getattr(config.agents, "global_disabled", []):
                    if not hasattr(config.agents, "global_disabled"):
                        config.agents.global_disabled = []
                    config.agents.global_disabled.append(name)
                    disabled_agents.append(name)
                    disabled_count += 1
                else:
                    console.print(f"[yellow]Agent '{name}' is already disabled globally[/yellow]")
            else:
                # Handle project-level disabling
                if name in config.agents.enabled:
                    config.agents.enabled.remove(name)
                if name not in config.agents.disabled:
                    config.agents.disabled.append(name)
                    disabled_agents.append(name)
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

            console.print(f"✅ Disabled {disabled_count} agent(s) {scope_text} and removed integration files")

        if not_found:
            console.print(f"[red]❌ Agent(s) not found: {', '.join(not_found)}[/red]")

    except Exception as e:
        console.print(f"[red]Error disabling agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name"),
    display_name: Optional[str] = typer.Option(None, "--display-name", help="Agent display name"),
    category: AgentCategory = typer.Option(AgentCategory.CUSTOM, "--category", "-c", help="Agent category"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template to use"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive creation mode"),  # noqa: FBT001
):
    """Create a new agent."""
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

            agent = manager.create_agent_basic(
                name=name,
                display_name=display_name or name.replace("-", " ").title(),
                description=description,
                category=category,
            )

            console.print(f"✅ Created agent '{name}'")

        if interactive:
            edit_choice = typer.confirm("Would you like to edit the agent content now?")
            if edit_choice:
                console.print("[dim]Tip: For full interactive agent creation, try 'myai wizard agent'[/dim]")
                console.print("Interactive editing not yet implemented")

    except Exception as e:
        console.print(f"[red]Error creating agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def edit(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to edit"),
):
    """Edit an agent's content file."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        agent = registry.get_agent(name)

        if not agent:
            console.print(f"[red]Agent '{name}' not found[/red]")
            return

        # For now, show the agent content instead of editing
        # TODO: Add proper API to get agent file paths from registry
        console.print(f"[yellow]Direct file editing not yet implemented for agent '{name}'[/yellow]")
        console.print("[dim]Showing agent content instead:[/dim]\n")

        # Show agent content
        content_panel = Panel(
            agent.content,
            title=f"📝 Agent: {agent.metadata.display_name}",
            border_style="green",
        )
        console.print(content_panel)

        console.print("\n[dim]To edit this agent, modify the source file directly.[/dim]")

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
    """Validate agent specifications."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        validator = AgentValidator(strict_mode=strict)

        if name:
            # Validate specific agent
            agent = registry.get_agent(name)
            if not agent:
                console.print(f"[red]Agent '{name}' not found[/red]")
                return

            errors = validator.validate_agent(agent)

            if not errors:
                console.print(f"✅ Agent '{name}' is valid")
            else:
                console.print(f"❌ Agent '{name}' has {len(errors)} validation errors:")
                for error in errors:
                    console.print(f"  • {error.field}: {error.message}")
        else:
            # Validate all agents
            agents = registry.list_agents()
            results = validator.validate_batch(agents)

            if not results:
                console.print("✅ All agents are valid")
            else:
                console.print(f"❌ Found validation errors in {len(results)} agents:")
                for agent_name, errors in results.items():
                    console.print(f"\n{agent_name}:")
                    for error in errors:
                        console.print(f"  • {error.field}: {error.message}")

    except Exception as e:
        console.print(f"[red]Error validating agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def diff(
    ctx: typer.Context,
    name1: str = typer.Argument(..., help="First agent name"),
    name2: str = typer.Argument(..., help="Second agent name"),
    show_content: bool = typer.Option(False, "--content", help="Show content differences"),  # noqa: FBT001
):
    """Compare two agents and show differences."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        agent1 = registry.get_agent(name1)
        agent2 = registry.get_agent(name2)

        if not agent1:
            console.print(f"[red]Agent '{name1}' not found[/red]")
            return
        if not agent2:
            console.print(f"[red]Agent '{name2}' not found[/red]")
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


@app.command()
def status(ctx: typer.Context):
    """Show agent enabled/disabled status."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()
        config_manager = get_config_manager()
        config = config_manager.get_config()

        enabled_list = config.agents.enabled
        disabled_list = config.agents.disabled

        # Get all agents
        agents = registry.list_agents()

        # Categorize agents
        explicitly_enabled = []
        explicitly_disabled = []
        default_enabled = []

        for agent in agents:
            if agent.metadata.name in disabled_list:
                explicitly_disabled.append(agent)
            elif agent.metadata.name in enabled_list:
                explicitly_enabled.append(agent)
            else:
                default_enabled.append(agent)

        # Display status
        console.print("\n[bold]Agent Status Summary:[/bold]")
        console.print(f"  • Total agents: {len(agents)}")
        console.print(f"  • Explicitly enabled: {len(explicitly_enabled)}")
        console.print(f"  • Explicitly disabled: {len(explicitly_disabled)}")
        console.print(f"  • Default (enabled): {len(default_enabled)}")

        if explicitly_enabled:
            console.print("\n[green]Explicitly Enabled:[/green]")
            for agent in sorted(explicitly_enabled, key=lambda a: a.metadata.name):
                console.print(f"  ✅ {agent.metadata.name} - {agent.metadata.display_name}")

        if explicitly_disabled:
            console.print("\n[red]Explicitly Disabled:[/red]")
            for agent in sorted(explicitly_disabled, key=lambda a: a.metadata.name):
                console.print(f"  ❌ {agent.metadata.name} - {agent.metadata.display_name}")

        if state.is_verbose() and default_enabled:
            console.print("\n[dim]Default Enabled:[/dim]")
            for agent in sorted(default_enabled, key=lambda a: a.metadata.name):
                console.print(f"  • {agent.metadata.name} - {agent.metadata.display_name}")
        elif default_enabled:
            console.print(f"\n[dim]Use --verbose to see {len(default_enabled)} default enabled agents[/dim]")

    except Exception as e:
        console.print(f"[red]Error showing agent status: {e}[/red]")
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
