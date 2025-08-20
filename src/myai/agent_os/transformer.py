"""Transform Agent-OS content to MyAI conventions."""

import re
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional


class AgentOSTransformer:
    """Transform Agent-OS content to MyAI conventions."""

    # Path mappings from Agent-OS to MyAI
    PATH_MAPPINGS: ClassVar[dict[str, str]] = {
        # Directory mappings
        ".agent-os": ".myai",
        "agent-os": "myai",
        "AGENT_OS": "MYAI",
        "Agent-OS": "MyAI",
        # Specific paths
        ".agent-os/product": ".myai/project",
        ".agent-os/specs": ".myai/specs",
        ".agent-os/recaps": ".myai/docs/recaps",
        ".agent-os/standards": ".myai/standards",
        ".agent-os/instructions": ".myai/workflows",
        ".agent-os/commands": ".myai/commands",
        # File references
        "@.agent-os/": "@workflows/",
    }

    # Content replacements
    CONTENT_REPLACEMENTS: ClassVar[dict[str, str]] = {
        "Agent-OS": "MyAI workflow system",
        "agent-os": "myai",
        "Agent OS": "MyAI",
        "buildermethods/agent-os": "internal/workflow-system",
        "Setting up Agent-OS": "Setting up MyAI workflows",
        "Agent-OS Setup": "MyAI Setup",
    }

    def transform_path(self, agent_os_path: Path) -> Optional[Path]:
        """Convert Agent-OS path to MyAI path."""
        path_str = str(agent_os_path)

        # Apply path mappings
        for old, new in self.PATH_MAPPINGS.items():
            path_str = path_str.replace(old, new)

        # Skip certain files
        if any(skip in path_str for skip in ["AGENT_OS_README.md", "agent-os-only"]):
            return None

        return Path(path_str)

    def transform_content(self, content: str) -> str:
        """Transform file content to remove Agent-OS references."""
        # Apply content replacements
        for old, new in self.CONTENT_REPLACEMENTS.items():
            content = content.replace(old, new)

        # Remove Agent-OS specific sections
        content = re.sub(r"<!--\s*AGENT-OS-ONLY\s*-->.*?<!--\s*/AGENT-OS-ONLY\s*-->", "", content, flags=re.DOTALL)

        # Update instruction references
        content = re.sub(r"@\.agent-os/instructions/([^/]+)/([^\s]+)", r"@workflows/\1/\2", content)

        # Update command references
        content = re.sub(r"@\.agent-os/commands/([^\s]+)", r"@commands/\1", content)

        return content

    def transform_agent(self, agent_content: str, agent_name: str) -> Dict[str, Any]:
        """Transform an Agent-OS agent to MyAI format."""
        # Transform the content
        transformed_content = self.transform_content(agent_content)

        # Extract metadata from frontmatter if present
        metadata = {}
        if transformed_content.startswith("---"):
            parts = transformed_content.split("---", 2)
            frontmatter_threshold = 3
            if len(parts) >= frontmatter_threshold:
                # Parse YAML frontmatter
                frontmatter = parts[1].strip()
                for line in frontmatter.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip()

                # Remove frontmatter from content
                transformed_content = parts[2].strip()

        # Create MyAI agent format
        myai_agent = {
            "name": agent_name,
            "content": transformed_content,
            "metadata": metadata,
            "source": "workflow-system",  # Don't expose Agent-OS
            "category": "workflow",
        }

        return myai_agent

    def transform_workflow(self, workflow_content: str) -> str:
        """Transform Agent-OS workflow/instruction to MyAI format."""
        # Transform content
        transformed = self.transform_content(workflow_content)

        # Add MyAI header if needed
        if not transformed.startswith("#"):
            transformed = f"# MyAI Workflow\n\n{transformed}"

        return transformed

    def transform_command(self, command_content: str) -> str:
        """Transform Agent-OS command to MyAI format."""
        # Transform content
        transformed = self.transform_content(command_content)

        # Update command structure
        transformed = transformed.replace("Refer to the instructions located in this file:", "This workflow uses:")

        return transformed
