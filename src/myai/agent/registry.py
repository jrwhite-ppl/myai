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
        self._custom_agents: Set[str] = set()  # Track custom/imported agents
        self._agents_by_source: Dict[str, Set[str]] = {}  # Track agents by source
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

            # Load custom agents from tracker
            self._load_custom_agents()

            # Load all agents from storage (including JSON agents)
            self._load_agents_from_storage()

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

            # Track custom agents
            if agent.is_custom:
                self._custom_agents.add(agent.metadata.name)

            # Track by source
            if agent.source:
                if agent.source not in self._agents_by_source:
                    self._agents_by_source[agent.source] = set()
                self._agents_by_source[agent.source].add(agent.metadata.name)

            # Add to enabled set if not explicitly disabled
            if not hasattr(agent.metadata, "enabled") or agent.metadata.enabled:
                self._enabled_agents.add(agent.metadata.name)

            # Update cache
            if self._cache_enabled:
                with self._cache_lock:
                    self._cache[agent.metadata.name] = (agent, datetime.now(timezone.utc))

            # Persist if requested (but not for custom agents with external paths)
            if persist and not (agent.is_custom and agent.external_path):
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

    def resolve_agent_name(self, name_or_display: str) -> Optional[str]:
        """
        Resolve an agent name from either the internal name or display name.

        Args:
            name_or_display: Either the agent's internal name or display name

        Returns:
            The agent's internal name if found, None otherwise
        """
        # First try direct lookup by internal name
        if self.get_agent(name_or_display):
            return name_or_display

        # If not found, search by display name
        with self._index_lock:
            for agent_name, agent in self._agents_by_name.items():
                if agent.metadata.display_name.lower() == name_or_display.lower():
                    return agent_name

        # Also check storage in case index is incomplete
        stored_agents = self._agent_storage.list_agents()
        for stored_name in stored_agents:
            loaded_agent = self._agent_storage.load_agent(stored_name)
            if loaded_agent is not None and loaded_agent.metadata.display_name.lower() == name_or_display.lower():
                return stored_name

        return None

    def unregister_agent(self, name: str) -> bool:
        """
        Unregister an agent from the registry.

        Args:
            name: Agent name to unregister

        Returns:
            True if agent was unregistered, False if not found
        """
        with self._index_lock:
            if name not in self._agents_by_name:
                return False

            agent = self._agents_by_name[name]

            # Remove from all indexes
            del self._agents_by_name[name]

            # Remove from category index
            category = agent.metadata.category.value
            if category in self._agents_by_category and name in self._agents_by_category[category]:
                self._agents_by_category[category].remove(name)
                if not self._agents_by_category[category]:
                    del self._agents_by_category[category]

            # Remove from tool index
            for tool in agent.metadata.tools:
                if tool in self._agents_by_tool and name in self._agents_by_tool[tool]:
                    self._agents_by_tool[tool].remove(name)
                    if not self._agents_by_tool[tool]:
                        del self._agents_by_tool[tool]

            # Remove from tag index
            for tag in agent.metadata.tags:
                if tag in self._agents_by_tag and name in self._agents_by_tag[tag]:
                    self._agents_by_tag[tag].remove(name)
                    if not self._agents_by_tag[tag]:
                        del self._agents_by_tag[tag]

            # Remove from custom agents
            if name in self._custom_agents:
                self._custom_agents.remove(name)

            # Remove from source index
            if agent.source and agent.source in self._agents_by_source:
                if name in self._agents_by_source[agent.source]:
                    self._agents_by_source[agent.source].remove(name)
                    if not self._agents_by_source[agent.source]:
                        del self._agents_by_source[agent.source]

            # Remove from enabled set
            if name in self._enabled_agents:
                self._enabled_agents.remove(name)

            # Clear from cache
            if self._cache_enabled:
                with self._cache_lock:
                    if name in self._cache:
                        del self._cache[name]

            return True

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

    def is_custom(self, name: str) -> bool:
        """Check if an agent is custom/imported."""
        with self._index_lock:
            return name in self._custom_agents

    def get_custom_agents(self) -> List[AgentSpecification]:
        """Get all custom/imported agents."""
        with self._index_lock:
            return [self._agents_by_name[name] for name in self._custom_agents if name in self._agents_by_name]

    def get_agents_by_source(self, source: str) -> List[AgentSpecification]:
        """Get all agents from a specific source."""
        with self._index_lock:
            if source not in self._agents_by_source:
                return []
            return [
                self._agents_by_name[name] for name in self._agents_by_source[source] if name in self._agents_by_name
            ]

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

                    # Skip deleted default agents
                    if self._is_deleted_default_agent(agent.metadata.name):
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
        # Store custom agents before clearing
        with self._index_lock:
            custom_agents_backup = {
                name: self._agents_by_name[name] for name in self._custom_agents if name in self._agents_by_name
            }

            # Clear indexes
            self._agents_by_name.clear()
            self._agents_by_category.clear()
            self._agents_by_tool.clear()
            self._agents_by_tag.clear()
            self._enabled_agents.clear()
            self._custom_agents.clear()
            self._agents_by_source.clear()

        # Clear cache
        self.clear_cache()

        # Re-discover agents
        if self._auto_discover:
            self.discover_agents()

            # Reload custom agents from tracker
            self._load_custom_agents()

            # Reload all agents from storage
            self._load_agents_from_storage()

        # Restore custom agents (in case they weren't in tracker yet)
        for agent in custom_agents_backup.values():
            self.register_agent(agent, persist=False, overwrite=True)

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
                "custom_agents": len(self._custom_agents),
                "sources": list(self._agents_by_source.keys()),
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

        # Remove from custom agents
        self._custom_agents.discard(name)

        # Remove from source index
        for source, agents in list(self._agents_by_source.items()):
            if name in agents:
                agents.discard(name)
                if not agents:
                    del self._agents_by_source[source]

        # Remove from main index
        del self._agents_by_name[name]

    def _load_custom_agents(self) -> None:
        """Load custom agents from the tracker."""
        try:
            from myai.integrations.custom_agents import get_custom_agent_tracker
            from myai.models.agent import AgentCategory, AgentMetadata

            tracker = get_custom_agent_tracker()
            custom_agents = tracker.get_custom_agents()

            for agent_data in custom_agents:
                try:
                    # Re-create the agent specification
                    metadata = AgentMetadata(
                        name=agent_data["name"],
                        display_name=agent_data["display_name"],
                        description=agent_data["description"],
                        category=AgentCategory(agent_data["category"]),
                        temperature=None,
                        max_tokens=None,
                    )

                    # Read content from external file if available
                    content = ""
                    file_path = None
                    if agent_data.get("external_path"):
                        file_path = Path(agent_data["external_path"])
                        if file_path.exists():
                            content = file_path.read_text(encoding="utf-8")

                    # Create agent specification
                    agent_spec = AgentSpecification(
                        metadata=metadata,
                        content=content,
                        is_custom=True,
                        source=agent_data.get("source"),
                        external_path=file_path,
                        file_path=file_path,
                    )

                    # Register without persisting
                    self.register_agent(agent_spec, persist=False, overwrite=True)

                except Exception:  # noqa: S112
                    # Skip agents that fail to load
                    continue

        except Exception:  # noqa: S110
            # If tracker fails, continue without custom agents
            pass

    def _load_agents_from_storage(self) -> None:
        """Load all agents from storage (including JSON format agents)."""
        try:
            # Get all agents from storage
            stored_agents = self._agent_storage.list_agents()

            for agent_name in stored_agents:
                # Skip if already loaded
                if agent_name in self._agents_by_name:
                    continue

                # Try to load the agent
                agent = self._agent_storage.load_agent(agent_name)
                if agent:
                    # Register without persisting (it's already in storage)
                    self.register_agent(agent, persist=False, overwrite=False)

        except Exception:  # noqa: S110
            # If storage loading fails, continue
            pass

    def _is_deleted_default_agent(self, agent_name: str) -> bool:
        """Check if agent is in the deleted default agents list."""
        try:
            from myai.config.manager import get_config_manager

            config_manager = get_config_manager()
            config = config_manager.get_config()
            deleted_list = getattr(config.agents, "deleted_default_agents", [])
            return agent_name in deleted_list
        except Exception:
            return False

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
