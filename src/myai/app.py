"""
MyAI CLI application.

This module provides the main CLI interface for MyAI, including command groups,
output formatting, and global options.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from myai.__about__ import __version__

# from myai.cli.formatters import get_formatter  # Currently unused
from myai.cli.state import AppState
from myai.commands import agent_cli, config_cli, integration_cli, setup_cli, system_cli, wizard_cli

# Create the main Typer application
app = typer.Typer(
    name="myai",
    help="🤖 MyAI - AI Agent and Configuration Management CLI",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help", "help"]},
)

# Global console instance
console = Console()

# Global application state
state = AppState()


@app.callback()
def main_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),  # noqa: FBT001
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),  # noqa: FBT001
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Custom config file path"),
    output_format: str = typer.Option("table", "--output", "-o", help="Output format (table, json)"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),  # noqa: FBT001
):
    """
    🤖 MyAI - AI Agent and Configuration Management CLI

    Manage your AI agents, configurations, and tool integrations from one place.
    """
    # Update global state
    state.debug = debug
    state.verbose = verbose
    state.config_path = config_path
    state.output_format = output_format

    # Configure console
    if no_color:
        console._color_system = None

    if debug:
        console.print("[dim]Debug mode enabled[/dim]")

    # Store state in context
    ctx.obj = state


@app.command()
def version(
    _ctx: typer.Context,
    short: bool = typer.Option(False, "--short", help="Show only version number"),  # noqa: FBT001
):
    """Show version information."""
    if short:
        console.print(__version__)
    else:
        version_panel = Panel(
            Text(__version__, style="bold cyan"),
            title="[bold]MyAI Version[/bold]",
            subtitle="AI Agent & Configuration Manager",
            border_style="blue",
        )
        console.print(version_panel)


@app.command()
def status(ctx: typer.Context):
    """Show comprehensive system status and overview."""
    import platform
    import sys

    from myai.agent.registry import get_agent_registry
    from myai.cli.formatters import get_formatter
    from myai.config.manager import get_config_manager

    state: AppState = ctx.obj

    if state.debug:
        console.print("[dim]Running status check...[/dim]")

    try:
        # Gather system information
        registry = get_agent_registry()
        config_manager = get_config_manager()
        agents = registry.list_agents()

        # Count enabled agents across all scopes
        config = config_manager.get_config()
        enabled_agents = []
        global_enabled = getattr(config.agents, "global_enabled", [])
        project_enabled = config.agents.enabled

        for agent in agents:
            if agent.metadata.name in global_enabled or agent.metadata.name in project_enabled:
                enabled_agents.append(agent)

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            system_data = {
                "system": {
                    "platform": platform.system(),
                    "python_version": sys.version.split()[0],
                    "myai_path": str(Path.home() / ".myai"),
                },
                "agents": {
                    "total": len(agents),
                    "global_enabled": len(global_enabled),
                    "project_enabled": len(project_enabled),
                    "categories": len({a.metadata.category.value for a in agents if hasattr(a.metadata, "category")}),
                },
                "configuration": {
                    "user_config": str(config_manager.get_config_path("user") or "Not set"),
                    "project_config": str(config_manager.get_config_path("project") or "Not set"),
                },
                "integrations": {
                    "claude": (Path.home() / ".claude" / "agents").exists(),
                    "cursor": (Path.cwd() / ".cursor" / "rules").exists(),
                },
            }
            formatter.format(system_data)
        else:
            # Create comprehensive status display
            console.print("[bold cyan]🔍 MyAI System Status[/bold cyan]\n")

            # System info table
            system_table = Table(title="System Information", show_header=False)
            system_table.add_column("Property", style="cyan")
            system_table.add_column("Value", style="white")

            system_table.add_row("Platform", platform.system())
            system_table.add_row("Python Version", sys.version.split()[0])
            system_table.add_row("MyAI Path", str(Path.home() / ".myai"))
            system_table.add_row("Current Directory", str(Path.cwd()))

            console.print(system_table)
            console.print()

            # Agent statistics table
            agent_table = Table(title="Agent Statistics", show_header=False)
            agent_table.add_column("Metric", style="cyan")
            agent_table.add_column("Count", style="white")

            agent_table.add_row("Total Agents", str(len(agents)))
            agent_table.add_row("Globally Enabled", str(len(global_enabled)))
            agent_table.add_row("Project Enabled", str(len(project_enabled)))
            agent_table.add_row(
                "Categories", str(len({a.metadata.category.value for a in agents if hasattr(a.metadata, "category")}))
            )

            console.print(agent_table)
            console.print()

            # Configuration & Integration status
            status_table = Table(title="Configuration & Integrations", show_header=True, header_style="bold magenta")
            status_table.add_column("Component", style="cyan", no_wrap=True)
            status_table.add_column("Status", justify="center")
            status_table.add_column("Details", style="dim")

            # Configuration status
            user_config_path = config_manager.get_config_path("user")
            if user_config_path and user_config_path.exists():
                status_table.add_row("User Config", "✅ OK", str(user_config_path))
            else:
                status_table.add_row("User Config", "⚠️  Not Set", "Using defaults")

            project_config_path = config_manager.get_config_path("project")
            if project_config_path and project_config_path.exists():
                status_table.add_row("Project Config", "✅ OK", str(project_config_path))
            else:
                status_table.add_row("Project Config", "⚠️  Not Set", "No project config")

            # Integration status
            claude_path = Path.home() / ".claude" / "agents"
            if claude_path.exists():
                claude_count = len(list(claude_path.glob("*.md")))
                status_table.add_row("Claude Integration", "✅ OK", f"{claude_count} agents synced")
            else:
                status_table.add_row("Claude Integration", "❌ Not Setup", "Run 'myai setup all-setup'")

            cursor_path = Path.cwd() / ".cursor" / "rules"
            if cursor_path.exists():
                cursor_count = len(list(cursor_path.glob("*.mdc")))
                status_table.add_row("Cursor Integration", "✅ OK", f"{cursor_count} rules active")
            else:
                status_table.add_row("Cursor Integration", "❌ Not Setup", "Run 'myai setup all-setup'")

            console.print(status_table)

    except Exception as e:
        console.print(f"[red]Error getting system status: {e}[/red]")
        if state.is_debug():
            raise


def main():
    """Main entry point for the CLI application."""
    # Add command groups
    app.add_typer(setup_cli.app, name="setup", help="🛠️  Setup and initialization commands")
    app.add_typer(config_cli.app, name="config", help="📝 Configuration management commands")
    app.add_typer(agent_cli.app, name="agent", help="🤖 Agent management commands")
    app.add_typer(integration_cli.app, name="integration", help="🔗 Tool integration management commands")
    app.add_typer(system_cli.app, name="system", help="🔧 System utilities and diagnostics")
    app.add_typer(wizard_cli.app, name="wizard", help="🧙 Interactive wizards and guided workflows")

    # Launch the application
    app()


if __name__ == "__main__":
    main()
