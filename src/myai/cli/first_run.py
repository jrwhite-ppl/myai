"""
First-run detection and welcome screen for MyAI CLI.

This module handles the initial setup experience for new users, displaying
a welcome message with ASCII logo and collecting initial configuration.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from myai.config.manager import get_config_manager
from myai.storage.filesystem import FileSystemStorage


class FirstRunManager:
    """Manages first-run detection and welcome experience."""

    def __init__(self):
        self.console = Console()
        self.storage = FileSystemStorage(base_path=Path.home() / ".myai")
        self.metadata_key = "app_metadata"

    def has_run_before(self) -> bool:
        """Check if MyAI has been run before."""
        metadata = self.storage.read(self.metadata_key)
        return metadata is not None and metadata.get("first_run_completed", False)

    def mark_first_run_complete(self):
        """Mark that first run has been completed."""
        metadata = self.storage.read(self.metadata_key) or {}
        metadata["first_run_completed"] = True
        self.storage.write(self.metadata_key, metadata)

    def should_show_welcome(self) -> bool:
        """Determine if welcome screen (logo + setup) should be shown for first run."""
        # Skip if already run
        if self.has_run_before():
            return False

        # Skip in CI/CD environments
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return False

        # Skip if output format is JSON
        if "--output" in sys.argv and "json" in sys.argv:
            return False

        # Skip ONLY for version commands (not help)
        # We WANT to show welcome when user runs 'myai' with no args
        skip_commands = ["--version", "version"]
        if any(cmd in sys.argv for cmd in skip_commands):
            return False

        # Show welcome for ANY command on first run, including 'myai' with no args
        return True

    def should_show_logo(self) -> bool:
        """Determine if logo should be shown (for status command)."""
        # Skip in CI/CD environments
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return False

        # Skip if output format is JSON
        if "--output" in sys.argv and "json" in sys.argv:
            return False

        # Show logo for status command
        if "status" in sys.argv:
            return True

        return False

    def display_logo(self):
        """Display the MYAI ASCII logo."""
        logo = """ ███╗   ███╗██╗   ██╗ █████╗ ██╗
 ████╗ ████║╚██╗ ██╔╝██╔══██╗██║
 ██╔████╔██║ ╚████╔╝ ███████║██║
 ██║╚██╔╝██║  ╚██╔╝  ██╔══██║██║
 ██║ ╚═╝ ██║   ██║   ██║  ██║██║
 ╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝"""
        self.console.print(Text(logo, style="bold cyan"))
        self.console.print()

    def run_welcome_setup(self) -> bool | str:
        """Run the interactive welcome setup with logo.

        Returns:
            bool | str: True if setup completed successfully, False if cancelled,
                       "install_all" if user chose to run installation.
        """
        try:
            # Always show logo as part of welcome
            self.display_logo()

            # Welcome message
            welcome_panel = Panel(
                "Welcome to [bold cyan]MyAI[/bold cyan]! 🤖\n\n"
                "Your AI Agent and Configuration Management CLI\n\n"
                "Let's quickly set up your environment to get you started.",
                title="[bold]First Time Setup[/bold]",
                border_style="cyan",
            )
            self.console.print(welcome_panel)
            self.console.print()

            # Check if we can do interactive prompts
            is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

            if is_interactive:
                # Ask for user name (optional)
                name = typer.prompt("What's your name? (optional, press Enter to skip)", default="", show_default=False)

                # Ask about installation
                self.console.print("\n[bold]Quick Setup Options:[/bold]")
                self.console.print("• Install all integrations (Claude, Cursor, default agents)")
                self.console.print("• Set up global configuration")
                self.console.print("• Enable recommended agents\n")

                install_all = typer.confirm("Would you like to run the complete setup now? (recommended)", default=True)
            else:
                # Non-interactive mode - use defaults
                name = ""
                install_all = False
                self.console.print("\n[dim]Running in non-interactive mode - skipping setup prompts[/dim]")

            # Store preferences
            if name:
                # Update user config with name
                config_manager = get_config_manager()
                config_manager.set_config_value("user.name", name, level="user")

            # Mark first run as complete
            self.mark_first_run_complete()

            # Success message and next steps
            self.console.print()
            if install_all:
                self.console.print("[green]✅ Great! Running the complete setup now...[/green]\n")
                # Run the install command instead of continuing with original command
                return "install_all"
            else:
                self.console.print(
                    "[green]✅ Setup complete! "
                    "Run '[bold]myai status[/bold]' anytime to check your configuration.[/green]"
                )
                self.console.print("\n[dim]Welcome complete. Run your MyAI commands to get started![/dim]\n")
                return True

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup cancelled. You can run 'myai wizard setup' anytime.[/yellow]")
            self.mark_first_run_complete()  # Still mark as complete to avoid annoyance
            return False
        except Exception as e:
            self.console.print(f"\n[red]Setup error: {e}[/red]")
            self.mark_first_run_complete()  # Mark complete to avoid blocking
            return False


# Singleton instance
_first_run_manager: Optional[FirstRunManager] = None


def get_first_run_manager() -> FirstRunManager:
    """Get the singleton FirstRunManager instance."""
    global _first_run_manager  # noqa: PLW0603
    if _first_run_manager is None:
        _first_run_manager = FirstRunManager()
    return _first_run_manager
