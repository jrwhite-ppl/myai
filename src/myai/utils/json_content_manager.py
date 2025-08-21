"""
JSON content management utilities with section preservation.

Since JSON doesn't support comments, we use a different approach:
- Preserve unknown top-level keys
- Update only specific managed sections
- Use a special _metadata key for tracking
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class JsonContentManager:
    """Manage specific sections in JSON files while preserving user content."""

    def __init__(self, managed_sections: list[str], metadata_key: str = "_myai_metadata"):
        """
        Initialize the JSON content manager.

        Args:
            managed_sections: List of top-level keys that MyAI manages
            metadata_key: Key to use for metadata (optional)
        """
        self.managed_sections = set(managed_sections)
        self.metadata_key = metadata_key

    def read_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Read and parse a JSON file."""
        if not file_path.exists():
            return {}

        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in {file_path}"
            raise ValueError(msg) from e

    def write_json_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write data to a JSON file with nice formatting."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")  # Add trailing newline

    def update_sections(
        self, file_path: Path, updates: Dict[str, Any], *, preserve_unknown: bool = True, create_if_missing: bool = True
    ) -> None:
        """
        Update specific sections in a JSON file while preserving other content.

        Args:
            file_path: Path to JSON file
            updates: Dictionary of sections to update
            preserve_unknown: Whether to preserve unknown keys
            create_if_missing: Whether to create file if it doesn't exist
        """
        # Read existing content
        if file_path.exists():
            existing_data = self.read_json_file(file_path)
        elif create_if_missing:
            existing_data = {}
        else:
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        # Create new data structure
        new_data = {}

        # First, preserve non-managed sections if requested
        if preserve_unknown:
            for key, value in existing_data.items():
                if key not in self.managed_sections and key != self.metadata_key:
                    new_data[key] = value

        # Then add/update managed sections
        for key, value in updates.items():
            if key in self.managed_sections:
                new_data[key] = value

        # Preserve any unmentioned managed sections from existing data
        for section in self.managed_sections:
            if section not in updates and section in existing_data:
                new_data[section] = existing_data[section]

        # Add metadata if it exists
        if self.metadata_key in existing_data:
            new_data[self.metadata_key] = existing_data[self.metadata_key]

        # Write back
        self.write_json_file(file_path, new_data)

    def get_user_sections(self, file_path: Path) -> Dict[str, Any]:
        """Get all non-managed sections from a JSON file."""
        if not file_path.exists():
            return {}

        data = self.read_json_file(file_path)
        user_sections = {}

        for key, value in data.items():
            if key not in self.managed_sections and key != self.metadata_key:
                user_sections[key] = value

        return user_sections

    def merge_with_template(
        self, template: Dict[str, Any], user_sections: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Merge template with user sections.

        Args:
            template: Template with managed sections
            user_sections: User-defined sections to preserve

        Returns:
            Merged dictionary
        """
        result = template.copy()

        if user_sections:
            for key, value in user_sections.items():
                if key not in self.managed_sections and key != self.metadata_key:
                    result[key] = value

        return result


# Convenience function for Claude settings
def update_claude_settings(file_path: Path, project_config: Dict[str, Any], *, create_if_missing: bool = True) -> None:
    """
    Update Claude settings.local.json file preserving user customizations.

    Args:
        file_path: Path to settings.local.json
        project_config: Project configuration to write
        create_if_missing: Whether to create file if missing
    """
    # Define what sections MyAI manages in Claude settings
    managed_sections = ["projects"]  # MyAI manages the projects section

    manager = JsonContentManager(managed_sections)

    # Update only the managed sections
    updates = {"projects": project_config.get("projects", {})}

    manager.update_sections(file_path, updates, preserve_unknown=True, create_if_missing=create_if_missing)
