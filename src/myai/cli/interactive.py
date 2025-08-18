"""
Interactive CLI utilities for MyAI.

This module provides interactive prompt functionality including single/multi selection,
text input with validation, and confirmation prompts using Rich and Typer.
"""

import re
from typing import Callable, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

console = Console()


class InteractivePrompts:
    """Interactive prompt utilities for CLI workflows."""

    @staticmethod
    def single_selection(
        title: str,
        choices: List[str],
        descriptions: Optional[List[str]] = None,
        default: Optional[int] = None,
    ) -> str:
        """
        Present a single selection menu to the user.

        Args:
            title: Title to display above the choices
            choices: List of choices to present
            descriptions: Optional descriptions for each choice
            default: Default choice index (0-based)

        Returns:
            Selected choice string
        """
        if not choices:
            console.print("[red]No choices available[/red]")
            raise typer.Exit(1)

        # Display title
        console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

        # Create table of choices
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Index", style="cyan", width=4)
        table.add_column("Choice", style="white")
        if descriptions:
            table.add_column("Description", style="dim")

        for i, choice in enumerate(choices, 1):
            row = [f"{i}.", choice]
            if descriptions and i - 1 < len(descriptions):
                row.append(descriptions[i - 1])
            table.add_row(*row)

        console.print(table)

        # Get user selection
        while True:
            default_text = f" [default: {default + 1}]" if default is not None else ""
            try:
                selection = IntPrompt.ask(
                    f"\nSelect option{default_text}", default=default + 1 if default is not None else None
                )
                if selection is not None and 1 <= selection <= len(choices):
                    return choices[selection - 1]
                else:
                    console.print(f"[red]Please enter a number between 1 and {len(choices)}[/red]")
            except (ValueError, KeyboardInterrupt):
                console.print("\n[yellow]Selection cancelled[/yellow]")
                raise typer.Exit(1) from None

    @staticmethod
    def multi_selection(
        title: str,
        choices: List[str],
        descriptions: Optional[List[str]] = None,
        min_selections: int = 0,
        max_selections: Optional[int] = None,
    ) -> List[str]:
        """
        Present a multi-selection menu to the user.

        Args:
            title: Title to display above the choices
            choices: List of choices to present
            descriptions: Optional descriptions for each choice
            min_selections: Minimum number of selections required
            max_selections: Maximum number of selections allowed

        Returns:
            List of selected choice strings
        """
        if not choices:
            console.print("[red]No choices available[/red]")
            raise typer.Exit(1)

        # Display title and instructions
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        console.print("[dim]Enter numbers separated by commas (e.g., 1,3,5) or 'all' for all options[/dim]\n")

        # Create table of choices
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Index", style="cyan", width=4)
        table.add_column("Choice", style="white")
        if descriptions:
            table.add_column("Description", style="dim")

        for i, choice in enumerate(choices, 1):
            row = [f"{i}.", choice]
            if descriptions and i - 1 < len(descriptions):
                row.append(descriptions[i - 1])
            table.add_row(*row)

        console.print(table)

        # Get user selections
        while True:
            try:
                user_input = Prompt.ask("\nSelect options").strip()

                if user_input.lower() == "all":
                    selected_indices = list(range(len(choices)))
                else:
                    # Parse comma-separated numbers
                    selected_indices = []
                    for part in user_input.split(","):
                        try:
                            index = int(part.strip()) - 1  # Convert to 0-based
                            if 0 <= index < len(choices):
                                selected_indices.append(index)
                            else:
                                console.print(f"[red]Invalid choice: {part.strip()}[/red]")
                                continue
                        except ValueError:
                            console.print(f"[red]Invalid number: {part.strip()}[/red]")
                            continue

                # Remove duplicates and sort
                selected_indices = sorted(set(selected_indices))

                # Validate selection count
                if len(selected_indices) < min_selections:
                    console.print(f"[red]Please select at least {min_selections} option(s)[/red]")
                    continue

                if max_selections and len(selected_indices) > max_selections:
                    console.print(f"[red]Please select at most {max_selections} option(s)[/red]")
                    continue

                return [choices[i] for i in selected_indices]

            except KeyboardInterrupt:
                console.print("\n[yellow]Selection cancelled[/yellow]")
                raise typer.Exit(1) from None

    @staticmethod
    def text_input(
        prompt: str,
        default: Optional[str] = None,
        password: bool = False,  # noqa: FBT001
        validator: Optional[Callable[[str], bool]] = None,
        error_message: str = "Invalid input",
        description: Optional[str] = None,
    ) -> str:
        """
        Get text input from the user with optional validation.

        Args:
            prompt: Prompt text to display
            default: Default value
            password: Whether to hide input (for passwords)
            validator: Optional validation function
            error_message: Error message for validation failures
            description: Optional description to show above prompt

        Returns:
            User input string
        """
        if description:
            console.print(f"[dim]{description}[/dim]")

        while True:
            try:
                if password:
                    value = typer.prompt(prompt, default=default, hide_input=True)
                else:
                    value = Prompt.ask(prompt, default=default)

                if validator and not validator(value):
                    console.print(f"[red]{error_message}[/red]")
                    continue

                return value

            except KeyboardInterrupt:
                console.print("\n[yellow]Input cancelled[/yellow]")
                raise typer.Exit(1) from None

    @staticmethod
    def confirmation(
        message: str,
        default: bool = False,  # noqa: FBT001
        show_default: bool = True,  # noqa: FBT001
    ) -> bool:
        """
        Ask for user confirmation.

        Args:
            message: Confirmation message
            default: Default response
            show_default: Whether to show the default in prompt

        Returns:
            User confirmation (True/False)
        """
        try:
            return Confirm.ask(message, default=default, show_default=show_default)
        except KeyboardInterrupt:
            console.print("\n[yellow]Confirmation cancelled[/yellow]")
            raise typer.Exit(1) from None

    @staticmethod
    def progress_steps(
        title: str,
        steps: List[str],
        current_step: int = 0,
    ) -> None:
        """
        Display a progress indicator for multi-step wizards.

        Args:
            title: Title of the wizard/process
            steps: List of step descriptions
            current_step: Current step index (0-based)
        """
        # Create progress display
        progress_text = Text()
        progress_text.append(f"{title}\n\n", style="bold cyan")

        for i, step in enumerate(steps):
            if i < current_step:
                progress_text.append("✅ ", style="green")
                progress_text.append(f"{step}\n", style="dim")
            elif i == current_step:
                progress_text.append("🔄 ", style="yellow")
                progress_text.append(f"{step}\n", style="bold white")
            else:
                progress_text.append("⏳ ", style="dim")
                progress_text.append(f"{step}\n", style="dim")

        panel = Panel(
            progress_text,
            title="Progress",
            border_style="blue",
            padding=(1, 2),
        )
        console.print(panel)


# Validation helper functions
def validate_name(name: str) -> bool:
    """Validate agent/configuration names."""
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name))


def validate_email(email: str) -> bool:
    """Validate email addresses."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format."""
    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(pattern, url))


def validate_version(version: str) -> bool:
    """Validate semantic version format."""
    pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$"
    return bool(re.match(pattern, version))
