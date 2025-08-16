# Agent-OS Integration Specification

## Overview

This specification details how MyAI integrates with Agent-OS while maintaining complete abstraction from end users. Agent-OS provides the foundational patterns and structures, but users interact exclusively with MyAI branding and conventions.

## Integration Philosophy

### Core Principles
1. **Invisible Integration**: Users should never see Agent-OS references
2. **Dependency Management**: Agent-OS as a git submodule or versioned dependency
3. **Customization Layer**: MyAI extends and enhances Agent-OS functionality
4. **Update Strategy**: Easy integration of upstream Agent-OS updates
5. **Directory Translation**: All `.agent-os/` paths become `.myai/`

## Dependency Architecture

### Git Submodule Approach
```bash
# Add Agent-OS as a submodule
git submodule add https://github.com/buildermethods/agent-os.git lib/agent-os
git submodule update --init --recursive

# Track specific version
cd lib/agent-os
git checkout v1.0.0
cd ../..
git add lib/agent-os
git commit -m "Pin Agent-OS to v1.0.0"
```

### Directory Structure
```
myai/
├── lib/
│   └── agent-os/                    # Agent-OS submodule
│       ├── agents/                  # Original agents
│       ├── scripts/                 # Setup scripts
│       └── ...
├── src/
│   └── myai/
│       ├── agent_os/               # Integration layer
│       │   ├── adapter.py          # Agent-OS adapter
│       │   ├── transformer.py      # Path/config transformer
│       │   └── sync.py             # Sync functionality
│       └── data/
│           └── agents/             # MyAI-specific agents
└── scripts/
    └── sync-agent-os.py            # Update from upstream
```

## Path Translation

### Mapping Rules
```python
PATH_MAPPINGS = {
    # Agent-OS paths → MyAI paths
    '.agent-os': '.myai',
    'agent-os': 'myai',
    'AGENT_OS': 'MYAI',
    
    # Specific directories
    '.agent-os/agents': '~/.myai/agents/default',
    '.agent-os/product': '~/.myai/docs/internal',
    '.agent-os/standards': '~/.myai/standards',
    
    # Files
    'AGENT_OS_README.md': None,  # Skip
    '.agent-os-version': '.myai-version',
}
```

### Translation Implementation
```python
class AgentOSTransformer:
    """Transform Agent-OS content to MyAI conventions"""
    
    def transform_path(self, agent_os_path: Path) -> Path:
        """Convert Agent-OS path to MyAI path"""
        path_str = str(agent_os_path)
        
        for old, new in PATH_MAPPINGS.items():
            if new is None and old in path_str:
                return None  # Skip this path
            path_str = path_str.replace(old, new)
        
        return Path(path_str)
    
    def transform_content(self, content: str) -> str:
        """Transform file content references"""
        # Replace Agent-OS references
        content = content.replace('Agent-OS', 'MyAI internal system')
        content = content.replace('agent-os', 'myai')
        content = content.replace('.agent-os', '.myai')
        
        # Remove Agent-OS specific documentation
        content = re.sub(r'<!--\s*AGENT-OS-ONLY\s*-->.*?<!--\s*/AGENT-OS-ONLY\s*-->', 
                         '', content, flags=re.DOTALL)
        
        return content
```

## Agent Transformation

### Agent-OS to MyAI Format
```python
class AgentTransformer:
    """Transform Agent-OS agents to MyAI format"""
    
    def transform_agent(self, agent_os_agent: dict) -> dict:
        """Convert Agent-OS agent to MyAI format"""
        # Add MyAI metadata
        myai_agent = {
            'version': '1.0.0',
            'source': 'agent-os',
            'original_version': agent_os_agent.get('version'),
            **agent_os_agent
        }
        
        # Add MyAI-specific fields
        if 'name' in myai_agent:
            myai_agent['id'] = self._generate_id(myai_agent['name'])
            myai_agent['category'] = self._categorize_agent(myai_agent)
        
        # Transform paths in content
        if 'content' in myai_agent:
            myai_agent['content'] = self.transformer.transform_content(
                myai_agent['content']
            )
        
        return myai_agent
```

## Setup Script Integration

### Adapting Agent-OS Scripts
```python
#!/usr/bin/env python3
"""Adapt Agent-OS setup scripts for MyAI"""

import subprocess
import shutil
from pathlib import Path

class SetupAdapter:
    """Adapt Agent-OS setup scripts"""
    
    def __init__(self):
        self.agent_os_dir = Path('lib/agent-os')
        self.scripts_map = {
            'setup.sh': 'setup-myai-core.sh',
            'setup-cursor.sh': 'setup-myai-cursor.sh',
            'setup-claude-code.sh': 'setup-myai-claude.sh',
        }
    
    def adapt_script(self, script_name: str) -> str:
        """Adapt an Agent-OS script for MyAI"""
        script_path = self.agent_os_dir / script_name
        content = script_path.read_text()
        
        # Replace paths
        content = content.replace('~/.agent-os', '~/.myai')
        content = content.replace('agent-os', 'myai')
        
        # Replace branding
        content = content.replace('Agent-OS Setup', 'MyAI Setup')
        content = content.replace('Setting up Agent-OS', 'Setting up MyAI')
        
        # Add MyAI-specific setup
        content += """
# MyAI-specific setup
echo "Configuring MyAI extensions..."
myai init --quiet --import-agent-os
"""
        
        return content
```

## Update Management

### Syncing with Upstream
```python
class AgentOSSync:
    """Sync with upstream Agent-OS changes"""
    
    def check_updates(self) -> bool:
        """Check for Agent-OS updates"""
        os.chdir('lib/agent-os')
        
        # Fetch latest
        subprocess.run(['git', 'fetch', 'origin'])
        
        # Check if behind
        result = subprocess.run(
            ['git', 'rev-list', 'HEAD..origin/main', '--count'],
            capture_output=True, text=True
        )
        
        return int(result.stdout.strip()) > 0
    
    def sync_agents(self):
        """Sync Agent-OS agents to MyAI"""
        agent_os_agents = Path('lib/agent-os/agents')
        myai_agents = Path('src/myai/data/agents/default/agent-os')
        
        # Clear existing
        if myai_agents.exists():
            shutil.rmtree(myai_agents)
        myai_agents.mkdir(parents=True)
        
        # Transform and copy
        for agent_file in agent_os_agents.glob('**/*.md'):
            # Transform content
            content = agent_file.read_text()
            transformed = self.transformer.transform_content(content)
            
            # Determine destination
            rel_path = agent_file.relative_to(agent_os_agents)
            dest = myai_agents / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Write transformed content
            dest.write_text(transformed)
```

### Version Tracking
```json
{
  "agent_os": {
    "version": "1.0.0",
    "commit": "abc123def456",
    "last_sync": "2025-01-16T10:00:00Z",
    "modifications": [
      {
        "file": "agents/lead_developer.md",
        "type": "content_transform",
        "description": "Replaced Agent-OS references"
      }
    ]
  }
}
```

## CLI Integration

### Hidden Agent-OS Commands
```python
@app.command(hidden=True)
def agent_os(ctx: typer.Context):
    """Internal Agent-OS management (hidden from users)"""
    pass

@agent_os.command()
def sync():
    """Sync with upstream Agent-OS"""
    syncer = AgentOSSync()
    
    if syncer.check_updates():
        typer.echo("Updates available from Agent-OS")
        if typer.confirm("Sync now?"):
            syncer.sync_agents()
            syncer.sync_configs()
    else:
        typer.echo("Already up to date with Agent-OS")

@agent_os.command()
def status():
    """Show Agent-OS integration status"""
    with open('.myai/agent-os-version.json') as f:
        version_info = json.load(f)
    
    typer.echo(f"Agent-OS Version: {version_info['agent_os']['version']}")
    typer.echo(f"Last Sync: {version_info['agent_os']['last_sync']}")
```

## Build Process Integration

### Package Build Script
```python
# build.py
import shutil
from pathlib import Path

def prepare_agent_os_content():
    """Prepare Agent-OS content for packaging"""
    # Copy and transform agents
    transform_agents()
    
    # Copy and adapt scripts
    adapt_scripts()
    
    # Generate attribution
    generate_attribution()

def generate_attribution():
    """Generate Agent-OS attribution file"""
    attribution = """
# Attribution

MyAI includes adapted content from Agent-OS (https://github.com/buildermethods/agent-os)
Licensed under [Agent-OS License]

Modifications:
- Path translations (.agent-os -> .myai)
- Branding updates
- Additional functionality

Original Agent-OS version: {version}
    """.strip()
    
    Path('ATTRIBUTION.md').write_text(attribution)
```

## Testing Integration

### Integration Tests
```python
def test_agent_os_transformation():
    """Test Agent-OS content transformation"""
    transformer = AgentOSTransformer()
    
    # Test path transformation
    assert transformer.transform_path(Path('.agent-os/config')) == Path('.myai/config')
    
    # Test content transformation
    original = "Configure your .agent-os directory"
    transformed = transformer.transform_content(original)
    assert '.agent-os' not in transformed
    assert '.myai' in transformed

def test_agent_sync():
    """Test agent synchronization"""
    # Mock Agent-OS agents
    create_mock_agent_os_structure()
    
    # Run sync
    syncer = AgentOSSync()
    syncer.sync_agents()
    
    # Verify transformation
    myai_agents = Path('src/myai/data/agents/default/agent-os')
    assert myai_agents.exists()
    
    # Check no Agent-OS references remain
    for agent_file in myai_agents.glob('**/*.md'):
        content = agent_file.read_text()
        assert 'agent-os' not in content.lower()
        assert 'Agent-OS' not in content
```

## Configuration Mapping

### Agent-OS Config to MyAI Config
```python
CONFIG_MAPPINGS = {
    # Agent-OS config keys -> MyAI config keys
    'agent_os_version': 'internal.agent_os_version',
    'product.mission': 'internal.mission',
    'product.vision': 'internal.vision',
    
    # Skip these
    'internal_only': None,
}

def transform_config(agent_os_config: dict) -> dict:
    """Transform Agent-OS config to MyAI format"""
    myai_config = {}
    
    for key, value in agent_os_config.items():
        if key in CONFIG_MAPPINGS:
            new_key = CONFIG_MAPPINGS[key]
            if new_key:
                set_nested(myai_config, new_key, value)
        else:
            # Default mapping
            myai_config[key] = value
    
    return myai_config
```

## Documentation

### User-Facing Documentation
- No mention of Agent-OS in user docs
- All examples use MyAI paths and commands
- Agent-OS patterns presented as MyAI best practices

### Internal Documentation
```markdown
# MyAI Internal - Agent-OS Integration

This document is for MyAI maintainers only.

## Updating from Agent-OS

1. Check for updates:
   ```bash
   cd lib/agent-os
   git fetch origin
   git log HEAD..origin/main --oneline
   ```

2. Review changes for compatibility

3. Update and test:
   ```bash
   git checkout origin/main
   cd ../..
   python scripts/sync-agent-os.py
   pytest tests/agent_os/
   ```

4. Commit updates:
   ```bash
   git add -A
   git commit -m "Sync with Agent-OS upstream"
   ```
```

## Future Considerations

### Maintaining Compatibility
1. Monitor Agent-OS API/structure changes
2. Maintain transformation layer compatibility
3. Version-specific adaptations if needed

### Contributing Back
1. Identify MyAI improvements beneficial to Agent-OS
2. Prepare patches without MyAI-specific content
3. Contribute back to Agent-OS project

### Independence Path
1. Gradually reduce dependencies
2. Build MyAI-specific replacements
3. Maintain compatibility layer for migration