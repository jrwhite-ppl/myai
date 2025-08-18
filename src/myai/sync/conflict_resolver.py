"""
Conflict detection and resolution system for MyAI.

This module provides sophisticated conflict detection and resolution
capabilities for handling conflicts between different tools and configurations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from myai.models.agent import AgentSpecification


class ConflictType(Enum):
    """Types of conflicts that can occur."""

    # Agent conflicts
    AGENT_NAME_CONFLICT = "agent_name_conflict"
    AGENT_CONTENT_CONFLICT = "agent_content_conflict"
    AGENT_METADATA_CONFLICT = "agent_metadata_conflict"
    AGENT_VERSION_CONFLICT = "agent_version_conflict"

    # Configuration conflicts
    CONFIG_VALUE_CONFLICT = "config_value_conflict"
    CONFIG_SCHEMA_CONFLICT = "config_schema_conflict"
    CONFIG_PATH_CONFLICT = "config_path_conflict"

    # Tool conflicts
    TOOL_SETTINGS_CONFLICT = "tool_settings_conflict"
    TOOL_VERSION_CONFLICT = "tool_version_conflict"
    TOOL_PATH_CONFLICT = "tool_path_conflict"

    # File conflicts
    FILE_MODIFICATION_CONFLICT = "file_modification_conflict"
    FILE_DELETION_CONFLICT = "file_deletion_conflict"
    FILE_PERMISSION_CONFLICT = "file_permission_conflict"

    # Dependency conflicts
    DEPENDENCY_CONFLICT = "dependency_conflict"
    CIRCULAR_DEPENDENCY = "circular_dependency"


class ConflictSeverity(Enum):
    """Severity levels for conflicts."""

    LOW = "low"  # Can be automatically resolved
    MEDIUM = "medium"  # Requires user attention but has suggestions
    HIGH = "high"  # Requires manual resolution
    CRITICAL = "critical"  # Blocks operation


class ConflictResolution(Enum):
    """Possible conflict resolution strategies."""

    # Automatic resolutions
    USE_LOCAL = "use_local"  # Use local version
    USE_REMOTE = "use_remote"  # Use remote version
    USE_LATEST = "use_latest"  # Use most recent version
    MERGE_CONTENT = "merge_content"  # Merge content intelligently

    # Manual resolutions
    ASK_USER = "ask_user"  # Prompt user for decision
    SKIP = "skip"  # Skip conflicting item
    BACKUP_AND_REPLACE = "backup_and_replace"  # Backup then replace

    # Advanced resolutions
    CREATE_VARIANT = "create_variant"  # Create variant with suffix
    SPLIT_CONFIG = "split_config"  # Split into separate configs


class Conflict:
    """Represents a conflict with resolution options."""

    def __init__(
        self,
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        description: str,
        local_value: Any = None,
        remote_value: Any = None,
        context: Optional[Dict[str, Any]] = None,
        suggested_resolution: Optional[ConflictResolution] = None,
    ):
        self.id = str(uuid4())
        self.conflict_type = conflict_type
        self.severity = severity
        self.description = description
        self.local_value = local_value
        self.remote_value = remote_value
        self.context = context or {}
        self.suggested_resolution = suggested_resolution

        # Resolution state
        self.resolved = False
        self.resolution_used: Optional[ConflictResolution] = None
        self.resolution_result: Optional[Any] = None
        self.resolved_at: Optional[datetime] = None
        self.resolved_by: Optional[str] = None

        # Metadata
        self.created_at = datetime.now(timezone.utc)
        self.source = self.context.get("source", "unknown")
        self.target = self.context.get("target", "unknown")

    def mark_resolved(
        self,
        resolution: ConflictResolution,
        result: Any = None,
        resolved_by: str = "system",
    ) -> None:
        """Mark conflict as resolved."""
        self.resolved = True
        self.resolution_used = resolution
        self.resolution_result = result
        self.resolved_at = datetime.now(timezone.utc)
        self.resolved_by = resolved_by

    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary."""
        return {
            "id": self.id,
            "type": self.conflict_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "local_value": self.local_value,
            "remote_value": self.remote_value,
            "context": self.context,
            "suggested_resolution": self.suggested_resolution.value if self.suggested_resolution else None,
            "resolved": self.resolved,
            "resolution_used": self.resolution_used.value if self.resolution_used else None,
            "resolution_result": self.resolution_result,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


class ConflictDetector(ABC):
    """Abstract base class for conflict detectors."""

    @abstractmethod
    def detect_conflicts(
        self,
        local_data: Any,
        remote_data: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Conflict]:
        """Detect conflicts between local and remote data."""
        pass


class AgentConflictDetector(ConflictDetector):
    """Detects conflicts between agent specifications."""

    def detect_conflicts(
        self,
        local_data: Union[AgentSpecification, Dict[str, Any]],
        remote_data: Union[AgentSpecification, Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Conflict]:
        """Detect conflicts between agent specifications."""
        conflicts = []
        context = context or {}

        # Convert to dicts if needed
        local_dict = local_data.dict() if hasattr(local_data, "dict") else local_data
        remote_dict = remote_data.dict() if hasattr(remote_data, "dict") else remote_data

        # Check name conflicts
        if local_dict.get("metadata", {}).get("name") != remote_dict.get("metadata", {}).get("name"):
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.AGENT_NAME_CONFLICT,
                    severity=ConflictSeverity.HIGH,
                    description="Agent names differ between local and remote versions",
                    local_value=local_dict.get("metadata", {}).get("name"),
                    remote_value=remote_dict.get("metadata", {}).get("name"),
                    context=context,
                    suggested_resolution=ConflictResolution.ASK_USER,
                )
            )

        # Check content conflicts
        local_content = local_dict.get("content", "")
        remote_content = remote_dict.get("content", "")
        if local_content != remote_content:
            # Constants for content comparison
            content_diff_threshold = 0.1
            content_preview_length = 200

            # Simple heuristic: if content length differs by more than 10%, suggest user review
            length_diff = abs(len(local_content) - len(remote_content)) / max(
                len(local_content), len(remote_content), 1
            )
            severity = ConflictSeverity.HIGH if length_diff > content_diff_threshold else ConflictSeverity.MEDIUM

            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.AGENT_CONTENT_CONFLICT,
                    severity=severity,
                    description="Agent content differs between local and remote versions",
                    local_value=(
                        local_content[:content_preview_length] + "..."
                        if len(local_content) > content_preview_length
                        else local_content
                    ),
                    remote_value=(
                        remote_content[:content_preview_length] + "..."
                        if len(remote_content) > content_preview_length
                        else remote_content
                    ),
                    context={**context, "full_local_content": local_content, "full_remote_content": remote_content},
                    suggested_resolution=(
                        ConflictResolution.USE_LATEST
                        if severity == ConflictSeverity.MEDIUM
                        else ConflictResolution.ASK_USER
                    ),
                )
            )

        # Check version conflicts
        local_version = local_dict.get("metadata", {}).get("version", "1.0.0")
        remote_version = remote_dict.get("metadata", {}).get("version", "1.0.0")
        if local_version != remote_version:
            conflicts.append(
                Conflict(
                    conflict_type=ConflictType.AGENT_VERSION_CONFLICT,
                    severity=ConflictSeverity.MEDIUM,
                    description="Agent versions differ between local and remote",
                    local_value=local_version,
                    remote_value=remote_version,
                    context=context,
                    suggested_resolution=ConflictResolution.USE_LATEST,
                )
            )

        # Check metadata conflicts (tags, category, etc.)
        local_meta = local_dict.get("metadata", {})
        remote_meta = remote_dict.get("metadata", {})

        for key in ["category", "tags", "description", "author"]:
            if local_meta.get(key) != remote_meta.get(key):
                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.AGENT_METADATA_CONFLICT,
                        severity=ConflictSeverity.LOW,
                        description=f"Agent {key} differs between local and remote",
                        local_value=local_meta.get(key),
                        remote_value=remote_meta.get(key),
                        context={**context, "field": key},
                        suggested_resolution=ConflictResolution.USE_LATEST,
                    )
                )

        return conflicts


class ConfigConflictDetector(ConflictDetector):
    """Detects conflicts between configuration files."""

    def detect_conflicts(
        self,
        local_data: Dict[str, Any],
        remote_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Conflict]:
        """Detect conflicts between configuration data."""
        conflicts = []
        context = context or {}

        # Find all keys that exist in both configs
        common_keys = set(local_data.keys()) & set(remote_data.keys())

        for key in common_keys:
            local_val = local_data[key]
            remote_val = remote_data[key]

            if local_val != remote_val:
                # Determine severity based on key importance
                critical_keys = ["api_key", "secret", "token", "password"]
                important_keys = ["model", "temperature", "max_tokens", "system_prompt"]

                if key.lower() in critical_keys:
                    severity = ConflictSeverity.CRITICAL
                    resolution = ConflictResolution.ASK_USER
                elif key.lower() in important_keys:
                    severity = ConflictSeverity.HIGH
                    resolution = ConflictResolution.ASK_USER
                else:
                    severity = ConflictSeverity.MEDIUM
                    resolution = ConflictResolution.USE_LATEST

                conflicts.append(
                    Conflict(
                        conflict_type=ConflictType.CONFIG_VALUE_CONFLICT,
                        severity=severity,
                        description=f"Configuration value '{key}' differs between local and remote",
                        local_value=local_val,
                        remote_value=remote_val,
                        context={**context, "config_key": key},
                        suggested_resolution=resolution,
                    )
                )

        return conflicts


class ConflictResolver:
    """Main conflict resolution system."""

    def __init__(self):
        self.detectors: Dict[str, ConflictDetector] = {
            "agent": AgentConflictDetector(),
            "config": ConfigConflictDetector(),
        }
        self.conflicts: List[Conflict] = []
        self.resolution_history: List[Dict[str, Any]] = []

    def register_detector(self, name: str, detector: ConflictDetector) -> None:
        """Register a conflict detector."""
        self.detectors[name] = detector

    def detect_conflicts(
        self,
        detector_name: str,
        local_data: Any,
        remote_data: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Conflict]:
        """Detect conflicts using a specific detector."""
        if detector_name not in self.detectors:
            msg = f"Unknown detector: {detector_name}"
            raise ValueError(msg)

        detector = self.detectors[detector_name]
        conflicts = detector.detect_conflicts(local_data, remote_data, context)

        # Add to global conflict list
        self.conflicts.extend(conflicts)

        return conflicts

    def get_conflicts(
        self,
        severity: Optional[ConflictSeverity] = None,
        conflict_type: Optional[ConflictType] = None,
        *,
        unresolved_only: bool = True,
    ) -> List[Conflict]:
        """Get conflicts matching criteria."""
        filtered_conflicts = self.conflicts

        if unresolved_only:
            filtered_conflicts = [c for c in filtered_conflicts if not c.resolved]

        if severity:
            filtered_conflicts = [c for c in filtered_conflicts if c.severity == severity]

        if conflict_type:
            filtered_conflicts = [c for c in filtered_conflicts if c.conflict_type == conflict_type]

        return filtered_conflicts

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: ConflictResolution,
        resolved_by: str = "user",
        custom_result: Optional[Any] = None,
    ) -> bool:
        """Resolve a specific conflict."""
        conflict = self._find_conflict(conflict_id)
        if not conflict:
            return False

        # Apply resolution strategy
        result = custom_result
        if result is None:
            result = self._apply_resolution_strategy(conflict, resolution)

        # Mark as resolved
        conflict.mark_resolved(resolution, result, resolved_by)

        # Add to history
        self.resolution_history.append(
            {
                "conflict_id": conflict_id,
                "resolution": resolution.value,
                "resolved_by": resolved_by,
                "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                "result": result,
            }
        )

        return True

    def auto_resolve_conflicts(self, max_severity: ConflictSeverity = ConflictSeverity.MEDIUM) -> int:
        """Automatically resolve conflicts up to a maximum severity."""
        # Map severity to ordinal values for comparison
        severity_order = {
            ConflictSeverity.LOW: 1,
            ConflictSeverity.MEDIUM: 2,
            ConflictSeverity.HIGH: 3,
            ConflictSeverity.CRITICAL: 4,
        }

        resolved_count = 0

        for conflict in self.get_conflicts(unresolved_only=True):
            if severity_order[conflict.severity] <= severity_order[max_severity] and conflict.suggested_resolution:
                if self.resolve_conflict(
                    conflict.id,
                    conflict.suggested_resolution,
                    resolved_by="auto_resolver",
                ):
                    resolved_count += 1

        return resolved_count

    def _find_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """Find conflict by ID."""
        for conflict in self.conflicts:
            if conflict.id == conflict_id:
                return conflict
        return None

    def _apply_resolution_strategy(self, conflict: Conflict, resolution: ConflictResolution) -> Any:
        """Apply a resolution strategy to get the result."""
        if resolution == ConflictResolution.USE_LOCAL:
            return conflict.local_value
        elif resolution == ConflictResolution.USE_REMOTE:
            return conflict.remote_value
        elif resolution == ConflictResolution.USE_LATEST:
            # Simple heuristic: use remote as it's typically the "newer" version
            return conflict.remote_value
        elif resolution == ConflictResolution.MERGE_CONTENT:
            # Simple merge for text content
            if isinstance(conflict.local_value, str) and isinstance(conflict.remote_value, str):
                return f"{conflict.local_value}\n\n# Merged from remote:\n{conflict.remote_value}"
            return conflict.remote_value
        elif resolution == ConflictResolution.CREATE_VARIANT:
            # Create a variant name/path
            if "name" in str(conflict.local_value):
                return f"{conflict.local_value}_variant"
            return conflict.local_value
        else:
            # Default to remote value
            return conflict.remote_value

    def get_resolution_stats(self) -> Dict[str, Any]:
        """Get conflict resolution statistics."""
        total_conflicts = len(self.conflicts)
        resolved_conflicts = len([c for c in self.conflicts if c.resolved])

        # Count by severity
        severity_counts = {}
        for severity in ConflictSeverity:
            severity_counts[severity.value] = len([c for c in self.conflicts if c.severity == severity])

        # Count by type
        type_counts = {}
        for conflict_type in ConflictType:
            type_counts[conflict_type.value] = len([c for c in self.conflicts if c.conflict_type == conflict_type])

        return {
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "unresolved_conflicts": total_conflicts - resolved_conflicts,
            "resolution_rate": resolved_conflicts / max(total_conflicts, 1),
            "severity_breakdown": severity_counts,
            "type_breakdown": type_counts,
            "resolution_history_count": len(self.resolution_history),
        }

    def clear_resolved_conflicts(self) -> int:
        """Clear resolved conflicts from memory."""
        initial_count = len(self.conflicts)
        self.conflicts = [c for c in self.conflicts if not c.resolved]
        return initial_count - len(self.conflicts)

    def export_conflicts(self, *, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Export conflicts to a list of dictionaries."""
        conflicts_to_export = self.conflicts
        if not include_resolved:
            conflicts_to_export = [c for c in conflicts_to_export if not c.resolved]

        return [conflict.to_dict() for conflict in conflicts_to_export]


# Global conflict resolver instance
_conflict_resolver: Optional[ConflictResolver] = None


def get_conflict_resolver() -> ConflictResolver:
    """Get the global conflict resolver instance."""
    global _conflict_resolver  # noqa: PLW0603
    if _conflict_resolver is None:
        _conflict_resolver = ConflictResolver()
    return _conflict_resolver
