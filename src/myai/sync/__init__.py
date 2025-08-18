"""
Auto-sync and conflict resolution system for MyAI.

This module provides automatic synchronization capabilities between MyAI
and external tools, including file watching, conflict detection and resolution,
and background sync operations.
"""

from myai.sync.auto_sync import AutoSyncManager, get_auto_sync_manager
from myai.sync.conflict_resolver import ConflictResolution, ConflictResolver, ConflictType
from myai.sync.file_watcher import FileWatcher, FileWatcherEvent, WatchTarget
from myai.sync.sync_scheduler import SyncJob, SyncJobStatus, SyncScheduler

__all__ = [
    "AutoSyncManager",
    "get_auto_sync_manager",
    "ConflictResolver",
    "ConflictResolution",
    "ConflictType",
    "FileWatcher",
    "FileWatcherEvent",
    "WatchTarget",
    "SyncScheduler",
    "SyncJob",
    "SyncJobStatus",
]
