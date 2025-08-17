"""
Filesystem-based storage implementation for MyAI.

This module provides a concrete implementation of the Storage interface
that persists data to the local filesystem using JSON files.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from myai.storage.base import Storage, StorageError


class FileSystemStorage(Storage):
    """Filesystem-based storage implementation."""

    def __init__(self, base_path: Path, *, create_dirs: bool = True):
        """
        Initialize filesystem storage.

        Args:
            base_path: Base directory for storage
            create_dirs: Whether to create directories if they don't exist
        """
        self.base_path = Path(base_path)
        self.backup_path = self.base_path / "_backups"

        if create_dirs:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self.backup_path.mkdir(parents=True, exist_ok=True)

            # Set secure permissions
            self.base_path.chmod(0o700)
            self.backup_path.chmod(0o700)

    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a given key."""
        # Sanitize key to prevent directory traversal while preserving hierarchy
        # Remove any .. components and normalize path separators
        key_parts = []
        for part in key.replace("\\", "/").split("/"):
            if part and part != ".." and part != ".":
                # Further sanitize each part
                safe_part = part.replace("..", "")
                if safe_part:
                    key_parts.append(safe_part)

        if not key_parts:
            msg = "Invalid key: empty after sanitization"
            raise ValueError(msg)

        # Create hierarchical path
        return self.base_path / Path(*key_parts).with_suffix(".json")

    def _get_backup_path(self, key: str, backup_id: str) -> Path:
        """Get the backup file path for a given key and backup ID."""
        # For backups, flatten the key to avoid deep directory structures
        safe_key = key.replace("..", "").replace("/", "_").replace("\\", "_")
        return self.backup_path / f"{safe_key}_{backup_id}.json"

    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        return self._get_file_path(key).exists()

    def read(self, key: str) -> Optional[Dict[str, Any]]:
        """Read data from storage by key."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        try:
            with file_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            msg = f"Failed to read {key}: {e}"
            raise StorageError(msg) from e

    def write(self, key: str, data: Dict[str, Any]) -> None:
        """Write data to storage with the given key."""
        file_path = self._get_file_path(key)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Add metadata, preserving existing user metadata
        existing_metadata = data.get("_metadata", {})
        system_metadata = {
            "key": key,
            "created": existing_metadata.get("created", datetime.now(timezone.utc).isoformat()),
            "modified": datetime.now(timezone.utc).isoformat(),
            "size": len(json.dumps(data)),
        }

        # Merge user metadata with system metadata
        enhanced_metadata = {**existing_metadata, **system_metadata}

        enhanced_data = {**data, "_metadata": enhanced_metadata}

        try:
            # Write to temporary file first, then move (atomic operation)
            temp_path = file_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)

            temp_path.replace(file_path)
            file_path.chmod(0o600)  # Secure permissions

        except OSError as e:
            # Clean up temp file if it exists
            temp_path = file_path.with_suffix(".tmp")
            if temp_path.exists():
                temp_path.unlink()
            msg = f"Failed to write {key}: {e}"
            raise StorageError(msg) from e

    def delete(self, key: str) -> bool:
        """Delete data from storage by key."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            return True
        except OSError as e:
            msg = f"Failed to delete {key}: {e}"
            raise StorageError(msg) from e

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys in storage, optionally filtered by prefix."""
        if not self.base_path.exists():
            return []

        keys = []

        try:
            for file_path in self.base_path.rglob("*.json"):
                if file_path.parent == self.backup_path:
                    continue  # Skip backup files

                # Convert file path back to key
                relative_path = file_path.relative_to(self.base_path)
                key = str(relative_path.with_suffix("")).replace("\\", "/")  # Normalize separators

                if prefix is None or key.startswith(prefix):
                    keys.append(key)

        except OSError as e:
            msg = f"Failed to list keys: {e}"
            raise StorageError(msg) from e

        return sorted(keys)

    def backup(self, key: str) -> Optional[str]:
        """Create a backup of the data at key."""
        if not self.exists(key):
            return None

        backup_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        source_path = self._get_file_path(key)
        backup_path = self._get_backup_path(key, backup_id)

        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, backup_path)
            backup_path.chmod(0o600)
            return backup_id
        except OSError as e:
            msg = f"Failed to backup {key}: {e}"
            raise StorageError(msg) from e

    def restore(self, key: str, backup_id: str) -> bool:
        """Restore data from backup."""
        backup_path = self._get_backup_path(key, backup_id)

        if not backup_path.exists():
            return False

        target_path = self._get_file_path(key)

        try:
            # Create backup of current data before restore
            if target_path.exists():
                self.backup(key)

            shutil.copy2(backup_path, target_path)
            target_path.chmod(0o600)
            return True
        except OSError as e:
            msg = f"Failed to restore {key} from {backup_id}: {e}"
            raise StorageError(msg) from e

    def list_backups(self, key: str) -> List[str]:
        """List all backup IDs for a given key."""
        if not self.backup_path.exists():
            return []

        safe_key = key.replace("..", "").replace("/", "_").replace("\\", "_")
        pattern = f"{safe_key}_*.json"

        backup_ids = []
        for backup_file in self.backup_path.glob(pattern):
            # Extract backup ID from filename
            filename = backup_file.stem
            backup_id = filename[len(safe_key) + 1 :]  # +1 for underscore
            backup_ids.append(backup_id)

        return sorted(backup_ids, reverse=True)  # Most recent first

    def cleanup_backups(self, key: str, keep_count: int = 5) -> int:
        """Clean up old backups, keeping only the most recent ones."""
        backup_ids = self.list_backups(key)

        if len(backup_ids) <= keep_count:
            return 0

        deleted_count = 0
        for backup_id in backup_ids[keep_count:]:
            backup_path = self._get_backup_path(key, backup_id)
            try:
                backup_path.unlink()
                deleted_count += 1
            except OSError:
                pass  # Ignore errors when cleaning up

        return deleted_count

    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the storage."""
        total_files = 0
        total_size = 0
        backup_files = 0
        backup_size = 0

        if self.base_path.exists():
            for file_path in self.base_path.rglob("*.json"):
                if file_path.parent == self.backup_path:
                    backup_files += 1
                    backup_size += file_path.stat().st_size
                else:
                    total_files += 1
                    total_size += file_path.stat().st_size

        return {
            "base_path": str(self.base_path),
            "total_files": total_files,
            "total_size_bytes": total_size,
            "backup_files": backup_files,
            "backup_size_bytes": backup_size,
            "exists": self.base_path.exists(),
        }
