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
    """Get a specific configuration value.

    This command retrieves configuration values using dot notation.

    Examples:
      myai config get agents.enabled           # Get enabled agents list
      myai config get integrations.claude      # Get Claude configuration
      myai config get agents.global_enabled    # Get globally enabled agents

    Related commands:
      myai config set <key> <value>    # Set configuration value
      myai config show                 # Show all configuration
    """
    state: AppState = ctx.obj

    try:
        config_manager = get_config_manager()
        value = config_manager.get_config_value(key)

        if state.output_format == "json":
            formatter = get_formatter("json", console)
            formatter.format({key: value})
        elif isinstance(value, list):
            if value:
                console.print(f"[bold]{key}:[/bold]")
                for item in value:
                    console.print(f"  • {item}")
            else:
                console.print(f"[bold]{key}:[/bold] [dim](empty list)[/dim]")
        elif isinstance(value, dict):
            console.print(f"[bold]{key}:[/bold]")
            for k, v in value.items():
                console.print(f"  {k}: {v}")
        else:
            console.print(f"[bold]{key}:[/bold] {value}")

    except Exception as e:
        console.print(f"[red]Error getting configuration value: {e}[/red]")
        console.print("[dim]Use 'myai config show' to see available configuration keys[/dim]")
        if state.is_debug():
            raise


@app.command(name="set")
def set_value(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key to set"),
    value: str = typer.Argument(..., help="Configuration value to set"),
    level: str = typer.Option("user", "--level", "-l", help="Configuration level to modify"),
):
    """Set a configuration value.

    This command sets configuration values using dot notation.
    The value will be automatically parsed to the correct type.

    Examples:
      myai config set agents.enabled "['python-expert','security-analyst']"  # Set list
      myai config set integrations.claude.enabled true                       # Set boolean
      myai config set user.name "John Doe"                                   # Set string

    Related commands:
      myai config get <key>        # Get configuration value
      myai config show             # Show all configuration
      myai config validate         # Validate configuration
    """
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Setting {key}={value} at {level} level[/dim]")

    try:
        config_manager = get_config_manager()

        # Get previous value for comparison
        try:
            previous_value = config_manager.get_config_value(key)
        except Exception:
            previous_value = None

        config_manager.set_config_value(key, value, level)

        console.print("✅ Configuration updated successfully")
        console.print(f"[bold]Key:[/bold] {key}")
        console.print(f"[bold]Level:[/bold] {level}")
        if previous_value is not None:
            console.print(f"[bold]Previous:[/bold] {previous_value}")
        console.print(f"[bold]New Value:[/bold] {value}")
        console.print(f"\n[dim]Use 'myai config get {key}' to verify the change[/dim]")

    except Exception as e:
        console.print(f"[red]Error setting configuration value: {e}[/red]")
        console.print("[dim]Use 'myai config show' to see available configuration keys[/dim]")
        if state.is_debug():
            raise


@app.command()
def validate(ctx: typer.Context):
    """Validate current configuration.

    This command performs comprehensive validation of your MyAI configuration
    files, checking for syntax errors, required fields, and configuration
    consistency across all levels.

    Validation checks include:
    - Configuration file syntax and format
    - Required configuration fields
    - Agent references and availability
    - Integration settings validity
    - Path existence and permissions
    - Value type and range validation

    Examples:
      myai config validate              # Validate all configuration

    Related commands:
      myai config show                 # View current configuration
      myai config set <key> <value>   # Fix configuration issues
      myai status                      # Check overall system status
    """
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Validating configuration...[/dim]")

    try:
        config_manager = get_config_manager()

        console.print("[bold]🔍 Configuration Validation[/bold]")
        console.print("[dim]Checking: Syntax, Required Fields, Agent References, Integrations, Paths[/dim]\n")

        # Get validation results
        issues = config_manager.validate_configuration()

        # Get configuration paths for context
        user_config_path = config_manager.get_config_path("user")
        project_config_path = config_manager.get_config_path("project")

        # Create validation summary table
        validation_table = Table(title="Validation Results", show_header=True, header_style="bold magenta")
        validation_table.add_column("Check", style="cyan", no_wrap=True)
        validation_table.add_column("Status", justify="center")
        validation_table.add_column("Details", style="dim")

        # Add configuration file checks
        if user_config_path and user_config_path.exists():
            validation_table.add_row("User Config", "✅ Found", str(user_config_path))
        else:
            validation_table.add_row("User Config", "⚠️  Missing", "Using default values")

        if project_config_path and project_config_path.exists():
            validation_table.add_row("Project Config", "✅ Found", str(project_config_path))
        else:
            validation_table.add_row("Project Config", "⚠️  Missing", "No project-specific settings")

        # Add syntax validation
        config = config_manager.get_config()
        if config:
            validation_table.add_row("Config Syntax", "✅ Valid", "All configuration files parse correctly")
        else:
            validation_table.add_row("Config Syntax", "❌ Invalid", "Configuration parsing failed")

        # Add agent references check
        try:
            enabled_count = len(config.agents.enabled) if config and config.agents else 0
            global_enabled_count = len(getattr(config.agents, "global_enabled", [])) if config and config.agents else 0
            total_enabled = enabled_count + global_enabled_count
            if total_enabled > 0:
                validation_table.add_row("Agent References", "✅ Valid", f"{total_enabled} agents configured")
            else:
                validation_table.add_row("Agent References", "⚠️  Empty", "No agents enabled")
        except Exception:
            validation_table.add_row("Agent References", "❌ Error", "Could not validate agent references")

        console.print(validation_table)
        console.print()

        if not issues:
            console.print("✅ Configuration validation passed")
            console.print("[dim]All checks completed successfully - your configuration is ready to use[/dim]")
        else:
            console.print(f"❌ Found {len(issues)} configuration issues:")
            console.print()
            for i, issue in enumerate(issues, 1):
                console.print(f"  {i}. {issue}")
            console.print()
            console.print(
                "[dim]Fix these issues using 'myai config set <key> <value>' or by editing config files directly[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        console.print("[dim]This may indicate a corrupted configuration file or system issue[/dim]")
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
