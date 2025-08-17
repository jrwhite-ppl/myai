"""
File permission management for MyAI.

This module provides secure file operations with proper permission management
to protect configuration files, agent specifications, and other sensitive data.
"""

import os
import stat
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SecureFileMode(Enum):
    """Secure file permission modes."""

    PRIVATE_FILE = 0o600  # rw-------
    PRIVATE_DIR = 0o700  # rwx------
    SHARED_FILE = 0o644  # rw-r--r--
    SHARED_DIR = 0o755  # rwxr-xr-x
    EXECUTABLE = 0o755  # rwxr-xr-x


class MyAIPermissionError(Exception):
    """Exception raised for permission-related errors."""

    pass


class FilePermissionManager:
    """Manages file permissions for secure operations."""

    def __init__(self):
        """Initialize the file permission manager."""
        self._sensitive_patterns = ["config", "credentials", "tokens", "keys", ".env", "secrets"]

    def create_secure_file(self, file_path: Path, content: str = "", mode: Optional[SecureFileMode] = None) -> None:
        """
        Create a file with secure permissions.

        Args:
            file_path: Path to the file to create
            content: Initial content for the file
            mode: File permission mode (defaults to PRIVATE_FILE for sensitive files)
        """
        # Determine appropriate mode
        if mode is None:
            mode = self._get_default_mode(file_path, is_directory=False)

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        self.secure_directory(file_path.parent)

        # Create file with secure permissions
        try:
            # Create file with restricted permissions
            fd = os.open(file_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, mode.value)
            try:
                if content:
                    os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)

            # Verify permissions were set correctly
            self.verify_permissions(file_path, mode)

        except OSError as e:
            msg = f"Failed to create secure file {file_path}: {e}"
            raise MyAIPermissionError(msg) from e

    def create_secure_directory(self, dir_path: Path, mode: Optional[SecureFileMode] = None) -> None:
        """
        Create a directory with secure permissions.

        Args:
            dir_path: Path to the directory to create
            mode: Directory permission mode (defaults to PRIVATE_DIR for sensitive dirs)
        """
        # Determine appropriate mode
        if mode is None:
            mode = self._get_default_mode(dir_path, is_directory=True)

        try:
            # Create directory with secure permissions
            dir_path.mkdir(parents=True, exist_ok=True, mode=mode.value)

            # Ensure permissions are correct (mkdir might not set them exactly)
            os.chmod(dir_path, mode.value)

            # Verify permissions
            self.verify_permissions(dir_path, mode)

        except OSError as e:
            msg = f"Failed to create secure directory {dir_path}: {e}"
            raise MyAIPermissionError(msg) from e

    def secure_existing_file(self, file_path: Path, mode: Optional[SecureFileMode] = None) -> None:
        """
        Secure an existing file by setting appropriate permissions.

        Args:
            file_path: Path to the file to secure
            mode: File permission mode (auto-detected if None)
        """
        if not file_path.exists():
            msg = f"File does not exist: {file_path}"
            raise MyAIPermissionError(msg)

        if mode is None:
            mode = self._get_default_mode(file_path, is_directory=False)

        try:
            os.chmod(file_path, mode.value)
            self.verify_permissions(file_path, mode)
        except OSError as e:
            msg = f"Failed to secure file {file_path}: {e}"
            raise MyAIPermissionError(msg) from e

    def secure_directory(
        self, dir_path: Path, mode: Optional[SecureFileMode] = None, *, recursive: bool = False
    ) -> None:
        """
        Secure a directory by setting appropriate permissions.

        Args:
            dir_path: Path to the directory to secure
            mode: Directory permission mode (auto-detected if None)
            recursive: Whether to secure subdirectories recursively
        """
        if not dir_path.exists():
            msg = f"Directory does not exist: {dir_path}"
            raise MyAIPermissionError(msg)

        if mode is None:
            mode = self._get_default_mode(dir_path, is_directory=True)

        try:
            # Secure the directory itself
            os.chmod(dir_path, mode.value)
            self.verify_permissions(dir_path, mode)

            if recursive:
                # Secure all subdirectories and files
                for item in dir_path.rglob("*"):
                    if item.is_dir():
                        self.secure_directory(item, mode, recursive=False)
                    else:
                        file_mode = self._get_default_mode(item, is_directory=False)
                        self.secure_existing_file(item, file_mode)

        except OSError as e:
            msg = f"Failed to secure directory {dir_path}: {e}"
            raise MyAIPermissionError(msg) from e

    def verify_permissions(self, path: Path, expected_mode: SecureFileMode) -> bool:
        """
        Verify that a file or directory has the expected permissions.

        Args:
            path: Path to check
            expected_mode: Expected permission mode

        Returns:
            True if permissions match, False otherwise

        Raises:
            PermissionError: If permissions don't match
        """
        if not path.exists():
            msg = f"Path does not exist: {path}"
            raise MyAIPermissionError(msg)

        try:
            stat.filemode(path.stat().st_mode)
            expected_octal = oct(expected_mode.value)
            actual_octal = oct(path.stat().st_mode & 0o777)

            if actual_octal != expected_octal:
                msg = f"Permission mismatch for {path}: expected {expected_octal}, got {actual_octal}"
                raise MyAIPermissionError(msg)

            return True

        except OSError as e:
            msg = f"Failed to verify permissions for {path}: {e}"
            raise MyAIPermissionError(msg) from e

    def check_permissions(self, path: Path) -> Dict[str, bool]:
        """
        Check permissions for a file or directory.

        Args:
            path: Path to check

        Returns:
            Dictionary with permission flags
        """
        if not path.exists():
            return {}

        mode = path.stat().st_mode

        return {
            "readable": bool(mode & stat.S_IRUSR),
            "writable": bool(mode & stat.S_IWUSR),
            "executable": bool(mode & stat.S_IXUSR),
            "group_readable": bool(mode & stat.S_IRGRP),
            "group_writable": bool(mode & stat.S_IWGRP),
            "group_executable": bool(mode & stat.S_IXGRP),
            "other_readable": bool(mode & stat.S_IROTH),
            "other_writable": bool(mode & stat.S_IWOTH),
            "other_executable": bool(mode & stat.S_IXOTH),
        }

    def repair_permissions(self, root_path: Path, *, fix_issues: bool = False) -> List[Dict[str, Any]]:
        """
        Scan and optionally repair permission issues.

        Args:
            root_path: Root path to scan
            fix_issues: Whether to fix issues found

        Returns:
            List of issues found (and optionally fixed)
        """
        issues: List[Dict[str, Any]] = []

        for path in root_path.rglob("*"):
            try:
                expected_mode = self._get_default_mode(path, is_directory=path.is_dir())

                # Check if permissions match expected
                try:
                    self.verify_permissions(path, expected_mode)
                except MyAIPermissionError as e:
                    issue: Dict[str, Any] = {"path": str(path), "issue": str(e), "fixed": False}

                    if fix_issues:
                        try:
                            if path.is_dir():
                                self.secure_directory(path, expected_mode)
                            else:
                                self.secure_existing_file(path, expected_mode)
                            issue["fixed"] = True
                        except MyAIPermissionError:
                            issue["fix_error"] = "Failed to fix permissions"

                    issues.append(issue)

            except OSError:
                # Skip files we can't access
                continue

        return issues

    def is_sensitive_path(self, path: Path) -> bool:
        """
        Check if a path contains sensitive data.

        Args:
            path: Path to check

        Returns:
            True if path appears to contain sensitive data
        """
        path_str = str(path).lower()

        return any(pattern in path_str for pattern in self._sensitive_patterns)

    def _get_default_mode(self, path: Path, *, is_directory: bool) -> SecureFileMode:
        """
        Get the default permission mode for a path.

        Args:
            path: Path to determine mode for
            is_directory: Whether the path is a directory

        Returns:
            Appropriate SecureFileMode
        """
        # Check if this is a sensitive path
        if self.is_sensitive_path(path):
            return SecureFileMode.PRIVATE_DIR if is_directory else SecureFileMode.PRIVATE_FILE

        # Check for executable files
        if not is_directory and (path.suffix in {".sh", ".py", ".exe", ".bat"} or "bin" in str(path)):
            return SecureFileMode.EXECUTABLE

        # Default modes
        return SecureFileMode.SHARED_DIR if is_directory else SecureFileMode.SHARED_FILE


class PermissionConfig(BaseModel):
    """Configuration for permission management."""

    strict_mode: bool = True
    auto_repair: bool = False
    sensitive_patterns: List[str] = []
    custom_modes: Dict[str, int] = {}

    def __init__(self, **data):
        """Initialize with default sensitive patterns."""
        if "sensitive_patterns" not in data:
            data["sensitive_patterns"] = ["config", "credentials", "tokens", "keys", ".env", "secrets", "myai"]
        super().__init__(**data)
