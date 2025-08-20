"""
System utility CLI commands.

This module provides CLI commands for system status, diagnostics,
and maintenance operations.
"""

import platform
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

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

# Constants
MAX_DISPLAY_ITEMS = 3
MAX_ERROR_DISPLAY = 5
CACHE_EXPIRY_DAYS = 7
BYTES_PER_KB = 1024.0


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
        # Generate backup ID with timestamp
        backup_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Determine backup directory
        if target == "auto":
            backup_base = Path.home() / ".myai" / "backups"
        else:
            backup_base = Path(target)

        backup_dir = backup_base / f"backup_{backup_id}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        items_backed_up = []
        total_files = 0

        # Backup agents
        agents_source = Path.home() / ".myai" / "agents"
        if agents_source.exists():
            agents_dest = backup_dir / "agents"
            shutil.copytree(agents_source, agents_dest, dirs_exist_ok=True)
            agent_count = len(list(agents_dest.glob("**/*.md")))
            items_backed_up.append(f"{agent_count} agents")
            total_files += agent_count

        # Backup configuration files if requested
        if include_config:
            config_manager = get_config_manager()
            configs_backed_up = 0

            # Backup user config
            user_config_path = config_manager.get_config_path("user")
            if user_config_path and user_config_path.exists():
                config_dest = backup_dir / "configs"
                config_dest.mkdir(exist_ok=True)
                shutil.copy2(user_config_path, config_dest / "user_config.json")
                configs_backed_up += 1

            # Backup project config if it exists
            project_config_path = config_manager.get_config_path("project")
            if project_config_path and project_config_path.exists():
                config_dest = backup_dir / "configs"
                config_dest.mkdir(exist_ok=True)
                shutil.copy2(project_config_path, config_dest / "project_config.json")
                configs_backed_up += 1

            if configs_backed_up > 0:
                items_backed_up.append(f"{configs_backed_up} configuration files")
                total_files += configs_backed_up

        # Create metadata file
        metadata_file = backup_dir / "backup_metadata.txt"
        with metadata_file.open("w") as f:
            f.write(f"Backup ID: {backup_id}\n")
            f.write(f"Created: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Total files: {total_files}\n")
            f.write(f"Items: {', '.join(items_backed_up)}\n")

        # Compress if requested
        final_path = backup_dir
        if compress:
            tar_path = backup_base / f"backup_{backup_id}.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=f"backup_{backup_id}")

            # Remove uncompressed directory
            shutil.rmtree(backup_dir)
            final_path = tar_path

            console.print("✅ System backup completed:")
            console.print(f"  • Backup ID: {backup_id}")
            console.print(f"  • Items: {', '.join(items_backed_up)}")
            console.print(f"  • Location: {final_path}")
            console.print("  • Compressed: Yes")
        else:
            console.print("✅ System backup completed:")
            console.print(f"  • Backup ID: {backup_id}")
            console.print(f"  • Items: {', '.join(items_backed_up)}")
            console.print(f"  • Location: {final_path}")
            console.print("  • Compressed: No")

    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def restore(
    ctx: typer.Context,
    backup_path: Path = typer.Argument(..., help="Path to backup file or directory"),
    dry_run: bool = typer.Option(  # noqa: FBT001
        False, "--dry-run", help="Show what would be restored without doing it"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force restore without confirmation"),  # noqa: FBT001
):
    """Restore system from backup."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print(f"[dim]Restoring from {backup_path}...[/dim]")

    try:
        # Validate backup path exists
        if not backup_path.exists():
            console.print(f"[red]Backup not found: {backup_path}[/red]")
            return

        # Handle compressed backups
        temp_dir = None
        if backup_path.is_file() and backup_path.suffix == ".gz":
            # Extract tar.gz file
            temp_dir = (
                Path.home() / ".myai" / "temp" / f"restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            temp_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(backup_path, "r:gz") as tar:
                # Filter to prevent directory traversal attacks
                def is_within_directory(directory, target):
                    abs_directory = Path(directory).resolve()
                    abs_target = Path(target).resolve()
                    return abs_directory in abs_target.parents or abs_directory == abs_target

                safe_members = []
                for member in tar.getmembers():
                    member_path = temp_dir / member.name
                    if is_within_directory(temp_dir, member_path):
                        safe_members.append(member)
                    else:
                        console.print(f"[yellow]Warning: Skipping potentially unsafe path: {member.name}[/yellow]")

                tar.extractall(temp_dir, members=safe_members)  # noqa: S202

            # Find the backup directory inside
            backup_dirs = list(temp_dir.glob("backup_*"))
            if not backup_dirs:
                console.print("[red]Invalid backup archive: no backup directory found[/red]")
                if temp_dir:
                    shutil.rmtree(temp_dir)
                return

            backup_dir = backup_dirs[0]
        else:
            backup_dir = backup_path

        # Read metadata
        metadata_file = backup_dir / "backup_metadata.txt"
        if not metadata_file.exists():
            console.print("[red]Invalid backup: metadata file not found[/red]")
            if temp_dir:
                shutil.rmtree(temp_dir)
            return

        # Parse metadata
        metadata = {}
        with metadata_file.open() as f:
            for line in f:
                if ": " in line:
                    key, value = line.strip().split(": ", 1)
                    metadata[key] = value

        # Show what will be restored
        console.print("[bold cyan]Backup Information:[/bold cyan]")
        console.print(f"  • Backup ID: {metadata.get('Backup ID', 'Unknown')}")
        console.print(f"  • Created: {metadata.get('Created', 'Unknown')}")
        console.print(f"  • Items: {metadata.get('Items', 'Unknown')}")

        if dry_run:
            console.print("\n[yellow]DRY RUN: No changes will be made[/yellow]")

            # Show what would be restored
            agents_dir = backup_dir / "agents"
            if agents_dir.exists():
                agent_count = len(list(agents_dir.glob("**/*.md")))
                console.print(f"  • Would restore {agent_count} agents")

            configs_dir = backup_dir / "configs"
            if configs_dir.exists():
                config_files = list(configs_dir.glob("*.json"))
                console.print(f"  • Would restore {len(config_files)} configuration files")
                for config_file in config_files:
                    console.print(f"    - {config_file.name}")

            if temp_dir:
                shutil.rmtree(temp_dir)
            return

        # Confirm restore
        if not force:
            if not typer.confirm(
                "\nAre you sure you want to restore from this backup? This will overwrite existing data."
            ):
                console.print("Restore cancelled")
                if temp_dir:
                    shutil.rmtree(temp_dir)
                return

        # Create backup of current state before restoring
        console.print("\n[dim]Creating backup of current state...[/dim]")
        ctx.invoke(backup, target="auto", include_config=True, compress=True)

        # Perform restore
        restored_items = []

        # Restore agents
        agents_source = backup_dir / "agents"
        if agents_source.exists():
            agents_dest = Path.home() / ".myai" / "agents"
            if agents_dest.exists():
                shutil.rmtree(agents_dest)
            shutil.copytree(agents_source, agents_dest)
            agent_count = len(list(agents_dest.glob("**/*.md")))
            restored_items.append(f"{agent_count} agents")

        # Restore configurations
        configs_source = backup_dir / "configs"
        if configs_source.exists():
            configs_restored = 0

            # Restore user config
            user_config_backup = configs_source / "user_config.json"
            if user_config_backup.exists():
                user_config_path = Path.home() / ".myai" / "config" / "user_config.json"
                user_config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(user_config_backup, user_config_path)
                configs_restored += 1

            # Restore project config
            project_config_backup = configs_source / "project_config.json"
            if project_config_backup.exists() and Path.cwd() != Path.home():
                project_config_path = Path.cwd() / ".myai" / "config.json"
                project_config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(project_config_backup, project_config_path)
                configs_restored += 1

            if configs_restored > 0:
                restored_items.append(f"{configs_restored} configuration files")

        # Clean up temp directory
        if temp_dir:
            shutil.rmtree(temp_dir)

        console.print("\n✅ System restore completed:")
        console.print(f"  • Restored: {', '.join(restored_items)}")
        console.print("\n[dim]You may need to restart MyAI or reload configurations for changes to take effect.[/dim]")

    except Exception as e:
        console.print(f"[red]Error restoring backup: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def clean(
    ctx: typer.Context,
    keep_backups: int = typer.Option(5, "--keep-backups", help="Number of recent backups to keep"),
    dry_run: bool = typer.Option(  # noqa: FBT001
        False, "--dry-run", help="Show what would be cleaned without doing it"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force cleanup without confirmation"),  # noqa: FBT001
):
    """Clean up temporary files and old backups."""
    state: AppState = ctx.obj

    if state.is_debug():
        console.print("[dim]Running system cleanup...[/dim]")

    try:
        myai_path = Path.home() / ".myai"
        items_to_clean = []
        total_size = 0

        # Check for old backups
        backup_dir = myai_path / "backups"
        if backup_dir.exists():
            all_backups = []

            # Find all backup files and directories
            for item in backup_dir.iterdir():
                if item.name.startswith("backup_"):
                    stat = item.stat()
                    all_backups.append((item, stat.st_mtime))

            # Sort by modification time (newest first)
            all_backups.sort(key=lambda x: x[1], reverse=True)

            # Identify backups to remove
            if len(all_backups) > keep_backups:
                for backup_path, _ in all_backups[keep_backups:]:
                    if backup_path.is_file():
                        size = backup_path.stat().st_size
                    else:
                        size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())

                    items_to_clean.append(("backup", backup_path, size))
                    total_size += size

        # Check for temporary files
        temp_dir = myai_path / "temp"
        if temp_dir.exists():
            for temp_item in temp_dir.iterdir():
                if temp_item.is_file():
                    size = temp_item.stat().st_size
                else:
                    size = sum(f.stat().st_size for f in temp_item.rglob("*") if f.is_file())

                items_to_clean.append(("temp", temp_item, size))
                total_size += size

        # Check for cache files
        cache_dir = myai_path / "cache"
        if cache_dir.exists():
            # Clean cache files older than 7 days
            import time

            current_time = time.time()
            seven_days_ago = current_time - (CACHE_EXPIRY_DAYS * 24 * 60 * 60)

            for cache_item in cache_dir.rglob("*"):
                if cache_item.is_file() and cache_item.stat().st_mtime < seven_days_ago:
                    size = cache_item.stat().st_size
                    items_to_clean.append(("cache", cache_item, size))
                    total_size += size

        if not items_to_clean:
            console.print("[green]✅ No items to clean up. System is already clean![/green]")
            return

        # Display what will be cleaned
        console.print(f"[bold cyan]Found {len(items_to_clean)} items to clean:[/bold cyan]")

        # Group by type
        by_type: Dict[str, List[Tuple[Path, int]]] = {}
        for item_type, path, size in items_to_clean:
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append((path, size))

        for item_type, items in by_type.items():
            type_size = sum(size for _, size in items)
            console.print(f"\n[bold]{item_type.capitalize()}:[/bold] {len(items)} items ({_format_size(type_size)})")

            # Show first few items
            for path, size in items[:MAX_DISPLAY_ITEMS]:
                console.print(f"  • {path.name} ({_format_size(size)})")

            if len(items) > MAX_DISPLAY_ITEMS:
                console.print(f"  • ... and {len(items) - MAX_DISPLAY_ITEMS} more")

        console.print(f"\n[bold]Total space to free:[/bold] {_format_size(total_size)}")

        if dry_run:
            console.print("\n[yellow]DRY RUN: No files will be deleted[/yellow]")
            return

        # Confirm cleanup
        if not force:
            if not typer.confirm(f"\nAre you sure you want to delete {len(items_to_clean)} items?"):
                console.print("Cleanup cancelled")
                return

        # Perform cleanup
        console.print("\n[dim]Cleaning up...[/dim]")

        cleaned_count = 0
        freed_space = 0
        errors = []

        for _, path, size in items_to_clean:
            try:
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)

                cleaned_count += 1
                freed_space += size
            except Exception as e:
                errors.append(f"{path.name}: {e}")

        # Display results
        console.print("\n✅ Cleanup completed:")
        console.print(f"  • Items removed: {cleaned_count}/{len(items_to_clean)}")
        console.print(f"  • Space freed: {_format_size(freed_space)}")

        if errors:
            console.print(f"\n[yellow]⚠️ {len(errors)} errors occurred:[/yellow]")
            for error in errors[:MAX_ERROR_DISPLAY]:
                console.print(f"  • {error}")
            if len(errors) > MAX_ERROR_DISPLAY:
                console.print(f"  • ... and {len(errors) - MAX_ERROR_DISPLAY} more")

    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}[/red]")
        if state.is_debug():
            raise


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < BYTES_PER_KB:
            return f"{size:.1f} {unit}"
        size /= BYTES_PER_KB
    return f"{size:.1f} TB"
