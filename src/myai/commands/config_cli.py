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

help_text = """📝 Configuration management - Control agents, IDE integrations, and system behavior

MyAI uses hierarchical configuration: Enterprise → User → Team → Project

Key areas:
  • agents.*        - Enable/disable agents (project vs global scope)
  • tools.*         - IDE integrations (Claude Code, Cursor, auto-sync)
  • integrations.*  - Sync timing, conflict resolution
  • settings.*      - Debug, backups, caching

Essential commands:
  myai config show                              # View current config
  myai config get agents.enabled               # Check enabled agents
  myai config set tools.claude.enabled false   # Disable Claude integration
  myai config list-keys                        # See all available settings
  myai config validate                          # Check for issues

Config files: ~/.myai/config/user.json (personal), .myai/config/project.json (project)
Changes auto-sync to IDE integrations (.claude/, .cursor/)"""

app = typer.Typer(
    help=help_text,
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help", "help"]},
)
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
    """SHOW commands/config_cli.py show TEST                      # See configuration status"""
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

    Key configuration areas:
      agents.*        - Agent enablement (enabled, disabled, global_enabled, auto_discover)
      tools.*         - IDE integrations (claude.enabled, cursor.enabled, auto_sync)
      integrations.*  - Sync behavior (auto_sync_interval, conflict_resolution)
      settings.*      - System behavior (debug, backup_enabled, cache_enabled)

    Examples:
      myai config get agents.enabled               # See enabled agents
      myai config get tools.claude.enabled         # Check Claude integration
      myai config get settings.debug               # Check debug mode

    Related commands:
      myai config set <key> <value>    # Change configuration value
      myai config list-keys            # See all available keys with details
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

    This command sets configuration values using dot notation. Changes are
    immediately applied and synced to your IDE integrations.

    Common examples:
      myai config set agents.enabled "['python-expert','security-analyst']"  # Enable agents
      myai config set tools.claude.enabled true                             # Enable Claude
      myai config set settings.debug true                                   # Enable debug mode
      myai config set integrations.auto_sync_interval 600                   # Sync every 10 min

    Configuration levels:
      --level user     # Save to ~/.myai/config/user.json (default)
      --level project  # Save to .myai/config/project.json
      --level team     # Save to team config (shared)

    After changes, validate with:
      myai config validate         # Check configuration
      myai agent list              # Verify agent status
      myai status                  # Check system health

    Related commands:
      myai config get <key>        # Get current value
      myai config list-keys        # See all available keys with examples
      myai config show             # Show all configuration
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
        validation_table = Table(title="Validation Results", show_header=True, header_style="bold magenta", expand=True)
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
def list_keys(ctx: typer.Context):
    """List all available configuration keys with descriptions.

    This command shows all configuration keys that can be set, along with
    their purpose, expected values, and impact on system behavior.

    Use this command to discover configuration options and understand
    what each setting controls.

    Examples:
      myai config list-keys                   # Show all available keys
      myai config list-keys | grep agent     # Find agent-related settings

    Related commands:
      myai config get <key>                   # Get current value of a key
      myai config set <key> <value>          # Set a configuration value
      myai config show                        # Show current configuration
    """
    state: AppState = ctx.obj

    # Configuration key definitions with descriptions
    config_keys = {
        "Agent Management": {
            "agents.enabled": {
                "type": "list[str]",
                "default": "[]",
                "description": "Agents active in the current project",
                "impact": "Creates .claude/agents/ and .cursor/rules/ files for enabled agents",
                "validation": "Check files exist, agents appear in IDE, 'myai agent list' shows enabled",
            },
            "agents.disabled": {
                "type": "list[str]",
                "default": "[]",
                "description": "Agents explicitly disabled for this project",
                "impact": "Prevents agents from being activated even if globally enabled",
                "validation": "Disabled agents don't appear in IDE, files are removed",
            },
            "agents.global_enabled": {
                "type": "list[str]",
                "default": "[]",
                "description": "Agents active across all projects",
                "impact": "Creates ~/.claude/agents/ files, available in all projects",
                "validation": "Check global files exist, agents available in new projects",
            },
            "agents.global_disabled": {
                "type": "list[str]",
                "default": "[]",
                "description": "Agents disabled globally across all projects",
                "impact": "Prevents agents from being used anywhere",
                "validation": "Agents don't appear in any project, global files removed",
            },
            "agents.auto_discover": {
                "type": "bool",
                "default": "true",
                "description": "Automatically detect and load new agents",
                "impact": "New agents in ~/.myai/agents/ are automatically available",
                "validation": "Add agent file, check if it appears in 'myai agent list'",
            },
            "agents.categories": {
                "type": "list[str]",
                "default": "[]",
                "description": "Agent categories to load (empty = all)",
                "impact": "Filters which agent categories are available",
                "validation": "Only specified categories appear in agent listings",
            },
            "agents.custom_path": {
                "type": "path",
                "default": "null",
                "description": "Custom directory for user-created agents",
                "impact": "Changes where MyAI looks for custom agents",
                "validation": "Agents in custom path appear in 'myai agent list'",
            },
        },
        "IDE Tool Integration": {
            "tools.claude.enabled": {
                "type": "bool",
                "default": "true",
                "description": "Enable Claude Code integration",
                "impact": "Controls whether agents sync to ~/.claude/agents/ and project .claude/",
                "validation": "Agent files appear in Claude directories, Claude Code sees agents",
            },
            "tools.claude.auto_sync": {
                "type": "bool",
                "default": "true",
                "description": "Automatically sync agents to Claude when enabled/disabled",
                "impact": "Agent files are created/removed immediately on status change",
                "validation": "Enable/disable agent, check files sync immediately",
            },
            "tools.claude.agents_path": {
                "type": "path",
                "default": "~/.claude/agents",
                "description": "Directory where Claude agent files are stored",
                "impact": "Changes where Claude integration files are created",
                "validation": "Agent files appear in specified directory",
            },
            "tools.claude.settings_path": {
                "type": "path",
                "default": "~/.claude/settings.json",
                "description": "Path to Claude configuration file",
                "impact": "Controls Claude integration settings location",
                "validation": "Settings file exists and is valid JSON",
            },
            "tools.cursor.enabled": {
                "type": "bool",
                "default": "true",
                "description": "Enable Cursor IDE integration",
                "impact": "Controls whether agents sync to .cursor/rules/",
                "validation": "Agent files appear in Cursor directory, Cursor sees rules",
            },
            "tools.cursor.auto_sync": {
                "type": "bool",
                "default": "true",
                "description": "Automatically sync agents to Cursor when enabled/disabled",
                "impact": "Cursor rule files are created/removed immediately",
                "validation": "Enable/disable agent, check .cursor/rules/ files sync",
            },
            "tools.cursor.rules_path": {
                "type": "path",
                "default": ".cursor/rules",
                "description": "Directory where Cursor rule files are stored",
                "impact": "Changes where Cursor integration files are created",
                "validation": "Rule files appear in specified directory",
            },
            "tools.cursor.project_specific": {
                "type": "bool",
                "default": "true",
                "description": "Create project-specific Cursor rules only",
                "impact": "Rules are per-project rather than global",
                "validation": "Rules only appear in current project's .cursor/",
            },
        },
        "Sync & Integration Behavior": {
            "integrations.auto_sync_interval": {
                "type": "int",
                "default": "300",
                "description": "How often to sync changes (seconds, 60-3600)",
                "impact": "Controls frequency of automatic synchronization",
                "validation": "Watch sync timestamps, enable debug to see sync activity",
            },
            "integrations.conflict_resolution": {
                "type": "str",
                "default": "interactive",
                "description": "How to handle sync conflicts (interactive/auto/manual/abort)",
                "impact": "Determines behavior when local and remote changes conflict",
                "validation": "Create conflict scenario, observe resolution behavior",
            },
            "integrations.sync_on_change": {
                "type": "bool",
                "default": "true",
                "description": "Sync immediately when agents are enabled/disabled",
                "impact": "Files update instantly vs waiting for sync interval",
                "validation": "Enable agent, check if files appear immediately",
            },
            "integrations.dry_run_default": {
                "type": "bool",
                "default": "false",
                "description": "Default to dry-run mode for sync operations",
                "impact": "Shows what would sync without making changes",
                "validation": "Sync operations show preview without actual changes",
            },
        },
        "System Settings": {
            "settings.debug": {
                "type": "bool",
                "default": "false",
                "description": "Enable detailed debug output",
                "impact": "Shows detailed operation logs, sync activity, file operations",
                "validation": "Commands show additional [dim] debug messages",
            },
            "settings.auto_sync": {
                "type": "bool",
                "default": "true",
                "description": "Global toggle for all automatic synchronization",
                "impact": "Master switch that disables all auto-sync when false",
                "validation": "Disable, check that no automatic syncing occurs",
            },
            "settings.backup_enabled": {
                "type": "bool",
                "default": "true",
                "description": "Create backups before making configuration changes",
                "impact": "Backup files created in ~/.myai/backups/ before modifications",
                "validation": "Make changes, check for timestamped backup files",
            },
            "settings.backup_count": {
                "type": "int",
                "default": "5",
                "description": "Maximum number of backup files to retain (1-50)",
                "impact": "Oldest backups are deleted when limit is exceeded",
                "validation": "Check backup directory, verify count limit enforcement",
            },
            "settings.cache_enabled": {
                "type": "bool",
                "default": "true",
                "description": "Enable configuration caching for performance",
                "impact": "Faster config loading, may delay seeing external changes",
                "validation": "Disable, check if config loading is slower but more current",
            },
            "settings.cache_ttl": {
                "type": "int",
                "default": "3600",
                "description": "Configuration cache lifetime in seconds (60-86400)",
                "impact": "How long cached configuration data remains valid",
                "validation": "Change external config, check when MyAI sees changes",
            },
            "settings.merge_strategy": {
                "type": "str",
                "default": "merge",
                "description": "How to combine configurations from different levels (merge/nuclear)",
                "impact": "Controls whether configs are deeply merged or completely overridden",
                "validation": "Set conflicting values at different levels, check resolution",
            },
        },
    }

    try:
        if state.output_format == "json":
            formatter = get_formatter("json", console)
            formatter.format(config_keys)
        else:
            console.print("[bold]📋 Available Configuration Keys[/bold]\n")

            for category, keys in config_keys.items():
                console.print(f"[bold cyan]{category}:[/bold cyan]")

                # Create table for this category
                table = Table(show_header=True, header_style="bold magenta", expand=True, show_lines=True)
                table.add_column("Key", style="cyan", no_wrap=True, width=25)
                table.add_column("Type", style="green", width=12)
                table.add_column("Default", style="yellow", width=15)
                table.add_column("Description & Impact", style="white", min_width=40)

                for key, info in keys.items():
                    # Format description with impact
                    description_text = info["description"]
                    impact_text = f"\n[dim]Impact:[/dim] {info['impact']}"
                    validation_text = f"\n[dim]Validate:[/dim] {info['validation']}"
                    full_description = description_text + impact_text + validation_text

                    table.add_row(key, info["type"], info["default"], full_description)

                console.print(table)
                console.print()

            console.print("[bold]Next Steps:[/bold]")
            console.print("  • Get current value: [cyan]myai config get <key>[/cyan]")
            console.print("  • Set a value: [cyan]myai config set <key> <value>[/cyan]")
            console.print("  • View all config: [cyan]myai config show[/cyan]")
            console.print("  • Validate setup: [cyan]myai config validate[/cyan]")

    except Exception as e:
        console.print(f"[red]Error listing configuration keys: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def reset(
    ctx: typer.Context,
    level: str = typer.Option("user", "--level", "-l", help="Configuration level to reset"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),  # noqa: FBT001
):
    """Reset configuration to defaults.

    This command resets a configuration level to its default values,
    removing all customizations. Use with caution as this cannot be undone
    (unless you have backups enabled).

    What gets reset:
      • All agent enablement settings
      • Tool integration configurations
      • Sync and integration behavior settings
      • System preferences and customizations

    Examples:
      myai config reset --level user          # Reset user preferences
      myai config reset --level project       # Reset project settings
      myai config reset --level user --yes    # Skip confirmation

    After reset, you may need to:
      • Re-enable your preferred agents
      • Reconfigure tool integrations
      • Adjust sync preferences
      • Check that IDE integrations still work

    To validate the reset worked:
      myai config show                        # Verify default values
      myai agent list                         # Check agent status
      myai status                             # Ensure system health

    Related commands:
      myai config show                        # See current configuration
      myai config validate                    # Check configuration validity
      myai install all                        # Reinstall with defaults
    """
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
    """Compare configurations between different levels.

    This command shows differences between configuration levels, helping you
    understand how settings override each other and troubleshoot conflicts.

    Configuration hierarchy (highest to lowest priority):
      1. Enterprise - Organization policies (readonly)
      2. User - Your personal settings
      3. Team - Shared team settings
      4. Project - Project-specific settings

    Examples:
      myai config diff user project           # Compare user vs project settings
      myai config diff default user           # See what you've customized
      myai config diff user project --key agents  # Compare just agent settings
      myai config diff user project --show-identical  # Show matching values too

    Common use cases:
      • Troubleshooting: Why is an agent not working?
      • Auditing: What settings have been customized?
      • Team sync: Ensuring consistent team configuration
      • Migration: Understanding differences before changes

    Understanding the output:
      ≠ Different  - Values differ between levels
      + Added      - Setting exists in target but not source
      - Removed    - Setting exists in source but not target
      = Same       - Values are identical (only with --show-identical)

    To validate configuration precedence:
      1. Check what's active: myai config show
      2. Compare levels: myai config diff user project
      3. Understand which takes priority
      4. Test behavior: myai agent list, myai status

    Related commands:
      myai config show                        # See effective configuration
      myai config get <key>                   # Get specific setting
      myai config validate                    # Check configuration validity
    """
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
            title=f"Configuration Comparison: {source} vs {target}",
            show_header=True,
            header_style="bold magenta",
            expand=True,
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
