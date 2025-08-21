"""
Reusable content management utilities for auto-generated sections in files.

This module provides a scalable way to manage auto-generated content within
user-editable files using comment markers.
"""

import re
from pathlib import Path
from typing import Optional, Tuple


class ContentMarkerManager:
    """Manage auto-generated content sections within files using comment markers."""

    def __init__(self, marker_prefix: str = "MYAI", comment_style: str = "html"):
        """
        Initialize the content marker manager.

        Args:
            marker_prefix: Prefix for marker comments (e.g., "MYAI")
            comment_style: Style of comments ("html", "markdown", "python", "shell")
        """
        self.marker_prefix = marker_prefix
        self.comment_style = comment_style
        self._setup_comment_format()

    def _setup_comment_format(self) -> None:
        """Set up comment format based on style."""
        formats = {
            "html": ("<!-- ", " -->"),
            "markdown": ("<!-- ", " -->"),
            "python": ("# ", ""),
            "shell": ("# ", ""),
            "javascript": ("// ", ""),
            "json": ('"_comment_', '": "_"'),  # Special handling for JSON
        }
        self.comment_start, self.comment_end = formats.get(self.comment_style, formats["html"])

    def create_marker(self, section_name: str, marker_type: str = "START") -> str:
        """
        Create a marker comment.

        Args:
            section_name: Name of the section (e.g., "AGENTS", "CONFIG")
            marker_type: Type of marker ("START" or "END")

        Returns:
            Formatted marker comment
        """
        marker = f"{self.marker_prefix}:{section_name}:{marker_type}"
        return f"{self.comment_start}{marker}{self.comment_end}"

    def wrap_content(self, content: str, section_name: str) -> str:
        """
        Wrap content with start/end markers.

        Args:
            content: Content to wrap
            section_name: Name of the section

        Returns:
            Content wrapped with markers
        """
        start_marker = self.create_marker(section_name, "START")
        end_marker = self.create_marker(section_name, "END")
        return f"{start_marker}\n{content}\n{end_marker}"

    def extract_sections(self, content: str) -> dict[str, Tuple[str, int, int]]:
        """
        Extract all managed sections from content.

        Args:
            content: Full file content

        Returns:
            Dictionary mapping section names to (content, start_pos, end_pos)
        """
        sections = {}

        # Build regex pattern for markers
        escaped_start = re.escape(self.comment_start)
        escaped_end = re.escape(self.comment_end)
        pattern = (
            f"{escaped_start}"
            f"{re.escape(self.marker_prefix)}:"
            f"([^:]+):START"  # Capture section name
            f"{escaped_end}"
            f"(.*?)"  # Capture content (non-greedy)
            f"{escaped_start}"
            f"{re.escape(self.marker_prefix)}:"
            f"\\1:END"  # Match same section name
            f"{escaped_end}"
        )

        # Find all sections
        for match in re.finditer(pattern, content, re.DOTALL):
            section_name = match.group(1)
            section_content = match.group(2).strip()
            sections[section_name] = (section_content, match.start(), match.end())

        return sections

    def detect_broken_markers(self, content: str) -> list[str]:
        """
        Detect broken or mismatched markers in content.

        Returns:
            List of warning messages about broken markers
        """
        warnings = []

        # Find all START markers
        start_pattern = (
            f"{re.escape(self.comment_start)}{re.escape(self.marker_prefix)}:([^:]+):START{re.escape(self.comment_end)}"
        )
        start_markers = [(m.group(1), m.start()) for m in re.finditer(start_pattern, content)]

        # Find all END markers
        end_pattern = (
            f"{re.escape(self.comment_start)}{re.escape(self.marker_prefix)}:([^:]+):END{re.escape(self.comment_end)}"
        )
        end_markers = [(m.group(1), m.start()) for m in re.finditer(end_pattern, content)]

        # Check for unmatched START markers
        start_sections = {name for name, _ in start_markers}
        end_sections = {name for name, _ in end_markers}

        for section in start_sections - end_sections:
            warnings.append(
                f"Found {self.marker_prefix}:{section}:START marker without matching END marker. "
                "The section may have been accidentally modified."
            )

        for section in end_sections - start_sections:
            warnings.append(
                f"Found {self.marker_prefix}:{section}:END marker without matching START marker. "
                "The section may have been accidentally modified."
            )

        # Check for nested or out-of-order markers
        all_markers = [(name, pos, "START") for name, pos in start_markers]
        all_markers.extend([(name, pos, "END") for name, pos in end_markers])
        all_markers.sort(key=lambda x: x[1])  # Sort by position

        open_sections = []
        for name, _, marker_type in all_markers:
            if marker_type == "START":
                if name in open_sections:
                    warnings.append(
                        f"Found nested {self.marker_prefix}:{name}:START markers. This may cause unexpected behavior."
                    )
                open_sections.append(name)
            elif open_sections and open_sections[-1] == name:
                open_sections.pop()
            elif name in open_sections:
                warnings.append(
                    f"Found {self.marker_prefix}:{name}:END marker out of order. "
                    f"Expected {self.marker_prefix}:{open_sections[-1]}:END first."
                )

        return warnings

    def update_section(self, content: str, section_name: str, new_content: str, *, check_warnings: bool = True) -> str:
        """
        Update a specific managed section in content.

        Args:
            content: Full file content
            section_name: Name of section to update
            new_content: New content for the section
            check_warnings: Whether to check for broken markers

        Returns:
            Updated full content

        Raises:
            ValueError: If broken markers are detected and check_warnings is True
        """
        # Check for broken markers if requested
        if check_warnings:
            warnings = self.detect_broken_markers(content)
            if warnings:
                warning_msg = "\n".join(warnings)
                msg = (
                    f"Detected broken or mismatched markers in file:\n{warning_msg}\n\n"
                    "Please fix the markers manually or remove them to allow automatic management."
                )
                raise ValueError(msg)

        sections = self.extract_sections(content)

        if section_name in sections:
            # Replace existing section
            _, start_pos, end_pos = sections[section_name]
            wrapped_content = self.wrap_content(new_content, section_name)
            return content[:start_pos] + wrapped_content + content[end_pos:]
        else:
            # Section doesn't exist - append it
            wrapped_content = self.wrap_content(new_content, section_name)
            if content and not content.endswith("\n"):
                content += "\n"
            return content + "\n" + wrapped_content

    def remove_section(self, content: str, section_name: str) -> str:
        """
        Remove a managed section from content.

        Args:
            content: Full file content
            section_name: Name of section to remove

        Returns:
            Updated content with section removed
        """
        sections = self.extract_sections(content)

        if section_name not in sections:
            return content

        _, start_pos, end_pos = sections[section_name]

        # Remove the section and clean up extra newlines
        before = content[:start_pos].rstrip()
        after = content[end_pos:].lstrip()

        if before and after:
            return before + "\n\n" + after
        elif before:
            return before
        else:
            return after

    def has_section(self, content: str, section_name: str) -> bool:
        """Check if a section exists in content."""
        sections = self.extract_sections(content)
        return section_name in sections

    def read_and_update_file(
        self,
        file_path: Path,
        section_name: str,
        new_content: str,
        *,
        create_if_missing: bool = True,
        check_warnings: bool = True,
    ) -> None:
        """
        Read a file and update a managed section.

        Args:
            file_path: Path to file
            section_name: Name of section to update
            new_content: New content for the section
            create_if_missing: Whether to create file if it doesn't exist
            check_warnings: Whether to check for broken markers

        Raises:
            ValueError: If broken markers are detected and check_warnings is True
        """
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        elif create_if_missing:
            content = ""
        else:
            msg = f"File not found: {file_path}"
            raise FileNotFoundError(msg)

        updated_content = self.update_section(content, section_name, new_content, check_warnings=check_warnings)
        file_path.write_text(updated_content, encoding="utf-8")


# Convenience functions for common use cases
def update_managed_section(
    file_path: Path,
    section_name: str,
    new_content: str,
    marker_prefix: str = "MYAI",
    comment_style: Optional[str] = None,
) -> None:
    """
    Update a managed section in a file.

    Args:
        file_path: Path to file
        section_name: Name of section (e.g., "AGENTS")
        new_content: New content for the section
        marker_prefix: Prefix for markers (default: "MYAI")
        comment_style: Comment style, auto-detected if None
    """
    if comment_style is None:
        # Auto-detect based on file extension
        ext = file_path.suffix.lower()
        style_map = {
            ".md": "markdown",
            ".py": "python",
            ".sh": "shell",
            ".js": "javascript",
            ".ts": "javascript",
        }
        comment_style = style_map.get(ext, "html")

    manager = ContentMarkerManager(marker_prefix, comment_style)
    manager.read_and_update_file(file_path, section_name, new_content)
