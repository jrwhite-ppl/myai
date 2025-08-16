# MyAI - Unified AI Configuration Management CLI

MyAI is a powerful command-line tool that centralizes and streamlines AI configuration management across multiple AI-powered development tools. It serves as a single source of truth for managing AI assistant configurations, agents, and integrations while maintaining compatibility with existing tools like Claude Code, Cursor, and future AI development assistants.

## 🚀 Key Features

- **Centralized Configuration**: Hierarchical configuration system supporting Enterprise, User, Team, and Project levels
- **AI Agent Management**: Full lifecycle management of specialized AI assistants with CRUD operations
- **Seamless Tool Integration**: Automatic synchronization with Claude Code, Cursor, and extensible to other tools
- **Smart Conflict Resolution**: Intelligent merging strategies with both incremental and complete override options
- **Beautiful CLI**: Built with Typer and Rich for an intuitive, visually appealing interface
- **Enterprise Ready**: Security-first design with audit logging, compliance features, and policy enforcement

## 📚 Documentation

The complete specifications for MyAI are available in the [`specs/`](specs/) directory. Here's a guide to help you navigate:

### Getting Started
- **Project Overview** - Vision, objectives, and principles → [`specs/overview.md`](specs/overview.md)
- **User Guide** - Quick start, common workflows, and best practices → [`specs/user-guide.md`](specs/user-guide.md)
- **Installation & Setup** - Multiple installation methods and requirements → [`specs/installation-setup.md`](specs/installation-setup.md)

### Architecture & Design
- **System Architecture** - Technical design and component structure → [`specs/architecture.md`](specs/architecture.md)
- **CLI Interface** - Command structure and user interaction design → [`specs/cli-interface.md`](specs/cli-interface.md)

### Core Features
- **Configuration Management** - Hierarchical config system with merge strategies → [`specs/configuration-management.md`](specs/configuration-management.md)
  - [Configuration Hierarchy](specs/configuration-management.md#configuration-hierarchy)
  - [Merge Strategies](specs/configuration-management.md#merge-strategies)
  - [Conflict Resolution](specs/configuration-management.md#conflict-resolution)

- **Agent Management** - AI agent lifecycle and operations → [`specs/agent-management.md`](specs/agent-management.md)
  - [Agent Structure](specs/agent-management.md#agent-structure)
  - [Agent Operations](specs/agent-management.md#agent-operations)
  - [Agent Templates](specs/agent-management.md#agent-templates)

### Integrations
- **Tool Integrations** - Claude Code and Cursor adapters → [`specs/tool-integrations.md`](specs/tool-integrations.md)
  - [Claude Code Integration](specs/tool-integrations.md#claude-code-integration)
  - [Cursor Integration](specs/tool-integrations.md#cursor-integration)
  - [Adding New Tools](specs/tool-integrations.md#future-tool-support)

- **Agent-OS Integration** - Hidden dependency management → [`specs/agent-os-integration.md`](specs/agent-os-integration.md)
  - [Integration Philosophy](specs/agent-os-integration.md#integration-philosophy)
  - [Path Translation](specs/agent-os-integration.md#path-translation)
  - [Update Management](specs/agent-os-integration.md#update-management)

### Security & Enterprise
- **Security** - Comprehensive security measures → [`specs/security.md`](specs/security.md)
  - [File System Security](specs/security.md#file-system-security)
  - [Sensitive Data Protection](specs/security.md#sensitive-data-protection)
  - [Enterprise Security](specs/security.md#enterprise-security)

## 🏗️ Architecture Overview

MyAI follows a layered architecture pattern:

```
┌─────────────────────────────────────────┐
│         CLI Interface (Typer + Rich)     │
├─────────────────────────────────────────┤
│         Configuration Manager            │
├─────────────────────────────────────────┤
│           Agent Manager                  │
├─────────────────────────────────────────┤
│        Integration Adapters              │
│   (Claude, Cursor, Future Tools)         │
├─────────────────────────────────────────┤
│          Storage Layer                   │
└─────────────────────────────────────────┘
```

For detailed architecture information, see [`specs/architecture.md`](specs/architecture.md).

## 🔧 Configuration Hierarchy

MyAI uses a powerful hierarchical configuration system:

1. **Project Level** (`.myai/config.json`) - Highest priority
2. **Team Level** (`~/.myai/config/teams/{team}.json`)
3. **User Level** (`~/.myai/config/global.json`)
4. **Enterprise Level** (`~/.myai/config/enterprise/{org}.json`)

Learn more in [`specs/configuration-management.md`](specs/configuration-management.md#configuration-hierarchy).

## 🤖 Agent System

Agents are specialized AI personalities with specific expertise:

- **Engineering**: Lead Developer, DevOps Engineer, QA Engineer
- **Business**: Data Analyst, Finance Specialist, Product Manager
- **Security**: Security Analyst, Chief Security Officer
- **And many more...**

Explore agent management in [`specs/agent-management.md`](specs/agent-management.md).

## 🛠️ Quick Start

```bash
# Install MyAI
pip install myai-cli

# Run interactive setup
myai init --mode guided

# List available agents
myai agent list

# Enable agents for your project
myai agent enable lead_developer security_analyst

# Sync with your tools
myai sync all
```

For complete setup instructions, see [`specs/installation-setup.md`](specs/installation-setup.md).

## 🔌 Tool Integration

MyAI seamlessly integrates with your favorite AI development tools:

### Claude Code
- Automatic settings synchronization
- Agent directory management
- MCP server configuration

### Cursor
- Dynamic rule generation from agents
- Project-specific configurations
- Automatic .cursorrules updates

Learn about integrations in [`specs/tool-integrations.md`](specs/tool-integrations.md).

## 🔒 Security

MyAI is built with security-first principles:

- Secure file permissions (600/700)
- Environment variable support for sensitive data
- Input validation and sanitization
- Audit logging for enterprise compliance

Read more in [`specs/security.md`](specs/security.md).

## 🌐 Internationalization

MyAI supports multiple languages:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Japanese (ja)
- Chinese Simplified (zh-CN)

See the [User Guide](specs/user-guide.md#internationalization) for language configuration.

## 📖 Complete Documentation

For comprehensive documentation, explore the [`specs/`](specs/) directory:

- [`specs/README.md`](specs/README.md) - Overview of all specifications
- Individual specification documents for deep dives into each component

## 🤝 Contributing

MyAI is designed to be extensible. Key areas for contribution:

- New tool adapters
- Additional agent templates
- Language translations
- Security enhancements

## 📄 License

[License details to be added]

## 🙏 Acknowledgments

MyAI integrates with and builds upon the excellent work of:
- [Agent-OS](https://github.com/buildermethods/agent-os) - Foundational agent patterns
- [Claude Code](https://claude.ai/code) - AI coding assistant
- [Cursor](https://cursor.sh) - AI-powered code editor

---

For detailed implementation specifications and technical documentation, please refer to the [`specs/`](specs/) directory.