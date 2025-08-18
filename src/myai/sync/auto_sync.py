"""
Auto-sync manager for MyAI.

This module provides the main auto-sync functionality that coordinates
file watching, sync scheduling, and integration management for seamless
background synchronization.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from myai.integrations.manager import IntegrationManager
from myai.sync.file_watcher import FileWatcher, FileWatcherEvent, WatchTarget, get_file_watcher
from myai.sync.sync_scheduler import SyncJobType, SyncScheduler, get_sync_scheduler


class AutoSyncManager:
    """Main auto-sync manager coordinating file watching and sync operations."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        sync_debounce_seconds: float = 2.0,
        full_sync_interval: float = 300.0,  # 5 minutes
        health_check_interval: float = 60.0,  # 1 minute
    ):
        self.enabled = enabled
        self.sync_debounce_seconds = sync_debounce_seconds
        self.full_sync_interval = full_sync_interval
        self.health_check_interval = health_check_interval

        # Components
        self._file_watcher: Optional[FileWatcher] = None
        self._sync_scheduler: Optional[SyncScheduler] = None
        self._integration_manager: Optional[IntegrationManager] = None

        # State
        self._is_running = False
        self._last_sync_trigger: Dict[WatchTarget, datetime] = {}
        self._pending_sync_targets: Set[WatchTarget] = set()
        self._full_sync_task: Optional[asyncio.Task] = None

        # Statistics
        self._stats: Dict[str, Any] = {
            "auto_syncs_triggered": 0,
            "file_events_processed": 0,
            "sync_jobs_created": 0,
            "last_auto_sync": None,
            "started_at": None,
        }

    async def initialize(self) -> None:
        """Initialize the auto-sync manager."""
        # Initialize components
        self._file_watcher = get_file_watcher()
        self._sync_scheduler = get_sync_scheduler()
        self._integration_manager = IntegrationManager()

        await self._sync_scheduler.initialize()
        await self._integration_manager.initialize()

        # Set up file watcher callback
        self._file_watcher.add_callback(self._handle_file_event)

    async def start(self) -> None:
        """Start auto-sync operations."""
        if self._is_running or not self.enabled:
            return

        if not self._sync_scheduler:
            await self.initialize()

        self._is_running = True
        self._stats["started_at"] = datetime.now(timezone.utc)

        # Start sync scheduler
        if self._sync_scheduler:
            await self._sync_scheduler.start()

        # Start file watching
        if self._file_watcher:
            watch_paths = self._file_watcher.get_default_watch_paths()
            self._file_watcher.start_watching(watch_paths)

        # Start periodic full sync
        self._full_sync_task = asyncio.create_task(self._full_sync_loop())

        # Trigger initial sync
        await self._trigger_initial_sync()

    async def stop(self) -> None:
        """Stop auto-sync operations."""
        if not self._is_running:
            return

        self._is_running = False

        # Stop file watching
        if self._file_watcher:
            self._file_watcher.stop_watching()

        # Stop sync scheduler
        if self._sync_scheduler:
            await self._sync_scheduler.stop()

        # Cancel full sync task
        if self._full_sync_task:
            self._full_sync_task.cancel()
            try:
                await self._full_sync_task
            except asyncio.CancelledError:
                pass

    def is_running(self) -> bool:
        """Check if auto-sync is running."""
        return self._is_running

    def enable(self) -> None:
        """Enable auto-sync."""
        self.enabled = True

    def disable(self) -> None:
        """Disable auto-sync."""
        self.enabled = False

    async def trigger_manual_sync(
        self,
        target_adapter: Optional[str] = None,
        priority: int = 1,
    ) -> str:
        """Trigger a manual sync operation."""
        if not self._sync_scheduler:
            msg = "Auto-sync manager not initialized"
            raise ValueError(msg)

        job_id = self._sync_scheduler.add_job(
            SyncJobType.FULL_SYNC, target_adapter=target_adapter, priority=priority, metadata={"manual": True}
        )

        self._stats["sync_jobs_created"] += 1
        return job_id

    async def trigger_config_sync(self, priority: int = 2) -> str:
        """Trigger a configuration sync operation."""
        if not self._sync_scheduler:
            msg = "Auto-sync manager not initialized"
            raise ValueError(msg)

        job_id = self._sync_scheduler.add_job(
            SyncJobType.CONFIG_SYNC, priority=priority, metadata={"auto_triggered": True, "target": "config"}
        )

        self._stats["sync_jobs_created"] += 1
        return job_id

    async def trigger_agent_sync(self, priority: int = 3) -> str:
        """Trigger an agent sync operation."""
        if not self._sync_scheduler:
            msg = "Auto-sync manager not initialized"
            raise ValueError(msg)

        job_id = self._sync_scheduler.add_job(
            SyncJobType.AGENT_SYNC, priority=priority, metadata={"auto_triggered": True, "target": "agents"}
        )

        self._stats["sync_jobs_created"] += 1
        return job_id

    def _handle_file_event(self, event: FileWatcherEvent) -> None:
        """Handle file watcher events."""
        if not self.enabled or not self._is_running:
            return

        self._stats["file_events_processed"] += 1

        # Add to pending sync targets
        self._pending_sync_targets.add(event.target_type)
        self._last_sync_trigger[event.target_type] = event.timestamp

        # Schedule debounced sync
        task = asyncio.create_task(self._debounced_sync(event.target_type))
        task.add_done_callback(lambda _: None)  # Prevent garbage collection

    async def _debounced_sync(self, target_type: WatchTarget) -> None:
        """Perform debounced sync for a target type."""
        # Wait for debounce period
        await asyncio.sleep(self.sync_debounce_seconds)

        # Check if we still need to sync this target
        if target_type not in self._pending_sync_targets:
            return

        # Remove from pending
        self._pending_sync_targets.discard(target_type)

        # Trigger appropriate sync
        try:
            if target_type == WatchTarget.CONFIG:
                await self.trigger_config_sync(priority=2)
            elif target_type in (WatchTarget.AGENTS, WatchTarget.TEMPLATES):
                await self.trigger_agent_sync(priority=3)
            else:
                # General sync for tools/integrations
                await self.trigger_manual_sync(priority=4)

            self._stats["auto_syncs_triggered"] += 1
            self._stats["last_auto_sync"] = datetime.now(timezone.utc)

        except Exception as e:
            print(f"Error triggering auto-sync for {target_type}: {e}")

    async def _full_sync_loop(self) -> None:
        """Periodic full sync loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self.full_sync_interval)

                if self.enabled:
                    await self.trigger_manual_sync(priority=5)  # Lower priority

            except Exception as e:
                print(f"Error in full sync loop: {e}")
                await asyncio.sleep(60.0)

    async def _trigger_initial_sync(self) -> None:
        """Trigger initial sync on startup."""
        try:
            # Trigger health check first
            if self._sync_scheduler:
                self._sync_scheduler.add_job(SyncJobType.HEALTH_CHECK, priority=1, metadata={"initial": True})

                # Then trigger initial full sync
                await self.trigger_manual_sync(priority=2)

        except Exception as e:
            print(f"Error triggering initial sync: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get auto-sync status."""
        scheduler_status = {}
        if self._sync_scheduler:
            scheduler_status = self._sync_scheduler.get_queue_status()

        return {
            "enabled": self.enabled,
            "is_running": self._is_running,
            "file_watcher_active": self._file_watcher.is_watching() if self._file_watcher else False,
            "pending_sync_targets": list(self._pending_sync_targets),
            "last_sync_triggers": {
                target.value: timestamp.isoformat() for target, timestamp in self._last_sync_trigger.items()
            },
            "scheduler": scheduler_status,
            "stats": self._stats.copy(),
        }

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sync events."""
        events = []

        if self._sync_scheduler:
            # Get recent completed jobs
            for job in self._sync_scheduler._completed_jobs[-limit:]:
                events.append(
                    {
                        "type": "job_completed",
                        "job_id": job.id,
                        "job_type": job.job_type.value,
                        "target_adapter": job.target_adapter,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "duration": job.duration,
                    }
                )

            # Get recent failed jobs
            for job in self._sync_scheduler._failed_jobs[-limit:]:
                events.append(
                    {
                        "type": "job_failed",
                        "job_id": job.id,
                        "job_type": job.job_type.value,
                        "target_adapter": job.target_adapter,
                        "failed_at": job.completed_at.isoformat() if job.completed_at else None,
                        "error": job.error_message,
                        "retry_count": job.retry_count,
                    }
                )

        # Sort by timestamp and limit
        events.sort(key=lambda x: x.get("completed_at") or x.get("failed_at") or "", reverse=True)
        return events[:limit]

    async def add_watch_path(self, path: Path) -> bool:
        """Add a path to be watched."""
        if not self._file_watcher:
            return False

        try:
            # Stop current watching
            was_watching = self._file_watcher.is_watching()
            if was_watching:
                self._file_watcher.stop_watching()

            # Get current paths and add new one
            current_paths = self._file_watcher.get_default_watch_paths()
            if path not in current_paths:
                current_paths.append(path)

            # Restart watching with updated paths
            if was_watching:
                self._file_watcher.start_watching(current_paths)

            return True

        except Exception as e:
            print(f"Error adding watch path {path}: {e}")
            return False

    async def remove_watch_path(self, path: Path) -> bool:
        """Remove a path from being watched."""
        if not self._file_watcher:
            return False

        try:
            # Stop current watching
            was_watching = self._file_watcher.is_watching()
            if was_watching:
                self._file_watcher.stop_watching()

            # Get current paths and remove the specified one
            current_paths = self._file_watcher.get_default_watch_paths()
            if path in current_paths:
                current_paths.remove(path)

            # Restart watching with updated paths
            if was_watching and current_paths:
                self._file_watcher.start_watching(current_paths)

            return True

        except Exception as e:
            print(f"Error removing watch path {path}: {e}")
            return False


# Global auto-sync manager instance
_auto_sync_manager: Optional[AutoSyncManager] = None


def get_auto_sync_manager() -> AutoSyncManager:
    """Get the global auto-sync manager instance."""
    global _auto_sync_manager  # noqa: PLW0603
    if _auto_sync_manager is None:
        _auto_sync_manager = AutoSyncManager()
    return _auto_sync_manager
