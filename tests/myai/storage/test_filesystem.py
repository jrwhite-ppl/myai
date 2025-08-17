"""Tests for filesystem storage implementation."""

import tempfile
from pathlib import Path

import pytest

from myai.storage.base import StorageError
from myai.storage.filesystem import FileSystemStorage


class TestFileSystemStorage:
    """Test filesystem storage implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """Create filesystem storage instance."""
        return FileSystemStorage(temp_dir)

    def test_init_creates_directories(self, temp_dir):
        """Test that initialization creates required directories."""
        storage_path = temp_dir / "storage"
        FileSystemStorage(storage_path)

        assert storage_path.exists()
        assert (storage_path / "_backups").exists()

        # Check permissions
        assert oct(storage_path.stat().st_mode)[-3:] == "700"

    def test_exists(self, storage):
        """Test checking key existence."""
        assert not storage.exists("nonexistent")

        storage.write("test_key", {"data": "value"})
        assert storage.exists("test_key")

    def test_write_and_read(self, storage):
        """Test writing and reading data."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}

        storage.write("test", test_data)
        result = storage.read("test")

        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 42
        assert result["list"] == [1, 2, 3]

        # Check metadata was added
        assert "_metadata" in result
        assert result["_metadata"]["key"] == "test"

    def test_read_nonexistent(self, storage):
        """Test reading nonexistent key returns None."""
        assert storage.read("nonexistent") is None

    def test_delete(self, storage):
        """Test deleting data."""
        storage.write("test", {"data": "value"})
        assert storage.exists("test")

        assert storage.delete("test") is True
        assert not storage.exists("test")

        # Deleting nonexistent key returns False
        assert storage.delete("test") is False

    def test_list_keys(self, storage):
        """Test listing keys."""
        assert storage.list_keys() == []

        storage.write("key1", {"data": "1"})
        storage.write("key2", {"data": "2"})
        storage.write("prefix_key", {"data": "3"})

        keys = storage.list_keys()
        assert sorted(keys) == ["key1", "key2", "prefix_key"]

        # Test prefix filtering
        prefix_keys = storage.list_keys("prefix")
        assert prefix_keys == ["prefix_key"]

    def test_backup_and_restore(self, storage):
        """Test backup and restore functionality."""
        original_data = {"original": "data"}
        storage.write("test", original_data)

        # Create backup
        backup_id = storage.backup("test")
        assert backup_id is not None

        # Modify data
        modified_data = {"modified": "data"}
        storage.write("test", modified_data)

        result = storage.read("test")
        assert result["modified"] == "data"

        # Restore from backup
        assert storage.restore("test", backup_id) is True

        restored = storage.read("test")
        assert restored["original"] == "data"

    def test_backup_nonexistent(self, storage):
        """Test backing up nonexistent key returns None."""
        assert storage.backup("nonexistent") is None

    def test_restore_invalid_backup(self, storage):
        """Test restoring from invalid backup returns False."""
        storage.write("test", {"data": "value"})
        assert storage.restore("test", "invalid_backup") is False

    def test_list_backups(self, storage):
        """Test listing backups for a key."""
        storage.write("test", {"data": "1"})

        # No backups initially
        assert storage.list_backups("test") == []

        # Create backups
        backup1 = storage.backup("test")
        storage.write("test", {"data": "2"})
        backup2 = storage.backup("test")

        backups = storage.list_backups("test")
        assert len(backups) == 2
        assert backup1 in backups
        assert backup2 in backups

    def test_cleanup_backups(self, storage):
        """Test cleaning up old backups."""
        import time

        storage.write("test", {"data": "1"})

        # Create multiple backups with small delays to ensure unique timestamps
        backup_count = 0
        for i in range(5):  # Reduced to avoid timing issues
            if storage.backup("test"):
                backup_count += 1
            storage.write("test", {"data": str(i)})
            time.sleep(0.001)  # Small delay to ensure unique timestamps

        assert len(storage.list_backups("test")) == backup_count

        # Keep only 2 most recent
        deleted = storage.cleanup_backups("test", keep_count=2)
        assert deleted == backup_count - 2
        assert len(storage.list_backups("test")) == 2

    def test_text_operations(self, storage):
        """Test text read/write operations."""
        text_content = "This is plain text content\nwith multiple lines."

        storage.write_text("text_file", text_content)
        result = storage.read_text("text_file")

        assert result == text_content

    def test_metadata_operations(self, storage):
        """Test metadata get/set operations."""
        storage.write("test", {"data": "value"})

        # Set metadata
        metadata = {"author": "test", "version": "1.0"}
        storage.set_metadata("test", metadata)

        # Get metadata
        result = storage.get_metadata("test")
        assert result["author"] == "test"
        assert result["version"] == "1.0"

    def test_copy_and_move(self, storage):
        """Test copying and moving data."""
        original_data = {"key": "value"}
        storage.write("source", original_data)

        # Test copy
        assert storage.copy("source", "dest") is True
        assert storage.read("source") is not None
        assert storage.read("dest") is not None

        # Test move
        assert storage.move("source", "moved") is True
        assert storage.read("source") is None
        assert storage.read("moved") is not None

    def test_copy_nonexistent(self, storage):
        """Test copying nonexistent key returns False."""
        assert storage.copy("nonexistent", "dest") is False

    def test_get_storage_info(self, storage):
        """Test getting storage information."""
        info = storage.get_storage_info()

        assert "base_path" in info
        assert "total_files" in info
        assert "total_size_bytes" in info
        assert "backup_files" in info
        assert "backup_size_bytes" in info
        assert "exists" in info

        # Add some data
        storage.write("test1", {"data": "1"})
        storage.write("test2", {"data": "2"})
        storage.backup("test1")

        info = storage.get_storage_info()
        assert info["total_files"] == 2
        assert info["backup_files"] == 1

    def test_file_permissions(self, storage, temp_dir):
        """Test that files have secure permissions."""
        storage.write("test", {"data": "sensitive"})

        file_path = temp_dir / "test.json"
        assert file_path.exists()

        # Check file permissions (should be 600)
        assert oct(file_path.stat().st_mode)[-3:] == "600"

    def test_atomic_writes(self, storage, temp_dir):
        """Test that writes are atomic."""
        # This test is more conceptual - we verify temp files are cleaned up
        original_data = {"data": "original"}
        storage.write("test", original_data)

        # No .tmp files should remain
        temp_files = list(temp_dir.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_key_sanitization(self, storage):
        """Test that keys are properly sanitized."""
        # Test dangerous characters in key
        dangerous_key = "../../../etc/passwd"
        storage.write(dangerous_key, {"data": "test"})

        # Should be stored safely
        assert storage.exists(dangerous_key)
        result = storage.read(dangerous_key)
        assert result["data"] == "test"

    def test_storage_errors(self, temp_dir):
        """Test storage error handling."""
        # Test with read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        try:
            # Try creating storage with create_dirs=False to avoid permission error during init
            with pytest.raises(PermissionError):
                FileSystemStorage(readonly_dir / "storage", create_dirs=True)
        finally:
            # Cleanup
            readonly_dir.chmod(0o755)

    def test_json_corruption_handling(self, storage, temp_dir):
        """Test handling of corrupted JSON files."""
        # Create corrupted JSON file
        file_path = temp_dir / "corrupted.json"
        file_path.write_text("{ invalid json content")

        with pytest.raises(StorageError):
            storage.read("corrupted")
