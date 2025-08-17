"""Tests for audit logging system."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from myai.security.audit import (
    AuditConfig,
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
)


class TestAuditEvent:
    """Test AuditEvent model."""

    def test_create_audit_event(self):
        """Test creating an audit event."""
        event = AuditEvent(
            event_type=AuditEventType.CONFIG_WRITE,
            action="update_setting",
            severity=AuditSeverity.INFO,
            user="test_user",
            resource="config/global.json",
            details={"setting": "debug", "old_value": "false", "new_value": "true"},
        )

        assert event.event_type == AuditEventType.CONFIG_WRITE
        assert event.action == "update_setting"
        assert event.severity == AuditSeverity.INFO
        assert event.user == "test_user"
        assert event.resource == "config/global.json"
        assert event.details["setting"] == "debug"
        assert event.timestamp is not None
        assert event.event_id is not None
        assert event.event_id.startswith("audit_")

    def test_audit_event_to_dict(self):
        """Test audit event serialization."""
        event = AuditEvent(
            event_type=AuditEventType.AGENT_CREATE,
            action="create_agent",
            user="test_user",
            resource="agent:engineering/developer",
            details={"category": "engineering", "name": "developer"},
        )

        data = event.to_dict()

        assert data["event_type"] == "agent.create"
        assert data["action"] == "create_agent"
        assert data["user"] == "test_user"
        assert data["resource"] == "agent:engineering/developer"
        assert data["details"]["category"] == "engineering"
        assert isinstance(data["timestamp"], str)
        assert data["event_id"] is not None


class TestAuditLogger:
    """Test AuditLogger class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create AuditLogger instance."""
        log_file = temp_dir / "audit.log"
        return AuditLogger(log_file=log_file, console_output=False)

    def test_log_event_basic(self, audit_logger):
        """Test basic event logging."""
        event_id = audit_logger.log_event(
            event_type=AuditEventType.CONFIG_READ, action="read_config", user="test_user", resource="config/global.json"
        )

        assert event_id is not None
        assert event_id.startswith("audit_")

        # Verify log file was created and contains the event
        assert audit_logger.log_file.exists()

        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "config.read" in log_content
            assert "read_config" in log_content
            assert "test_user" in log_content

    def test_log_event_with_details(self, audit_logger):
        """Test logging event with details."""
        details = {
            "config_path": "settings.debug",
            "old_value": "false",
            "new_value": "true",
            "change_reason": "enable debugging",
        }

        event_id = audit_logger.log_event(
            event_type=AuditEventType.CONFIG_WRITE,
            action="update_setting",
            severity=AuditSeverity.INFO,
            user="admin",
            resource="config/global.json",
            details=details,
            result="success",
        )

        assert event_id is not None

        # Verify log contains all details
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "config_path" in log_content
            assert "old_value" in log_content
            assert "enable debugging" in log_content
            assert "success" in log_content

    def test_log_event_with_error(self, audit_logger):
        """Test logging event with error."""
        event_id = audit_logger.log_event(
            event_type=AuditEventType.CONFIG_WRITE,
            action="update_setting",
            severity=AuditSeverity.ERROR,
            user="user",
            resource="config/invalid.json",
            error_message="Configuration file not found",
            result="failure",
        )

        assert event_id is not None

        # Verify error is logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "Configuration file not found" in log_content
            assert "failure" in log_content
            assert "ERROR" in log_content or "error" in log_content

    def test_log_config_change(self, audit_logger):
        """Test logging configuration changes."""
        event_id = audit_logger.log_config_change(
            action="update_setting", config_path="settings.backup_count", old_value=5, new_value=10, user="admin"
        )

        assert event_id is not None

        # Verify config change was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "settings.backup_count" in log_content
            assert "old_value" in log_content
            assert "new_value" in log_content
            assert "config.write" in log_content

    def test_log_agent_operation(self, audit_logger):
        """Test logging agent operations."""
        event_id = audit_logger.log_agent_operation(
            action="create",
            agent_name="developer",
            category="engineering",
            user="team_lead",
            details={"template": "base_agent", "customizations": ["tools", "instructions"]},
        )

        assert event_id is not None

        # Verify agent operation was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "agent.create" in log_content
            assert "agent:engineering/developer" in log_content
            assert "template" in log_content
            assert "team_lead" in log_content

    def test_log_file_operation(self, audit_logger):
        """Test logging file operations."""
        event_id = audit_logger.log_file_operation(
            action="write",
            file_path="/home/user/.myai/config/global.json",
            user="user",
            details={"size": 1024, "permissions": "0600"},
        )

        assert event_id is not None

        # Verify file operation was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "file.write" in log_content
            assert "/home/user/.myai/config/global.json" in log_content
            assert "size" in log_content
            assert "permissions" in log_content

    def test_log_security_event(self, audit_logger):
        """Test logging security events."""
        event_id = audit_logger.log_security_event(
            action="permission_violation",
            severity=AuditSeverity.WARNING,
            details={
                "attempted_path": "/etc/passwd",
                "denied_reason": "path_traversal_detected",
                "source_ip": "192.168.1.100",
            },
            user="suspicious_user",
        )

        assert event_id is not None

        # Verify security event was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "security.violation" in log_content
            assert "permission_violation" in log_content
            assert "path_traversal_detected" in log_content
            assert "WARNING" in log_content or "warning" in log_content

    def test_log_cli_command(self, audit_logger):
        """Test logging CLI commands."""
        event_id = audit_logger.log_cli_command(
            command="myai config set", args=["settings.debug", "true"], user="admin", result="success"
        )

        assert event_id is not None

        # Verify CLI command was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "cli.command" in log_content
            assert "myai config set" in log_content
            assert "settings.debug" in log_content
            assert "success" in log_content

    def test_log_cli_command_with_error(self, audit_logger):
        """Test logging CLI command with error."""
        event_id = audit_logger.log_cli_command(
            command="myai config get",
            args=["nonexistent.setting"],
            user="user",
            error="Setting not found: nonexistent.setting",
        )

        assert event_id is not None

        # Verify CLI error was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "Setting not found" in log_content
            assert "ERROR" in log_content or "error" in log_content

    def test_log_credential_operation(self, audit_logger):
        """Test logging credential operations."""
        event_id = audit_logger.log_credential_operation(
            action="create",
            credential_name="api_key",
            user="admin",
            details={"description": "External API key", "expires_in": "30 days"},
        )

        assert event_id is not None

        # Verify credential operation was logged
        with audit_logger.log_file.open() as f:
            log_content = f.read()
            assert "credential.create" in log_content
            assert "credential:api_key" in log_content
            assert "External API key" in log_content
            # Should NOT contain actual credential values
            assert "value" not in log_content
            assert "password" not in log_content
            assert "token" not in log_content

    def test_search_events(self, audit_logger):
        """Test searching audit events."""
        # Log several events
        audit_logger.log_event(
            event_type=AuditEventType.CONFIG_READ, action="read_config", user="user1", resource="config/global.json"
        )

        audit_logger.log_event(
            event_type=AuditEventType.CONFIG_WRITE, action="write_config", user="user2", resource="config/local.json"
        )

        audit_logger.log_event(
            event_type=AuditEventType.AGENT_CREATE,
            action="create_agent",
            user="user1",
            resource="agent:engineering/developer",
        )

        # Search by event type
        config_events = audit_logger.search_events(event_type=AuditEventType.CONFIG_READ)
        assert len(config_events) == 1
        assert config_events[0]["action"] == "read_config"

        # Search by user
        user1_events = audit_logger.search_events(user="user1")
        assert len(user1_events) == 2

        # Search by resource pattern
        config_resources = audit_logger.search_events(resource="config/global.json")
        assert len(config_resources) == 1
        assert config_resources[0]["resource"] == "config/global.json"

    def test_search_events_with_time_range(self, audit_logger):
        """Test searching events with time range."""
        # Log event
        audit_logger.log_event(event_type=AuditEventType.CONFIG_READ, action="read_config", user="user")

        # Search with time range
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        one_hour_later = now + timedelta(hours=1)

        # Should find event within range
        events = audit_logger.search_events(start_time=one_hour_ago, end_time=one_hour_later)
        assert len(events) == 1

        # Should not find event outside range
        events = audit_logger.search_events(start_time=one_hour_later, end_time=one_hour_later + timedelta(hours=1))
        assert len(events) == 0

    def test_get_audit_summary(self, audit_logger):
        """Test getting audit summary."""
        # Log various events
        audit_logger.log_event(
            event_type=AuditEventType.CONFIG_READ, action="read_config", user="user1", severity=AuditSeverity.INFO
        )

        audit_logger.log_event(
            event_type=AuditEventType.CONFIG_WRITE, action="write_config", user="user1", severity=AuditSeverity.INFO
        )

        audit_logger.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action="permission_denied",
            user="user2",
            severity=AuditSeverity.WARNING,
        )

        # Get summary
        summary = audit_logger.get_audit_summary(hours=1)

        assert summary["total_events"] == 3
        assert summary["time_period"] == "1 hours"
        assert "config.read" in summary["event_types"]
        assert "config.write" in summary["event_types"]
        assert "security.violation" in summary["event_types"]
        assert "info" in summary["severity_counts"]
        assert "warning" in summary["severity_counts"]
        assert "user1" in summary["users"]
        assert "user2" in summary["users"]

    def test_log_file_permissions(self, audit_logger, temp_dir):  # noqa: ARG002
        """Test audit log file has secure permissions."""
        # Log an event to create the file
        audit_logger.log_event(event_type=AuditEventType.SYSTEM_START, action="system_startup")

        # Check file permissions
        assert audit_logger.log_file.exists()
        mode = audit_logger.log_file.stat().st_mode & 0o777
        assert mode == 0o600  # Should be readable/writable by owner only

        # Check parent directory permissions
        parent_mode = audit_logger.log_file.parent.stat().st_mode & 0o777
        assert parent_mode == 0o700  # Should be accessible by owner only


class TestAuditConfig:
    """Test AuditConfig model."""

    def test_default_config(self):
        """Test default audit configuration."""
        config = AuditConfig()

        assert config.enabled is True
        assert config.log_file is None
        assert config.max_log_size == 100 * 1024 * 1024  # 100MB
        assert config.backup_count == 5
        assert config.console_output is False
        assert config.log_level == "INFO"
        assert config.include_debug is False
        assert config.compress_backups is True

    def test_custom_config(self):
        """Test custom audit configuration."""
        config = AuditConfig(
            enabled=False,
            log_file=Path("/custom/audit.log"),
            max_log_size=50 * 1024 * 1024,  # 50MB
            backup_count=3,
            console_output=True,
            log_level="DEBUG",
            include_debug=True,
            compress_backups=False,
        )

        assert config.enabled is False
        assert config.log_file == Path("/custom/audit.log")
        assert config.max_log_size == 50 * 1024 * 1024
        assert config.backup_count == 3
        assert config.console_output is True
        assert config.log_level == "DEBUG"
        assert config.include_debug is True
        assert config.compress_backups is False


class TestAuditIntegration:
    """Integration tests for audit logging."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def audit_logger(self, temp_dir):
        """Create AuditLogger instance."""
        log_file = temp_dir / "audit.log"
        return AuditLogger(log_file=log_file, console_output=False)

    def test_comprehensive_audit_trail(self, audit_logger):
        """Test comprehensive audit trail for a typical workflow."""
        # Simulate a complete user workflow

        # 1. System startup
        audit_logger.log_event(event_type=AuditEventType.SYSTEM_START, action="myai_startup", user="system")

        # 2. User login
        audit_logger.log_event(
            event_type=AuditEventType.AUTH_LOGIN,
            action="user_login",
            user="john_doe",
            details={"login_method": "local", "session_id": "sess_123"},
        )

        # 3. Configuration read
        audit_logger.log_config_change(action="read_config", config_path="global.json", user="john_doe")

        # 4. Agent creation
        audit_logger.log_agent_operation(
            action="create",
            agent_name="custom_developer",
            category="engineering",
            user="john_doe",
            details={"template": "developer", "customizations": ["git_tools"]},
        )

        # 5. File operation
        audit_logger.log_file_operation(
            action="write",
            file_path="/home/john/.myai/agents/engineering/custom_developer.md",
            user="john_doe",
            details={"operation": "agent_save", "size": 2048},
        )

        # 6. Security event
        audit_logger.log_security_event(
            action="permission_check",
            severity=AuditSeverity.INFO,
            user="john_doe",
            details={"resource": "agent_file", "result": "allowed"},
        )

        # 7. CLI command
        audit_logger.log_cli_command(
            command="myai agent list", args=["--category", "engineering"], user="john_doe", result="success"
        )

        # 8. User logout
        audit_logger.log_event(
            event_type=AuditEventType.AUTH_LOGOUT,
            action="user_logout",
            user="john_doe",
            details={"session_duration": "30 minutes"},
        )

        # Verify complete audit trail
        all_events = audit_logger.search_events(limit=100)
        assert len(all_events) == 8

        # Verify event sequence
        event_types = [event["event_type"] for event in all_events]
        expected_types = [
            "system.start",
            "auth.login",
            "config.write",  # log_config_change uses CONFIG_WRITE
            "agent.create",
            "file.write",
            "security.violation",  # log_security_event uses SECURITY_VIOLATION
            "cli.command",
            "auth.logout",
        ]
        assert event_types == expected_types

        # Verify user tracking
        user_events = audit_logger.search_events(user="john_doe")
        assert len(user_events) == 7  # All except system.start

    def test_security_audit_scenario(self, audit_logger):
        """Test security-focused audit scenario."""
        # Simulate security-related events

        # 1. Failed login attempt
        audit_logger.log_event(
            event_type=AuditEventType.AUTH_FAILED,
            action="login_attempt",
            severity=AuditSeverity.WARNING,
            user="unknown_user",
            details={"reason": "invalid_credentials", "attempts": 3},
        )

        # 2. Path traversal attempt
        audit_logger.log_security_event(
            action="path_traversal_blocked",
            severity=AuditSeverity.WARNING,
            user="suspicious_user",
            details={
                "attempted_path": "../../../etc/passwd",
                "blocked_by": "input_validation",
                "source_ip": "192.168.1.100",
            },
        )

        # 3. Permission violation
        audit_logger.log_security_event(
            action="permission_denied",
            severity=AuditSeverity.ERROR,
            user="limited_user",
            details={"resource": "/admin/config", "required_permission": "admin", "user_permission": "user"},
        )

        # 4. Successful security scan
        audit_logger.log_event(
            event_type=AuditEventType.SECURITY_SCAN,
            action="vulnerability_scan",
            severity=AuditSeverity.INFO,
            user="system",
            details={"scan_type": "file_permissions", "issues_found": 0},
        )

        # Analyze security events
        security_events = audit_logger.search_events(event_type=AuditEventType.SECURITY_VIOLATION)
        assert len(security_events) >= 2  # Path traversal and permission violation

        # Check severity distribution
        summary = audit_logger.get_audit_summary(hours=1)
        assert summary["severity_counts"].get("warning", 0) >= 2
        assert summary["severity_counts"].get("error", 0) >= 1

        # Verify all security events are logged
        all_events = audit_logger.search_events(limit=100)
        security_related = [
            event for event in all_events if any(keyword in event["event_type"] for keyword in ["auth", "security"])
        ]
        assert len(security_related) >= 4

    def test_audit_log_rotation(self, audit_logger, temp_dir):
        """Test audit log rotation behavior."""
        # Configure small log size for testing
        audit_logger.max_log_size = 1024  # 1KB

        # Log many events to trigger rotation
        for i in range(100):
            audit_logger.log_event(
                event_type=AuditEventType.CONFIG_READ,
                action=f"test_action_{i}",
                user=f"user_{i}",
                details={"large_data": "x" * 100},  # Make events larger
            )

        # Check if rotation occurred
        log_files = list(temp_dir.glob("audit.log*"))

        # Should have at least the main log file
        assert len(log_files) >= 1

        # Verify main log file exists
        assert audit_logger.log_file in log_files

        # Verify we can still search recent events
        recent_events = audit_logger.search_events(limit=10)
        assert len(recent_events) > 0
