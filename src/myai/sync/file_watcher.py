"""
Advanced file watcher for auto-sync functionality.

This module provides sophisticated file watching capabilities specifically designed
for monitoring MyAI configurations, agents, and tool integrations with intelligent
debouncing and event filtering.
"""

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from myai.models.path import PathManager


class WatchTarget(Enum):
    """Types of files/directories to watch."""

    CONFIG = "config"
    AGENTS = "agents"
    TOOLS = "tools"
    TEMPLATES = "templates"
    INTEGRATIONS = "integrations"


class FileWatcherEventType(Enum):
    """File watcher event types."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


class FileWatcherEvent:
    """File watcher event with metadata."""

    def __init__(
        self,
        event_type: FileWatcherEventType,
        path: Path,
        target_type: WatchTarget,
        timestamp: Optional[datetime] = None,
        old_path: Optional[Path] = None,
    ):
        self.event_type = event_type
        self.path = path
        self.target_type = target_type
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.old_path = old_path  # For move events

    def __str__(self) -> str:
        """String representation of the event."""
        if self.event_type == FileWatcherEventType.MOVED and self.old_path:
            return f"{self.event_type.value}: {self.old_path} -> {self.path} [{self.target_type.value}]"
        return f"{self.event_type.value}: {self.path} [{self.target_type.value}]"


class DebouncedEventHandler(FileSystemEventHandler):
    """File system event handler with debouncing."""

    def __init__(
        self,
        callback: Callable[[FileWatcherEvent], None],
        debounce_seconds: float = 1.0,
        watch_patterns: Optional[Dict[WatchTarget, List[str]]] = None,
    ):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.watch_patterns = watch_patterns or {}
        self._pending_events: Dict[str, FileWatcherEvent] = {}
        self._debounce_timers: Dict[str, float] = {}

    def _should_watch_path(self, path: Path) -> Optional[WatchTarget]:
        """Check if path should be watched and return target type."""
        path_str = str(path)

        # Check each watch target
        for target_type, patterns in self.watch_patterns.items():
            for pattern in patterns:
                if path.match(pattern) or pattern in path_str:
                    return target_type

        # Default detection based on path components
        path_parts = path.parts
        if ".myai" in path_parts:
            idx = path_parts.index(".myai")
            if idx + 1 < len(path_parts):
                dir_name = path_parts[idx + 1]
                if dir_name == "agents":
                    return WatchTarget.AGENTS
                elif dir_name == "config":
                    return WatchTarget.CONFIG
                elif dir_name == "templates":
                    return WatchTarget.TEMPLATES

        return None

    def _create_event(
        self,
        event_type: FileWatcherEventType,
        path: Path,
        old_path: Optional[Path] = None,
    ) -> Optional[FileWatcherEvent]:
        """Create a file watcher event if path should be watched."""
        target_type = self._should_watch_path(path)
        if not target_type:
            return None

        return FileWatcherEvent(
            event_type=event_type,
            path=path,
            target_type=target_type,
            old_path=old_path,
        )

    def _schedule_event(self, event: FileWatcherEvent) -> None:
        """Schedule an event with debouncing."""
        event_key = f"{event.target_type.value}:{event.path}"
        current_time = time.time()

        # Store the event
        self._pending_events[event_key] = event
        self._debounce_timers[event_key] = current_time + self.debounce_seconds

        # Schedule the callback
        task = asyncio.create_task(self._process_debounced_event(event_key))
        task.add_done_callback(lambda _: None)  # Prevent garbage collection

    async def _process_debounced_event(self, event_key: str) -> None:
        """Process a debounced event after the delay."""
        if event_key not in self._debounce_timers:
            return

        # Wait for debounce period
        delay = self._debounce_timers[event_key] - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

        # Check if event is still pending and hasn't been superseded
        if (
            event_key in self._pending_events
            and event_key in self._debounce_timers
            and time.time() >= self._debounce_timers[event_key]
        ):
            event = self._pending_events.pop(event_key)
            self._debounce_timers.pop(event_key)

            # Execute callback
            try:
                self.callback(event)
            except Exception as e:
                # Log error but don't crash the watcher
                print(f"Error processing file watcher event: {e}")

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file/directory creation."""
        if event.is_directory:
            return

        watcher_event = self._create_event(FileWatcherEventType.CREATED, Path(str(event.src_path)))
        if watcher_event:
            self._schedule_event(watcher_event)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file/directory modification."""
        if event.is_directory:
            return

        watcher_event = self._create_event(FileWatcherEventType.MODIFIED, Path(str(event.src_path)))
        if watcher_event:
            self._schedule_event(watcher_event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file/directory deletion."""
        if event.is_directory:
            return

        watcher_event = self._create_event(FileWatcherEventType.DELETED, Path(str(event.src_path)))
        if watcher_event:
            self._schedule_event(watcher_event)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file/directory move."""
        if event.is_directory or not hasattr(event, "dest_path"):
            return

        watcher_event = self._create_event(
            FileWatcherEventType.MOVED, Path(str(event.dest_path)), Path(str(event.src_path))
        )
        if watcher_event:
            self._schedule_event(watcher_event)


class FileWatcher:
    """Advanced file watcher for MyAI auto-sync."""

    def __init__(
        self,
        debounce_seconds: float = 1.0,
        watch_patterns: Optional[Dict[WatchTarget, List[str]]] = None,
    ):
        self.debounce_seconds = debounce_seconds
        self.watch_patterns = watch_patterns or self._get_default_patterns()
        self.observers: List[Any] = []  # Observer objects from watchdog
        self.event_handlers: List[DebouncedEventHandler] = []
        self._callbacks: List[Callable[[FileWatcherEvent], None]] = []
        self._is_watching = False

    def _get_default_patterns(self) -> Dict[WatchTarget, List[str]]:
        """Get default file patterns to watch."""
        return {
            WatchTarget.CONFIG: [
                "*.toml",
                "*.json",
                "*.yaml",
                "*.yml",
                "config.toml",
                "settings.json",
            ],
            WatchTarget.AGENTS: [
                "*.md",
                "*.yaml",
                "*.yml",
                "*agent*.md",
                "agents/*.md",
            ],
            WatchTarget.TOOLS: [
                ".cursorrules",
                "settings.json",
                "claude_*",
                "cursor_*",
            ],
            WatchTarget.TEMPLATES: [
                "*.md",
                "*.yaml",
                "*.yml",
                "template_*",
                "templates/*.md",
            ],
            WatchTarget.INTEGRATIONS: [
                "*integration*",
                "*adapter*",
                "*.json",
            ],
        }

    def add_callback(self, callback: Callable[[FileWatcherEvent], None]) -> None:
        """Add a callback for file events."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[FileWatcherEvent], None]) -> None:
        """Remove a callback for file events."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _handle_event(self, event: FileWatcherEvent) -> None:
        """Handle a file watcher event by calling all callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in file watcher callback: {e}")

    def start_watching(self, paths: List[Path]) -> None:
        """Start watching the specified paths."""
        if self._is_watching:
            return

        self._is_watching = True

        for path in paths:
            if not path.exists():
                continue

            observer = Observer()
            handler = DebouncedEventHandler(
                callback=self._handle_event,
                debounce_seconds=self.debounce_seconds,
                watch_patterns=self.watch_patterns,
            )

            observer.schedule(handler, str(path), recursive=True)
            observer.start()

            self.observers.append(observer)
            self.event_handlers.append(handler)

    def stop_watching(self) -> None:
        """Stop watching files."""
        if not self._is_watching:
            return

        for observer in self.observers:
            observer.stop()  # type: ignore[attr-defined]
            observer.join()  # type: ignore[attr-defined]

        self.observers.clear()
        self.event_handlers.clear()
        self._is_watching = False

    def is_watching(self) -> bool:
        """Check if currently watching files."""
        return self._is_watching

    def get_default_watch_paths(self) -> List[Path]:
        """Get default paths to watch based on MyAI structure."""
        path_manager = PathManager()
        paths = []

        # Add MyAI directories
        myai_root = path_manager.get_user_path()
        if myai_root.exists():
            paths.extend(
                [
                    myai_root / "config",
                    myai_root / "agents",
                    myai_root / "templates",
                    myai_root / "data",
                ]
            )

        # Add tool-specific paths
        try:
            # Claude Code paths
            from myai.integrations.claude import ClaudeAdapter

            claude_adapter = ClaudeAdapter()
            if (
                hasattr(claude_adapter, "_claude_path")
                and claude_adapter._claude_path
                and claude_adapter._claude_path.exists()  # type: ignore[attr-defined]
            ):
                paths.append(claude_adapter._claude_path)  # type: ignore[attr-defined]
        except Exception:  # noqa: S110
            # Ignore Claude adapter import/config errors
            pass

        try:
            # Cursor paths
            from myai.integrations.cursor import CursorAdapter

            cursor_adapter = CursorAdapter()
            if (
                hasattr(cursor_adapter, "_cursor_config_path")
                and cursor_adapter._cursor_config_path
                and cursor_adapter._cursor_config_path.exists()  # type: ignore[attr-defined]
            ):
                paths.append(cursor_adapter._cursor_config_path.parent)  # type: ignore[attr-defined]
        except Exception:  # noqa: S110
            # Ignore Cursor adapter import/config errors
            pass

        return [p for p in paths if p.exists()]

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_watching()


# Global file watcher instance
_file_watcher: Optional[FileWatcher] = None


def get_file_watcher() -> FileWatcher:
    """Get the global file watcher instance."""
    global _file_watcher  # noqa: PLW0603
    if _file_watcher is None:
        _file_watcher = FileWatcher()
    return _file_watcher
