"""
Path translation utilities for Agent-OS to MyAI migration.

This module provides utilities to translate paths between Agent-OS and MyAI
directory structures, enabling seamless migration and compatibility.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Union


class PathTranslator:
    """Handles path translation between Agent-OS and MyAI directory structures."""

    def __init__(self):
        self.home = Path.home()
        self.agentos_root = self.home / ".agent-os"
        self.myai_root = self.home / ".myai"

        # Define path mappings
        self.path_mappings = {
            # Agent-OS -> MyAI
            str(self.agentos_root / "agents"): str(self.myai_root / "agents"),
            str(self.agentos_root / "config"): str(self.myai_root / "config"),
            str(self.agentos_root / "templates"): str(self.myai_root / "templates"),
            str(self.agentos_root / "hooks"): str(self.myai_root / "data" / "hooks"),
            str(self.agentos_root / "cache"): str(self.myai_root / "cache"),
            str(self.agentos_root / "logs"): str(self.myai_root / "logs"),
            str(self.agentos_root / "backups"): str(self.myai_root / "backups"),
        }

        # Reverse mappings for MyAI -> Agent-OS
        self.reverse_mappings = {v: k for k, v in self.path_mappings.items()}

    def translate_to_myai(self, agentos_path: Union[str, Path]) -> Optional[Path]:
        """
        Translate an Agent-OS path to the corresponding MyAI path.

        Args:
            agentos_path: Agent-OS path to translate

        Returns:
            Corresponding MyAI path, or None if no mapping exists
        """
        agentos_str = str(agentos_path)

        # Check for exact matches first
        if agentos_str in self.path_mappings:
            return Path(self.path_mappings[agentos_str])

        # Check for parent directory matches
        for agentos_dir, myai_dir in self.path_mappings.items():
            if agentos_str.startswith(agentos_dir):
                # Replace the parent directory part
                relative_path = agentos_str[len(agentos_dir) :].lstrip(os.sep)
                return Path(myai_dir) / relative_path

        return None

    def translate_to_agentos(self, myai_path: Union[str, Path]) -> Optional[Path]:
        """
        Translate a MyAI path to the corresponding Agent-OS path.

        Args:
            myai_path: MyAI path to translate

        Returns:
            Corresponding Agent-OS path, or None if no mapping exists
        """
        myai_str = str(myai_path)

        # Check for exact matches first
        if myai_str in self.reverse_mappings:
            return Path(self.reverse_mappings[myai_str])

        # Check for parent directory matches
        for myai_dir, agentos_dir in self.reverse_mappings.items():
            if myai_str.startswith(myai_dir):
                # Replace the parent directory part
                relative_path = myai_str[len(myai_dir) :].lstrip(os.sep)
                return Path(agentos_dir) / relative_path

        return None

    def is_agentos_path(self, path: Union[str, Path]) -> bool:
        """Check if a path is within the Agent-OS directory structure."""
        path_str = str(path)
        return path_str.startswith(str(self.agentos_root))

    def is_myai_path(self, path: Union[str, Path]) -> bool:
        """Check if a path is within the MyAI directory structure."""
        path_str = str(path)
        return path_str.startswith(str(self.myai_root))

    def create_myai_structure(self) -> None:
        """Create the MyAI directory structure based on Agent-OS."""
        # Create base MyAI directory
        self.myai_root.mkdir(exist_ok=True)

        # Create all mapped directories
        for myai_dir in self.path_mappings.values():
            Path(myai_dir).mkdir(parents=True, exist_ok=True)

    def get_migration_plan(self) -> Dict[str, Dict[str, Union[str, bool]]]:
        """
        Generate a migration plan showing what files would be moved.

        Returns:
            Dictionary with migration details for each Agent-OS directory
        """
        plan = {}

        for agentos_dir, myai_dir in self.path_mappings.items():
            agentos_path = Path(agentos_dir)
            myai_path = Path(myai_dir)

            plan[agentos_dir] = {
                "target": myai_dir,
                "exists": agentos_path.exists(),
                "files": len(list(agentos_path.rglob("*"))) if agentos_path.exists() else 0,
                "target_exists": myai_path.exists(),
            }

        return plan

    def migrate_file(self, agentos_path: Path, *, dry_run: bool = False) -> Dict[str, Union[str, bool]]:
        """
        Migrate a single file from Agent-OS to MyAI structure.

        Args:
            agentos_path: Source file path in Agent-OS structure
            dry_run: If True, don't actually move files

        Returns:
            Migration result dictionary
        """
        result = {
            "source": str(agentos_path),
            "target": "",
            "success": False,
            "error": "",
            "skipped": False,
        }

        # Translate path
        myai_path = self.translate_to_myai(agentos_path)
        if not myai_path:
            result["error"] = "No mapping found for path"
            result["skipped"] = True
            return result

        result["target"] = str(myai_path)

        # Check if source exists
        if not agentos_path.exists():
            result["error"] = "Source file does not exist"
            return result

        if dry_run:
            result["success"] = True
            result["skipped"] = True
            return result

        try:
            # Create target directory if needed
            myai_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file (don't remove original for safety)
            if agentos_path.is_file():
                import shutil

                shutil.copy2(agentos_path, myai_path)
            elif agentos_path.is_dir():
                import shutil

                shutil.copytree(agentos_path, myai_path, dirs_exist_ok=True)

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def intercept_path(self, original_path: Union[str, Path]) -> Path:
        """
        Intercept a path and redirect Agent-OS paths to MyAI equivalents.

        This is the main interception method that other parts of the system
        can use to transparently handle path translation.

        Args:
            original_path: The original path that might be Agent-OS

        Returns:
            MyAI path if translation is possible, otherwise original path
        """
        if self.is_agentos_path(original_path):
            myai_path = self.translate_to_myai(original_path)
            if myai_path:
                return myai_path

        return Path(original_path)

    def get_legacy_paths(self) -> list[str]:
        """Get all legacy Agent-OS paths that should be redirected."""
        return list(self.path_mappings.keys())

    def get_myai_paths(self) -> list[str]:
        """Get all MyAI paths that are mapped from Agent-OS."""
        return list(self.path_mappings.values())


# Global path translator instance
_path_translator: Optional[PathTranslator] = None


def get_path_translator() -> PathTranslator:
    """Get the global path translator instance."""
    global _path_translator  # noqa: PLW0603
    if _path_translator is None:
        _path_translator = PathTranslator()
    return _path_translator


def translate_path(path: Union[str, Path], *, to_myai: bool = True) -> Optional[Path]:
    """
    Convenience function to translate paths.

    Args:
        path: Path to translate
        to_myai: If True, translate Agent-OS->MyAI, else MyAI->Agent-OS

    Returns:
        Translated path or None
    """
    translator = get_path_translator()
    if to_myai:
        return translator.translate_to_myai(path)
    else:
        return translator.translate_to_agentos(path)


def intercept_path(path: Union[str, Path]) -> Path:
    """
    Convenience function to intercept and redirect paths.

    Args:
        path: Original path

    Returns:
        Intercepted path (MyAI if applicable, otherwise original)
    """
    translator = get_path_translator()
    return translator.intercept_path(path)
