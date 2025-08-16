# Agent-OS Integration Adapter

## Overview
This document connects MyAgents specialized agents with the Agent-OS methodology at ~/.agent-os

## Integration Points

### 1. Instruction Execution
When agents need to execute structured tasks, they reference:
- `@agent-os-global/instructions/core/` for core workflows
- `@agent-os-global/instructions/` for specialized instructions

### 2. Standards Compliance
All agents follow standards from:
- `@agent-os-global/standards/best-practices.md` - Development best practices
- `@agent-os-global/standards/code-style/` - Language-specific style guides
- `@agent-os-global/standards/tech-stack.md` - Technology standards

### 3. Specification Creation
When creating new features or specifications:
```
EXECUTE: @agent-os-global/instructions/core/create-spec.md
```

### 4. Task Execution
For structured task execution:
```
EXECUTE: @agent-os-global/instructions/core/execute-tasks.md
```

### 5. Product Analysis
For analyzing requirements or features:
```
EXECUTE: @agent-os-global/instructions/core/analyze-product.md
```

## Agent-Specific Mappings

### Engineering Team
- **Systems Architect** → Uses `create-spec.md` for architecture specifications
- **Lead Developer** → Follows `code-style.md` and `best-practices.md`
- **QA Engineer** → References testing standards from `best-practices.md`
- **Data Analyst** → Uses `analyze-product.md` for data requirements
- **BI Developer** → Follows `execute-tasks.md` for dashboard creation
- **DevOps Engineer** → Uses deployment standards from `tech-stack.md`

### Marketing Team
- **Brand Strategist** → Uses `analyze-product.md` for market analysis
- **Content Creator** → Follows content standards and best practices
- **Customer Success** → References customer workflows
- **Customer Support** → Uses issue resolution protocols

### Legal Team
- **Senior Legal Advisor** → Creates legal specs using `create-spec.md`
- **Contract Specialist** → Follows contract review workflows

### Security Team
- **Chief Security Officer** → Uses security standards and compliance workflows
- **Security Analyst** → Follows incident response protocols

### Finance Team
- **CFO** → Uses financial analysis workflows
- **Finance Specialist** → Follows compliance and reporting standards

### Leadership
- **A-Player Leaders** → Coordinate using `plan-product.md` workflows

## Workflow Integration Pattern

When an agent receives a request:

1. **Check for Agent-OS Workflow**
   ```
   IF task matches agent-os instruction:
     EXECUTE: @agent-os-global/instructions/[relevant-instruction].md
   ```

2. **Apply Standards**
   ```
   APPLY: @agent-os-global/standards/[relevant-standard].md
   ```

3. **Follow Team Workflow**
   ```
   FOLLOW: @agent_os/workflows/[team]_workflows.md
   ```

4. **Maintain RAW Output**
   ```
   OUTPUT: Using RAW agent protocol from @CLAUDE.md
   ```

## Voice Command Extensions

### Spec Creation
"Hey [Agent], create a spec for [feature]"
→ Agent executes `@agent-os-global/instructions/core/create-spec.md`

### Task Execution
"Hey [Agent], execute tasks for [project]"
→ Agent follows `@agent-os-global/instructions/core/execute-tasks.md`

### Product Analysis
"Hey [Agent], analyze [requirement]"
→ Agent uses `@agent-os-global/instructions/core/analyze-product.md`

### Best Practices Check
"Hey [Agent], review this code against best practices"
→ Agent applies `@agent-os-global/standards/best-practices.md`

## Context Management

Agents maintain context using:
- `.agent-os/context/` - Session-specific context
- `.agent-os/specs/` - Created specifications
- `.agent-os/product/` - Product configuration

## Continuous Improvement

After each interaction:
1. Update agent knowledge if new patterns discovered
2. Refine workflows based on outcomes
3. Document lessons learned in team dynamics
4. Enhance cross-team protocols as needed
