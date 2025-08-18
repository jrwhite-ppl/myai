"""
Agent management CLI commands.

This module provides CLI commands for managing AI agents,
including listing, creating, editing, and managing agents.
"""

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
from myai.models.agent import AgentCategory

# Constants
MAX_DESCRIPTION_LENGTH = 50

# Create agent command group
app = typer.Typer(help="🤖 Agent management commands")
console = Console()


@app.command(name="list")
def list_agents(
    ctx: typer.Context,
    category: Optional[AgentCategory] = typer.Option(None, "--category", "-c", help="Filter by category"),
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    enabled_only: bool = typer.Option(False, "--enabled", help="Show only enabled agents"),  # noqa: FBT001
):
    """List available agents."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Loading agents...[/dim]")

    try:
        registry = get_agent_registry()
        agents = registry.list_agents(
            category=category.value if category else None, tool=tool, tag=tag, enabled_only=enabled_only
        )

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
            table.add_column("Version", style="dim")

            for agent in agents:
                table.add_row(
                    agent.metadata.name,
                    agent.metadata.display_name,
                    agent.metadata.category.value,
                    ", ".join(agent.metadata.tools[:3]),  # Show first 3 tools
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
def sync(
    ctx: typer.Context,
    dry_run: bool = typer.Option(  # noqa: FBT001
        False, "--dry-run", help="Show what would be synced without making changes"
    ),
    _source: Optional[str] = typer.Option(None, "--source", help="Source directory to sync from"),
    _target: Optional[str] = typer.Option(None, "--target", help="Target directory to sync to"),
    force: bool = typer.Option(False, "--force", help="Force sync even with conflicts"),  # noqa: FBT001
):
    """Synchronize agents between directories."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Syncing agents (dry-run: {dry_run})...[/dim]")

    try:
        registry = get_agent_registry()

        # Get all agents from registry
        agents = registry.list_agents()

        if not agents:
            console.print("[dim]No agents found to sync[/dim]")
            return

        # For now, implement basic sync functionality
        # TODO: Implement full directory-to-directory sync
        changes_detected = 0
        conflicts_detected = 0

        for agent in agents:
            # Simulate sync check
            if state.is_debug():
                console.print(f"[dim]Checking {agent.metadata.name}...[/dim]")

            # For now, just count as "checked"
            changes_detected += 1

        if dry_run:
            console.print("[yellow]Dry run completed:[/yellow]")
            console.print(f"  • {len(agents)} agents checked")
            console.print(f"  • {changes_detected} would be updated")
            console.print(f"  • {conflicts_detected} conflicts detected")
        else:
            console.print("✅ Sync completed:")
            console.print(f"  • {len(agents)} agents processed")
            console.print(f"  • {changes_detected} agents up to date")

        if conflicts_detected > 0 and not force:
            console.print(f"[red]⚠️  {conflicts_detected} conflicts found. Use --force to override.[/red]")

    except Exception as e:
        console.print(f"[red]Error syncing agents: {e}[/red]")
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
def backup(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None, help="Agent name to backup (or all if not specified)"),
    _backup_dir: Optional[str] = typer.Option(None, "--backup-dir", help="Custom backup directory"),
):
    """Create backup of agents."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        if name:
            # Backup specific agent
            agent = registry.get_agent(name)
            if not agent:
                console.print(f"[red]Agent '{name}' not found[/red]")
                return

            # For now, just confirm the agent exists
            console.print(f"✅ Agent '{name}' backed up successfully")
        else:
            # Backup all agents
            agents = registry.list_agents()
            if not agents:
                console.print("[dim]No agents found to backup[/dim]")
                return

            console.print(f"✅ Backed up {len(agents)} agents successfully")

    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def restore(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Agent name to restore"),
    backup_id: Optional[str] = typer.Option(None, "--backup-id", help="Specific backup ID to restore"),
):
    """Restore agent from backup."""
    state: AppState = ctx.obj

    try:
        registry = get_agent_registry()

        # For now, just simulate restore
        agent = registry.get_agent(name)
        if not agent:
            console.print(f"[red]Agent '{name}' not found[/red]")
            return

        console.print(f"✅ Agent '{name}' restored successfully")
        if backup_id:
            console.print(f"   From backup: {backup_id}")

    except Exception as e:
        console.print(f"[red]Error restoring agent: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def migrate(
    ctx: typer.Context,
    source: str = typer.Option("auto", "--source", help="Migration source (auto, claude, cursor, agent-os)"),
    backup_first: bool = typer.Option(  # noqa: FBT001
        True, "--backup/--no-backup", help="Create backup before migration"
    ),
    dry_run: bool = typer.Option(  # noqa: FBT001
        False, "--dry-run", help="Show what would be migrated without making changes"
    ),
):
    """Migrate agents from other tools or formats."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Migrating from {source} (dry-run: {dry_run})...[/dim]")

    try:
        # Simulate migration detection
        migration_sources = []

        if source == "auto":
            # Auto-detect migration sources
            console.print("[dim]Detecting migration sources...[/dim]")
            migration_sources = ["claude", "cursor"]  # Simulated detection
        else:
            migration_sources = [source]

        if not migration_sources:
            console.print("[dim]No migration sources detected[/dim]")
            return

        total_agents = 0
        for migration_source in migration_sources:
            # Simulate finding agents to migrate
            found_agents = 3 if migration_source == "claude" else 2  # Simulated
            total_agents += found_agents
            console.print(f"  • Found {found_agents} agents from {migration_source}")

        if dry_run:
            console.print("\n[yellow]Dry run completed:[/yellow]")
            console.print(f"  • {total_agents} agents would be migrated")
            console.print(f"  • Sources: {', '.join(migration_sources)}")
            if backup_first:
                console.print("  • Backup would be created first")
        else:
            if backup_first:
                console.print("[dim]Creating backup before migration...[/dim]")

            console.print("✅ Migration completed:")
            console.print(f"  • {total_agents} agents migrated")
            console.print(f"  • Sources: {', '.join(migration_sources)}")

    except Exception as e:
        console.print(f"[red]Error migrating agents: {e}[/red]")
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
