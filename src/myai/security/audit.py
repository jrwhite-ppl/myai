"""
Audit logging system for MyAI.

This module provides comprehensive audit logging for security-critical
operations, configuration changes, and user activities.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"

    # Configuration events
    CONFIG_READ = "config.read"
    CONFIG_WRITE = "config.write"
    CONFIG_DELETE = "config.delete"
    CONFIG_MERGE = "config.merge"
    CONFIG_VALIDATE = "config.validate"

    # Agent events
    AGENT_CREATE = "agent.create"
    AGENT_UPDATE = "agent.update"
    AGENT_DELETE = "agent.delete"
    AGENT_IMPORT = "agent.import"
    AGENT_EXPORT = "agent.export"
    AGENT_ENABLE = "agent.enable"
    AGENT_DISABLE = "agent.disable"

    # File operations
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    FILE_DELETE = "file.delete"
    FILE_MOVE = "file.move"
    FILE_COPY = "file.copy"
    FILE_PERMISSION = "file.permission"

    # Credential events
    CRED_CREATE = "credential.create"
    CRED_READ = "credential.read"
    CRED_UPDATE = "credential.update"
    CRED_DELETE = "credential.delete"
    CRED_ROTATE = "credential.rotate"

    # Security events
    SECURITY_VIOLATION = "security.violation"
    SECURITY_SCAN = "security.scan"
    SECURITY_ALERT = "security.alert"

    # System events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"

    # CLI events
    CLI_COMMAND = "cli.command"
    CLI_ERROR = "cli.error"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """Audit event record."""

    event_id: str = Field(default_factory=lambda: f"audit_{int(datetime.now(timezone.utc).timestamp() * 1000000)}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    user: Optional[str] = None
    session_id: Optional[str] = None
    source_ip: Optional[str] = None
    resource: Optional[str] = None
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "severity": self.severity,
            "user": self.user,
            "session_id": self.session_id,
            "source_ip": self.source_ip,
            "resource": self.resource,
            "action": self.action,
            "details": self.details,
            "result": self.result,
            "error_message": self.error_message,
        }


class AuditLogger:
    """Comprehensive audit logging system."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        max_log_size: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 5,
        *,
        console_output: bool = False,
    ):
        """
        Initialize audit logger.

        Args:
            log_file: Path to audit log file
            max_log_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            console_output: Whether to also log to console
        """
        self.log_file = log_file or Path.home() / ".myai" / "logs" / "audit.log"
        self.max_log_size = max_log_size
        self.backup_count = backup_count
        self.console_output = console_output

        # Create log directory with secure permissions
        self.log_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Set up Python logger
        self._setup_logger()

        # Session tracking
        self.session_id = f"session_{int(datetime.now(timezone.utc).timestamp())}"

    def _setup_logger(self) -> None:
        """Set up the underlying Python logger."""
        self.logger = logging.getLogger("myai.audit")
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # File handler with rotation
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler(self.log_file, maxBytes=self.max_log_size, backupCount=self.backup_count)
        file_handler.setLevel(logging.DEBUG)

        # JSON formatter for structured logging
        formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Console handler if requested
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # Set secure permissions on log file
        if self.log_file.exists():
            self.log_file.chmod(0o600)

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        user: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> str:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            action: Action performed
            severity: Event severity
            user: User performing action
            resource: Resource affected
            details: Additional event details
            result: Operation result
            error_message: Error message if applicable

        Returns:
            Event ID
        """
        event = AuditEvent(
            event_type=event_type,
            action=action,
            severity=severity,
            user=user or self._get_current_user(),
            session_id=self.session_id,
            source_ip=self._get_source_ip(),
            resource=resource,
            details=details or {},
            result=result,
            error_message=error_message,
        )

        # Log the event
        log_entry = json.dumps(event.to_dict(), ensure_ascii=False)

        if severity == AuditSeverity.CRITICAL:
            self.logger.critical(log_entry)
        elif severity == AuditSeverity.ERROR:
            self.logger.error(log_entry)
        elif severity == AuditSeverity.WARNING:
            self.logger.warning(log_entry)
        elif severity == AuditSeverity.DEBUG:
            self.logger.debug(log_entry)
        else:
            self.logger.info(log_entry)

        return event.event_id

    def log_config_change(
        self, action: str, config_path: str, old_value: Any = None, new_value: Any = None, user: Optional[str] = None
    ) -> str:
        """Log configuration change."""
        details = {"config_path": config_path}

        if old_value is not None:
            details["old_value"] = str(old_value)[:1000]  # Limit size
        if new_value is not None:
            details["new_value"] = str(new_value)[:1000]  # Limit size

        return self.log_event(
            event_type=AuditEventType.CONFIG_WRITE,
            action=action,
            severity=AuditSeverity.INFO,
            user=user,
            resource=config_path,
            details=details,
            result="success",
        )

    def log_agent_operation(
        self,
        action: str,
        agent_name: str,
        category: Optional[str] = None,
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log agent operation."""
        resource = f"agent:{agent_name}"
        if category:
            resource = f"agent:{category}/{agent_name}"

        event_type_map = {
            "create": AuditEventType.AGENT_CREATE,
            "update": AuditEventType.AGENT_UPDATE,
            "delete": AuditEventType.AGENT_DELETE,
            "import": AuditEventType.AGENT_IMPORT,
            "export": AuditEventType.AGENT_EXPORT,
            "enable": AuditEventType.AGENT_ENABLE,
            "disable": AuditEventType.AGENT_DISABLE,
        }

        event_type = event_type_map.get(action.lower(), AuditEventType.AGENT_UPDATE)

        return self.log_event(
            event_type=event_type,
            action=action,
            severity=AuditSeverity.INFO,
            user=user,
            resource=resource,
            details=details or {},
            result="success",
        )

    def log_file_operation(
        self,
        action: str,
        file_path: Union[str, Path],
        user: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log file operation."""
        file_path_str = str(file_path)

        event_type_map = {
            "read": AuditEventType.FILE_READ,
            "write": AuditEventType.FILE_WRITE,
            "delete": AuditEventType.FILE_DELETE,
            "move": AuditEventType.FILE_MOVE,
            "copy": AuditEventType.FILE_COPY,
            "chmod": AuditEventType.FILE_PERMISSION,
        }

        event_type = event_type_map.get(action.lower(), AuditEventType.FILE_WRITE)

        return self.log_event(
            event_type=event_type,
            action=action,
            severity=AuditSeverity.INFO,
            user=user,
            resource=file_path_str,
            details=details or {},
            result="success",
        )

    def log_security_event(
        self,
        action: str,
        severity: AuditSeverity = AuditSeverity.WARNING,
        details: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> str:
        """Log security event."""
        return self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action=action,
            severity=severity,
            user=user,
            details=details or {},
            result="security_event",
        )

    def log_cli_command(
        self,
        command: str,
        args: List[str],
        user: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> str:
        """Log CLI command execution."""
        details = {
            "command": command,
            "args": args[:10],  # Limit args to prevent huge logs
        }

        severity = AuditSeverity.ERROR if error else AuditSeverity.INFO

        return self.log_event(
            event_type=AuditEventType.CLI_COMMAND,
            action=f"execute_command:{command}",
            severity=severity,
            user=user,
            details=details,
            result=result,
            error_message=error,
        )

    def log_credential_operation(
        self, action: str, credential_name: str, user: Optional[str] = None, details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log credential operation."""
        event_type_map = {
            "create": AuditEventType.CRED_CREATE,
            "read": AuditEventType.CRED_READ,
            "update": AuditEventType.CRED_UPDATE,
            "delete": AuditEventType.CRED_DELETE,
            "rotate": AuditEventType.CRED_ROTATE,
        }

        event_type = event_type_map.get(action.lower(), AuditEventType.CRED_UPDATE)

        # Don't log actual credential values
        safe_details = details.copy() if details else {}
        safe_details.pop("value", None)
        safe_details.pop("password", None)
        safe_details.pop("token", None)

        return self.log_event(
            event_type=event_type,
            action=action,
            severity=AuditSeverity.INFO,
            user=user,
            resource=f"credential:{credential_name}",
            details=safe_details,
            result="success",
        )

    def search_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user: Optional[str] = None,
        resource: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search audit events.

        Args:
            event_type: Filter by event type
            user: Filter by user
            resource: Filter by resource
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of results

        Returns:
            List of matching events
        """
        events: List[Dict[str, Any]] = []

        if not self.log_file.exists():
            return events

        try:
            with self.log_file.open("r") as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())

                        # Apply filters
                        if event_type and event_data.get("event_type") != event_type:
                            continue
                        if user and event_data.get("user") != user:
                            continue
                        if resource and event_data.get("resource") != resource:
                            continue

                        # Time filters
                        if start_time or end_time:
                            event_time = datetime.fromisoformat(event_data["timestamp"])
                            if start_time and event_time < start_time:
                                continue
                            if end_time and event_time > end_time:
                                continue

                        events.append(event_data)

                        if len(events) >= limit:
                            break

                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        except OSError:
            pass

        return events[-limit:]  # Return most recent events

    def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get audit summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Summary statistics
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        events = self.search_events(start_time=start_time, end_time=end_time, limit=10000)

        summary: Dict[str, Any] = {
            "total_events": len(events),
            "time_period": f"{hours} hours",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "event_types": {},
            "severity_counts": {},
            "users": set(),
            "resources": set(),
        }

        for event in events:
            # Count event types
            event_type = event.get("event_type", "unknown")
            summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1

            # Count severities
            severity = event.get("severity", "info")
            summary["severity_counts"][severity] = summary["severity_counts"].get(severity, 0) + 1

            # Track users and resources
            if event.get("user"):
                summary["users"].add(event["user"])
            if event.get("resource"):
                summary["resources"].add(event["resource"])

        # Convert sets to lists for JSON serialization
        summary["users"] = list(summary["users"])
        summary["resources"] = list(summary["resources"])

        return summary

    def _get_current_user(self) -> str:
        """Get current user from environment."""
        return os.getenv("USER") or os.getenv("USERNAME") or "unknown"

    def _get_source_ip(self) -> Optional[str]:
        """Get source IP address."""
        # For CLI applications, this is usually localhost
        return "127.0.0.1"


class AuditConfig(BaseModel):
    """Configuration for audit logging."""

    enabled: bool = True
    log_file: Optional[Path] = None
    max_log_size: int = 100 * 1024 * 1024  # 100MB
    backup_count: int = 5
    console_output: bool = False
    log_level: str = "INFO"
    include_debug: bool = False
    compress_backups: bool = True
