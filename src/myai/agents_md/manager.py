"""
Manager for AGENTS.md files in a project.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from myai.agent.registry import get_agent_registry
from myai.agents_md.templates import TEMPLATES
from myai.config.manager import get_config_manager
from myai.models.agents_md import AgentsMdEntry, AgentsMdRegistry

console = Console()


class AgentsMdManager:
    """Manage AGENTS.md files in a project."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the manager."""
        self.project_root = project_root or Path.cwd()
        self.registry_path = self.project_root / ".myai" / "agents-md-registry.json"
        self.registry = self._load_registry()

    def _load_registry(self) -> AgentsMdRegistry:
        """Load the registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, encoding="utf-8") as f:
                    data = json.load(f)
                    return AgentsMdRegistry(**data)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not load registry: {e}[/yellow]")

        # Create new registry
        return AgentsMdRegistry(project_root=self.project_root)

    def _save_registry(self) -> None:
        """Save the registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.registry.model_dump(), f, indent=2, default=str)

    def _calculate_checksum(self, path: Path) -> str:
        """Calculate checksum of a file."""
        if not path.exists():
            return ""
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _is_ignored(self, path: Path) -> bool:
        """Check if path should be ignored."""
        ignore_patterns = ["node_modules", "venv", ".venv", "dist", "build", "__pycache__"]
        return any(pattern in path.parts for pattern in ignore_patterns)

    def discover(self) -> List[Path]:
        """Discover all AGENTS.md files in the project."""
        agents_md_files = []

        for agents_md in self.project_root.rglob("AGENTS.md"):
            # Skip hidden directories (except .myai)
            parts = agents_md.parts[len(self.project_root.parts) : -1]
            if any(part.startswith(".") and part != ".myai" for part in parts):
                continue

            if not self._is_ignored(agents_md):
                agents_md_files.append(agents_md)

        return sorted(agents_md_files)

    def sync_registry(self) -> None:
        """Sync registry with discovered files."""
        discovered = self.discover()

        # Add new files to registry
        for path in discovered:
            if not self.registry.get_entry(path):
                entry = AgentsMdEntry(
                    path=path,
                    enabled=True,
                    type="root" if path == self.project_root / "AGENTS.md" else "subdirectory",
                    last_modified=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                    checksum=self._calculate_checksum(path),
                )

                # Check for inheritance
                if entry.type == "subdirectory":
                    parent_path = path.parent
                    while parent_path != self.project_root:
                        potential_parent = parent_path / "AGENTS.md"
                        if potential_parent.exists() and potential_parent != path:
                            entry.inherits_from = potential_parent
                            break
                        parent_path = parent_path.parent

                self.registry.add_entry(entry)

        # Remove deleted files from registry
        registry_paths = {entry.path for entry in self.registry.files}
        for path in registry_paths:
            if path not in discovered:
                self.registry.remove_entry(path)

        self._save_registry()

    def list_files(self) -> List[AgentsMdEntry]:
        """List all AGENTS.md files with their status."""
        self.sync_registry()
        return self.registry.files

    def create(self, path: Path, template: str = "root", *, force: bool = False) -> None:
        """Create a new AGENTS.md file."""
        if path.exists() and not force:
            msg = f"AGENTS.md already exists at {path}"
            raise FileExistsError(msg)

        # Get template
        content = TEMPLATES.get(template, TEMPLATES["root"])

        # Customize template
        content = self._customize_template(content, path, template)

        # Write file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        # Add to registry
        entry = AgentsMdEntry(
            path=path,
            enabled=True,
            type="root" if path == self.project_root / "AGENTS.md" else "subdirectory",
            agents=self._extract_agents_from_content(content),
            last_modified=datetime.now(timezone.utc),
            checksum=self._calculate_checksum(path),
        )

        self.registry.add_entry(entry)
        self._save_registry()

    def update_agents_section(self, path: Path) -> None:
        """Update only the agents section of an AGENTS.md file, preserving user content."""
        from myai.utils.content_manager import ContentMarkerManager

        if not path.exists():
            return

        # Use content marker manager
        manager = ContentMarkerManager(marker_prefix="MYAI", comment_style="markdown")

        # Generate the new agents section content
        agent_sections = self._generate_agent_sections()

        # Update just the AGENTS section
        # This will raise ValueError if markers are broken
        manager.read_and_update_file(path, "AGENTS", agent_sections)

    def _customize_template(self, template: str, path: Path, template_type: str) -> str:  # noqa: ARG002
        """Customize template with project-specific information."""
        replacements = {
            "{project_name}": self.project_root.name,
            "{install_command}": "uv sync",
            "{dev_command}": "uv run python -m myai",
            "{test_command}": "uv run pytest",
            "{build_command}": "uv build",
        }

        # Add agent sections for root template
        if template_type == "root":
            agent_sections = self._generate_agent_sections()
            replacements["{agent_sections}"] = agent_sections

        # Apply replacements
        for key, value in replacements.items():
            template = template.replace(key, value)

        return template

    def _generate_agent_sections(self) -> str:
        """Generate agent sections for root AGENTS.md."""
        config = get_config_manager().get_config()
        registry = get_agent_registry()

        # Get enabled agents
        enabled_names = config.agents.enabled + getattr(config.agents, "global_enabled", [])
        if not enabled_names:
            enabled_names = self.registry.default_agents

        sections = []
        for agent_name in enabled_names:
            agent = registry.get_agent(agent_name)
            if agent:
                category = agent.metadata.category.value
                section = f"""### {agent.metadata.display_name} (@myai/agents/{category}/{agent_name})
{agent.metadata.description}"""
                sections.append(section)

        return "\n\n".join(sections)

    def _extract_agents_from_content(self, content: str) -> List[str]:
        """Extract agent references from AGENTS.md content."""
        agents = []
        for line in content.split("\n"):
            if "@myai/agents/" in line:
                # Extract agent name from path
                parts = line.split("@myai/agents/")
                if len(parts) > 1:
                    agent_path = parts[1].split(")")[0]
                    agent_name = agent_path.split("/")[-1]
                    agents.append(agent_name)
        return agents

    def read(self, path: Path) -> str:
        """Read an AGENTS.md file."""
        if not path.exists():
            msg = f"AGENTS.md not found at {path}"
            raise FileNotFoundError(msg)
        return path.read_text(encoding="utf-8")

    def update(self, path: Path, content: str) -> None:
        """Update an AGENTS.md file."""
        if not path.exists():
            msg = f"AGENTS.md not found at {path}"
            raise FileNotFoundError(msg)

        path.write_text(content, encoding="utf-8")

        # Update registry
        entry = self.registry.get_entry(path)
        if entry:
            entry.last_modified = datetime.now(timezone.utc)
            entry.checksum = self._calculate_checksum(path)
            entry.agents = self._extract_agents_from_content(content)
            self._save_registry()

    def delete(self, path: Path, *, force: bool = False) -> None:
        """Delete an AGENTS.md file."""
        if not path.exists():
            msg = f"AGENTS.md not found at {path}"
            raise FileNotFoundError(msg)

        if not force:
            # Check if file has local modifications
            entry = self.registry.get_entry(path)
            if entry and entry.checksum != self._calculate_checksum(path):
                msg = "File has local modifications. Use --force to delete anyway."
                raise ValueError(msg)

        path.unlink()
        self.registry.remove_entry(path)
        self._save_registry()

    def enable(self, path: Path) -> None:
        """Enable an AGENTS.md file."""
        # Convert to absolute path for comparison
        abs_path = path if path.is_absolute() else self.project_root / path

        entry = self.registry.get_entry(abs_path)
        if not entry:
            # Try to find by relative path
            for e in self.registry.files:
                if e.path in (abs_path, self.project_root / path):
                    entry = e
                    break

            if not entry:
                msg = f"AGENTS.md not registered at {path}"
                raise ValueError(msg)

        entry.enabled = True
        self._save_registry()

    def disable(self, path: Path) -> None:
        """Disable an AGENTS.md file."""
        # Convert to absolute path for comparison
        abs_path = path if path.is_absolute() else self.project_root / path

        entry = self.registry.get_entry(abs_path)
        if not entry:
            # Try to find by relative path
            for e in self.registry.files:
                if e.path in (abs_path, self.project_root / path):
                    entry = e
                    break

            if not entry:
                msg = f"AGENTS.md not registered at {path}"
                raise ValueError(msg)

        entry.enabled = False
        self._save_registry()

    def get_status(self) -> Dict[str, Any]:
        """Get status of all AGENTS.md files."""
        self.sync_registry()

        return {
            "total_files": len(self.registry.files),
            "enabled_files": len([e for e in self.registry.files if e.enabled]),
            "root_file": self.registry.get_root_entry() is not None,
            "files": self.registry.files,
        }

    def display_list(self) -> None:
        """Display list of AGENTS.md files in a table."""
        files = self.list_files()

        if not files:
            console.print("[yellow]No AGENTS.md files found in project[/yellow]")
            return

        table = Table(title="AGENTS.md Files in Project")
        table.add_column("Path", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Details", style="white")

        for entry in files:
            # Make path relative to project root
            rel_path = entry.path.relative_to(self.project_root)

            status = "✅ Enabled" if entry.enabled else "❌ Disabled"

            details = []
            if entry.agents:
                details.append(f"{len(entry.agents)} agents")
            if entry.inherits_from:
                inherit_path = entry.inherits_from.relative_to(self.project_root)
                details.append(f"inherits from {inherit_path}")

            table.add_row(
                str(rel_path),
                status,
                entry.type,
                ", ".join(details) if details else "-",
            )

        console.print(table)
