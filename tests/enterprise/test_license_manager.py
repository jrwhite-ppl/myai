"""
Tests for license manager functionality.
"""

from datetime import datetime, timedelta, timezone

import pytest

from myai.enterprise.license_manager import (
    FeatureFlag,
    License,
    LicenseManager,
    LicenseStatus,
    LicenseType,
)


class TestLicense:
    """Test cases for the License class."""

    def test_license_creation(self):
        """Test license creation."""
        valid_until = datetime.now(timezone.utc) + timedelta(days=30)

        test_license = License(
            license_key="TEST-KEY-123",
            license_type=LicenseType.PROFESSIONAL,
            organization="Test Org",
            max_users=10,
            valid_until=valid_until,
            features={FeatureFlag.AUTO_SYNC, FeatureFlag.CONFLICT_RESOLUTION},
        )

        assert test_license.license_key == "TEST-KEY-123"
        assert test_license.license_type == LicenseType.PROFESSIONAL
        assert test_license.organization == "Test Org"
        assert test_license.max_users == 10
        assert test_license.valid_until == valid_until
        assert len(test_license.features) == 2

    def test_license_validity(self):
        """Test license validity checks."""
        # Valid license
        valid_license = License(
            license_key="VALID-ENTERPRISE-LICENSE-KEY-123456",
            license_type=LicenseType.ENTERPRISE,
            organization="Test Org",
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        )

        assert valid_license.is_valid()
        assert valid_license.get_status() == LicenseStatus.VALID

    def test_license_expiration(self):
        """Test license expiration."""
        # Expired license
        expired_license = License(
            license_key="EXPIRED-PROFESSIONAL-LICENSE-KEY-123456",
            license_type=LicenseType.PROFESSIONAL,
            organization="Test Org",
            valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        )

        assert not expired_license.is_valid()
        assert expired_license.get_status() == LicenseStatus.EXPIRED

    def test_license_key_validation(self):
        """Test license key validation."""
        # Invalid key (too short)
        invalid_license = License(
            license_key="SHORT",
            license_type=LicenseType.COMMUNITY,
            organization="Test Org",
        )

        assert not invalid_license.is_valid()
        assert invalid_license.get_status() == LicenseStatus.INVALID

    def test_feature_checking(self):
        """Test feature availability checking."""
        test_license = License(
            license_key="FEATURE-TEST-123",
            license_type=LicenseType.ENTERPRISE,
            organization="Test Org",
            features={FeatureFlag.POLICY_ENFORCEMENT, FeatureFlag.USAGE_ANALYTICS},
        )

        assert test_license.has_feature(FeatureFlag.POLICY_ENFORCEMENT)
        assert test_license.has_feature(FeatureFlag.USAGE_ANALYTICS)
        assert not test_license.has_feature(FeatureFlag.SSO)

    def test_days_remaining(self):
        """Test days remaining calculation."""
        # 30 days remaining
        future_license = License(
            license_key="FUTURE-KEY-123",
            license_type=LicenseType.TRIAL,
            organization="Test Org",
            valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        )

        days = future_license.days_remaining()
        assert days is not None
        assert days >= 29  # Allow for small time differences

        # No expiration
        permanent_license = License(
            license_key="PERMANENT-KEY-123",
            license_type=LicenseType.ENTERPRISE,
            organization="Test Org",
            valid_until=None,
        )

        assert permanent_license.days_remaining() is None

    def test_license_dict_conversion(self):
        """Test license to dictionary conversion."""
        test_license = License(
            license_key="DICT-TEST-123-456",
            license_type=LicenseType.PROFESSIONAL,
            organization="Test Org",
            max_users=5,
            features={FeatureFlag.AUTO_SYNC},
        )

        license_dict = test_license.to_dict()

        # Key should be masked
        assert license_dict["license_key"] == "DICT-TES...-456"
        assert license_dict["license_type"] == "professional"
        assert license_dict["organization"] == "Test Org"
        assert license_dict["max_users"] == 5
        assert "auto_sync" in license_dict["features"]


class TestLicenseManager:
    """Test cases for the LicenseManager."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use a temporary location for testing
        import tempfile
        from pathlib import Path

        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = LicenseManager(license_file=self.temp_dir / "test_license.json")

    def test_community_license_creation(self):
        """Test default community license creation."""
        license_info = self.manager.get_license_info()

        assert license_info["license_type"] == "community"

    def test_feature_checking(self):
        """Test feature availability checking."""
        # Community features should be available
        assert self.manager.check_feature(FeatureFlag.BASIC_AGENTS)
        assert self.manager.check_feature(FeatureFlag.BASIC_CONFIG)

        # Enterprise features should not be available
        assert not self.manager.check_feature(FeatureFlag.POLICY_ENFORCEMENT)
        assert not self.manager.check_feature(FeatureFlag.USAGE_ANALYTICS)

    def test_feature_enforcement(self):
        """Test feature enforcement."""
        # Community feature should not raise exception
        self.manager.enforce_feature(FeatureFlag.BASIC_AGENTS)

        # Enterprise feature should raise exception
        with pytest.raises(PermissionError):
            self.manager.enforce_feature(FeatureFlag.POLICY_ENFORCEMENT)

    def test_trial_license_creation(self):
        """Test trial license creation."""
        trial_key = self.manager.create_trial_license("TestOrg", days=14)

        assert trial_key is not None
        assert trial_key.startswith("TRL-TES")

        license_info = self.manager.get_license_info()
        assert license_info["license_type"] == "trial"

        # Should have enterprise features during trial
        assert self.manager.check_feature(FeatureFlag.POLICY_ENFORCEMENT)
        assert self.manager.check_feature(FeatureFlag.USAGE_ANALYTICS)

    def test_license_activation(self):
        """Test license activation."""
        # Valid professional license key
        pro_key = "PRO-TEST-5-20251231-VALID"

        success = self.manager.activate_license(pro_key)
        assert success

        license_info = self.manager.get_license_info()
        assert license_info["license_type"] == "professional"

        # Should have professional features
        assert self.manager.check_feature(FeatureFlag.AUTO_SYNC)
        assert self.manager.check_feature(FeatureFlag.CONFLICT_RESOLUTION)

        # Should not have enterprise-only features
        assert not self.manager.check_feature(FeatureFlag.POLICY_ENFORCEMENT)

    def test_enterprise_license_activation(self):
        """Test enterprise license activation."""
        # Valid enterprise license key
        ent_key = "ENT-CORP-50-NEVER-VALID"

        success = self.manager.activate_license(ent_key)
        assert success

        license_info = self.manager.get_license_info()
        assert license_info["license_type"] == "enterprise"
        assert license_info["max_users"] == 50

        # Should have all features
        assert self.manager.check_feature(FeatureFlag.BASIC_AGENTS)
        assert self.manager.check_feature(FeatureFlag.AUTO_SYNC)
        assert self.manager.check_feature(FeatureFlag.POLICY_ENFORCEMENT)
        assert self.manager.check_feature(FeatureFlag.USAGE_ANALYTICS)
        assert self.manager.check_feature(FeatureFlag.RBAC)

    def test_invalid_license_activation(self):
        """Test invalid license activation."""
        invalid_key = "INVALID-KEY"

        success = self.manager.activate_license(invalid_key)
        assert not success

        # Should still have community license
        license_info = self.manager.get_license_info()
        assert license_info["license_type"] == "community"

    def test_feature_usage_tracking(self):
        """Test feature usage tracking."""
        # Load a valid license first so usage tracking works
        license_key = self.manager.create_trial_license("TestOrg", days=30)
        success = self.manager.activate_license(license_key)
        assert success

        # Use some features
        self.manager.check_feature(FeatureFlag.BASIC_AGENTS)
        self.manager.check_feature(FeatureFlag.BASIC_AGENTS)
        self.manager.check_feature(FeatureFlag.BASIC_CONFIG)

        usage_stats = self.manager.get_feature_usage()

        assert usage_stats["total_feature_checks"] == 3
        assert "basic_agents" in usage_stats["feature_breakdown"]
        assert usage_stats["feature_breakdown"]["basic_agents"]["count"] == 2
        assert usage_stats["most_used_feature"] == "basic_agents"

    def test_compliance_status(self):
        """Test compliance status checking."""
        # Community license should be compliant
        status = self.manager.get_compliance_status()

        assert status["compliant"] is True
        assert status["license_type"] == "community"
        assert len(status["warnings"]) == 0

    def test_expired_license_compliance(self):
        """Test compliance with expired license."""
        # Create expired trial
        self.manager.create_trial_license("TestOrg", days=-1)  # Already expired

        status = self.manager.get_compliance_status()
        assert status["compliant"] is False
        assert len(status["warnings"]) > 0
        assert any("expired" in warning.lower() for warning in status["warnings"])

    def test_license_upgrade(self):
        """Test license upgrade."""
        # Start with trial
        self.manager.create_trial_license("TestOrg")
        assert self.manager.get_license_info()["license_type"] == "trial"

        # Upgrade to professional
        pro_key = "PRO-TEST-10-20251231-VALID"
        success = self.manager.upgrade_license(pro_key)
        assert success

        license_info = self.manager.get_license_info()
        assert license_info["license_type"] == "professional"

    def test_license_persistence(self):
        """Test license persistence to file."""
        # Create trial license
        self.manager.create_trial_license("TestOrg", days=30)

        # Create new manager with same file
        new_manager = LicenseManager(license_file=self.manager.license_file)

        # Should load the same license
        license_info = new_manager.get_license_info()
        assert license_info["license_type"] == "trial"
        assert license_info["organization"] == "TestOrg"
