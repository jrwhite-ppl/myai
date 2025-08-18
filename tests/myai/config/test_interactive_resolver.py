"""
Tests for interactive conflict resolution.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest

from myai.config.interactive_resolver import (
    BatchInteractiveResolver,
    CLIInteractiveResolver,
    ConflictResolutionSession,
    InteractiveMode,
    InteractiveResolverFactory,
    ResolutionChoice,
    resolve_conflicts_interactively,
)
from myai.config.merger import ConfigConflict, ConflictType


class TestConflictResolutionSession:
    """Test cases for ConflictResolutionSession."""

    def test_session_creation(self):
        """Test session creation."""
        session = ConflictResolutionSession(InteractiveMode.CLI)

        assert session.mode == InteractiveMode.CLI
        assert session.conflicts == []
        assert session.resolutions == {}
        assert session.auto_rules == {}
        assert session.session_aborted is False

    def test_conflict_management(self):
        """Test adding and managing conflicts."""
        session = ConflictResolutionSession()

        conflict = ConfigConflict(
            path="test.path",
            conflict_type=ConflictType.VALUE_CONFLICT,
            source1="source1",
            value1="value1",
            priority1=1,
            source2="source2",
            value2="value2",
            priority2=2,
        )

        session.add_conflicts([conflict])
        assert len(session.conflicts) == 1
        assert session.conflicts[0] == conflict

    def test_resolution_tracking(self):
        """Test resolution tracking."""
        session = ConflictResolutionSession()

        session.set_resolution("test.path", "resolved_value")
        assert session.get_resolution("test.path") == "resolved_value"
        assert session.get_resolution("nonexistent") is None

    def test_auto_rules(self):
        """Test automatic resolution rules."""
        session = ConflictResolutionSession()

        session.add_auto_rule("*.debug", ResolutionChoice.SOURCE2)
        assert session.auto_rules["*.debug"] == ResolutionChoice.SOURCE2

    def test_completion_status(self):
        """Test session completion checking."""
        session = ConflictResolutionSession()

        # Empty session is complete
        assert session.is_complete()

        # Add conflicts - now incomplete
        conflict = ConfigConflict("test", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2)
        session.add_conflicts([conflict])
        assert not session.is_complete()

        # Resolve conflict - now complete
        session.set_resolution("test", "resolved")
        assert session.is_complete()

        # Abort session - should be complete
        session.session_aborted = True
        assert session.is_complete()


class TestCLIInteractiveResolver:
    """Test cases for CLI interactive resolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.input_stream = StringIO()
        self.output_stream = StringIO()
        self.resolver = CLIInteractiveResolver(self.input_stream, self.output_stream)

    def test_simple_conflict_resolution(self):
        """Test resolving a simple conflict."""
        conflict = ConfigConflict(
            path="test.setting",
            conflict_type=ConflictType.VALUE_CONFLICT,
            source1="user",
            value1="user_value",
            priority1=1,
            source2="project",
            value2="project_value",
            priority2=2,
        )

        session = ConflictResolutionSession()

        # Simulate user choosing option 1
        self.input_stream.write("1\n")
        self.input_stream.seek(0)

        result = self.resolver.resolve_conflict(conflict, session)
        assert result == "user_value"

    def test_choice_parsing(self):
        """Test parsing user choices."""
        # Test various input formats
        assert self.resolver._parse_choice("1") == ResolutionChoice.SOURCE1
        assert self.resolver._parse_choice("2") == ResolutionChoice.SOURCE2
        assert self.resolver._parse_choice("m") == ResolutionChoice.MERGE
        assert self.resolver._parse_choice("merge") == ResolutionChoice.MERGE
        assert self.resolver._parse_choice("c") == ResolutionChoice.CUSTOM
        assert self.resolver._parse_choice("s") == ResolutionChoice.SKIP
        assert self.resolver._parse_choice("q") == ResolutionChoice.ABORT
        assert self.resolver._parse_choice("a") == ResolutionChoice.APPLY_TO_ALL

        # Test invalid choice
        with pytest.raises(ValueError):
            self.resolver._parse_choice("invalid")

    def test_value_merging(self):
        """Test automatic value merging."""
        # Test list merging
        conflict_lists = ConfigConflict(
            "test.list", ConflictType.VALUE_CONFLICT, "s1", ["a", "b"], 1, "s2", ["b", "c"], 2
        )
        merged = self.resolver._attempt_merge(conflict_lists)
        assert merged == ["a", "b", "c"]

        # Test dict merging
        conflict_dicts = ConfigConflict(
            "test.dict", ConflictType.VALUE_CONFLICT, "s1", {"a": 1, "b": 2}, 1, "s2", {"b": 3, "c": 4}, 2
        )
        merged = self.resolver._attempt_merge(conflict_dicts)
        assert merged == {"a": 1, "b": 3, "c": 4}

    def test_value_formatting(self):
        """Test value formatting for display."""
        # Test simple values
        assert self.resolver._format_value("string") == "string"
        assert self.resolver._format_value(123) == "123"

        # Test complex values
        complex_dict = {"key": "value", "nested": {"inner": "data"}}
        formatted = self.resolver._format_value(complex_dict)
        assert json.loads(formatted) == complex_dict

    def test_multiple_conflicts_resolution(self):
        """Test resolving multiple conflicts."""
        conflicts = [
            ConfigConflict("test1", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2),
            ConfigConflict("test2", ConflictType.VALUE_CONFLICT, "s1", "a1", 1, "s2", "a2", 2),
        ]

        # Simulate user inputs for both conflicts
        self.input_stream.write("1\n2\n")
        self.input_stream.seek(0)

        resolutions = self.resolver.resolve_conflicts(conflicts)

        assert resolutions["test1"] == "v1"
        assert resolutions["test2"] == "a2"

    def test_global_choice_application(self):
        """Test applying choice to all remaining conflicts."""
        conflicts = [
            ConfigConflict("test1", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2),
            ConfigConflict("test2", ConflictType.VALUE_CONFLICT, "s1", "a1", 1, "s2", "a2", 2),
            ConfigConflict("test3", ConflictType.VALUE_CONFLICT, "s1", "b1", 1, "s2", "b2", 2),
        ]

        # First conflict: choose "apply to all" with option 1
        self.input_stream.write("a\n1\n")
        self.input_stream.seek(0)

        resolutions = self.resolver.resolve_conflicts(conflicts)

        # All should use source1 (first option)
        assert resolutions["test1"] == "v1"
        assert resolutions["test2"] == "a1"
        assert resolutions["test3"] == "b1"

    def test_session_abort(self):
        """Test aborting resolution session."""
        conflicts = [
            ConfigConflict("test1", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2),
            ConfigConflict("test2", ConflictType.VALUE_CONFLICT, "s1", "a1", 1, "s2", "a2", 2),
        ]

        # First conflict: abort
        self.input_stream.write("q\n")
        self.input_stream.seek(0)

        resolutions = self.resolver.resolve_conflicts(conflicts)

        # Only first conflict should be resolved (with fallback)
        assert len(resolutions) == 1
        assert "test1" in resolutions


class TestBatchInteractiveResolver:
    """Test cases for batch interactive resolver."""

    def test_simple_rules(self):
        """Test simple resolution rules."""
        rules = {
            "test.setting": "source1",
            "another.setting": "source2",
            "*.debug": "merge",
        }

        resolver = BatchInteractiveResolver(rules=rules)

        # Test exact match
        conflict1 = ConfigConflict("test.setting", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2)
        result1 = resolver.resolve_conflict(conflict1, ConflictResolutionSession())
        assert result1 == "v1"  # source1

        # Test pattern match
        conflict2 = ConfigConflict("app.debug", ConflictType.VALUE_CONFLICT, "s1", ["a"], 1, "s2", ["b"], 2)
        result2 = resolver.resolve_conflict(conflict2, ConflictResolutionSession())
        assert result2 == ["a", "b"]  # merged

    def test_complex_rules(self):
        """Test complex resolution rules."""
        rules = {"custom.setting": {"action": "custom", "value": "custom_value"}, "merge.lists": {"action": "merge"}}

        resolver = BatchInteractiveResolver(rules=rules)

        # Test custom value rule
        conflict1 = ConfigConflict("custom.setting", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2)
        result1 = resolver.resolve_conflict(conflict1, ConflictResolutionSession())
        assert result1 == "custom_value"

    def test_rules_file_loading(self):
        """Test loading rules from file."""
        rules_data = {"*.test": "source1", "specific.path": "source2"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(rules_data, f)
            rules_file = f.name

        try:
            resolver = BatchInteractiveResolver(rules_file=rules_file)
            assert resolver.rules == rules_data
        finally:
            Path(rules_file).unlink()

    def test_no_matching_rules(self):
        """Test behavior when no rules match."""
        rules = {"other.setting": "source1"}

        resolver = BatchInteractiveResolver(rules=rules)

        conflict = ConfigConflict("unmatched.setting", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2)
        result = resolver.resolve_conflict(conflict, ConflictResolutionSession())

        # Should fall back to higher priority
        assert result == "v2"  # source2 has higher priority

    def test_multiple_conflicts_batch(self):
        """Test resolving multiple conflicts with batch rules."""
        rules = {"test1": "source1", "test2": "source2", "test*": "merge"}  # Should match test3

        resolver = BatchInteractiveResolver(rules=rules)

        conflicts = [
            ConfigConflict("test1", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2),
            ConfigConflict("test2", ConflictType.VALUE_CONFLICT, "s1", "a1", 1, "s2", "a2", 2),
            ConfigConflict("test3", ConflictType.VALUE_CONFLICT, "s1", ["x"], 1, "s2", ["y"], 2),
        ]

        resolutions = resolver.resolve_conflicts(conflicts)

        assert resolutions["test1"] == "v1"  # source1
        assert resolutions["test2"] == "a2"  # source2
        assert resolutions["test3"] == ["x", "y"]  # merged


class TestInteractiveResolverFactory:
    """Test cases for the resolver factory."""

    def test_create_cli_resolver(self):
        """Test creating CLI resolver."""
        resolver = InteractiveResolverFactory.create_resolver(InteractiveMode.CLI)
        assert isinstance(resolver, CLIInteractiveResolver)

    def test_create_batch_resolver(self):
        """Test creating batch resolver."""
        resolver = InteractiveResolverFactory.create_resolver(InteractiveMode.BATCH, rules={"test": "source1"})
        assert isinstance(resolver, BatchInteractiveResolver)

    def test_create_auto_resolver(self):
        """Test creating auto resolver."""
        resolver = InteractiveResolverFactory.create_resolver(InteractiveMode.AUTO)
        assert isinstance(resolver, BatchInteractiveResolver)
        # Should have default rules
        assert len(resolver.rules) > 0

    def test_create_unsupported_resolver(self):
        """Test creating unsupported resolver."""
        with pytest.raises(NotImplementedError):
            InteractiveResolverFactory.create_resolver(InteractiveMode.WEB)

    def test_create_invalid_mode(self):
        """Test creating resolver with invalid mode."""
        with pytest.raises(ValueError):
            InteractiveResolverFactory.create_resolver("invalid_mode")


class TestGlobalFunctions:
    """Test cases for global convenience functions."""

    def test_resolve_conflicts_interactively(self):
        """Test the global resolve function."""
        conflicts = [ConfigConflict("test", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2)]

        # Test with auto mode (batch resolver with default rules)
        resolutions = resolve_conflicts_interactively(conflicts, InteractiveMode.AUTO)

        assert len(resolutions) == 1
        assert "test" in resolutions

    def test_pattern_matching(self):
        """Test pattern matching in resolvers."""
        resolver = CLIInteractiveResolver()

        # Test basic pattern matching
        assert resolver._matches_pattern("app.debug", "*.debug")
        assert resolver._matches_pattern("user.settings.theme", "*.settings.*")
        assert not resolver._matches_pattern("other.path", "*.debug")

        # Test exact matching
        assert resolver._matches_pattern("exact.path", "exact.path")
        assert not resolver._matches_pattern("exact.path", "exact.other")


class TestIntegrationScenarios:
    """Test integration scenarios with multiple resolvers."""

    def test_cli_to_batch_transition(self):
        """Test transitioning from CLI to batch resolution."""
        conflicts = [
            ConfigConflict("debug.enabled", ConflictType.VALUE_CONFLICT, "user", True, 1, "project", False, 2),
            ConfigConflict("cache.size", ConflictType.VALUE_CONFLICT, "user", 100, 1, "project", 200, 2),
        ]

        # First, resolve with auto mode
        auto_resolutions = resolve_conflicts_interactively(conflicts, InteractiveMode.AUTO)

        # Auto mode should provide reasonable defaults
        assert len(auto_resolutions) == 2

        # Then resolve with batch mode using custom rules
        batch_rules = {
            "debug.*": "source2",  # Use project settings for debug
            "cache.*": "source1",  # Use user settings for cache
        }

        batch_resolutions = resolve_conflicts_interactively(conflicts, InteractiveMode.BATCH, rules=batch_rules)

        assert batch_resolutions["debug.enabled"] is False  # project value
        assert batch_resolutions["cache.size"] == 100  # user value

    def test_mixed_conflict_types(self):
        """Test resolving different types of conflicts."""
        conflicts = [
            ConfigConflict("setting1", ConflictType.VALUE_CONFLICT, "s1", "v1", 1, "s2", "v2", 2),
            ConfigConflict("setting2", ConflictType.TYPE_CONFLICT, "s1", "string", 1, "s2", 123, 2),
            ConfigConflict("setting3", ConflictType.ARRAY_CONFLICT, "s1", ["a"], 1, "s2", ["b"], 2),
        ]

        rules = {"*": "merge"}  # Try to merge everything

        resolutions = resolve_conflicts_interactively(conflicts, InteractiveMode.BATCH, rules=rules)

        assert len(resolutions) == 3
        # Array should be merged
        assert resolutions["setting3"] == ["a", "b"]
