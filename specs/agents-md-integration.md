# AGENTS.md Integration Specification for MyAI

## Overview
This specification describes how MyAI integrates the AGENTS.md standard as a core part of its design. Following the Agent-OS philosophy, MyAI treats AGENTS.md as the standard interface for communicating project context to AI agents, while leveraging MyAI's rich agent system capabilities.

## Goals
1. Make AGENTS.md a fundamental part of every MyAI project
2. Automatically maintain AGENTS.md files that reflect enabled agents
3. Provide seamless integration between MyAI agents and the AGENTS.md standard
4. Support the open AGENTS.md standard for compatibility with other AI tools
5. Enable hierarchical AGENTS.md files throughout project directories
6. Bootstrap projects with comprehensive agent references by default

## AGENTS.md Integration Design

### Core Integration Philosophy

AGENTS.md is a fundamental part of MyAI's design, not a separate feature. Like Agent-OS, MyAI treats AGENTS.md as the standard way to communicate project guidelines to AI agents. Every MyAI project automatically includes an AGENTS.md file that:

1. Is created by default during `myai install project`
2. Is automatically updated when agents are enabled/disabled
3. Provides a bridge between MyAI's agent system and standard AI tools
4. Maintains compatibility with the AGENTS.md open standard

### Seamless Management

AGENTS.md management is integrated directly into agent commands:

```bash
# When setting up a project, AGENTS.md is created automatically
myai install project

# When enabling agents, AGENTS.md is updated automatically
myai agent enable lead-developer security-analyst

# When disabling agents, AGENTS.md is updated automatically
myai agent disable lead-developer

# The root AGENTS.md reflects the current state of enabled agents
cat AGENTS.md
```

### Behind-the-Scenes Management

While AGENTS.md appears as a simple markdown file to users and AI tools, MyAI maintains internal tracking for advanced features:

- Automatic synchronization with enabled/disabled agents
- Support for hierarchical AGENTS.md files in subdirectories
- Preservation of custom content added by users
- Integration with MyAI's agent registry system

This tracking is invisible to users - they simply see AGENTS.md files that "just work" and stay in sync with their agent configuration.

### Automatic AGENTS.md Generation

The root AGENTS.md is automatically generated and maintained by MyAI. It dynamically includes all enabled agents for the project:

```markdown
# AGENTS.md - Project Guidelines

This project is managed with MyAI agents. The following specialized agents are available:

## Available Agents

### Lead Developer (@myai/agents/engineering/lead-developer)
Technical leadership, architecture decisions, and code quality standards.

### Security Engineer (@myai/agents/security/security-analyst)
Security reviews, vulnerability assessments, and secure coding practices.

### DevOps Engineer (@myai/agents/engineering/devops-engineer)
CI/CD pipelines, deployment strategies, and infrastructure management.

### Documentation Writer (@myai/agents/business/technical-writer)
API documentation, user guides, and technical specifications.

## Project-Specific Guidelines

### Development Environment
- [Project-specific setup instructions]

### Code Style

## User Experience

### Seamless Integration

From the user's perspective, AGENTS.md "just works":

1. **Project Setup**: Running `myai install project` automatically creates an AGENTS.md file with enabled agents
2. **Agent Management**: Enabling or disabling agents automatically updates AGENTS.md
3. **No Extra Commands**: No need to learn separate AGENTS.md management commands
4. **Standard Compliance**: The generated AGENTS.md follows the open standard and works with any AI tool

### Example Workflow

```bash
# Initialize a new project
cd my-project
myai install project

# AGENTS.md is automatically created with default agents
cat AGENTS.md
# Shows project guidelines and enabled Agent-OS agents

# Enable additional agents
myai agent enable lead-developer security-analyst

# AGENTS.md is automatically updated
cat AGENTS.md
# Now includes lead-developer and security-analyst references

# Disable an agent
myai agent disable security-analyst

# AGENTS.md is automatically updated to remove the reference
```

### Benefits

- **Zero Learning Curve**: Users don't need to learn AGENTS.md-specific commands
- **Always in Sync**: AGENTS.md always reflects the current agent configuration
- **Industry Standard**: Compatible with Claude, Cursor, and other AI tools that support AGENTS.md
- **Extensible**: Users can add custom guidelines while MyAI maintains agent references
- [Project-specific conventions]

### Testing
- [Project-specific testing requirements]

### Security
- [Project-specific security policies]
```

### Subdirectory AGENTS.md

Subdirectory AGENTS.md files focus on their specific context:

```markdown
# AGENTS.md - API Module

This directory contains the REST API implementation.

## Module-Specific Guidelines

### API Design
- Follow RESTful principles
- Use consistent error responses
- Version all endpoints

### Testing
- Unit test all endpoints
- Integration tests for critical paths
- Load testing for performance endpoints

### Documentation
- OpenAPI/Swagger specs required
- Example requests/responses
- Error code documentation
```

### Integration with Install/Uninstall

The AGENTS.md system will be integrated into existing MyAI commands:

```python
# During myai install project
def setup_agents_md(project_path: Path, force: bool = False):
    """Setup AGENTS.md files for a project."""
    root_agents_md = project_path / "AGENTS.md"

    if root_agents_md.exists() and not force:
        console.print("[yellow]AGENTS.md already exists, skipping...[/yellow]")
        return

    # Create root AGENTS.md from template
    template = load_agents_md_template("engineering-project")

    # Customize with enabled agents
    enabled_agents = get_enabled_agents()
    template = customize_template(template, enabled_agents)

    # Write file
    root_agents_md.write_text(template)

    # Register in tracking system
    register_agents_md(root_agents_md, enabled=True, type="root")

# During myai install uninstall
def cleanup_agents_md(project_path: Path, force: bool = False):
    """Remove MyAI-managed AGENTS.md files."""
    registry = load_agents_md_registry(project_path)

    for entry in registry.files:
        if entry.type == "root" and is_myai_managed(entry.path):
            if force:
                Path(entry.path).unlink()
            else:
                # Preserve user modifications
                backup_user_content(entry.path)
                remove_myai_sections(entry.path)
```

## Proposed Architecture

### 1. Agent Context Enhancement

MyAI agents will gain the ability to read and incorporate AGENTS.md files:

```python
# New fields in AgentSpecification model
class AgentSpecification(BaseModel):
    # ... existing fields ...

    # Project context from AGENTS.md
    project_context: Optional[Dict[str, str]] = None
    project_context_source: Optional[Path] = None

    # Merge strategy for combining base agent with project context
    context_merge_strategy: Literal["append", "prepend", "replace", "smart"] = "smart"
```

### 2. AGENTS.md Parser

Create a dedicated parser for AGENTS.md files:

```python
# src/myai/agents_md/parser.py
class AgentsMdParser:
    """Parse AGENTS.md files and extract structured sections."""

    def parse(self, file_path: Path) -> Dict[str, str]:
        """
        Parse AGENTS.md file into sections.

        Returns:
            Dictionary mapping section names to content
        """
        sections = {
            "overview": "",
            "dev_environment": "",
            "testing": "",
            "code_style": "",
            "pr_instructions": "",
            "security": "",
            "custom": {}
        }
        # Implementation details...

    def extract_commands(self, content: str) -> List[Dict[str, str]]:
        """Extract executable commands from content."""
        # Parse code blocks, command examples, etc.
```

### 3. Context-Aware Agent Loading

Enhance the agent registry to automatically load project context:

```python
# Enhanced agent loading in registry
class AgentRegistry:
    def get_agent(self, name: str, project_path: Optional[Path] = None) -> Agent:
        """Get agent with optional project context."""
        base_agent = self._load_base_agent(name)

        if project_path:
            agents_md = self._find_agents_md(project_path)
            if agents_md:
                context = self._parser.parse(agents_md)
                base_agent = self._apply_project_context(base_agent, context)

        return base_agent
```

### 4. Integration Commands

Enhanced CLI commands for AGENTS.md integration:

```bash
# AGENTS.md file management
myai agent agents-md list                    # List all AGENTS.md files in project
myai agent agents-md create [PATH]           # Create new AGENTS.md file
myai agent agents-md show [PATH]             # Display AGENTS.md content
myai agent agents-md edit [PATH]             # Edit AGENTS.md file
myai agent agents-md delete [PATH]           # Delete AGENTS.md file
myai agent agents-md enable [PATH]           # Enable AGENTS.md file
myai agent agents-md disable [PATH]          # Disable AGENTS.md file
myai agent agents-md status                  # Show status of all files

# Agent integration commands
myai agent export AGENT --format agents-md   # Export agent to AGENTS.md format
myai agent preview AGENT --context PATH      # Preview agent with AGENTS.md context

# Project setup integration
myai install project --with-agents-md        # Setup project with AGENTS.md
myai install uninstall --force               # Remove all including AGENTS.md
```

### 5. Smart Context Merging

Implement intelligent merging of base agent instructions with project context:

```python
class ContextMerger:
    """Intelligently merge agent instructions with project context."""

    def merge(self, base: str, context: Dict[str, str], strategy: str) -> str:
        if strategy == "smart":
            # Intelligent section-based merging
            return self._smart_merge(base, context)
        elif strategy == "append":
            return base + "\n\n" + self._format_context(context)
        elif strategy == "prepend":
            return self._format_context(context) + "\n\n" + base
        elif strategy == "replace":
            return self._format_context(context)
```

## Example Usage

### Scenario 1: Python Expert with Project Context

Given this AGENTS.md:
```markdown
# AGENTS.md

## Dev Environment
- Use Poetry for dependency management
- Python 3.11+ required
- Pre-commit hooks must pass

## Code Style
- Use Black with line length 100
- Type hints required for all public functions
- Docstrings in NumPy style

## Testing
- Pytest with 90% coverage requirement
- Run `make test` before commits
```

The Python Expert agent would automatically:
- Recommend Poetry commands instead of pip
- Format code with Black at 100 char lines
- Generate NumPy-style docstrings
- Suggest pytest-specific testing patterns

### Scenario 2: Dynamic Agent Creation

```bash
# Create a lightweight agent from AGENTS.md
myai agent create-from-agents-md ./AGENTS.md --name project-guide

# This creates an agent that:
# - Knows all project-specific commands
# - Understands the testing workflow
# - Follows project code style
# - Can guide through PR process
```

### Scenario 3: Export for Compatibility

```bash
# Export MyAI agent for use with other tools
myai agent export lead-developer --format agents-md

# Generates AGENTS.md with:
# - Core competencies as capabilities section
# - Decision framework as guidelines
# - Communication style as interaction notes
# - Technical specs as requirements
```

## AGENTS.md Registry Model

The registry tracks all AGENTS.md files and their relationships:

```python
# src/myai/models/agents_md.py
class AgentsMdEntry(BaseModel):
    """Registry entry for an AGENTS.md file."""
    path: Path
    enabled: bool = True
    type: Literal["root", "subdirectory"] = "subdirectory"
    agents: List[str] = Field(default_factory=list)
    inherits_from: Optional[Path] = None
    last_modified: datetime
    checksum: str

class AgentsMdRegistry(BaseModel):
    """Registry of all AGENTS.md files in a project."""
    version: str = "1.0.0"
    project_root: Path
    files: List[AgentsMdEntry] = Field(default_factory=list)
    default_agents: List[str] = Field(
        default_factory=lambda: [
            "lead-developer",
            "security-analyst",
            "devops-engineer",
            "technical-writer"
        ]
    )
```

## Implementation Phases

### Phase 1: AGENTS.md Management System (Week 1)
- [ ] Create AGENTS.md registry model and storage
- [ ] Implement discovery system for finding AGENTS.md files
- [ ] Add CRUD operations (create, read, update, delete)
- [ ] Implement enable/disable functionality
- [ ] Create `myai agent agents-md` subcommand group

### Phase 2: Bootstrap and Templates (Week 2)
- [ ] Create root AGENTS.md template with MyAI agent references
- [ ] Create subdirectory templates for common project structures
- [ ] Integrate with `myai install project` command
- [ ] Implement preserve/force logic for existing files
- [ ] Add uninstall support with cleanup

### Phase 3: Context Integration (Week 3)
- [ ] Create AGENTS.md parser for extracting sections
- [ ] Implement context merging with agent definitions
- [ ] Add preview functionality to show enhanced agents
- [ ] Update agent loading to consider AGENTS.md context
- [ ] Create tests for context-aware agents

### Phase 4: Advanced Features (Week 4)
- [ ] Add inheritance system for subdirectory AGENTS.md
- [ ] Implement export of MyAI agents to AGENTS.md format
- [ ] Add validation and linting for AGENTS.md files
- [ ] Create documentation and examples
- [ ] Performance optimization for large projects

## Benefits

1. **Standards Compliance**: Align with industry-standard AGENTS.md format
2. **Flexibility**: Support both rich agents and simple project instructions
3. **Compatibility**: Work seamlessly with other AI coding tools
4. **User Choice**: Let users decide between detailed agents or simple contexts
5. **Future-Proof**: Ready for the growing AGENTS.md ecosystem

## Considerations

1. **Performance**: Cache parsed AGENTS.md files
2. **Conflicts**: Clear rules for handling instruction conflicts
3. **Validation**: Ensure AGENTS.md files are well-formed
4. **Discovery**: Smart detection of AGENTS.md in project hierarchies
5. **Security**: Validate commands and paths in AGENTS.md files

## Example Implementation

Here's a simple example of how the Python Expert agent would incorporate project context:

```python
# src/myai/agents_md/integration.py
class AgentsmdIntegration:
    def enhance_agent(self, agent: Agent, agents_md_path: Path) -> Agent:
        """Enhance an agent with AGENTS.md context."""
        parser = AgentsMdParser()
        context = parser.parse(agents_md_path)

        # Create enhanced instructions
        enhanced_content = f"""
{agent.content}

## Project-Specific Context

### Development Environment
{context.get('dev_environment', 'No specific environment requirements.')}

### Code Style Guidelines
{context.get('code_style', 'Follow standard conventions.')}

### Testing Requirements
{context.get('testing', 'Write appropriate tests.')}

### PR Process
{context.get('pr_instructions', 'Follow standard PR process.')}
"""

        # Return enhanced agent
        return agent.model_copy(update={"content": enhanced_content})
```

This integration would make MyAI a powerful bridge between rich, personality-driven agents and the simple, standard AGENTS.md format, providing the best of both worlds.

## Implementation Details

### AGENTS.md Discovery System

```python
# src/myai/agents_md/discovery.py
class AgentsMdDiscovery:
    """Discover and track AGENTS.md files in a project."""

    def discover(self, project_root: Path) -> List[Path]:
        """Find all AGENTS.md files in the project."""
        agents_md_files = []

        # Find all AGENTS.md files
        for agents_md in project_root.rglob("AGENTS.md"):
            # Skip hidden directories and common ignore patterns
            if not any(part.startswith('.') for part in agents_md.parts[:-1]):
                if not self._is_ignored(agents_md):
                    agents_md_files.append(agents_md)

        return sorted(agents_md_files)

    def _is_ignored(self, path: Path) -> bool:
        """Check if path should be ignored."""
        ignore_patterns = ['node_modules', 'venv', '.venv', 'dist', 'build']
        return any(pattern in path.parts for pattern in ignore_patterns)
```

### AGENTS.md Template System

```python
# src/myai/agents_md/templates.py
TEMPLATES = {
    "root": """# AGENTS.md - {project_name}

This project is enhanced with MyAI agents for comprehensive development support.

## Available AI Agents

{agent_sections}

## Project Guidelines

### Development Environment
- {dev_environment}

### Code Standards
- {code_standards}

### Testing Requirements
- {testing_requirements}

### Security Policies
- {security_policies}

## Getting Started

1. Install dependencies: `{install_command}`
2. Run tests: `{test_command}`
3. Start development: `{dev_command}`

---
Generated by MyAI - Manage with: `myai agent agents-md`
""",

    "api": """# AGENTS.md - API Module

## API-Specific Guidelines

### Design Principles
- RESTful architecture
- Consistent error handling
- Comprehensive validation

### Endpoints
- Follow naming conventions
- Document all parameters
- Include example requests

### Testing
- Unit tests for each endpoint
- Integration test suites
- Performance benchmarks
""",

    "frontend": """# AGENTS.md - Frontend Module

## Frontend Guidelines

### Component Architecture
- Reusable components
- Clear prop interfaces
- Proper state management

### Styling
- Consistent design system
- Responsive layouts
- Accessibility first

### Performance
- Code splitting
- Lazy loading
- Bundle optimization
"""
}
```

### Enable/Disable System

```python
# src/myai/agents_md/manager.py
class AgentsMdManager:
    """Manage AGENTS.md files in a project."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.registry_path = project_root / ".myai" / "agents-md-registry.json"
        self.registry = self._load_registry()

    def enable(self, path: Path) -> None:
        """Enable an AGENTS.md file."""
        entry = self._get_or_create_entry(path)
        entry.enabled = True
        self._save_registry()

        # Trigger re-sync with integrations
        self._sync_integrations()

    def disable(self, path: Path) -> None:
        """Disable an AGENTS.md file."""
        entry = self._get_or_create_entry(path)
        entry.enabled = False
        self._save_registry()

        # Update integrations
        self._sync_integrations()

    def create(self, path: Path, template: str = "root") -> None:
        """Create a new AGENTS.md file."""
        if path.exists():
            raise FileExistsError(f"AGENTS.md already exists at {path}")

        # Get template
        content = TEMPLATES.get(template, TEMPLATES["root"])

        # Customize template
        content = self._customize_template(content, path)

        # Write file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        # Register
        self._register_file(path, enabled=True)
```

### Integration with Project Setup

```python
# Updated src/myai/commands/install_cli.py
@app.command(name="project")
def install_project(
    with_agents_md: bool = typer.Option(True, "--with-agents-md/--no-agents-md",
                                       help="Include AGENTS.md setup"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files")
):
    """Setup project with MyAI configuration."""
    project_root = Path.cwd()

    # Existing setup code...

    if with_agents_md:
        console.print("\n[bold]Setting up AGENTS.md integration[/bold]")

        # Create AGENTS.md manager
        manager = AgentsMdManager(project_root)

        # Create root AGENTS.md
        root_agents_md = project_root / "AGENTS.md"
        if root_agents_md.exists() and not force:
            console.print("[yellow]AGENTS.md exists, preserving...[/yellow]")
        else:
            # Get enabled agents
            config = get_config_manager().get_config()
            agents = config.agents.enabled + config.agents.global_enabled

            # Create from template
            manager.create(root_agents_md, template="root")
            console.print("✅ Created root AGENTS.md")

        # Register with integrations
        _update_claude_settings_for_agents_md(project_root)
        _update_cursor_rules_for_agents_md(project_root)
```

### Usage Examples

```bash
# Setup new project with AGENTS.md
$ myai install project --with-agents-md
🚀 Setting up project configuration...
✅ Created .myai directory
✅ Created .claude directory
✅ Created .cursor directory
✅ Created root AGENTS.md with 4 default agents

# List all AGENTS.md files
$ myai agent agents-md list
📄 AGENTS.md Files in Project
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Path                ┃ Status   ┃ Type      ┃ Agents      ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ ./AGENTS.md         │ ✅ Enabled │ root      │ 4 agents    │
│ ./src/api/AGENTS.md │ ✅ Enabled │ subdirectory │ inherits   │
│ ./tests/AGENTS.md   │ ❌ Disabled │ subdirectory │ testing    │
└─────────────────────┴──────────┴───────────┴─────────────┘

# Create subdirectory AGENTS.md
$ myai agent agents-md create src/api/AGENTS.md --template api
✅ Created AGENTS.md at src/api/AGENTS.md

# Disable a specific file
$ myai agent agents-md disable ./tests/AGENTS.md
✅ Disabled ./tests/AGENTS.md

# Show AGENTS.md content
$ myai agent agents-md show ./AGENTS.md
[Shows formatted content]

# Export an agent to AGENTS.md format
$ myai agent export python-expert --format agents-md
[Outputs AGENTS.md formatted content]
```
