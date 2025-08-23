"""
Models for AGENTS.md file management.
"""

from datetime import datetime
from pathlib import Path
from typing import ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentsMdEntry(BaseModel):
    """Registry entry for an AGENTS.md file."""

    path: Path
    enabled: bool = True
    type: Literal["root", "subdirectory"] = "subdirectory"
    agents: List[str] = Field(default_factory=list)
    inherits_from: Optional[Path] = None
    last_modified: datetime
    checksum: str

    class Config:
        """Pydantic configuration."""

        json_encoders: ClassVar[Dict] = {
            Path: str,
            datetime: lambda v: v.isoformat(),
        }


class AgentsMdRegistry(BaseModel):
    """Registry of all AGENTS.md files across multiple projects."""

    version: str = "1.0.0"
    projects: Dict[str, "ProjectRegistry"] = Field(default_factory=dict)
    default_agents: List[str] = Field(
        default_factory=lambda: [
            "lead-developer",
            "systems-architect",
            "security-analyst",
            "devops-engineer",
            "technical-writer",
        ]
    )

    def get_project_registry(self, project_root: Path) -> "ProjectRegistry":
        """Get or create a project registry."""
        project_key = str(project_root)
        if project_key not in self.projects:
            self.projects[project_key] = ProjectRegistry(project_root=project_root)
        return self.projects[project_key]


class ProjectRegistry(BaseModel):
    """Registry for a single project's AGENTS.md files."""

    project_root: Path
    files: List[AgentsMdEntry] = Field(default_factory=list)

    class Config:
        """Pydantic configuration."""

        json_encoders: ClassVar[Dict] = {
            Path: str,
        }

    def get_entry(self, path: Path) -> Optional[AgentsMdEntry]:
        """Get entry for a specific path."""
        for entry in self.files:
            if entry.path == path:
                return entry
        return None

    def add_entry(self, entry: AgentsMdEntry) -> None:
        """Add or update an entry."""
        existing = self.get_entry(entry.path)
        if existing:
            self.files.remove(existing)
        self.files.append(entry)

    def remove_entry(self, path: Path) -> bool:
        """Remove an entry by path."""
        entry = self.get_entry(path)
        if entry:
            self.files.remove(entry)
            return True
        return False

    def get_enabled_files(self) -> List[AgentsMdEntry]:
        """Get all enabled AGENTS.md files."""
        return [entry for entry in self.files if entry.enabled]

    def get_root_entry(self) -> Optional[AgentsMdEntry]:
        """Get the root AGENTS.md entry."""
        for entry in self.files:
            if entry.type == "root":
                return entry
        return None
