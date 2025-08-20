"""Adapter for integrating Agent-OS functionality into MyAI."""

from pathlib import Path
from typing import Dict, List

from myai.agent_os.transformer import AgentOSTransformer


class AgentOSAdapter:
    """Adapt Agent-OS functionality for MyAI."""

    def __init__(self):
        self.transformer = AgentOSTransformer()
        self.agent_os_source = None  # Will be set when we add as submodule
        self.myai_base = Path.home() / ".myai"

    def setup_from_temp(self, temp_agent_os_path: Path) -> None:
        """Setup MyAI using Agent-OS from a temporary location."""
        if not temp_agent_os_path.exists():
            msg = f"Agent-OS path does not exist: {temp_agent_os_path}"
            raise ValueError(msg)

        # Create MyAI directory structure
        self._create_myai_structure()

        # Copy and transform content
        self._copy_workflows(temp_agent_os_path)
        self._copy_standards(temp_agent_os_path)
        self._copy_commands(temp_agent_os_path)
        self._copy_agents(temp_agent_os_path)

    def _create_myai_structure(self) -> None:
        """Create MyAI directory structure."""
        directories = [
            self.myai_base / "workflows" / "core",
            self.myai_base / "workflows" / "meta",
            self.myai_base / "standards" / "code-style",
            self.myai_base / "commands",
            self.myai_base / "project",
            self.myai_base / "specs",
            self.myai_base / "docs" / "recaps",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _copy_workflows(self, source: Path) -> None:
        """Copy and transform Agent-OS instructions to MyAI workflows."""
        instructions_dir = source / "instructions"
        if not instructions_dir.exists():
            return

        workflows_dir = self.myai_base / "workflows"

        for instruction_file in instructions_dir.rglob("*.md"):
            # Get relative path
            rel_path = instruction_file.relative_to(instructions_dir)

            # Transform path
            dest_path = workflows_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Read and transform content
            content = instruction_file.read_text()
            transformed = self.transformer.transform_workflow(content)

            # Write transformed content
            dest_path.write_text(transformed)

    def _copy_standards(self, source: Path) -> None:
        """Copy and transform Agent-OS standards to MyAI."""
        standards_dir = source / "standards"
        if not standards_dir.exists():
            return

        myai_standards = self.myai_base / "standards"

        for standard_file in standards_dir.rglob("*.md"):
            # Get relative path
            rel_path = standard_file.relative_to(standards_dir)

            # Transform path
            dest_path = myai_standards / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Read and transform content
            content = standard_file.read_text()
            transformed = self.transformer.transform_content(content)

            # Write transformed content
            dest_path.write_text(transformed)

    def _copy_commands(self, source: Path) -> None:
        """Copy and transform Agent-OS commands to MyAI."""
        commands_dir = source / "commands"
        if not commands_dir.exists():
            return

        myai_commands = self.myai_base / "commands"

        for command_file in commands_dir.glob("*.md"):
            # Transform the command name
            command_name = command_file.stem.replace("-", "_")
            dest_path = myai_commands / f"{command_name}.md"

            # Read and transform content
            content = command_file.read_text()
            transformed = self.transformer.transform_command(content)

            # Write transformed content
            dest_path.write_text(transformed)

    def _copy_agents(self, source: Path) -> None:
        """Copy and transform Agent-OS agents to MyAI workflow agents."""
        # Look for agents in multiple possible locations
        agent_locations = [source / "claude-code" / "agents", source / "agents", source / ".claude" / "agents"]

        target_agents_dir = self.myai_base / "agents" / "workflow"
        target_agents_dir.mkdir(parents=True, exist_ok=True)

        for agent_dir in agent_locations:
            if agent_dir.exists() and agent_dir.is_dir():
                for agent_file in agent_dir.glob("*.md"):
                    # Read content
                    content = agent_file.read_text()

                    # Transform agent
                    agent_name = f"workflow_{agent_file.stem}"
                    transformed_agent = self.transformer.transform_agent(content, agent_name)

                    # Write to workflow agents directory
                    dest_path = target_agents_dir / f"{agent_name}.md"

                    # Format as markdown agent file
                    agent_content = f"# {transformed_agent['name'].replace('_', ' ').title()}\n\n"
                    if transformed_agent.get("metadata"):
                        agent_content += f"Category: {transformed_agent.get('category', 'workflow')}\n"
                        agent_content += f"Source: {transformed_agent.get('source', 'workflow-system')}\n\n"
                    agent_content += transformed_agent["content"]

                    dest_path.write_text(agent_content)

    def create_project_structure(self, project_path: Path) -> None:
        """Create MyAI project structure (transformed from Agent-OS)."""
        myai_project = project_path / ".myai"

        # Create directories
        directories = [
            myai_project / "project",
            myai_project / "specs",
            myai_project / "docs" / "recaps",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Create symlinks to global workflows and standards
        if (self.myai_base / "workflows").exists():
            workflows_link = myai_project / "workflows"
            if not workflows_link.exists():
                workflows_link.symlink_to(self.myai_base / "workflows")

        if (self.myai_base / "standards").exists():
            standards_link = myai_project / "standards"
            if not standards_link.exists():
                standards_link.symlink_to(self.myai_base / "standards")

    def import_agent_os_agents(self, source: Path) -> List[Dict[str, str]]:
        """Import and transform Agent-OS agents."""
        agents = []
        claude_agents = source / "claude-code" / "agents"

        if claude_agents.exists():
            for agent_file in claude_agents.glob("*.md"):
                content = agent_file.read_text()
                agent_name = f"workflow_{agent_file.stem}"  # Prefix to avoid confusion

                # Transform the agent
                transformed_agent = self.transformer.transform_agent(content, agent_name)
                agents.append(transformed_agent)

        return agents
