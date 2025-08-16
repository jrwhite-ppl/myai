# MyAgents - Unified AI Configuration System

A comprehensive multi-agent AI system that unifies specialized teams, hooks, and workflows for AI development tools like Claude Code and Cursor.

## 🎯 Overview

MyAgents provides a hierarchical configuration system that brings together:
- **22 Specialized Agents** across 6 teams (Engineering, Marketing, Legal, Security, Finance, Leadership)
- **Claude Code Hooks** for deterministic control and security
- **Agent-OS Workflows** for proven development methodologies
- **Voice Integration** with Whisper and TTS
- **Cross-Tool Compatibility** (Claude Code, Cursor, and more)

## 🏗️ Architecture

```
~/.myagents/                    # Global configurations
├── agents/                     # Global agent definitions
├── hooks/                      # Global hook scripts
├── workflows/                  # Global workflows
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
```

## 🚀 Quick Start

### 1. Voice Commands
```bash
# Engineering Team
"Hey Engineering Leader, design our microservices architecture"
"Hey Data, analyze our customer retention metrics"
"Hey DevOps, optimize our deployment pipeline"

# Marketing Team  
"Hey Marketing Leader, optimize our customer lifecycle"
"Hey Success, improve our onboarding process"
"Hey Support, resolve this customer issue"

# Legal Team
"Hey Legal, review this software license"
"Hey Contracts, draft an NDA"

# Security Team
"Hey Security, analyze this AWS configuration"
"Hey Analyst, investigate this security alert"

# Finance Team
"Hey CFO, analyze our funding runway"
"Hey Finance, optimize our R&D tax credits"

# Leadership
"Hey Leader, coordinate this cross-team initiative"
```

### 2. Agent Invocation
Each agent responds with authentic professional expertise using the RAW output protocol:

```
=== BEGIN ENGINEERING TEAM LEADER RESPONSE ===
[Complete response as the Engineering Leader - NO modifications]
=== END ENGINEERING TEAM LEADER RESPONSE ===
```

## 🎭 Agent Teams

### Engineering Team (7 agents)
- **Engineering Team Leader** - Technical organization leadership
- **Systems Architect** - Architecture and design
- **Lead Developer** - Software development leadership  
- **DevOps Engineer** - Infrastructure and deployment
- **Data Analyst** - Business intelligence and analytics
- **BI Developer** - Dashboard development
- **QA Engineer** - Quality assurance and testing

### Marketing & Customer Success Team (5 agents)
- **Marketing Team Leader** - Customer-facing organization leadership
- **Brand Strategist** - Brand strategy and positioning
- **Content Creator** - Content creation and social media
- **Customer Success Manager** - Customer success and retention
- **Customer Support Specialist** - Support and issue resolution

### Legal Team (3 agents)
- **Legal Team Leader** - Legal team coordination
- **Senior Legal Advisor** - Strategic legal guidance
- **Contract Specialist** - Contract drafting and review

### Security Team (3 agents)
- **Security Team Leader** - Security team coordination
- **Chief Security Officer** - Security strategy and compliance
- **Security Analyst** - Security analysis and threat hunting

### Finance Team (3 agents)
- **Finance Team Leader** - Finance team coordination
- **Chief Financial Officer** - Financial strategy and planning
- **Finance Specialist** - Tax planning and grant management

### Leadership Team (1 agent)
- **A-Player Department Leader** - Cross-team coordination and strategic operations

## 🔧 Configuration

### Project Configuration
```json
{
  "version": "1.0.0",
  "teams": {
    "active": ["engineering", "marketing"],
    "configs": ".myagents/teams/"
  },
  "voice": {
    "enabled": true,
    "trigger_prefix": "Hey",
    "tts_provider": "elevenlabs"
  },
  "integrations": {
    "claude_code": {
      "enabled": true,
      "settings_path": ".claude/settings.json"
    },
    "cursor": {
      "enabled": true,
      "rules_path": ".cursorrules"
    }
  }
}
```

### Team Configuration
Each team has its own configuration with:
- Agent definitions
- Workflow mappings
- Hook configurations
- Voice triggers
- Standards references

## 🔗 Integrations

### Claude Code Integration
- Hooks automatically loaded from `.myagents/hooks/`
- Agents available as sub-agents via `.claude/agents/`
- Settings generated from `.myagents/config.json`

### Cursor Integration
- `.cursorrules` generated from active configurations
- Team-specific prompts and contexts
- Automatic workflow integration

### Agent-OS Integration
- Workflows referenced from `~/.agent-os/`
- Specifications created in `.agent-os/specs/`
- Standards enforced via hooks

## 🎤 Voice Integration

### Setup
1. **Whisper** for speech-to-text
2. **TTS Provider** (ElevenLabs, OpenAI, pyttsx3)
3. **Voice Triggers** - "Hey [Agent]" or "Consult [Role]"

### Usage
```bash
# Speak to Whisper: "Hey Engineering Leader, design our API"
# Paste transcribed text into Claude Code
# Receive authentic agent response
# Optional: Use TTS to hear response
```

## 🔒 Security & Hooks

### Hook Lifecycle
- **UserPromptSubmit** - Prompt validation and context injection
- **PreToolUse** - Security validation and command blocking
- **PostToolUse** - Result validation and logging
- **SessionStart** - Context loading and initialization
- **Stop** - Completion validation and cleanup
- **SubagentStop** - Sub-agent completion handling
- **Notification** - User alerts and TTS
- **PreCompact** - Transcript backup and preservation

### Security Features
- Dangerous command blocking (`rm -rf`, system access)
- Sensitive file access prevention
- Audit logging of all interactions
- Permission-based tool access control

## 📋 Workflows

### Engineering Workflows
- Architecture review and design
- Code review and quality assurance
- Deployment and infrastructure
- Data analysis and business intelligence

### Marketing Workflows
- Brand strategy development
- Content creation and campaigns
- Customer onboarding and success
- Support escalation and resolution

### Legal Workflows
- Contract review and drafting
- Compliance assessment
- Risk analysis and mitigation

### Security Workflows
- Security assessment and governance
- Incident response and analysis
- Threat hunting and monitoring

### Finance Workflows
- Financial planning and analysis
- Fundraising and investor relations
- Tax planning and optimization
- Grant management and compliance

### Leadership Workflows
- Strategic planning and coordination
- Cross-team collaboration
- Escalation management
- Knowledge sharing and best practices

## 🛠️ Development

### Adding New Agents
1. Create agent profile in `.myagents/agents/`
2. Add to team configuration in `.myagents/teams/[team]/config.json`
3. Define voice triggers and workflows
4. Update main configuration if needed

### Adding New Hooks
1. Create hook script in `.myagents/hooks/`
2. Configure in `.myagents/config.json`
3. Test with Claude Code session
4. Add to team-specific configurations if needed

### Adding New Teams
1. Create team directory in `.myagents/teams/`
2. Define team configuration with agents and workflows
3. Add to available teams in main configuration
4. Update documentation and examples

## 📚 Documentation

- [AI Configuration Architecture](AI_CONFIGURATION_ARCHITECTURE.md) - Detailed system design
- [Agent Profiles](.myagents/agents/) - Individual agent specifications
- [Team Configurations](.myagents/teams/) - Team-specific settings
- [Workflows](agent_os/workflows/) - Process definitions
- [CLAUDE.md](CLAUDE.md) - Master instructions for Claude

## 🎯 Benefits

1. **Unified Configuration** - Single source of truth for all AI tools
2. **Team Collaboration** - Shared configurations per team
3. **Hierarchical Control** - Override at any level
4. **Tool Agnostic** - Works with Claude, Cursor, and more
5. **Voice First** - Natural language interaction
6. **Secure by Default** - Built-in validation and blocking
7. **Workflow Driven** - Follows best practices automatically
8. **Authentic Responses** - RAW output protocol preserves agent voices

## 🚀 Getting Started

1. **Clone this repository**
2. **Install dependencies**: `pip install uv`
3. **Configure voice**: Set up Whisper and TTS providers
4. **Activate teams**: Modify `.myagents/config.json`
5. **Test with Claude Code**: Start a session and try voice commands
6. **Customize**: Add your own agents, hooks, and workflows

## 🤝 Contributing

This system is designed to be extensible. Contributions welcome for:
- New agent profiles
- Additional hook scripts
- Team configurations
- Workflow definitions
- Documentation improvements

## 📄 License

This project provides a framework for AI development teams. Use responsibly and in accordance with your organization's policies.
