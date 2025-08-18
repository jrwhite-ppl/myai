"""
Tests for cache manager functionality.
"""

import tempfile
import time
from pathlib import Path

from myai.performance.cache_manager import CacheEntry, CacheManager


class TestCacheEntry:
    """Test cases for the CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(
            key="test-key",
            value="test-value",
            ttl=300,
            tags={"tag1", "tag2"},
        )

        assert entry.key == "test-key"
        assert entry.value == "test-value"
        assert entry.ttl == 300
        assert entry.tags == {"tag1", "tag2"}
        assert not entry.is_expired()

    def test_cache_entry_expiration(self):
        """Test cache entry expiration."""
        # Create entry with very short TTL
        entry = CacheEntry(
            key="expire-key",
            value="expire-value",
            ttl=0.01,  # 10 milliseconds
        )

        assert not entry.is_expired()

        # Wait for expiration
        time.sleep(0.02)
        assert entry.is_expired()

    def test_cache_entry_no_ttl(self):
        """Test cache entry without TTL."""
        entry = CacheEntry(
            key="no-ttl-key",
            value="no-ttl-value",
        )

        assert not entry.is_expired()

        # Even after time passes, should not expire
        time.sleep(0.01)
        assert not entry.is_expired()


class TestCacheManager:
    """Test cases for the CacheManager."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for disk cache
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_manager = CacheManager(
            memory_cache_mb=1,  # Small for testing
            disk_cache_mb=10,
        )
        # Override memory cache settings for testing
        self.cache_manager.memory_cache.max_entries = 100
        # Set custom disk cache path
        self.cache_manager.disk_cache.cache_dir = self.temp_dir
        self.cache_manager.disk_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_manager.disk_cache.metadata_file = self.temp_dir / "cache_metadata.json"

    def test_basic_get_set(self):
        """Test basic cache get and set operations."""
        # Set value
        self.cache_manager.set("key1", "value1")

        # Get value
        value = self.cache_manager.get("key1")
        assert value == "value1"

    def test_cache_miss(self):
        """Test cache miss behavior."""
        value = self.cache_manager.get("nonexistent-key")
        assert value is None

    def test_cache_with_ttl(self):
        """Test cache with TTL."""
        # Set with short TTL
        self.cache_manager.set("ttl-key", "ttl-value", ttl=0.01)

        # Should be available immediately
        assert self.cache_manager.get("ttl-key") == "ttl-value"

        # Wait for expiration
        time.sleep(0.02)

        # Should be None after expiration
        assert self.cache_manager.get("ttl-key") is None

    def test_cache_with_category(self):
        """Test cache with category."""
        self.cache_manager.set("key1", "value1", category="category1")
        self.cache_manager.set("key2", "value2", category="category2")

        assert self.cache_manager.get("key1", category="category1") == "value1"
        assert self.cache_manager.get("key2", category="category2") == "value2"

        # Wrong category should return None
        assert self.cache_manager.get("key1", category="category2") is None

    def test_cache_with_tags(self):
        """Test cache with tags."""
        self.cache_manager.set("key1", "value1", tags={"tag1", "tag2"})
        self.cache_manager.set("key2", "value2", tags={"tag2", "tag3"})

        # Get by tag
        values = self.cache_manager.get_by_tag("tag1")
        assert len(values) == 1
        assert values[0] == "value1"

        values = self.cache_manager.get_by_tag("tag2")
        assert len(values) == 2
        assert set(values) == {"value1", "value2"}

    def test_cache_invalidation_by_key(self):
        """Test cache invalidation by key."""
        self.cache_manager.set("key1", "value1")
        assert self.cache_manager.get("key1") == "value1"

        # Invalidate
        self.cache_manager.invalidate("key1")
        assert self.cache_manager.get("key1") is None

    def test_cache_invalidation_by_tag(self):
        """Test cache invalidation by tag."""
        self.cache_manager.set("key1", "value1", tags={"tag1"})
        self.cache_manager.set("key2", "value2", tags={"tag1", "tag2"})
        self.cache_manager.set("key3", "value3", tags={"tag3"})

        # Invalidate by tag
        count = self.cache_manager.invalidate_by_tag("tag1")
        assert count == 2

        # key1 and key2 should be invalidated
        assert self.cache_manager.get("key1") is None
        assert self.cache_manager.get("key2") is None

        # key3 should still exist
        assert self.cache_manager.get("key3") == "value3"

    def test_cache_invalidation_by_category(self):
        """Test cache invalidation by category."""
        self.cache_manager.set("key1", "value1", category="cat1")
        self.cache_manager.set("key2", "value2", category="cat1")
        self.cache_manager.set("key3", "value3", category="cat2")

        # Invalidate category
        count = self.cache_manager.invalidate_by_category("cat1")
        assert count == 2

        # cat1 items should be invalidated
        assert self.cache_manager.get("key1", category="cat1") is None
        assert self.cache_manager.get("key2", category="cat1") is None

        # cat2 item should still exist
        assert self.cache_manager.get("key3", category="cat2") == "value3"

    def test_lru_eviction(self):
        """Test LRU eviction in memory cache."""
        # Fill cache to capacity (memory only to test LRU eviction)
        for i in range(110):  # More than max_size of 100
            self.cache_manager.set(f"key{i}", f"value{i}", memory_only=True)

        # Earlier keys should be evicted from memory cache
        assert self.cache_manager.memory_cache.get("key0") is None
        assert self.cache_manager.memory_cache.get("key5") is None

        # Later keys should still exist
        assert self.cache_manager.memory_cache.get("key109") == "value109"
        assert self.cache_manager.get("key105") == "value105"

    def test_cache_promotion(self):
        """Test cache promotion from disk to memory."""
        # Set item in memory
        self.cache_manager.set("promo-key", "promo-value")

        # Force to disk by filling memory
        for i in range(110):
            self.cache_manager.set(f"fill-key{i}", f"fill-value{i}")

        # Original item should be evicted from memory but available from disk
        # Getting it should promote it back to memory
        value = self.cache_manager.get("promo-key")
        assert value == "promo-value"

        # Should now be in memory cache
        memory_value = self.cache_manager.memory_cache.get("promo-key")
        assert memory_value == "promo-value"

    def test_cache_statistics(self):
        """Test cache statistics."""
        # Perform some operations
        self.cache_manager.set("key1", "value1")
        self.cache_manager.set("key2", "value2")

        self.cache_manager.get("key1")  # Hit
        self.cache_manager.get("key2")  # Hit
        self.cache_manager.get("key3")  # Miss

        stats = self.cache_manager.get_stats()

        assert stats["hits"] >= 2
        assert stats["misses"] >= 1
        assert stats["sets"] >= 2
        assert stats["memory_size"] >= 2

    def test_cache_clear(self):
        """Test cache clearing."""
        # Add items
        self.cache_manager.set("key1", "value1")
        self.cache_manager.set("key2", "value2", category="cat1")

        assert self.cache_manager.get("key1") == "value1"
        assert self.cache_manager.get("key2", category="cat1") == "value2"

        # Clear all
        self.cache_manager.clear()

        assert self.cache_manager.get("key1") is None
        assert self.cache_manager.get("key2", category="cat1") is None

    def test_cache_cleanup(self):
        """Test automatic cleanup of expired entries."""
        # Set items with short TTL
        self.cache_manager.set("expire1", "value1", ttl=0.01)
        self.cache_manager.set("expire2", "value2", ttl=0.01)
        self.cache_manager.set("keep", "value3")  # No TTL

        # Wait for expiration
        time.sleep(0.02)

        # Trigger cleanup
        cleaned = self.cache_manager.cleanup_expired()

        assert cleaned >= 2
        assert self.cache_manager.get("expire1") is None
        assert self.cache_manager.get("expire2") is None
        assert self.cache_manager.get("keep") == "value3"

    def test_disk_cache_persistence(self):
        """Test disk cache persistence."""
        # Set value that will be persisted to disk
        self.cache_manager.set("disk-key", "disk-value")

        # Force to disk by filling memory
        for i in range(110):
            self.cache_manager.set(f"fill{i}", f"value{i}")

        # Create new cache manager with same disk location
        new_cache = CacheManager(
            memory_cache_mb=1,
            disk_cache_mb=10,
        )
        # Set custom disk cache path
        new_cache.disk_cache.cache_dir = self.temp_dir
        new_cache.disk_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        new_cache.disk_cache.metadata_file = self.temp_dir / "cache_metadata.json"
        # Reload metadata from disk
        new_cache.disk_cache.metadata = new_cache.disk_cache._load_metadata()

        # Should be able to retrieve from disk
        value = new_cache.get("disk-key")
        assert value == "disk-value"

    def test_complex_data_types(self):
        """Test caching complex data types."""
        # Dictionary
        dict_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        self.cache_manager.set("dict-key", dict_data)

        retrieved_dict = self.cache_manager.get("dict-key")
        assert retrieved_dict == dict_data

        # List
        list_data = [1, 2, {"nested": "dict"}, [4, 5]]
        self.cache_manager.set("list-key", list_data)

        retrieved_list = self.cache_manager.get("list-key")
        assert retrieved_list == list_data

    def test_concurrent_access(self):
        """Test basic concurrent access patterns."""
        import threading

        results = []

        def worker(thread_id):
            for i in range(10):
                key = f"thread-{thread_id}-key-{i}"
                value = f"thread-{thread_id}-value-{i}"

                self.cache_manager.set(key, value)
                retrieved = self.cache_manager.get(key)
                results.append(retrieved == value)

        # Create and start threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All operations should have succeeded
        assert all(results)
        assert len(results) == 30  # 3 threads * 10 operations
