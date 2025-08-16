# MyAI User Guide

## Welcome to MyAI

MyAI is your unified command-line tool for managing AI assistant configurations across multiple development tools. Think of it as your personal AI configuration hub that keeps Claude Code, Cursor, and other AI tools in perfect sync.

## Quick Start

### Installation

The fastest way to get started:

```bash
# Install via pip
pip install myai-cli

# Or use pipx for isolation
pipx install myai-cli

# Verify installation
myai --version
```

### First Time Setup

After installation, run the guided setup:

```bash
myai init --mode guided
```

This interactive wizard will:
1. Set up your configuration directory
2. Detect installed AI tools (Claude Code, Cursor, etc.)
3. Install recommended AI agents
4. Configure tool integrations

## Core Concepts

### 1. Configurations

MyAI uses a hierarchical configuration system. Think of it like CSS - more specific settings override general ones:

- **Project** (`.myai/config.json`) - Highest priority, project-specific
- **Team** (`~/.myai/config/teams/`) - Shared team settings
- **User** (`~/.myai/config/global.json`) - Your personal preferences
- **Enterprise** (`~/.myai/config/enterprise/`) - Company-wide policies

### 2. Agents

Agents are specialized AI personalities with specific expertise. For example:
- **Lead Developer**: Architecture decisions and code reviews
- **DevOps Engineer**: Infrastructure and deployment guidance
- **Security Analyst**: Security reviews and best practices

### 3. Tool Integration

MyAI automatically syncs your configurations and agents with:
- **Claude Code**: Direct integration via settings and agent directories
- **Cursor**: Generates rules from your agent configurations
- **More tools**: Coming soon!

## Common Workflows

### Setting Up a New Project

```bash
# Navigate to your project
cd my-project

# Initialize MyAI for the project
myai init

# Add project-specific agents
myai agent enable python_expert backend_specialist

# Sync with your tools
myai sync all
```

### Managing Agents

```bash
# List all available agents
myai agent list

# Search for specific agents
myai agent search "python backend"

# Show agent details
myai agent show lead_developer

# Enable agents for current project
myai agent enable security_analyst qa_engineer

# Create a custom agent
myai agent create my_custom_agent --interactive
```

### Configuration Management

```bash
# View current configuration
myai config show

# Set a configuration value
myai config set tools.claude.enabled true

# View merged configuration (all levels combined)
myai config show --level merged

# Backup configuration before changes
myai config backup --name "before-experiment"

# Restore if needed
myai config restore "before-experiment"
```

### Syncing with Tools

```bash
# Sync everything to all tools
myai sync all

# Sync only to Claude Code
myai sync claude

# Preview what will be synced
myai sync all --dry-run

# Force sync (overwrite tool configs)
myai sync all --force
```

## Advanced Usage

### Environment-Specific Settings

Use environment variables for sensitive data:

```json
{
  "tools": {
    "claude": {
      "api_key": "${CLAUDE_API_KEY}"
    }
  }
}
```

### Team Collaboration

1. Create a team configuration:
```bash
myai config set --level team --name backend-team
```

2. Share the team config file with your team:
```bash
~/.myai/config/teams/backend-team.json
```

3. Team members can now use team settings:
```bash
myai config show --level team
```

### Custom Agent Creation

Create specialized agents for your workflow:

```bash
# Create interactively
myai agent create api_specialist --interactive

# Or from a template
myai agent create api_specialist --template backend_specialist

# Edit the agent
myai agent edit api_specialist
```

Agent format:
```markdown
---
name: api_specialist
display_name: API Design Specialist
category: engineering
tags: [api, rest, graphql, design]
---

# API Design Specialist

You are an expert in API design and implementation...

## Core Principles
- RESTful design patterns
- GraphQL best practices
- API versioning strategies
...
```

### Automation and Scripting

MyAI is automation-friendly:

```bash
# Non-interactive mode
export MYAI_NONINTERACTIVE=1
myai init --force

# JSON output for parsing
myai agent list --format json | jq '.agents[].name'

# Batch operations
myai agent enable api_specialist security_analyst database_expert
```

## Troubleshooting

### Diagnostic Commands

```bash
# Run full diagnostics
myai doctor

# Check specific area
myai doctor config
myai doctor integrations

# Get detailed status
myai status --verbose
```

### Common Issues

**Issue**: "Configuration not syncing to Claude Code"
```bash
# Check integration status
myai status --tools

# Re-setup Claude integration
myai sync claude --setup

# Force sync
myai sync claude --force
```

**Issue**: "Agent not appearing in tool"
```bash
# Verify agent is enabled
myai agent list --enabled

# Check agent validity
myai agent validate my_agent

# Re-sync agents
myai sync all --agents
```

**Issue**: "Permission denied errors"
```bash
# Check file permissions
myai doctor permissions

# Fix permissions
myai doctor fix --permissions
```

## Best Practices

### 1. Configuration Management
- Use environment variables for secrets
- Backup before major changes
- Use project-level configs for project-specific settings
- Keep user-level configs for personal preferences

### 2. Agent Usage
- Enable only needed agents per project
- Create custom agents for specialized domains
- Review agent recommendations for new tasks
- Keep agents updated with `myai agent update`

### 3. Team Collaboration
- Use team configurations for shared settings
- Document custom agents in your project
- Version control project-level `.myai/` directory
- Regularly sync to avoid configuration drift

### 4. Security
- Never commit secrets to configuration files
- Use `${VARIABLE}` syntax for sensitive data
- Review permissions with `myai doctor permissions`
- Enable audit logging for enterprise use

## Internationalization

MyAI supports multiple languages. Set your preferred language:

```bash
# Set language preference
myai config set ui.language es

# Available languages
myai config get ui.supported_languages
```

Supported languages:
- English (en) - Default
- Spanish (es)
- French (fr)
- German (de)
- Japanese (ja)
- Chinese Simplified (zh-CN)
- More coming soon!

## Getting Help

### Built-in Help

```bash
# General help
myai --help

# Command-specific help
myai agent --help
myai config set --help

# Interactive help
myai help
```

### Resources

- **Documentation**: https://docs.myai.dev
- **GitHub Issues**: https://github.com/myai/myai-cli/issues
- **Community Forum**: https://community.myai.dev
- **Email Support**: support@myai.dev

### Reporting Issues

When reporting issues, include:

1. MyAI version: `myai --version`
2. Diagnostic output: `myai doctor --export`
3. Steps to reproduce the issue
4. Expected vs. actual behavior

## Keyboard Shortcuts

When using interactive modes:

- **↑/↓**: Navigate options
- **Space**: Select/deselect option
- **Enter**: Confirm selection
- **Ctrl+C**: Cancel operation
- **?**: Show context help

## Updating MyAI

Stay up to date with the latest features:

```bash
# Check for updates
myai upgrade check

# Update to latest version
myai upgrade

# Update to specific version
myai upgrade --version 1.2.0
```

## Uninstalling

If you need to uninstall MyAI:

```bash
# Complete uninstall (backs up configs first)
myai uninstall --complete

# Or just remove the package
pip uninstall myai-cli
```

Your configurations are backed up to `~/myai-backup-{timestamp}/` before removal.

## FAQ

**Q: Can I use MyAI with tools other than Claude Code and Cursor?**
A: More integrations are coming soon! MyAI is designed to be extensible.

**Q: Will MyAI overwrite my existing tool configurations?**
A: By default, MyAI merges configurations. Use `--force` to overwrite.

**Q: Can I use different agents for different projects?**
A: Yes! Each project can have its own `.myai/config.json` with specific agents.

**Q: Is MyAI suitable for enterprise use?**
A: Yes! MyAI supports enterprise policies, audit logging, and centralized configuration.

**Q: How do I share configurations with my team?**
A: Use team-level configurations in `~/.myai/config/teams/` or commit project-level `.myai/` to version control.

## Next Steps

Now that you're familiar with MyAI:

1. Explore available agents: `myai agent list`
2. Customize your configuration: `myai config set --interactive`
3. Create custom agents for your workflow
4. Set up team configurations if working with others
5. Integrate MyAI into your development workflow

Happy coding with MyAI! 🚀