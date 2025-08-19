"""
Integration management CLI commands.

This module provides CLI commands for managing tool integrations,
including sync, health checks, and configuration management.
"""

import asyncio
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from myai.cli.state import AppState
from myai.integrations import IntegrationManager

# Create integration command group
app = typer.Typer(help="🔗 Tool integration management commands")
console = Console()


def run_async(coro):
    """Helper to run async functions in sync CLI commands."""
    return asyncio.run(coro)


@app.command(name="list")
def list_integrations(
    ctx: typer.Context,
    available: bool = typer.Option(False, "--available", help="Show available integrations"),  # noqa: FBT001
    status: bool = typer.Option(True, "--status", help="Show integration status"),  # noqa: FBT001
):
    """List available and active integrations."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Loading integrations...[/dim]")

    try:
        manager = IntegrationManager()

        if available:
            # Show available integrations (discovery)
            from myai.integrations.factory import get_adapter_factory

            factory = get_adapter_factory()

            console.print("🔍 [bold cyan]Discovering available integrations...[/bold cyan]")
            discovered = run_async(factory.discover_adapters())

            if not discovered:
                console.print("[dim]No integrations found[/dim]")
                return

            # Create table
            table = Table(title="🔗 Available Integrations", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Display Name", style="white")
            table.add_column("Status", style="green")
            table.add_column("Version", style="dim")
            table.add_column("Path", style="dim")

            for name, info in discovered.items():
                if "error" in info:
                    status_text = f"[red]Error: {info['error']}[/red]"
                    version = "N/A"
                    path = "N/A"
                else:
                    status_text = f"[green]{info['status']}[/green]"
                    version = info.get("tool_version", "unknown")
                    path = info.get("installation_path", "unknown")

                table.add_row(
                    name,
                    info.get("display_name", name),
                    status_text,
                    version,
                    path,
                )

            console.print(table)

        if status:
            # Show active integration status
            active_adapters = manager.list_adapters()

            if not active_adapters:
                console.print("[dim]No active integrations[/dim]")
                return

            console.print("📊 [bold cyan]Getting integration status...[/bold cyan]")
            status_info = run_async(manager.get_adapter_status())

            # Create status table
            table = Table(title="📊 Integration Status", show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Status", style="white")
            table.add_column("Tool", style="green")
            table.add_column("Version", style="dim")
            table.add_column("Last Sync", style="dim")

            for name, info in status_info.items():
                if "error" in info:
                    status_text = f"[red]Error: {info['error']}[/red]"
                    tool_name = "Unknown"
                    version = "N/A"
                    last_sync = "N/A"
                else:
                    status_color = {
                        "configured": "green",
                        "connected": "green",
                        "available": "yellow",
                        "error": "red",
                        "disabled": "dim",
                    }.get(info["status"], "white")
                    status_text = f"[{status_color}]{info['status']}[/{status_color}]"
                    tool_name = info.get("tool_name", "Unknown")
                    version = info.get("tool_version", "unknown")
                    last_sync = info.get("last_sync", "never")

                table.add_row(name, status_text, tool_name, version, last_sync)

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error listing integrations: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def health(
    ctx: typer.Context,
    integration: Optional[str] = typer.Argument(None, help="Specific integration to check"),
):
    """Perform health checks on integrations."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Running health checks...[/dim]")

    try:
        manager = IntegrationManager()

        # Initialize integrations first
        if state.is_debug():
            console.print("[dim]Initializing integrations...[/dim]")
        run_async(manager.initialize())

        if integration:
            # Check specific integration
            if integration not in manager.list_adapters():
                console.print(f"[red]Integration '{integration}' not found or not active[/red]")
                return

            console.print(f"🔍 Checking health of {integration}...")
            health_info = run_async(manager.health_check(integration))

            _display_health_results({integration: health_info[integration]})
        else:
            # Check all integrations
            console.print("🔍 Checking health of all integrations...")
            health_info = run_async(manager.health_check())

            if not health_info:
                console.print("[dim]No active integrations to check[/dim]")
                return

            _display_health_results(health_info)

    except Exception as e:
        console.print(f"[red]Error during health check: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def sync(
    ctx: typer.Context,
    integration: Optional[List[str]] = typer.Option(
        None, "--integration", "-i", help="Specific integration(s) to sync"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be synced"),  # noqa: FBT001
    force: bool = typer.Option(False, "--force", help="Force sync even with warnings"),  # noqa: FBT001
):
    """Sync agents to tool integrations."""
    _ = force  # Mark as intentionally unused for now
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Syncing agents (dry-run: {dry_run})...[/dim]")

    try:
        manager = IntegrationManager()

        # Initialize integrations first
        if state.is_debug():
            console.print("[dim]Initializing integrations...[/dim]")
        run_async(manager.initialize())

        if integration:
            # Validate specified integrations
            active_adapters = manager.list_adapters()
            invalid_integrations = [i for i in integration if i not in active_adapters]

            if invalid_integrations:
                console.print(f"[red]Invalid integrations: {', '.join(invalid_integrations)}[/red]")
                return

        # Get agents to sync
        from myai.agent.registry import get_agent_registry

        registry = get_agent_registry()
        agents = registry.list_agents()

        if not agents:
            console.print("[dim]No agents found to sync[/dim]")
            return

        console.print(f"🔄 Syncing {len(agents)} agents...")
        if dry_run:
            console.print("[yellow]Dry run - no changes will be made[/yellow]")

        # Perform sync
        results = run_async(manager.sync_agents(agents, integration, dry_run=dry_run))

        # Display results
        _display_sync_results(results, dry_run=dry_run)

    except Exception as e:
        console.print(f"[red]Error during sync: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def import_agents(
    ctx: typer.Context,
    integration: Optional[List[str]] = typer.Option(
        None, "--integration", "-i", help="Specific integration(s) to import from"
    ),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before import"),  # noqa: FBT001
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing agents"),  # noqa: FBT001
):
    """Import agents from tool integrations."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Importing agents...[/dim]")

    try:
        manager = IntegrationManager()

        if integration:
            # Validate specified integrations
            active_adapters = manager.list_adapters()
            invalid_integrations = [i for i in integration if i not in active_adapters]

            if invalid_integrations:
                console.print(f"[red]Invalid integrations: {', '.join(invalid_integrations)}[/red]")
                return

        console.print("📥 Importing agents from integrations...")

        # Create backup if requested
        if backup:
            console.print("[dim]Creating backup...[/dim]")
            backup_results = run_async(manager.backup_configurations(integration))
            backup_count = sum(1 for path in backup_results.values() if path is not None)
            console.print(f"✅ Created {backup_count} backups")

        # Import agents
        imported = run_async(manager.import_agents(integration))

        # Display results
        total_imported = 0
        for adapter_name, agents in imported.items():
            count = len(agents)
            total_imported += count
            console.print(f"  • {adapter_name}: {count} agents")

            if state.is_debug() and agents:
                preview_limit = 3  # Number of agents to preview
                for agent in agents[:preview_limit]:
                    console.print(f"    - {agent.get('name', 'unnamed')}")
                if len(agents) > preview_limit:
                    console.print(f"    ... and {len(agents) - preview_limit} more")

        if total_imported == 0:
            console.print("[dim]No agents imported[/dim]")
        else:
            console.print(f"✅ [green]Imported {total_imported} agents successfully[/green]")

            if merge:
                console.print("[dim]Use 'myai agent list' to see imported agents[/dim]")

    except Exception as e:
        console.print(f"[red]Error importing agents: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def validate(
    ctx: typer.Context,
    integration: Optional[str] = typer.Argument(None, help="Specific integration to validate"),
):
    """Validate integration configurations."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Validating configurations...[/dim]")

    try:
        manager = IntegrationManager()

        if integration:
            integrations_to_validate = [integration]
        else:
            integrations_to_validate = manager.list_adapters()

        if not integrations_to_validate:
            console.print("[dim]No integrations to validate[/dim]")
            return

        console.print("✅ Validating integration configurations...")

        results = run_async(manager.validate_configurations(integrations_to_validate))

        # Display results
        has_errors = False
        for adapter_name, errors in results.items():
            if errors:
                has_errors = True
                console.print(f"❌ [red]{adapter_name}[/red]:")
                for error in errors:
                    console.print(f"  • {error}")
            else:
                console.print(f"✅ [green]{adapter_name}[/green]: Configuration valid")

        if not has_errors:
            console.print("[green]All configurations are valid![/green]")

    except Exception as e:
        console.print(f"[red]Error validating configurations: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def backup(
    ctx: typer.Context,
    integration: Optional[List[str]] = typer.Option(
        None, "--integration", "-i", help="Specific integration(s) to backup"
    ),
    backup_dir: Optional[Path] = typer.Option(None, "--backup-dir", help="Custom backup directory"),
):
    """Create backups of integration configurations."""
    _ = backup_dir  # Mark as intentionally unused for now
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Creating backups...[/dim]")

    try:
        manager = IntegrationManager()

        if integration:
            # Validate specified integrations
            active_adapters = manager.list_adapters()
            invalid_integrations = [i for i in integration if i not in active_adapters]

            if invalid_integrations:
                console.print(f"[red]Invalid integrations: {', '.join(invalid_integrations)}[/red]")
                return

        console.print("💾 Creating configuration backups...")

        results = run_async(manager.backup_configurations(integration))

        # Display results
        success_count = 0
        for adapter_name, backup_path in results.items():
            if backup_path:
                success_count += 1
                console.print(f"✅ {adapter_name}: {backup_path}")
            else:
                console.print(f"❌ {adapter_name}: Backup failed")

        if success_count == 0:
            console.print("[red]No backups created[/red]")
        else:
            console.print(f"✅ [green]Created {success_count} backups successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error creating backups: {e}[/red]")
        if state.is_debug():
            raise


def _display_health_results(health_info: dict):
    """Display health check results in a formatted way."""
    for adapter_name, health in health_info.items():
        # Determine overall status color
        status = health.get("status", "unknown")
        status_color = {
            "healthy": "green",
            "unhealthy": "red",
            "warning": "yellow",
        }.get(status, "white")

        # Create health panel
        health_text = Text()
        health_text.append("Status: ", style="bold")
        health_text.append(f"{status}\n", style=f"bold {status_color}")
        health_text.append(f"Timestamp: {health.get('timestamp', 'unknown')}\n")

        # Add check details
        checks = health.get("checks", {})
        if checks:
            health_text.append("\nChecks:\n", style="bold")
            for check_name, check_info in checks.items():
                check_status = check_info.get("status", "unknown")
                check_color = {
                    "pass": "green",
                    "fail": "red",
                    "warning": "yellow",
                }.get(check_status, "white")

                health_text.append(f"  • {check_name}: ", style="dim")
                health_text.append(f"{check_status}", style=check_color)

                if "message" in check_info:
                    health_text.append(f" - {check_info['message']}", style="dim")
                health_text.append("\n")

        # Add errors and warnings
        errors = health.get("errors", [])
        warnings = health.get("warnings", [])

        if errors:
            health_text.append("\nErrors:\n", style="bold red")
            for error in errors:
                health_text.append(f"  • {error}\n", style="red")

        if warnings:
            health_text.append("\nWarnings:\n", style="bold yellow")
            for warning in warnings:
                health_text.append(f"  • {warning}\n", style="yellow")

        panel = Panel(
            health_text,
            title=f"🔍 Health Check: {adapter_name}",
            border_style=status_color,
        )
        console.print(panel)


def _display_sync_results(results: dict, *, dry_run: bool = False):
    """Display sync results in a formatted way."""
    # Create results table
    table = Table(
        title=f"🔄 Sync Results{'(Dry Run)' if dry_run else ''}", show_header=True, header_style="bold magenta"
    )
    table.add_column("Integration", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Synced", style="green")
    table.add_column("Skipped", style="yellow")
    table.add_column("Errors", style="red")

    total_synced = 0
    total_errors = 0

    for adapter_name, result in results.items():
        status = result.get("status", "unknown")
        synced = result.get("synced", 0)
        skipped = result.get("skipped", 0)
        errors = len(result.get("errors", []))

        total_synced += synced
        total_errors += errors

        # Status color
        status_color = {
            "success": "green",
            "partial": "yellow",
            "error": "red",
        }.get(status, "white")

        table.add_row(
            adapter_name,
            f"[{status_color}]{status}[/{status_color}]",
            str(synced),
            str(skipped),
            str(errors),
        )

    console.print(table)

    # Show error details if any
    for adapter_name, result in results.items():
        errors = result.get("errors", [])
        warnings = result.get("warnings", [])

        if errors or warnings:
            console.print(f"\n[bold]{adapter_name} Details:[/bold]")

            for error in errors:
                console.print(f"  [red]Error:[/red] {error}")

            for warning in warnings:
                console.print(f"  [yellow]Warning:[/yellow] {warning}")

    # Summary
    if total_synced > 0:
        console.print(f"\n✅ [green]Total synced: {total_synced}[/green]")
    if total_errors > 0:
        console.print(f"❌ [red]Total errors: {total_errors}[/red]")

    # Show project-level message for Cursor
    for adapter_name, result in results.items():
        if adapter_name == "cursor" and "message" in result:
            console.print(f"\n[cyan]Info: {result['message']}[/cyan]")
