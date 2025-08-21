# Agent Management Specification

## Overview

The Agent Management system provides comprehensive lifecycle management for AI agents, enabling users to discover, create, modify, and organize specialized AI assistants. It supports both default agents based on Agent-OS patterns and custom user-defined agents.

## Agent Structure

### Agent Specification Format
```markdown
---
name: agent-identifier
display_name: Human Readable Name
description: Detailed description of agent's purpose and capabilities
version: 1.0.0
category: engineering|marketing|finance|security|custom
tags: [python, backend, api, testing]
tools: [Task, Bash, Read, Edit, WebSearch]  # Optional - inherits all if omitted
model: claude-3-sonnet  # Optional - uses default if omitted
temperature: 0.7  # Optional
max_tokens: 4096  # Optional
requires: [python>=3.8, node>=16]  # Optional dependencies
author: user@example.com
created: 2025-01-16T10:00:00Z
modified: 2025-01-16T10:00:00Z
---

# {Agent Name}

## Role and Purpose

{Clear description of the agent's role, expertise, and primary objectives}

## Core Competencies

- {Competency 1}: {Description}
- {Competency 2}: {Description}
- {Competency 3}: {Description}

## Behavioral Guidelines

### Communication Style
- {How the agent should communicate}
- {Tone and formality level}
- {Response structure preferences}

### Decision Making
- {How the agent approaches problems}
- {Prioritization strategies}
- {Risk tolerance and safety considerations}

## Specialized Knowledge

### Domain Expertise
{Specific areas of deep knowledge}

### Best Practices
{Industry or domain-specific best practices the agent should follow}

### Anti-patterns
{What the agent should explicitly avoid}

## Task-Specific Instructions

### For {Task Type 1}
1. {Step-by-step approach}
2. {Specific considerations}
3. {Success criteria}

### For {Task Type 2}
1. {Step-by-step approach}
2. {Specific considerations}
3. {Success criteria}

## Integration Points

### With Other Agents
- {How this agent collaborates with others}
- {Information sharing protocols}
- {Handoff procedures}

### With Tools
- {Preferred tools and their usage}
- {Tool-specific optimizations}
- {Automation strategies}

## Examples

### Example 1: {Scenario}
**Input**: {User request}
**Approach**: {How the agent handles it}
**Output**: {Expected result}

### Example 2: {Scenario}
**Input**: {User request}
**Approach**: {How the agent handles it}
**Output**: {Expected result}

## Constraints and Limitations

- {Explicit boundaries}
- {Ethical considerations}
- {Technical limitations}

## Performance Metrics

- {How to measure agent effectiveness}
- {Key performance indicators}
- {Success criteria}
```

## Agent Categories

### 1. Engineering Agents
```
~/.myai/agents/default/engineering/
├── lead_developer.md
├── devops_engineer.md
├── systems_architect.md
├── frontend_specialist.md
├── backend_specialist.md
├── qa_engineer.md
└── security_analyst.md
```

### 2. Product & Design Agents
```
~/.myai/agents/default/product/
├── product_manager.md
├── ux_designer.md
├── ui_designer.md
├── user_researcher.md
└── technical_writer.md
```

### 3. Business & Operations Agents
```
~/.myai/agents/default/business/
├── project_manager.md
├── business_analyst.md
├── data_analyst.md
├── financial_analyst.md
└── operations_manager.md
```

### 4. Specialized Agents
```
~/.myai/agents/default/specialized/
├── ml_engineer.md
├── data_scientist.md
├── cloud_architect.md
├── mobile_developer.md
└── game_developer.md
```

## Agent Operations

### 1. Discovery Operations
```bash
# List all available agents
myai agent list [--category <category>] [--tags <tag1,tag2>]

# Search agents
myai agent search <query> [--in description|name|content]

# Show agent details
myai agent show <agent-name> [--format full|summary|yaml]

# Find agents for a task
myai agent recommend <task-description>
```

### 2. CRUD Operations
```bash
# Create new agent
myai agent create <name> [--template <template-name>] [--interactive]

# Edit existing agent
myai agent edit <name> [--editor <editor>]

# Copy agent
myai agent copy <source> <destination> [--modify]

# Delete agent
myai agent delete <name> [--force]

# Export/Import agents
myai agent export <name> [--format md|yaml|json] [--output <file>]
myai agent import <file> [--overwrite]
```

### 3. Management Operations
```bash
# Enable/Disable agents
myai agent enable <name> [--scope global|project]
myai agent disable <name> [--scope global|project]

# Validate agents
myai agent validate <name|--all>

# Update agent from template
myai agent update <name> [--from-template <template>]

# Version control
myai agent diff <name> [--with <version|file>]
myai agent history <name>
```

## Agent Registry

### Registry Structure
```json
{
  "version": "1.0.0",
  "agents": {
    "lead_developer": {
      "name": "lead_developer",
      "display_name": "Lead Developer",
      "category": "engineering",
      "path": "~/.myai/agents/default/engineering/lead_developer.md",
      "version": "1.2.0",
      "checksum": "sha256:...",
      "enabled": true,
      "source": "default|custom|community",
      "stats": {
        "usage_count": 42,
        "last_used": "2025-01-16T10:00:00Z",
        "rating": 4.5
      }
    }
  },
  "templates": {
    "base_engineer": {
      "path": "~/.myai/templates/base_engineer.md",
      "description": "Base template for engineering agents"
    }
  }
}
```

### Agent Discovery Process
1. **Scan Directories**
   - Project agents (`.myai/agents/`)
   - User custom agents (`~/.myai/agents/custom/`)
   - Package default agents (`src/myai/data/agents/default/`)
   - User copied agents (`~/.myai/agents/`)
   - Community agents (`~/.myai/agents/community/`)
   - **Imported custom agents** (tracked via metadata, original files preserved)

2. **Parse Specifications**
   - Extract metadata from frontmatter (if present)
   - Extract metadata from content structure (if no frontmatter)
   - Validate agent structure
   - Compute checksums
   - **Load custom agent metadata** from `~/.myai/config/custom_agents.json`

3. **Build Registry**
   - Merge discovered agents
   - Resolve conflicts (project > custom > package default)
   - **Track custom/imported agents** with source attribution
   - Cache results

4. **Apply Filters**
   - Enabled/disabled status
   - Category filters
   - Tag matching
   - Tool requirements
   - **Custom agent source** (e.g., `claude`, `cursor`, `user`)

### Default Agent Loading
- Default agents are bundled with the package in `src/myai/data/agents/default/`
- Agents without YAML frontmatter extract metadata from content structure
- The `myai setup all-setup` command copies default agents to `~/.myai/agents/`
- Package agents are always available even without setup

## Tool Integration

### Claude Code Integration
```bash
# Sync agents to Claude
myai agent sync claude [--agents <list>]

# Creates symlinks:
~/.claude/agents/ -> ~/.myai/agents/enabled/
```

### Cursor Integration
```bash
# Sync agents to current project's .cursor directory
myai integration sync cursor

# Creates .cursor/*.cursorrules in the current project
# Must be run from within a project directory
```

### Agent Transformation
```python
def transform_agent_to_cursor_rules(agent: Agent) -> str:
    """Transform agent spec to Cursor rules format"""
    # For project-level integration, just return the agent content
    # No metadata or frontmatter needed
    return agent.content
```

## Custom Agent Management

### Importing External Agents
```bash
# Import custom agents from integrations
myai system integration-import -i claude

# Import from multiple sources
myai system integration-import -i claude -i cursor
```

### Custom Agent Tracking
- **Metadata Storage**: `~/.myai/config/custom_agents.json`
- **Original Files**: Preserved in their original locations
- **Visual Indicators**: Custom agents show with source `(claude)` or `(cursor)`
- **Uninstall Protection**: Custom agents are NOT removed during MyAI uninstall

### Custom Agent Metadata Format
```json
{
  "my-code-reviewer": {
    "name": "my-code-reviewer",
    "display_name": "My Code Reviewer",
    "description": "Custom code review assistant",
    "category": "custom",
    "source": "claude",
    "external_path": "/Users/john/.claude/agents/my-code-reviewer.md",
    "file_path": "/Users/john/.claude/agents/my-code-reviewer.md"
  }
}
```

### Managing Custom Agents
```bash
# List all agents (including custom)
myai agent list

# Show custom agent details
myai agent show my-code-reviewer

# Enable/disable custom agents
myai agent enable my-code-reviewer
myai agent disable my-code-reviewer

# Custom agents cannot be:
# - Edited through MyAI (use original tool)
# - Deleted through MyAI (remove from original location)
# - Exported (they remain in original location)
```

## Agent Templates

### Base Templates
```
~/.myai/templates/
├── base_agent.md          # Minimal agent template
├── engineering_base.md    # Engineering-focused template
├── analyst_base.md        # Analysis-focused template
├── creative_base.md       # Creative work template
└── leadership_base.md     # Leadership role template
```

### Template Variables
```markdown
---
name: {{agent_name}}
display_name: {{display_name}}
category: {{category}}
created: {{timestamp}}
author: {{user_email}}
---

# {{display_name}}

{{content}}
```

### Template Usage
```bash
# Create from template
myai agent create my-agent --template engineering_base

# Create custom template
myai agent template create <name> [--from-agent <agent>]

# List templates
myai agent template list
```

## Agent Collaboration

### Inter-Agent Communication
```yaml
# In agent specification
integrations:
  delegates_to:
    - security_analyst: "For security reviews"
    - qa_engineer: "For test planning"
  receives_from:
    - product_manager: "Requirements and priorities"
  parallel_work:
    - frontend_specialist: "UI implementation"
```

### Workflow Integration
```json
{
  "workflows": {
    "code_review": {
      "agents": ["lead_developer", "security_analyst"],
      "sequence": "parallel",
      "aggregation": "consensus"
    }
  }
}
```

## Quality Assurance

### Agent Validation Rules
1. **Structure Validation**
   - Required metadata fields
   - Valid YAML frontmatter
   - Proper markdown structure

2. **Content Validation**
   - Minimum content length
   - Required sections present
   - No conflicting instructions

3. **Tool Validation**
   - Requested tools exist
   - Tool permissions valid
   - No dangerous combinations

### Agent Testing
```bash
# Test agent with sample inputs
myai agent test <name> [--scenario <file>]

# Benchmark agent performance
myai agent benchmark <name> [--tasks <task-set>]

# Compare agents
myai agent compare <agent1> <agent2> [--task <task>]
```

## Performance Optimization

### 1. Agent Caching
- Pre-parsed agent specifications
- Indexed search capabilities
- Memory-mapped registry

### 2. Lazy Loading
- Load agent content on-demand
- Metadata-only operations
- Incremental discovery

### 3. Search Optimization
- Full-text search index
- Tag-based filtering
- Category hierarchies

## Security Considerations

### 1. Agent Sandboxing
- Tool restrictions
- Resource limits
- Execution boundaries

### 2. Validation
- Input sanitization
- Instruction injection prevention
- Circular reference detection

### 3. Access Control
- Agent visibility scopes
- Usage permissions
- Audit logging

## Migration and Compatibility

### From Agent-OS
```bash
# Import Agent-OS configurations
myai migrate agent-os [--path <agent-os-path>]

# Maps Agent-OS structure to MyAI format
```

### Version Migration
- Automatic version detection
- Schema migration support
- Backwards compatibility

## Future Enhancements

### 1. Agent Marketplace
- Community agent sharing
- Rating and reviews
- Verified publishers

### 2. Agent Composition
- Combine multiple agents
- Dynamic role switching
- Skill inheritance

### 3. Agent Analytics
- Usage statistics
- Performance metrics
- Improvement suggestions

### 4. AI-Assisted Agent Creation
- Generate agents from descriptions
- Optimize existing agents
- A/B testing support
