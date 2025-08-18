"""
Tests for conflict resolution functionality.
"""

from myai.sync.conflict_resolver import (
    AgentConflictDetector,
    ConfigConflictDetector,
    Conflict,
    ConflictResolution,
    ConflictResolver,
    ConflictSeverity,
    ConflictType,
)


class TestConflict:
    """Test cases for the Conflict class."""

    def test_conflict_creation(self):
        """Test conflict creation."""
        conflict = Conflict(
            conflict_type=ConflictType.AGENT_CONTENT_CONFLICT,
            severity=ConflictSeverity.HIGH,
            description="Content differs",
            local_value="local content",
            remote_value="remote content",
        )

        assert conflict.conflict_type == ConflictType.AGENT_CONTENT_CONFLICT
        assert conflict.severity == ConflictSeverity.HIGH
        assert not conflict.resolved
        assert conflict.id is not None

    def test_conflict_resolution(self):
        """Test conflict resolution."""
        conflict = Conflict(
            conflict_type=ConflictType.CONFIG_VALUE_CONFLICT,
            severity=ConflictSeverity.MEDIUM,
            description="Value differs",
            local_value="local",
            remote_value="remote",
        )

        conflict.mark_resolved(ConflictResolution.USE_REMOTE, "remote", "user")

        assert conflict.resolved
        assert conflict.resolution_used == ConflictResolution.USE_REMOTE
        assert conflict.resolution_result == "remote"
        assert conflict.resolved_by == "user"

    def test_conflict_dict_conversion(self):
        """Test conflict dictionary conversion."""
        conflict = Conflict(
            conflict_type=ConflictType.AGENT_NAME_CONFLICT,
            severity=ConflictSeverity.LOW,
            description="Test conflict",
        )

        conflict_dict = conflict.to_dict()

        assert conflict_dict["type"] == ConflictType.AGENT_NAME_CONFLICT.value
        assert conflict_dict["severity"] == ConflictSeverity.LOW.value
        assert conflict_dict["description"] == "Test conflict"
        assert conflict_dict["resolved"] is False


class TestAgentConflictDetector:
    """Test cases for the AgentConflictDetector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = AgentConflictDetector()

    def test_name_conflict_detection(self):
        """Test agent name conflict detection."""
        local_agent = {
            "metadata": {"name": "local-agent"},
            "content": "Test content",
        }

        remote_agent = {
            "metadata": {"name": "remote-agent"},
            "content": "Test content",
        }

        conflicts = self.detector.detect_conflicts(local_agent, remote_agent)

        name_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.AGENT_NAME_CONFLICT]
        assert len(name_conflicts) == 1
        assert name_conflicts[0].severity == ConflictSeverity.HIGH

    def test_content_conflict_detection(self):
        """Test agent content conflict detection."""
        local_agent = {
            "metadata": {"name": "test-agent"},
            "content": "Local content that is different",
        }

        remote_agent = {
            "metadata": {"name": "test-agent"},
            "content": "Remote content that is completely different and much longer to trigger high severity",
        }

        conflicts = self.detector.detect_conflicts(local_agent, remote_agent)

        content_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.AGENT_CONTENT_CONFLICT]
        assert len(content_conflicts) == 1

    def test_version_conflict_detection(self):
        """Test agent version conflict detection."""
        local_agent = {
            "metadata": {"name": "test-agent", "version": "1.0.0"},
            "content": "Test content",
        }

        remote_agent = {
            "metadata": {"name": "test-agent", "version": "2.0.0"},
            "content": "Test content",
        }

        conflicts = self.detector.detect_conflicts(local_agent, remote_agent)

        version_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.AGENT_VERSION_CONFLICT]
        assert len(version_conflicts) == 1
        assert version_conflicts[0].suggested_resolution == ConflictResolution.USE_LATEST

    def test_metadata_conflict_detection(self):
        """Test agent metadata conflict detection."""
        local_agent = {
            "metadata": {
                "name": "test-agent",
                "category": "engineering",
                "tags": ["python", "automation"],
            },
            "content": "Test content",
        }

        remote_agent = {
            "metadata": {
                "name": "test-agent",
                "category": "business",
                "tags": ["analysis", "reporting"],
            },
            "content": "Test content",
        }

        conflicts = self.detector.detect_conflicts(local_agent, remote_agent)

        metadata_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.AGENT_METADATA_CONFLICT]
        assert len(metadata_conflicts) >= 2  # category and tags


class TestConfigConflictDetector:
    """Test cases for the ConfigConflictDetector."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ConfigConflictDetector()

    def test_value_conflict_detection(self):
        """Test configuration value conflict detection."""
        local_config = {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        remote_config = {
            "model": "gpt-3.5-turbo",
            "temperature": 0.5,
            "max_tokens": 2000,
        }

        conflicts = self.detector.detect_conflicts(local_config, remote_config)

        assert len(conflicts) == 3  # All values differ

        # Check severity assignment
        model_conflicts = [c for c in conflicts if c.context.get("config_key") == "model"]
        assert len(model_conflicts) == 1
        assert model_conflicts[0].severity == ConflictSeverity.HIGH

    def test_critical_key_conflict(self):
        """Test conflict detection for critical keys."""
        local_config = {
            "api_key": "local_key",
            "model": "gpt-4",
        }

        remote_config = {
            "api_key": "remote_key",
            "model": "gpt-4",
        }

        conflicts = self.detector.detect_conflicts(local_config, remote_config)

        api_key_conflicts = [c for c in conflicts if c.context.get("config_key") == "api_key"]
        assert len(api_key_conflicts) == 1
        assert api_key_conflicts[0].severity == ConflictSeverity.CRITICAL
        assert api_key_conflicts[0].suggested_resolution == ConflictResolution.ASK_USER


class TestConflictResolver:
    """Test cases for the ConflictResolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = ConflictResolver()

    def test_conflict_detection(self):
        """Test conflict detection using registered detectors."""
        local_agent = {
            "metadata": {"name": "test-agent", "version": "1.0.0"},
            "content": "Test content",
        }

        remote_agent = {
            "metadata": {"name": "test-agent", "version": "2.0.0"},
            "content": "Different content",
        }

        conflicts = self.resolver.detect_conflicts("agent", local_agent, remote_agent)

        assert len(conflicts) >= 1
        assert all(isinstance(c, Conflict) for c in conflicts)

    def test_conflict_filtering(self):
        """Test conflict filtering by criteria."""
        # Create test conflicts
        conflict1 = Conflict(ConflictType.AGENT_NAME_CONFLICT, ConflictSeverity.HIGH, "High severity conflict")
        conflict2 = Conflict(ConflictType.CONFIG_VALUE_CONFLICT, ConflictSeverity.LOW, "Low severity conflict")

        self.resolver.conflicts = [conflict1, conflict2]

        # Filter by severity
        high_conflicts = self.resolver.get_conflicts(severity=ConflictSeverity.HIGH)
        assert len(high_conflicts) == 1
        assert high_conflicts[0] == conflict1

        # Filter by type
        agent_conflicts = self.resolver.get_conflicts(conflict_type=ConflictType.AGENT_NAME_CONFLICT)
        assert len(agent_conflicts) == 1
        assert agent_conflicts[0] == conflict1

    def test_conflict_resolution(self):
        """Test manual conflict resolution."""
        conflict = Conflict(
            ConflictType.AGENT_CONTENT_CONFLICT,
            ConflictSeverity.MEDIUM,
            "Content differs",
            local_value="local",
            remote_value="remote",
        )

        self.resolver.conflicts = [conflict]

        success = self.resolver.resolve_conflict(conflict.id, ConflictResolution.USE_REMOTE, resolved_by="test_user")

        assert success
        assert conflict.resolved
        assert conflict.resolution_result == "remote"

    def test_auto_resolution(self):
        """Test automatic conflict resolution."""
        # Create conflicts with different severities
        conflicts = [
            Conflict(
                ConflictType.AGENT_VERSION_CONFLICT,
                ConflictSeverity.LOW,
                "Low severity",
                suggested_resolution=ConflictResolution.USE_LATEST,
            ),
            Conflict(
                ConflictType.AGENT_CONTENT_CONFLICT,
                ConflictSeverity.HIGH,
                "High severity",
                suggested_resolution=ConflictResolution.ASK_USER,
            ),
        ]

        self.resolver.conflicts = conflicts

        # Auto-resolve up to medium severity
        resolved_count = self.resolver.auto_resolve_conflicts(ConflictSeverity.MEDIUM)

        assert resolved_count == 1  # Only the low severity conflict should be resolved
        assert conflicts[0].resolved
        assert not conflicts[1].resolved

    def test_resolution_statistics(self):
        """Test resolution statistics generation."""
        conflicts = [
            Conflict(ConflictType.AGENT_NAME_CONFLICT, ConflictSeverity.HIGH, "Test 1"),
            Conflict(ConflictType.CONFIG_VALUE_CONFLICT, ConflictSeverity.LOW, "Test 2"),
        ]

        conflicts[0].mark_resolved(ConflictResolution.USE_LOCAL, "result", "user")

        self.resolver.conflicts = conflicts

        stats = self.resolver.get_resolution_stats()

        assert stats["total_conflicts"] == 2
        assert stats["resolved_conflicts"] == 1
        assert stats["unresolved_conflicts"] == 1
        assert stats["resolution_rate"] == 0.5

    def test_conflict_export(self):
        """Test conflict export functionality."""
        conflict = Conflict(
            ConflictType.AGENT_METADATA_CONFLICT,
            ConflictSeverity.MEDIUM,
            "Test conflict",
        )

        self.resolver.conflicts = [conflict]

        exported = self.resolver.export_conflicts()

        assert len(exported) == 1
        assert exported[0]["type"] == ConflictType.AGENT_METADATA_CONFLICT.value
        assert exported[0]["severity"] == ConflictSeverity.MEDIUM.value
