"""Tests for credential management."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import SecretStr

from myai.security.credentials import (
    Credential,
    CredentialConfig,
    CredentialError,
    CredentialManager,
)


class TestCredential:
    """Test Credential model."""

    def test_create_credential(self):
        """Test creating a credential."""
        credential = Credential(name="test_key", value=SecretStr("secret_value"), description="Test credential")

        assert credential.name == "test_key"
        assert credential.value.get_secret_value() == "secret_value"
        assert credential.description == "Test credential"
        assert credential.created_at is not None
        assert credential.updated_at is not None
        assert credential.expires_at is None
        assert credential.tags == []

    def test_credential_with_expiration(self):
        """Test credential with expiration."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        credential = Credential(
            name="temp_key", value=SecretStr("temp_value"), expires_at=expires_at, tags=["temporary", "test"]
        )

        assert credential.expires_at == expires_at
        assert credential.tags == ["temporary", "test"]
        assert not credential.is_expired()

    def test_credential_expired(self):
        """Test expired credential detection."""
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        credential = Credential(name="expired_key", value=SecretStr("expired_value"), expires_at=expires_at)

        assert credential.is_expired()

    def test_credential_to_dict(self):
        """Test credential serialization."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        credential = Credential(
            name="test_key",
            value=SecretStr("secret_value"),
            description="Test credential",
            expires_at=expires_at,
            tags=["test"],
        )

        data = credential.to_dict()

        assert data["name"] == "test_key"
        assert data["value"] == "secret_value"
        assert data["description"] == "Test credential"
        assert data["expires_at"] == expires_at.isoformat()
        assert data["tags"] == ["test"]
        assert "created_at" in data
        assert "updated_at" in data

    def test_credential_from_dict(self):
        """Test credential deserialization."""
        data = {
            "name": "test_key",
            "value": "secret_value",
            "description": "Test credential",
            "created_at": "2023-01-01T00:00:00+00:00",
            "updated_at": "2023-01-01T00:00:00+00:00",
            "expires_at": "2023-12-31T23:59:59+00:00",
            "tags": ["test"],
        }

        credential = Credential.from_dict(data)

        assert credential.name == "test_key"
        assert credential.value.get_secret_value() == "secret_value"
        assert credential.description == "Test credential"
        assert credential.tags == ["test"]
        assert isinstance(credential.created_at, datetime)
        assert isinstance(credential.expires_at, datetime)


class TestCredentialManager:
    """Test CredentialManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def credential_manager(self, temp_dir):
        """Create CredentialManager instance with fallback storage."""
        with patch("myai.security.credentials.KEYRING_AVAILABLE", False):
            manager = CredentialManager()
            # Override fallback path for testing
            manager._fallback_path = temp_dir / "credentials.enc"
            manager._ensure_fallback_directory()
            return manager

    def keyring_manager(self):
        """Create CredentialManager instance with mocked keyring."""
        with patch("myai.security.credentials.KEYRING_AVAILABLE", True):
            with patch("myai.security.credentials.keyring") as mock_keyring:
                manager = CredentialManager()
                mock_keyring.set_password = Mock()
                mock_keyring.get_password = Mock()
                mock_keyring.delete_password = Mock()
                return manager, mock_keyring

    def test_store_credential_fallback(self, credential_manager):
        """Test storing credential with fallback storage."""
        credential_manager.store_credential(name="test_key", value="secret_value", description="Test credential")

        # Should be able to retrieve it
        credential = credential_manager.get_credential("test_key")
        assert credential is not None
        assert credential.name == "test_key"
        assert credential.value.get_secret_value() == "secret_value"
        assert credential.description == "Test credential"

    def test_store_credential_keyring(self):
        """Test storing credential with keyring."""
        with patch("myai.security.credentials.KEYRING_AVAILABLE", True):
            with patch("myai.security.credentials.keyring") as mock_keyring:
                # Mock the get_password to return None (credential doesn't exist)
                mock_keyring.get_password.return_value = None

                manager = CredentialManager()

                manager.store_credential(name="test_key", value="secret_value", description="Test credential")

                # Should have called keyring
                mock_keyring.set_password.assert_called_once()
                args = mock_keyring.set_password.call_args[0]
                assert args[0] == "myai"  # service name
                assert args[1] == "test_key"  # credential name

                # Should be JSON with credential data
                credential_json = args[2]
                credential_data = json.loads(credential_json)
                assert credential_data["name"] == "test_key"
                assert credential_data["value"] == "secret_value"

    def test_store_credential_overwrite_protection(self, credential_manager):
        """Test credential overwrite protection."""
        # Store initial credential
        credential_manager.store_credential("test_key", "value1")

        # Attempt to store again without overwrite flag
        with pytest.raises(CredentialError, match="already exists"):
            credential_manager.store_credential("test_key", "value2")

        # Should still have original value
        credential = credential_manager.get_credential("test_key")
        assert credential.value.get_secret_value() == "value1"

    def test_store_credential_overwrite_allowed(self, credential_manager):
        """Test credential overwrite when explicitly allowed."""
        # Store initial credential
        credential_manager.store_credential("test_key", "value1")

        # Overwrite with new value
        credential_manager.store_credential("test_key", "value2", overwrite=True)

        # Should have new value
        credential = credential_manager.get_credential("test_key")
        assert credential.value.get_secret_value() == "value2"

    def test_get_credential_not_found(self, credential_manager):
        """Test getting non-existent credential."""
        credential = credential_manager.get_credential("nonexistent")
        assert credential is None

    def test_get_credential_value(self, credential_manager):
        """Test getting credential value directly."""
        credential_manager.store_credential("test_key", "secret_value")

        value = credential_manager.get_credential_value("test_key")
        assert value == "secret_value"

        # Non-existent should return None
        value = credential_manager.get_credential_value("nonexistent")
        assert value is None

    def test_delete_credential_success(self, credential_manager):
        """Test successful credential deletion."""
        credential_manager.store_credential("test_key", "secret_value")

        # Should exist
        assert credential_manager.credential_exists("test_key")

        # Delete it
        result = credential_manager.delete_credential("test_key")
        assert result is True

        # Should no longer exist
        assert not credential_manager.credential_exists("test_key")

    def test_delete_credential_not_found(self, credential_manager):
        """Test deleting non-existent credential."""
        result = credential_manager.delete_credential("nonexistent")
        assert result is False

    def test_list_credentials(self, credential_manager):
        """Test listing credentials."""
        # Initially empty
        credentials = credential_manager.list_credentials()
        assert credentials == []

        # Add some credentials
        credential_manager.store_credential("key1", "value1")
        credential_manager.store_credential("key2", "value2")
        credential_manager.store_credential("key3", "value3")

        # Should list all credentials
        credentials = credential_manager.list_credentials()
        assert set(credentials) == {"key1", "key2", "key3"}

    def test_credential_exists(self, credential_manager):
        """Test checking credential existence."""
        assert not credential_manager.credential_exists("test_key")

        credential_manager.store_credential("test_key", "secret_value")
        assert credential_manager.credential_exists("test_key")

        credential_manager.delete_credential("test_key")
        assert not credential_manager.credential_exists("test_key")

    def test_get_from_environment(self, credential_manager):
        """Test getting credentials from environment variables."""
        # Set environment variables
        os.environ["TEST_VAR"] = "test_value"
        os.environ["MYAI_ANOTHER_VAR"] = "another_value"

        try:
            # Should find direct match
            value = credential_manager.get_from_environment("TEST_VAR")
            assert value == "test_value"

            # Should find with prefix
            value = credential_manager.get_from_environment("ANOTHER_VAR")
            assert value == "another_value"

            # Should return default for non-existent
            value = credential_manager.get_from_environment("NONEXISTENT", "default")
            assert value == "default"

        finally:
            # Clean up
            os.environ.pop("TEST_VAR", None)
            os.environ.pop("MYAI_ANOTHER_VAR", None)

    def test_store_from_environment(self, credential_manager):
        """Test storing credentials from environment variables."""
        # Set environment variables
        os.environ["API_KEY"] = "secret_api_key"
        os.environ["MYAI_TOKEN"] = "secret_token"

        try:
            results = credential_manager.store_from_environment(["API_KEY", "TOKEN", "MISSING"], prefix="MYAI_")

            # Should succeed for found variables
            assert results["API_KEY"] is True
            assert results["TOKEN"] is True
            assert results["MISSING"] is False

            # Should have stored the credentials
            assert credential_manager.get_credential_value("api_key") == "secret_api_key"
            assert credential_manager.get_credential_value("token") == "secret_token"

        finally:
            # Clean up
            os.environ.pop("API_KEY", None)
            os.environ.pop("MYAI_TOKEN", None)

    def test_rotate_credential(self, credential_manager):
        """Test credential rotation."""
        # Store initial credential
        credential_manager.store_credential("api_key", "old_value")

        # Rotate it
        credential_manager.rotate_credential("api_key", "new_value", keep_backup=True)

        # Should have new value
        assert credential_manager.get_credential_value("api_key") == "new_value"

        # Should have backup
        backups = [name for name in credential_manager.list_credentials() if name.startswith("api_key_backup_")]
        assert len(backups) == 1

        backup_value = credential_manager.get_credential_value(backups[0])
        assert backup_value == "old_value"

    def test_rotate_credential_not_found(self, credential_manager):
        """Test rotating non-existent credential."""
        with pytest.raises(CredentialError, match="not found"):
            credential_manager.rotate_credential("nonexistent", "new_value")

    def test_cleanup_expired(self, credential_manager):
        """Test cleaning up expired credentials."""
        # Store normal credential
        credential_manager.store_credential("normal", "value")

        # Store expired credential by directly manipulating the storage
        # since store_credential doesn't allow storing already-expired credentials
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_credential = Credential(name="expired", value=SecretStr("value"), expires_at=expired_time)

        # Store directly in fallback storage
        credentials = credential_manager._load_fallback_credentials()
        credentials["expired"] = expired_credential.to_dict()
        credential_manager._save_fallback_credentials(credentials)

        # Should have both initially in raw storage
        raw_credentials = credential_manager._load_fallback_credentials()
        assert len(raw_credentials) == 2
        assert "expired" in raw_credentials
        assert "normal" in raw_credentials

        # Clear cache to force reload from storage
        credential_manager._cache.clear()

        # Cleanup expired - this will find and remove expired credentials
        credential_manager.cleanup_expired()

        # Should have identified the expired one (it gets removed during get_credential call)
        # The behavior is that get_credential removes expired credentials automatically
        assert len(credential_manager.list_credentials()) == 1
        assert credential_manager.credential_exists("normal")
        assert not credential_manager.credential_exists("expired")

    def test_expired_credential_auto_removal(self, credential_manager):
        """Test automatic removal of expired credentials on access."""
        # Store expired credential by directly manipulating storage
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_credential = Credential(name="expired", value=SecretStr("value"), expires_at=expired_time)

        # Store directly in fallback storage
        credentials = credential_manager._load_fallback_credentials()
        credentials["expired"] = expired_credential.to_dict()
        credential_manager._save_fallback_credentials(credentials)

        # Should initially exist in raw storage
        assert "expired" in credential_manager.list_credentials()

        # Trying to get it should remove it and return None
        credential = credential_manager.get_credential("expired")
        assert credential is None
        assert not credential_manager.credential_exists("expired")

    def test_fallback_file_permissions(self, credential_manager, temp_dir):  # noqa: ARG002
        """Test fallback file has secure permissions."""
        credential_manager.store_credential("test", "value")

        fallback_file = credential_manager._fallback_path
        assert fallback_file.exists()

        # Check file permissions are secure (600)
        mode = fallback_file.stat().st_mode & 0o777
        assert mode == 0o600

        # Check parent directory permissions are secure (700)
        parent_mode = fallback_file.parent.stat().st_mode & 0o777
        assert parent_mode == 0o700


class TestCredentialConfig:
    """Test CredentialConfig model."""

    def test_default_config(self):
        """Test default credential configuration."""
        config = CredentialConfig()

        assert config.service_name == "myai"
        assert config.use_keyring is True
        assert config.fallback_encryption is True
        assert config.auto_cleanup_expired is True
        assert config.max_cache_size == 100

    def test_custom_config(self):
        """Test custom credential configuration."""
        config = CredentialConfig(
            service_name="custom_service",
            use_keyring=False,
            fallback_encryption=False,
            auto_cleanup_expired=False,
            max_cache_size=50,
        )

        assert config.service_name == "custom_service"
        assert config.use_keyring is False
        assert config.fallback_encryption is False
        assert config.auto_cleanup_expired is False
        assert config.max_cache_size == 50


class TestCredentialIntegration:
    """Integration tests for credential management."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def credential_manager(self, temp_dir):
        """Create CredentialManager instance."""
        with patch("myai.security.credentials.KEYRING_AVAILABLE", False):
            manager = CredentialManager()
            manager._fallback_path = temp_dir / "credentials.enc"
            manager._ensure_fallback_directory()
            return manager

    def test_credential_lifecycle(self, credential_manager):
        """Test complete credential lifecycle."""
        # Create credential
        credential_manager.store_credential(
            name="api_key", value="secret_key_123", description="API key for external service", tags=["api", "external"]
        )

        # Verify it exists
        assert credential_manager.credential_exists("api_key")

        # Retrieve and verify
        credential = credential_manager.get_credential("api_key")
        assert credential.name == "api_key"
        assert credential.value.get_secret_value() == "secret_key_123"
        assert credential.description == "API key for external service"
        assert credential.tags == ["api", "external"]

        # Update credential
        credential_manager.store_credential(
            name="api_key", value="new_secret_key_456", description="Updated API key", overwrite=True
        )

        # Verify update
        updated_credential = credential_manager.get_credential("api_key")
        assert updated_credential.value.get_secret_value() == "new_secret_key_456"
        assert updated_credential.description == "Updated API key"

        # Rotate credential
        credential_manager.rotate_credential("api_key", "rotated_key_789")

        # Verify rotation
        rotated_credential = credential_manager.get_credential("api_key")
        assert rotated_credential.value.get_secret_value() == "rotated_key_789"

        # Verify backup exists
        backups = [name for name in credential_manager.list_credentials() if name.startswith("api_key_backup_")]
        assert len(backups) == 1

        # Delete credential
        result = credential_manager.delete_credential("api_key")
        assert result is True
        assert not credential_manager.credential_exists("api_key")

    def test_multiple_credentials_management(self, credential_manager):
        """Test managing multiple credentials."""
        # Store multiple credentials
        credentials_data = [
            ("database_password", "db_pass_123", "Database connection password"),
            ("api_token", "api_token_456", "External API token"),
            ("encryption_key", "encrypt_key_789", "Data encryption key"),
        ]

        for name, value, description in credentials_data:
            credential_manager.store_credential(name, value, description=description)

        # Verify all exist
        credential_names = credential_manager.list_credentials()
        assert len(credential_names) == 3
        assert set(credential_names) == {"database_password", "api_token", "encryption_key"}

        # Verify all can be retrieved
        for name, expected_value, _ in credentials_data:
            value = credential_manager.get_credential_value(name)
            assert value == expected_value

        # Delete one
        credential_manager.delete_credential("api_token")

        # Verify deletion
        remaining_names = credential_manager.list_credentials()
        assert len(remaining_names) == 2
        assert "api_token" not in remaining_names

    def test_environment_integration(self, credential_manager):
        """Test integration with environment variables."""
        # Set up environment
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "MYAI_API_KEY": "api_key_from_env",
            "SECRET_TOKEN": "secret_token_123",
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        try:
            # Import from environment
            results = credential_manager.store_from_environment(
                ["DATABASE_URL", "API_KEY", "SECRET_TOKEN"], prefix="MYAI_"
            )

            # Verify imports
            assert results["DATABASE_URL"] is True
            assert results["API_KEY"] is True
            assert results["SECRET_TOKEN"] is True

            # Verify stored values
            assert credential_manager.get_credential_value("database_url") == env_vars["DATABASE_URL"]
            assert credential_manager.get_credential_value("api_key") == env_vars["MYAI_API_KEY"]
            assert credential_manager.get_credential_value("secret_token") == env_vars["SECRET_TOKEN"]

            # Test fallback to environment
            assert credential_manager.get_from_environment("DATABASE_URL") == env_vars["DATABASE_URL"]
            assert credential_manager.get_from_environment("API_KEY") == env_vars["MYAI_API_KEY"]

        finally:
            # Clean up environment
            for key in env_vars:
                os.environ.pop(key, None)
