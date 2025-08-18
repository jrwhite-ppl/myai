"""
Performance profiler for MyAI operations.

This module provides performance profiling and monitoring capabilities.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional


class PerformanceProfiler:
    """Performance profiler for MyAI operations."""

    def __init__(self):
        self.enabled = True
        self.profiles: Dict[str, List[float]] = {}

    @contextmanager
    def profile(self, operation: str):
        """Profile an operation."""
        if not self.enabled:
            yield
            return

        start_time = time.perf_counter()
        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time

            if operation not in self.profiles:
                self.profiles[operation] = []
            self.profiles[operation].append(duration)

    def get_stats(self) -> Dict[str, Any]:
        """Get profiling statistics."""
        stats = {}

        for operation, durations in self.profiles.items():
            if durations:
                stats[operation] = {
                    "count": len(durations),
                    "total_time": sum(durations),
                    "avg_time": sum(durations) / len(durations),
                    "min_time": min(durations),
                    "max_time": max(durations),
                }
            else:
                stats[operation] = {
                    "count": 0,
                    "total_time": 0.0,
                    "avg_time": 0.0,
                    "min_time": 0.0,
                    "max_time": 0.0,
                }

        return {
            "enabled": self.enabled,
            "operations": stats,
        }

    def clear_stats(self) -> None:
        """Clear profiling statistics."""
        self.profiles.clear()


# Global profiler instance
_performance_profiler: Optional[PerformanceProfiler] = None


def get_performance_profiler() -> PerformanceProfiler:
    """Get the global performance profiler instance."""
    global _performance_profiler  # noqa: PLW0603
    if _performance_profiler is None:
        _performance_profiler = PerformanceProfiler()
    return _performance_profiler
