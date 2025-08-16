# MyAgents Tech Stack

## Core Technologies

### AI/LLM Layer
- **Claude**: Primary AI engine (Opus/Sonnet models)
- **Claude Code**: Development environment and execution platform
- **Whisper**: Speech-to-text for voice commands
- **TTS**: Text-to-speech for voice responses (user-selected)

### Architecture
- **Multi-Agent System**: 22 specialized agents
- **RAW Output Protocol**: Unmodified agent responses
- **Markdown-based Configuration**: All agent profiles and workflows in .md files

### Integration
- **Agent-OS**: Workflow management and specification system
- **Voice Pipeline**: Whisper → Text → Claude → Agent → Response → TTS

## Development Standards
- Follow agent-os specifications at ~/.agent-os
- Maintain RAW output protocol for all agents
- Use markdown for all configuration and documentation
- Implement cross-team collaboration protocols

## File Structure
```
myagents/
├── agents/              # Agent personality profiles
├── agent_os/            # Local workflows and standards
├── agent-os-global/     # Link to ~/.agent-os
├── .agent-os/           # Product-specific configurations
├── team_dynamics/       # Cross-team protocols
└── CLAUDE.md           # Master instructions
```

## Voice Command Pattern
```
"Hey [Agent]" or "Consult [Role]"
→ Whisper transcription
→ Claude processes with agent profile
→ Agent responds using RAW protocol
→ Optional TTS output
```
