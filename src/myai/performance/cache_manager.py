"""
Advanced caching system for MyAI performance optimization.

This module provides multi-level caching with intelligent invalidation,
TTL support, and memory management for optimal performance.
"""

import hashlib
import pickle
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from myai.models.path import PathManager


class CacheLevel(Enum):
    """Cache levels with different characteristics."""

    MEMORY = "memory"  # Fast, volatile, limited size
    DISK = "disk"  # Slower, persistent, larger size
    HYBRID = "hybrid"  # Combination of memory and disk


class CacheEntry:
    """A cache entry with metadata."""

    def __init__(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
        size_bytes: Optional[int] = None,
    ):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.tags = tags or set()
        self.size_bytes = size_bytes or self._calculate_size(value)

        # Timestamps
        self.created_at = time.time()
        self.last_accessed = self.created_at
        self.access_count = 0

        # Metadata
        self.id = str(uuid4())

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Update access time and count."""
        self.last_accessed = time.time()
        self.access_count += 1

    def _calculate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            # Fallback estimation
            if isinstance(value, str):
                return len(value.encode("utf-8"))
            elif isinstance(value, (list, dict)):
                return len(str(value).encode("utf-8"))
            else:
                return 1024  # Default 1KB estimate


class MemoryCache:
    """In-memory cache with LRU eviction."""

    def __init__(self, max_size_mb: int = 100, max_entries: int = 1000):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_entries = max_entries
        self.entries: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.current_size = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key not in self.entries:
            return None

        entry = self.entries[key]

        # Check expiration
        if entry.is_expired():
            self.delete(key)
            return None

        # Update access info
        entry.touch()

        # Move to end of access order (most recent)
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None, tags: Optional[Set[str]] = None) -> bool:
        """Set value in cache."""
        # Create entry
        entry = CacheEntry(key, value, ttl, tags)

        # Remove existing entry if present
        if key in self.entries:
            self.delete(key)

        # Check if we need to evict entries
        while (
            (len(self.entries) >= self.max_entries) or (self.current_size + entry.size_bytes > self.max_size_bytes)
        ) and self.access_order:
            # Evict least recently used
            lru_key = self.access_order[0]
            self.delete(lru_key)

        # Check if entry is too large for cache
        if entry.size_bytes > self.max_size_bytes:
            return False

        # Add entry
        self.entries[key] = entry
        self.access_order.append(key)
        self.current_size += entry.size_bytes

        return True

    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        if key not in self.entries:
            return False

        entry = self.entries[key]
        self.current_size -= entry.size_bytes

        del self.entries[key]
        if key in self.access_order:
            self.access_order.remove(key)

        return True

    def clear(self) -> None:
        """Clear all entries from cache."""
        self.entries.clear()
        self.access_order.clear()
        self.current_size = 0

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired_keys = [key for key, entry in self.entries.items() if entry.is_expired()]

        for key in expired_keys:
            self.delete(key)

        return len(expired_keys)

    def invalidate_by_tags(self, tags: Set[str]) -> int:
        """Invalidate entries matching any of the given tags."""
        matching_keys = [key for key, entry in self.entries.items() if tags & entry.tags]  # Intersection of sets

        for key in matching_keys:
            self.delete(key)

        return len(matching_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_accesses = sum(entry.access_count for entry in self.entries.values())

        return {
            "entries": len(self.entries),
            "max_entries": self.max_entries,
            "size_bytes": self.current_size,
            "max_size_bytes": self.max_size_bytes,
            "size_mb": self.current_size / (1024 * 1024),
            "utilization": self.current_size / max(self.max_size_bytes, 1) * 100,
            "total_accesses": total_accesses,
            "avg_accesses_per_entry": total_accesses / max(len(self.entries), 1),
        }


class DiskCache:
    """Persistent disk cache."""

    def __init__(self, cache_dir: Optional[Path] = None, max_size_mb: int = 1000):
        self.cache_dir = cache_dir or (PathManager().get_user_path() / "cache")
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata: Dict[str, Dict[str, Any]] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Load cache metadata from disk."""
        if not self.metadata_file.exists():
            return {}

        try:
            import json

            with open(self.metadata_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache metadata: {e}")
            return {}

    def _save_metadata(self) -> None:
        """Save cache metadata to disk."""
        try:
            import json

            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving cache metadata: {e}")

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Create hash of key for filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Optional[Any]:
        """Get value from disk cache."""
        if key not in self.metadata:
            return None

        entry_meta = self.metadata[key]

        # Check expiration
        if entry_meta.get("ttl") and time.time() - entry_meta["created_at"] > entry_meta["ttl"]:
            self.delete(key)
            return None

        # Load from disk
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            # Metadata exists but file doesn't - clean up
            del self.metadata[key]
            self._save_metadata()
            return None

        try:
            with open(cache_path, "rb") as f:
                value = pickle.load(f)  # noqa: S301

            # Update access info
            entry_meta["last_accessed"] = time.time()
            entry_meta["access_count"] = entry_meta.get("access_count", 0) + 1
            self._save_metadata()

            return value

        except Exception as e:
            print(f"Error loading cache entry {key}: {e}")
            self.delete(key)
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None, tags: Optional[Set[str]] = None) -> bool:
        """Set value in disk cache."""
        cache_path = self._get_cache_path(key)

        try:
            # Serialize and save to disk
            with open(cache_path, "wb") as f:
                pickle.dump(value, f)

            # Calculate file size
            file_size = cache_path.stat().st_size

            # Update metadata
            self.metadata[key] = {
                "created_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 0,
                "ttl": ttl,
                "tags": list(tags) if tags else [],
                "size_bytes": file_size,
                "file_path": str(cache_path),
            }

            self._save_metadata()

            # Clean up if over size limit
            self._cleanup_if_needed()

            return True

        except Exception as e:
            print(f"Error saving cache entry {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete entry from disk cache."""
        if key not in self.metadata:
            return False

        cache_path = self._get_cache_path(key)

        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception as e:
            print(f"Error deleting cache file {cache_path}: {e}")

        del self.metadata[key]
        self._save_metadata()

        return True

    def clear(self) -> None:
        """Clear all entries from disk cache."""
        # Remove all cache files
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                cache_file.unlink()
            except Exception:  # noqa: S112
                # Ignore errors when removing cache files during cleanup
                continue

        self.metadata.clear()
        self._save_metadata()

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = []

        for key, meta in self.metadata.items():
            if meta.get("ttl") and current_time - meta["created_at"] > meta["ttl"]:
                expired_keys.append(key)

        for key in expired_keys:
            self.delete(key)

        return len(expired_keys)

    def _cleanup_if_needed(self) -> None:
        """Clean up cache if over size limit."""
        total_size = sum(meta.get("size_bytes", 0) for meta in self.metadata.values())

        if total_size <= self.max_size_bytes:
            return

        # Sort by last access time (oldest first)
        sorted_keys = sorted(self.metadata.keys(), key=lambda k: self.metadata[k].get("last_accessed", 0))

        # Remove oldest entries until under size limit
        for key in sorted_keys:
            self.delete(key)
            total_size -= self.metadata.get(key, {}).get("size_bytes", 0)

            if total_size <= self.max_size_bytes * 0.8:  # Leave 20% buffer
                break

    def get_stats(self) -> Dict[str, Any]:
        """Get disk cache statistics."""
        total_size = sum(meta.get("size_bytes", 0) for meta in self.metadata.values())
        total_accesses = sum(meta.get("access_count", 0) for meta in self.metadata.values())

        return {
            "entries": len(self.metadata),
            "size_bytes": total_size,
            "max_size_bytes": self.max_size_bytes,
            "size_mb": total_size / (1024 * 1024),
            "utilization": total_size / max(self.max_size_bytes, 1) * 100,
            "total_accesses": total_accesses,
            "cache_dir": str(self.cache_dir),
        }


class CacheManager:
    """Multi-level cache manager."""

    def __init__(
        self,
        memory_cache_mb: int = 100,
        disk_cache_mb: int = 1000,
        default_ttl: Optional[float] = 3600.0,  # 1 hour
    ):
        self.memory_cache = MemoryCache(max_size_mb=memory_cache_mb)
        self.disk_cache = DiskCache(max_size_mb=disk_cache_mb)
        self.default_ttl = default_ttl

        # Cache categories for easier management
        self.categories = {
            "config": {"ttl": 1800, "tags": {"config"}},  # 30 minutes
            "agent": {"ttl": 3600, "tags": {"agent"}},  # 1 hour
            "integration": {"ttl": 900, "tags": {"integration"}},  # 15 minutes
            "command": {"ttl": 300, "tags": {"command"}},  # 5 minutes
        }

    def get(self, key: str, category: Optional[str] = None) -> Optional[Any]:
        """Get value from cache (memory first, then disk)."""
        # Create namespaced key if category is provided
        cache_key = f"{category}:{key}" if category else key

        # Try memory cache first
        value = self.memory_cache.get(cache_key)
        if value is not None:
            self._track_hit()
            return value

        # Try disk cache
        value = self.disk_cache.get(cache_key)
        if value is not None:
            # Promote to memory cache
            category_config = self.categories.get(category or "", {})
            ttl_raw = category_config.get("ttl", self.default_ttl)
            ttl = float(ttl_raw) if isinstance(ttl_raw, (int, float)) else self.default_ttl
            tags_raw = category_config.get("tags")
            tags = set(tags_raw) if isinstance(tags_raw, list) else None

            self.memory_cache.set(cache_key, value, ttl=ttl, tags=tags)
            self._track_hit()
            return value

        self._track_miss()
        return None

    def set(
        self,
        key: str,
        value: Any,
        category: Optional[str] = None,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
        *,
        memory_only: bool = False,
    ) -> bool:
        """Set value in cache."""
        # Create namespaced key if category is provided
        cache_key = f"{category}:{key}" if category else key

        # Use category configuration if available
        category_config = self.categories.get(category or "", {})
        if ttl is None:
            ttl_raw = category_config.get("ttl", self.default_ttl)
            ttl = float(ttl_raw) if isinstance(ttl_raw, (int, float)) else self.default_ttl
        if tags is None:
            tags_raw = category_config.get("tags", set())
            tags = set(tags_raw) if isinstance(tags_raw, (list, set)) else set()

        # Set in memory cache
        memory_success = self.memory_cache.set(cache_key, value, ttl=ttl, tags=tags)

        if memory_only:
            return memory_success

        # Set in disk cache
        disk_success = self.disk_cache.set(cache_key, value, ttl=ttl, tags=tags)

        self._track_set()
        return memory_success or disk_success

    def delete(self, key: str) -> bool:
        """Delete from both caches."""
        memory_deleted = self.memory_cache.delete(key)
        disk_deleted = self.disk_cache.delete(key)
        return memory_deleted or disk_deleted

    def clear(self, category: Optional[str] = None) -> None:
        """Clear cache entries."""
        if category:
            # Clear by category tags
            category_config = self.categories.get(category, {})
            tags_raw = category_config.get("tags", set())
            tags = set(tags_raw) if isinstance(tags_raw, (list, set)) else set()
            if tags:
                self.memory_cache.invalidate_by_tags(tags)
                # Disk cache doesn't support tag-based invalidation yet
        else:
            # Clear everything
            self.memory_cache.clear()
            self.disk_cache.clear()

    def cleanup(self) -> Dict[str, int]:
        """Clean up expired entries from both caches."""
        memory_cleaned = self.memory_cache.cleanup_expired()
        disk_cleaned = self.disk_cache.cleanup_expired()

        return {
            "memory_cleaned": memory_cleaned,
            "disk_cleaned": disk_cleaned,
            "total_cleaned": memory_cleaned + disk_cleaned,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics with additional metrics."""
        memory_stats = self.memory_cache.get_stats()
        disk_stats = self.disk_cache.get_stats()

        stats = {
            "memory": memory_stats,
            "disk": disk_stats,
            "total_entries": memory_stats["entries"] + disk_stats["entries"],
            "total_size_mb": memory_stats["size_mb"] + disk_stats["size_mb"],
            "categories": list(self.categories.keys()),
        }

        # Add hit/miss tracking (simplified implementation)
        stats.update(
            {
                "hits": getattr(self, "_hits", 0),
                "misses": getattr(self, "_misses", 0),
                "sets": getattr(self, "_sets", 0),
                "memory_size": memory_stats["entries"],
            }
        )

        return stats

    def cached(
        self,
        key: Optional[str] = None,
        category: Optional[str] = None,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> Callable:
        """Decorator for caching function results."""

        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                # Generate cache key if not provided
                cache_key = key
                if cache_key is None:
                    # Create key from function name and arguments
                    args_str = str(args) + str(sorted(kwargs.items()))
                    cache_key = f"{func.__name__}:{hashlib.md5(args_str.encode()).hexdigest()}"  # noqa: S324

                # Try to get from cache
                cached_result = self.get(cache_key, category)
                if cached_result is not None:
                    return cached_result

                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, category=category, ttl=ttl, tags=tags)

                return result

            return wrapper

        return decorator

    def get_by_tag(self, tag: str) -> List[Any]:
        """Get all values that have the specified tag."""
        values = []

        # Search memory cache
        for entry in self.memory_cache.entries.values():
            if tag in entry.tags:
                values.append(entry.value)

        # Search disk cache (limited implementation)
        for key, meta in self.disk_cache.metadata.items():
            if tag in meta.get("tags", []):
                value = self.disk_cache.get(key)
                if value is not None and value not in values:
                    values.append(value)

        return values

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache key."""
        return self.delete(key)

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with the specified tag."""
        # Collect all unique keys from both caches that have the tag
        all_keys = set()

        # Memory cache keys with the tag
        for key, entry in self.memory_cache.entries.items():
            if tag in entry.tags:
                all_keys.add(key)

        # Disk cache keys with the tag
        for key, meta in self.disk_cache.metadata.items():
            if tag in meta.get("tags", []):
                all_keys.add(key)

        # Delete from both caches
        count = 0
        for key in all_keys:
            memory_deleted = self.memory_cache.delete(key)
            disk_deleted = self.disk_cache.delete(key)
            if memory_deleted or disk_deleted:
                count += 1

        return count

    def invalidate_by_category(self, category: str) -> int:
        """Invalidate all entries in the specified category."""
        prefix = f"{category}:"

        # Collect all unique keys from both caches
        all_keys = set()

        # Memory cache keys
        for key in self.memory_cache.entries.keys():
            if key.startswith(prefix):
                all_keys.add(key)

        # Disk cache keys
        for key in self.disk_cache.metadata.keys():
            if key.startswith(prefix):
                all_keys.add(key)

        # Delete from both caches
        count = 0
        for key in all_keys:
            memory_deleted = self.memory_cache.delete(key)
            disk_deleted = self.disk_cache.delete(key)
            if memory_deleted or disk_deleted:
                count += 1

        return count

    def cleanup_expired(self) -> int:
        """Clean up expired entries from both caches."""
        cleanup_result = self.cleanup()
        return cleanup_result.get("total_cleaned", 0)

    def _track_hit(self) -> None:
        """Track a cache hit."""
        self._hits = getattr(self, "_hits", 0) + 1

    def _track_miss(self) -> None:
        """Track a cache miss."""
        self._misses = getattr(self, "_misses", 0) + 1

    def _track_set(self) -> None:
        """Track a cache set operation."""
        self._sets = getattr(self, "_sets", 0) + 1


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager  # noqa: PLW0603
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
