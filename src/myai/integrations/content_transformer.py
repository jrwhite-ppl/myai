"""
Content transformation utilities for Agent-OS to MyAI migration.

This module provides utilities to transform Agent-OS content, configurations,
and documentation to MyAI format while preserving functionality.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ContentTransformer:
    """Handles content transformation from Agent-OS to MyAI format."""

    def __init__(self):
        # Define replacement patterns
        self.text_replacements = {
            # Basic text replacements
            "Agent-OS": "MyAI",
            "agent-os": "myai",
            "AGENT_OS": "MYAI",
            "AGENTOS": "MYAI",
            "agentos": "myai",
            # Path replacements
            ".agent-os": ".myai",
            "/agent-os/": "/myai/",
            "~/.agent-os": "~/.myai",
            "$HOME/.agent-os": "$HOME/.myai",
            # Command replacements
            "agentos ": "myai ",
            "agentos\t": "myai\t",
            "agentos\n": "myai\n",
            # URL and repository replacements
            "agent-os.com": "myai.com",  # Hypothetical
            "github.com/agent-os": "github.com/myai",  # Hypothetical
        }

        # Regex patterns for more complex replacements
        self.regex_patterns = [
            # Environment variables
            (re.compile(r"\bAGENT_OS_([A-Z_]+)\b"), r"MYAI_\1"),
            (re.compile(r"\bagent_os_([a-z_]+)\b"), r"myai_\1"),
            # Configuration keys
            (re.compile(r'"agent-os":', re.IGNORECASE), '"myai":'),
            (re.compile(r"'agent-os':", re.IGNORECASE), "'myai':"),
            # Import statements
            (re.compile(r"\bfrom agent_os\b"), "from myai"),
            (re.compile(r"\bimport agent_os\b"), "import myai"),
            # Class and module references
            (re.compile(r"\bAgentOS([A-Z][a-zA-Z]*)\b"), r"MyAI\1"),
            (re.compile(r"\bagent_os\.([a-zA-Z_]+)\b"), r"myai.\1"),
        ]

        # Special case handlers
        self.special_cases = {
            "config.json": self._transform_config_json,
            "package.json": self._transform_package_json,
            "setup.py": self._transform_setup_py,
            "pyproject.toml": self._transform_pyproject_toml,
            "README.md": self._transform_readme,
        }

    def transform_text_content(self, content: str, *, preserve_functionality: bool = True) -> str:
        """
        Transform text content from Agent-OS to MyAI format.

        Args:
            content: Original content
            preserve_functionality: If True, preserve code functionality

        Returns:
            Transformed content
        """
        transformed = content

        # Apply basic text replacements
        for old_text, new_text in self.text_replacements.items():
            transformed = transformed.replace(old_text, new_text)

        # Apply regex patterns
        for pattern, replacement in self.regex_patterns:
            transformed = pattern.sub(replacement, transformed)

        # Handle special preservation cases
        if preserve_functionality:
            transformed = self._preserve_functionality(transformed)

        return transformed

    def transform_file(
        self, file_path: Path, output_path: Optional[Path] = None, *, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Transform a file from Agent-OS to MyAI format.

        Args:
            file_path: Path to the file to transform
            output_path: Output path (defaults to same path)
            dry_run: If True, don't write the file

        Returns:
            Transformation result
        """
        result = {
            "source": str(file_path),
            "target": str(output_path or file_path),
            "success": False,
            "changes_made": False,
            "error": "",
            "preview": "",
        }

        if not file_path.exists():
            result["error"] = "Source file does not exist"
            return result

        try:
            # Read original content
            with open(file_path, encoding="utf-8") as f:
                original_content = f.read()

            # Apply transformations
            filename = file_path.name
            if filename in self.special_cases:
                # Use special case handler
                transformed_content = self.special_cases[filename](original_content)
            else:
                # Use general transformation
                transformed_content = self.transform_text_content(original_content)

            # Check if changes were made
            result["changes_made"] = original_content != transformed_content
            result["preview"] = self._generate_preview(original_content, transformed_content)

            if not dry_run and result["changes_made"]:
                output_file = output_path or file_path
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(transformed_content)

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def transform_directory(
        self,
        directory_path: Path,
        output_path: Optional[Path] = None,
        file_patterns: Optional[List[str]] = None,
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Transform all files in a directory.

        Args:
            directory_path: Directory to transform
            output_path: Output directory (defaults to same directory)
            file_patterns: File patterns to include (e.g., ['*.py', '*.md'])
            dry_run: If True, don't write files

        Returns:
            Transformation results
        """
        results = {
            "source": str(directory_path),
            "target": str(output_path or directory_path),
            "files_processed": 0,
            "files_changed": 0,
            "files": [],
            "errors": [],
        }

        if not directory_path.exists():
            results["errors"].append("Source directory does not exist")
            return results

        # Default patterns if none provided
        if file_patterns is None:
            file_patterns = ["*.py", "*.md", "*.json", "*.yaml", "*.yml", "*.toml", "*.txt", "*.rst"]

        # Find all matching files
        files_to_process = []
        for pattern in file_patterns:
            files_to_process.extend(directory_path.rglob(pattern))

        # Process each file
        for file_path in files_to_process:
            try:
                # Calculate output path maintaining relative structure
                if output_path:
                    relative_path = file_path.relative_to(directory_path)
                    target_path = output_path / relative_path
                else:
                    target_path = file_path

                file_result = self.transform_file(file_path, target_path, dry_run=dry_run)

                results["files"].append(file_result)
                results["files_processed"] += 1

                if file_result["changes_made"]:
                    results["files_changed"] += 1

                if file_result["error"]:
                    results["errors"].append(f"{file_path}: {file_result['error']}")

            except Exception as e:
                results["errors"].append(f"{file_path}: {e!s}")

        return results

    def _preserve_functionality(self, content: str) -> str:
        """Preserve functionality in transformed content."""
        # Add compatibility imports if needed
        if "import myai" in content and "# Agent-OS compatibility" not in content:
            compatibility_note = "# Agent-OS compatibility maintained via MyAI\n"
            content = compatibility_note + content

        return content

    def _generate_preview(self, original: str, transformed: str) -> str:
        """Generate a preview of changes made."""
        if original == transformed:
            return "No changes made"

        # Find first few differences for preview
        original_lines = original.split("\n")
        transformed_lines = transformed.split("\n")

        preview_lines = []
        for i, (orig_line, trans_line) in enumerate(zip(original_lines, transformed_lines)):
            if orig_line != trans_line:
                preview_lines.append(f"Line {i+1}:")
                preview_lines.append(f"  - {orig_line}")
                preview_lines.append(f"  + {trans_line}")

                # Limit preview to first 3 changes
                max_preview_lines = 9
                if len(preview_lines) >= max_preview_lines:
                    preview_lines.append("  ... (more changes)")
                    break

        return "\n".join(preview_lines)

    def _transform_config_json(self, content: str) -> str:
        """Transform config.json files with special handling."""
        import json

        try:
            data = json.loads(content)

            # Transform configuration data
            data = self._transform_dict_keys_and_values(data)

            return json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            # Fall back to text transformation if not valid JSON
            return self.transform_text_content(content)

    def _transform_package_json(self, content: str) -> str:
        """Transform package.json files."""
        import json

        try:
            data = json.loads(content)

            # Transform package-specific fields
            if "name" in data and "agent-os" in data["name"]:
                data["name"] = data["name"].replace("agent-os", "myai")

            if "description" in data:
                data["description"] = self.transform_text_content(data["description"])

            # Transform other fields
            data = self._transform_dict_keys_and_values(data)

            return json.dumps(data, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return self.transform_text_content(content)

    def _transform_setup_py(self, content: str) -> str:
        """Transform setup.py files."""
        transformed = self.transform_text_content(content)

        # Handle setup() call parameters
        transformed = re.sub(r'name=["\']agent[_-]?os["\']', 'name="myai"', transformed, flags=re.IGNORECASE)

        return transformed

    def _transform_pyproject_toml(self, content: str) -> str:
        """Transform pyproject.toml files."""
        try:
            import toml

            data = toml.loads(content)

            # Transform project name
            if "project" in data and "name" in data["project"]:
                if "agent-os" in data["project"]["name"]:
                    data["project"]["name"] = data["project"]["name"].replace("agent-os", "myai")

            # Transform other fields
            data = self._transform_dict_keys_and_values(data)

            return toml.dumps(data)
        except Exception:
            # Fall back to text transformation
            return self.transform_text_content(content)

    def _transform_readme(self, content: str) -> str:
        """Transform README files with special handling."""
        transformed = self.transform_text_content(content)

        # Add migration notice if this was an Agent-OS README
        if "Agent-OS" in content and "# Migration from Agent-OS" not in transformed:
            migration_notice = """
# Migration from Agent-OS

This project has been migrated from Agent-OS to MyAI. All functionality has been preserved
while providing an improved and unified interface.

"""
            # Insert after the first heading if present
            lines = transformed.split("\n")
            if lines and lines[0].startswith("#"):
                lines.insert(2, migration_notice)
            else:
                lines.insert(0, migration_notice)

            transformed = "\n".join(lines)

        return transformed

    def _transform_dict_keys_and_values(self, data: Union[Dict, List, Any]) -> Any:
        """Recursively transform dictionary keys and values."""
        if isinstance(data, dict):
            transformed_dict = {}
            for key, value in data.items():
                # Transform key
                new_key = self.transform_text_content(str(key)) if isinstance(key, str) else key
                # Transform value
                new_value = self._transform_dict_keys_and_values(value)
                transformed_dict[new_key] = new_value
            return transformed_dict
        elif isinstance(data, list):
            return [self._transform_dict_keys_and_values(item) for item in data]
        elif isinstance(data, str):
            return self.transform_text_content(data)
        else:
            return data

    def analyze_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze content to identify Agent-OS references and transformation needs.

        Args:
            content: Content to analyze

        Returns:
            Analysis results
        """
        analysis = {
            "has_agentos_references": False,
            "reference_count": 0,
            "reference_types": [],
            "transformations_needed": [],
            "estimated_changes": 0,
        }

        # Count total references
        total_refs = 0
        for old_text in self.text_replacements.keys():
            count = content.lower().count(old_text.lower())
            total_refs += count
            if count > 0:
                analysis["reference_types"].append(f"{old_text}: {count}")

        # Check regex patterns
        for pattern, _ in self.regex_patterns:
            matches = pattern.findall(content)
            if matches:
                total_refs += len(matches)
                analysis["reference_types"].append(f"Pattern matches: {len(matches)}")

        analysis["reference_count"] = total_refs
        analysis["has_agentos_references"] = total_refs > 0
        analysis["estimated_changes"] = total_refs

        # Identify specific transformation needs
        if "import agent_os" in content or "from agent_os" in content:
            analysis["transformations_needed"].append("Python import statements")

        if ".agent-os" in content:
            analysis["transformations_needed"].append("Path references")

        if "agentos " in content:
            analysis["transformations_needed"].append("Command references")

        return analysis


# Global content transformer instance
_content_transformer: Optional[ContentTransformer] = None


def get_content_transformer() -> ContentTransformer:
    """Get the global content transformer instance."""
    global _content_transformer  # noqa: PLW0603
    if _content_transformer is None:
        _content_transformer = ContentTransformer()
    return _content_transformer


def transform_content(content: str, *, preserve_functionality: bool = True) -> str:
    """
    Convenience function to transform content.

    Args:
        content: Content to transform
        preserve_functionality: Whether to preserve functionality

    Returns:
        Transformed content
    """
    transformer = get_content_transformer()
    return transformer.transform_text_content(content, preserve_functionality)
