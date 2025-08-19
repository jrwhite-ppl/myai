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
    """Show system status and health check."""
    state: AppState = ctx.obj

    if state.debug:
        console.print("[dim]Running status check...[/dim]")

    # Create status table
    table = Table(title="🔍 MyAI System Status", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    # Add status rows (placeholder for now)
    table.add_row("Configuration", "✅ OK", "Config loaded successfully")
    table.add_row("Agent Registry", "✅ OK", "Registry initialized")
    table.add_row("Storage", "✅ OK", "File system accessible")
    table.add_row("Templates", "✅ OK", "4 default templates loaded")

    console.print(table)


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
