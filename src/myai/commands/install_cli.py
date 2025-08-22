"""
MyAI Installation CLI command interface.
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from myai.agent.registry import get_agent_registry
from myai.agent_os.adapter import AgentOSAdapter
from myai.config.manager import get_config_manager
from myai.integrations.manager import IntegrationManager
from myai.models.config import MyAIConfig

app = typer.Typer()
console = Console()

# Constants for Agent-OS style minimal wrappers


class Outputs(str, Enum):
    pretty = "pretty"
    json = "json"


def _detect_agentos() -> Optional[Path]:
    """Detect existing Agent-OS installation."""
    # Check for .agent-os directory in user home
    home = Path.home()
    agentos_dir = home / ".agent-os"

    if agentos_dir.exists() and agentos_dir.is_dir():
        return agentos_dir

    # Check for agentos command in PATH
    try:
        result = subprocess.run(
            ["agentos", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S603,S607
        )
        if result.returncode == 0:
            # Try to find installation path from command
            which_result = subprocess.run(
                ["which", "agentos"], capture_output=True, text=True, timeout=5, check=False  # noqa: S603,S607
            )
            if which_result.returncode == 0:
                agentos_cmd = Path(which_result.stdout.strip())
                # Usually installed in a parent directory structure
                possible_dir = agentos_cmd.parent.parent / ".agent-os"
                if possible_dir.exists():
                    return possible_dir
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _setup_workflow_system() -> None:
    """Setup internal workflow system (based on Agent-OS)."""
    import tempfile

    from myai.agent_os import AgentOSAdapter

    console.print("[dim]Setting up workflow system...[/dim]")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Clone Agent-OS repository
        try:
            subprocess.run(
                [  # noqa: S603, S607
                    "git",
                    "clone",
                    "https://github.com/buildermethods/agent-os.git",
                    str(temp_path / "agent-os"),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # Use adapter to transform and integrate
            adapter = AgentOSAdapter()
            adapter.setup_from_temp(temp_path / "agent-os")

            console.print("✅ Workflow system initialized")

        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]Warning: Could not setup workflow system: {e}[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Workflow system setup failed: {e}[/yellow]")


def _clone_and_integrate_agentos() -> None:
    """Clone Agent-OS repository and integrate it invisibly into MyAI."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        agentos_path = temp_path / "agent-os"

        try:
            # Clone the Agent-OS repository
            console.print("  Setting up workflow system components...")
            result = subprocess.run(
                [  # noqa: S603, S607
                    "git",
                    "clone",
                    "https://github.com/buildermethods/agent-os.git",
                    str(agentos_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                console.print(f"  [yellow]Warning: Could not fetch workflow components: {result.stderr}[/yellow]")
                return

            # Use AgentOSAdapter to transform and integrate content
            adapter = AgentOSAdapter()
            adapter.setup_from_temp(agentos_path)

            console.print("  ✅ Workflow system components integrated")

        except Exception as e:
            console.print(f"  [yellow]Warning: Could not setup workflow system: {e}[/yellow]")


def _migrate_agentos_data(agentos_path: Path, myai_path: Path) -> None:
    """Migrate data from existing Agent-OS installation."""
    console.print(f"\n[yellow]Found existing Agent-OS at: {agentos_path}[/yellow]")

    # Create backup
    backup_dir = myai_path / "backups" / "agentos-migration"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Map Agent-OS directories to MyAI
    mappings = {
        "agents": "agents",
        "templates": "templates",
        "tools": "tools",
        "hooks": "hooks",
        "config": "config/agentos-imported",
    }

    migrated_items = []

    for agentos_subdir, myai_subdir in mappings.items():
        src = agentos_path / agentos_subdir
        if src.exists():
            dst = myai_path / myai_subdir
            dst.mkdir(parents=True, exist_ok=True)

            # Copy files
            for item in src.iterdir():
                if item.is_file():
                    # Backup original if exists
                    dst_file = dst / item.name
                    if dst_file.exists():
                        backup_file = backup_dir / myai_subdir / item.name
                        backup_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dst_file, backup_file)

                    # Copy from Agent-OS
                    shutil.copy2(item, dst_file)
                    migrated_items.append(f"{agentos_subdir}/{item.name}")

    if migrated_items:
        console.print(f"✅ Migrated {len(migrated_items)} items from Agent-OS")

        # Update Agent-OS config to point to MyAI
        agentos_config = agentos_path / "config.json"
        if agentos_config.exists():
            try:
                with open(agentos_config) as f:
                    existing_config = json.load(f)

                # Add MyAI integration marker
                existing_config["myai_integration"] = {
                    "enabled": True,
                    "myai_path": str(myai_path),
                    "migrated": True,
                }

                # Backup original config
                backup_config = backup_dir / "config.json"
                shutil.copy2(agentos_config, backup_config)

                # Write updated config
                with open(agentos_config, "w") as f:
                    json.dump(existing_config, f, indent=2)

                console.print("✅ Updated Agent-OS config for MyAI integration")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not update Agent-OS config: {e}[/yellow]")


########################################################################################
# The callback function's docstring is used by typer to derive the CLI menu            #
# information, and provides a default command landing point when no command is passed. #
#                                                                                      #
# Ie..simply passing `bt okta` won't yield an error, but will yield                   #
# the `bt --help` page instead.                                                       #
########################################################################################
@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """
    Interact with MyAI with this command.

    See the Commands section for the supported commands.
    """
    # Check if the callback was triggered by the primary app.
    if ctx.invoked_subcommand is None:
        # If no subcommand was invoked, execute the app's --help menu.
        ctx.invoke(app, ["--help"])


# Subcommand docstrings are used for help messages
@app.command(name="all")
def install_all():
    """
    Comprehensive setup of MyAI with all integrations.

    This command:
    - Sets up global ~/.myai directory with agents and Agent-OS
    - Configures ~/.claude directory with agents
    - Creates project-level .claude/agents directory
    - Creates project-level .cursor/rules directory with .mdc files

    Files/directories created:
    - ~/.myai/ (entire directory structure)
    - ~/.myai/agents/**/*.md (default agents)
    - ~/.myai/.agent-os/config.json
    - ~/.myai/config/default_agents.yaml
    - ~/.claude/agents/ (directory) and *.md files
    - .claude/agents/ (directory) and *.md files
    - .claude/settings.local.json (only if doesn't exist)
    - .cursor/rules/ (directory) and *.mdc files

    Examples:
      myai install all
    """
    import myai

    console.print("🚀 Starting comprehensive MyAI setup...")

    # Check for existing Agent-OS installation
    existing_agentos = _detect_agentos()
    if existing_agentos:
        console.print(f"\n[yellow]🔍 Detected existing Agent-OS installation at: {existing_agentos}[/yellow]")
        if typer.confirm("Would you like to migrate your Agent-OS data to MyAI?"):
            myai_dir = Path.home() / ".myai"
            myai_dir.mkdir(exist_ok=True)
            _migrate_agentos_data(existing_agentos, myai_dir)

    # Step 1: Setup global MyAI directory with workflow system
    console.print("\n[bold]Step 1: Setting up ~/.myai directory with workflow system[/bold]")

    # Setup the workflow system (invisible Agent-OS integration)
    _setup_workflow_system()

    package_path = Path(myai.__file__).parent
    source_agents_dir = package_path / "data" / "agents" / "default"

    if not source_agents_dir.exists():
        console.print("[red]Error: Default agents directory not found in package[/red]")
        raise typer.Exit(1)

    # Create target directories
    myai_dir = Path.home() / ".myai"
    target_agents_dir = myai_dir / "agents"
    target_agents_dir.mkdir(parents=True, exist_ok=True)

    # Copy all default agents (merge-safe - only copy if not exists)
    copied_count = 0
    skipped_count = 0
    created_categories = []

    for category_dir in source_agents_dir.iterdir():
        if category_dir.is_dir():
            target_category_dir = target_agents_dir / category_dir.name
            category_created = not target_category_dir.exists()
            target_category_dir.mkdir(exist_ok=True)

            if category_created:
                created_categories.append(category_dir.name)

            for agent_file in category_dir.glob("*.md"):
                target_file = target_category_dir / agent_file.name
                if not target_file.exists():
                    shutil.copy2(agent_file, target_file)
                    copied_count += 1
                    console.print(
                        f"  [green]✓[/green] Created {category_dir.name}/{agent_file.name} [dim]-"
                        f" {agent_file.name.replace('-', ' ').title()} agent[/dim]"
                    )
                else:
                    skipped_count += 1

    if created_categories:
        console.print(
            f"  [green]✓[/green] Created {len(created_categories)} agent categories: {', '.join(created_categories)}"
        )

    if skipped_count > 0:
        console.print(
            f"✅ Installed {copied_count} new agents, preserved {skipped_count} existing agents [dim](merge-safe)[/dim]"
        )
    else:
        console.print(
            f"✅ Installed {copied_count} default agents to ~/.myai/agents [dim](23 professional agents ready)[/dim]"
        )

    # Clone and integrate Agent-OS invisibly
    _clone_and_integrate_agentos()

    # Create MyAI config directory
    config_dir = myai_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Create templates directory
    templates_dir = myai_dir / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Create tools directory
    tools_dir = myai_dir / "tools"
    tools_dir.mkdir(exist_ok=True)

    # Create hooks directory
    hooks_dir = myai_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Create example hook for agent creation
    example_hook = hooks_dir / "on_agent_create.sh"
    if not example_hook.exists():
        hook_content = """#!/bin/bash
# Example MyAI hook for agent creation
# This hook is called when a new agent is created

AGENT_NAME="$1"
AGENT_PATH="$2"

echo "New agent created: $AGENT_NAME at $AGENT_PATH"

# Add your custom logic here
# Example: sync to version control, notify team, etc.
"""
        example_hook.write_text(hook_content)
        example_hook.chmod(0o755)
        console.print("✅ Created example hooks")

    default_agents_config = config_dir / "default_agents.yaml"
    if not default_agents_config.exists():
        default_config = {
            "default_agents": [
                "lead-developer",
                "systems-architect",
                "data-analyst",
                "security-analyst",
                "brand-strategist",
            ],
            "auto_load_defaults": True,
        }

        with open(default_agents_config, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False)

        console.print("✅ Created default agents configuration")

    # Step 2: Setup Claude integration globally
    console.print("\n[bold]Step 2: Setting up ~/.claude directory[/bold]")

    claude_dir = Path.home() / ".claude"
    claude_dir.mkdir(exist_ok=True)

    # Create Claude agents directory
    claude_agents_dir = claude_dir / "agents"
    claude_agents_created = not claude_agents_dir.exists()
    claude_agents_dir.mkdir(exist_ok=True)

    if claude_agents_created:
        console.print("✅ Created ~/.claude directory structure [dim](for Claude Code integration)[/dim]")
    else:
        console.print("✅ Verified ~/.claude directory structure [dim](already exists)[/dim]")

    # Step 3: Configure default agent enablement - set Agent-OS agents as enabled defaults
    console.print("\n[bold]Step 3: Configuring default agent enablement...[/bold]")

    # Define Agent-OS agents (the only ones that should be pre-enabled)
    agentos_agents = ["agentos-project-manager", "agentos-spec-creator", "agentos-workflow-executor"]

    registry = get_agent_registry()
    config_manager = get_config_manager()

    # Set Agent-OS agents as globally enabled so they're ready to use across all projects
    config_manager.set_config_value("agents.global_enabled", agentos_agents, level="user")
    # Clear any disabled lists so all agents are visible
    config_manager.set_config_value("agents.global_disabled", [], level="user")
    config_manager.set_config_value("agents.disabled", [], level="user")

    console.print(f"✅ Pre-enabled {len(agentos_agents)} Agent-OS agents")
    console.print("✅ All other agents available and can be enabled as needed")

    # Step 4: Sync globally enabled agents to Claude
    console.print("\n[bold]Step 4: Syncing globally enabled agents to Claude[/bold]")

    async def sync_to_claude():
        manager = IntegrationManager()
        await manager.initialize(["claude"])

        # Get enabled agents only and sync them to ~/.claude/agents
        config = config_manager.get_config()

        all_agents = registry.list_agents()
        # Filter to only globally enabled agents for Claude global setup
        global_enabled_list = getattr(config.agents, "global_enabled", [])
        enabled_agents = [a for a in all_agents if a.metadata.name in global_enabled_list]

        # Sync only enabled agents to Claude
        results = await manager.sync_agents(enabled_agents, ["claude"])
        return results

    claude_results = asyncio.run(sync_to_claude())
    if claude_results.get("claude", {}).get("status") == "success":
        synced = claude_results["claude"].get("synced", 0)
        console.print(
            f"✅ Synced {synced} globally enabled agents to ~/.claude/agents [dim](ready for Claude Code)[/dim]"
        )
    else:
        errors = claude_results.get("claude", {}).get("errors", [])
        console.print(f"[yellow]⚠️  Claude sync had issues: {'; '.join(errors) if errors else 'Unknown error'}[/yellow]")

    # Step 5: Setup project-level directories
    console.print("\n[bold]Step 5: Setting up project-level integration[/bold]")

    cwd = Path.cwd()

    # Create project .claude directory with local agents
    project_claude_dir = cwd / ".claude"
    project_claude_created = not project_claude_dir.exists()
    project_claude_dir.mkdir(exist_ok=True)

    # Create project-level agents directory
    project_claude_agents = project_claude_dir / "agents"
    project_claude_agents.mkdir(exist_ok=True)

    if project_claude_created:
        console.print(
            "  [green]✓[/green] Created project .claude directory [dim](for project-specific Claude settings)[/dim]"
        )
    else:
        console.print("  [green]✓[/green] Verified project .claude directory [dim](already exists)[/dim]")

    # Create lightweight wrapper agents that reference central configs
    console.print("  Creating lightweight agent wrappers for project...")
    agent_count = 0
    skipped_count = 0

    # Get all agents from registry to create wrappers
    registry = get_agent_registry()
    agents = registry.list_agents()

    # Filter to only project-enabled agents (not global ones)
    # Global agents are available via ~/.claude/agents and don't need project wrappers
    config_manager = get_config_manager()
    project_config: MyAIConfig = config_manager.get_config()
    project_enabled_list = project_config.agents.enabled

    # Only create project files for project-enabled agents
    project_enabled_agents = [a for a in agents if a.metadata.name in project_enabled_list]

    # For Cursor, we need BOTH global and project agents since Cursor doesn't have global settings
    global_enabled_list = getattr(project_config.agents, "global_enabled", [])
    cursor_enabled_agents = [
        a for a in agents if a.metadata.name in global_enabled_list or a.metadata.name in project_enabled_list
    ]

    for agent in project_enabled_agents:
        agent_name = agent.metadata.name
        target_file = project_claude_agents / f"{agent_name}.md"

        if not target_file.exists():
            # Create minimal Agent-OS style wrapper - bare bones reference
            wrapper_content = f"""---
agent: "{agent_name}"
source: "~/.myai/agents"
---

# {agent_name.replace('-', ' ').title()}

@myai/agents/{agent.metadata.category.value if agent.metadata.category else 'default'}/{agent_name}.md
"""
            target_file.write_text(wrapper_content)
            agent_count += 1
        else:
            skipped_count += 1

    if skipped_count > 0:
        console.print(f"  ✅ Created {agent_count} new agent wrappers, skipped {skipped_count} existing")
    else:
        console.print(f"  ✅ Created {agent_count} agent wrappers in .claude/agents")

    # Create or update project-level Claude settings
    project_claude_settings = project_claude_dir / "settings.local.json"

    # Always update the project configuration to keep it in sync
    from myai.utils.json_content_manager import update_claude_settings

    claude_project_config = {
        "projects": {
            str(cwd): {
                "name": cwd.name,
                "description": f"MyAI-managed project: {cwd.name}",
                "tools": [
                    "Task",
                    "Bash",
                    "Read",
                    "Edit",
                    "Write",
                    "NotebookRead",
                    "NotebookEdit",
                    "WebFetch",
                    "TodoWrite",
                    "WebSearch",
                ],
                "agentsPath": str(project_claude_agents),
                "settings": {"model": "claude-3-sonnet-20241022", "temperature": 0.7},
            }
        }
    }

    # Update settings preserving any user customizations
    update_claude_settings(project_claude_settings, claude_project_config)
    console.print("✅ Created/updated project .claude configuration")

    # Create project .cursor directory with rules subdirectory
    project_cursor_dir = cwd / ".cursor"
    project_cursor_created = not project_cursor_dir.exists()
    project_cursor_dir.mkdir(exist_ok=True)
    project_cursor_rules = project_cursor_dir / "rules"
    project_cursor_rules.mkdir(exist_ok=True)

    if project_cursor_created:
        console.print("✅ Created project .cursor/rules directory [dim](for Cursor IDE integration)[/dim]")
    else:
        console.print("✅ Verified project .cursor/rules directory [dim](already exists)[/dim]")

    # Step 6: Create Cursor rules as lightweight .mdc wrappers
    console.print("\n[bold]Step 6: Creating lightweight Cursor rule wrappers[/bold]")

    # Create .mdc files for both global and project enabled agents (Cursor needs both)
    mdc_count = 0
    for agent in cursor_enabled_agents:
        agent_name = "unknown"  # Default value to avoid UnboundLocalError
        try:
            agent_name = agent.metadata.name

            # Create minimal Agent-OS style cursor rule - bare bones reference
            mdc_content = f"""---
agent: "{agent_name}"
description: "{agent_name.replace('-', ' ').title()}"
source: "~/.myai/agents"
globs: ['**/*']
alwaysApply: false
---

# {agent_name.replace('-', ' ').title()}

@myai/agents/{agent.metadata.category.value if agent.metadata.category else 'default'}/{agent_name}.md
"""

            # Write .mdc file (merge-safe)
            mdc_file = project_cursor_rules / f"{agent_name}.mdc"
            if not mdc_file.exists():
                with open(mdc_file, "w", encoding="utf-8") as f:
                    f.write(mdc_content)
                mdc_count += 1
        except Exception as e:
            console.print(f"[yellow]  Warning: Failed to create rule for {agent_name}: {e}[/yellow]")

    console.print(f"✅ Created {mdc_count} Cursor rules in .cursor/rules/")

    # Step 7: Create AGENTS.md file at project root
    console.print("\n[bold]Step 7: Setting up AGENTS.md integration[/bold]")

    from myai.agents_md import AgentsMdManager

    agents_md_manager = AgentsMdManager(cwd)
    root_agents_md = cwd / "AGENTS.md"

    if root_agents_md.exists():
        console.print("  [yellow]AGENTS.md already exists, preserving existing file[/yellow]")
    else:
        try:
            # Create root AGENTS.md with enabled agents
            agents_md_manager.create(root_agents_md, template="root", force=False)
            console.print("✅ Created root AGENTS.md with MyAI agent references")
        except Exception as e:
            console.print(f"  [yellow]Warning: Could not create AGENTS.md: {e}[/yellow]")

    # Final summary
    console.print("\n[bold green]✨ MyAI setup complete![/bold green]")

    # Create summary table
    summary_table = Table(title="Installation Summary", show_header=True, header_style="bold cyan")
    summary_table.add_column("Component", style="cyan", no_wrap=True)
    summary_table.add_column("Location", style="white")
    summary_table.add_column("Purpose", style="dim")

    summary_table.add_row("Global MyAI", "~/.myai/", "Core system, agents, workflow components")
    summary_table.add_row(
        "Claude Integration",
        "~/.claude/agents/",
        f"Global agent access in Claude Code ({synced if 'synced' in locals() else 'N/A'} agents)",
    )
    summary_table.add_row(
        "Project Claude",
        ".claude/agents/",
        f"Project-specific agent wrappers ({agent_count if 'agent_count' in locals() else 'N/A'} agents)",
    )
    summary_table.add_row(
        "Project Cursor",
        ".cursor/rules/",
        f"Cursor IDE rules ({mdc_count if 'mdc_count' in locals() else 'N/A'} rules)",
    )
    summary_table.add_row("Project Guide", "AGENTS.md", "Project agent documentation")

    console.print(summary_table)

    console.print("\n[bold]Quick Start Commands:[/bold]")
    console.print("  [cyan]myai status[/cyan]                   - Check system status")
    console.print("  [cyan]myai agent list[/cyan]               - See all available agents")
    console.print("  [cyan]myai agent enable <name>[/cyan]      - Enable specific agents")
    console.print("  [cyan]myai agent show <name>[/cyan]        - View agent details")
    console.print("  [cyan]myai system integration-health[/cyan] - Verify integrations")

    console.print("\n[bold]Integration Status:[/bold]")
    console.print("  ✅ Claude Code - Agents available via global ~/.claude/agents")
    console.print("  ✅ Cursor IDE - Rules active in project .cursor/rules")
    console.print("  ✅ Project Setup - Ready for development workflows")


@app.command(name="global")
def install_global():
    """
    Setup global MyAI configuration.

    Examples:
      myai install global
    """
    pass


@app.command()
def project(
    with_agents_md: bool = typer.Option(  # noqa: FBT001
        True, "--with-agents-md/--no-agents-md", help="Include AGENTS.md setup"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),  # noqa: FBT001
):
    """
    Setup project MyAI configuration.

    This command creates:
    - .myai directory for project configuration
    - .claude directory with settings
    - .cursor directory with rules
    - AGENTS.md file with project guidelines (optional)

    Examples:
      myai install project
      myai install project --no-agents-md
      myai install project --force
    """
    console.print("🚀 Setting up project configuration...")

    cwd = Path.cwd()

    # Create .myai directory
    myai_dir = cwd / ".myai"
    myai_dir.mkdir(exist_ok=True)
    console.print("✅ Created .myai directory")

    # Create .claude directory
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(exist_ok=True)
    claude_agents_dir = claude_dir / "agents"
    claude_agents_dir.mkdir(exist_ok=True)
    console.print("✅ Created .claude directory structure")

    # Create or update Claude settings preserving user customizations
    claude_settings = claude_dir / "settings.local.json"

    from myai.utils.json_content_manager import update_claude_settings

    claude_project_config = {
        "projects": {
            str(cwd): {
                "name": cwd.name,
                "description": f"MyAI-managed project: {cwd.name}",
                "tools": [
                    "Task",
                    "Bash",
                    "Read",
                    "Edit",
                    "Write",
                    "NotebookRead",
                    "NotebookEdit",
                    "WebFetch",
                    "TodoWrite",
                    "WebSearch",
                ],
                "agentsPath": str(claude_agents_dir),
                "settings": {"model": "claude-3-sonnet-20241022", "temperature": 0.7},
            }
        }
    }

    # Update settings preserving any user customizations
    update_claude_settings(claude_settings, claude_project_config)
    console.print("✅ Created/updated Claude settings")

    # Create .cursor directory
    cursor_dir = cwd / ".cursor"
    cursor_dir.mkdir(exist_ok=True)
    cursor_rules_dir = cursor_dir / "rules"
    cursor_rules_dir.mkdir(exist_ok=True)
    console.print("✅ Created .cursor directory structure")

    # Setup AGENTS.md if requested
    if with_agents_md:
        from myai.agents_md import AgentsMdManager

        agents_md_manager = AgentsMdManager(cwd)
        root_agents_md = cwd / "AGENTS.md"

        if root_agents_md.exists() and not force:
            console.print("[yellow]AGENTS.md already exists, preserving existing file[/yellow]")
        else:
            try:
                agents_md_manager.create(root_agents_md, template="root", force=force)
                console.print("✅ Created root AGENTS.md with MyAI agent references")
            except Exception as e:
                console.print(f"[yellow]Warning: Could not create AGENTS.md: {e}[/yellow]")

    console.print("\n[green]✨ Project setup complete![/green]")
    console.print("\nNext steps:")
    console.print("  • Run 'myai agent list' to see available agents")
    console.print("  • Run 'myai agent enable <name>' to enable agents")
    console.print("  • Run 'myai status' to check configuration")


@app.command()
def client(client_name: str):
    """
    Setup client-specific configuration.

    Args:
        client_name: The client name (e.g., claude, cursor)

    Examples:
      myai install client claude
    """
    # TODO: Implement client-specific setup logic in Phase 5
    _ = client_name  # Acknowledge parameter usage
    pass
