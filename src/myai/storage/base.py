"""
Base storage interface and exceptions for MyAI.

This module defines the abstract base class for all storage implementations
and common storage-related exceptions.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageError(Exception):
    """Base exception for storage-related errors."""

    pass


class Storage(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        pass

    @abstractmethod
    def read(self, key: str) -> Optional[Dict[str, Any]]:
        """Read data from storage by key."""
        pass

    @abstractmethod
    def write(self, key: str, data: Dict[str, Any]) -> None:
        """Write data to storage with the given key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete data from storage by key. Returns True if deleted."""
        pass

    @abstractmethod
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys in storage, optionally filtered by prefix."""
        pass

    @abstractmethod
    def backup(self, key: str) -> Optional[str]:
        """Create a backup of the data at key. Returns backup identifier."""
        pass

    @abstractmethod
    def restore(self, key: str, backup_id: str) -> bool:
        """Restore data from backup. Returns True if successful."""
        pass

    def read_text(self, key: str) -> Optional[str]:
        """Read raw text data from storage by key."""
        data = self.read(key)
        if data is None:
            return None
        if isinstance(data, dict) and "_content" in data:
            return data["_content"]
        return json.dumps(data, indent=2)

    def write_text(self, key: str, content: str) -> None:
        """Write raw text data to storage with the given key."""
        self.write(key, {"_content": content})

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a storage key."""
        data = self.read(key)
        if data is None:
            return None
        return data.get("_metadata", {})

    def set_metadata(self, key: str, metadata: Dict[str, Any]) -> None:
        """Set metadata for a storage key."""
        data = self.read(key) or {}
        data["_metadata"] = metadata
        self.write(key, data)

    def copy(self, source_key: str, dest_key: str) -> bool:
        """Copy data from source key to destination key."""
        data = self.read(source_key)
        if data is None:
            return False
        self.write(dest_key, data)
        return True

    def move(self, source_key: str, dest_key: str) -> bool:
        """Move data from source key to destination key."""
        if self.copy(source_key, dest_key):
            return self.delete(source_key)
        return False
