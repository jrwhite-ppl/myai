# Installation and Setup Specification

## Overview

This specification defines the installation process, setup workflows, and system requirements for MyAI. The installation should be simple, reliable, and provide multiple installation methods to accommodate different user preferences and system configurations.

## System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **Operating Systems**: 
  - macOS 11.0+ (Big Sur)
  - Ubuntu 20.04+
  - Windows 10+ (with WSL2 recommended)
- **Memory**: 512MB RAM
- **Storage**: 100MB for application + space for configurations
- **Network**: Internet connection for tool syncing and updates

### Dependencies
- **Required Python Packages**:
  - `typer>=0.9.0` - CLI framework
  - `rich>=13.0.0` - Terminal formatting
  - `pydantic>=2.0.0` - Data validation
  - `httpx>=0.25.0` - HTTP client
  - `watchdog>=3.0.0` - File system monitoring
  - `gitpython>=3.1.0` - Git integration
  - `pyyaml>=6.0` - YAML support
  - `toml>=0.10.0` - TOML support

## Installation Methods

### 1. PyPI Installation (Recommended)
```bash
# Install from PyPI
pip install myai-cli

# Or with pipx for isolation
pipx install myai-cli

# Or with uv for speed
uv tool install myai-cli

# Verify installation
myai --version
```

### 2. Homebrew Installation (macOS/Linux)
```bash
# Add tap
brew tap myai/tools

# Install
brew install myai

# Verify
myai --version
```

### 3. Installation Script
```bash
# One-line installer
curl -sSL https://install.myai.dev | bash

# Or with wget
wget -qO- https://install.myai.dev | bash

# Options
curl -sSL https://install.myai.dev | bash -s -- --version=latest --no-agents
```

### 4. Development Installation
```bash
# Clone repository
git clone https://github.com/myai/myai-cli.git
cd myai-cli

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .

# Install dev dependencies
uv pip install -e ".[dev]"
```

### 5. Docker Installation
```bash
# Pull image
docker pull myai/cli:latest

# Run with volume mount
docker run -v ~/.myai:/root/.myai myai/cli:latest --help

# Alias for convenience
alias myai='docker run -v ~/.myai:/root/.myai -v $(pwd):/workspace myai/cli:latest'
```

## Installation Script Details

### Script Behavior
```bash
#!/bin/bash
# install.sh - MyAI installer script

set -euo pipefail

# Configuration
MYAI_VERSION="${MYAI_VERSION:-latest}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
CONFIG_DIR="${HOME}/.myai"
SKIP_AGENTS="${SKIP_AGENTS:-false}"
IMPORT_EXISTING="${IMPORT_EXISTING:-true}"

# Functions
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*)  echo "linux" ;;
        MINGW*|CYGWIN*|MSYS*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}

detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64) echo "amd64" ;;
        arm64|aarch64) echo "arm64" ;;
        *) echo "unknown" ;;
    esac
}

check_prerequisites() {
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3.8+ is required"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        echo "❌ pip is required"
        exit 1
    fi
}

install_myai() {
    echo "🚀 Installing MyAI..."
    
    # Create virtual environment
    python3 -m venv "${CONFIG_DIR}/venv"
    source "${CONFIG_DIR}/venv/bin/activate"
    
    # Install package
    pip install --upgrade pip
    pip install myai-cli=="${MYAI_VERSION}"
    
    # Create symlink
    ln -sf "${CONFIG_DIR}/venv/bin/myai" "${INSTALL_DIR}/myai"
    
    echo "✅ MyAI installed successfully"
}

setup_configuration() {
    echo "📁 Setting up configuration..."
    
    # Create directory structure
    mkdir -p "${CONFIG_DIR}"/{config,agents,backups,logs,cache}
    mkdir -p "${CONFIG_DIR}"/agents/{default,custom}
    
    # Initialize configuration
    myai init --quiet
    
    # Import existing configurations
    if [[ "${IMPORT_EXISTING}" == "true" ]]; then
        myai migrate detect --quiet || true
    fi
    
    echo "✅ Configuration setup complete"
}

install_default_agents() {
    if [[ "${SKIP_AGENTS}" == "true" ]]; then
        return
    fi
    
    echo "🤖 Installing default agents..."
    
    # Download agent pack
    curl -sSL https://agents.myai.dev/default-pack.tar.gz | \
        tar -xz -C "${CONFIG_DIR}/agents/default"
    
    echo "✅ Default agents installed"
}

setup_shell_completion() {
    echo "🐚 Setting up shell completion..."
    
    # Detect shell
    if [[ -n "${BASH_VERSION}" ]]; then
        myai --install-completion bash
    elif [[ -n "${ZSH_VERSION}" ]]; then
        myai --install-completion zsh
    fi
    
    echo "✅ Shell completion configured"
}

# Main installation flow
main() {
    echo "MyAI CLI Installer"
    echo "=================="
    
    check_prerequisites
    install_myai
    setup_configuration
    install_default_agents
    setup_shell_completion
    
    echo ""
    echo "🎉 Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'myai doctor' to verify installation"
    echo "  2. Run 'myai init --mode guided' for interactive setup"
    echo "  3. Run 'myai agent list' to see available agents"
    echo ""
    echo "Documentation: https://docs.myai.dev"
}

main "$@"
```

## Post-Installation Setup

### 1. Initial Configuration
```bash
# Quick setup (non-interactive)
myai init

# Guided setup (recommended for first time)
myai init --mode guided

# Enterprise setup
myai init --mode enterprise --config-url https://company.com/myai-config
```

### 2. Tool Integration Setup
```bash
# Auto-detect and configure tools
myai sync detect

# Manual tool setup
myai sync claude --setup
myai sync cursor --setup
```

### 3. Verification
```bash
# Run diagnostic
myai doctor

# Expected output:
✅ MyAI CLI v1.0.0
✅ Configuration directory exists
✅ Default agents installed (15 agents)
✅ Claude Code integration ready
✅ Cursor integration ready
✅ No issues found

# Check status
myai status
```

## Directory Structure Creation

### Initial Directory Layout
```
~/.myai/
├── config/
│   ├── global.json          # Created with defaults
│   ├── teams/               # Empty, ready for team configs
│   └── enterprise/          # Empty, ready for enterprise configs
├── agents/
│   ├── default/             # Populated with default agents
│   │   ├── engineering/
│   │   ├── product/
│   │   ├── business/
│   │   └── specialized/
│   └── custom/              # Empty, for user agents
├── templates/               # Agent templates
├── backups/                 # Empty, for backups
├── cache/                   # Empty cache directory
├── logs/                    # Log files
│   └── install.log         # Installation log
└── .version                # Version tracking file
```

### Default Configuration
```json
{
  "version": "1.0.0",
  "metadata": {
    "created": "2025-01-16T10:00:00Z",
    "modified": "2025-01-16T10:00:00Z",
    "source": "user"
  },
  "settings": {
    "merge_strategy": "merge",
    "auto_sync": true,
    "backup_enabled": true,
    "backup_count": 5,
    "check_updates": true
  },
  "tools": {
    "claude": {
      "enabled": true,
      "auto_detect_path": true
    },
    "cursor": {
      "enabled": true,
      "auto_detect_path": true
    }
  },
  "agents": {
    "enabled": ["lead_developer", "devops_engineer"],
    "auto_discover": true
  }
}
```

## Upgrade Process

### 1. Standard Upgrade
```bash
# Using pip
pip install --upgrade myai-cli

# Using homebrew
brew upgrade myai

# Using installer script
curl -sSL https://install.myai.dev | bash -s -- --upgrade
```

### 2. Version Management
```bash
# Check current version
myai --version

# Check for updates
myai upgrade check

# Upgrade to specific version
myai upgrade --version 1.2.0

# Upgrade with backup
myai upgrade --backup
```

### 3. Migration Between Versions
```bash
# Automatic migration
myai upgrade --migrate

# Manual migration
myai migrate version --from 1.0.0 --to 1.1.0
```

## Uninstallation

### Complete Uninstall
```bash
# Uninstall script
curl -sSL https://install.myai.dev/uninstall | bash

# Or manual uninstall
myai uninstall --complete

# This will:
# 1. Backup configurations to ~/myai-backup-{timestamp}
# 2. Remove ~/.myai directory
# 3. Remove tool integrations
# 4. Uninstall package
```

### Partial Uninstall
```bash
# Remove package but keep configs
pip uninstall myai-cli

# Remove specific components
myai uninstall --components agents,cache
```

## Platform-Specific Considerations

### macOS
- Default install location: `/usr/local/bin/myai`
- Config location: `~/.myai`
- Gatekeeper handling for downloaded binaries
- Keychain integration for secure storage

### Linux
- Default install location: `/usr/local/bin/myai`
- Config location: `~/.myai`
- Systemd service for background sync (optional)
- XDG Base Directory support

### Windows
- Default install location: `%LOCALAPPDATA%\MyAI\myai.exe`
- Config location: `%USERPROFILE%\.myai`
- WSL2 recommended for full compatibility
- PowerShell completion support

## Enterprise Deployment

### 1. Centralized Configuration
```bash
# Deploy with enterprise config
MYAI_ENTERPRISE_URL=https://corp.com/myai/config.json myai init --mode enterprise

# Lock certain settings
{
  "locked_settings": [
    "tools.*.api_endpoint",
    "security.*"
  ]
}
```

### 2. Mass Deployment Script
```bash
#!/bin/bash
# enterprise-deploy.sh

# Configuration server
CONFIG_SERVER="https://internal.corp.com/myai"

# Install MyAI
curl -sSL https://install.myai.dev | bash

# Configure for enterprise
myai init --mode enterprise \
  --config-url "${CONFIG_SERVER}/config.json" \
  --agents-url "${CONFIG_SERVER}/agents.tar.gz" \
  --no-user-agents
```

### 3. Policy Enforcement
```json
{
  "enterprise_policy": {
    "required_agents": ["security_reviewer", "compliance_checker"],
    "forbidden_tools": ["experimental_tool"],
    "audit_logging": true,
    "telemetry_endpoint": "https://metrics.corp.com/myai"
  }
}
```

## Troubleshooting Installation

### Common Issues

#### 1. Permission Denied
```bash
# Error: Permission denied writing to /usr/local/bin

# Solution 1: Use user directory
INSTALL_DIR=~/.local/bin ./install.sh

# Solution 2: Use sudo (not recommended)
sudo ./install.sh
```

#### 2. Python Version Issues
```bash
# Error: Python 3.7 detected, 3.8+ required

# Solution: Use pyenv or update Python
pyenv install 3.11
pyenv global 3.11
```

#### 3. Conflicting Installations
```bash
# Error: Another version of myai detected

# Solution: Clean install
myai uninstall --complete
curl -sSL https://install.myai.dev | bash
```

### Diagnostic Commands
```bash
# Full system diagnostic
myai doctor --verbose

# Installation verification
myai doctor install

# Configuration check
myai doctor config

# Tool integration check
myai doctor integrations
```

## Security Considerations

### 1. Installation Verification
- GPG signature verification for releases
- SHA256 checksum validation
- HTTPS-only downloads

### 2. Permissions
- Minimal required permissions
- No sudo required for user install
- Secure file permissions (600/700)

### 3. Network Security
- Certificate pinning for updates
- Proxy support with authentication
- Offline installation option