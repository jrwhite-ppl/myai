"""
MyAI CLI application.

This module provides the main CLI interface for MyAI, including command groups,
output formatting, and global options.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from myai.__about__ import __version__

# from myai.cli.formatters import get_formatter  # Currently unused
from myai.cli.state import AppState
from myai.commands import agent_cli, config_cli, install_cli, system_cli, uninstall_cli, wizard_cli

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
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode with detailed output"),  # noqa: FBT001
    output: str = typer.Option("table", "--output", "-o", help="Output format (table, json)"),
):
    """
    🤖 MyAI - AI Agent and Configuration Management CLI

    Manage your AI agents, configurations, and tool integrations from one place.
    """
    # Update global state
    state.debug = debug
    state.output_format = output

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
    """Show comprehensive system status and overview.

    This command displays:
    - System information (platform, Python version, MyAI paths)
    - Agent statistics (total, enabled, categories)
    - Configuration status with actionable next steps
    - Integration status for Claude and Cursor

    Use this command to:
    - Check if MyAI is properly configured
    - See which agents are enabled
    - Troubleshoot configuration issues
    - Get guidance on next steps

    Examples:
      myai status                    # Show full status
      myai status --output json     # JSON output for scripts

    Related commands:
      myai install all              # Set up all integrations
      myai agent list               # See available agents
      myai system integration-health # Check integrations
    """
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
                status_table.add_row(
                    "User Config", "⚠️  Not Set", "[dim]Using defaults • Run 'myai config set' to customize[/dim]"
                )

            project_config_path = config_manager.get_config_path("project")
            if project_config_path and project_config_path.exists():
                status_table.add_row("Project Config", "✅ OK", str(project_config_path))
            else:
                status_table.add_row(
                    "Project Config",
                    "⚠️  Not Set",
                    "[dim]No project config • Run 'myai install project' for project setup[/dim]",
                )

            # Integration status
            claude_path = Path.home() / ".claude" / "agents"
            if claude_path.exists():
                claude_count = len(list(claude_path.glob("*.md")))
                status_table.add_row("Claude Integration", "✅ OK", f"{claude_count} agents synced to Claude Code")
            else:
                status_table.add_row(
                    "Claude Integration",
                    "❌ Not Setup",
                    "[dim]Claude Code integration not configured • Run 'myai install all'[/dim]",
                )

            cursor_path = Path.cwd() / ".cursor" / "rules"
            if cursor_path.exists():
                cursor_count = len(list(cursor_path.glob("*.mdc")))
                status_table.add_row("Cursor Integration", "✅ OK", f"{cursor_count} rules active in project")
            else:
                status_table.add_row(
                    "Cursor Integration",
                    "❌ Not Setup",
                    "[dim]Cursor rules not configured • Run 'myai install all' in project[/dim]",
                )

            console.print(status_table)

            # Add next steps section for unconfigured items
            needs_setup = []
            if not user_config_path or not user_config_path.exists():
                needs_setup.append("User configuration")
            if not project_config_path or not project_config_path.exists():
                needs_setup.append("Project configuration")
            if not claude_path.exists():
                needs_setup.append("Claude Code integration")
            if not cursor_path.exists():
                needs_setup.append("Cursor integration")

            if needs_setup:
                console.print()
                next_steps_panel = Panel(
                    "[bold yellow]Recommended Next Steps:[/bold yellow]\n\n"
                    "• Run [cyan]myai install all[/cyan] for complete setup\n"
                    "• Run [cyan]myai agent list[/cyan] to see available agents\n"
                    "• Run [cyan]myai agent enable <name>[/cyan] to enable specific agents\n"
                    "• Check [cyan]myai system integration-health[/cyan] for detailed diagnostics",
                    title="🚀 Getting Started",
                    border_style="yellow",
                )
                console.print(next_steps_panel)

    except Exception as e:
        console.print(f"[red]Error getting system status: {e}[/red]")
        if state.is_debug():
            raise


def create_app():
    """Create and configure the main application."""
    # Add command groups
    app.add_typer(install_cli.app, name="install", help="📦 Installation and configuration commands")
    app.add_typer(uninstall_cli.app, name="uninstall", help="🗑️ Uninstall MyAI components")
    app.add_typer(config_cli.app, name="config", help="📝 Configuration management commands")
    app.add_typer(agent_cli.app, name="agent")
    app.add_typer(system_cli.app, name="system", help="🔧 System utilities, integrations, and diagnostics")
    app.add_typer(wizard_cli.app, name="wizard", help="🧙 Interactive wizards and guided workflows")
    return app


def main():
    """Main entry point for the CLI application."""
    # Create and launch the application
    app = create_app()
    app()


if __name__ == "__main__":
    main()
