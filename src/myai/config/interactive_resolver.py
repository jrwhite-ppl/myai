"""
Interactive conflict resolution for MyAI configuration merging.

This module provides user-interactive conflict resolution with various
interfaces including CLI prompts, web interface, and batch resolution.
"""

import fnmatch
import json
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, TextIO, Union

from myai.config.merger import ConfigConflict


class InteractiveMode(str, Enum):
    """Interactive resolution modes."""

    CLI = "cli"  # Command-line prompts
    WEB = "web"  # Web-based interface
    BATCH = "batch"  # Batch processing from file
    AUTO = "auto"  # Automatic resolution with rules


class ResolutionChoice(str, Enum):
    """User resolution choices."""

    SOURCE1 = "source1"  # Use first source value
    SOURCE2 = "source2"  # Use second source value
    MERGE = "merge"  # Merge values if possible
    CUSTOM = "custom"  # User provides custom value
    SKIP = "skip"  # Skip this conflict
    ABORT = "abort"  # Abort entire merge
    APPLY_TO_ALL = "apply_to_all"  # Apply choice to remaining conflicts


class ConflictResolutionSession:
    """Session for tracking interactive conflict resolution."""

    def __init__(self, mode: InteractiveMode = InteractiveMode.CLI):
        self.mode = mode
        self.conflicts: List[ConfigConflict] = []
        self.resolutions: Dict[str, Any] = {}
        self.auto_rules: Dict[str, ResolutionChoice] = {}
        self.session_aborted = False

    def add_conflicts(self, conflicts: List[ConfigConflict]) -> None:
        """Add conflicts to the resolution session."""
        self.conflicts.extend(conflicts)

    def add_auto_rule(self, pattern: str, choice: ResolutionChoice) -> None:
        """Add automatic resolution rule for path patterns."""
        self.auto_rules[pattern] = choice

    def get_resolution(self, conflict_path: str) -> Optional[Any]:
        """Get resolution for a specific conflict path."""
        return self.resolutions.get(conflict_path)

    def set_resolution(self, conflict_path: str, value: Any) -> None:
        """Set resolution for a specific conflict path."""
        self.resolutions[conflict_path] = value

    def is_complete(self) -> bool:
        """Check if all conflicts have been resolved."""
        return len(self.resolutions) >= len(self.conflicts) or self.session_aborted


class InteractiveResolverBase(ABC):
    """Base class for interactive conflict resolvers."""

    @abstractmethod
    def resolve_conflict(self, conflict: ConfigConflict, session: ConflictResolutionSession) -> Any:
        """
        Resolve a single configuration conflict interactively.

        Args:
            conflict: The conflict to resolve
            session: The resolution session

        Returns:
            Resolved value for the configuration
        """

    @abstractmethod
    def resolve_conflicts(
        self, conflicts: List[ConfigConflict], session: Optional[ConflictResolutionSession] = None
    ) -> Dict[str, Any]:
        """
        Resolve multiple configuration conflicts.

        Args:
            conflicts: List of conflicts to resolve
            session: Optional existing session

        Returns:
            Dictionary of path -> resolved value
        """


class CLIInteractiveResolver(InteractiveResolverBase):
    """Command-line interactive conflict resolver."""

    def __init__(self, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout):
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.global_choice: Optional[ResolutionChoice] = None

    def resolve_conflict(self, conflict: ConfigConflict, session: ConflictResolutionSession) -> Any:
        """Resolve a single conflict using CLI prompts."""
        # Check if we have a global choice that applies
        if self.global_choice in (ResolutionChoice.SOURCE1, ResolutionChoice.SOURCE2):
            return self._apply_choice(conflict, self.global_choice)

        # Check session auto-rules
        for pattern, choice in session.auto_rules.items():
            if self._matches_pattern(conflict.path, pattern):
                return self._apply_choice(conflict, choice)

        # Interactive prompt
        return self._prompt_for_resolution(conflict, session)

    def resolve_conflicts(
        self, conflicts: List[ConfigConflict], session: Optional[ConflictResolutionSession] = None
    ) -> Dict[str, Any]:
        """Resolve multiple conflicts with CLI interface."""
        if session is None:
            session = ConflictResolutionSession(InteractiveMode.CLI)

        session.add_conflicts(conflicts)
        resolutions = {}

        self._print_header(len(conflicts))

        for i, conflict in enumerate(conflicts, 1):
            if session.session_aborted:
                break

            # Check if already resolved
            if conflict.path in session.resolutions:
                resolutions[conflict.path] = session.resolutions[conflict.path]
                continue

            self._print_conflict_info(conflict, i, len(conflicts))

            try:
                resolution = self.resolve_conflict(conflict, session)
                resolutions[conflict.path] = resolution
                session.set_resolution(conflict.path, resolution)
            except KeyboardInterrupt:
                self.output_stream.write("\n\nResolution aborted by user.\n")
                session.session_aborted = True
                break

        return resolutions

    def _prompt_for_resolution(self, conflict: ConfigConflict, session: ConflictResolutionSession) -> Any:
        """Prompt user for conflict resolution choice."""
        while True:
            self._print_resolution_options()
            choice_input = self._get_user_input("Your choice: ").strip().lower()

            try:
                choice = self._parse_choice(choice_input)

                if choice == ResolutionChoice.ABORT:
                    session.session_aborted = True
                    return conflict.higher_priority_value
                elif choice == ResolutionChoice.SKIP:
                    return conflict.higher_priority_value
                elif choice == ResolutionChoice.APPLY_TO_ALL:
                    # Ask which choice to apply to all
                    self.output_stream.write("Which choice should be applied to all remaining conflicts?\n")
                    self._print_basic_options()
                    global_choice_input = self._get_user_input("Global choice: ").strip().lower()
                    global_choice = self._parse_choice(global_choice_input, allow_global=False)

                    if global_choice in (ResolutionChoice.SOURCE1, ResolutionChoice.SOURCE2):
                        self.global_choice = global_choice
                        return self._apply_choice(conflict, global_choice)
                    else:
                        self.output_stream.write("Invalid global choice. Please try again.\n")
                        continue
                elif choice == ResolutionChoice.CUSTOM:
                    return self._get_custom_value(conflict)
                else:
                    return self._apply_choice(conflict, choice)

            except ValueError as e:
                self.output_stream.write(f"Invalid choice: {e}\n")

    def _apply_choice(self, conflict: ConfigConflict, choice: ResolutionChoice) -> Any:
        """Apply a resolution choice to get the final value."""
        if choice == ResolutionChoice.SOURCE1:
            return conflict.value1
        elif choice == ResolutionChoice.SOURCE2:
            return conflict.value2
        elif choice == ResolutionChoice.MERGE:
            return self._attempt_merge(conflict)
        else:
            return conflict.higher_priority_value

    def _attempt_merge(self, conflict: ConfigConflict) -> Any:
        """Attempt to merge two conflicting values."""
        val1, val2 = conflict.value1, conflict.value2

        # Try to merge lists
        if isinstance(val1, list) and isinstance(val2, list):
            merged: List[Any] = val1.copy()
            for item in val2:
                if item not in merged:
                    merged.append(item)
            return merged

        # Try to merge dictionaries
        if isinstance(val1, dict) and isinstance(val2, dict):
            merged_dict: Dict[str, Any] = val1.copy()
            merged_dict.update(val2)
            return merged_dict

        # Can't merge - fall back to higher priority
        self.output_stream.write("Values cannot be merged automatically. Using higher priority value.\n")
        return conflict.higher_priority_value

    def _get_custom_value(self, _conflict: ConfigConflict) -> Any:
        """Get custom value from user."""
        self.output_stream.write("\nEnter custom value:\n")
        self.output_stream.write("(You can enter JSON for complex values)\n")

        custom_input = self._get_user_input("Custom value: ")

        # Try to parse as JSON first
        try:
            return json.loads(custom_input)
        except json.JSONDecodeError:
            # Return as string if not valid JSON
            return custom_input

    def _print_header(self, conflict_count: int) -> None:
        """Print session header."""
        self.output_stream.write(f"\n{'='*60}\n")
        self.output_stream.write(f"Configuration Conflict Resolution ({conflict_count} conflicts)\n")
        self.output_stream.write(f"{'='*60}\n\n")

    def _print_conflict_info(self, conflict: ConfigConflict, current: int, total: int) -> None:
        """Print information about a specific conflict."""
        self.output_stream.write(f"\nConflict {current}/{total}: {conflict.path}\n")
        self.output_stream.write(f"{'-'*50}\n")
        self.output_stream.write(f"Type: {conflict.conflict_type}\n")
        self.output_stream.write(f"Message: {conflict.message}\n\n")

        # Show conflicting values
        self.output_stream.write(f"Option 1 - {conflict.source1} (priority {conflict.priority1}):\n")
        self.output_stream.write(f"  {self._format_value(conflict.value1)}\n\n")

        self.output_stream.write(f"Option 2 - {conflict.source2} (priority {conflict.priority2}):\n")
        self.output_stream.write(f"  {self._format_value(conflict.value2)}\n\n")

    def _print_resolution_options(self) -> None:
        """Print resolution options."""
        self.output_stream.write("Resolution options:\n")
        self.output_stream.write("  1 - Use option 1 (first source)\n")
        self.output_stream.write("  2 - Use option 2 (second source)\n")
        self.output_stream.write("  m - Merge values (if possible)\n")
        self.output_stream.write("  c - Enter custom value\n")
        self.output_stream.write("  s - Skip this conflict\n")
        self.output_stream.write("  a - Apply choice to all remaining conflicts\n")
        self.output_stream.write("  q - Quit/abort resolution\n")

    def _print_basic_options(self) -> None:
        """Print basic resolution options for global application."""
        self.output_stream.write("  1 - Use option 1 (first source)\n")
        self.output_stream.write("  2 - Use option 2 (second source)\n")

    def _get_user_input(self, prompt: str) -> str:
        """Get user input with prompt."""
        self.output_stream.write(prompt)
        self.output_stream.flush()
        return self.input_stream.readline().strip()

    def _parse_choice(self, choice_input: str, *, allow_global: bool = True) -> ResolutionChoice:
        """Parse user input into a resolution choice."""
        if choice_input in ("1", "source1"):
            return ResolutionChoice.SOURCE1
        elif choice_input in ("2", "source2"):
            return ResolutionChoice.SOURCE2
        elif choice_input in ("m", "merge"):
            return ResolutionChoice.MERGE
        elif choice_input in ("c", "custom"):
            return ResolutionChoice.CUSTOM
        elif choice_input in ("s", "skip"):
            return ResolutionChoice.SKIP
        elif choice_input in ("q", "quit", "abort"):
            return ResolutionChoice.ABORT
        elif choice_input in ("a", "all") and allow_global:
            return ResolutionChoice.APPLY_TO_ALL
        else:
            error_msg = f"Unknown choice: {choice_input}"
            raise ValueError(error_msg)

    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern."""
        # Simple fnmatch-style pattern matching
        return fnmatch.fnmatch(path, pattern)


class BatchInteractiveResolver(InteractiveResolverBase):
    """Batch conflict resolver using predefined rules."""

    def __init__(self, rules_file: Optional[str] = None, rules: Optional[Dict[str, Any]] = None):
        self.rules = rules or {}
        if rules_file:
            self._load_rules_from_file(rules_file)

    def resolve_conflict(self, conflict: ConfigConflict, _session: ConflictResolutionSession) -> Any:
        """Resolve conflict using batch rules."""
        # Check for exact path match
        if conflict.path in self.rules:
            rule = self.rules[conflict.path]
            return self._apply_rule(conflict, rule)

        # Check for pattern matches
        for pattern, rule in self.rules.items():
            if fnmatch.fnmatch(conflict.path, pattern):
                return self._apply_rule(conflict, rule)

        # Default to higher priority if no rule found
        return conflict.higher_priority_value

    def resolve_conflicts(
        self, conflicts: List[ConfigConflict], session: Optional[ConflictResolutionSession] = None
    ) -> Dict[str, Any]:
        """Resolve all conflicts using batch rules."""
        if session is None:
            session = ConflictResolutionSession(InteractiveMode.BATCH)

        resolutions = {}
        for conflict in conflicts:
            resolutions[conflict.path] = self.resolve_conflict(conflict, session)

        return resolutions

    def _load_rules_from_file(self, rules_file: str) -> None:
        """Load resolution rules from JSON file."""
        try:
            with open(rules_file, encoding="utf-8") as f:
                self.rules = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            error_msg = f"Warning: Could not load rules from {rules_file}: {e}"
            print(error_msg)

    def _apply_rule(self, conflict: ConfigConflict, rule: Union[str, Dict[str, Any]]) -> Any:
        """Apply a batch resolution rule."""
        if isinstance(rule, str):
            # Simple string rule
            if rule == "source1":
                return conflict.value1
            elif rule == "source2":
                return conflict.value2
            elif rule == "higher_priority":
                return conflict.higher_priority_value
            elif rule == "merge":
                return self._merge_values(conflict.value1, conflict.value2)
        elif isinstance(rule, dict):
            # Complex rule with conditions
            action = rule.get("action", "higher_priority")
            custom_value = rule.get("value")

            if action == "custom" and custom_value is not None:
                return custom_value
            elif action == "source1":
                return conflict.value1
            elif action == "source2":
                return conflict.value2
            elif action == "merge":
                return self._merge_values(conflict.value1, conflict.value2)

        # Default fallback
        return conflict.higher_priority_value

    def _merge_values(self, val1: Any, val2: Any) -> Any:
        """Merge two values if possible."""
        if isinstance(val1, list) and isinstance(val2, list):
            merged_list: List[Any] = val1.copy()
            for item in val2:
                if item not in merged_list:
                    merged_list.append(item)
            return merged_list
        elif isinstance(val1, dict) and isinstance(val2, dict):
            merged_dict: Dict[str, Any] = val1.copy()
            merged_dict.update(val2)
            return merged_dict
        else:
            return val1  # Can't merge, use first value


class InteractiveResolverFactory:
    """Factory for creating interactive resolvers."""

    @classmethod
    def create_resolver(
        cls,
        mode: InteractiveMode,
        **kwargs: Any,
    ) -> InteractiveResolverBase:
        """Create an interactive resolver for the specified mode."""
        if mode == InteractiveMode.CLI:
            return CLIInteractiveResolver(
                input_stream=kwargs.get("input_stream", sys.stdin),
                output_stream=kwargs.get("output_stream", sys.stdout),
            )
        elif mode == InteractiveMode.BATCH:
            return BatchInteractiveResolver(
                rules_file=kwargs.get("rules_file"),
                rules=kwargs.get("rules"),
            )
        elif mode == InteractiveMode.WEB:
            # Web interface would be implemented here
            msg = "Web interface not yet implemented"
            raise NotImplementedError(msg)
        elif mode == InteractiveMode.AUTO:
            # Auto resolver with default rules
            default_rules = {
                "*.debug": "source2",  # Always use newer debug settings
                "*.paths.*": "merge",  # Merge path configurations
                "security.*": "source1",  # Prefer higher priority for security
            }
            return BatchInteractiveResolver(rules=default_rules)
        else:
            msg = f"Unknown interactive mode: {mode}"
            raise ValueError(msg)


# Global resolver instance
_default_resolver: Optional[InteractiveResolverBase] = None


def get_interactive_resolver(mode: InteractiveMode = InteractiveMode.CLI, **kwargs: Any) -> InteractiveResolverBase:
    """Get an interactive resolver instance."""
    global _default_resolver  # noqa: PLW0603
    if _default_resolver is None or kwargs:
        _default_resolver = InteractiveResolverFactory.create_resolver(mode, **kwargs)
    return _default_resolver


def resolve_conflicts_interactively(
    conflicts: List[ConfigConflict], mode: InteractiveMode = InteractiveMode.CLI, **kwargs: Any
) -> Dict[str, Any]:
    """Convenience function to resolve conflicts interactively."""
    resolver = get_interactive_resolver(mode, **kwargs)
    return resolver.resolve_conflicts(conflicts)
