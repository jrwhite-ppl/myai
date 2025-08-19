# Tool Integrations Specification

## Overview

This specification defines how MyAI integrates with various AI development tools, starting with Claude Code and Cursor. The integration system is designed to be extensible, allowing future tools to be added with minimal effort while maintaining consistency across integrations.

## Integration Architecture

### Base Integration Interface
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

class ToolAdapter(ABC):
    """Base adapter for AI tool integrations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tool_name = self.__class__.__name__.replace('Adapter', '')

    @abstractmethod
    def detect_installation(self) -> Optional[Path]:
        """Detect if tool is installed and return config path"""
        pass

    @abstractmethod
    def read_config(self) -> Dict[str, Any]:
        """Read tool's current configuration"""
        pass

    @abstractmethod
    def write_config(self, config: Dict[str, Any]) -> None:
        """Write configuration to tool"""
        pass

    @abstractmethod
    def sync_agents(self, agents: List[Agent]) -> None:
        """Sync agents to tool's format"""
        pass

    @abstractmethod
    def validate_integration(self) -> bool:
        """Validate the integration is working"""
        pass
```

## Claude Code Integration

### Configuration Mapping
```yaml
# MyAI → Claude Code mapping
myai_to_claude:
  # Settings mapping
  tools.claude.settings → ~/.claude/settings.json
  tools.claude.permissions → ~/.claude/settings.json#permissions
  tools.claude.allowed_tools → ~/.claude/settings.json#allowedTools

  # MCP Servers
  integrations.mcp_servers → ~/.claude/mcp_servers.json

  # Agents (via symlinks)
  agents.enabled → ~/.claude/agents/

  # Hooks (if configured)
  tools.claude.hooks → ~/.claude/hooks/
```

### Claude Adapter Implementation
```python
class ClaudeAdapter(ToolAdapter):
    """Claude Code integration adapter"""

    DEFAULT_PATHS = {
        'darwin': Path.home() / '.claude',
        'linux': Path.home() / '.claude',
        'win32': Path.home() / 'AppData' / 'Roaming' / 'Claude'
    }

    def detect_installation(self) -> Optional[Path]:
        """Detect Claude Code installation"""
        platform_path = self.DEFAULT_PATHS.get(sys.platform)
        if platform_path and platform_path.exists():
            return platform_path
        return None

    def sync_agents(self, agents: List[Agent]) -> None:
        """Sync agents to Claude format"""
        claude_agents_dir = self.claude_path / 'agents'

        # Clear existing symlinks
        for item in claude_agents_dir.iterdir():
            if item.is_symlink():
                item.unlink()

        # Create new symlinks
        for agent in agents:
            if agent.enabled:
                source = Path(agent.path)
                target = claude_agents_dir / f"{agent.name}.md"
                target.symlink_to(source)
```

### Claude Configuration Structure
```json
{
  "projects": {
    "/path/to/project": {
      "mcpServers": {
        "filesystem": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"]
        }
      },
      "allowedTools": [
        "Task",
        "Bash",
        "Read",
        "Edit",
        "Write"
      ]
    }
  },
  "permissions": {
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(secrets/**)"
    ]
  }
}
```

### Claude-Specific Features

#### 1. MCP Server Management
```bash
# List MCP servers
myai claude mcp list

# Add MCP server
myai claude mcp add filesystem --path /allowed/directory

# Configure MCP server
myai claude mcp config memory --args "--cache-size 1024"
```

#### 2. Permissions Management
```bash
# Add permission rule
myai claude permission add --deny "Read(*.key)"

# List permissions
myai claude permission list

# Test permission
myai claude permission test "Read(.env)"
```

#### 3. Project-Specific Settings
```bash
# Configure for current project
myai claude project setup

# Set project-specific tools
myai claude project tools --allow "Task,Read,Edit"
```

## Cursor Integration

### Important Note: Project-Level Integration Only
MyAI's Cursor integration is designed for project-level rules only. This provides better project isolation and allows different projects to have different agent configurations.

- **Project-level rules**: Stored in `.cursor/rules/` directory within each project
- **Global rules**: NOT supported - each project maintains its own agent rules
- **Rule format**: `.mdc` files (Markdown with Code) containing agent content with YAML frontmatter

### Configuration Mapping
```yaml
# MyAI → Cursor mapping
myai_to_cursor:
  # Project-level rules only
  agents.enabled → .cursor/rules/*.mdc

  # Settings (if applicable)
  tools.cursor.settings → .cursor/settings.json

  # Project config
  tools.cursor.project → .cursorignore
```

### Cursor Adapter Implementation
```python
class CursorAdapter(ToolAdapter):
    """Cursor integration adapter - project-level only"""

    def sync_agents(self, agents: List[Agent]) -> Dict[str, Any]:
        """Sync agents to project .cursor directory"""
        result = {
            'synced': 0,
            'errors': [],
            'message': None
        }

        # Check if we're in a project context
        cwd = Path.cwd()
        if cwd == Path.home():
            result['status'] = 'error'
            result['errors'].append('Cannot sync Cursor rules to home directory. Please run from within a project.')
            return result

        # Create project-level .cursor/rules directory
        cursor_rules_dir = cwd / '.cursor' / 'rules'
        cursor_rules_dir.mkdir(parents=True, exist_ok=True)

        for agent in agents:
            if agent.enabled:
                # Generate MDC content with frontmatter
                mdc_content = f"""---
description: "{agent.display_name} Agent"
globs:
  - '**/*'
alwaysApply: false
---

{agent.content}
"""
                # Write .mdc file
                rule_file = cursor_rules_dir / f"{agent.name}.mdc"
                rule_file.write_text(mdc_content)
                result['synced'] += 1

        if result['synced'] > 0:
            result['message'] = f"Synced {result['synced']} agents to project .cursor/rules/ directory"

        return result
```

### Cursor Rules Generation
```yaml
# Generated .mdc file example: lead-developer.mdc
---
description: "Lead Developer Agent"
globs:
  - '**/*'
alwaysApply: false
---

# Lead Developer

## Identity
- **Name**: Sarah Chen, Engineering Lead
- **Title**: Lead Developer & Technical Architect
- **Team**: Engineering
- **Personality**: Systems thinker, problem solver, mentor
- **Voice Trigger**: "Hey Lead" or "Consult Architecture"

## Core Competencies
### Primary Expertise
- Software architecture and system design
- Code quality and best practices
- Team leadership and mentoring
- Technical debt management

### Code Review Standards
- Ensure code follows SOLID principles
- Check for proper error handling
- Verify test coverage
- Look for performance implications

### Architecture Decisions
- Prefer composition over inheritance
- Use dependency injection
- Keep modules loosely coupled
- Document architectural decisions
```

### Cursor-Specific Features

#### 1. Project-Level Rules Management
```bash
# Sync agents to current project's .cursor/rules directory
myai integration sync cursor

# List project rules
ls .cursor/rules/*.mdc

# Note: Must be run from within a project directory
```

#### 2. How It Works
When syncing to Cursor, MyAI will:
1. Check that you're in a project directory (not home)
2. Create `.cursor/rules/` directory in the current project
3. Write each agent as a `.mdc` file with proper frontmatter
4. Report success with number of agents synced

Example output:
```
🔄 Syncing 23 agents...
✅ Synced 23 agents to project .cursor/rules/ directory
```

#### 3. Project Configuration
```bash
# Each project maintains its own agent configuration
cd /path/to/project1
myai integration sync cursor  # Creates project1/.cursor/rules/

cd /path/to/project2
myai integration sync cursor  # Creates project2/.cursor/rules/
```

## Integration Sync Strategies

### 1. One-Way Sync (MyAI → Tool)
```python
def sync_to_tool(tool: str, components: List[str]) -> None:
    """Sync MyAI config to tool"""
    adapter = get_adapter(tool)

    if 'config' in components:
        myai_config = load_myai_config()
        tool_config = transform_config(myai_config, tool)
        adapter.write_config(tool_config)

    if 'agents' in components:
        agents = load_enabled_agents()
        adapter.sync_agents(agents)
```

### 2. Two-Way Sync (MyAI ↔ Tool)
```python
def bidirectional_sync(tool: str) -> None:
    """Bidirectional sync with conflict resolution"""
    adapter = get_adapter(tool)

    # Read both configs
    myai_config = load_myai_config()
    tool_config = adapter.read_config()

    # Detect conflicts
    conflicts = detect_conflicts(myai_config, tool_config)

    if conflicts:
        resolution = resolve_conflicts(conflicts)

    # Apply changes
    merged_config = merge_configs(myai_config, tool_config, resolution)
    save_myai_config(merged_config)
    adapter.write_config(merged_config)
```

### 3. Auto-Sync with File Watching
```python
class SyncWatcher:
    """Watch for changes and auto-sync"""

    def __init__(self, tools: List[str]):
        self.tools = tools
        self.observer = Observer()

    def start(self):
        # Watch MyAI config directory
        self.observer.schedule(
            MyAIHandler(self.on_myai_change),
            path='~/.myai',
            recursive=True
        )

        # Watch tool directories
        for tool in self.tools:
            adapter = get_adapter(tool)
            if path := adapter.detect_installation():
                self.observer.schedule(
                    ToolHandler(self.on_tool_change, tool),
                    path=path,
                    recursive=True
                )
```

## Conflict Resolution

### Conflict Detection
```json
{
  "conflicts": [
    {
      "path": "tools.claude.settings.model",
      "myai_value": "claude-3-sonnet",
      "tool_value": "claude-3-opus",
      "detected_at": "2025-01-16T10:00:00Z"
    }
  ]
}
```

### Resolution Strategies
```python
class ConflictResolver:
    """Handle configuration conflicts"""

    STRATEGIES = {
        'prefer_myai': lambda m, t: m,
        'prefer_tool': lambda m, t: t,
        'newest': lambda m, t: m if m.modified > t.modified else t,
        'interactive': lambda m, t: prompt_user(m, t),
        'merge': lambda m, t: deep_merge(m, t)
    }
```

## Tool Discovery

### Auto-Detection
```python
class ToolDetector:
    """Automatically detect installed AI tools"""

    KNOWN_TOOLS = {
        'claude': {
            'paths': ['~/.claude', '~/AppData/Roaming/Claude'],
            'indicators': ['settings.json', 'mcp_servers.json']
        },
        'cursor': {
            'paths': ['.cursor', '~/.cursor'],
            'indicators': ['settings.json', '.cursorrules']
        },
        'copilot': {
            'paths': ['~/.config/github-copilot'],
            'indicators': ['config.json']
        }
    }

    def detect_all(self) -> List[str]:
        """Detect all installed tools"""
        detected = []
        for tool, config in self.KNOWN_TOOLS.items():
            if self._is_installed(tool, config):
                detected.append(tool)
        return detected
```

## Future Tool Support

### Adding New Tools
```python
# 1. Create adapter class
class NewToolAdapter(ToolAdapter):
    def detect_installation(self) -> Optional[Path]:
        # Tool-specific detection logic
        pass

    # Implement other required methods

# 2. Register adapter
TOOL_ADAPTERS['newtool'] = NewToolAdapter

# 3. Add to CLI
@app.command()
def newtool(ctx: Context):
    """Manage NewTool integration"""
    pass
```

### Plugin Architecture
```yaml
# ~/.myai/plugins/vscode-integration.yaml
name: vscode
version: 1.0.0
adapter: VSCodeAdapter
commands:
  - name: vscode
    description: Manage VSCode integration
detection:
  paths:
    - ~/.vscode
    - ~/AppData/Roaming/Code
  indicators:
    - settings.json
```

## Integration Testing

### Test Scenarios
```python
class IntegrationTests:
    """Test tool integrations"""

    def test_claude_sync(self):
        # Setup
        create_test_agents()

        # Sync
        myai.sync('claude', components=['agents'])

        # Verify
        assert claude_agents_exist()
        assert symlinks_valid()

    def test_cursor_rules_generation(self):
        # Setup
        agents = load_test_agents()

        # Generate
        rules = generate_cursor_rules(agents)

        # Verify
        assert '.cursorrules' in rules
        assert all(agent.name in rules for agent in agents)
```

## Monitoring and Logging

### Integration Events
```json
{
  "event": "sync_completed",
  "tool": "claude",
  "timestamp": "2025-01-16T10:00:00Z",
  "components": ["config", "agents"],
  "status": "success",
  "changes": {
    "config_updated": true,
    "agents_synced": 5,
    "errors": []
  }
}
```

### Health Checks
```bash
# Check integration status
myai status --tools

# Output:
Tool Integration Status
┏━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Tool    ┃ Installed ┃ Configured   ┃ Last Sync ┃
┡━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Claude  │ ✅ Yes    │ ✅ Synced    │ 2 min ago │
│ Cursor  │ ✅ Yes    │ ⚠️  Modified │ 1 hour ago│
│ Copilot │ ❌ No     │ -            │ -         │
└─────────┴───────────┴──────────────┴───────────┘
```

## Security Considerations

### 1. Secure Configuration Storage
- Sensitive data in environment variables
- No credentials in synced configs
- Encrypted storage for API keys

### 2. Permission Validation
- Validate file permissions before sync
- Check tool directory ownership
- Prevent privilege escalation

### 3. Audit Trail
```json
{
  "audit_log": [
    {
      "action": "sync_claude",
      "user": "john.doe",
      "timestamp": "2025-01-16T10:00:00Z",
      "changes": ["Updated 3 agents", "Modified settings.json"],
      "ip": "192.168.1.100"
    }
  ]
}
```
