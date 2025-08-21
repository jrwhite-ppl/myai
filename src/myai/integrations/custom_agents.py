"""
Custom agent tracking and persistence.

This module handles tracking of custom/imported agents that exist
outside of MyAI's normal agent storage.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from myai.models.agent import AgentSpecification


class CustomAgentTracker:
    """Tracks custom agents imported from external sources."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the tracker."""
        self.base_path = base_path or Path.home() / ".myai"
        self.metadata_file = self.base_path / "config" / "custom_agents.json"
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

    def load_custom_agents(self) -> Dict[str, Dict]:
        """Load custom agent metadata from disk."""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file) as f:
                return json.load(f)
        except Exception:
            return {}

    def save_custom_agents(self, agents: Dict[str, Dict]) -> None:
        """Save custom agent metadata to disk."""
        with open(self.metadata_file, "w") as f:
            json.dump(agents, f, indent=2)

    def add_custom_agent(self, agent: AgentSpecification) -> None:
        """Add a custom agent to tracking."""
        if not agent.is_custom:
            return

        agents = self.load_custom_agents()
        agents[agent.metadata.name] = {
            "name": agent.metadata.name,
            "display_name": agent.metadata.display_name,
            "description": agent.metadata.description,
            "category": agent.metadata.category.value,
            "source": agent.source,
            "external_path": str(agent.external_path) if agent.external_path else None,
            "file_path": str(agent.file_path) if agent.file_path else None,
        }
        self.save_custom_agents(agents)

    def remove_custom_agent(self, name: str) -> None:
        """Remove a custom agent from tracking."""
        agents = self.load_custom_agents()
        if name in agents:
            del agents[name]
            self.save_custom_agents(agents)

    def get_custom_agents(self) -> List[Dict]:
        """Get all tracked custom agents."""
        return list(self.load_custom_agents().values())

    def is_custom_agent(self, name: str) -> bool:
        """Check if an agent is a custom agent."""
        agents = self.load_custom_agents()
        return name in agents


# Global instance
_tracker = CustomAgentTracker()


def get_custom_agent_tracker() -> CustomAgentTracker:
    """Get the global custom agent tracker."""
    return _tracker
