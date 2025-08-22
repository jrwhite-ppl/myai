# MyAI Integration Status - UPDATED

## Important: Python Command Execution
**ALWAYS use `uv run` for Python commands** - e.g., `uv run python -m myai ...`

## Claude SDK Integration 🚀
**New**: MyAI now integrates with Claude Code SDK for enhanced agent creation and testing!

### Agent Creation with Claude SDK
```bash
# Create agent with Claude SDK refinement (default)
myai agent create my-expert --interactive

# Create without SDK
myai agent create my-expert --no-claude-sdk
```

When creating an agent, MyAI will:
1. Create the basic agent structure
2. Launch Claude SDK for interactive refinement
3. Help you perfect your agent with Claude's assistance

### Testing Agents with Claude SDK
```bash
# Test an agent with a specific prompt
myai agent test my-expert "Analyze this Python code for security issues"

# Test without SDK (not yet implemented)
myai agent test my-expert "Test prompt" --no-claude-sdk
```

### SDK Requirements
- Node.js 18+
- Claude CLI: `npm install -g @anthropic-ai/claude-code`
- Claude SDK for Python: `pip install claude-code-sdk` (automatically installed with MyAI)

## Comprehensive Install Command
**New**: `myai install all` now provides complete setup:
1. Sets up global `~/.myai` directory with all default agents
2. Creates and configures `~/.claude` directory with agents
3. Creates project-level `.claude` directory with configuration
4. Creates project-level `.cursor` directory with agent rules
5. Syncs all agents to both Claude and Cursor

## Claude Integration
**Path**: `~/.claude/agents/`
- Global agent files stored as `.md` files in SDK-compatible format
- Project configuration in `.claude/settings.local.json`
- Project config references global agents via `agentsPath`
- All 23 default agents available in Claude Code
- Agents synced with proper Claude SDK formatting

## Cursor Integration - Project-Level Only
**Path**: `.cursor/` (in each project)
- Project-level `.cursorrules` files
- No global rules support (by design)
- Each project maintains its own agent rules
- Run from within project directory

## Custom Agent Import
**New**: Import and manage custom agents created in Claude or Cursor:
- `myai system integration-import -i claude` - Import custom agents from `~/.claude/agents/`
- Custom agents are marked with source indicator: `my-agent (claude)`
- Original files are preserved (not moved or modified)
- Custom agents persist across MyAI updates and are preserved during uninstall
- Metadata stored in `~/.myai/config/custom_agents.json`
- Fully manageable through MyAI (enable/disable/list/show)

## MyAI Commands
- `myai install all` - Complete installation (global + project)
- `myai agent list` - List all available agents (custom agents show with source indicator)
- `myai system integration-health` - Check integration status
- `myai system integration-import -i claude` - Import custom agents from Claude
- `myai system integration-list` - List available integrations
- `myai uninstall` - Uninstall MyAI (preserves custom agents)

## Agent-OS Integration
**New**: MyAI now includes full Agent-OS integration for structured AI-driven development:
- `myai agentos install --claude-code` - Install Agent-OS with Claude Code agents
- `myai agentos install --project` - Install Agent-OS in current project
- `myai agentos commands` - List available Agent-OS workflow commands
- `myai agentos run <command>` - Run Agent-OS workflows
- `myai agentos status` - Check Agent-OS installation status

Agent-OS provides structured workflows for:
- **analyze-product** - Analyze existing codebase and install Agent-OS
- **plan-product** - Plan new products with Agent-OS structure
- **create-spec** - Create detailed feature specifications
- **create-tasks** - Break down features into executable tasks
- **execute-tasks** - Execute development tasks following standards

## What Gets Created
After running `myai install all`:
```
~/.myai/
├── agents/           # Default agents copied here
├── config/          # Configuration files
└── agent-os/        # Agent-OS base installation (if installed)
    ├── instructions/  # Workflow instructions
    ├── standards/    # Coding standards
    └── commands/     # Command templates

~/.claude/
└── agents/          # Claude agent files (23+ .md files)

./                   # Current project directory
├── .claude/
│   └── settings.local.json  # Project config
├── .cursor/
│   └── *.cursorrules  # Project agent rules (23 files)
└── .agent-os/       # Project Agent-OS (if installed)
    ├── product/     # Product documentation
    ├── specs/       # Feature specifications
    └── recaps/      # Task completion records
```

## Testing
- `make dev` - Install development dependencies
- `make pre-ci` - Run all tests and linting (must pass with zero errors)
