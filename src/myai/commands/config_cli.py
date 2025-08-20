"""
Configuration management CLI commands.

This module provides CLI commands for managing MyAI configurations,
including reading, writing, and validating configuration files.
"""

from typing import Optional

import typer
from rich.console import Console

from myai.cli.formatters import get_formatter
from myai.cli.state import AppState
from myai.config.manager import get_config_manager

# Create config command group
app = typer.Typer(help="📝 Configuration management commands")
console = Console()


@app.command()
def show(
    ctx: typer.Context,
    _level: Optional[str] = typer.Option(
        None, "--level", "-l", help="Configuration level (enterprise, user, team, project)"
    ),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Specific configuration key to show"),
    output_fmt: Optional[str] = typer.Option(None, "--format", "-f", help="Output format (vertical, json, table)"),
):
    """Show current configuration."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Loading configuration...[/dim]")

    try:
        config_manager = get_config_manager()

        if key:
            # Show specific key
            value = config_manager.get_config_value(key)
            # Use specified format or default to vertical for better display
            if output_fmt:
                output_format = output_fmt
            else:
                output_format = "vertical" if state.output_format == "table" else state.output_format
            formatter = get_formatter(output_format, console)
            formatter.format({key: value}, title=f"Configuration: {key}")
        else:
            # Show all configuration
            config = config_manager.get_config()
            # Use specified format or default to vertical for better display
            if output_fmt:
                output_format = output_fmt
            else:
                output_format = "vertical" if state.output_format == "table" else state.output_format
            formatter = get_formatter(output_format, console)
            formatter.format(config.model_dump(), title="Current Configuration")

    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def get(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key to retrieve"),
):
    """Get a specific configuration value."""
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        value = config_manager.get_config_value(key)

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            formatter.format({key: value})
        else:
            console.print(f"{key}: {value}")

    except Exception as e:
        console.print(f"[red]Error getting configuration value: {e}[/red]")
        if state.is_debug():
            raise


@app.command(name="set")
def set_value(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Configuration value to set"),
    level: str = typer.Option("user", "--level", "-l", help="Configuration level to modify"),
):
    """Set a configuration value."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Setting {key}={value} at {level} level[/dim]")

    try:
        config_manager = get_config_manager()
        config_manager.set_config_value(key, value, level)

        console.print(f"✅ Set {key} = {value} at {level} level")

    except Exception as e:
        console.print(f"[red]Error setting configuration value: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def validate(ctx: typer.Context):
    """Validate current configuration."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Validating configuration...[/dim]")

    try:
        config_manager = get_config_manager()
        issues = config_manager.validate_configuration()

        if not issues:
            console.print("✅ Configuration is valid")
        else:
            console.print(f"❌ Found {len(issues)} configuration issues:")
            for issue in issues:
                console.print(f"  • {issue}")

    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def reset(
    ctx: typer.Context,
    level: str = typer.Option("user", "--level", "-l", help="Configuration level to reset"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),  # noqa: FBT001
):
    """Reset configuration to defaults."""
    state: AppState = ctx.obj

    if not confirm:
        if not typer.confirm(f"Are you sure you want to reset {level} configuration?"):
            console.print("Operation cancelled")
            return

    if state.is_debug():
        console.print(f"[dim]Resetting {level} configuration...[/dim]")

    try:
        config_manager = get_config_manager()
        config_manager.reset_configuration(level)

        console.print(f"✅ Reset {level} configuration to defaults")

    except Exception as e:
        console.print(f"[red]Error resetting configuration: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def agents(
    ctx: typer.Context,
    action: str = typer.Argument(None, help="Action: enable, disable, list"),
    names: Optional[list[str]] = typer.Argument(None, help="Agent names for enable/disable"),
):
    """Manage agent configuration (enable/disable agents)."""
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()

        if not action or action == "list":
            # Show current agent configuration
            console.print("\n[bold]Agent Configuration:[/bold]")

            if config.agents.enabled:
                console.print("\n[green]Explicitly Enabled:[/green]")
                for name in sorted(config.agents.enabled):
                    console.print(f"  ✅ {name}")
            else:
                console.print("\n[dim]No explicitly enabled agents[/dim]")

            if config.agents.disabled:
                console.print("\n[red]Explicitly Disabled:[/red]")
                for name in sorted(config.agents.disabled):
                    console.print(f"  ❌ {name}")
            else:
                console.print("[dim]No explicitly disabled agents[/dim]")

            console.print(f"\n[dim]Auto-discover: {config.agents.auto_discover}[/dim]")
            if config.agents.custom_path:
                console.print(f"[dim]Custom path: {config.agents.custom_path}[/dim]")

        elif action == "enable":
            if not names:
                console.print("[red]Error: No agent names provided[/red]")
                return

            enabled_count = 0
            for name in names:
                # Remove from disabled list if present
                if name in config.agents.disabled:
                    config.agents.disabled.remove(name)

                # Add to enabled list if not already there
                if name not in config.agents.enabled:
                    config.agents.enabled.append(name)
                    enabled_count += 1

            # Save config
            config_manager.set_config_value("agents.enabled", config.agents.enabled)
            config_manager.set_config_value("agents.disabled", config.agents.disabled)
            console.print(f"✅ Enabled {enabled_count} agent(s)")

        elif action == "disable":
            if not names:
                console.print("[red]Error: No agent names provided[/red]")
                return

            disabled_count = 0
            for name in names:
                # Remove from enabled list if present
                if name in config.agents.enabled:
                    config.agents.enabled.remove(name)

                # Add to disabled list if not already there
                if name not in config.agents.disabled:
                    config.agents.disabled.append(name)
                    disabled_count += 1

            # Save config
            config_manager.set_config_value("agents.enabled", config.agents.enabled)
            config_manager.set_config_value("agents.disabled", config.agents.disabled)
            console.print(f"✅ Disabled {disabled_count} agent(s)")

        else:
            console.print(f"[red]Unknown action: {action}[/red]")
            console.print("Valid actions: list, enable, disable")

    except Exception as e:
        console.print(f"[red]Error managing agent configuration: {e}[/red]")
        if state.is_debug():
            raise
