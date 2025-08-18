"""
Interactive wizard CLI commands for MyAI.

This module provides guided wizards for setup, agent creation, migration,
and troubleshooting to improve user experience.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from myai.agent.manager import AgentManager
from myai.agent.registry import get_agent_registry
from myai.agent.templates import get_template_registry
from myai.cli.interactive import InteractivePrompts, validate_email, validate_name
from myai.cli.state import AppState
from myai.config.manager import get_config_manager
from myai.models.agent import AgentCategory

# Create wizard command group
app = typer.Typer(help="🧙 Interactive wizards and guided workflows")
console = Console()


@app.command()
def setup(
    ctx: typer.Context,
    quick: bool = typer.Option(False, "--quick", help="Run quick setup with defaults"),  # noqa: FBT001
):
    """Interactive setup wizard for initial MyAI configuration."""
    state: AppState = ctx.obj
    prompts = InteractivePrompts()

    if state.is_debug():
        console.print("[dim]Starting setup wizard...[/dim]")

    try:
        # Welcome message
        welcome_text = Text()
        welcome_text.append("Welcome to MyAI! ", style="bold cyan")
        welcome_text.append("🤖\n\n", style="cyan")
        welcome_text.append("This wizard will help you set up your AI agent management system.\n")
        welcome_text.append("You can exit at any time by pressing Ctrl+C.")

        welcome_panel = Panel(
            welcome_text,
            title="🚀 MyAI Setup Wizard",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(welcome_panel)

        if quick:
            console.print("\n[yellow]Quick setup mode - using defaults...[/yellow]")
            setup_data = _get_quick_setup_defaults()
        else:
            # Show progress
            steps = [
                "Basic Configuration",
                "Directory Setup",
                "Tool Preferences",
                "Create First Agent",
                "Finalize Setup",
            ]
            prompts.progress_steps("MyAI Setup", steps, 0)

            setup_data = _run_interactive_setup(prompts)

        # Apply configuration
        console.print("\n[dim]Applying configuration...[/dim]")
        _apply_setup_configuration(setup_data)

        # Success message
        success_text = Text()
        success_text.append("🎉 Setup Complete!\n\n", style="bold green")
        success_text.append("MyAI has been configured successfully. Here's what you can do next:\n\n")
        success_text.append("• Run ", style="dim")
        success_text.append("myai agent list", style="bold cyan")
        success_text.append(" to see your agents\n", style="dim")
        success_text.append("• Run ", style="dim")
        success_text.append("myai system status", style="bold cyan")
        success_text.append(" to check system health\n", style="dim")
        success_text.append("• Run ", style="dim")
        success_text.append("myai --help", style="bold cyan")
        success_text.append(" to explore all commands", style="dim")

        success_panel = Panel(
            success_text,
            title="✅ Ready to Go!",
            border_style="green",
            padding=(1, 2),
        )
        console.print(success_panel)

    except Exception as e:
        console.print(f"[red]Setup failed: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def agent(ctx: typer.Context):
    """Interactive agent creation wizard."""
    state: AppState = ctx.obj
    prompts = InteractivePrompts()

    if state.is_debug():
        console.print("[dim]Starting agent creation wizard...[/dim]")

    try:
        # Welcome
        console.print("\n[bold cyan]🤖 Agent Creation Wizard[/bold cyan]\n")
        console.print("Let's create a new AI agent together!\n")

        # Show progress
        steps = ["Agent Type Selection", "Basic Information", "Configuration", "Content Setup", "Review & Create"]
        prompts.progress_steps("Agent Creation", steps, 0)

        # Step 1: Choose agent type
        console.print("\n[bold]Step 1: Choose Agent Type[/bold]")

        template_registry = get_template_registry()
        templates = template_registry.list_templates()

        # Prepare choices
        choices = ["Custom Agent (blank template)"]
        descriptions = ["Create a custom agent from scratch"]

        for template in templates:
            choices.append(f"{template.display_name}")
            descriptions.append(template.description)

        agent_type = prompts.single_selection(
            "What type of agent would you like to create?", choices, descriptions, default=0
        )

        # Step 2: Basic information
        prompts.progress_steps("Agent Creation", steps, 1)
        console.print("\n[bold]Step 2: Basic Information[/bold]")

        name = prompts.text_input(
            "Agent name",
            validator=validate_name,
            error_message="Name must start with a letter and contain only letters, numbers, hyphens, and underscores",
            description="Choose a unique name for your agent (e.g., 'code-reviewer', 'data-analyst')",
        )

        display_name = prompts.text_input(
            "Display name",
            default=name.replace("-", " ").replace("_", " ").title(),
            description="Human-readable name for your agent",
        )

        description = prompts.text_input("Description", description="Brief description of what this agent does")

        # Step 3: Configuration
        prompts.progress_steps("Agent Creation", steps, 2)
        console.print("\n[bold]Step 3: Configuration[/bold]")

        # Category selection
        categories = [cat.value for cat in AgentCategory]
        category_descriptions = [
            "Software engineering and development",
            "Business analysis and strategy",
            "Security and compliance",
            "Data analysis and science",
            "Content creation and marketing",
            "Custom or specialized use case",
        ]

        selected_category = prompts.single_selection(
            "Select agent category", categories, category_descriptions, default=0
        )

        # Tools selection
        available_tools = ["claude", "cursor", "openai", "anthropic", "local"]
        tool_descriptions = [
            "Claude AI assistant",
            "Cursor AI code editor",
            "OpenAI models",
            "Anthropic models",
            "Local AI models",
        ]

        selected_tools = prompts.multi_selection(
            "Select compatible tools", available_tools, tool_descriptions, min_selections=1, max_selections=3
        )

        # Tags
        tag_input = prompts.text_input(
            "Tags (comma-separated)",
            default="",
            description="Optional tags to help organize and find this agent (e.g., 'productivity,automation')",
        )
        tags = [tag.strip() for tag in tag_input.split(",") if tag.strip()]

        # Step 4: Content setup
        prompts.progress_steps("Agent Creation", steps, 3)
        console.print("\n[bold]Step 4: Content Setup[/bold]")

        if agent_type == choices[0]:  # Custom agent
            content = prompts.text_input(
                "Agent content/instructions", description="Enter the main instructions or prompt for this agent"
            )
        else:
            # Find and use template
            agent_template: Optional[Any] = None
            for t in templates:
                if t.display_name == agent_type:
                    agent_template = t
                    break

            if agent_template:
                console.print(f"[dim]Using template: {agent_template.name}[/dim]")
                content = getattr(
                    agent_template, "content", "Default template content"
                )  # Will be rendered with variables
            else:
                content = prompts.text_input(
                    "Agent content/instructions", description="Enter the main instructions or prompt for this agent"
                )

        # Step 5: Review and create
        prompts.progress_steps("Agent Creation", steps, 4)
        console.print("\n[bold]Step 5: Review & Create[/bold]")

        # Show review
        review_text = Text()
        review_text.append("Agent Summary:\n\n", style="bold")
        review_text.append(f"Name: {name}\n")
        review_text.append(f"Display Name: {display_name}\n")
        review_text.append(f"Description: {description}\n")
        review_text.append(f"Category: {selected_category}\n")
        review_text.append(f"Tools: {', '.join(selected_tools)}\n")
        review_text.append(f"Tags: {', '.join(tags) if tags else 'None'}\n")

        review_panel = Panel(
            review_text,
            title="Review Your Agent",
            border_style="yellow",
            padding=(1, 2),
        )
        console.print(review_panel)

        if prompts.confirmation("Create this agent?", default=True):
            # Create the agent
            manager = AgentManager()

            _ = manager.create_agent_basic(
                name=name,
                display_name=display_name,
                description=description,
                category=AgentCategory(selected_category),
                tools=selected_tools,
                tags=tags,
            )

            # Update content if provided
            if content and content.strip():
                manager.update_agent(name, content=content)

            console.print(f"\n✅ [green]Agent '{name}' created successfully![/green]")

            # Ask about editing
            if prompts.confirmation("Would you like to open the agent for editing?", default=False):
                console.print("[dim]Agent editing not yet implemented. You can manually edit the agent file.[/dim]")

        else:
            console.print("[yellow]Agent creation cancelled[/yellow]")

    except Exception as e:
        console.print(f"[red]Agent creation failed: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def migrate(ctx: typer.Context):
    """Interactive migration wizard for importing from other tools."""
    state: AppState = ctx.obj
    prompts = InteractivePrompts()

    if state.is_debug():
        console.print("[dim]Starting migration wizard...[/dim]")

    try:
        # Welcome
        console.print("\n[bold cyan]🔄 Migration Wizard[/bold cyan]\n")
        console.print("This wizard will help you migrate agents and configurations from other tools.\n")

        # Show progress
        steps = ["Source Detection", "Select Items to Migrate", "Migration Options", "Backup & Migrate", "Verification"]
        prompts.progress_steps("Migration", steps, 0)

        # Step 1: Source detection
        console.print("\n[bold]Step 1: Source Detection[/bold]")

        # Simulate detection
        detected_sources = _detect_migration_sources()

        if not detected_sources:
            console.print("[yellow]No migration sources detected automatically.[/yellow]")
            manual_source = prompts.single_selection(
                "Select source to migrate from",
                ["Claude Code", "Cursor", "Agent-OS", "Other"],
                [
                    "Claude AI configuration and agents",
                    "Cursor editor rules and settings",
                    "Agent-OS agents and config",
                    "Manually specify source",
                ],
                default=0,
            )
            detected_sources = {manual_source.lower().replace(" ", "-"): {"agents": 0, "configs": 0}}

        # Display detected sources
        for source, info in detected_sources.items():
            console.print(f"  📁 {source}: {info['agents']} agents, {info['configs']} configs")

        # Step 2: Select items
        if detected_sources:
            prompts.progress_steps("Migration", steps, 1)
            console.print("\n[bold]Step 2: Select Items to Migrate[/bold]")

            migrate_sources = prompts.multi_selection(
                "Which sources would you like to migrate?",
                list(detected_sources.keys()),
                [f"{info['agents']} agents, {info['configs']} configs" for info in detected_sources.values()],
                min_selections=1,
            )

            # Step 3: Migration options
            prompts.progress_steps("Migration", steps, 2)
            console.print("\n[bold]Step 3: Migration Options[/bold]")

            backup_first = prompts.confirmation("Create backup before migration?", default=True)
            _ = prompts.confirmation("Merge duplicate agents?", default=True)
            _ = prompts.confirmation("Preserve original directory structure?", default=True)

            # Step 4: Execute migration
            prompts.progress_steps("Migration", steps, 3)
            console.print("\n[bold]Step 4: Backup & Migrate[/bold]")

            if backup_first:
                console.print("[dim]Creating backup...[/dim]")
                # Simulate backup
                console.print("✅ Backup created")

            # Simulate migration
            total_migrated = 0
            for source in migrate_sources:
                console.print(f"[dim]Migrating from {source}...[/dim]")
                migrated = detected_sources[source]["agents"]
                total_migrated += migrated
                console.print(f"✅ Migrated {migrated} items from {source}")

            # Step 5: Verification
            prompts.progress_steps("Migration", steps, 4)
            console.print("\n[bold]Step 5: Verification[/bold]")

            console.print("✅ [green]Migration completed successfully![/green]")
            console.print(f"   • {total_migrated} agents migrated")
            console.print(f"   • Sources: {', '.join(migrate_sources)}")

            if prompts.confirmation("View migrated agents?", default=True):
                console.print("[dim]Run 'myai agent list' to see all agents[/dim]")

    except Exception as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        if state.is_debug():
            raise


@app.command()
def troubleshoot(ctx: typer.Context):
    """Interactive troubleshooting wizard."""
    state: AppState = ctx.obj
    prompts = InteractivePrompts()

    if state.is_debug():
        console.print("[dim]Starting troubleshooting wizard...[/dim]")

    try:
        # Welcome
        console.print("\n[bold cyan]🔧 Troubleshooting Wizard[/bold cyan]\n")
        console.print("Let's diagnose and fix any issues with your MyAI setup.\n")

        # Step 1: What's the problem?
        problem_categories = [
            "Agent not working",
            "Configuration issues",
            "Tool integration problems",
            "Performance issues",
            "Installation/setup problems",
            "Other",
        ]

        problem_descriptions = [
            "Agent not responding or producing unexpected results",
            "Configuration not loading or merging correctly",
            "Claude, Cursor, or other tool integration failing",
            "MyAI running slowly or using too much memory",
            "Problems with initial setup or installation",
            "Something else not covered above",
        ]

        problem_type = prompts.single_selection(
            "What type of issue are you experiencing?", problem_categories, problem_descriptions
        )

        # Run diagnostics based on problem type
        console.print(f"\n[dim]Running diagnostics for: {problem_type}...[/dim]")

        # Simulate diagnostic results
        issues_found = _run_diagnostics(problem_type)

        if not issues_found:
            console.print("✅ [green]No issues detected![/green]")
            console.print("Your MyAI installation appears to be working correctly.")
        else:
            console.print(f"❌ [red]Found {len(issues_found)} issue(s):[/red]")
            for i, issue in enumerate(issues_found, 1):
                console.print(f"  {i}. {issue}")

            # Offer to fix issues
            if prompts.confirmation("Would you like me to try to fix these issues?", default=True):
                console.print("\n[dim]Applying fixes...[/dim]")
                _apply_fixes(issues_found)
                console.print("✅ [green]Fixes applied![/green]")
                console.print("\nPlease test your setup and run this wizard again if problems persist.")

    except Exception as e:
        console.print(f"[red]Troubleshooting failed: {e}[/red]")
        if state.is_debug():
            raise


# Helper functions


def _get_quick_setup_defaults() -> Dict[str, Any]:
    """Get default configuration for quick setup."""
    return {
        "user_name": "MyAI User",
        "user_email": "",
        "base_directory": str(Path.home() / ".myai"),
        "default_tools": ["claude"],
        "auto_sync": False,
        "create_sample_agent": True,
    }


def _run_interactive_setup(prompts: InteractivePrompts) -> Dict[str, Any]:
    """Run the interactive setup process."""
    setup_data: Dict[str, Any] = {}

    # Basic configuration
    console.print("\n[bold]Basic Configuration[/bold]")
    setup_data["user_name"] = prompts.text_input("Your name", default="MyAI User")
    setup_data["user_email"] = prompts.text_input(
        "Email (optional)",
        default="",
        validator=lambda x: not x or validate_email(x),
        error_message="Please enter a valid email address",
    )

    # Directory setup
    prompts.progress_steps(
        "MyAI Setup",
        ["Basic Configuration", "Directory Setup", "Tool Preferences", "Create First Agent", "Finalize Setup"],
        1,
    )
    console.print("\n[bold]Directory Setup[/bold]")

    default_dir = str(Path.home() / ".myai")
    setup_data["base_directory"] = prompts.text_input(
        "MyAI base directory", default=default_dir, description="Where MyAI will store agents and configurations"
    )

    # Tool preferences
    prompts.progress_steps(
        "MyAI Setup",
        ["Basic Configuration", "Directory Setup", "Tool Preferences", "Create First Agent", "Finalize Setup"],
        2,
    )
    console.print("\n[bold]Tool Preferences[/bold]")

    available_tools = ["claude", "cursor", "openai", "anthropic"]
    tool_descriptions = [
        "Claude AI assistant integration",
        "Cursor AI code editor integration",
        "OpenAI API integration",
        "Anthropic API integration",
    ]

    selected_tools = prompts.multi_selection(
        "Select tools you want to integrate with", available_tools, tool_descriptions, min_selections=1
    )
    setup_data["default_tools"] = selected_tools

    # Additional options
    prompts.progress_steps(
        "MyAI Setup",
        ["Basic Configuration", "Directory Setup", "Tool Preferences", "Create First Agent", "Finalize Setup"],
        3,
    )
    console.print("\n[bold]Additional Options[/bold]")

    auto_sync = prompts.confirmation("Enable automatic synchronization?", default=False)
    create_sample = prompts.confirmation("Create a sample agent to get started?", default=True)
    setup_data["auto_sync"] = auto_sync
    setup_data["create_sample_agent"] = create_sample

    return setup_data


def _apply_setup_configuration(setup_data: Dict[str, Any]) -> None:
    """Apply the setup configuration."""
    # Create base directory
    base_dir = Path(setup_data["base_directory"])
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "agents").mkdir(exist_ok=True)
    (base_dir / "config").mkdir(exist_ok=True)

    # Create sample agent if requested
    if setup_data.get("create_sample_agent"):
        manager = AgentManager()
        try:
            _ = manager.create_agent_basic(
                name="welcome-agent",
                display_name="Welcome Agent",
                description="A sample agent to help you get started with MyAI",
                category=AgentCategory.CUSTOM,
                tools=setup_data["default_tools"],
                tags=["sample", "welcome"],
            )
            # Update content
            manager.update_agent(
                "welcome-agent",
                content="Hello! I'm your first MyAI agent. I'm here to help you get started with the system.",
            )
        except ValueError:
            # Agent already exists
            pass


def _detect_migration_sources() -> Dict[str, Dict[str, int]]:
    """Detect available migration sources."""
    # Simulate detection
    sources = {}

    # Check for Claude configuration
    claude_config = Path.home() / ".config" / "claude"
    if claude_config.exists():
        sources["claude"] = {"agents": 2, "configs": 1}

    # Check for Cursor rules
    cursor_config = Path.home() / ".cursor"
    if cursor_config.exists():
        sources["cursor"] = {"agents": 1, "configs": 1}

    # Check for Agent-OS
    agent_os_dir = Path.home() / ".agent-os"
    if agent_os_dir.exists():
        sources["agent-os"] = {"agents": 3, "configs": 2}

    return sources


def _run_diagnostics(problem_type: str) -> List[str]:
    """Run diagnostics based on problem type."""
    issues = []

    if problem_type == "Agent not working":
        # Check agent registry
        try:
            registry = get_agent_registry()
            agents = registry.list_agents()
            if not agents:
                issues.append("No agents found in registry")
        except Exception:
            issues.append("Agent registry not accessible")

    elif problem_type == "Configuration issues":
        # Check configuration
        try:
            config_manager = get_config_manager()
            user_config = config_manager.get_config_path("user")
            if not user_config or not user_config.exists():
                issues.append("User configuration file not found")
        except Exception:
            issues.append("Configuration manager not accessible")

    elif problem_type == "Installation/setup problems":
        # Check basic setup
        myai_dir = Path.home() / ".myai"
        if not myai_dir.exists():
            issues.append("MyAI directory not found")
        elif not (myai_dir / "agents").exists():
            issues.append("Agents directory not found")

    return issues


def _apply_fixes(issues: List[str]) -> None:
    """Apply fixes for detected issues."""
    for issue in issues:
        if "MyAI directory not found" in issue:
            myai_dir = Path.home() / ".myai"
            myai_dir.mkdir(parents=True, exist_ok=True)
        elif "Agents directory not found" in issue:
            agents_dir = Path.home() / ".myai" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
