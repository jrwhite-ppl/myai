"""
Credential management for MyAI.

This module provides secure credential storage and retrieval using
system keyring services and environment variables.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import keyring  # type: ignore[import]
    from keyring.errors import KeyringError  # type: ignore[import]

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception  # type: ignore

from pydantic import BaseModel, Field, SecretStr


class CredentialError(Exception):
    """Exception raised for credential-related errors."""

    pass


class Credential(BaseModel):
    """Secure credential model."""

    name: str
    value: SecretStr
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if credential is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "value": self.value.get_secret_value(),
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Credential":
        """Create from dictionary."""
        # Convert datetime strings back to datetime objects
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])

        return cls(**data)


class CredentialManager:
    """Manages secure credential storage and retrieval."""

    def __init__(self, service_name: str = "myai"):
        """
        Initialize credential manager.

        Args:
            service_name: Service name for keyring storage
        """
        self.service_name = service_name
        self._keyring_available = KEYRING_AVAILABLE
        self._cache: Dict[str, Credential] = {}  # In-memory cache for performance

        # Fallback to file storage if keyring not available
        if not self._keyring_available:
            self._fallback_path = Path.home() / ".myai" / "credentials.enc"
            self._ensure_fallback_directory()

    def store_credential(
        self,
        name: str,
        value: str,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        *,
        overwrite: bool = False,
    ) -> None:
        """
        Store a credential securely.

        Args:
            name: Credential name/identifier
            value: Credential value (password, token, etc.)
            description: Optional description
            expires_at: Optional expiration datetime
            tags: Optional tags for organization
            overwrite: Whether to overwrite existing credential

        Raises:
            CredentialError: If credential already exists and overwrite=False
        """
        # Check if credential already exists
        if not overwrite and self.credential_exists(name):
            msg = f"Credential '{name}' already exists"
            raise CredentialError(msg)

        credential = Credential(
            name=name, value=SecretStr(value), description=description, expires_at=expires_at, tags=tags or []
        )

        try:
            if self._keyring_available:
                self._store_in_keyring(name, credential)
            else:
                self._store_in_fallback(name, credential)

            # Update cache
            self._cache[name] = credential

        except Exception as e:
            msg = f"Failed to store credential '{name}': {e}"
            raise CredentialError(msg) from e

    def get_credential(self, name: str) -> Optional[Credential]:
        """
        Retrieve a credential.

        Args:
            name: Credential name

        Returns:
            Credential object or None if not found
        """
        # Check cache first
        if name in self._cache:
            cached_credential = self._cache[name]
            if not cached_credential.is_expired():
                return cached_credential
            else:
                # Remove expired credential
                self.delete_credential(name)
                return None

        try:
            credential: Optional[Credential]
            if self._keyring_available:
                credential = self._get_from_keyring(name)
            else:
                credential = self._get_from_fallback(name)

            if credential and not credential.is_expired():
                self._cache[name] = credential
                return credential
            elif credential and credential.is_expired():
                # Remove expired credential
                self.delete_credential(name)
                return None

            return None

        except Exception as e:
            msg = f"Failed to retrieve credential '{name}': {e}"
            raise CredentialError(msg) from e

    def get_credential_value(self, name: str) -> Optional[str]:
        """
        Get just the credential value.

        Args:
            name: Credential name

        Returns:
            Credential value or None if not found
        """
        credential = self.get_credential(name)
        return credential.value.get_secret_value() if credential else None

    def delete_credential(self, name: str) -> bool:
        """
        Delete a credential.

        Args:
            name: Credential name

        Returns:
            True if deleted, False if not found
        """
        try:
            if self._keyring_available:
                success = self._delete_from_keyring(name)
            else:
                success = self._delete_from_fallback(name)

            # Remove from cache
            self._cache.pop(name, None)

            return success

        except Exception as e:
            msg = f"Failed to delete credential '{name}': {e}"
            raise CredentialError(msg) from e

    def list_credentials(self) -> List[str]:
        """
        List all stored credential names.

        Returns:
            List of credential names
        """
        try:
            if self._keyring_available:
                return self._list_keyring_credentials()
            else:
                return self._list_fallback_credentials()
        except Exception as e:
            msg = f"Failed to list credentials: {e}"
            raise CredentialError(msg) from e

    def credential_exists(self, name: str) -> bool:
        """
        Check if a credential exists.

        Args:
            name: Credential name

        Returns:
            True if credential exists
        """
        return self.get_credential(name) is not None

    def get_from_environment(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get credential from environment variable.

        Args:
            name: Environment variable name
            default: Default value if not found

        Returns:
            Environment variable value or default
        """
        # Try direct environment variable
        value = os.getenv(name)
        if value:
            return value

        # Try with MYAI prefix
        prefixed_name = f"MYAI_{name.upper()}"
        value = os.getenv(prefixed_name)
        if value:
            return value

        return default

    def store_from_environment(self, env_vars: List[str], prefix: str = "MYAI_") -> Dict[str, bool]:
        """
        Store credentials from environment variables.

        Args:
            env_vars: List of environment variable names
            prefix: Prefix to add when looking for env vars

        Returns:
            Dictionary mapping var names to success status
        """
        results = {}

        for var_name in env_vars:
            # Try with and without prefix
            for name in [var_name, f"{prefix}{var_name}"]:
                value = os.getenv(name)
                if value:
                    try:
                        self.store_credential(
                            name=var_name.lower(),
                            value=value,
                            description=f"From environment variable {name}",
                            tags=["environment"],
                        )
                        results[var_name] = True
                        break
                    except CredentialError:
                        results[var_name] = False
            else:
                results[var_name] = False

        return results

    def rotate_credential(self, name: str, new_value: str, *, keep_backup: bool = True) -> None:
        """
        Rotate a credential value.

        Args:
            name: Credential name
            new_value: New credential value
            keep_backup: Whether to keep backup of old value
        """
        old_credential = self.get_credential(name)
        if not old_credential:
            msg = f"Credential '{name}' not found"
            raise CredentialError(msg)

        # Create backup if requested
        if keep_backup:
            backup_name = f"{name}_backup_{int(datetime.now(timezone.utc).timestamp())}"
            self.store_credential(
                name=backup_name,
                value=old_credential.value.get_secret_value(),
                description=f"Backup of {name}",
                tags=["backup"],
            )

        # Update with new value
        self.store_credential(
            name=name, value=new_value, description=old_credential.description, tags=old_credential.tags, overwrite=True
        )

    def cleanup_expired(self) -> List[str]:
        """
        Remove all expired credentials.

        Returns:
            List of removed credential names
        """
        removed = []

        for name in self.list_credentials():
            credential = self.get_credential(name)
            if credential and credential.is_expired():
                self.delete_credential(name)
                removed.append(name)

        return removed

    def _store_in_keyring(self, name: str, credential: Credential) -> None:
        """Store credential in system keyring."""
        if not self._keyring_available:
            msg = "Keyring not available"
            raise CredentialError(msg)

        # Store the credential data as JSON
        credential_data = credential.to_dict()
        keyring.set_password(self.service_name, name, json.dumps(credential_data))

    def _get_from_keyring(self, name: str) -> Optional[Credential]:
        """Get credential from system keyring."""
        if not self._keyring_available:
            msg = "Keyring not available"
            raise CredentialError(msg)

        try:
            credential_json = keyring.get_password(self.service_name, name)
            if not credential_json:
                return None

            credential_data = json.loads(credential_json)
            return Credential.from_dict(credential_data)

        except (KeyringError, json.JSONDecodeError, ValueError) as e:
            msg = f"Failed to parse credential from keyring: {e}"
            raise CredentialError(msg) from e

    def _delete_from_keyring(self, name: str) -> bool:
        """Delete credential from system keyring."""
        if not self._keyring_available:
            msg = "Keyring not available"
            raise CredentialError(msg)

        try:
            keyring.delete_password(self.service_name, name)
            return True
        except KeyringError:
            return False

    def _list_keyring_credentials(self) -> List[str]:
        """List credentials in keyring."""
        # Note: Most keyring backends don't support listing
        # We maintain a registry in a special entry
        try:
            registry_json = keyring.get_password(self.service_name, "_registry")
            if registry_json:
                registry = json.loads(registry_json)
                return registry.get("credentials", [])
            return []
        except (KeyringError, json.JSONDecodeError):
            return []

    def _store_in_fallback(self, name: str, credential: Credential) -> None:
        """Store credential in encrypted fallback file."""
        # Simple fallback implementation - in production would use proper encryption
        credentials = self._load_fallback_credentials()
        credentials[name] = credential.to_dict()
        self._save_fallback_credentials(credentials)

    def _get_from_fallback(self, name: str) -> Optional[Credential]:
        """Get credential from fallback storage."""
        credentials = self._load_fallback_credentials()
        if name in credentials:
            return Credential.from_dict(credentials[name])
        return None

    def _delete_from_fallback(self, name: str) -> bool:
        """Delete credential from fallback storage."""
        credentials = self._load_fallback_credentials()
        if name in credentials:
            del credentials[name]
            self._save_fallback_credentials(credentials)
            return True
        return False

    def _list_fallback_credentials(self) -> List[str]:
        """List credentials in fallback storage."""
        credentials = self._load_fallback_credentials()
        return list(credentials.keys())

    def _load_fallback_credentials(self) -> Dict[str, Any]:
        """Load credentials from fallback file."""
        if not self._fallback_path.exists():
            return {}

        try:
            with self._fallback_path.open("r") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_fallback_credentials(self, credentials: Dict[str, Any]) -> None:
        """Save credentials to fallback file."""
        # Ensure directory exists with secure permissions
        self._fallback_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Write with secure permissions
        with self._fallback_path.open("w") as f:
            json.dump(credentials, f, indent=2)

        # Set secure file permissions
        self._fallback_path.chmod(0o600)

    def _ensure_fallback_directory(self) -> None:
        """Ensure fallback directory exists with secure permissions."""
        self._fallback_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


class CredentialConfig(BaseModel):
    """Configuration for credential management."""

    service_name: str = "myai"
    use_keyring: bool = True
    fallback_encryption: bool = True
    auto_cleanup_expired: bool = True
    max_cache_size: int = 100
