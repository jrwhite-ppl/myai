"""
Agent manager for MyAI.

This module provides high-level agent management operations including
CRUD operations, state management, and agent relationships.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from myai.agent.registry import AgentRegistry, get_agent_registry
from myai.models.agent import AgentCategory, AgentMetadata, AgentSpecification
from myai.storage.agent import AgentStorage
from myai.storage.filesystem import FileSystemStorage


class AgentManager:
    """
    High-level agent management operations.

    Provides CRUD operations, state management, agent relationships,
    and advanced agent operations like templating and versioning.
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        registry: Optional[AgentRegistry] = None,
    ):
        """
        Initialize agent manager.

        Args:
            base_path: Base path for agent storage
            registry: Agent registry instance (uses singleton if None)
        """
        self.base_path = base_path or Path.home() / ".myai"
        self.registry = registry or get_agent_registry()

        # Storage setup
        self._storage = FileSystemStorage(self.base_path)
        self._agent_storage = AgentStorage(self._storage)

        # Agent state tracking
        self._agent_states: Dict[str, Dict[str, Any]] = {}

        # Agent relationships
        self._dependencies: Dict[str, Set[str]] = {}  # agent -> dependencies
        self._dependents: Dict[str, Set[str]] = {}  # agent -> dependents

    def create_agent(
        self,
        name: str,
        display_name: str,
        category: AgentCategory,
        description: Optional[str] = None,
        content: str = "",
        tools: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
        *,
        persist: bool = True,
    ) -> AgentSpecification:
        """
        Create a new agent.

        Args:
            name: Unique agent name (kebab-case)
            display_name: Human-readable name
            category: Agent category
            description: Agent description
            content: Agent content/instructions
            tools: Compatible tools
            tags: Agent tags
            version: Agent version
            persist: Whether to persist to storage

        Returns:
            Created agent specification
        """
        # Validate name format
        if not name.replace("-", "").replace("_", "").isalnum():
            msg = f"Invalid agent name: {name}. Use alphanumeric with hyphens/underscores."
            raise ValueError(msg)

        # Check if agent already exists
        if self.registry.get_agent(name):
            msg = f"Agent '{name}' already exists"
            raise ValueError(msg)

        # Create metadata
        metadata = AgentMetadata(
            name=name,
            display_name=display_name,
            version=version,
            description=description or "No description provided",
            category=category,
            tools=tools or [],
            tags=tags or [],
            temperature=None,
            max_tokens=None,
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc),
        )

        # Create agent specification
        agent = AgentSpecification(
            metadata=metadata,
            content=content or "This is a placeholder agent content.",
        )

        # Register agent
        self.registry.register_agent(agent, persist=persist)

        # Initialize state
        self._agent_states[name] = {
            "created_at": datetime.now(timezone.utc),
            "modified": False,
            "active_version": version,
            "versions": [version],
        }

        return agent

    def create_agent_basic(
        self,
        name: str,
        display_name: str,
        description: str,
        category: AgentCategory = AgentCategory.CUSTOM,
        tools: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
        persist: bool = True,  # noqa: FBT001
    ) -> AgentSpecification:
        """
        Create a basic agent with minimal content.

        This is a simplified version of create_agent for CLI usage.

        Args:
            name: Unique agent identifier
            display_name: Human-readable name
            description: Agent description
            category: Agent category
            tools: Compatible tools
            tags: Agent tags
            version: Agent version
            persist: Whether to persist to storage

        Returns:
            Created agent specification
        """
        # Create basic content template
        content = f"""# {display_name}

{description}

## Instructions

You are {display_name.lower()}, an AI agent designed to help with {category.value} tasks.

Please provide helpful, accurate, and relevant responses based on your role and expertise.

## Guidelines

- Be professional and helpful
- Provide clear and actionable advice
- Ask clarifying questions when needed
- Stay within your area of expertise

---

This agent was created using MyAI CLI. Edit this content to customize the agent's behavior and instructions.
"""

        return self.create_agent(
            name=name,
            display_name=display_name,
            category=category,
            description=description,
            content=content,
            tools=tools,
            tags=tags,
            version=version,
            persist=persist,
        )

    def update_agent(
        self,
        name: str,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        tools: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: Optional[AgentCategory] = None,
        version_bump: bool = True,
        persist: bool = True,
    ) -> AgentSpecification:
        """
        Update an existing agent.

        Args:
            name: Agent name
            display_name: New display name
            description: New description
            content: New content
            tools: New tools list
            tags: New tags list
            category: New category
            version_bump: Whether to bump version
            persist: Whether to persist changes

        Returns:
            Updated agent specification

        Raises:
            ValueError: If agent not found
        """
        # Get existing agent
        agent = self.registry.get_agent(name)
        if not agent:
            msg = f"Agent '{name}' not found"
            raise ValueError(msg)

        # Create a copy with updates
        metadata_dict = agent.metadata.model_dump()

        # Update fields if provided
        if display_name is not None:
            metadata_dict["display_name"] = display_name
        if description is not None:
            metadata_dict["description"] = description
        if tools is not None:
            metadata_dict["tools"] = tools
        if tags is not None:
            metadata_dict["tags"] = tags
        if category is not None:
            metadata_dict["category"] = category

        # Update timestamps
        metadata_dict["modified"] = datetime.now(timezone.utc)

        # Version bump if requested
        if version_bump:
            current_version = metadata_dict["version"]
            parts = current_version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            metadata_dict["version"] = ".".join(parts)

        # Create updated metadata
        updated_metadata = AgentMetadata(**metadata_dict)

        # Create updated agent
        updated_agent = AgentSpecification(
            metadata=updated_metadata,
            content=content if content is not None else agent.content,
            file_path=agent.file_path,
            is_template=agent.is_template,
            template_variables=agent.template_variables,
            dependencies=agent.dependencies,
        )

        # Register updated agent
        self.registry.register_agent(updated_agent, persist=persist, overwrite=True)

        # Update state
        if name in self._agent_states:
            self._agent_states[name]["modified"] = True
            self._agent_states[name]["active_version"] = updated_metadata.version
            if updated_metadata.version not in self._agent_states[name]["versions"]:
                self._agent_states[name]["versions"].append(updated_metadata.version)

        return updated_agent

    def delete_agent(
        self,
        name: str,
        *,
        force: bool = False,
    ) -> bool:
        """
        Delete an agent.

        Args:
            name: Agent name
            force: Force deletion even if agent has dependents

        Returns:
            True if deleted, False if not found

        Raises:
            ValueError: If agent has dependents and force=False
        """
        # Check if agent exists
        if not self.registry.get_agent(name):
            return False

        # Check dependencies
        dependents = self._dependents.get(name, set())
        if dependents and not force:
            msg = f"Agent '{name}' has dependents: {', '.join(dependents)}"
            raise ValueError(msg)

        # Remove from registry
        with self.registry._index_lock:
            self.registry._remove_from_index(name)

        # Clear from cache
        with self.registry._cache_lock:
            self.registry._cache.pop(name, None)

        # Remove from storage
        self._agent_storage.delete_agent(name)

        # Clean up state
        self._agent_states.pop(name, None)

        # Clean up relationships
        self._dependencies.pop(name, None)
        for deps in self._dependencies.values():
            deps.discard(name)

        self._dependents.pop(name, None)
        for deps in self._dependents.values():
            deps.discard(name)

        return True

    def copy_agent(
        self,
        source_name: str,
        target_name: str,
        *,
        display_name: Optional[str] = None,
        version: str = "1.0.0",
        persist: bool = True,
    ) -> AgentSpecification:
        """
        Copy an agent to create a new one.

        Args:
            source_name: Source agent name
            target_name: Target agent name
            display_name: Display name for new agent
            version: Version for new agent
            persist: Whether to persist

        Returns:
            New agent specification
        """
        # Get source agent
        source = self.registry.get_agent(source_name)
        if not source:
            msg = f"Source agent '{source_name}' not found"
            raise ValueError(msg)

        # Check if target exists
        if self.registry.get_agent(target_name):
            msg = f"Target agent '{target_name}' already exists"
            raise ValueError(msg)

        # Create new metadata
        metadata_dict = source.metadata.model_dump()
        metadata_dict["name"] = target_name
        metadata_dict["display_name"] = display_name or f"Copy of {source.metadata.display_name}"
        metadata_dict["version"] = version
        metadata_dict["created"] = datetime.now(timezone.utc)
        metadata_dict["modified"] = datetime.now(timezone.utc)

        new_metadata = AgentMetadata(**metadata_dict)

        # Create new agent
        new_agent = AgentSpecification(
            metadata=new_metadata,
            content=source.content,
            is_template=source.is_template,
            template_variables=source.template_variables.copy(),
            dependencies=source.dependencies.copy(),
        )

        # Register new agent
        self.registry.register_agent(new_agent, persist=persist)

        # Initialize state
        self._agent_states[target_name] = {
            "created_at": datetime.now(timezone.utc),
            "modified": False,
            "active_version": version,
            "versions": [version],
            "copied_from": source_name,
        }

        return new_agent

    def export_agent(
        self,
        name: str,
        output_path: Path,
        *,
        include_metadata: bool = True,
    ) -> Path:
        """
        Export an agent to a file.

        Args:
            name: Agent name
            output_path: Output file path
            include_metadata: Whether to include metadata in export

        Returns:
            Path to exported file
        """
        # Get agent
        agent = self.registry.get_agent(name)
        if not agent:
            msg = f"Agent '{name}' not found"
            raise ValueError(msg)

        # Convert to markdown
        if include_metadata:
            content = agent.to_markdown()
        else:
            content = agent.content

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

        return output_path

    def import_agent(
        self,
        file_path: Path,
        *,
        name: Optional[str] = None,
        overwrite: bool = False,
    ) -> AgentSpecification:
        """
        Import an agent from a file.

        Args:
            file_path: Path to agent file
            name: Override agent name
            overwrite: Whether to overwrite existing agent

        Returns:
            Imported agent specification
        """
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        # Load agent from file
        content = file_path.read_text(encoding="utf-8")
        agent = AgentSpecification.from_markdown(content, file_path=file_path)

        # Override name if provided
        if name:
            metadata_dict = agent.metadata.model_dump()
            metadata_dict["name"] = name
            agent.metadata = AgentMetadata(**metadata_dict)

        # Check if agent exists
        if self.registry.get_agent(agent.metadata.name) and not overwrite:
            msg = f"Agent '{agent.metadata.name}' already exists"
            raise ValueError(msg)

        # Register agent
        self.registry.register_agent(agent, persist=True, overwrite=overwrite)

        # Initialize state
        self._agent_states[agent.metadata.name] = {
            "created_at": datetime.now(timezone.utc),
            "modified": False,
            "active_version": agent.metadata.version,
            "versions": [agent.metadata.version],
            "imported_from": str(file_path),
        }

        return agent

    def add_dependency(
        self,
        agent_name: str,
        dependency_name: str,
    ) -> None:
        """
        Add a dependency between agents.

        Args:
            agent_name: Agent that has the dependency
            dependency_name: Agent that is depended upon

        Raises:
            ValueError: If either agent not found or circular dependency
        """
        # Verify both agents exist
        if not self.registry.get_agent(agent_name):
            msg = f"Agent '{agent_name}' not found"
            raise ValueError(msg)

        if not self.registry.get_agent(dependency_name):
            msg = f"Dependency agent '{dependency_name}' not found"
            raise ValueError(msg)

        # Check for circular dependencies
        if self._would_create_cycle(agent_name, dependency_name):
            msg = "Adding dependency would create a circular reference"
            raise ValueError(msg)

        # Add dependency
        if agent_name not in self._dependencies:
            self._dependencies[agent_name] = set()
        self._dependencies[agent_name].add(dependency_name)

        # Add reverse mapping
        if dependency_name not in self._dependents:
            self._dependents[dependency_name] = set()
        self._dependents[dependency_name].add(agent_name)

    def remove_dependency(
        self,
        agent_name: str,
        dependency_name: str,
    ) -> bool:
        """
        Remove a dependency between agents.

        Args:
            agent_name: Agent that has the dependency
            dependency_name: Agent that is depended upon

        Returns:
            True if removed, False if dependency didn't exist
        """
        # Remove dependency
        if agent_name in self._dependencies:
            if dependency_name in self._dependencies[agent_name]:
                self._dependencies[agent_name].discard(dependency_name)
                if not self._dependencies[agent_name]:
                    del self._dependencies[agent_name]

                # Remove reverse mapping
                if dependency_name in self._dependents:
                    self._dependents[dependency_name].discard(agent_name)
                    if not self._dependents[dependency_name]:
                        del self._dependents[dependency_name]

                return True

        return False

    def get_dependencies(self, agent_name: str) -> List[str]:
        """Get direct dependencies of an agent."""
        return list(self._dependencies.get(agent_name, set()))

    def get_dependents(self, agent_name: str) -> List[str]:
        """Get agents that depend on this agent."""
        return list(self._dependents.get(agent_name, set()))

    def get_all_dependencies(self, agent_name: str) -> List[str]:
        """Get all dependencies (transitive) of an agent."""
        visited = set()
        result = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)

            for dep in self._dependencies.get(name, set()):
                visit(dep)
                if dep not in result:
                    result.append(dep)

        visit(agent_name)
        return result

    def get_agent_state(self, name: str) -> Dict[str, Any]:
        """Get agent state information."""
        return self._agent_states.get(name, {}).copy()

    def list_versions(self, name: str) -> List[str]:
        """List all versions of an agent."""
        state = self._agent_states.get(name, {})
        return state.get("versions", [])

    def _would_create_cycle(
        self,
        agent_name: str,
        dependency_name: str,
    ) -> bool:
        """Check if adding a dependency would create a cycle."""
        # Check if dependency_name can reach agent_name
        visited = set()
        queue = [dependency_name]

        while queue:
            current = queue.pop(0)
            if current == agent_name:
                return True

            if current in visited:
                continue

            visited.add(current)
            queue.extend(self._dependencies.get(current, set()))

        return False
