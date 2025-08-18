"""
Agent template management for MyAI.

This module provides template creation, management, and instantiation
for agent specifications, including default templates and variable substitution.
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional, Set

from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification
from myai.storage.agent import AgentStorage
from myai.storage.filesystem import FileSystemStorage

# Default template variables
DEFAULT_TEMPLATE_VARS = {
    "author": "MyAI User",
    "version": "1.0.0",
    "model": "claude-3-sonnet",
    "temperature": "0.7",
    "max_tokens": "4096",
}


class AgentTemplate:
    """
    Represents an agent template with variable substitution support.

    Templates use Python's string.Template syntax for variables:
    - $variable or ${variable} for simple substitution
    - $$ for literal $ character
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        category: AgentCategory,
        description: str,
        content_template: str,
        default_variables: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        *,
        is_system: bool = False,
    ):
        """
        Initialize agent template.

        Args:
            name: Template name (kebab-case)
            display_name: Human-readable name
            category: Template category
            description: Template description
            content_template: Template content with variables
            default_variables: Default variable values
            tools: Recommended tools
            tags: Template tags
            is_system: Whether this is a system template
        """
        self.name = name
        self.display_name = display_name
        self.category = category
        self.description = description
        self.content_template = content_template
        self.default_variables = default_variables or {}
        self.tools = tools or []
        self.tags = tags or []
        self.is_system = is_system

        # Extract variables from template
        self.required_variables = self._extract_variables()

    def _extract_variables(self) -> Set[str]:
        """Extract variable names from template content."""
        # First, temporarily replace $$ with a placeholder to avoid false matches
        temp_content = self.content_template.replace("$$", "\x00")

        # Use regex to find $variable or ${variable} patterns
        pattern = r"\$(?:(\w+)|\{(\w+)\})"
        matches = re.findall(pattern, temp_content)

        # Flatten the tuples and filter out empty strings
        variables = set()
        for match in matches:
            var = match[0] or match[1]
            if var:
                variables.add(var)

        return variables

    def validate_variables(self, variables: Dict[str, Any]) -> List[str]:
        """
        Validate provided variables against template requirements.

        Returns:
            List of missing required variables
        """
        provided = set(variables.keys())
        defaults = set(self.default_variables.keys())
        required = self.required_variables - defaults

        missing = list(required - provided)
        return missing

    def render(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> AgentSpecification:
        """
        Render template into an agent specification.

        Args:
            name: Agent name
            display_name: Agent display name
            description: Agent description (uses template description if None)
            variables: Template variables
            tools: Agent tools (uses template tools if None)
            tags: Agent tags (uses template tags if None)

        Returns:
            Rendered agent specification

        Raises:
            ValueError: If required variables are missing
        """
        # Merge variables with defaults
        all_vars = {**DEFAULT_TEMPLATE_VARS, **self.default_variables}
        if variables:
            all_vars.update(variables)

        # Validate variables
        missing = self.validate_variables(all_vars)
        if missing:
            msg = f"Missing required variables: {', '.join(missing)}"
            raise ValueError(msg)

        # Render content
        template = Template(self.content_template)
        rendered_content = template.safe_substitute(all_vars)

        # Create metadata
        metadata = AgentMetadata(
            name=name,
            display_name=display_name,
            description=description or self.description,
            category=self.category,
            tools=tools or self.tools,
            tags=tags or self.tags,
            version=all_vars.get("version", "1.0.0"),
            model=all_vars.get("model"),
            temperature=float(all_vars.get("temperature", 0.7)) if all_vars.get("temperature") else None,
            max_tokens=int(all_vars.get("max_tokens", 4096)) if all_vars.get("max_tokens") else None,
            author=all_vars.get("author"),
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

        # Create specification
        return AgentSpecification(
            metadata=metadata,
            content=rendered_content,
            is_template=False,
            template_variables={},
        )

    def to_specification(self) -> AgentSpecification:
        """Convert template to agent specification for storage."""
        metadata = AgentMetadata(
            name=f"template-{self.name}",
            display_name=f"Template: {self.display_name}",
            description=self.description,
            category=self.category,
            tools=self.tools,
            tags=[*self.tags, "template"],
            temperature=0.7,  # Default temperature for templates
            max_tokens=4096,  # Default max tokens for templates
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

        return AgentSpecification(
            metadata=metadata,
            content=self.content_template,
            is_template=True,
            template_variables=self.default_variables,
        )


class TemplateRegistry:
    """
    Registry for agent templates.

    Manages system templates and user-defined templates,
    providing discovery, registration, and retrieval operations.
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        *,
        auto_discover: bool = True,
    ):
        """
        Initialize template registry.

        Args:
            base_path: Base path for template storage
            auto_discover: Whether to auto-discover templates
        """
        self.base_path = base_path or Path.home() / ".myai"
        self._templates: Dict[str, AgentTemplate] = {}
        self._system_templates: Dict[str, AgentTemplate] = {}

        # Storage setup
        self._storage = FileSystemStorage(self.base_path)
        self._agent_storage = AgentStorage(self._storage)

        # Register default templates
        self._register_default_templates()

        # Discover user templates
        if auto_discover:
            self.discover_templates()

    def _register_default_templates(self) -> None:
        """Register default system templates."""
        # Engineering template
        self.register_template(
            AgentTemplate(
                name="engineering-base",
                display_name="Engineering Base",
                category=AgentCategory.ENGINEERING,
                description="Base template for engineering agents focused on coding and architecture",
                content_template="""You are ${agent_role}, an engineering specialist focused on ${specialty}.

## Core Competencies
- Software architecture and design patterns
- Code quality and best practices
- Performance optimization
- Security considerations
- Testing strategies

## Working Style
- Clear, concise communication
- Evidence-based recommendations
- Practical, implementable solutions
- Focus on maintainability and scalability

## Tools and Technologies
${tools_list}

## Specific Guidelines
${guidelines}

Remember to:
- Prioritize code quality and maintainability
- Consider performance implications
- Follow security best practices
- Write comprehensive tests
- Document your decisions""",
                default_variables={
                    "agent_role": "an expert engineer",
                    "specialty": "software development",
                    "tools_list": (
                        "- Modern programming languages\n- Development frameworks\n- Testing tools\n- CI/CD pipelines"
                    ),
                    "guidelines": (
                        "- Follow SOLID principles\n- Use appropriate design patterns\n- Write clean, readable code"
                    ),
                },
                tools=["claude", "cursor", "terminal"],
                tags=["engineering", "development", "template"],
                is_system=True,
            )
        )

        # Business template
        self.register_template(
            AgentTemplate(
                name="business-analyst",
                display_name="Business Analyst",
                category=AgentCategory.BUSINESS,
                description="Template for business analysis and strategy agents",
                content_template="""You are ${agent_role}, a business specialist focused on ${specialty}.

## Core Competencies
- Business analysis and strategy
- Market research and insights
- Financial analysis
- Process optimization
- Stakeholder management

## Analytical Framework
${framework}

## Key Metrics
${metrics}

## Communication Style
- Executive-ready summaries
- Data-driven insights
- Clear recommendations
- Risk assessment

Remember to:
- Base recommendations on data
- Consider all stakeholders
- Assess risks and opportunities
- Provide actionable insights""",
                default_variables={
                    "agent_role": "a senior business analyst",
                    "specialty": "strategic planning and analysis",
                    "framework": (
                        "- SWOT analysis\n- Porter's Five Forces\n- Value chain analysis\n- Cost-benefit analysis"
                    ),
                    "metrics": (
                        "- ROI and profitability\n- Market share\n- Customer satisfaction\n- Operational efficiency"
                    ),
                },
                tools=["claude", "browser"],
                tags=["business", "analysis", "strategy", "template"],
                is_system=True,
            )
        )

        # Security template
        self.register_template(
            AgentTemplate(
                name="security-expert",
                display_name="Security Expert",
                category=AgentCategory.SECURITY,
                description="Template for security analysis and implementation agents",
                content_template="""You are ${agent_role}, a security specialist focused on ${specialty}.

## Security Domains
- Application security
- Infrastructure security
- Data protection
- Compliance and governance
- Incident response

## Security Framework
${framework}

## Key Responsibilities
${responsibilities}

## Tools and Techniques
${tools}

Remember to:
- Follow the principle of least privilege
- Defense in depth approach
- Regular security assessments
- Compliance with regulations
- Incident response preparedness""",
                default_variables={
                    "agent_role": "a cybersecurity expert",
                    "specialty": "comprehensive security assessment and implementation",
                    "framework": (
                        "- OWASP Top 10\n- NIST Cybersecurity Framework\n- ISO 27001\n- Zero Trust Architecture"
                    ),
                    "responsibilities": (
                        "- Vulnerability assessment\n- Security architecture review\n"
                        "- Compliance auditing\n- Incident response planning"
                    ),
                    "tools": (
                        "- Static analysis tools\n- Penetration testing\n- Security monitoring\n- Encryption"
                        " technologies"
                    ),
                },
                tools=["claude", "terminal"],
                tags=["security", "compliance", "protection", "template"],
                is_system=True,
            )
        )

        # Custom template
        self.register_template(
            AgentTemplate(
                name="custom-specialist",
                display_name="Custom Specialist",
                category=AgentCategory.CUSTOM,
                description="Flexible template for specialized agents",
                content_template="""You are ${agent_role}, specializing in ${specialty}.

## Overview
${overview}

## Core Principles
${principles}

## Methodology
${methodology}

## Success Criteria
${success_criteria}

Remember to maintain focus on your specialized domain while collaborating effectively with other agents.""",
                default_variables={
                    "agent_role": "a specialized expert",
                    "specialty": "your domain of expertise",
                    "overview": "Provide a brief overview of your specialization",
                    "principles": "List the key principles that guide your work",
                    "methodology": "Describe your approach and methodology",
                    "success_criteria": "Define what success looks like in your domain",
                },
                tools=["claude"],
                tags=["custom", "specialist", "template"],
                is_system=True,
            )
        )

    def register_template(
        self,
        template: AgentTemplate,
        *,
        persist: bool = True,
    ) -> None:
        """
        Register a template in the registry.

        Args:
            template: Template to register
            persist: Whether to persist to storage
        """
        if template.is_system:
            self._system_templates[template.name] = template
        else:
            self._templates[template.name] = template

            if persist:
                # Save as agent specification
                spec = template.to_specification()
                self._agent_storage.save_agent(spec)

    def get_template(self, name: str) -> Optional[AgentTemplate]:
        """Get template by name."""
        # Check user templates first
        if name in self._templates:
            return self._templates[name]

        # Check system templates
        return self._system_templates.get(name)

    def list_templates(
        self,
        category: Optional[AgentCategory] = None,
        *,
        include_system: bool = True,
    ) -> List[AgentTemplate]:
        """List available templates."""
        templates: List[AgentTemplate] = []

        # Add user templates
        templates.extend(self._templates.values())

        # Add system templates if requested
        if include_system:
            templates.extend(self._system_templates.values())

        # Filter by category if specified
        if category:
            templates = [t for t in templates if t.category == category]

        return sorted(templates, key=lambda t: t.name)

    def discover_templates(self) -> List[str]:
        """Discover templates from storage."""
        discovered = []

        # Search for template agents
        agent_names = self._agent_storage.list_agents()

        for agent_name in agent_names:
            # Load the agent specification
            agent = self._agent_storage.load_agent(agent_name)
            if agent and agent.is_template and not agent.metadata.name.startswith("template-"):
                # Convert to template
                template = AgentTemplate(
                    name=agent.metadata.name,
                    display_name=agent.metadata.display_name,
                    category=agent.metadata.category,
                    description=agent.metadata.description,
                    content_template=agent.content,
                    default_variables=agent.template_variables,
                    tools=agent.metadata.tools,
                    tags=[tag for tag in agent.metadata.tags if tag != "template"],
                    is_system=False,
                )

                self._templates[template.name] = template
                discovered.append(template.name)

        return discovered

    def create_from_agent(
        self,
        agent: AgentSpecification,
        template_name: str,
        variables_to_extract: Optional[List[str]] = None,
    ) -> AgentTemplate:
        """
        Create a template from an existing agent.

        Args:
            agent: Source agent specification
            template_name: Name for the new template
            variables_to_extract: Variable names to extract as template variables

        Returns:
            Created template
        """
        # Extract variables from content if specified
        content = agent.content
        default_vars = {}

        if variables_to_extract:
            for var_name in variables_to_extract:
                # Simple extraction - could be enhanced
                placeholder = f"${{{var_name}}}"
                default_vars[var_name] = f"[{var_name} value]"

                # Replace first occurrence as example
                # In practice, this would be more sophisticated
                content = content.replace(f"[{var_name} value]", placeholder, 1)

        # Create template
        template = AgentTemplate(
            name=template_name,
            display_name=f"Template: {agent.metadata.display_name}",
            category=agent.metadata.category,
            description=f"Template based on {agent.metadata.name}",
            content_template=content,
            default_variables=default_vars,
            tools=agent.metadata.tools,
            tags=[*agent.metadata.tags, "user-template"],
            is_system=False,
        )

        # Register template
        self.register_template(template)

        return template

    def delete_template(self, name: str) -> bool:
        """
        Delete a user template.

        Args:
            name: Template name

        Returns:
            True if deleted, False if not found or system template
        """
        if name in self._system_templates:
            msg = f"Cannot delete system template: {name}"
            raise ValueError(msg)

        if name in self._templates:
            del self._templates[name]

            # Remove from storage
            self._agent_storage.delete_agent(f"template-{name}")

            return True

        return False


# Convenience function
def get_template_registry() -> TemplateRegistry:
    """Get the default template registry instance."""
    return TemplateRegistry()
