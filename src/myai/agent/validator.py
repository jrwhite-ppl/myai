"""
Agent validation for MyAI.

This module provides comprehensive validation for agent specifications,
including metadata validation, content checks, security validation, and more.
"""

import re
from typing import ClassVar, Dict, List, Optional, Set, Tuple

from myai.models.agent import AgentCategory, AgentSpecification
from myai.security.validation import ValidationError


class AgentValidationError(ValidationError):
    """Agent-specific validation error."""

    def __init__(self, message: str, field: Optional[str] = None, agent_name: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.agent_name = agent_name


class AgentValidator:
    """
    Comprehensive validator for agent specifications.

    Performs validation checks including:
    - Required field validation
    - Format validation
    - Content guidelines
    - Security checks
    - Tool compatibility
    - Dependency validation
    """

    # Content guidelines
    MIN_CONTENT_LENGTH = 50  # Minimum meaningful content
    MAX_CONTENT_LENGTH = 50000  # Maximum content size
    MIN_DESCRIPTION_LENGTH = 20
    MAX_DESCRIPTION_LENGTH = 500

    # Security patterns
    UNSAFE_PATTERNS: ClassVar[list[str]] = [
        r"__import__",  # Dynamic imports
        r"subprocess\.",  # Subprocess calls
        r"os\.system",  # System calls
        r"<script[^>]*>",  # Script tags
        r"javascript:",  # JavaScript URLs
        r"data:text/html",  # Data URLs with HTML
    ]

    # Valid tools
    VALID_TOOLS: ClassVar[set[str]] = {
        "claude",
        "cursor",
        "vscode",
        "terminal",
        "browser",
        "file_system",
        "git",
        "docker",
        "kubernetes",
        "aws",
    }

    # Content quality patterns
    QUALITY_INDICATORS: ClassVar[dict[str, str]] = {
        "has_sections": r"^#{1,3}\s+.+$",  # Markdown headers
        "has_lists": r"^[\*\-\+]\s+.+$",  # Bullet points
        "has_guidelines": r"(guideline|principle|rule|best practice)",  # Guidelines
        "has_instructions": r"(should|must|remember|ensure|follow)",  # Instructions
    }

    def __init__(self, *, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: Enable strict validation rules
        """
        self.strict_mode = strict_mode

    def validate_agent(
        self,
        agent: AgentSpecification,
        *,
        validate_dependencies: bool = True,
        existing_agents: Optional[Set[str]] = None,
    ) -> List[AgentValidationError]:
        """
        Perform comprehensive agent validation.

        Args:
            agent: Agent specification to validate
            validate_dependencies: Whether to validate dependencies
            existing_agents: Set of existing agent names for dependency validation

        Returns:
            List of validation errors
        """
        errors = []

        # Metadata validation
        errors.extend(self._validate_metadata(agent))

        # Content validation
        errors.extend(self._validate_content(agent))

        # Security validation
        errors.extend(self._validate_security(agent))

        # Tool validation
        errors.extend(self._validate_tools(agent))

        # Dependency validation
        if validate_dependencies and agent.dependencies:
            errors.extend(self._validate_dependencies(agent, existing_agents))

        # Quality validation (in strict mode)
        if self.strict_mode:
            errors.extend(self._validate_quality(agent))

        return errors

    def _validate_metadata(self, agent: AgentSpecification) -> List[AgentValidationError]:
        """Validate agent metadata."""
        errors = []
        metadata = agent.metadata

        # Name validation
        if not re.match(r"^[a-z0-9][a-z0-9\-_]*[a-z0-9]$", metadata.name):
            errors.append(
                AgentValidationError(
                    "Agent name must start and end with alphanumeric, contain only lowercase letters, numbers, hyphens,"
                    " and underscores",
                    field="name",
                    agent_name=metadata.name,
                )
            )

        min_name_length = 3
        if len(metadata.name) < min_name_length:
            errors.append(
                AgentValidationError(
                    f"Agent name must be at least {min_name_length} characters long",
                    field="name",
                    agent_name=metadata.name,
                )
            )

        max_name_length = 50
        if len(metadata.name) > max_name_length:
            errors.append(
                AgentValidationError(
                    f"Agent name must not exceed {max_name_length} characters",
                    field="name",
                    agent_name=metadata.name,
                )
            )

        # Display name validation
        if not metadata.display_name.strip():
            errors.append(
                AgentValidationError(
                    "Display name cannot be empty",
                    field="display_name",
                    agent_name=metadata.name,
                )
            )

        max_display_name_length = 100
        if len(metadata.display_name) > max_display_name_length:
            errors.append(
                AgentValidationError(
                    f"Display name must not exceed {max_display_name_length} characters",
                    field="display_name",
                    agent_name=metadata.name,
                )
            )

        # Description validation
        if len(metadata.description) < self.MIN_DESCRIPTION_LENGTH:
            errors.append(
                AgentValidationError(
                    f"Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters",
                    field="description",
                    agent_name=metadata.name,
                )
            )

        if len(metadata.description) > self.MAX_DESCRIPTION_LENGTH:
            errors.append(
                AgentValidationError(
                    f"Description must not exceed {self.MAX_DESCRIPTION_LENGTH} characters",
                    field="description",
                    agent_name=metadata.name,
                )
            )

        # Version validation
        if not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$", metadata.version):
            errors.append(
                AgentValidationError(
                    "Version must follow semantic versioning (e.g., 1.0.0 or 1.0.0-beta)",
                    field="version",
                    agent_name=metadata.name,
                )
            )

        # Tag validation
        for tag in metadata.tags:
            if not re.match(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$", tag):
                errors.append(
                    AgentValidationError(
                        f"Invalid tag '{tag}': must be lowercase alphanumeric with hyphens",
                        field="tags",
                        agent_name=metadata.name,
                    )
                )

            max_tag_length = 30
            if len(tag) > max_tag_length:
                errors.append(
                    AgentValidationError(
                        f"Tag '{tag}' exceeds maximum length of {max_tag_length} characters",
                        field="tags",
                        agent_name=metadata.name,
                    )
                )

        # Model parameters validation
        if metadata.temperature is not None:
            min_temperature = 0.0
            max_temperature = 2.0
            if metadata.temperature < min_temperature or metadata.temperature > max_temperature:
                errors.append(
                    AgentValidationError(
                        f"Temperature must be between {min_temperature} and {max_temperature}",
                        field="temperature",
                        agent_name=metadata.name,
                    )
                )

        if metadata.max_tokens is not None:
            min_tokens = 1
            max_tokens = 100000
            if metadata.max_tokens < min_tokens or metadata.max_tokens > max_tokens:
                errors.append(
                    AgentValidationError(
                        f"Max tokens must be between {min_tokens} and {max_tokens}",
                        field="max_tokens",
                        agent_name=metadata.name,
                    )
                )

        return errors

    def _validate_content(self, agent: AgentSpecification) -> List[AgentValidationError]:
        """Validate agent content."""
        errors = []
        content = agent.content.strip()

        # Length validation
        if len(content) < self.MIN_CONTENT_LENGTH:
            errors.append(
                AgentValidationError(
                    f"Content must be at least {self.MIN_CONTENT_LENGTH} characters",
                    field="content",
                    agent_name=agent.metadata.name,
                )
            )

        if len(content) > self.MAX_CONTENT_LENGTH:
            errors.append(
                AgentValidationError(
                    f"Content exceeds maximum length of {self.MAX_CONTENT_LENGTH} characters",
                    field="content",
                    agent_name=agent.metadata.name,
                )
            )

        # Check for placeholder content
        placeholder_patterns = [
            r"^\s*TODO\s*$",
            r"^\s*TBD\s*$",
            r"^\s*\[placeholder\]\s*$",
            r"^\s*Lorem ipsum",
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                errors.append(
                    AgentValidationError(
                        "Content contains placeholder text",
                        field="content",
                        agent_name=agent.metadata.name,
                    )
                )
                break

        return errors

    def _validate_security(self, agent: AgentSpecification) -> List[AgentValidationError]:
        """Validate agent security."""
        errors = []
        content = agent.content

        # Check for unsafe patterns
        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                errors.append(
                    AgentValidationError(
                        f"Content contains potentially unsafe pattern: {pattern}",
                        field="content",
                        agent_name=agent.metadata.name,
                    )
                )

        # Check for exposed secrets patterns
        secret_patterns = [
            r'["\']?[Aa][Pp][Ii][_-]?[Kk][Ee][Yy]["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'["\']?[Ss][Ee][Cc][Rr][Ee][Tt]["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'["\']?[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd]["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r'["\']?[Tt][Oo][Kk][Ee][Nn]["\']?\s*[:=]\s*["\'][^"\']+["\']',
            r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY",
        ]

        for pattern in secret_patterns:
            if re.search(pattern, content):
                errors.append(
                    AgentValidationError(
                        "Content may contain exposed secrets or credentials",
                        field="content",
                        agent_name=agent.metadata.name,
                    )
                )
                break

        # Check for external URLs (potential data exfiltration)
        if self.strict_mode:
            url_pattern = r"https?://[^\s/$.?#].[^\s]*"
            urls = re.findall(url_pattern, content)

            # Allow some common documentation URLs
            allowed_domains = ["github.com", "docs.python.org", "stackoverflow.com"]

            for url in urls:
                if not any(domain in url for domain in allowed_domains):
                    errors.append(
                        AgentValidationError(
                            f"Content contains external URL: {url}",
                            field="content",
                            agent_name=agent.metadata.name,
                        )
                    )

        return errors

    def _validate_tools(self, agent: AgentSpecification) -> List[AgentValidationError]:
        """Validate agent tools."""
        errors = []

        for tool in agent.metadata.tools:
            if tool not in self.VALID_TOOLS:
                # Check if it's a valid custom tool format
                if not re.match(r"^[a-z][a-z0-9_-]*$", tool):
                    errors.append(
                        AgentValidationError(
                            f"Invalid tool name '{tool}': must be lowercase alphanumeric with hyphens/underscores",
                            field="tools",
                            agent_name=agent.metadata.name,
                        )
                    )
                elif self.strict_mode:
                    errors.append(
                        AgentValidationError(
                            f"Unknown tool '{tool}' (not in standard tool list)",
                            field="tools",
                            agent_name=agent.metadata.name,
                        )
                    )

        # Check for tool compatibility
        incompatible_pairs = [
            ("cursor", "vscode"),  # Can't use both editors
        ]

        for tool1, tool2 in incompatible_pairs:
            if tool1 in agent.metadata.tools and tool2 in agent.metadata.tools:
                errors.append(
                    AgentValidationError(
                        f"Incompatible tools: {tool1} and {tool2}",
                        field="tools",
                        agent_name=agent.metadata.name,
                    )
                )

        return errors

    def _validate_dependencies(
        self,
        agent: AgentSpecification,
        existing_agents: Optional[Set[str]] = None,
    ) -> List[AgentValidationError]:
        """Validate agent dependencies."""
        errors = []

        for dep in agent.dependencies:
            # Format validation
            if not re.match(r"^[a-z0-9][a-z0-9\-_]*[a-z0-9]$", dep):
                errors.append(
                    AgentValidationError(
                        f"Invalid dependency name '{dep}': must follow agent naming rules",
                        field="dependencies",
                        agent_name=agent.metadata.name,
                    )
                )

            # Self-dependency check
            if dep == agent.metadata.name:
                errors.append(
                    AgentValidationError(
                        "Agent cannot depend on itself",
                        field="dependencies",
                        agent_name=agent.metadata.name,
                    )
                )

            # Existence check
            if existing_agents and dep not in existing_agents:
                errors.append(
                    AgentValidationError(
                        f"Dependency '{dep}' does not exist",
                        field="dependencies",
                        agent_name=agent.metadata.name,
                    )
                )

        return errors

    def _validate_quality(self, agent: AgentSpecification) -> List[AgentValidationError]:
        """Validate content quality (strict mode only)."""
        errors = []
        content = agent.content

        # Check for quality indicators
        quality_issues = []

        # Check for sections
        if not re.search(self.QUALITY_INDICATORS["has_sections"], content, re.MULTILINE):
            quality_issues.append("missing section headers")

        # Check for lists
        if not re.search(self.QUALITY_INDICATORS["has_lists"], content, re.MULTILINE):
            quality_issues.append("missing structured lists")

        # Check for guidelines
        if not re.search(self.QUALITY_INDICATORS["has_guidelines"], content, re.IGNORECASE):
            quality_issues.append("missing guidelines or principles")

        # Check for instructions
        if not re.search(self.QUALITY_INDICATORS["has_instructions"], content, re.IGNORECASE):
            quality_issues.append("missing clear instructions")

        if quality_issues:
            errors.append(
                AgentValidationError(
                    f"Content quality issues: {', '.join(quality_issues)}",
                    field="content",
                    agent_name=agent.metadata.name,
                )
            )

        # Check for appropriate length based on category
        if agent.metadata.category == AgentCategory.ENGINEERING:
            min_engineering_content_length = 500
            if len(content) < min_engineering_content_length:
                errors.append(
                    AgentValidationError(
                        f"Engineering agents should have more detailed content ({min_engineering_content_length}+"
                        " characters)",
                        field="content",
                        agent_name=agent.metadata.name,
                    )
                )

        return errors

    def validate_batch(
        self,
        agents: List[AgentSpecification],
        *,
        check_circular_deps: bool = True,
    ) -> Dict[str, List[AgentValidationError]]:
        """
        Validate multiple agents together.

        Args:
            agents: List of agents to validate
            check_circular_deps: Whether to check for circular dependencies

        Returns:
            Dictionary mapping agent names to their validation errors
        """
        results = {}
        agent_names = {agent.metadata.name for agent in agents}

        # Validate each agent
        for agent in agents:
            errors = self.validate_agent(agent, existing_agents=agent_names)
            if errors:
                results[agent.metadata.name] = errors

        # Check for circular dependencies
        if check_circular_deps:
            circular_errors = self._check_circular_dependencies(agents)
            for agent_name, error in circular_errors:
                if agent_name not in results:
                    results[agent_name] = []
                results[agent_name].append(error)

        return results

    def _check_circular_dependencies(
        self,
        agents: List[AgentSpecification],
    ) -> List[Tuple[str, AgentValidationError]]:
        """Check for circular dependencies among agents."""
        errors = []

        # Build dependency graph
        deps_graph = {agent.metadata.name: set(agent.dependencies) for agent in agents}

        # Check each agent for circular dependencies
        for agent in agents:
            visited: Set[str] = set()
            path: List[str] = []

            if self._has_circular_dep(agent.metadata.name, deps_graph, visited, path):
                cycle = " -> ".join([*path, agent.metadata.name])
                errors.append(
                    (
                        agent.metadata.name,
                        AgentValidationError(
                            f"Circular dependency detected: {cycle}",
                            field="dependencies",
                            agent_name=agent.metadata.name,
                        ),
                    )
                )

        return errors

    def _has_circular_dep(
        self,
        node: str,
        graph: Dict[str, Set[str]],
        visited: Set[str],
        path: List[str],
    ) -> bool:
        """Helper to detect circular dependencies."""
        if node in path:
            return True

        if node in visited:
            return False

        visited.add(node)
        path.append(node)

        for dep in graph.get(node, set()):
            if self._has_circular_dep(dep, graph, visited, path):
                return True

        path.pop()
        return False

    def suggest_fixes(
        self,
        errors: List[AgentValidationError],
    ) -> Dict[str, List[str]]:
        """
        Suggest fixes for validation errors.

        Args:
            errors: List of validation errors

        Returns:
            Dictionary mapping error messages to suggested fixes
        """
        suggestions = {}

        for error in errors:
            error_key = str(error)

            if "must start and end with alphanumeric" in str(error):
                suggestions[error_key] = [
                    "Use lowercase letters, numbers, hyphens, and underscores only",
                    "Ensure the name starts and ends with a letter or number",
                    "Example: 'my-agent-name' or 'agent_123'",
                ]
            elif "must be at least" in str(error) and "characters" in str(error):
                suggestions[error_key] = [
                    "Add more descriptive content",
                    "Include specific guidelines and instructions",
                    "Provide clear examples and use cases",
                ]
            elif "placeholder text" in str(error):
                suggestions[error_key] = [
                    "Replace placeholder text with actual content",
                    "Provide specific agent instructions",
                    "Remove TODO/TBD markers",
                ]
            elif "unsafe pattern" in str(error):
                suggestions[error_key] = [
                    "Remove code execution patterns",
                    "Use safe alternatives for dynamic operations",
                    "Follow security best practices",
                ]
            elif "exposed secrets" in str(error):
                suggestions[error_key] = [
                    "Remove hardcoded credentials",
                    "Use environment variables for secrets",
                    "Reference credential management tools instead",
                ]
            elif "circular dependency" in str(error):
                suggestions[error_key] = [
                    "Review and restructure agent dependencies",
                    "Remove unnecessary dependencies",
                    "Consider creating a base agent without dependencies",
                ]

        return suggestions
