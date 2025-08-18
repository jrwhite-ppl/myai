"""
Tests for auto-sync functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from myai.sync.auto_sync import AutoSyncManager
from myai.sync.file_watcher import FileWatcherEvent, FileWatcherEventType, WatchTarget


class TestAutoSyncManager:
    """Test cases for the AutoSyncManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = AutoSyncManager(enabled=True, sync_debounce_seconds=0.1)

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test auto-sync manager initialization."""
        await self.manager.initialize()

        assert self.manager._file_watcher is not None
        assert self.manager._sync_scheduler is not None
        assert self.manager._integration_manager is not None

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping auto-sync."""
        with patch.object(self.manager, "_trigger_initial_sync") as mock_initial_sync:
            await self.manager.start()

            assert self.manager.is_running()
            mock_initial_sync.assert_called_once()

            await self.manager.stop()
            assert not self.manager.is_running()

    @pytest.mark.asyncio
    async def test_manual_sync_trigger(self):
        """Test manual sync triggering."""
        await self.manager.initialize()

        job_id = await self.manager.trigger_manual_sync()
        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_file_event_handling(self):
        """Test file event handling."""
        with patch.object(self.manager, "_trigger_initial_sync"):
            await self.manager.start()

        # Create a file event
        event = FileWatcherEvent(
            event_type=FileWatcherEventType.MODIFIED,
            path=Path("/test/agent.md"),
            target_type=WatchTarget.AGENTS,
        )

        # Handle the event
        self.manager._handle_file_event(event)

        # Check that sync was triggered
        assert WatchTarget.AGENTS in self.manager._pending_sync_targets

        await self.manager.stop()

    @pytest.mark.asyncio
    async def test_debounced_sync(self):
        """Test debounced sync functionality."""
        await self.manager.initialize()

        # Add to pending sync targets
        self.manager._pending_sync_targets.add(WatchTarget.CONFIG)

        with patch.object(self.manager, "trigger_config_sync") as mock_sync:
            # Trigger debounced sync
            await self.manager._debounced_sync(WatchTarget.CONFIG)

            # Should have triggered config sync
            mock_sync.assert_called_once()

            # Should have removed from pending
            assert WatchTarget.CONFIG not in self.manager._pending_sync_targets

    def test_enable_disable(self):
        """Test enabling and disabling auto-sync."""
        assert self.manager.enabled

        self.manager.disable()
        assert not self.manager.enabled

        self.manager.enable()
        assert self.manager.enabled

    def test_status_reporting(self):
        """Test status reporting."""
        status = self.manager.get_status()

        assert "enabled" in status
        assert "is_running" in status
        assert "stats" in status
        assert isinstance(status["stats"], dict)

    @pytest.mark.asyncio
    async def test_watch_path_management(self):
        """Test adding and removing watch paths."""
        await self.manager.initialize()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)

            # Add watch path
            result = await self.manager.add_watch_path(test_path)
            assert result is True

            # Remove watch path
            result = await self.manager.remove_watch_path(test_path)
            assert result is True
