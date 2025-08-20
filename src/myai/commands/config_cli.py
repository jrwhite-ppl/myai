"""
Configuration management CLI commands.

This module provides CLI commands for managing MyAI configurations,
including reading, writing, and validating configuration files.
"""

from typing import Any, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from myai.cli.formatters import get_formatter
from myai.cli.state import AppState
from myai.config.manager import get_config_manager

# Create config command group
app = typer.Typer(help="📝 Configuration management commands")
console = Console()

# Constants
MAX_LIST_DISPLAY = 3


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
def diff(
    ctx: typer.Context,
    source: str = typer.Argument("user", help="Source configuration level (user, project, default)"),
    target: str = typer.Argument("project", help="Target configuration level to compare against"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Specific configuration key to compare"),
    show_identical: bool = typer.Option(False, "--show-identical", help="Show identical values"),  # noqa: FBT001
):
    """Compare configurations between different levels."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Comparing {source} vs {target} configuration...[/dim]")

    try:
        config_manager = get_config_manager()

        # Get configurations
        if source == "default":
            # Get empty config to compare against (acts as default)
            from myai.models.config import MyAIConfig

            source_config = MyAIConfig()
        else:
            source_config = config_manager.get_config([source])

        if target == "default":
            # Get empty config to compare against (acts as default)
            from myai.models.config import MyAIConfig

            target_config = MyAIConfig()
        else:
            target_config = config_manager.get_config([target])

        # Convert to dictionaries
        source_dict: Dict[str, Any] = source_config.model_dump() if hasattr(source_config, "model_dump") else {}
        target_dict: Dict[str, Any] = target_config.model_dump() if hasattr(target_config, "model_dump") else {}

        # If specific key requested, extract just that part
        if key:
            source_val = _get_nested_value(source_dict, key)
            target_val = _get_nested_value(target_dict, key)

            if source_val is None or target_val is None:
                console.print(f"[red]Key '{key}' not found in one or both configurations[/red]")
                return

            # Create new dicts with just the requested key for comparison
            source_dict = {key: source_val}
            target_dict = {key: target_val}

        # Compare configurations
        differences = _compare_dicts(source_dict, target_dict)

        if not differences and not show_identical:
            console.print(f"[green]✅ No differences found between {source} and {target} configurations[/green]")
            return

        # Display differences
        table = Table(
            title=f"Configuration Comparison: {source} vs {target}", show_header=True, header_style="bold magenta"
        )
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column(f"{source.capitalize()}", style="yellow")
        table.add_column(f"{target.capitalize()}", style="green")
        table.add_column("Status", style="white")

        # Add rows for differences
        for diff_key, (source_val, target_val, status) in sorted(differences.items()):
            if status != "identical" or show_identical:
                status_display = {
                    "different": "≠ Different",
                    "added": "+ Added",
                    "removed": "- Removed",
                    "identical": "= Same",
                }.get(status, status)

                # Format values for display
                source_str = _format_value(source_val) if source_val is not None else "[dim]not set[/dim]"
                target_str = _format_value(target_val) if target_val is not None else "[dim]not set[/dim]"

                # Apply styling based on status
                if status == "removed":
                    source_str = f"[red]{source_str}[/red]"
                elif status == "added":
                    target_str = f"[green]{target_str}[/green]"

                table.add_row(diff_key, source_str, target_str, status_display)

        console.print(table)

        # Summary
        diff_count = sum(1 for _, (_, _, status) in differences.items() if status != "identical")
        if diff_count > 0:
            console.print(f"\n[yellow]Found {diff_count} differences[/yellow]")

    except Exception as e:
        console.print(f"[red]Error comparing configurations: {e}[/red]")
        if state.is_debug():
            raise


def _get_nested_value(data: dict, key: str):
    """Get a nested value from a dictionary using dot notation."""
    keys = key.split(".")
    value = data

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None

    return value


def _compare_dicts(source: dict, target: dict, prefix: str = "") -> dict:
    """Compare two dictionaries and return differences."""
    differences = {}

    # Get all keys from both dicts
    all_keys = set(source.keys()) | set(target.keys())

    for key in all_keys:
        full_key = f"{prefix}.{key}" if prefix else key
        source_val = source.get(key)
        target_val = target.get(key)

        if key not in source:
            differences[full_key] = (None, target_val, "added")
        elif key not in target:
            differences[full_key] = (source_val, None, "removed")
        elif isinstance(source_val, dict) and isinstance(target_val, dict):
            # Recursively compare nested dicts
            nested_diffs = _compare_dicts(source_val, target_val, full_key)
            differences.update(nested_diffs)
        elif source_val != target_val:
            differences[full_key] = (source_val, target_val, "different")
        else:
            differences[full_key] = (source_val, target_val, "identical")

    return differences


def _format_value(value) -> str:
    """Format a value for display."""
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return "[]"
        elif len(value) <= MAX_LIST_DISPLAY:
            return f"[{', '.join(str(v) for v in value)}]"
        else:
            return f"[{', '.join(str(v) for v in value[:MAX_LIST_DISPLAY])}, ... ({len(value)} items)]"
    elif isinstance(value, dict):
        if len(value) == 0:
            return "{}"
        else:
            return f"{{...}} ({len(value)} keys)"
    elif isinstance(value, bool):
        return str(value).lower()
    elif value is None:
        return "null"
    else:
        return str(value)
