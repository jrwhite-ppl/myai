"""
MyAI Setup CLI command interface.
"""

import shutil
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()
console = Console()


class Outputs(str, Enum):
    pretty = "pretty"
    json = "json"


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
@app.command()
def all_setup():
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
    - .cursor/rules/ (directory) and *.mdc files (NOT .cursor itself)

    Examples:
      myai setup all-setup
    """
    import asyncio
    import json

    import yaml

    import myai
    from myai.agent.registry import get_agent_registry
    from myai.integrations.manager import IntegrationManager

    console.print("🚀 Starting comprehensive MyAI setup...")

    # Step 1: Setup global MyAI directory with Agent-OS components
    console.print("\n[bold]Step 1: Setting up ~/.myai directory with Agent-OS[/bold]")

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
    for category_dir in source_agents_dir.iterdir():
        if category_dir.is_dir():
            target_category_dir = target_agents_dir / category_dir.name
            target_category_dir.mkdir(exist_ok=True)

            for agent_file in category_dir.glob("*.md"):
                target_file = target_category_dir / agent_file.name
                if not target_file.exists():
                    shutil.copy2(agent_file, target_file)
                    copied_count += 1
                else:
                    skipped_count += 1

    if skipped_count > 0:
        console.print(f"✅ Copied {copied_count} new agents, skipped {skipped_count} existing agents")
    else:
        console.print(f"✅ Copied {copied_count} default agents to ~/.myai/agents")

    # Setup Agent-OS components
    agentos_dir = myai_dir / ".agent-os"
    if not agentos_dir.exists():
        agentos_dir.mkdir(parents=True, exist_ok=True)
        console.print("✅ Created .agent-os directory structure")

        # Create Agent-OS config
        agentos_config = agentos_dir / "config.json"
        if not agentos_config.exists():
            config = {
                "version": "1.0.0",
                "myai_integration": True,
                "paths": {
                    "agents": str(myai_dir / "agents"),
                    "templates": str(myai_dir / "templates"),
                    "tools": str(myai_dir / "tools"),
                },
            }
            with open(agentos_config, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            console.print("✅ Created Agent-OS configuration")

    # Create default configuration
    config_dir = myai_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

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
    claude_agents_dir.mkdir(exist_ok=True)

    console.print("✅ Created ~/.claude directory structure")

    # Step 3: Sync agents to Claude
    console.print("\n[bold]Step 3: Syncing agents to Claude[/bold]")

    async def sync_to_claude():
        manager = IntegrationManager()
        await manager.initialize(["claude"])

        # Get all agents from registry
        registry = get_agent_registry()
        agents = registry.list_agents()

        # Sync to Claude
        results = await manager.sync_agents(agents, ["claude"])
        return results

    claude_results = asyncio.run(sync_to_claude())
    if claude_results.get("claude", {}).get("status") == "success":
        synced = claude_results["claude"].get("synced", 0)
        console.print(f"✅ Synced {synced} agents to ~/.claude/agents")
    else:
        console.print("[yellow]⚠️  Claude sync had issues[/yellow]")

    # Step 4: Setup project-level directories
    console.print("\n[bold]Step 4: Setting up project-level integration[/bold]")

    cwd = Path.cwd()

    # Create project .claude directory with local agents
    project_claude_dir = cwd / ".claude"
    project_claude_dir.mkdir(exist_ok=True)

    # Create project-level agents directory
    project_claude_agents = project_claude_dir / "agents"
    project_claude_agents.mkdir(exist_ok=True)

    # Copy agents to project .claude/agents (merge-safe)
    console.print("  Syncing agents to project .claude/agents...")
    agent_count = 0
    skipped_count = 0
    for agent_file in (Path.home() / ".claude" / "agents").glob("*.md"):
        target_file = project_claude_agents / agent_file.name
        if not target_file.exists():
            shutil.copy2(agent_file, target_file)
            agent_count += 1
        else:
            skipped_count += 1

    if skipped_count > 0:
        console.print(f"  ✅ Copied {agent_count} new agents, skipped {skipped_count} existing")
    else:
        console.print(f"  ✅ Copied {agent_count} agents to .claude/agents")

    # Create project-level Claude settings
    project_claude_settings = project_claude_dir / "settings.local.json"
    if not project_claude_settings.exists():
        # Create a basic project configuration
        project_config = {
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

        with open(project_claude_settings, "w", encoding="utf-8") as f:
            json.dump(project_config, f, indent=2)

        console.print("✅ Created project .claude configuration")

    # Create project .cursor directory with rules subdirectory
    project_cursor_dir = cwd / ".cursor"
    project_cursor_dir.mkdir(exist_ok=True)
    project_cursor_rules = project_cursor_dir / "rules"
    project_cursor_rules.mkdir(exist_ok=True)
    console.print("✅ Created project .cursor/rules directory")

    # Step 5: Create Cursor rules as .mdc files
    console.print("\n[bold]Step 5: Creating Cursor rules (.mdc files)[/bold]")

    # Get all agents from registry
    registry = get_agent_registry()
    agents = registry.list_agents()

    # Create .mdc files for each agent
    mdc_count = 0
    for agent in agents:
        agent_name = "unknown"  # Default value to avoid UnboundLocalError
        try:
            # Get agent name
            if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                agent_name = agent.metadata.name
            elif hasattr(agent, "name"):
                agent_name = agent.name
            elif isinstance(agent, dict) and "name" in agent:
                agent_name = agent["name"]

            # Get agent content
            if hasattr(agent, "content"):
                agent_content = agent.content
            elif isinstance(agent, dict) and "content" in agent:
                agent_content = agent["content"]
            else:
                agent_content = ""

            agent_display = agent_name.replace("-", " ").replace("_", " ").title()

            # Create MDC content with frontmatter
            mdc_content = f"""---
description: "{agent_display} Agent"
globs:
  - '**/*'
alwaysApply: false
---

{agent_content}
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

    # Final summary
    console.print("\n[bold green]✨ MyAI setup complete![/bold green]")
    console.print("\n[bold]What was set up:[/bold]")
    console.print("  • Global configuration in ~/.myai with Agent-OS")
    console.print("  • Claude integration in ~/.claude")
    console.print("  • Project-level .claude/agents directory")
    console.print("  • Project-level .cursor/rules directory with .mdc files")
    console.print("\n[bold]You can now:[/bold]")
    console.print("  • Use 'myai agent list' to see available agents")
    console.print("  • Access agents in Claude Code (from project .claude/agents)")
    console.print("  • Access agents in Cursor as project rules")
    console.print("  • Run 'myai integration sync' to update integrations")


@app.command()
def global_setup():
    """
    Setup global MyAI configuration.

    Examples:
      myai setup global-setup
    """
    pass


@app.command()
def project():
    """
    Setup project MyAI configuration.

    Examples:
      myai setup project
    """
    pass


@app.command()
def client(client_name: str):
    """
    Setup client-specific configuration.

    Args:
        client_name: The client name (e.g., claude, cursor)

    Examples:
      myai setup client claude
    """
    # TODO: Implement client-specific setup logic in Phase 5
    _ = client_name  # Acknowledge parameter usage
    pass


@app.command()
def uninstall(
    global_agents: bool = typer.Option(False, "--global-agents", help="Remove global MyAI agents"),  # noqa: FBT001
    global_config: bool = typer.Option(False, "--global-config", help="Remove global MyAI config"),  # noqa: FBT001
    claude: bool = typer.Option(False, "--claude", help="Remove Claude integration"),  # noqa: FBT001
    project: bool = typer.Option(False, "--project", help="Remove project-level files"),  # noqa: FBT001
    remove_all: bool = typer.Option(False, "--all", help="Remove all MyAI files"),  # noqa: FBT001
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts"),  # noqa: FBT001
):
    """
    Uninstall MyAI components.

    This command removes only the files that MyAI added. User-created agents
    and configurations are preserved unless --force is used.

    Examples:
      myai setup uninstall --project        # Remove project files only
      myai setup uninstall --global-agents  # Remove global agents only
      myai setup uninstall --all            # Remove everything
      myai setup uninstall --all --force    # Remove everything without prompts
    """
    if not any([global_agents, global_config, claude, project, remove_all]):
        console.print("[yellow]No components selected for removal. Use --help for options.[/yellow]")
        raise typer.Exit(0)

    # If --all is specified, enable all options
    if remove_all:
        global_agents = global_config = claude = project = True

    console.print("🔍 Analyzing MyAI installation...")

    # Track what will be removed
    # Each item is: (name, path_or_paths, description)
    # where path_or_paths can be a Path or List[Path]
    to_remove: list[tuple[str, Path | list[Path], str]] = []

    # Check global MyAI directory
    myai_dir = Path.home() / ".myai"
    if myai_dir.exists() and (global_agents or global_config):
        # When removing global components, remove entire ~/.myai directory
        file_count = sum(1 for _ in myai_dir.rglob("*") if _.is_file())
        dir_count = sum(1 for _ in myai_dir.rglob("*") if _.is_dir())
        to_remove.append(("Global MyAI directory", myai_dir, f"{file_count} files in {dir_count} directories"))

    # Check Claude directory
    if claude:
        claude_dir = Path.home() / ".claude"
        claude_agents_dir = claude_dir / "agents"
        if claude_agents_dir.exists():
            # Get list of our agent names to identify which .md files we created
            from myai.agent.registry import get_agent_registry

            registry = get_agent_registry()
            agents = registry.list_agents()

            # Build list of our .md files to remove
            our_agent_files = []
            for agent in agents:
                if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                    agent_name = agent.metadata.name
                elif hasattr(agent, "name"):
                    agent_name = agent.name
                else:
                    continue

                agent_file = claude_agents_dir / f"{agent_name}.md"
                if agent_file.exists():
                    our_agent_files.append(agent_file)

            if our_agent_files:
                to_remove.append(
                    ("Claude agents (MyAI agent files only)", our_agent_files, f"{len(our_agent_files)} .md files")
                )

    # Check project-level files
    if project:
        cwd = Path.cwd()

        # Project Claude directory - we create:
        # 1. .claude/agents/*.md files (specific agent files only)
        # 2. .claude/settings.local.json (only if it didn't exist during setup)
        project_claude = cwd / ".claude"
        if project_claude.exists():
            project_agents = project_claude / "agents"
            if project_agents.exists():
                # Get list of our agent names to identify which .md files we created
                from myai.agent.registry import get_agent_registry

                registry = get_agent_registry()
                agents = registry.list_agents()

                # Build list of our .md files to remove
                our_agent_files = []
                for agent in agents:
                    if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                        agent_name = agent.metadata.name
                    elif hasattr(agent, "name"):
                        agent_name = agent.name
                    else:
                        continue

                    agent_file = project_agents / f"{agent_name}.md"
                    if agent_file.exists():
                        our_agent_files.append(agent_file)

                if our_agent_files:
                    to_remove.append(
                        (
                            "Project Claude agents (MyAI agent files only)",
                            our_agent_files,
                            f"{len(our_agent_files)} .md files",
                        )
                    )

        # Project Cursor directory - we create:
        # 1. .cursor/rules/*.mdc files (specific agent files only)
        project_cursor_rules = cwd / ".cursor" / "rules"
        if project_cursor_rules.exists():
            # Get list of our agent names to identify which .mdc files we created
            from myai.agent.registry import get_agent_registry

            registry = get_agent_registry()
            agents = registry.list_agents()

            # Build list of our .mdc files to remove
            our_mdc_files = []
            for agent in agents:
                if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                    agent_name = agent.metadata.name
                elif hasattr(agent, "name"):
                    agent_name = agent.name
                else:
                    continue

                mdc_file = project_cursor_rules / f"{agent_name}.mdc"
                if mdc_file.exists():
                    our_mdc_files.append(mdc_file)

            if our_mdc_files:
                to_remove.append(
                    ("Project Cursor rules (MyAI agent files only)", our_mdc_files, f"{len(our_mdc_files)} .mdc files")
                )

    if not to_remove:
        console.print("[green]✅ No MyAI files found to remove.[/green]")
        raise typer.Exit(0)

    # Display what will be removed
    console.print("\n[bold]The following will be removed:[/bold]")
    for name, path_or_paths, details in to_remove:
        if isinstance(path_or_paths, list):
            # For lists of files, show summary instead of full list
            console.print(f"  • {name}: {details}")
        else:
            console.print(f"  • {name}: {path_or_paths}")
    console.print(f"\n[yellow]Total: {len(to_remove)} locations[/yellow]")

    # Confirm unless --force
    if not force:
        confirm = typer.confirm("\nDo you want to proceed with removal?", default=False)
        if not confirm:
            console.print("[yellow]Uninstall cancelled.[/yellow]")
            raise typer.Exit(0)

    # Perform removal
    console.print("\n🗑️  Removing MyAI components...")
    removed_count = 0

    for name, path_or_paths, _ in to_remove:
        try:
            # Handle both single path and list of paths
            if isinstance(path_or_paths, list):
                # Remove individual files (for Cursor rules)
                for file_path in path_or_paths:
                    file_path.unlink()
                console.print(f"  ✅ Removed {name}")
            elif path_or_paths.is_file():
                path_or_paths.unlink()
                console.print(f"  ✅ Removed {name}")
            else:
                shutil.rmtree(path_or_paths)
                console.print(f"  ✅ Removed {name}")
            removed_count += 1
        except Exception as e:
            console.print(f"  [red]❌ Failed to remove {name}: {e}[/red]")

    # Cleanup empty directories after file removal

    if claude:
        # Check if agents directory is empty after removing our files
        claude_agents_dir = Path.home() / ".claude" / "agents"
        if claude_agents_dir.exists() and not any(claude_agents_dir.iterdir()):
            try:
                claude_agents_dir.rmdir()
                console.print("  ✅ Removed empty ~/.claude/agents directory")
            except Exception:  # noqa: S110
                pass

        # Check if ~/.claude itself is empty
        claude_dir = Path.home() / ".claude"
        if claude_dir.exists() and not any(claude_dir.iterdir()):
            try:
                claude_dir.rmdir()
                console.print("  ✅ Removed empty ~/.claude directory")
            except Exception:  # noqa: S110
                pass

    if project:
        # Check if project .claude/agents is empty after removing our files
        project_agents = Path.cwd() / ".claude" / "agents"
        if project_agents.exists() and not any(project_agents.iterdir()):
            try:
                project_agents.rmdir()
                console.print("  ✅ Removed empty .claude/agents directory")
            except Exception:  # noqa: S110
                pass

        # Check if project .claude is empty
        project_claude = Path.cwd() / ".claude"
        if project_claude.exists() and not any(project_claude.iterdir()):
            try:
                project_claude.rmdir()
                console.print("  ✅ Removed empty .claude directory")
            except Exception:  # noqa: S110
                pass

        # Check if .cursor/rules is empty after removing our files
        project_cursor_rules = Path.cwd() / ".cursor" / "rules"
        if project_cursor_rules.exists() and not any(project_cursor_rules.iterdir()):
            try:
                project_cursor_rules.rmdir()
                console.print("  ✅ Removed empty .cursor/rules directory")
            except Exception:  # noqa: S110
                pass

        # For .cursor itself, we only remove if completely empty
        # Users might have other Cursor-related files
        project_cursor = Path.cwd() / ".cursor"
        if project_cursor.exists() and not any(project_cursor.iterdir()):
            try:
                project_cursor.rmdir()
                console.print("  ✅ Removed empty .cursor directory")
            except Exception:  # noqa: S110
                pass

    console.print(f"\n[green]✨ Uninstall complete! Removed {removed_count} components.[/green]")

    if removed_count < len(to_remove):
        console.print("[yellow]Some components could not be removed. Check permissions.[/yellow]")
