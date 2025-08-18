"""
Agent data models for MyAI.

This module contains pydantic models for agent specifications,
metadata, and validation schemas.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Constants for validation
MAX_TAG_LENGTH = 50
MIN_CONTENT_LENGTH = 10


class AgentCategory(str, Enum):
    """Agent categories for organization."""

    ENGINEERING = "engineering"
    BUSINESS = "business"
    MARKETING = "marketing"
    FINANCE = "finance"
    LEGAL = "legal"
    SECURITY = "security"
    LEADERSHIP = "leadership"
    CUSTOM = "custom"


class AgentMetadata(BaseModel):
    """Metadata for agent specifications."""

    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    version: str = Field(default="1.0.0")
    category: AgentCategory
    tags: List[str] = Field(default_factory=list, max_length=20)
    tools: List[str] = Field(default_factory=list, max_length=50)
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=100000)
    requires: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    created: datetime = Field(default_factory=datetime.now)
    modified: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate agent name format."""
        # Must be a valid identifier-like string
        if not v.replace("_", "").replace("-", "").isalnum():
            msg = "Agent name must contain only alphanumeric characters, hyphens, and underscores"
            raise ValueError(msg)
        return v.lower()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate individual tags."""
        validated_tags = []
        for tag in v:
            if not tag or len(tag) > MAX_TAG_LENGTH:
                msg = f"Tags must be 1-{MAX_TAG_LENGTH} characters long"
                raise ValueError(msg)
            validated_tags.append(tag.lower())
        return validated_tags

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v):
        """Validate tool names."""
        valid_tools = ["claude", "cursor", "vscode", "terminal", "browser", "file_system"]
        validated_tools = []
        for tool in v:
            if tool not in valid_tools:
                # Allow custom tools but validate format
                if not tool.replace("_", "").replace("-", "").isalnum():
                    msg = "Tool names must be alphanumeric with hyphens/underscores"
                    raise ValueError(msg)
            validated_tools.append(tool.lower())
        return validated_tools


class AgentSpecification(BaseModel):
    """Complete agent specification including content."""

    metadata: AgentMetadata
    content: str = Field(..., min_length=10)
    file_path: Optional[Path] = None
    is_template: bool = False
    template_variables: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        """Validate agent content."""
        if len(v.strip()) < MIN_CONTENT_LENGTH:
            msg = f"Agent content must be at least {MIN_CONTENT_LENGTH} characters long"
            raise ValueError(msg)
        return v

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(cls, v):
        """Validate dependency names."""
        validated_deps = []
        for dep in v:
            if not dep.replace("_", "").replace("-", "").isalnum():
                msg = "Dependency names must be alphanumeric with hyphens/underscores"
                raise ValueError(msg)
            validated_deps.append(dep.lower())
        return validated_deps

    def get_frontmatter(self) -> Dict[str, Any]:
        """Extract frontmatter as dictionary."""
        return {
            "name": self.metadata.name,
            "display_name": self.metadata.display_name,
            "description": self.metadata.description,
            "version": self.metadata.version,
            "category": self.metadata.category.value,
            "tags": self.metadata.tags,
            "tools": self.metadata.tools,
            "model": self.metadata.model,
            "temperature": self.metadata.temperature,
            "max_tokens": self.metadata.max_tokens,
            "requires": self.metadata.requires,
            "author": self.metadata.author,
            "created": self.metadata.created.isoformat(),
            "modified": self.metadata.modified.isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert agent specification to markdown format."""
        frontmatter = self.get_frontmatter()

        # Build frontmatter section
        fm_lines = ["---"]
        for key, value in frontmatter.items():
            if value is not None:
                if isinstance(value, list):
                    if value:  # Only include non-empty lists
                        fm_lines.append(f"{key}: {value}")
                else:
                    fm_lines.append(f"{key}: {value}")
        fm_lines.append("---")

        # Combine frontmatter and content
        return "\n".join(fm_lines) + "\n\n" + self.content

    @classmethod
    def from_markdown(cls, content: str, file_path: Optional[Path] = None) -> "AgentSpecification":
        """Create agent specification from markdown content."""
        lines = content.split("\n")

        # Parse frontmatter
        if lines[0].strip() == "---":
            frontmatter_end = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    frontmatter_end = i
                    break

            if frontmatter_end is None:
                msg = "Invalid frontmatter: missing closing ---"
                raise ValueError(msg)

            # Extract frontmatter and content
            frontmatter_lines = lines[1:frontmatter_end]
            content_lines = lines[frontmatter_end + 1 :]

            # Parse frontmatter using YAML
            import yaml

            frontmatter_yaml = "\n".join(frontmatter_lines)
            try:
                frontmatter_dict = yaml.safe_load(frontmatter_yaml) or {}
            except yaml.YAMLError as e:
                msg = f"Invalid YAML in frontmatter: {e}"
                raise ValueError(msg) from e

            agent_content = "\n".join(content_lines).strip()
        else:
            # No frontmatter, use content as-is
            frontmatter_dict = {}
            agent_content = content.strip()

        # Create metadata from frontmatter
        metadata_dict = {
            "name": frontmatter_dict.get("name", "unnamed_agent"),
            "display_name": frontmatter_dict.get("display_name", "Unnamed Agent"),
            "description": frontmatter_dict.get("description", "No description provided"),
            "category": AgentCategory(frontmatter_dict.get("category", "custom")),
        }

        # Add optional fields if present
        for field in ["version", "tags", "tools", "model", "temperature", "max_tokens", "requires", "author"]:
            if field in frontmatter_dict:
                metadata_dict[field] = frontmatter_dict[field]

        # Parse datetime fields
        for field in ["created", "modified"]:
            if field in frontmatter_dict:
                value = frontmatter_dict[field]
                if isinstance(value, str):
                    metadata_dict[field] = datetime.fromisoformat(value)
                else:
                    metadata_dict[field] = value

        metadata = AgentMetadata(**metadata_dict)

        return cls(
            metadata=metadata,
            content=agent_content,
            file_path=file_path,
            is_template=frontmatter_dict.get("is_template", False),
            template_variables=frontmatter_dict.get("template_variables", {}),
            dependencies=frontmatter_dict.get("dependencies", []),
        )
