"""
Configuration file watcher for MyAI.

This module provides real-time monitoring of configuration files with
debouncing, event filtering, and automatic reload capabilities.
"""

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

if TYPE_CHECKING:
    from watchdog.events import FileSystemEvent
    from watchdog.observers import Observer

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler  # type: ignore[import]
    from watchdog.observers import Observer  # type: ignore[import]

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEvent = object  # type: ignore
    FileSystemEventHandler = object  # type: ignore
    Observer = object  # type: ignore


class ConfigurationWatcher:
    """
    Real-time configuration file watcher with intelligent event handling.

    Provides file system monitoring for configuration files with debouncing,
    event filtering, and automatic reload capabilities. Falls back to polling
    if watchdog is not available.
    """

    def __init__(
        self,
        debounce_delay: float = 1.0,
        poll_interval: float = 2.0,
        *,
        use_polling: bool = False,
    ):
        """
        Initialize configuration watcher.

        Args:
            debounce_delay: Delay in seconds before triggering change events
            poll_interval: Polling interval when using fallback polling
            use_polling: Force use of polling instead of watchdog
        """
        self.debounce_delay = debounce_delay
        self.poll_interval = poll_interval
        self.use_polling = use_polling or not WATCHDOG_AVAILABLE

        # Watching state
        self._watching = False
        self._observer: Optional[Any] = None  # Observer when watchdog available
        self._poll_thread: Optional[threading.Thread] = None

        # Watched paths and handlers
        self._watched_paths: Dict[str, Dict[str, Any]] = {}
        self._event_handlers: Set[Callable] = set()

        # Debouncing
        self._pending_events: Dict[str, Dict[str, Any]] = {}
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

        # File state tracking for polling
        self._file_states: Dict[str, Dict[str, Any]] = {}

    def add_path(
        self,
        path: Path,
        *,
        recursive: bool = False,
        file_patterns: Optional[List[str]] = None,
    ) -> None:
        """
        Add path to watch for configuration changes.

        Args:
            path: Path to watch (file or directory)
            recursive: Whether to watch subdirectories recursively
            file_patterns: File patterns to filter (e.g., ["*.json", "*.yaml"])
        """
        path_str = str(path.resolve())

        self._watched_paths[path_str] = {
            "path": path,
            "recursive": recursive,
            "patterns": file_patterns or ["*.json", "*.yaml", "*.yml", "*.toml"],
            "is_file": path.is_file(),
        }

        # Initialize file state if polling
        if self.use_polling:
            self._initialize_file_state(path, recursive=recursive)

        # Restart watching if already started
        if self._watching:
            self.stop()
            self.start()

    def remove_path(self, path: Path) -> None:
        """
        Remove path from watching.

        Args:
            path: Path to stop watching
        """
        path_str = str(path.resolve())

        if path_str in self._watched_paths:
            del self._watched_paths[path_str]

            # Clean up file states
            if path_str in self._file_states:
                del self._file_states[path_str]

            # Restart watching if needed
            if self._watching:
                self.stop()
                if self._watched_paths:
                    self.start()

    def add_handler(self, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Add event handler for configuration changes.

        Args:
            handler: Callback function with signature (event_type, event_data)
        """
        self._event_handlers.add(handler)

    def remove_handler(self, handler: Callable) -> None:
        """
        Remove event handler.

        Args:
            handler: Handler function to remove
        """
        self._event_handlers.discard(handler)

    def start(self) -> None:
        """Start watching for configuration changes."""
        if self._watching or not self._watched_paths:
            return

        self._watching = True

        if self.use_polling:
            self._start_polling()
        else:
            self._start_watchdog()

    def stop(self) -> None:
        """Stop watching for configuration changes."""
        if not self._watching:
            return

        self._watching = False

        # Cancel pending debounce timer
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        # Stop observer or polling thread
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        if self._poll_thread:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None

        # Clear pending events
        self._pending_events.clear()

    def is_watching(self) -> bool:
        """Check if watcher is currently active."""
        return self._watching

    def get_watched_paths(self) -> List[Dict[str, Any]]:
        """
        Get list of watched paths and their configurations.

        Returns:
            List of path configurations
        """
        return [
            {
                "path": str(config["path"]),
                "recursive": config["recursive"],
                "patterns": config["patterns"],
                "is_file": config["is_file"],
            }
            for config in self._watched_paths.values()
        ]

    def force_check(self) -> None:
        """Force immediate check for changes (useful for testing)."""
        if self.use_polling:
            self._check_for_changes()
        else:
            # Trigger a scan of all watched paths
            for _path_str, config in self._watched_paths.items():
                path = config["path"]
                if path.exists():
                    self._handle_file_event("modified", path)

        # Process pending events immediately for testing
        if self._pending_events:
            with self._lock:
                if self._debounce_timer:
                    self._debounce_timer.cancel()
                    self._debounce_timer = None
            self._process_pending_events()

    def _start_watchdog(self) -> None:
        """Start watchdog-based file monitoring."""
        if not WATCHDOG_AVAILABLE:
            msg = "Watchdog not available, use polling instead"
            raise RuntimeError(msg)

        self._observer = Observer()

        # Create event handler
        event_handler = ConfigFileEventHandler(self)

        # Add watchers for each path
        for _path_str, config in self._watched_paths.items():
            path = config["path"]
            recursive = config["recursive"]

            if path.exists():
                if path.is_file():
                    # Watch the parent directory for file changes
                    self._observer.schedule(event_handler, str(path.parent), recursive=False)
                else:
                    # Watch directory
                    self._observer.schedule(event_handler, str(path), recursive=recursive)

        self._observer.start()

    def _start_polling(self) -> None:
        """Start polling-based file monitoring."""
        self._poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._poll_thread.start()

    def _polling_loop(self) -> None:
        """Main polling loop for file monitoring."""
        while self._watching:
            try:
                self._check_for_changes()
                time.sleep(self.poll_interval)
            except Exception:
                # Continue polling even if there are errors
                time.sleep(self.poll_interval)

    def _check_for_changes(self) -> None:
        """Check for file changes in polling mode."""
        for _path_str, config in self._watched_paths.items():
            path = config["path"]
            recursive = config["recursive"]
            patterns = config["patterns"]

            if config["is_file"]:
                # Check single file
                self._check_file_change(path)
            else:
                # Check directory
                self._check_directory_changes(path, recursive=recursive, patterns=patterns)

    def _check_file_change(self, file_path: Path) -> None:
        """Check if a single file has changed."""
        if not file_path.exists():
            # File was deleted
            path_str = str(file_path)
            if path_str in self._file_states:
                del self._file_states[path_str]
                self._handle_file_event("deleted", file_path)
            return

        try:
            stat = file_path.stat()
            current_state = {
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }

            path_str = str(file_path)

            if path_str not in self._file_states:
                # New file
                self._file_states[path_str] = current_state
                self._handle_file_event("created", file_path)
            elif self._file_states[path_str] != current_state:
                # File modified
                self._file_states[path_str] = current_state
                self._handle_file_event("modified", file_path)
        except OSError:
            # File might be temporarily inaccessible
            pass

    def _check_directory_changes(
        self,
        dir_path: Path,
        *,
        recursive: bool,
        patterns: List[str],
    ) -> None:
        """Check for changes in directory."""
        if not dir_path.exists():
            return

        glob_pattern = "**/*" if recursive else "*"

        try:
            for file_path in dir_path.glob(glob_pattern):
                if file_path.is_file() and self._matches_patterns(file_path, patterns):
                    self._check_file_change(file_path)
        except OSError:
            # Directory might be temporarily inaccessible
            pass

    def _matches_patterns(self, file_path: Path, patterns: List[str]) -> bool:
        """Check if file matches any of the patterns."""
        import fnmatch

        file_name = file_path.name
        return any(fnmatch.fnmatch(file_name, pattern) for pattern in patterns)

    def _initialize_file_state(self, path: Path, *, recursive: bool) -> None:
        """Initialize file state tracking for polling."""
        if path.is_file():
            self._check_file_change(path)
        elif path.is_dir():
            patterns = self._watched_paths.get(str(path), {}).get("patterns", ["*"])
            self._check_directory_changes(path, recursive=recursive, patterns=patterns)

    def _handle_file_event(self, event_type: str, file_path: Path) -> None:
        """Handle file system event with debouncing."""
        path_str = str(file_path)

        with self._lock:
            # Add to pending events
            self._pending_events[path_str] = {"event_type": event_type, "timestamp": time.time()}

            # Cancel existing timer and start new one
            if self._debounce_timer:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self.debounce_delay,
                self._process_pending_events,
            )
            self._debounce_timer.daemon = True  # Make sure timer threads don't block shutdown
            self._debounce_timer.start()

    def _process_pending_events(self) -> None:
        """Process pending events after debounce period."""
        with self._lock:
            if not self._pending_events:
                return

            # Process all pending events
            for path_str, event_info in self._pending_events.items():
                file_path = Path(path_str)
                event_type = event_info["event_type"]
                timestamp = event_info["timestamp"]

                # Verify event type is still valid
                if event_type == "created" and not file_path.exists():
                    event_type = "deleted"
                elif event_type == "deleted" and file_path.exists():
                    event_type = "modified"

                # Notify handlers
                event_data = {
                    "path": path_str,
                    "timestamp": timestamp,
                    "exists": file_path.exists(),
                }

                self._notify_handlers(event_type, event_data)

            # Clear pending events
            self._pending_events.clear()
            self._debounce_timer = None

    def _notify_handlers(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Notify all registered handlers of an event."""
        for handler in self._event_handlers.copy():  # Copy to avoid modification during iteration
            try:
                handler(event_type, event_data)
            except Exception:
                # Remove broken handlers
                self._event_handlers.discard(handler)


class ConfigFileEventHandler(FileSystemEventHandler):
    """Watchdog event handler for configuration files."""

    def __init__(self, watcher: ConfigurationWatcher):
        """Initialize event handler."""
        super().__init__()
        self.watcher = watcher

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            file_path = Path(str(event.src_path))
            if self._should_handle_file(file_path):
                self.watcher._handle_file_event("modified", file_path)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            file_path = Path(str(event.src_path))
            if self._should_handle_file(file_path):
                self.watcher._handle_file_event("created", file_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if not event.is_directory:
            file_path = Path(str(event.src_path))
            if self._should_handle_file(file_path):
                self.watcher._handle_file_event("deleted", file_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if not event.is_directory:
            # Treat move as delete + create
            old_path = Path(str(event.src_path))
            new_path = Path(str(event.dest_path))

            if self._should_handle_file(old_path):
                self.watcher._handle_file_event("deleted", old_path)

            if self._should_handle_file(new_path):
                self.watcher._handle_file_event("created", new_path)

    def _should_handle_file(self, file_path: Path) -> bool:
        """Check if file should be handled based on watched paths and patterns."""
        for _path_str, config in self.watcher._watched_paths.items():
            watched_path = config["path"]
            patterns = config["patterns"]

            # Check if file is under watched path
            try:
                if config["is_file"]:
                    # Watching specific file
                    if file_path == watched_path:
                        return True
                elif config["recursive"]:
                    # Check if file is under directory (recursively)
                    try:
                        file_path.relative_to(watched_path)
                        return self.watcher._matches_patterns(file_path, patterns)
                    except ValueError:
                        continue
                elif file_path.parent == watched_path:
                    return self.watcher._matches_patterns(file_path, patterns)
            except (OSError, ValueError):
                continue

        return False
