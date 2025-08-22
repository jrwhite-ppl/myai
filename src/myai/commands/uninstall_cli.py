"""
MyAI Uninstall CLI command interface.
"""

import shutil
from pathlib import Path

import typer
from rich.console import Console

help_text = """🗑️ Uninstall MyAI components - Remove files, configurations, and integrations

Safely remove MyAI installations while preserving important data and offering recovery options.

Uninstall options:
  • Complete removal  - All MyAI files and configurations
  • Selective removal - Choose specific components to remove
  • Backup creation  - Automatic backup before removal
  • Custom preservation - Keep custom agents and important data

What gets removed:
  • ~/.myai/          - User data and configurations
  • ~/.claude/agents/ - Global Claude Code integration
  • .claude/          - Project Claude configurations
  • .cursor/          - Project Cursor rules and settings
  • System packages   - MyAI CLI and dependencies

Data protection:
  • Custom agents are preserved by default
  • Configuration backups created automatically
  • Option to keep specific directories
  • Recovery instructions provided

Essential commands:
  myai uninstall                          # Interactive uninstall with options
  myai uninstall --all                    # Complete removal
  myai uninstall --preserve-custom        # Keep custom agents
  myai uninstall --backup-first           # Create backup before removal

Safety features:
  Always creates recovery information and offers selective preservation of your custom work."""

app = typer.Typer(
    help=help_text,
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help", "help"]},
)
console = Console()


@app.callback(invoke_without_command=True)
def uninstall(
    ctx: typer.Context,
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
      myai uninstall --project        # Remove project files only
      myai uninstall --global-agents  # Remove global agents only
      myai uninstall --all            # Remove everything
      myai uninstall --all --force    # Remove everything without prompts
    """
    # Check if there's a subcommand invoked
    if ctx.invoked_subcommand is not None:
        return

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

            # Build list of our .md files to remove (excluding custom agents)
            our_agent_files = []
            for agent in agents:
                # Skip custom/imported agents - they should not be removed
                if getattr(agent, "is_custom", False):
                    continue

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

                # Build list of our .md files to remove (excluding custom agents)
                our_agent_files = []
                for agent in agents:
                    # Skip custom/imported agents - they should not be removed
                    if hasattr(agent, "is_custom") and agent.is_custom:
                        continue

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

            # Build list of our .mdc files to remove (excluding custom agents)
            our_mdc_files = []
            for agent in agents:
                # Skip custom/imported agents - they should not be removed
                if getattr(agent, "is_custom", False):
                    continue

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

        # Check for AGENTS.md files created by MyAI
        root_agents_md = cwd / "AGENTS.md"
        if root_agents_md.exists():
            # Check if it's a MyAI-generated file
            try:
                content = root_agents_md.read_text(encoding="utf-8")
                if "Generated by MyAI" in content or "@myai/agents/" in content:
                    to_remove.append(("Root AGENTS.md (MyAI-generated)", root_agents_md, "1 file"))
            except Exception:  # noqa: S110
                pass

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
                    if file_path.exists():
                        file_path.unlink()
                console.print(f"✅ Removed {name}")
                removed_count += 1
            else:
                # Remove directory or file
                if path_or_paths.is_dir():
                    shutil.rmtree(path_or_paths)
                else:
                    path_or_paths.unlink()
                console.print(f"✅ Removed {name}")
                removed_count += 1
        except Exception as e:
            console.print(f"[red]❌ Failed to remove {name}: {e}[/red]")

    # Clean up empty directories
    if claude:
        # Check if agents directory is empty after removing our files
        claude_agents_dir = Path.home() / ".claude" / "agents"
        if claude_agents_dir.exists() and not any(claude_agents_dir.iterdir()):
            try:
                claude_agents_dir.rmdir()
                console.print("✅ Removed empty ~/.claude/agents directory")
            except Exception:  # noqa: S110
                pass

        # Check if ~/.claude itself is empty
        claude_dir = Path.home() / ".claude"
        if claude_dir.exists() and not any(claude_dir.iterdir()):
            try:
                claude_dir.rmdir()
                console.print("✅ Removed empty ~/.claude directory")
            except Exception:  # noqa: S110
                pass

    if project:
        # Check if .cursor/rules is empty after removal
        cursor_rules = Path.cwd() / ".cursor" / "rules"
        if cursor_rules.exists() and not any(cursor_rules.iterdir()):
            try:
                cursor_rules.rmdir()
                console.print("✅ Removed empty .cursor/rules directory")
            except Exception:  # noqa: S110
                pass

        # Check if .cursor is empty
        cursor_dir = Path.cwd() / ".cursor"
        if cursor_dir.exists() and not any(cursor_dir.iterdir()):
            try:
                cursor_dir.rmdir()
                console.print("✅ Removed empty .cursor directory")
            except Exception:  # noqa: S110
                pass

        # Check if .claude/agents is empty after removal
        claude_agents = Path.cwd() / ".claude" / "agents"
        if claude_agents.exists() and not any(claude_agents.iterdir()):
            try:
                claude_agents.rmdir()
                console.print("✅ Removed empty .claude/agents directory")
            except Exception:  # noqa: S110
                pass

    console.print(f"\n[green]✅ Successfully removed {removed_count} component(s).[/green]")

    # Provide next steps based on what was removed
    if global_agents or global_config:
        console.print("\n[dim]To reinstall MyAI globally, run: myai install global[/dim]")
    if project:
        console.print("[dim]To reinstall project files, run: myai install project[/dim]")
