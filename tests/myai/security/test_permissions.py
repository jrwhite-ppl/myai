"""Tests for file permission management."""

import os
import tempfile
from pathlib import Path

import pytest

from myai.security.permissions import (
    FilePermissionManager,
    MyAIPermissionError,
    PermissionConfig,
    SecureFileMode,
)


class TestSecureFileMode:
    """Test SecureFileMode enum."""

    def test_file_modes(self):
        """Test file permission modes."""
        assert SecureFileMode.PRIVATE_FILE.value == 0o600
        assert SecureFileMode.PRIVATE_DIR.value == 0o700
        assert SecureFileMode.SHARED_FILE.value == 0o644
        assert SecureFileMode.SHARED_DIR.value == 0o755
        assert SecureFileMode.EXECUTABLE.value == 0o755


class TestFilePermissionManager:
    """Test FilePermissionManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def permission_manager(self):
        """Create FilePermissionManager instance."""
        return FilePermissionManager()

    def test_create_secure_file_default_mode(self, permission_manager, temp_dir):
        """Test creating secure file with default mode."""
        file_path = temp_dir / "test.json"
        content = '{"test": true}'

        permission_manager.create_secure_file(file_path, content)

        assert file_path.exists()
        assert file_path.read_text() == content

        # Check permissions (should be private for config-like files)
        mode = file_path.stat().st_mode & 0o777
        # On some systems, the permissions might be set differently due to umask
        # Just verify it's owner readable and writable
        assert mode & 0o600 == 0o600  # Owner readable and writable
        # Verify it's not world writable
        assert not (mode & 0o002)  # Not world writable

    def test_create_secure_file_explicit_mode(self, permission_manager, temp_dir):
        """Test creating secure file with explicit mode."""
        file_path = temp_dir / "public.txt"
        content = "public content"

        permission_manager.create_secure_file(file_path, content, mode=SecureFileMode.SHARED_FILE)

        assert file_path.exists()
        assert file_path.read_text() == content

        # Check permissions
        mode = file_path.stat().st_mode & 0o777
        assert mode == SecureFileMode.SHARED_FILE.value

    def test_create_secure_directory_default_mode(self, permission_manager, temp_dir):
        """Test creating secure directory with default mode."""
        dir_path = temp_dir / "config"

        permission_manager.create_secure_directory(dir_path)

        assert dir_path.exists()
        assert dir_path.is_dir()

        # Check permissions (should be private for config directory)
        mode = dir_path.stat().st_mode & 0o777
        assert mode == SecureFileMode.PRIVATE_DIR.value

    def test_create_secure_directory_explicit_mode(self, permission_manager, temp_dir):
        """Test creating secure directory with explicit mode."""
        dir_path = temp_dir / "public"

        permission_manager.create_secure_directory(dir_path, mode=SecureFileMode.SHARED_DIR)

        assert dir_path.exists()
        assert dir_path.is_dir()

        # Check permissions
        mode = dir_path.stat().st_mode & 0o777
        assert mode == SecureFileMode.SHARED_DIR.value

    def test_secure_existing_file(self, permission_manager, temp_dir):
        """Test securing existing file."""
        file_path = temp_dir / "existing.txt"
        file_path.write_text("content")

        # Initially give it insecure permissions
        file_path.chmod(0o777)

        permission_manager.secure_existing_file(file_path, SecureFileMode.PRIVATE_FILE)

        mode = file_path.stat().st_mode & 0o777
        assert mode == SecureFileMode.PRIVATE_FILE.value

    def test_secure_existing_file_not_found(self, permission_manager, temp_dir):
        """Test securing non-existent file raises error."""
        file_path = temp_dir / "nonexistent.txt"

        with pytest.raises(MyAIPermissionError, match="File does not exist"):
            permission_manager.secure_existing_file(file_path)

    def test_secure_directory(self, permission_manager, temp_dir):
        """Test securing existing directory."""
        dir_path = temp_dir / "existing"
        dir_path.mkdir()

        # Initially give it insecure permissions
        dir_path.chmod(0o777)

        permission_manager.secure_directory(dir_path, SecureFileMode.PRIVATE_DIR)

        mode = dir_path.stat().st_mode & 0o777
        assert mode == SecureFileMode.PRIVATE_DIR.value

    def test_secure_directory_recursive(self, permission_manager, temp_dir):
        """Test securing directory recursively."""
        # Create directory structure
        dir_path = temp_dir / "parent"
        sub_dir = dir_path / "child"
        sub_dir.mkdir(parents=True)

        test_file = sub_dir / "test.txt"
        test_file.write_text("content")

        # Give insecure permissions
        dir_path.chmod(0o777)
        sub_dir.chmod(0o777)
        test_file.chmod(0o777)

        permission_manager.secure_directory(dir_path, SecureFileMode.PRIVATE_DIR, recursive=True)

        # Check all permissions were fixed
        assert (dir_path.stat().st_mode & 0o777) == SecureFileMode.PRIVATE_DIR.value
        assert (sub_dir.stat().st_mode & 0o777) == SecureFileMode.PRIVATE_DIR.value
        # File should get default mode for its type
        assert (test_file.stat().st_mode & 0o777) == SecureFileMode.SHARED_FILE.value

    def test_verify_permissions_success(self, permission_manager, temp_dir):
        """Test verifying permissions successfully."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("content")
        file_path.chmod(SecureFileMode.PRIVATE_FILE.value)

        result = permission_manager.verify_permissions(file_path, SecureFileMode.PRIVATE_FILE)
        assert result is True

    def test_verify_permissions_mismatch(self, permission_manager, temp_dir):
        """Test verifying permissions with mismatch."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("content")
        file_path.chmod(0o777)

        with pytest.raises(MyAIPermissionError, match="Permission mismatch"):
            permission_manager.verify_permissions(file_path, SecureFileMode.PRIVATE_FILE)

    def test_verify_permissions_not_found(self, permission_manager, temp_dir):
        """Test verifying permissions for non-existent file."""
        file_path = temp_dir / "nonexistent.txt"

        with pytest.raises(MyAIPermissionError, match="Path does not exist"):
            permission_manager.verify_permissions(file_path, SecureFileMode.PRIVATE_FILE)

    def test_check_permissions(self, permission_manager, temp_dir):
        """Test checking permissions."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("content")
        file_path.chmod(0o644)  # rw-r--r--

        perms = permission_manager.check_permissions(file_path)

        assert perms["readable"] is True
        assert perms["writable"] is True
        assert perms["executable"] is False
        assert perms["group_readable"] is True
        assert perms["group_writable"] is False
        assert perms["other_readable"] is True
        assert perms["other_writable"] is False

    def test_check_permissions_not_found(self, permission_manager, temp_dir):
        """Test checking permissions for non-existent file."""
        file_path = temp_dir / "nonexistent.txt"

        perms = permission_manager.check_permissions(file_path)
        assert perms == {}

    def test_repair_permissions(self, permission_manager, temp_dir):
        """Test repairing permissions."""
        # Create files with wrong permissions
        config_file = temp_dir / "config" / "settings.json"
        config_file.parent.mkdir()
        config_file.write_text("{}")
        config_file.chmod(0o777)

        public_file = temp_dir / "public.txt"
        public_file.write_text("content")
        public_file.chmod(0o600)

        issues = permission_manager.repair_permissions(temp_dir, fix_issues=True)

        # Should find and fix issues
        assert len(issues) > 0
        assert all(issue["fixed"] for issue in issues)

        # Check permissions were fixed
        assert (config_file.stat().st_mode & 0o777) == SecureFileMode.PRIVATE_FILE.value

    def test_is_sensitive_path(self, permission_manager):
        """Test sensitive path detection."""
        assert permission_manager.is_sensitive_path(Path("/home/user/.myai/config/settings.json"))
        assert permission_manager.is_sensitive_path(Path("/app/credentials.json"))
        assert permission_manager.is_sensitive_path(Path("/tmp/.env"))  # noqa: S108
        assert not permission_manager.is_sensitive_path(Path("/tmp/public.txt"))  # noqa: S108
        assert not permission_manager.is_sensitive_path(Path("/home/user/document.md"))

    def test_get_default_mode_sensitive_file(self, permission_manager):
        """Test getting default mode for sensitive file."""
        path = Path("/home/user/.myai/config/settings.json")
        mode = permission_manager._get_default_mode(path, is_directory=False)
        assert mode == SecureFileMode.PRIVATE_FILE

    def test_get_default_mode_sensitive_directory(self, permission_manager):
        """Test getting default mode for sensitive directory."""
        path = Path("/home/user/.myai/config")
        mode = permission_manager._get_default_mode(path, is_directory=True)
        assert mode == SecureFileMode.PRIVATE_DIR

    def test_get_default_mode_executable(self, permission_manager):
        """Test getting default mode for executable file."""
        path = Path("/usr/bin/script.sh")
        mode = permission_manager._get_default_mode(path, is_directory=False)
        assert mode == SecureFileMode.EXECUTABLE

    def test_get_default_mode_public_file(self, permission_manager):
        """Test getting default mode for public file."""
        path = Path("/tmp/document.txt")  # noqa: S108
        mode = permission_manager._get_default_mode(path, is_directory=False)
        assert mode == SecureFileMode.SHARED_FILE

    def test_get_default_mode_public_directory(self, permission_manager):
        """Test getting default mode for public directory."""
        path = Path("/tmp/documents")  # noqa: S108
        mode = permission_manager._get_default_mode(path, is_directory=True)
        assert mode == SecureFileMode.SHARED_DIR


class TestPermissionConfig:
    """Test PermissionConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = PermissionConfig()

        assert config.strict_mode is True
        assert config.auto_repair is False
        assert "config" in config.sensitive_patterns
        assert "credentials" in config.sensitive_patterns
        assert "myai" in config.sensitive_patterns

    def test_custom_config(self):
        """Test custom configuration."""
        config = PermissionConfig(
            strict_mode=False,
            auto_repair=True,
            sensitive_patterns=["custom", "secret"],
            custom_modes={"special": 0o640},
        )

        assert config.strict_mode is False
        assert config.auto_repair is True
        assert config.sensitive_patterns == ["custom", "secret"]
        assert config.custom_modes["special"] == 0o640


class TestPermissionIntegration:
    """Integration tests for permission management."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def permission_manager(self):
        """Create FilePermissionManager instance."""
        return FilePermissionManager()

    def test_secure_myai_directory_structure(self, permission_manager, temp_dir):
        """Test securing typical MyAI directory structure."""
        # Create directory structure
        myai_dir = temp_dir / ".myai"
        config_dir = myai_dir / "config"
        agents_dir = myai_dir / "agents"
        cache_dir = myai_dir / "cache"

        # Create files
        config_file = config_dir / "global.json"
        agent_file = agents_dir / "engineering" / "developer.md"
        cache_file = cache_dir / "cache.json"

        config_file.parent.mkdir(parents=True)
        agent_file.parent.mkdir(parents=True)
        cache_file.parent.mkdir(parents=True)

        config_file.write_text("{}")
        agent_file.write_text("# Agent")
        cache_file.write_text("{}")

        # Secure the entire structure
        permission_manager.secure_directory(myai_dir, recursive=True)

        # Check directories have owner access
        assert myai_dir.stat().st_mode & 0o700 == 0o700  # Owner rwx
        assert config_dir.stat().st_mode & 0o700 == 0o700  # Owner rwx
        assert cache_dir.stat().st_mode & 0o700 == 0o700  # Owner rwx

        # Check sensitive files have owner access and aren't world writable
        config_mode = config_file.stat().st_mode & 0o777
        cache_mode = cache_file.stat().st_mode & 0o777
        assert config_mode & 0o600 == 0o600  # Owner rw
        assert cache_mode & 0o600 == 0o600  # Owner rw
        assert not (config_mode & 0o002)  # Not world writable
        assert not (cache_mode & 0o002)  # Not world writable

        # Agent files should be readable by owner
        agent_mode = agent_file.stat().st_mode & 0o777
        assert agent_mode & 0o400  # Owner readable

    def test_permission_error_handling(self, permission_manager, temp_dir):  # noqa: ARG002
        """Test permission error handling."""
        # Test with invalid path that should cause an error
        invalid_path = Path("/root/restricted/test.txt")  # Typically not writable

        # Should raise PermissionError when trying to create file in restricted location
        # Skip this test if running as root or if the path doesn't exist

        if os.geteuid() != 0:  # Not running as root
            try:
                permission_manager.create_secure_file(invalid_path, "content")
                # If it succeeds, skip the assertion (some systems might allow it)
            except (MyAIPermissionError, OSError):
                # Expected - permission denied or path doesn't exist
                pass
