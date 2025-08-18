"""
Usage analytics and monitoring for MyAI enterprise features.

This module provides comprehensive usage tracking, analytics, and reporting
capabilities for enterprise deployments.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from myai.models.path import PathManager


class EventType(Enum):
    """Types of events to track."""

    # Agent events
    AGENT_CREATED = "agent_created"
    AGENT_MODIFIED = "agent_modified"
    AGENT_DELETED = "agent_deleted"
    AGENT_EXECUTED = "agent_executed"

    # Configuration events
    CONFIG_UPDATED = "config_updated"
    CONFIG_VALIDATED = "config_validated"

    # Integration events
    INTEGRATION_SYNC = "integration_sync"
    INTEGRATION_ERROR = "integration_error"

    # Command events
    COMMAND_EXECUTED = "command_executed"
    COMMAND_ERROR = "command_error"

    # Policy events
    POLICY_VIOLATION = "policy_violation"
    POLICY_APPLIED = "policy_applied"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


class UsageEvent:
    """A usage event with metadata."""

    def __init__(
        self,
        event_type: EventType,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.id = str(uuid4())
        self.event_type = event_type
        self.user_id = user_id or "system"
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageEvent":
        """Create event from dictionary."""
        event = cls(
            event_type=EventType(data["event_type"]),
            user_id=data["user_id"],
            metadata=data["metadata"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )
        event.id = data["id"]
        return event


class UsageAnalytics:
    """Usage analytics and monitoring system."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (PathManager().get_user_path() / "analytics")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.events_file = self.storage_path / "events.jsonl"
        self.stats_file = self.storage_path / "stats.json"

        # In-memory cache for recent events
        self.recent_events: List[UsageEvent] = []
        self.max_recent_events = 1000

        # Statistics cache
        self.cached_stats: Optional[Dict[str, Any]] = None
        self.stats_cache_time: Optional[datetime] = None
        self.stats_cache_ttl = 300  # 5 minutes

    def track_event(
        self,
        event_type: EventType,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Track a usage event."""
        event = UsageEvent(event_type, user_id, metadata)

        # Add to recent events
        self.recent_events.append(event)
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events.pop(0)

        # Persist to disk
        self._persist_event(event)

        # Invalidate stats cache
        self.cached_stats = None

        return event.id

    def _persist_event(self, event: UsageEvent) -> None:
        """Persist event to disk storage."""
        try:
            with open(self.events_file, "a", encoding="utf-8") as f:
                json.dump(event.to_dict(), f)
                f.write("\n")
        except Exception as e:
            print(f"Error persisting usage event: {e}")

    def get_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[EventType]] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[UsageEvent]:
        """Get events matching criteria."""
        # Start with recent events for performance
        events = self.recent_events.copy()

        # Load more events from disk if needed
        if start_time or (limit and limit > len(events)):
            events.extend(self._load_events_from_disk(start_time, end_time, limit))

        # Apply filters
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply limit
        if limit:
            events = events[:limit]

        return events

    def _load_events_from_disk(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[UsageEvent]:
        """Load events from disk storage."""
        events: List[UsageEvent] = []

        if not self.events_file.exists():
            return events

        try:
            with open(self.events_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        event_data = json.loads(line.strip())
                        event = UsageEvent.from_dict(event_data)

                        # Apply time filters
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue

                        events.append(event)

                        if limit and len(events) >= limit:
                            break

                    except Exception as e:
                        print(f"Error parsing event line: {e}")
                        continue

        except Exception as e:
            print(f"Error loading events from disk: {e}")

        return events

    def get_statistics(self, *, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get usage statistics."""
        # Check cache
        if (
            not refresh_cache
            and self.cached_stats
            and self.stats_cache_time
            and (datetime.now(timezone.utc) - self.stats_cache_time).total_seconds() < self.stats_cache_ttl
        ):
            return self.cached_stats

        # Calculate statistics
        stats = self._calculate_statistics()

        # Update cache
        self.cached_stats = stats
        self.stats_cache_time = datetime.now(timezone.utc)

        return stats

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive usage statistics."""
        # Get events from last 30 days
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=30)

        events = self.get_events(start_time=start_time, end_time=end_time)

        # Basic counts
        total_events = len(events)
        event_counts: defaultdict[str, int] = defaultdict(int)
        user_counts: defaultdict[str, int] = defaultdict(int)
        daily_counts: defaultdict[str, int] = defaultdict(int)
        hourly_counts: defaultdict[int, int] = defaultdict(int)

        for event in events:
            event_counts[event.event_type.value] += 1
            user_counts[event.user_id] += 1

            # Daily activity
            day_key = event.timestamp.date().isoformat()
            daily_counts[day_key] += 1

            # Hourly activity
            hour_key = event.timestamp.hour
            hourly_counts[hour_key] += 1

        # Calculate trends
        last_week_events = [e for e in events if e.timestamp >= end_time - timedelta(days=7)]
        previous_week_start = end_time - timedelta(days=14)
        previous_week_end = end_time - timedelta(days=7)
        previous_week_events = [e for e in events if previous_week_start <= e.timestamp < previous_week_end]

        # Calculate growth rate
        current_week_count = len(last_week_events)
        previous_week_count = len(previous_week_events)
        growth_rate = 0.0
        if previous_week_count > 0:
            growth_rate = ((current_week_count - previous_week_count) / previous_week_count) * 100

        # Most active users
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Most common event types
        top_events = sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "overview": {
                "total_events": total_events,
                "unique_users": len(user_counts),
                "events_last_week": current_week_count,
                "growth_rate_percent": growth_rate,
                "avg_events_per_day": total_events / 30,
                "avg_events_per_user": total_events / max(len(user_counts), 1),
            },
            "event_types": dict(event_counts),
            "top_event_types": top_events,
            "user_activity": {
                "total_users": len(user_counts),
                "top_users": top_users,
            },
            "temporal_patterns": {
                "daily_activity": dict(daily_counts),
                "hourly_activity": dict(hourly_counts),
            },
            "recent_activity": {
                "last_24h": len([e for e in events if e.timestamp >= end_time - timedelta(days=1)]),
                "last_week": current_week_count,
                "last_month": total_events,
            },
            "generated_at": end_time.isoformat(),
        }

    def generate_report(
        self,
        report_type: str = "weekly",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate a detailed usage report."""
        if report_type == "weekly":
            if not start_time:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=7)
        elif report_type == "monthly":
            if not start_time:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=30)
        elif report_type == "daily":
            if not start_time:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=1)

        end_time = end_time or datetime.now(timezone.utc)

        events = self.get_events(start_time=start_time, end_time=end_time)

        # Agent usage patterns
        agent_events = [e for e in events if e.event_type.value.startswith("agent_")]
        agent_stats = {
            "total_agent_events": len(agent_events),
            "agents_created": len([e for e in agent_events if e.event_type == EventType.AGENT_CREATED]),
            "agents_modified": len([e for e in agent_events if e.event_type == EventType.AGENT_MODIFIED]),
            "agents_executed": len([e for e in agent_events if e.event_type == EventType.AGENT_EXECUTED]),
        }

        # Integration patterns
        integration_events = [e for e in events if e.event_type.value.startswith("integration_")]
        integration_stats = {
            "total_sync_events": len([e for e in integration_events if e.event_type == EventType.INTEGRATION_SYNC]),
            "sync_errors": len([e for e in integration_events if e.event_type == EventType.INTEGRATION_ERROR]),
            "success_rate": 0.0,
        }

        if integration_stats["total_sync_events"] > 0:
            success_count = integration_stats["total_sync_events"] - integration_stats["sync_errors"]
            integration_stats["success_rate"] = (success_count / integration_stats["total_sync_events"]) * 100

        # Policy compliance
        policy_events = [e for e in events if e.event_type.value.startswith("policy_")]
        policy_stats = {
            "policy_violations": len([e for e in policy_events if e.event_type == EventType.POLICY_VIOLATION]),
            "policies_applied": len([e for e in policy_events if e.event_type == EventType.POLICY_APPLIED]),
        }

        return {
            "report_type": report_type,
            "period": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat(),
                "duration_days": (end_time - start_time).days if start_time else None,
            },
            "summary": {
                "total_events": len(events),
                "unique_users": len({e.user_id for e in events}),
                "most_active_day": self._get_most_active_day(events),
            },
            "agent_usage": agent_stats,
            "integrations": integration_stats,
            "policy_compliance": policy_stats,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _get_most_active_day(self, events: List[UsageEvent]) -> Optional[str]:
        """Get the most active day from a list of events."""
        if not events:
            return None

        daily_counts: defaultdict[str, int] = defaultdict(int)
        for event in events:
            day_key = event.timestamp.date().isoformat()
            daily_counts[day_key] += 1

        if not daily_counts:
            return None

        return max(daily_counts.items(), key=lambda x: x[1])[0]

    def cleanup_old_events(self, days_to_keep: int = 90) -> int:
        """Clean up old events from storage."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        # Clean up in-memory events
        initial_count = len(self.recent_events)
        self.recent_events = [e for e in self.recent_events if e.timestamp >= cutoff_time]
        cleaned_memory = initial_count - len(self.recent_events)

        # Clean up disk storage (would require rewriting the file)
        # For now, just return memory cleanup count
        return cleaned_memory


# Global analytics instance
_usage_analytics: Optional[UsageAnalytics] = None


def get_usage_analytics() -> UsageAnalytics:
    """Get the global usage analytics instance."""
    global _usage_analytics  # noqa: PLW0603
    if _usage_analytics is None:
        _usage_analytics = UsageAnalytics()
    return _usage_analytics
