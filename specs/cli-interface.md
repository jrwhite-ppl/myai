# CLI Interface Specification

## Overview

The MyAI CLI provides an intuitive, powerful command-line interface built with Typer and Rich. It follows modern CLI design principles with clear command hierarchies, helpful documentation, and beautiful output formatting.

## Command Structure

### Root Command
```bash
myai [OPTIONS] COMMAND [ARGS]...

Options:
  --version              Show version and exit
  --config PATH          Config file path [default: ~/.myai/config/global.json]
  --verbose, -v          Verbose output (repeat for more verbosity)
  --quiet, -q            Suppress non-essential output
  --format FORMAT        Output format [json|yaml|table|plain]
  --no-color             Disable colored output
  --help                 Show help and exit

Commands:
  init        Initialize MyAI configuration
  config      Manage configurations
  agent       Manage AI agents
  sync        Synchronize with AI tools
  migrate     Migrate from other tools
  backup      Backup and restore operations
  status      Show system status
  doctor      Diagnose and fix issues
```

## Core Commands

### 1. Initialization Command
```bash
myai init [OPTIONS]

Options:
  --mode [quick|guided|enterprise]  Setup mode [default: quick]
  --force                          Overwrite existing configuration
  --import-from [claude|cursor]    Import existing tool configs
  --no-agents                      Skip default agent installation
  --minimal                        Minimal setup (config only)

Examples:
  myai init                        # Quick setup with defaults
  myai init --mode guided          # Interactive setup wizard
  myai init --import-from claude   # Import Claude settings
  myai init --force --minimal      # Reset to minimal config
```

### 2. Configuration Commands
```bash
myai config [COMMAND]

Commands:
  show     Display configuration
  get      Get specific configuration value
  set      Set configuration value
  merge    Merge configuration file
  validate Validate configuration
  backup   Backup current configuration
  restore  Restore configuration backup
  reset    Reset configuration to defaults
  diff     Show configuration differences

Examples:
  myai config show --level merged           # Show merged config
  myai config get tools.claude.enabled      # Get specific value
  myai config set tools.cursor.enabled true # Set value
  myai config merge team-config.json        # Merge config file
  myai config backup --name "pre-update"    # Create backup
  myai config diff --with yesterday         # Compare configs
```

### 3. Agent Commands
```bash
myai agent [COMMAND]

Commands:
  list       List available agents
  show       Show agent details
  search     Search agents
  create     Create new agent
  edit       Edit existing agent
  delete     Delete agent
  enable     Enable agent
  disable    Disable agent
  sync       Sync agents to tools
  validate   Validate agent specs
  recommend  Recommend agents for task
  export     Export agent(s)
  import     Import agent(s)

Examples:
  myai agent list --category engineering     # List by category
  myai agent show lead_developer            # Show agent details
  myai agent search "python backend"        # Search agents
  myai agent create my-expert --interactive # Create interactively
  myai agent sync claude --all              # Sync all to Claude
  myai agent recommend "build REST API"     # Get recommendations
```

### 4. Synchronization Commands
```bash
myai sync [TOOL] [OPTIONS]

Tools:
  all     Sync all configured tools
  claude  Sync with Claude Code
  cursor  Sync with Cursor
  status  Show sync status

Options:
  --agents              Sync agents only
  --config              Sync configuration only
  --force               Force overwrite
  --dry-run             Preview changes
  --backup              Backup before sync

Examples:
  myai sync all                    # Sync everything
  myai sync claude --agents        # Sync agents to Claude
  myai sync cursor --dry-run       # Preview Cursor sync
  myai sync status                 # Check sync status
```

### 5. Migration Commands
```bash
myai migrate [SOURCE] [OPTIONS]

Sources:
  detect     Auto-detect and migrate
  claude     Migrate from Claude Code
  cursor     Migrate from Cursor
  agent-os   Migrate from Agent-OS

Options:
  --merge               Merge with existing config
  --backup              Backup before migration
  --components LIST     Specific components to migrate
  --dry-run            Preview migration

Examples:
  myai migrate detect              # Auto-detect and migrate
  myai migrate claude --merge      # Merge Claude settings
  myai migrate agent-os           # Import Agent-OS setup
```

### 6. System Commands
```bash
myai system [COMMAND] [OPTIONS]

Commands:
  doctor                Run system diagnostics
  integration-list      List available integrations
  integration-health    Check integration health
  integration-import    Import agents from integrations
  integration-validate  Validate integration configs
  integration-backup    Backup integration configs
  backup               Create system backup
  restore              Restore from backup
  clean                Clean temporary files

Options:
  --integration, -i     Specific integration(s)
  --backup             Create backup before operations
  --merge              Merge with existing
  --force              Force operation

Examples:
  myai system doctor                        # Run diagnostics
  myai system integration-import -i claude  # Import custom agents
  myai system integration-health            # Check all integrations
  myai system backup                        # Create full backup
```

## Interactive Features

### 1. Guided Setup Wizard
```
$ myai init --mode guided

Welcome to MyAI Setup Wizard! 🚀

[1/5] Configuration Scope
Which configuration level would you like to set up?
> ● User (personal settings)
  ○ Team (shared team settings)
  ○ Project (project-specific)
  ○ Enterprise (organization-wide)

[2/5] AI Tools
Which AI tools do you use? (space to select, enter to continue)
> ☑ Claude Code
  ☑ Cursor
  ☐ GitHub Copilot
  ☐ Other

[3/5] Default Agents
Select default agents to install:
> ☑ Lead Developer
  ☑ DevOps Engineer
  ☐ Security Analyst
  ☑ QA Engineer
  [Show more...]

[4/5] Integration Settings
Configure tool integrations:
- Claude Code path: ~/.claude [✓ Found]
- Cursor path: ~/Library/Application Support/Cursor [✓ Found]
- Auto-sync enabled? [Y/n]: Y

[5/5] Review and Confirm
Configuration Summary:
─────────────────────
Level: User
Tools: Claude Code, Cursor
Agents: 8 selected
Auto-sync: Enabled

Proceed with setup? [Y/n]: Y

✨ Setup complete! Run 'myai status' to verify.
```

### 2. Agent Creation Wizard
```
$ myai agent create --interactive

Creating New Agent 🤖

Agent Identifier (lowercase, no spaces): python_expert
Display Name: Python Expert
Category: [engineering|product|business|custom]: engineering
Primary Purpose (one line): Expert Python developer specializing in backend systems

Tags (comma-separated): python, backend, fastapi, testing
Requires Tools (comma-separated) [default: all]: Task, Bash, Read, Edit, Grep

Would you like to:
1. Start from scratch
2. Use a template
3. Clone existing agent

Choice [1-3]: 2

Available Templates:
1. base_agent - Minimal agent template
2. engineering_base - Engineering-focused template
3. backend_specialist - Backend development template

Select template [1-3]: 3

Opening editor for customization...
[Editor opens with pre-filled template]

✅ Agent 'python_expert' created successfully!
```

## Output Formatting

### 1. Table Format (Default)
```
$ myai agent list

                          Available Agents
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Name               ┃ Category      ┃ Status     ┃ Last Used   ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ lead_developer     │ engineering   │ ✅ Enabled │ 2 hours ago │
│ devops_engineer    │ engineering   │ ✅ Enabled │ Yesterday   │
│ security_analyst   │ security      │ ⚠️ Disabled│ Never       │
│ product_manager    │ product       │ ✅ Enabled │ Last week   │
└────────────────────┴───────────────┴────────────┴─────────────┘
```

### 2. JSON Format
```json
$ myai agent list --format json

{
  "agents": [
    {
      "name": "lead_developer",
      "category": "engineering",
      "status": "enabled",
      "last_used": "2025-01-16T08:00:00Z"
    }
  ]
}
```

### 3. Progress Indicators
```
$ myai sync all

Synchronizing configurations...
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Task                         ┃ Status    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Loading configurations       │ ✅ Done   │
│ Syncing to Claude Code      │ ⏳ 45%    │
│ Syncing to Cursor           │ ⏸️  Pending│
│ Updating agent registry     │ ⏸️  Pending│
└──────────────────────────────┴───────────┘
```

## Error Handling

### 1. User-Friendly Error Messages
```
$ myai config set invalid.key value

❌ Configuration Error

Cannot set 'invalid.key': Key does not exist in schema

💡 Suggestions:
  • Use 'myai config show --schema' to see valid keys
  • Did you mean 'tools.invalid.key'?
  • Check for typos in the key path

Run 'myai config set --help' for more information
```

### 2. Validation Errors
```
$ myai agent create "invalid name"

❌ Validation Error

Agent name 'invalid name' is invalid:
  ✗ Contains spaces (use underscores instead)
  ✗ Must be lowercase

Valid example: 'invalid_name'

Try again with a valid name.
```

### 3. Recovery Suggestions
```
$ myai sync claude

⚠️  Sync Failed

Could not sync to Claude Code: Configuration file locked

Possible solutions:
1. Check if Claude Code is running
2. Try 'myai doctor' to diagnose issues
3. Force sync with 'myai sync claude --force'
4. Restore previous config: 'myai config restore'

Error details (--verbose for full trace):
  FileLockedError: ~/.claude/settings.json
```

## Advanced Features

### 1. Shell Completion
```bash
# Install completions
myai --install-completion bash|zsh|fish

# Usage
myai config set tools.<TAB>
# Shows: tools.claude  tools.cursor  tools.github
```

### 2. Aliases and Shortcuts
```bash
# Built-in aliases
myai ls    → myai agent list
myai show  → myai agent show
myai cfg   → myai config

# Custom aliases (in config)
{
  "aliases": {
    "pull": "sync all --backup",
    "push": "sync all --agents --config"
  }
}
```

### 3. Batch Operations
```bash
# Batch enable agents
myai agent enable lead_developer devops_engineer qa_engineer

# Batch operations from file
myai agent enable --from-file agents.txt

# Pipeline support
myai agent list --format json | jq '.agents[].name' | xargs myai agent validate
```

### 4. Scripting Support
```bash
# Non-interactive mode
MYAI_NONINTERACTIVE=1 myai init --force

# Machine-readable output
myai agent list --format json --no-color

# Exit codes
# 0 - Success
# 1 - General error
# 2 - Validation error
# 3 - Configuration error
# 4 - Tool integration error
```

## Help System

### 1. Contextual Help
```
$ myai agent --help

Usage: myai agent [OPTIONS] COMMAND [ARGS]...

  Manage AI agents - specialized assistants for various tasks.

  Agents are AI personalities with specific expertise and behaviors.
  Use these commands to discover, create, and manage agents.

Commands:
  list       List available agents
  show       Show detailed agent information
  create     Create a new agent
  ...

Examples:
  myai agent list                    # Show all agents
  myai agent show lead_developer     # View specific agent
  myai agent create my_agent         # Create new agent

See 'myai agent COMMAND --help' for more information on a command.
```

### 2. Interactive Help
```
$ myai help

MyAI Help System 📚

What would you like help with?
1. Getting Started
2. Configuration Management
3. Agent Management
4. Tool Integration
5. Troubleshooting
6. Advanced Topics

Choice [1-6]: 3

[Shows detailed agent management help]
```

## Performance Considerations

### 1. Command Response Time
- Instant (<100ms) for simple operations
- Progress bars for operations >1s
- Async operations for long tasks

### 2. Output Optimization
- Pagination for large lists
- Streaming output for real-time updates
- Lazy loading for detailed views

### 3. Caching
- Command completion cache
- Configuration cache
- Agent registry cache

## Accessibility

### 1. Screen Reader Support
- Semantic output structure
- Alternative text for icons
- Keyboard navigation

### 2. Color Blind Mode
```bash
myai --no-color          # Disable all colors
myai --color-scheme cb   # Color-blind friendly
```

### 3. Simplified Output
```bash
myai --plain            # Plain text output
myai --quiet            # Minimal output
myai --verbose          # Detailed output
```

## Future Enhancements

### 1. Plugin System
- Custom commands
- Output formatters
- Integration extensions

### 2. Interactive Mode
```bash
myai interactive
MyAI> agent list
MyAI> config show
MyAI> exit
```

### 3. Web UI
- Local web interface
- Remote management
- Visual configuration editor
