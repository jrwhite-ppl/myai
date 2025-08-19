"""
Agent registry for MyAI.

This module provides centralized agent registration, discovery, and management
with caching, indexing, and persistence capabilities.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from myai.models.agent import AgentSpecification
from myai.storage.agent import AgentStorage
from myai.storage.filesystem import FileSystemStorage


class AgentRegistry:
    """
    Central registry for all agents in the system.

    Provides agent discovery, registration, indexing, and caching with
    thread-safe operations and persistence support.
    """

    _instance: Optional["AgentRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "AgentRegistry":  # noqa: ARG003
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        base_path: Optional[Path] = None,
        *,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        auto_discover: bool = True,
    ):
        """
        Initialize agent registry.

        Args:
            base_path: Base path for agent storage
            cache_enabled: Whether to enable agent caching
            cache_ttl: Cache time-to-live in seconds
            auto_discover: Whether to automatically discover agents on init
        """
        # Prevent re-initialization of singleton
        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Storage setup
        self.base_path = base_path or Path.home() / ".myai"
        self._storage = FileSystemStorage(self.base_path)
        self._agent_storage = AgentStorage(self._storage)

        # Cache settings
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[AgentSpecification, datetime]] = {}
        self._cache_lock = threading.Lock()

        # Agent indexing
        self._agents_by_name: Dict[str, AgentSpecification] = {}
        self._agents_by_category: Dict[str, Set[str]] = {}
        self._agents_by_tool: Dict[str, Set[str]] = {}
        self._agents_by_tag: Dict[str, Set[str]] = {}
        self._enabled_agents: Set[str] = set()
        self._index_lock = threading.Lock()

        # Discovery settings
        self._auto_discover = auto_discover
        self._discovery_paths: List[Path] = [
            self.base_path / "agents",
            Path.home() / ".myai" / "agents",
            Path.home() / ".config" / "myai" / "agents",
        ]

        # Add default agents from the package
        import myai

        package_path = Path(myai.__file__).parent
        default_agents_path = package_path / "data" / "agents" / "default"
        if default_agents_path.exists():
            self._discovery_paths.append(default_agents_path)

        # Add enterprise path if available
        enterprise_path = Path("/etc/myai/agents")
        if enterprise_path.exists():
            self._discovery_paths.append(enterprise_path)

        # Initial discovery
        if self._auto_discover:
            self.discover_agents()

    def register_agent(
        self,
        agent: AgentSpecification,
        *,
        persist: bool = True,
        overwrite: bool = False,
    ) -> None:
        """
        Register an agent in the registry.

        Args:
            agent: Agent specification to register
            persist: Whether to persist to storage
            overwrite: Whether to overwrite existing agent

        Raises:
            ValueError: If agent already exists and overwrite=False
        """
        with self._index_lock:
            # Check if agent exists
            if agent.metadata.name in self._agents_by_name and not overwrite:
                msg = f"Agent '{agent.metadata.name}' already exists"
                raise ValueError(msg)

            # Remove old index entries if overwriting
            if overwrite and agent.metadata.name in self._agents_by_name:
                self._remove_from_index(agent.metadata.name)

            # Add to primary index
            self._agents_by_name[agent.metadata.name] = agent

            # Update category index
            category = agent.metadata.category
            if category not in self._agents_by_category:
                self._agents_by_category[category] = set()
            self._agents_by_category[category].add(agent.metadata.name)

            # Update tool index
            for tool in agent.metadata.tools:
                if tool not in self._agents_by_tool:
                    self._agents_by_tool[tool] = set()
                self._agents_by_tool[tool].add(agent.metadata.name)

            # Update tag index
            for tag in agent.metadata.tags:
                if tag not in self._agents_by_tag:
                    self._agents_by_tag[tag] = set()
                self._agents_by_tag[tag].add(agent.metadata.name)

            # Add to enabled set if not explicitly disabled
            if not hasattr(agent.metadata, "enabled") or agent.metadata.enabled:
                self._enabled_agents.add(agent.metadata.name)

            # Update cache
            if self._cache_enabled:
                with self._cache_lock:
                    self._cache[agent.metadata.name] = (agent, datetime.now(timezone.utc))

            # Persist if requested
            if persist:
                self._agent_storage.save_agent(agent)

    def get_agent(self, name: str) -> Optional[AgentSpecification]:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent specification or None if not found
        """
        # Check cache first
        if self._cache_enabled:
            with self._cache_lock:
                if name in self._cache:
                    agent, cached_time = self._cache[name]
                    # Check if cache is still valid
                    if (datetime.now(timezone.utc) - cached_time).total_seconds() < self._cache_ttl:
                        return agent
                    else:
                        # Remove expired cache entry
                        del self._cache[name]

        # Check index
        with self._index_lock:
            if name in self._agents_by_name:
                agent = self._agents_by_name[name]
                # Update cache
                if self._cache_enabled:
                    with self._cache_lock:
                        self._cache[name] = (agent, datetime.now(timezone.utc))
                return agent

        # Try loading from storage
        loaded_agent = self._agent_storage.load_agent(name)
        if loaded_agent:
            # Register in index (without persisting again)
            self.register_agent(loaded_agent, persist=False)
            return loaded_agent

        return None

    def list_agents(
        self,
        *,
        category: Optional[str] = None,
        tool: Optional[str] = None,
        tag: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[AgentSpecification]:
        """
        List agents with optional filtering.

        Args:
            category: Filter by category
            tool: Filter by tool compatibility
            tag: Filter by tag
            enabled_only: Only return enabled agents

        Returns:
            List of matching agents
        """
        with self._index_lock:
            # Start with all agents
            agent_names = set(self._agents_by_name.keys())

            # If index is empty, try to load from storage
            if not agent_names:
                stored_agents = self._agent_storage.list_agents()
                for stored_name in stored_agents:
                    stored_agent = self._agent_storage.load_agent(stored_name)
                    if stored_agent:
                        # Add to index directly (avoid lock recursion)
                        self._add_to_index(stored_agent)
                        agent_names.add(stored_name)

            # Apply filters
            if category:
                agent_names &= self._agents_by_category.get(category, set())

            if tool:
                agent_names &= self._agents_by_tool.get(tool, set())

            if tag:
                agent_names &= self._agents_by_tag.get(tag, set())

            if enabled_only:
                agent_names &= self._enabled_agents

            # Get agent objects
            agents = []
            for name in sorted(agent_names):
                agent = self._agents_by_name.get(name)
                if agent:
                    agents.append(agent)

            return agents

    def search_agents(
        self,
        query: str,
        *,
        search_fields: Optional[List[str]] = None,
    ) -> List[AgentSpecification]:
        """
        Search agents by query string.

        Args:
            query: Search query
            search_fields: Fields to search in (default: name, description, content)

        Returns:
            List of matching agents
        """
        if search_fields is None:
            search_fields = ["name", "description", "content"]

        query_lower = query.lower()
        results = []

        with self._index_lock:
            for agent in self._agents_by_name.values():
                # Search in specified fields
                for field in search_fields:
                    if field == "name" and query_lower in agent.metadata.name.lower():
                        results.append(agent)
                        break
                    elif field == "description" and agent.metadata.description:
                        if query_lower in agent.metadata.description.lower():
                            results.append(agent)
                            break
                    elif field == "content" and query_lower in agent.content.lower():
                        results.append(agent)
                        break
                    elif field == "tags":
                        for tag in agent.metadata.tags:
                            if query_lower in tag.lower():
                                results.append(agent)
                                break

        return results

    def enable_agent(self, name: str) -> bool:
        """
        Enable an agent.

        Args:
            name: Agent name

        Returns:
            True if agent was enabled, False if not found
        """
        with self._index_lock:
            if name in self._agents_by_name:
                self._enabled_agents.add(name)
                return True
            return False

    def disable_agent(self, name: str) -> bool:
        """
        Disable an agent.

        Args:
            name: Agent name

        Returns:
            True if agent was disabled, False if not found
        """
        with self._index_lock:
            if name in self._agents_by_name:
                self._enabled_agents.discard(name)
                return True
            return False

    def is_enabled(self, name: str) -> bool:
        """Check if an agent is enabled."""
        with self._index_lock:
            return name in self._enabled_agents

    def discover_agents(
        self,
        paths: Optional[List[Path]] = None,
        *,
        recursive: bool = True,
    ) -> List[str]:
        """
        Discover agents from filesystem.

        Args:
            paths: Paths to search (uses default discovery paths if None)
            recursive: Whether to search recursively

        Returns:
            List of discovered agent names
        """
        if paths is None:
            paths = self._discovery_paths

        discovered = []

        for path in paths:
            if not path.exists():
                continue

            if recursive:
                # Find all .md files recursively
                md_files = path.rglob("*.md")
            else:
                # Find .md files in directory only
                md_files = path.glob("*.md")

            for md_file in md_files:
                try:
                    # Try to load as agent
                    content = md_file.read_text(encoding="utf-8")
                    # Now we can handle agents with or without frontmatter
                    agent = AgentSpecification.from_markdown(content, file_path=md_file)
                    # Skip unnamed agents (likely not real agent files)
                    if agent.metadata.name == "unnamed_agent":
                        continue
                    # Register agent
                    self.register_agent(agent, persist=False, overwrite=True)
                    discovered.append(agent.metadata.name)
                except Exception:  # noqa: S112
                    # Skip files that aren't valid agents
                    # TODO: Consider logging these errors
                    continue

        return discovered

    def add_discovery_path(self, path: Path) -> None:
        """Add a path to agent discovery locations."""
        if path not in self._discovery_paths:
            self._discovery_paths.append(path)

    def remove_discovery_path(self, path: Path) -> None:
        """Remove a path from agent discovery locations."""
        if path in self._discovery_paths:
            self._discovery_paths.remove(path)

    def clear_cache(self) -> None:
        """Clear the agent cache."""
        with self._cache_lock:
            self._cache.clear()

    def refresh(self) -> None:
        """Refresh registry by re-discovering agents."""
        # Clear indexes
        with self._index_lock:
            self._agents_by_name.clear()
            self._agents_by_category.clear()
            self._agents_by_tool.clear()
            self._agents_by_tag.clear()
            self._enabled_agents.clear()

        # Clear cache
        self.clear_cache()

        # Re-discover agents
        if self._auto_discover:
            self.discover_agents()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with registry statistics
        """
        with self._index_lock:
            return {
                "total_agents": len(self._agents_by_name),
                "enabled_agents": len(self._enabled_agents),
                "categories": list(self._agents_by_category.keys()),
                "tools": list(self._agents_by_tool.keys()),
                "tags": list(self._agents_by_tag.keys()),
                "cache_size": len(self._cache),
                "discovery_paths": [str(p) for p in self._discovery_paths],
            }

    def _remove_from_index(self, name: str) -> None:
        """Remove agent from all indexes (must be called with lock held)."""
        if name not in self._agents_by_name:
            return

        agent = self._agents_by_name[name]

        # Remove from category index
        category = agent.metadata.category
        if category in self._agents_by_category:
            self._agents_by_category[category].discard(name)
            if not self._agents_by_category[category]:
                del self._agents_by_category[category]

        # Remove from tool index
        for tool in agent.metadata.tools:
            if tool in self._agents_by_tool:
                self._agents_by_tool[tool].discard(name)
                if not self._agents_by_tool[tool]:
                    del self._agents_by_tool[tool]

        # Remove from tag index
        for tag in agent.metadata.tags:
            if tag in self._agents_by_tag:
                self._agents_by_tag[tag].discard(name)
                if not self._agents_by_tag[tag]:
                    del self._agents_by_tag[tag]

        # Remove from enabled set
        self._enabled_agents.discard(name)

        # Remove from main index
        del self._agents_by_name[name]

    def _add_to_index(self, agent: AgentSpecification) -> None:
        """Add agent to all indexes without locking."""
        # Add to primary index
        self._agents_by_name[agent.metadata.name] = agent

        # Update category index
        category = agent.metadata.category
        if category not in self._agents_by_category:
            self._agents_by_category[category] = set()
        self._agents_by_category[category].add(agent.metadata.name)

        # Update tool index
        for tool in agent.metadata.tools:
            if tool not in self._agents_by_tool:
                self._agents_by_tool[tool] = set()
            self._agents_by_tool[tool].add(agent.metadata.name)

        # Update tag index
        for tag in agent.metadata.tags:
            if tag not in self._agents_by_tag:
                self._agents_by_tag[tag] = set()
            self._agents_by_tag[tag].add(agent.metadata.name)

        # Agent starts as enabled by default
        self._enabled_agents.add(agent.metadata.name)


# Convenience function for getting the singleton instance
def get_agent_registry() -> AgentRegistry:
    """Get the singleton AgentRegistry instance."""
    return AgentRegistry()
