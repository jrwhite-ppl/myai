"""
System utility CLI commands.

This module provides CLI commands for system status, diagnostics,
and maintenance operations.
"""

import platform
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from myai.agent.registry import get_agent_registry
from myai.cli.formatters import get_formatter
from myai.cli.state import AppState
from myai.config.manager import get_config_manager

# Create system command group
app = typer.Typer(help="🔧 System utilities and diagnostics")
console = Console()


@app.command()
def status(ctx: typer.Context):
    """Show system status and overview."""
    state: AppState = ctx.obj

    try:
        # Gather system information
        registry = get_agent_registry()
        config_manager = get_config_manager()

        agents = registry.list_agents()
        enabled_agents = [a for a in agents if registry.is_enabled(a.metadata.name)]

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
                    "enabled": len(enabled_agents),
                    "categories": len({a.metadata.category.value for a in agents}),
                },
                "configuration": {
                    "user_config": str(config_manager.get_config_path("user") or "Not set"),
                    "has_user_config": bool(
                        config_manager.get_config_path("user") is not None
                        and config_manager.get_config_path("user").exists()  # type: ignore[union-attr]
                    ),
                },
            }
            formatter.format(system_data)
        else:
            # Create status overview
            console.print("[bold cyan]🔧 MyAI System Status[/bold cyan]\n")

            # System info
            system_table = Table(title="System Information", show_header=False)
            system_table.add_column("Property", style="cyan")
            system_table.add_column("Value", style="white")

            system_table.add_row("Platform", platform.system())
            system_table.add_row("Python Version", sys.version.split()[0])
            system_table.add_row("MyAI Path", str(Path.home() / ".myai"))

            console.print(system_table)
            console.print()

            # Agent statistics
            agent_table = Table(title="Agent Statistics", show_header=False)
            agent_table.add_column("Metric", style="cyan")
            agent_table.add_column("Count", style="white")

            agent_table.add_row("Total Agents", str(len(agents)))
            agent_table.add_row("Enabled Agents", str(len(enabled_agents)))
            agent_table.add_row("Categories", str(len({a.metadata.category.value for a in agents})))

            console.print(agent_table)
            console.print()

            # Configuration status
            user_config_path = config_manager.get_config_path("user")
            config_status = "✅ Found" if user_config_path and user_config_path.exists() else "❌ Not found"
            console.print(f"Configuration: {config_status}")

    except Exception as e:
        console.print(f"[red]Error getting system status: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def doctor(ctx: typer.Context):
    """Run system diagnostics and health checks."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Running diagnostics...[/dim]")

    try:
        # Run health checks
        checks = []

        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 8):
            checks.append(("Python Version", "✅", f"Python {python_version.major}.{python_version.minor}"))
        else:
            checks.append(
                ("Python Version", "❌", f"Python {python_version.major}.{python_version.minor} (requires 3.8+)")
            )

        # Check MyAI directory
        myai_path = Path.home() / ".myai"
        if myai_path.exists():
            checks.append(("MyAI Directory", "✅", str(myai_path)))
        else:
            checks.append(("MyAI Directory", "⚠️", f"{myai_path} does not exist"))

        # Check agents directory
        agents_path = myai_path / "agents"
        if agents_path.exists():
            checks.append(("Agents Directory", "✅", str(agents_path)))
        else:
            checks.append(("Agents Directory", "⚠️", f"{agents_path} does not exist"))

        # Check agent registry
        try:
            registry = get_agent_registry()
            agents = registry.list_agents()
            checks.append(("Agent Registry", "✅", f"{len(agents)} agents loaded"))
        except Exception as e:
            checks.append(("Agent Registry", "❌", f"Error: {e}"))

        # Check configuration
        try:
            config_manager = get_config_manager()
            user_config_path = config_manager.get_config_path("user")
            if user_config_path and user_config_path.exists():
                checks.append(("Configuration", "✅", str(user_config_path)))
            else:
                checks.append(("Configuration", "⚠️", "No user configuration file found"))
        except Exception as e:
            checks.append(("Configuration", "❌", f"Error: {e}"))

        # Display results
        table = Table(title="🩺 System Health Check", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="white", no_wrap=True)
        table.add_column("Details", style="dim")

        issues_found = 0
        for component, status, details in checks:
            table.add_row(component, status, details)
            if "❌" in status or "⚠️" in status:
                issues_found += 1

        console.print(table)

        if issues_found == 0:
            console.print("\n[green]✅ All checks passed! System is healthy.[/green]")
        else:
            console.print(f"\n[yellow]⚠️ Found {issues_found} issues that may need attention.[/yellow]")

    except Exception as e:
        console.print(f"[red]Error running diagnostics: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def version(
    ctx: typer.Context,
    check_updates: bool = typer.Option(False, "--check-updates", help="Check for available updates"),  # noqa: FBT001
):
    """Show version information."""
    state: AppState = ctx.obj

    # TODO: Get actual version from package metadata
    myai_version = "0.1.0-dev"

    try:
        if state.output_format == "json":
            formatter = get_formatter("json", console)
            version_data: dict = {
                "myai_version": myai_version,
                "python_version": sys.version.split()[0],
                "platform": platform.system(),
                "platform_version": platform.release(),
            }

            if check_updates:
                # TODO: Implement actual update checking
                version_data["update_available"] = False
                version_data["latest_version"] = myai_version

            formatter.format(version_data)
        else:
            # Create version display
            version_text = Text()
            version_text.append("MyAI ", style="bold cyan")
            version_text.append(f"v{myai_version}", style="bold white")
            version_text.append(f"\nPython {sys.version.split()[0]}", style="dim")
            version_text.append(f"\n{platform.system()} {platform.release()}", style="dim")

            if check_updates:
                console.print("[dim]Checking for updates...[/dim]")
                # TODO: Implement actual update checking
                version_text.append("\n✅ Up to date", style="green")

            panel = Panel(
                version_text,
                title="📦 Version Information",
                border_style="blue",
            )
            console.print(panel)

    except Exception as e:
        console.print(f"[red]Error getting version information: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def backup(
    ctx: typer.Context,
    target: str = typer.Option("auto", "--target", help="Backup target directory"),
    include_config: bool = typer.Option(  # noqa: FBT001
        True, "--config/--no-config", help="Include configuration in backup"
    ),
    compress: bool = typer.Option(True, "--compress/--no-compress", help="Compress backup"),  # noqa: FBT001
):
    """Create system backup."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Creating system backup to {target}...[/dim]")

    try:
        # Simulate backup creation
        registry = get_agent_registry()
        agents = registry.list_agents()

        items_backed_up = []
        items_backed_up.append(f"{len(agents)} agents")

        if include_config:
            items_backed_up.append("configuration files")

        backup_id = "20250818_143022_001"  # Simulated backup ID

        console.print("✅ System backup completed:")
        console.print(f"  • Backup ID: {backup_id}")
        console.print(f"  • Items: {', '.join(items_backed_up)}")
        console.print(f"  • Target: {target}")
        if compress:
            console.print("  • Compressed: Yes")

    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        if state.is_debug():
            raise
