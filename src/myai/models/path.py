"""
Path and directory structure models for MyAI.

This module contains models for managing file paths, directory layouts,
and path resolution logic.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PathConfig(BaseModel):
    """Configuration for various file and directory paths."""

    # Core MyAI paths
    myai_home: Path = Field(default_factory=lambda: Path.home() / ".myai")
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "config")
    agents_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "agents")
    templates_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "templates")
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "cache")
    logs_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "logs")
    backups_dir: Path = Field(default_factory=lambda: Path.home() / ".myai" / "backups")

    # Tool-specific paths
    claude_config: Optional[Path] = Field(default_factory=lambda: Path.home() / ".claude")
    cursor_config: Optional[Path] = Field(default_factory=lambda: Path.home() / ".cursor")

    # Project-specific paths
    project_root: Optional[Path] = None
    project_config: Optional[Path] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        """Initialize with environment variable expansion."""
        super().__init__(**data)
        self._expand_paths()

    def _expand_paths(self):
        """Expand environment variables and user home in paths."""
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, Path):
                expanded = Path(os.path.expanduser(os.path.expandvars(str(field_value))))
                setattr(self, field_name, expanded)

    @field_validator("*", mode="before")
    @classmethod
    def validate_paths(cls, v):
        """Validate and convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v

    def resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve a path relative to MyAI home if not absolute."""
        path = Path(path)
        if path.is_absolute():
            return path
        return self.myai_home / path

    def get_config_path(self, level: str) -> Path:
        """Get configuration file path for a specific level."""
        level_map = {
            "global": self.config_dir / "global.json",
            "user": self.config_dir / "global.json",  # Same as global
            "project": self.project_config or Path.cwd() / ".myai" / "config.json",
        }

        if level in level_map:
            return level_map[level]

        # Handle team and enterprise configs
        if level.startswith("team."):
            team_name = level.split(".", 1)[1]
            return self.config_dir / "teams" / f"{team_name}.json"
        elif level.startswith("enterprise."):
            org_name = level.split(".", 1)[1]
            return self.config_dir / "enterprise" / f"{org_name}.json"

        msg = f"Unknown configuration level: {level}"
        raise ValueError(msg)

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.myai_home,
            self.config_dir,
            self.agents_dir,
            self.templates_dir,
            self.cache_dir,
            self.logs_dir,
            self.backups_dir,
            self.config_dir / "teams",
            self.config_dir / "enterprise",
            self.agents_dir / "default",
            self.agents_dir / "custom",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

            # Set secure permissions for sensitive directories
            if directory.name in ["config", "cache", "logs", "backups"]:
                directory.chmod(0o700)  # Owner read/write/execute only


class DirectoryLayout(BaseModel):
    """Represents the directory structure layout for MyAI."""

    name: str
    description: str
    structure: Dict[str, Union[str, Dict]] = Field(default_factory=dict)

    def create_structure(self, base_path: Path) -> List[Path]:
        """Create the directory structure at the given base path."""
        created_paths = []

        def create_recursive(current_path: Path, structure: Dict[str, Union[str, Dict]]):
            for name, content in structure.items():
                item_path = current_path / name

                if isinstance(content, dict):
                    # Directory
                    item_path.mkdir(parents=True, exist_ok=True)
                    created_paths.append(item_path)
                    create_recursive(item_path, content)
                else:
                    # File with content
                    item_path.parent.mkdir(parents=True, exist_ok=True)
                    if not item_path.exists():
                        item_path.write_text(content)
                        created_paths.append(item_path)

        create_recursive(base_path, self.structure)
        return created_paths

    @classmethod
    def get_default_layout(cls) -> "DirectoryLayout":
        """Get the default MyAI directory layout."""
        return cls(
            name="default",
            description="Default MyAI directory structure",
            structure={
                "config": {
                    "global.json": "{}",
                    "teams": {},
                    "enterprise": {},
                },
                "agents": {
                    "default": {
                        "engineering": {},
                        "business": {},
                        "marketing": {},
                        "finance": {},
                        "legal": {},
                        "security": {},
                        "leadership": {},
                    },
                    "custom": {},
                },
                "templates": {
                    "config.json": "{}",
                    "agent.md": "# Template Agent\n\nDescription here.",
                },
                "cache": {},
                "logs": {},
                "backups": {},
            },
        )

    @classmethod
    def get_project_layout(cls) -> "DirectoryLayout":
        """Get the project-specific directory layout."""
        return cls(
            name="project",
            description="Project-specific MyAI directory structure",
            structure={
                ".myai": {
                    "config.json": "{}",
                    "agents": {},
                    "overrides": {},
                }
            },
        )
