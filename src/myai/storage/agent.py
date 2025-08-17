"""
Agent storage implementation for MyAI.

This module provides specialized storage for agent specifications
with support for markdown files, categorization, and template management.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from myai.models.agent import AgentCategory, AgentSpecification
from myai.storage.base import Storage, StorageError

# Constants
MIN_KEY_PARTS = 3  # For agents/category/name structure


class AgentStorage:
    """Specialized storage for agent specifications."""

    def __init__(self, storage: Storage):
        """
        Initialize agent storage.

        Args:
            storage: Underlying storage implementation
        """
        self.storage = storage

    def save_agent(self, agent: AgentSpecification, category: Optional[str] = None) -> None:
        """
        Save an agent specification.

        Args:
            agent: Agent specification to save
            category: Optional category override
        """
        try:
            # Use category from metadata if not provided
            if category is None:
                category = agent.metadata.category.value

            key = self._get_agent_key(agent.metadata.name, category)

            # Create backup if agent already exists
            if self.storage.exists(key):
                self.storage.backup(key)

            # Convert to storage format
            agent_dict = agent.model_dump(mode="json")
            if agent_dict.get("file_path"):
                agent_dict["file_path"] = str(agent.file_path)

            self.storage.write(key, agent_dict)

        except ValidationError as e:
            msg = f"Agent validation failed: {e}"
            raise StorageError(msg) from e

    def load_agent(self, name: str, category: Optional[str] = None) -> Optional[AgentSpecification]:
        """
        Load an agent specification.

        Args:
            name: Agent name
            category: Agent category (if None, searches all categories)

        Returns:
            Agent specification or None if not found
        """
        if category:
            key = self._get_agent_key(name, category)
            data = self.storage.read(key)
            if data:
                return self._dict_to_agent(data)
        else:
            # Search all categories
            for cat in AgentCategory:
                agent = self.load_agent(name, cat.value)
                if agent:
                    return agent

        return None

    def list_agents(self, category: Optional[str] = None) -> List[str]:
        """
        List all available agents.

        Args:
            category: Optional category filter

        Returns:
            List of agent names
        """
        if category:
            prefix = f"agents/{category}/"
        else:
            prefix = "agents/"

        keys = self.storage.list_keys(prefix)
        agent_names = []

        for key in keys:
            # Extract agent name from key (format: agents/category/name)
            parts = key.split("/")
            if len(parts) >= MIN_KEY_PARTS and parts[0] == "agents":  # agents/category/name
                agent_names.append(parts[2])

        return sorted(set(agent_names))

    def list_categories(self) -> List[str]:
        """List all categories that contain agents."""
        keys = self.storage.list_keys("agents/")
        categories = set()

        for key in keys:
            parts = key.split("/")
            if len(parts) >= MIN_KEY_PARTS and parts[0] == "agents":  # agents/category/name
                categories.add(parts[1])

        return sorted(categories)

    def get_agents_by_category(self, category: str) -> List[AgentSpecification]:
        """
        Get all agents in a specific category.

        Args:
            category: Category name

        Returns:
            List of agent specifications
        """
        agents = []
        agent_names = self.list_agents(category)

        for name in agent_names:
            agent = self.load_agent(name, category)
            if agent:
                agents.append(agent)

        return agents

    def search_agents(
        self,
        query: str = "",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
    ) -> List[AgentSpecification]:
        """
        Search agents by various criteria.

        Args:
            query: Text to search in name, description, and content
            category: Category filter
            tags: Tag filters (agent must have all tags)
            tools: Tool filters (agent must support all tools)

        Returns:
            List of matching agent specifications
        """
        agents = []
        categories_to_search = [category] if category else self.list_categories()

        for cat in categories_to_search:
            for agent in self.get_agents_by_category(cat):
                if self._matches_criteria(agent, query, tags, tools):
                    agents.append(agent)

        return agents

    def delete_agent(self, name: str, category: Optional[str] = None) -> bool:
        """
        Delete an agent specification.

        Args:
            name: Agent name
            category: Agent category (if None, searches all categories)

        Returns:
            True if deleted, False if not found
        """
        if category:
            key = self._get_agent_key(name, category)
            if self.storage.exists(key):
                self.storage.backup(key)
                return self.storage.delete(key)
        else:
            # Search all categories
            for cat in AgentCategory:
                if self.delete_agent(name, cat.value):
                    return True

        return False

    def move_agent(self, name: str, from_category: str, to_category: str) -> bool:
        """
        Move an agent from one category to another.

        Args:
            name: Agent name
            from_category: Source category
            to_category: Destination category

        Returns:
            True if moved successfully
        """
        agent = self.load_agent(name, from_category)
        if not agent:
            return False

        # Update category in metadata
        agent.metadata.category = AgentCategory(to_category)

        # Save to new location and delete from old
        self.save_agent(agent, to_category)
        return self.delete_agent(name, from_category)

    def copy_agent(self, name: str, new_name: str, category: Optional[str] = None) -> bool:
        """
        Copy an agent with a new name.

        Args:
            name: Source agent name
            new_name: New agent name
            category: Agent category

        Returns:
            True if copied successfully
        """
        agent = self.load_agent(name, category)
        if not agent:
            return False

        # Update name in metadata
        agent.metadata.name = new_name
        agent.metadata.display_name = f"Copy of {agent.metadata.display_name}"

        # Save with new name
        self.save_agent(agent, category)
        return True

    def export_agent(self, name: str, file_path: Path, category: Optional[str] = None) -> None:
        """
        Export an agent to a markdown file.

        Args:
            name: Agent name
            file_path: Destination file path
            category: Agent category
        """
        agent = self.load_agent(name, category)
        if not agent:
            msg = f"Agent not found: {name}"
            raise StorageError(msg)

        markdown_content = agent.to_markdown()

        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(markdown_content)
        except OSError as e:
            msg = f"Failed to export agent: {e}"
            raise StorageError(msg) from e

    def import_agent(self, file_path: Path, category: Optional[str] = None) -> AgentSpecification:
        """
        Import an agent from a markdown file.

        Args:
            file_path: Source file path
            category: Optional category override

        Returns:
            Imported agent specification
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            msg = f"Failed to read agent file: {e}"
            raise StorageError(msg) from e

        try:
            agent = AgentSpecification.from_markdown(content, file_path)

            # Override category if specified
            if category:
                agent.metadata.category = AgentCategory(category)

            # Save the imported agent
            self.save_agent(agent)
            return agent

        except ValidationError as e:
            msg = f"Invalid agent specification: {e}"
            raise StorageError(msg) from e

    def get_agent_dependencies(self, name: str, category: Optional[str] = None) -> List[AgentSpecification]:
        """
        Get all agents that this agent depends on.

        Args:
            name: Agent name
            category: Agent category

        Returns:
            List of dependency agent specifications
        """
        agent = self.load_agent(name, category)
        if not agent:
            return []

        dependencies = []
        for dep_name in agent.dependencies:
            dep_agent = self.load_agent(dep_name)
            if dep_agent:
                dependencies.append(dep_agent)

        return dependencies

    def validate_agent(self, agent_data: Dict[str, Any]) -> List[str]:
        """
        Validate agent data and return any errors.

        Args:
            agent_data: Agent data to validate

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            AgentSpecification(**agent_data)
        except ValidationError as e:
            for error in e.errors():
                field = " -> ".join(str(loc) for loc in error["loc"])
                errors.append(f"{field}: {error['msg']}")

        return errors

    def _get_agent_key(self, name: str, category: str) -> str:
        """Get the storage key for an agent."""
        return f"agents/{category}/{name}"

    def _dict_to_agent(self, data: Dict[str, Any]) -> AgentSpecification:
        """Convert dictionary data to AgentSpecification."""
        # Remove storage metadata fields
        agent_data = {k: v for k, v in data.items() if not k.startswith("_")}

        # Convert file_path back to Path object
        if agent_data.get("file_path"):
            agent_data["file_path"] = Path(agent_data["file_path"])

        try:
            return AgentSpecification(**agent_data)
        except ValidationError as e:
            msg = f"Invalid agent data: {e}"
            raise StorageError(msg) from e

    def _matches_criteria(
        self, agent: AgentSpecification, query: str, tags: Optional[List[str]], tools: Optional[List[str]]
    ) -> bool:
        """Check if an agent matches the search criteria."""
        # Text search
        if query:
            query_lower = query.lower()
            searchable_text = (
                f"{agent.metadata.name} {agent.metadata.display_name} {agent.metadata.description} {agent.content}"
                .lower()
            )
            if query_lower not in searchable_text:
                return False

        # Tag filter
        if tags:
            agent_tags = [tag.lower() for tag in agent.metadata.tags]
            if not all(tag.lower() in agent_tags for tag in tags):
                return False

        # Tool filter
        if tools:
            agent_tools = [tool.lower() for tool in agent.metadata.tools]
            if not all(tool.lower() in agent_tools for tool in tools):
                return False

        return True
