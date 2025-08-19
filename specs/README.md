# MyAI Specifications

This directory contains the complete specifications for the MyAI CLI tool. These documents define the architecture, features, and implementation details for building a unified AI configuration management system.

## Specification Documents

### Core Specifications

1. **[overview.md](overview.md)** - Project vision, objectives, and principles
   - Vision and core objectives
   - Key features overview
   - User experience principles
   - Target audience

2. **[architecture.md](architecture.md)** - System architecture and technical design
   - Layered architecture pattern
   - Core components and their responsibilities
   - Directory structures
   - Design patterns and extension points

3. **[configuration-management.md](configuration-management.md)** - Hierarchical configuration system
   - Four-level hierarchy (Enterprise → User → Team → Project)
   - Merge strategies and conflict resolution
   - Tool-specific mappings
   - Advanced features (env vars, conditionals)

4. **[agent-management.md](agent-management.md)** - AI agent lifecycle and operations
   - Agent specification format
   - CRUD operations
   - Agent categories and organization
   - Tool integration transformations

5. **[cli-interface.md](cli-interface.md)** - Command-line interface design
   - Command structure and hierarchy
   - Interactive features and wizards
   - Output formatting with Rich
   - Error handling and help system

### Integration and Deployment

6. **[tool-integrations.md](tool-integrations.md)** - Claude Code and Cursor integration
   - Base adapter pattern
   - Tool-specific implementations
   - Sync strategies
   - Future tool support

7. **[agent-os-integration.md](agent-os-integration.md)** - Agent-OS dependency management
   - Integration philosophy (invisible to users)
   - Path and content transformation
   - Update management
   - Build process integration

8. **[installation-setup.md](installation-setup.md)** - Installation and setup process
   - Multiple installation methods
   - Post-installation configuration
   - Platform-specific considerations
   - Enterprise deployment

### Additional Specifications

9. **[security.md](security.md)** - Security measures and best practices
   - File system permissions
   - Sensitive data protection
   - Input validation
   - Audit logging

10. **[user-guide.md](user-guide.md)** - End-user documentation
    - Quick start guide
    - Common workflows
    - Troubleshooting
    - Best practices

## Implementation Status (As of 2025-08-19)

### ✅ Completed Phases
- **Phase 1-7**: All core functionality implemented
- **Claude Integration**: Working with `~/.claude` path
- **Cursor Integration**: Project-level only (`.cursor/rules/` directory with .mdc files)
- **Default Agents**: 23 rich agents in various categories
- **Setup Commands**:
  - `myai setup all-setup`: Comprehensive setup with Agent-OS integration
  - `myai setup uninstall`: Surgical removal that preserves user files
- **Testing**: 768 tests passing with `make pre-ci`

### 🚧 Remaining Phases
- **Phase 8**: Testing and Quality Assurance
- **Phase 9**: Documentation and Polish
- **Phase 10**: Additional Core Features
- **Phase 11**: Advanced System Features
- **Phase 12**: Release Preparation
- **Phase 13**: Migration and Rollback Systems
- **Phase 14**: Community and Extension Features
- **Phase 15**: Performance and Monitoring

## Key Design Decisions

1. **Typer + Rich**: Modern CLI framework with beautiful output
2. **Hierarchical Configuration**: Flexible system supporting multiple contexts
3. **Agent-OS Integration**: Hidden dependency providing proven patterns
4. **Extensible Architecture**: Plugin system for future tools
5. **Security First**: Secure defaults and practices throughout

## Directory Structure

The implementation will follow this structure:

```
myai/
├── src/
│   └── myai/
│       ├── __init__.py
│       ├── cli/             # CLI commands
│       ├── config/          # Configuration management
│       ├── agents/          # Agent management
│       ├── integrations/    # Tool adapters
│       ├── agent_os/        # Agent-OS integration
│       └── data/            # Default agents and configs
├── tests/
├── docs/
└── scripts/
```

## Next Steps

1. Set up the basic project structure
2. Implement core CLI framework
3. Build configuration management
4. Add agent discovery and management
5. Implement tool integrations
6. Add interactive features
7. Comprehensive testing
8. Documentation and release

These specifications provide a complete blueprint for building MyAI. Each document contains detailed implementation guidance while maintaining flexibility for adjustments during development.
