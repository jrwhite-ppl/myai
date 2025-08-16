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

### Configuration Mapping
```yaml
# MyAI → Cursor mapping
myai_to_cursor:
  # Agent rules generation
  agents.enabled → .cursorrules (generated)
  
  # Cursor-specific rules
  tools.cursor.rules → .cursor/rules/*.md
  
  # Settings
  tools.cursor.settings → .cursor/settings.json
  
  # Project config
  tools.cursor.project → .cursorignore
```

### Cursor Adapter Implementation
```python
class CursorAdapter(ToolAdapter):
    """Cursor integration adapter"""
    
    def sync_agents(self, agents: List[Agent]) -> None:
        """Convert agents to Cursor rules format"""
        rules_content = self._generate_cursor_rules(agents)
        
        # Write to .cursorrules
        cursorrules_path = Path.cwd() / '.cursorrules'
        cursorrules_path.write_text(rules_content)
        
        # Also sync to .cursor/rules/ if exists
        cursor_dir = Path.cwd() / '.cursor'
        if cursor_dir.exists():
            rules_dir = cursor_dir / 'rules'
            rules_dir.mkdir(exist_ok=True)
            
            for agent in agents:
                if agent.enabled:
                    rule_file = rules_dir / f"{agent.name}.md"
                    rule_content = self._agent_to_rule(agent)
                    rule_file.write_text(rule_content)
    
    def _agent_to_rule(self, agent: Agent) -> str:
        """Convert agent spec to Cursor rule format"""
        return f"""---
description: {agent.display_name} - {agent.description}
globs: {', '.join(agent.file_patterns) if agent.file_patterns else '*'}
alwaysApply: {str(agent.always_apply).lower()}
---

{agent.content}
"""
```

### Cursor Rules Generation
```markdown
# Generated .cursorrules example

## Lead Developer Rules
You are a senior technical leader with deep expertise in software architecture and team leadership.

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

## DevOps Engineer Rules
You are a DevOps specialist focused on reliability and automation.

### Infrastructure as Code
- All infrastructure must be version controlled
- Use declarative configuration
- Implement proper state management
- Include rollback procedures

### CI/CD Best Practices
- Automated testing is mandatory
- Use blue-green deployments
- Monitor deployment metrics
- Implement proper secrets management
```

### Cursor-Specific Features

#### 1. Rules Management
```bash
# Generate rules from agents
myai cursor rules generate

# List active rules
myai cursor rules list

# Test rules
myai cursor rules test --file example.py
```

#### 2. Project Configuration
```bash
# Initialize Cursor for project
myai cursor init

# Update .cursorignore
myai cursor ignore add "*.log" "temp/"
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