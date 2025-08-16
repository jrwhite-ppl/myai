# Configuration Management Specification

## Overview

The Configuration Management system is the heart of MyAI, providing a hierarchical, flexible, and tool-agnostic way to manage AI assistant configurations. It implements a layered approach supporting Enterprise, User, Team, and Project-level configurations with intelligent merging and conflict resolution.

## Configuration Hierarchy

### 1. Enterprise Level
- **Location**: `~/.myai/config/enterprise/{organization}.json`
- **Purpose**: Organization-wide policies and standards
- **Use Cases**:
  - Mandated security settings
  - Approved agent lists
  - Compliance requirements
  - Resource limits

### 2. User Level
- **Location**: `~/.myai/config/global.json`
- **Purpose**: Personal preferences and defaults
- **Use Cases**:
  - Personal agent preferences
  - Default tool settings
  - UI/UX preferences
  - Personal shortcuts

### 3. Team Level
- **Location**: `~/.myai/config/teams/{team-name}.json`
- **Purpose**: Team-specific configurations
- **Use Cases**:
  - Team coding standards
  - Shared agent configurations
  - Project templates
  - Team-specific tools

### 4. Project Level
- **Location**: `.myai/config.json` (in project root)
- **Purpose**: Project-specific settings
- **Use Cases**:
  - Project-specific agents
  - Custom tool configurations
  - Override defaults
  - Project workflows

## Configuration Schema

### Base Configuration Structure
```json
{
  "version": "1.0.0",
  "metadata": {
    "created": "2025-01-16T10:00:00Z",
    "modified": "2025-01-16T10:00:00Z",
    "source": "user|team|enterprise|project",
    "priority": 100
  },
  "settings": {
    "merge_strategy": "merge|nuclear",
    "auto_sync": true,
    "backup_enabled": true,
    "backup_count": 5
  },
  "tools": {
    "claude": {
      "enabled": true,
      "settings": {},
      "permissions": {},
      "allowed_tools": []
    },
    "cursor": {
      "enabled": true,
      "rules": {},
      "extensions": []
    }
  },
  "agents": {
    "enabled": ["agent1", "agent2"],
    "disabled": ["agent3"],
    "custom_path": "path/to/agents",
    "auto_discover": true
  },
  "integrations": {
    "git": {
      "auto_commit_config": false,
      "config_branch": "main"
    },
    "mcp_servers": {}
  }
}
```

### Merge Strategies

#### 1. Merge Mode (Default)
```python
# Intelligent deep merge preserving user intent
{
  "base": {"a": 1, "b": {"c": 2}},
  "overlay": {"b": {"d": 3}, "e": 4}
}
# Result: {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
```

#### 2. Nuclear Mode
```python
# Complete replacement - use with caution
{
  "base": {"a": 1, "b": 2},
  "overlay": {"c": 3}
}
# Result: {"c": 3}  # Base completely replaced
```

### Special Merge Rules

#### Arrays
- **Default**: Concatenate and deduplicate
- **Override**: Use `!replace` prefix
```json
{
  "agents": {
    "enabled": ["!replace", "agent1", "agent2"]
  }
}
```

#### Deletions
- Use `!delete` marker
```json
{
  "tools": {
    "deprecated_tool": "!delete"
  }
}
```

## Configuration Operations

### 1. Read Operation
```bash
myai config show [--level user|team|project|merged]
myai config get <key.path>
```

### 2. Write Operation
```bash
myai config set <key.path> <value> [--level user|team|project]
myai config merge <config-file> [--strategy merge|nuclear]
```

### 3. Management Operations
```bash
myai config backup [--name <backup-name>]
myai config restore <backup-name>
myai config reset [--level user|team|project|all]
myai config validate [--file <config-file>]
```

## Conflict Resolution

### Priority Rules
1. Explicit priority values (higher wins)
2. Level-based priority: Project > Team > User > Enterprise
3. Timestamp-based (newer wins) for same level

### Conflict Detection
```json
{
  "conflicts": [
    {
      "key": "tools.claude.settings.model",
      "sources": [
        {"level": "team", "value": "claude-3"},
        {"level": "user", "value": "claude-2"}
      ],
      "resolved": "claude-3",
      "strategy": "priority"
    }
  ]
}
```

## Tool-Specific Mappings

### Claude Code Mapping
```yaml
myai_config:
  tools.claude.settings -> ~/.claude/settings.json
  tools.claude.permissions -> ~/.claude/settings.json#permissions
  agents.enabled -> ~/.claude/agents/ (symlinks)
  integrations.mcp_servers -> ~/.claude/mcp_servers.json
```

### Cursor Mapping
```yaml
myai_config:
  agents -> .cursorrules (generated)
  tools.cursor.rules -> .cursor/rules/
  tools.cursor.extensions -> .cursor/extensions.json
```

## Advanced Features

### 1. Environment Variable Support
```json
{
  "tools": {
    "claude": {
      "api_key": "${CLAUDE_API_KEY}",
      "endpoint": "${CLAUDE_ENDPOINT:-https://api.anthropic.com}"
    }
  }
}
```

### 2. Conditional Configuration
```json
{
  "conditions": [
    {
      "if": {"os": "darwin"},
      "then": {"tools": {"cursor": {"keybindings": "mac"}}}
    }
  ]
}
```

### 3. Configuration Inheritance
```json
{
  "extends": "~/.myai/templates/python-project.json",
  "overrides": {
    "agents": {"enabled": ["python-expert"]}
  }
}
```

## Security Considerations

### 1. Sensitive Data
- Never store credentials directly
- Use environment variables or secure stores
- Implement `.myai-private` for sensitive configs

### 2. Access Control
```json
{
  "security": {
    "readonly_keys": ["enterprise.*"],
    "encrypted_keys": ["integrations.api_keys.*"],
    "audit_changes": true
  }
}
```

### 3. Validation Rules
- Schema validation on all writes
- Type checking for values
- Path validation to prevent traversal
- Size limits for configurations

## Migration Support

### From Existing Tools
```bash
myai migrate claude  # Import from Claude Code
myai migrate cursor  # Import from Cursor
myai migrate detect  # Auto-detect and import
```

### Version Migration
```json
{
  "migrations": {
    "1.0.0->1.1.0": {
      "renames": {"old_key": "new_key"},
      "transforms": {"key": "transform_function"}
    }
  }
}
```

## Performance Optimization

### 1. Caching Strategy
- In-memory cache with TTL
- File watchers for invalidation
- Lazy loading of configurations

### 2. Efficient Storage
- Minimize file I/O
- Compress large configurations
- Delta updates for changes

### 3. Parallel Processing
- Concurrent tool updates
- Async configuration loading
- Batch operations support

## Error Handling

### 1. Validation Errors
```json
{
  "error": "validation_failed",
  "details": {
    "field": "tools.claude.model",
    "expected": "string",
    "received": "number",
    "suggestion": "Use quotes around the model name"
  }
}
```

### 2. Merge Conflicts
```json
{
  "error": "merge_conflict",
  "conflicts": [...],
  "resolution_options": [
    "Use --force to apply anyway",
    "Use --interactive for manual resolution",
    "Use --prefer-local or --prefer-remote"
  ]
}
```

### 3. Recovery Options
- Automatic backups before changes
- Rollback to previous state
- Dry-run mode for testing