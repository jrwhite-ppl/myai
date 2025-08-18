"""
Tests for central manager functionality.
"""

from datetime import datetime, timezone

import pytest

from myai.enterprise.central_manager import CentralManager


class TestCentralManager:
    """Test cases for the CentralManager."""

    def setup_method(self):
        """Set up test fixtures."""
        # Server mode (no server_url)
        self.server_manager = CentralManager()

        # Client mode
        self.client_manager = CentralManager(server_url="https://central.example.com")

    def test_server_mode_detection(self):
        """Test server mode detection."""
        assert self.server_manager.is_server_mode is True
        assert self.client_manager.is_server_mode is False

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test server mode initialization."""
        await self.server_manager.start()

        # Should have initialized policy engine with defaults
        policies = list(self.server_manager.policy_engine.policies.values())
        assert len(policies) > 0

        # Should have started maintenance task
        assert self.server_manager._sync_task is not None
        assert not self.server_manager._sync_task.done()

        await self.server_manager.stop()

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client mode initialization."""
        await self.client_manager.start()

        # Should have started sync task
        assert self.client_manager._sync_task is not None
        assert not self.client_manager._sync_task.done()

        await self.client_manager.stop()

    @pytest.mark.asyncio
    async def test_node_registration(self):
        """Test managed node registration."""
        node_info = {
            "hostname": "test-node-1",
            "version": "1.0.0",
            "capabilities": ["sync", "policy"],
        }

        success = await self.server_manager.register_node("node-123", node_info)
        assert success is True

        # Should not work in client mode
        success = await self.client_manager.register_node("node-456", node_info)
        assert success is False

        # Verify node was registered
        assert "node-123" in self.server_manager.managed_nodes
        node = self.server_manager.managed_nodes["node-123"]
        assert node["hostname"] == "test-node-1"
        assert node["status"] == "active"
        assert "registered_at" in node
        assert "last_seen" in node

    @pytest.mark.asyncio
    async def test_node_status_update(self):
        """Test node status updates."""
        # Register a node first
        await self.server_manager.register_node("node-123", {"hostname": "test-node"})

        # Update status
        status_data = {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "active_agents": 5,
        }

        success = await self.server_manager.update_node_status("node-123", status_data)
        assert success is True

        node = self.server_manager.managed_nodes["node-123"]
        assert node["cpu_usage"] == 45.2
        assert node["memory_usage"] == 67.8
        assert node["active_agents"] == 5

        # Should update last_seen
        assert node["last_seen"] is not None

    @pytest.mark.asyncio
    async def test_node_status_update_nonexistent(self):
        """Test updating status of nonexistent node."""
        success = await self.server_manager.update_node_status("nonexistent-node", {"status": "test"})
        assert success is False

    @pytest.mark.asyncio
    async def test_policy_deployment(self):
        """Test policy deployment to managed nodes."""
        # Register some nodes
        await self.server_manager.register_node("node-1", {"hostname": "node1"})
        await self.server_manager.register_node("node-2", {"hostname": "node2"})

        # Create policy data
        policy_data = {
            "name": "test-deployment-policy",
            "description": "Test policy for deployment",
            "rules": [
                {
                    "name": "Name Required",
                    "target": "agent",
                    "condition": {"required_tags": ["category"]},
                    "action": "warn",
                }
            ],
        }

        # Deploy to all nodes
        results = await self.server_manager.deploy_policy(policy_data)

        assert len(results) == 2
        assert results["node-1"] is True
        assert results["node-2"] is True

        # Verify policy was added to local policy engine
        policies = list(self.server_manager.policy_engine.policies.values())
        deployed_policies = [p for p in policies if p.name == "test-deployment-policy"]
        assert len(deployed_policies) == 1

        # Verify node policy tracking
        node1 = self.server_manager.managed_nodes["node-1"]
        assert "policies" in node1
        assert len(node1["policies"]) == 1

    @pytest.mark.asyncio
    async def test_policy_deployment_specific_nodes(self):
        """Test policy deployment to specific nodes."""
        # Register nodes
        await self.server_manager.register_node("node-1", {"hostname": "node1"})
        await self.server_manager.register_node("node-2", {"hostname": "node2"})
        await self.server_manager.register_node("node-3", {"hostname": "node3"})

        policy_data = {
            "name": "selective-policy",
            "description": "Policy for specific nodes",
            "rules": [],
        }

        # Deploy only to node-1 and node-3
        results = await self.server_manager.deploy_policy(policy_data, target_nodes=["node-1", "node-3"])

        assert len(results) == 2
        assert "node-1" in results
        assert "node-3" in results
        assert "node-2" not in results

    @pytest.mark.asyncio
    async def test_compliance_status_reporting(self):
        """Test organization-wide compliance status."""
        # Register some nodes
        await self.server_manager.register_node(
            "node-1",
            {
                "hostname": "node1",
                "status": "active",
            },
        )
        await self.server_manager.register_node(
            "node-2",
            {
                "hostname": "node2",
                "status": "inactive",
            },
        )

        status = await self.server_manager.get_compliance_status()

        assert "central_server" in status
        assert "managed_nodes" in status
        assert status["total_nodes"] == 2
        assert status["active_nodes"] == 1

        # Check node-specific reports
        node_reports = status["managed_nodes"]
        assert "node-1" in node_reports
        assert "node-2" in node_reports
        assert node_reports["node-1"]["status"] == "active"
        assert node_reports["node-2"]["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_client_mode_restrictions(self):
        """Test that client mode has appropriate restrictions."""
        # These operations should not work in client mode

        node_info = {"hostname": "test"}
        success = await self.client_manager.register_node("node-123", node_info)
        assert success is False

        policy_data = {"name": "test", "rules": []}
        results = await self.client_manager.deploy_policy(policy_data)
        assert results == {}

        status = await self.client_manager.get_compliance_status()
        assert status == {}

    @pytest.mark.asyncio
    async def test_server_maintenance_loop(self):
        """Test server maintenance loop functionality."""
        # Register a node with an old last_seen time
        old_time = datetime.now(timezone.utc)
        await self.server_manager.register_node("stale-node", {"hostname": "stale"})

        # Manually set an old last_seen time (simulate 25+ hours ago)
        from datetime import timedelta

        self.server_manager.managed_nodes["stale-node"]["last_seen"] = old_time - timedelta(hours=25)

        # Run cleanup
        await self.server_manager._cleanup_old_data()

        # Node should be marked inactive
        node = self.server_manager.managed_nodes["stale-node"]
        assert node["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_sync_state_tracking(self):
        """Test sync state tracking in client mode."""
        # Initially no sync
        assert self.client_manager.last_sync is None

        # Simulate sync
        await self.client_manager._sync_with_server()

        # Should have updated last_sync
        assert self.client_manager.last_sync is not None
        assert isinstance(self.client_manager.last_sync, datetime)

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self):
        """Test complete manager lifecycle."""
        manager = CentralManager()

        # Start
        await manager.start()
        assert manager._sync_task is not None

        # Should be running
        assert not manager._sync_task.done()

        # Stop
        await manager.stop()

        # Task should be cancelled
        assert manager._sync_task.cancelled() or manager._sync_task.done()

    @pytest.mark.asyncio
    async def test_multiple_policy_deployments(self):
        """Test multiple policy deployments to same node."""
        # Register a node
        await self.server_manager.register_node("multi-policy-node", {"hostname": "test"})

        # Deploy multiple policies
        policy1 = {"name": "policy-1", "rules": []}

        policy2 = {"name": "policy-2", "rules": []}

        await self.server_manager.deploy_policy(policy1)
        await self.server_manager.deploy_policy(policy2)

        # Node should have both policies tracked
        node = self.server_manager.managed_nodes["multi-policy-node"]
        assert len(node["policies"]) == 2

        policy_names = [p["policy_id"] for p in node["policies"]]
        # Both policies should be tracked (policy IDs will be generated)
        assert len(set(policy_names)) == 2

    @pytest.mark.asyncio
    async def test_node_update_without_registration(self):
        """Test updating node status without prior registration."""
        success = await self.server_manager.update_node_status("unregistered-node", {"status": "test"})

        assert success is False
        assert "unregistered-node" not in self.server_manager.managed_nodes
