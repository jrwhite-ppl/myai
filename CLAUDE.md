# MyAI Integration Status - UPDATED

## Comprehensive Setup Command
**New**: `myai setup all-setup` now provides complete setup:
1. Sets up global `~/.myai` directory with all default agents
2. Creates and configures `~/.claude` directory with agents
3. Creates project-level `.claude` directory with configuration
4. Creates project-level `.cursor` directory with agent rules
5. Syncs all agents to both Claude and Cursor

## Claude Integration
**Path**: `~/.claude/agents/`
- Global agent files stored as `.md` files
- Project configuration in `.claude/settings.local.json`
- Project config references global agents via `agentsPath`
- All 23 default agents available in Claude Code

## Cursor Integration - Project-Level Only
**Path**: `.cursor/` (in each project)
- Project-level `.cursorrules` files
- No global rules support (by design)
- Each project maintains its own agent rules
- Run from within project directory

## MyAI Commands
- `myai setup all-setup` - Complete setup (global + project)
- `myai agent list` - List all available agents
- `myai integration sync` - Sync agents to integrations
- `myai integration health` - Check integration status

## What Gets Created
After running `myai setup all-setup`:
```
~/.myai/
├── agents/           # Default agents copied here
└── config/          # Configuration files

~/.claude/
└── agents/          # Claude agent files (23 .md files)

./                   # Current project directory
├── .claude/
│   └── settings.local.json  # Project config
└── .cursor/
    └── *.cursorrules  # Project agent rules (23 files)
```

## Testing
- `make dev` - Install development dependencies
- `make pre-ci` - Run all tests and linting (must pass with zero errors)
