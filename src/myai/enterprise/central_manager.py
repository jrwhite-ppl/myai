"""
Centralized management system for MyAI enterprise features.

This module provides centralized configuration management, remote policy updates,
and coordination of enterprise features across the organization.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from myai.enterprise.policy_engine import get_policy_engine


class CentralManager:
    """Central management system for enterprise deployments."""

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url
        self.policy_engine = get_policy_engine()
        self.managed_nodes: Dict[str, Dict[str, Any]] = {}
        self.is_server_mode = server_url is None  # None means we are the server

        # Management state
        self.last_sync: Optional[datetime] = None
        self.sync_interval = 300.0  # 5 minutes
        self._sync_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start central management operations."""
        if self.is_server_mode:
            await self._start_server_mode()
        else:
            await self._start_client_mode()

    async def stop(self) -> None:
        """Stop central management operations."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def _start_server_mode(self) -> None:
        """Start in server mode (central management server)."""
        # Initialize with default policies
        self.policy_engine.create_default_policies()

        # Start periodic cleanup
        self._sync_task = asyncio.create_task(self._server_maintenance_loop())

    async def _start_client_mode(self) -> None:
        """Start in client mode (managed node)."""
        # Start periodic sync with server
        self._sync_task = asyncio.create_task(self._client_sync_loop())

    async def _server_maintenance_loop(self) -> None:
        """Server maintenance loop."""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)

                # Clean up old data
                await self._cleanup_old_data()

                # Update node statistics
                await self._update_node_stats()

            except Exception as e:
                print(f"Error in server maintenance loop: {e}")
                await asyncio.sleep(60.0)

    async def _client_sync_loop(self) -> None:
        """Client sync loop."""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)

                if self.server_url:
                    await self._sync_with_server()

            except Exception as e:
                print(f"Error in client sync loop: {e}")
                await asyncio.sleep(60.0)

    async def register_node(self, node_id: str, node_info: Dict[str, Any]) -> bool:
        """Register a managed node."""
        if not self.is_server_mode:
            return False

        self.managed_nodes[node_id] = {
            "registered_at": datetime.now(timezone.utc),
            "last_seen": datetime.now(timezone.utc),
            "status": "active",  # Default status
            **node_info,  # This will override the default status if provided
        }

        return True

    async def update_node_status(self, node_id: str, status_data: Dict[str, Any]) -> bool:
        """Update status of a managed node."""
        if not self.is_server_mode or node_id not in self.managed_nodes:
            return False

        self.managed_nodes[node_id].update(
            {
                **status_data,
                "last_seen": datetime.now(timezone.utc),
            }
        )

        return True

    async def deploy_policy(
        self, policy_data: Dict[str, Any], target_nodes: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Deploy policy to managed nodes."""
        if not self.is_server_mode:
            return {}

        # Load policy locally first
        policy_id = self.policy_engine.load_policy_from_dict(policy_data)

        results = {}
        target_list = target_nodes or list(self.managed_nodes.keys())

        for node_id in target_list:
            if node_id in self.managed_nodes:
                # In a real implementation, this would send the policy to the remote node
                # For now, we'll simulate success
                results[node_id] = True

                # Update node policy info
                if "policies" not in self.managed_nodes[node_id]:
                    self.managed_nodes[node_id]["policies"] = []
                self.managed_nodes[node_id]["policies"].append(
                    {
                        "policy_id": policy_id,
                        "deployed_at": datetime.now(timezone.utc),
                    }
                )

        return results

    async def get_compliance_status(self) -> Dict[str, Any]:
        """Get organization-wide compliance status."""
        if not self.is_server_mode:
            return {}

        # Get local compliance report
        local_report = self.policy_engine.get_compliance_report()

        # Aggregate node reports
        node_reports = {}
        for node_id, node_info in self.managed_nodes.items():
            # In a real implementation, this would fetch reports from remote nodes
            node_reports[node_id] = {
                "status": node_info.get("status", "unknown"),
                "last_seen": node_info.get("last_seen"),
                "compliance_rate": 95.0,  # Simulated
                "policies_count": len(node_info.get("policies", [])),
            }

        return {
            "central_server": local_report,
            "managed_nodes": node_reports,
            "total_nodes": len(self.managed_nodes),
            "active_nodes": len([n for n in self.managed_nodes.values() if n.get("status") == "active"]),
        }

    async def _sync_with_server(self) -> None:
        """Sync with central management server (client mode)."""
        if not self.server_url:
            return

        # In a real implementation, this would make HTTP requests to the server
        # For now, we'll simulate the sync
        print(f"Syncing with central server at {self.server_url}")

        self.last_sync = datetime.now(timezone.utc)

    async def _cleanup_old_data(self) -> None:
        """Clean up old data on the server."""
        current_time = datetime.now(timezone.utc)

        # Remove nodes that haven't been seen in over 24 hours
        cache_expiry_seconds = 86400  # 24 hours
        stale_nodes = [
            node_id
            for node_id, node_info in self.managed_nodes.items()
            if (current_time - node_info.get("last_seen", current_time)).total_seconds() > cache_expiry_seconds
        ]

        for node_id in stale_nodes:
            self.managed_nodes[node_id]["status"] = "inactive"

    async def _update_node_stats(self) -> None:
        """Update statistics for managed nodes."""
        # This would collect and aggregate statistics from all nodes
        pass


# Global central manager instance
_central_manager: Optional[CentralManager] = None


def get_central_manager(server_url: Optional[str] = None) -> CentralManager:
    """Get the global central manager instance."""
    global _central_manager  # noqa: PLW0603
    if _central_manager is None:
        _central_manager = CentralManager(server_url)
    return _central_manager
