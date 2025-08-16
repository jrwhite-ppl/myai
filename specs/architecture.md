# MyAI Architecture Specification

## System Architecture Overview

MyAI follows a layered architecture pattern that separates concerns and enables extensibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Interface Layer                      │
│                    (Typer + Rich + Commands)                     │
├─────────────────────────────────────────────────────────────────┤
│                      Configuration Manager                       │
│              (Settings, Merge Logic, Validation)                 │
├─────────────────────────────────────────────────────────────────┤
│                        Agent Manager                             │
│           (Registry, Discovery, CRUD Operations)                 │
├─────────────────────────────────────────────────────────────────┤
│                     Integration Adapters                         │
│        (Claude Adapter, Cursor Adapter, Future Adapters)         │
├─────────────────────────────────────────────────────────────────┤
│                      Storage Layer                               │
│              (File System, JSON/YAML/TOML Support)               │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. CLI Interface Layer
- **Technology**: Typer for command parsing, Rich for output formatting
- **Responsibility**: User interaction, command routing, output presentation
- **Key Classes**:
  - `CLIApp`: Main application entry point
  - `CommandRegistry`: Dynamic command registration
  - `OutputFormatter`: Consistent output formatting

### 2. Configuration Manager
- **Responsibility**: Hierarchical configuration management and merging
- **Key Classes**:
  - `ConfigurationManager`: Core configuration operations
  - `ConfigMerger`: Intelligent merge strategies
  - `ConfigValidator`: Schema validation
  - `ConfigBackup`: Backup and restore functionality

### 3. Agent Manager
- **Responsibility**: Agent lifecycle management
- **Key Classes**:
  - `AgentRegistry`: Central agent repository
  - `AgentLoader`: Dynamic agent loading
  - `AgentValidator`: Agent specification validation
  - `AgentTemplate`: Template management

### 4. Integration Adapters
- **Responsibility**: Tool-specific configuration translation
- **Key Classes**:
  - `BaseAdapter`: Abstract adapter interface
  - `ClaudeAdapter`: Claude Code integration
  - `CursorAdapter`: Cursor integration
  - `AdapterFactory`: Dynamic adapter creation

### 5. Storage Layer
- **Responsibility**: Persistent storage operations
- **Key Classes**:
  - `StorageManager`: File system operations
  - `FormatHandler`: Multi-format support
  - `PathResolver`: Path resolution and management

## Directory Structure

### User Home Directory (`~/.myai/`)
```
~/.myai/
├── config/
│   ├── global.json          # User-level global configuration
│   ├── teams/               # Team configurations
│   │   └── {team-name}.json
│   └── enterprise/          # Enterprise configurations
│       └── {org-name}.json
├── agents/
│   ├── default/             # Default agent library
│   │   ├── engineering/
│   │   ├── marketing/
│   │   └── ...
│   └── custom/              # User-defined agents
│       └── {agent-name}.md
├── templates/               # Agent templates
│   └── {template-name}.md
├── backups/                 # Configuration backups
│   └── {timestamp}/
├── cache/                   # Temporary cache
└── logs/                    # Application logs
```

### Project Directory (`.myai/`)
```
.myai/
├── config.json              # Project-specific configuration
├── agents/                  # Project-specific agents
│   └── {agent-name}.md
└── overrides/               # Tool-specific overrides
    ├── claude.json
    └── cursor.json
```

### Tool-Specific Directories
```
# Claude Code Integration
~/.claude/
├── settings.json            # Redirects to ~/.myai/config/
├── agents/                  # Symlink to ~/.myai/agents/
└── ...

# Cursor Integration  
.cursor/
├── rules/                   # Generated from MyAI agents
└── ...
```

## Configuration Hierarchy

### Resolution Order (Highest to Lowest Priority)
1. **Project Level** (`.myai/config.json`)
2. **Team Level** (`~/.myai/config/teams/{team}.json`)
3. **User Level** (`~/.myai/config/global.json`)
4. **Enterprise Level** (`~/.myai/config/enterprise/{org}.json`)
5. **Defaults** (Built-in defaults)

### Merge Strategy
```python
# Pseudo-code for configuration merging
def merge_configs(configs: List[Config]) -> Config:
    result = {}
    for config in reversed(configs):  # Start with lowest priority
        if merge_mode == "merge":
            deep_merge(result, config)
        elif merge_mode == "nuclear":
            result = config  # Complete replacement
    return result
```

## Data Flow

### Configuration Read Flow
```
User Request → CLI Command → ConfigurationManager
    ↓
PathResolver → Determine active configs
    ↓
StorageManager → Load config files
    ↓
ConfigMerger → Merge hierarchically
    ↓
ConfigValidator → Validate result
    ↓
Return merged configuration
```

### Agent Discovery Flow
```
Agent Request → AgentManager → AgentRegistry
    ↓
PathResolver → Search paths:
    1. Project agents (.myai/agents/)
    2. Custom agents (~/.myai/agents/custom/)
    3. Default agents (~/.myai/agents/default/)
    ↓
AgentLoader → Load and parse agent files
    ↓
AgentValidator → Validate specifications
    ↓
Return agent collection
```

### Tool Integration Flow
```
Integration Command → AdapterFactory → Select Adapter
    ↓
Adapter → Read MyAI configuration
    ↓
Transform → Convert to tool-specific format
    ↓
Write → Update tool configuration
    ↓
Verify → Validate tool acceptance
```

## Design Patterns

### 1. Strategy Pattern
- Used for merge strategies (merge vs nuclear)
- Used for output formats (JSON, YAML, pretty)

### 2. Factory Pattern
- `AdapterFactory` for creating tool-specific adapters
- `CommandFactory` for dynamic command creation

### 3. Chain of Responsibility
- Configuration resolution through hierarchy
- Error handling and recovery

### 4. Observer Pattern
- Configuration change notifications
- Tool synchronization triggers

### 5. Template Method
- Base adapter class defining integration flow
- Agent specification processing

## Extension Points

### 1. New AI Tool Integration
```python
class NewToolAdapter(BaseAdapter):
    def transform_config(self, config: Config) -> ToolConfig:
        # Tool-specific transformation
        pass
    
    def write_config(self, tool_config: ToolConfig) -> None:
        # Tool-specific write operation
        pass
```

### 2. Custom Command Addition
```python
@app.command()
def custom_command(ctx: Context):
    # Command implementation
    pass
```

### 3. New Configuration Format
```python
class NewFormatHandler(BaseFormatHandler):
    def load(self, path: Path) -> dict:
        # Format-specific load
        pass
    
    def save(self, path: Path, data: dict) -> None:
        # Format-specific save
        pass
```

## Performance Considerations

### 1. Lazy Loading
- Agents loaded on-demand
- Configurations cached in memory
- Tool adapters instantiated when needed

### 2. Efficient Merging
- Smart diff algorithms for incremental updates
- Minimal file I/O operations
- Parallel processing for multiple tools

### 3. Caching Strategy
- In-memory configuration cache
- File system watch for invalidation
- TTL-based cache expiration

## Security Architecture

### 1. File Permissions
- Secure file creation (600 for sensitive files)
- Directory permissions (700 for private directories)
- Ownership validation

### 2. Configuration Validation
- Schema validation before write
- Injection attack prevention
- Path traversal protection

### 3. Sensitive Data Handling
- No credentials in configurations
- Environment variable support
- Secure delete for backups

## Error Handling Strategy

### 1. Graceful Degradation
- Missing configurations use defaults
- Partial tool updates on failure
- Rollback capability

### 2. User-Friendly Errors
- Clear error messages
- Suggested fixes
- Debug mode for detailed traces

### 3. Recovery Mechanisms
- Automatic backup before changes
- Configuration restore commands
- Conflict resolution workflows

## Testing Architecture

### 1. Unit Testing
- Component isolation with mocks
- Comprehensive coverage targets
- Property-based testing for mergers

### 2. Integration Testing
- Real file system operations
- Tool adapter verification
- End-to-end workflows

### 3. Performance Testing
- Large configuration handling
- Many agents scenarios
- Concurrent operations