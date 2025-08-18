"""
Sync scheduler for background synchronization operations.

This module provides a scheduler for managing background sync jobs,
queue management, error recovery, and status reporting.
"""

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from myai.integrations.manager import IntegrationManager


class SyncJobStatus(Enum):
    """Status of a sync job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class SyncJobType(Enum):
    """Type of sync job."""

    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    CONFIG_SYNC = "config_sync"
    AGENT_SYNC = "agent_sync"
    CONFLICT_RESOLUTION = "conflict_resolution"
    HEALTH_CHECK = "health_check"


class SyncJob:
    """A sync job with metadata and execution context."""

    def __init__(
        self,
        job_type: SyncJobType,
        target_adapter: Optional[str] = None,
        priority: int = 5,
        max_retries: int = 3,
        retry_delay: float = 30.0,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = str(uuid4())
        self.job_type = job_type
        self.target_adapter = target_adapter  # None means all adapters
        self.priority = priority  # Lower number = higher priority
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout or 300.0  # 5 minutes default
        self.metadata = metadata or {}

        # Execution state
        self.status = SyncJobStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.retry_count = 0
        self.error_message: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None

    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == SyncJobStatus.FAILED and self.retry_count < self.max_retries

    def mark_started(self) -> None:
        """Mark job as started."""
        self.status = SyncJobStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark job as completed."""
        self.status = SyncJobStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.result = result

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = SyncJobStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = SyncJobStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)

    def prepare_retry(self) -> None:
        """Prepare job for retry."""
        self.status = SyncJobStatus.RETRYING
        self.retry_count += 1
        self.started_at = None
        self.error_message = None

    @property
    def duration(self) -> Optional[float]:
        """Get job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def __lt__(self, other: "SyncJob") -> bool:
        """Compare jobs for priority queue."""
        return self.priority < other.priority


class SyncScheduler:
    """Background sync scheduler with queue management and error recovery."""

    def __init__(
        self,
        max_concurrent_jobs: int = 3,
        job_timeout: float = 300.0,
        health_check_interval: float = 60.0,
    ):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.job_timeout = job_timeout
        self.health_check_interval = health_check_interval

        # Job queues and tracking
        self._job_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running_jobs: Dict[str, SyncJob] = {}
        self._completed_jobs: List[SyncJob] = []
        self._failed_jobs: List[SyncJob] = []

        # Scheduler state
        self._is_running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._health_check_task: Optional[asyncio.Task] = None
        self._integration_manager: Optional[IntegrationManager] = None

        # Statistics
        self._stats: Dict[str, Any] = {
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_retried": 0,
            "total_sync_time": 0.0,
            "last_sync": None,
        }

    async def initialize(self) -> None:
        """Initialize the scheduler."""
        self._integration_manager = IntegrationManager()
        await self._integration_manager.initialize()

    def add_job(self, job_type: SyncJobType, target_adapter: Optional[str] = None, priority: int = 5, **kwargs) -> str:
        """Add a sync job to the queue."""
        job = SyncJob(job_type=job_type, target_adapter=target_adapter, priority=priority, **kwargs)

        # Use negative priority for PriorityQueue (lower number = higher priority)
        self._job_queue.put_nowait((-job.priority, time.time(), job))
        return job.id

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job by ID."""
        # Cancel running job
        if job_id in self._running_jobs:
            job = self._running_jobs[job_id]
            job.mark_cancelled()
            return True

        # Can't easily cancel queued jobs in asyncio.PriorityQueue
        # so we'll mark them as cancelled when they're processed
        return False

    def get_job_status(self, job_id: str) -> Optional[SyncJob]:
        """Get status of a job by ID."""
        # Check running jobs
        if job_id in self._running_jobs:
            return self._running_jobs[job_id]

        # Check completed jobs
        for job in self._completed_jobs:
            if job.id == job_id:
                return job

        # Check failed jobs
        for job in self._failed_jobs:
            if job.id == job_id:
                return job

        return None

    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status."""
        return {
            "queue_size": self._job_queue.qsize(),
            "running_jobs": len(self._running_jobs),
            "completed_jobs": len(self._completed_jobs),
            "failed_jobs": len(self._failed_jobs),
            "is_running": self._is_running,
            "stats": self._stats.copy(),
        }

    async def start(self) -> None:
        """Start the scheduler."""
        if self._is_running:
            return

        if not self._integration_manager:
            await self.initialize()

        self._is_running = True

        # Start worker tasks
        for i in range(self.max_concurrent_jobs):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._worker_tasks.append(task)

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._is_running:
            return

        self._is_running = False

        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()

        if self._health_check_task:
            self._health_check_task.cancel()

        # Wait for tasks to complete
        all_tasks = list(self._worker_tasks)
        if self._health_check_task:
            all_tasks.append(self._health_check_task)
        await asyncio.gather(*all_tasks, return_exceptions=True)

        self._worker_tasks.clear()
        self._health_check_task = None

    async def _worker_loop(self, worker_name: str) -> None:
        """Worker loop for processing jobs."""
        while self._is_running:
            try:
                # Get next job with timeout
                try:
                    _, _, job = await asyncio.wait_for(self._job_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Check if job was cancelled while in queue
                if job.status == SyncJobStatus.CANCELLED:
                    continue

                # Execute job
                self._running_jobs[job.id] = job
                await self._execute_job(job, worker_name)

                # Remove from running jobs
                self._running_jobs.pop(job.id, None)

                # Add to completed or failed lists
                if job.status == SyncJobStatus.COMPLETED:
                    self._completed_jobs.append(job)
                    self._stats["jobs_completed"] = self._stats.get("jobs_completed", 0) + 1
                    if job.duration is not None:
                        self._stats["total_sync_time"] = self._stats.get("total_sync_time", 0) + job.duration
                        self._stats["last_sync"] = job.completed_at
                elif job.status == SyncJobStatus.FAILED:
                    if job.can_retry():
                        # Retry job
                        job.prepare_retry()
                        self._stats["jobs_retried"] = self._stats.get("jobs_retried", 0) + 1
                        await asyncio.sleep(job.retry_delay)
                        self._job_queue.put_nowait((-job.priority, time.time(), job))
                    else:
                        self._failed_jobs.append(job)
                        self._stats["jobs_failed"] = self._stats.get("jobs_failed", 0) + 1

            except Exception as e:
                print(f"Error in sync worker {worker_name}: {e}")
                await asyncio.sleep(1.0)

    async def _execute_job(self, job: SyncJob, _worker_name: str) -> None:
        """Execute a sync job."""
        job.mark_started()

        try:
            # Execute based on job type
            if job.job_type == SyncJobType.FULL_SYNC:
                result = await self._execute_full_sync(job)
            elif job.job_type == SyncJobType.INCREMENTAL_SYNC:
                result = await self._execute_incremental_sync(job)
            elif job.job_type == SyncJobType.CONFIG_SYNC:
                result = await self._execute_config_sync(job)
            elif job.job_type == SyncJobType.AGENT_SYNC:
                result = await self._execute_agent_sync(job)
            elif job.job_type == SyncJobType.HEALTH_CHECK:
                result = await self._execute_health_check(job)
            else:
                msg = f"Unknown job type: {job.job_type}"
                raise ValueError(msg)

            job.mark_completed(result)

        except asyncio.TimeoutError:
            job.mark_failed("Job timed out")
        except Exception as e:
            job.mark_failed(str(e))

    async def _execute_full_sync(self, job: SyncJob) -> Dict[str, Any]:
        """Execute a full sync job."""
        if not self._integration_manager:
            msg = "Integration manager not initialized"
            raise ValueError(msg)

        if job.target_adapter:
            # Sync specific adapter
            adapter = self._integration_manager.get_adapter(job.target_adapter)
            if not adapter:
                msg = f"Adapter not found: {job.target_adapter}"
                raise ValueError(msg)

            result = await self._integration_manager.sync_agents([job.target_adapter])
        else:
            # Sync all adapters
            result = await self._integration_manager.sync_agents([])

        return result

    async def _execute_incremental_sync(self, job: SyncJob) -> Dict[str, Any]:
        """Execute an incremental sync job."""
        # For now, incremental sync is the same as full sync
        # In the future, this could track changes and sync only what's needed
        return await self._execute_full_sync(job)

    async def _execute_config_sync(self, _job: SyncJob) -> Dict[str, Any]:
        """Execute a config sync job."""
        if not self._integration_manager:
            msg = "Integration manager not initialized"
            raise ValueError(msg)

        # Validate all adapter configurations
        results = await self._integration_manager.validate_configurations()

        # Sync configurations that need updates
        sync_results: Dict[str, Any] = {}
        for adapter_name, validation_result in results.items():
            if isinstance(validation_result, dict) and validation_result.get("needs_sync", False):
                adapter = self._integration_manager.get_adapter(adapter_name)
                if adapter:
                    # Perform config-specific sync operations
                    sync_result = await adapter.sync_agents([])  # Empty list for config-only sync
                    sync_results[adapter_name] = sync_result

        return {"validation": results, "sync": sync_results}

    async def _execute_agent_sync(self, job: SyncJob) -> Dict[str, Any]:
        """Execute an agent sync job."""
        return await self._execute_full_sync(job)

    async def _execute_health_check(self, job: SyncJob) -> Dict[str, Any]:
        """Execute a health check job."""
        if not self._integration_manager:
            msg = "Integration manager not initialized"
            raise ValueError(msg)

        if job.target_adapter:
            adapter = self._integration_manager.get_adapter(job.target_adapter)
            if not adapter:
                msg = f"Adapter not found: {job.target_adapter}"
                raise ValueError(msg)

            health = await adapter.health_check()
            return {job.target_adapter: health}
        else:
            # Health check all adapters
            health_results = {}
            for adapter_name in self._integration_manager.list_adapters():
                adapter = self._integration_manager.get_adapter(adapter_name)
                if adapter:
                    health = await adapter.health_check()
                    health_results[adapter_name] = health

            return health_results

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._is_running:
            try:
                # Add health check job
                self.add_job(
                    SyncJobType.HEALTH_CHECK,
                    priority=10,  # Low priority
                    max_retries=1,
                )

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                print(f"Error in health check loop: {e}")
                await asyncio.sleep(60.0)

    def cleanup_old_jobs(self, max_completed: int = 100, max_failed: int = 50) -> None:
        """Clean up old completed and failed jobs."""
        # Keep only the most recent completed jobs
        if len(self._completed_jobs) > max_completed:
            self._completed_jobs = sorted(
                self._completed_jobs, key=lambda j: j.completed_at or j.created_at, reverse=True
            )[:max_completed]

        # Keep only the most recent failed jobs
        if len(self._failed_jobs) > max_failed:
            self._failed_jobs = sorted(self._failed_jobs, key=lambda j: j.completed_at or j.created_at, reverse=True)[
                :max_failed
            ]


# Global sync scheduler instance
_sync_scheduler: Optional[SyncScheduler] = None


def get_sync_scheduler() -> SyncScheduler:
    """Get the global sync scheduler instance."""
    global _sync_scheduler  # noqa: PLW0603
    if _sync_scheduler is None:
        _sync_scheduler = SyncScheduler()
    return _sync_scheduler
