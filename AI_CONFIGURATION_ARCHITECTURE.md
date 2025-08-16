# AI Configuration Architecture

## Overview
This system unifies multi-agent teams, hooks, and workflows into a hierarchical configuration system for AI development tools.

## Configuration Hierarchy

```
~/.myagents/                    # Global configurations
├── agents/                     # Global agent definitions
├── hooks/                      # Global hook scripts
├── workflows/                  # Global workflows (agent-os)
└── config.json                 # Global settings

/project/.myagents/             # Project configurations  
├── agents/                     # Project-specific agents
├── hooks/                      # Project-specific hooks
├── teams/                      # Team configurations
│   ├── engineering/
│   ├── marketing/
│   ├── legal/
│   ├── security/
│   ├── finance/
│   └── leadership/
└── config.json                 # Project settings

/project/src/.myagents/         # Directory configurations
└── config.json                 # Directory-specific overrides
```

## Configuration Priority (highest to lowest)
1. Directory-level (.myagents in current directory)
2. Project-level (.myagents in project root)
3. Team-level (inherited from team membership)
4. Global-level (~/.myagents)

## Integration Points

### 1. Claude Code Integration
- Symlink to `.claude/` for compatibility
- Hooks automatically loaded from `.myagents/hooks/`
- Agents available as sub-agents via `.claude/agents/`

### 2. Cursor Integration
- `.cursorrules` generated from active configurations
- Team-specific prompts and contexts
- Automatic workflow integration

### 3. Agent-OS Integration
- Workflows referenced from `~/.agent-os/`
- Specifications created in `.agent-os/specs/`
- Standards enforced via hooks

## Configuration Schema

```json
{
  "version": "1.0.0",
  "extends": ["global", "team:engineering"],
  "agents": {
    "enabled": ["*"],
    "disabled": [],
    "overrides": {}
  },
  "hooks": {
    "UserPromptSubmit": [],
    "PreToolUse": [],
    "PostToolUse": [],
    "SessionStart": []
  },
  "workflows": {
    "default": "agent-os",
    "custom": []
  },
  "teams": {
    "active": ["engineering", "security"],
    "leadership": "engineering-leader"
  },
  "voice": {
    "enabled": true,
    "trigger_prefix": "Hey",
    "tts_provider": "elevenlabs"
  }
}
```

## Key Features

### 1. Multi-Agent Teams
- 22 specialized agents across 6 teams
- RAW output protocol for authentic responses
- Voice-triggered interactions
- Cross-team collaboration

### 2. Hook System
- 8 lifecycle events with full control
- Security validation and blocking
- Context injection and enhancement
- Automatic logging and auditing

### 3. Workflow Integration
- Agent-OS specifications and standards
- Team-specific workflows
- Automated task execution
- Quality checkpoints

### 4. Voice Integration
- Whisper for speech-to-text
- Multiple TTS providers
- Natural command patterns
- Agent-specific triggers

## Usage Examples

### Team Activation
```bash
# Activate engineering team configuration
myagents team activate engineering

# This enables:
# - Engineering agents (Lead Dev, DevOps, Data Analyst, etc.)
# - Engineering workflows and standards
# - Technical hooks (code review, testing, etc.)
```

### Agent Invocation
```bash
# Voice command
"Hey Engineering Leader, design our microservices architecture"

# Direct command
myagents agent invoke engineering-leader "design microservices"

# With workflow
myagents agent invoke --workflow=create-spec systems-architect
```

### Hook Management
```bash
# Enable security hooks
myagents hooks enable security

# Add custom hook
myagents hooks add pre-commit ./hooks/lint-check.py

# View active hooks
myagents hooks list
```

## File Structure

```
myagents/
├── .myagents/                  # Project configuration
│   ├── agents/                 # All agent definitions
│   ├── hooks/                  # Hook scripts
│   ├── teams/                  # Team configurations
│   ├── workflows/              # Custom workflows
│   └── config.json            # Main configuration
├── .claude/                    # Claude Code compatibility
│   ├── agents/ → ../.myagents/agents/
│   ├── hooks/ → ../.myagents/hooks/
│   └── settings.json          # Generated from config
├── .cursorrules               # Generated Cursor rules
├── .agent-os/                 # Agent-OS integration
│   ├── product/
│   ├── specs/
│   └── context/
└── agent-os-global/ → ~/.agent-os/
```

## Migration Path

### From MyAgents
1. Agents preserved in `.myagents/agents/`
2. Team structure maintained in `.myagents/teams/`
3. RAW output protocol integrated into hooks

### From Claude-Code-Hooks-Mastery
1. Hooks migrated to `.myagents/hooks/`
2. Settings converted to unified config.json
3. Sub-agents integrated with team agents

### From Agent-OS
1. Workflows linked via symlink
2. Standards enforced through hooks
3. Specifications integrated into agent prompts

## Benefits

1. **Unified Configuration** - Single source of truth for all AI tools
2. **Team Collaboration** - Shared configurations per team
3. **Hierarchical Control** - Override at any level
4. **Tool Agnostic** - Works with Claude, Cursor, and more
5. **Voice First** - Natural language interaction
6. **Secure by Default** - Built-in validation and blocking
7. **Workflow Driven** - Follows best practices automatically
