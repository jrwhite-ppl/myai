"""
License management system for MyAI enterprise features.

This module provides license validation, feature enforcement, and
compliance tracking for enterprise deployments.
"""

import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from myai.models.path import PathManager


class LicenseType(Enum):
    """Types of licenses."""

    COMMUNITY = "community"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    TRIAL = "trial"


class LicenseStatus(Enum):
    """License status."""

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class FeatureFlag(Enum):
    """Enterprise features that can be enabled/disabled."""

    # Core features (always available)
    BASIC_AGENTS = "basic_agents"
    BASIC_CONFIG = "basic_config"

    # Professional features
    ADVANCED_INTEGRATIONS = "advanced_integrations"
    AUTO_SYNC = "auto_sync"
    CONFLICT_RESOLUTION = "conflict_resolution"

    # Enterprise features
    POLICY_ENFORCEMENT = "policy_enforcement"
    CENTRAL_MANAGEMENT = "central_management"
    USAGE_ANALYTICS = "usage_analytics"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    AUDIT_LOGGING = "audit_logging"
    RBAC = "rbac"  # Role-based access control
    SSO = "sso"  # Single sign-on

    # Trial features (time-limited)
    TRIAL_ENTERPRISE = "trial_enterprise"


class License:
    """License information and validation."""

    def __init__(
        self,
        license_key: str,
        license_type: LicenseType,
        organization: str,
        max_users: int = 1,
        valid_until: Optional[datetime] = None,
        features: Optional[Set[FeatureFlag]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.license_key = license_key
        self.license_type = license_type
        self.organization = organization
        self.max_users = max_users
        self.valid_until = valid_until
        self.features = features or set()
        self.metadata = metadata or {}

        # Runtime state
        self.issued_at = datetime.now(timezone.utc)
        self.last_validated = None
        self.validation_count = 0

    def is_valid(self) -> bool:
        """Check if license is currently valid."""
        # Check expiration
        if self.valid_until and datetime.now(timezone.utc) > self.valid_until:
            return False

        # Check license key format (basic validation)
        if not self._validate_license_key():
            return False

        return True

    def _validate_license_key(self) -> bool:
        """Validate license key format and checksum."""
        # Basic format validation
        min_license_key_length = 20
        if not self.license_key or len(self.license_key) < min_license_key_length:
            return False

        # In a real implementation, this would validate against a signature
        # For now, just check if it looks like a valid key
        return self.license_key.replace("-", "").isalnum()

    def get_status(self) -> LicenseStatus:
        """Get current license status."""
        if not self.is_valid():
            if self.valid_until and datetime.now(timezone.utc) > self.valid_until:
                return LicenseStatus.EXPIRED
            return LicenseStatus.INVALID

        if self.license_type == LicenseType.TRIAL:
            return LicenseStatus.TRIAL

        return LicenseStatus.VALID

    def has_feature(self, feature: FeatureFlag) -> bool:
        """Check if license includes a specific feature."""
        return feature in self.features

    def days_remaining(self) -> Optional[int]:
        """Get number of days remaining on license."""
        if not self.valid_until:
            return None

        remaining = self.valid_until - datetime.now(timezone.utc)
        return max(0, remaining.days)

    def to_dict(self) -> Dict[str, Any]:
        """Convert license to dictionary."""
        return {
            "license_key": self.license_key[:8] + "..." + self.license_key[-4:],  # Masked
            "license_type": self.license_type.value,
            "organization": self.organization,
            "max_users": self.max_users,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "features": [f.value for f in self.features],
            "status": self.get_status().value,
            "days_remaining": self.days_remaining(),
            "issued_at": self.issued_at.isoformat(),
        }


class LicenseManager:
    """License management and feature enforcement."""

    def __init__(self, license_file: Optional[Path] = None):
        self.license_file = license_file or (PathManager().get_user_path() / "license.json")
        self.current_license: Optional[License] = None
        self.feature_usage: Dict[str, int] = {}

        # Default feature sets by license type
        self.default_features = {
            LicenseType.COMMUNITY: {
                FeatureFlag.BASIC_AGENTS,
                FeatureFlag.BASIC_CONFIG,
            },
            LicenseType.PROFESSIONAL: {
                FeatureFlag.BASIC_AGENTS,
                FeatureFlag.BASIC_CONFIG,
                FeatureFlag.ADVANCED_INTEGRATIONS,
                FeatureFlag.AUTO_SYNC,
                FeatureFlag.CONFLICT_RESOLUTION,
            },
            LicenseType.ENTERPRISE: {
                FeatureFlag.BASIC_AGENTS,
                FeatureFlag.BASIC_CONFIG,
                FeatureFlag.ADVANCED_INTEGRATIONS,
                FeatureFlag.AUTO_SYNC,
                FeatureFlag.CONFLICT_RESOLUTION,
                FeatureFlag.POLICY_ENFORCEMENT,
                FeatureFlag.CENTRAL_MANAGEMENT,
                FeatureFlag.USAGE_ANALYTICS,
                FeatureFlag.PERFORMANCE_OPTIMIZATION,
                FeatureFlag.AUDIT_LOGGING,
                FeatureFlag.RBAC,
                FeatureFlag.SSO,
            },
            LicenseType.TRIAL: {
                FeatureFlag.BASIC_AGENTS,
                FeatureFlag.BASIC_CONFIG,
                FeatureFlag.TRIAL_ENTERPRISE,
            },
        }

        # Load existing license
        self._load_license()

    def _load_license(self) -> None:
        """Load license from file."""
        if not self.license_file.exists():
            # Create default community license
            self.current_license = self._create_community_license()
            return

        try:
            with open(self.license_file) as f:
                license_data = json.load(f)

            # Reconstruct license object
            features = {FeatureFlag(f) for f in license_data.get("features", [])}
            valid_until = None
            if license_data.get("valid_until"):
                valid_until = datetime.fromisoformat(license_data["valid_until"])

            self.current_license = License(
                license_key=license_data["license_key"],
                license_type=LicenseType(license_data["license_type"]),
                organization=license_data["organization"],
                max_users=license_data.get("max_users", 1),
                valid_until=valid_until,
                features=features,
                metadata=license_data.get("metadata", {}),
            )

        except Exception as e:
            print(f"Error loading license: {e}")
            self.current_license = self._create_community_license()

    def _save_license(self) -> None:
        """Save current license to file."""
        if not self.current_license:
            return

        try:
            license_data = {
                "license_key": self.current_license.license_key,
                "license_type": self.current_license.license_type.value,
                "organization": self.current_license.organization,
                "max_users": self.current_license.max_users,
                "valid_until": (
                    self.current_license.valid_until.isoformat() if self.current_license.valid_until else None
                ),
                "features": [f.value for f in self.current_license.features],
                "metadata": self.current_license.metadata,
            }

            with open(self.license_file, "w") as f:
                json.dump(license_data, f, indent=2)

        except Exception as e:
            print(f"Error saving license: {e}")

    def _create_community_license(self) -> License:
        """Create a default community license."""
        return License(
            license_key="community-" + str(uuid4())[:8],
            license_type=LicenseType.COMMUNITY,
            organization="Community User",
            max_users=1,
            features=self.default_features[LicenseType.COMMUNITY],
        )

    def activate_license(self, license_key: str) -> bool:
        """Activate a new license."""
        # In a real implementation, this would validate with a license server
        license_info = self._validate_license_key(license_key)

        if not license_info:
            return False

        self.current_license = license_info
        self._save_license()

        return True

    def _validate_license_key(self, license_key: str) -> Optional[License]:
        """Validate license key and return license info."""
        # This is a simplified validation - in reality, this would
        # communicate with a license server or validate cryptographic signatures

        try:
            # Parse license key format: TYPE-ORG-USERS-EXPIRY-CHECKSUM
            parts = license_key.split("-")
            min_license_key_parts = 4
            if len(parts) < min_license_key_parts:
                return None

            license_type_code = parts[0]
            org_code = parts[1]
            user_count = int(parts[2])
            expiry_code = parts[3]

            # Decode license type
            type_mapping = {
                "PRO": LicenseType.PROFESSIONAL,
                "ENT": LicenseType.ENTERPRISE,
                "TRL": LicenseType.TRIAL,
            }

            license_type = type_mapping.get(license_type_code, LicenseType.COMMUNITY)

            # Decode expiry (simple format: YYYYMMDD)
            if expiry_code != "NEVER":
                try:
                    year = int(expiry_code[:4])
                    month = int(expiry_code[4:6])
                    day = int(expiry_code[6:8])
                    valid_until = datetime(year, month, day, tzinfo=timezone.utc)
                except ValueError:
                    valid_until = datetime.now(timezone.utc) + timedelta(days=30)  # Default trial
            else:
                valid_until = None

            # Create license
            features = self.default_features.get(license_type, set())

            return License(
                license_key=license_key,
                license_type=license_type,
                organization=f"Organization {org_code}",
                max_users=user_count,
                valid_until=valid_until,
                features=features,
            )

        except Exception as e:
            print(f"Error validating license key: {e}")
            return None

    def check_feature(self, feature: FeatureFlag) -> bool:
        """Check if a feature is available under current license."""
        if not self.current_license:
            return feature in self.default_features[LicenseType.COMMUNITY]

        # Check license validity
        if not self.current_license.is_valid():
            # Fall back to community features if license is invalid/expired
            return feature in self.default_features[LicenseType.COMMUNITY]

        # Track feature usage
        self.feature_usage[feature.value] = self.feature_usage.get(feature.value, 0) + 1

        return self.current_license.has_feature(feature)

    def enforce_feature(self, feature: FeatureFlag) -> None:
        """Enforce feature availability (raise exception if not available)."""
        if not self.check_feature(feature):
            license_type = self.current_license.license_type.value if self.current_license else "community"
            msg = f"Feature '{feature.value}' not available in {license_type} license"
            raise PermissionError(msg)

    def get_license_info(self) -> Dict[str, Any]:
        """Get current license information."""
        if not self.current_license:
            return {"license_type": "community", "status": "active"}

        return self.current_license.to_dict()

    def get_feature_usage(self) -> Dict[str, Any]:
        """Get feature usage statistics."""
        total_usage = sum(self.feature_usage.values())

        usage_stats = {}
        for feature, count in self.feature_usage.items():
            usage_stats[feature] = {
                "count": count,
                "percentage": (count / max(total_usage, 1)) * 100,
            }

        return {
            "total_feature_checks": total_usage,
            "feature_breakdown": usage_stats,
            "most_used_feature": max(self.feature_usage.items(), key=lambda x: x[1])[0] if self.feature_usage else None,
        }

    def create_trial_license(self, organization: str, days: int = 30) -> str:
        """Create a trial license."""
        expiry_date = datetime.now(timezone.utc) + timedelta(days=days)
        expiry_code = expiry_date.strftime("%Y%m%d")

        # Generate trial license key
        trial_key = f"TRL-{organization[:3].upper()}-10-{expiry_code}-TRIAL"

        # Create and activate license
        features = self.default_features[LicenseType.ENTERPRISE].copy()  # Full features for trial
        features.add(FeatureFlag.TRIAL_ENTERPRISE)

        trial_license = License(
            license_key=trial_key,
            license_type=LicenseType.TRIAL,
            organization=organization,
            max_users=10,  # Limited users for trial
            valid_until=expiry_date,
            features=features,
            metadata={"trial_created": datetime.now(timezone.utc).isoformat()},
        )

        self.current_license = trial_license
        self._save_license()

        return trial_key

    def upgrade_license(self, new_license_key: str) -> bool:
        """Upgrade to a new license."""
        return self.activate_license(new_license_key)

    def get_compliance_status(self) -> Dict[str, Any]:
        """Get license compliance status."""
        if not self.current_license:
            return {
                "compliant": True,
                "license_type": "community",
                "warnings": [],
            }

        warnings = []

        # Check expiration
        days_remaining = self.current_license.days_remaining()
        if days_remaining is not None:
            if days_remaining <= 0:
                warnings.append("License has expired")
            else:
                warning_threshold_days = 30
                if days_remaining <= warning_threshold_days:
                    warnings.append(f"License expires in {days_remaining} days")

        # Check user limits (would need actual user tracking)
        # This is a placeholder
        current_users = 1  # Would be actual user count
        if current_users > self.current_license.max_users:
            warnings.append(f"User count ({current_users}) exceeds license limit ({self.current_license.max_users})")

        return {
            "compliant": len(warnings) == 0,
            "license_type": self.current_license.license_type.value,
            "status": self.current_license.get_status().value,
            "warnings": warnings,
            "expires": self.current_license.valid_until.isoformat() if self.current_license.valid_until else None,
            "days_remaining": days_remaining,
        }


# Global license manager instance
_license_manager: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """Get the global license manager instance."""
    global _license_manager  # noqa: PLW0603
    if _license_manager is None:
        _license_manager = LicenseManager()
    return _license_manager
