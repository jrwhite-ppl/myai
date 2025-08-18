"""
Tests for policy engine functionality.
"""

from myai.enterprise.policy_engine import (
    Policy,
    PolicyAction,
    PolicyEngine,
    PolicyRule,
    PolicyTarget,
)


class TestPolicy:
    """Test cases for the Policy class."""

    def test_policy_creation(self):
        """Test policy creation."""
        policy = Policy(
            name="test-policy",
            description="Test policy",
        )

        assert policy.name == "test-policy"
        assert policy.description == "Test policy"
        assert policy.enabled is True
        assert policy.id is not None
        assert policy.version == "1.0.0"
        assert policy.rules == []

    def test_policy_rule_addition(self):
        """Test adding rules to policy."""
        policy = Policy(
            name="test-policy",
            description="Test policy",
        )

        rule = PolicyRule(
            name="API Key Required",
            target=PolicyTarget.CONFIG,
            condition={"field": "api_key", "operator": "not_empty"},
            action=PolicyAction.BLOCK,
        )

        policy.add_rule(rule)
        assert len(policy.rules) == 1
        assert policy.rules[0] == rule

    def test_policy_rule_evaluation(self):
        """Test policy rule evaluation."""
        policy = Policy(
            name="api-key-policy",
            description="Require API key",
        )

        # Add rule requiring API key
        policy.add_rule(
            PolicyRule(
                name="API Key Required",
                target=PolicyTarget.CONFIG,
                condition={"required_keys": ["api_key"]},
                action=PolicyAction.BLOCK,
            )
        )

        # Test with missing API key
        config_without_key = {"model": "gpt-4"}
        violations = policy.get_violations(config_without_key)
        assert len(violations) == 1

        # Test with API key present
        config_with_key = {"model": "gpt-4", "api_key": "test-key"}
        violations = policy.get_violations(config_with_key)
        assert len(violations) == 0

    def test_policy_contains_condition(self):
        """Test CONTAINS condition."""
        policy = Policy(
            name="model-policy",
            description="Only allow GPT models",
        )

        policy.add_rule(
            PolicyRule(
                name="GPT Model Required",
                target=PolicyTarget.CONFIG,
                condition={"value_restrictions": {"model": {"allowed_values": ["gpt-3.5", "gpt-4", "gpt-4-turbo"]}}},
                action=PolicyAction.WARN,
            )
        )

        # Should pass
        config_gpt = {"model": "gpt-4"}
        violations = policy.get_violations(config_gpt)
        assert len(violations) == 0

        # Should fail
        config_claude = {"model": "claude-3"}
        violations = policy.get_violations(config_claude)
        assert len(violations) == 1

    def test_policy_equals_condition(self):
        """Test EQUALS condition."""
        policy = Policy(
            name="temperature-policy",
            description="Require specific temperature",
        )

        policy.add_rule(
            PolicyRule(
                name="Temperature Equals Check",
                target=PolicyTarget.CONFIG,
                condition={"value_restrictions": {"temperature": {"allowed_values": [0.7]}}},
                action=PolicyAction.BLOCK,
            )
        )

        # Should pass
        config_correct = {"temperature": 0.7}
        violations = policy.get_violations(config_correct)
        assert len(violations) == 0

        # Should fail
        config_wrong = {"temperature": 0.5}
        violations = policy.get_violations(config_wrong)
        assert len(violations) == 1

    def test_policy_dict_conversion(self):
        """Test policy dictionary conversion."""
        policy = Policy(
            name="test-policy",
            description="Test policy",
        )

        policy_dict = policy.dict()

        assert policy_dict["name"] == "test-policy"
        assert policy_dict["description"] == "Test policy"
        assert policy_dict["enabled"] is True
        assert policy_dict["version"] == "1.0.0"


class TestPolicyEngine:
    """Test cases for the PolicyEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = PolicyEngine()

    def test_policy_creation(self):
        """Test policy creation."""
        policy_data = {"name": "test-policy", "description": "Test policy", "rules": []}

        policy_id = self.engine.load_policy_from_dict(policy_data)

        assert policy_id is not None
        assert policy_id in self.engine.policies

        policy = self.engine.policies[policy_id]
        assert policy.name == "test-policy"

    def test_policy_rule_addition(self):
        """Test adding rules to policies."""
        policy_data = {
            "name": "agent-name-policy",
            "description": "Agent name requirements",
            "rules": [
                {
                    "name": "Agent Name Required",
                    "target": PolicyTarget.AGENT.value,
                    "condition": {"required_tags": ["category"]},
                    "action": PolicyAction.WARN.value,
                }
            ],
        }

        policy_id = self.engine.load_policy_from_dict(policy_data)

        assert policy_id is not None
        policy = self.engine.policies[policy_id]
        assert len(policy.rules) == 1

    def test_policy_evaluation(self):
        """Test policy evaluation."""
        # Create policy requiring agent tags
        policy_data = {
            "name": "agent-tag-policy",
            "description": "Require agent tags",
            "rules": [
                {
                    "name": "Agent Tags Required",
                    "target": PolicyTarget.AGENT.value,
                    "condition": {"required_tags": ["category"]},
                    "action": PolicyAction.BLOCK.value,
                }
            ],
        }

        self.engine.load_policy_from_dict(policy_data)

        # Test agent without category tag
        agent_without_tag = {
            "metadata": {"name": "test-agent", "tags": []},
            "content": "Test agent",
        }

        result = self.engine.evaluate(agent_without_tag, PolicyTarget.AGENT)
        assert result["allowed"] is False
        assert len(result["violations"]) == 1

        # Test agent with category tag
        agent_with_tag = {
            "metadata": {"name": "test-agent", "tags": ["category"]},
            "content": "Test agent",
        }

        result = self.engine.evaluate(agent_with_tag, PolicyTarget.AGENT)
        assert result["allowed"] is True
        assert len(result["violations"]) == 0

    def test_policy_enabling_disabling(self):
        """Test enabling and disabling policies."""
        policy_data = {"name": "test-policy", "description": "Test policy", "rules": []}

        policy_id = self.engine.load_policy_from_dict(policy_data)

        # Initially enabled
        assert self.engine.policies[policy_id].enabled

        # Disable policy
        self.engine.policies[policy_id].enabled = False
        assert not self.engine.policies[policy_id].enabled

        # Enable policy
        self.engine.policies[policy_id].enabled = True
        assert self.engine.policies[policy_id].enabled

    def test_policy_removal(self):
        """Test policy removal."""
        policy_data = {"name": "test-policy", "description": "Test policy", "rules": []}

        policy_id = self.engine.load_policy_from_dict(policy_data)

        assert policy_id in self.engine.policies

        success = self.engine.remove_policy(policy_id)
        assert success
        assert policy_id not in self.engine.policies

    def test_policy_listing(self):
        """Test policy listing."""
        # Create multiple policies
        policy1_data = {
            "name": "policy-1",
            "description": "First policy",
            "rules": [
                {
                    "name": "Rule 1",
                    "target": PolicyTarget.AGENT.value,
                    "condition": {"required_tags": ["test"]},
                    "action": PolicyAction.WARN.value,
                }
            ],
        }

        policy2_data = {
            "name": "policy-2",
            "description": "Second policy",
            "rules": [
                {
                    "name": "Rule 2",
                    "target": PolicyTarget.CONFIG.value,
                    "condition": {"required_keys": ["api_key"]},
                    "action": PolicyAction.BLOCK.value,
                }
            ],
        }

        self.engine.load_policy_from_dict(policy1_data)
        self.engine.load_policy_from_dict(policy2_data)

        all_policies = list(self.engine.policies.values())
        assert len(all_policies) == 2

        # Check policy names
        policy_names = [p.name for p in all_policies]
        assert "policy-1" in policy_names
        assert "policy-2" in policy_names

    def test_compliance_report(self):
        """Test compliance report generation."""
        # Create a policy
        policy_data = {
            "name": "test-policy",
            "description": "Test policy",
            "rules": [
                {
                    "name": "API Key Required",
                    "target": PolicyTarget.CONFIG.value,
                    "condition": {"required_keys": ["api_key"]},
                    "action": PolicyAction.WARN.value,
                }
            ],
        }

        self.engine.load_policy_from_dict(policy_data)

        # Evaluate some data
        config_good = {"api_key": "test-key"}
        config_bad = {"model": "gpt-4"}  # missing api_key

        self.engine.evaluate(config_good, PolicyTarget.CONFIG)
        self.engine.evaluate(config_bad, PolicyTarget.CONFIG)

        report = self.engine.get_compliance_report()

        assert "overview" in report
        assert "total_evaluations" in report["overview"]
        assert "total_violations" in report["overview"]
        assert "compliance_rate" in report["overview"]
        assert report["overview"]["total_evaluations"] == 2
        assert report["overview"]["total_violations"] == 1
        assert report["overview"]["compliance_rate"] == 50.0

    def test_policy_loading_from_dict(self):
        """Test loading policy from dictionary."""
        policy_data = {
            "name": "loaded-policy",
            "description": "Policy loaded from dict",
            "rules": [
                {
                    "name": "Category Approval",
                    "target": PolicyTarget.AGENT.value,
                    "condition": {"allowed_categories": ["approved"]},
                    "action": PolicyAction.BLOCK.value,
                }
            ],
        }

        policy_id = self.engine.load_policy_from_dict(policy_data)
        assert policy_id is not None

        policy = self.engine.policies[policy_id]
        assert policy.name == "loaded-policy"
        assert len(policy.rules) == 1

        # Test evaluation
        approved_agent = {
            "metadata": {"category": "approved"},
            "content": "Test agent",
        }

        result = self.engine.evaluate(approved_agent, PolicyTarget.AGENT)
        assert result["allowed"] is True

        unapproved_agent = {
            "metadata": {"category": "experimental"},
            "content": "Test agent",
        }

        result = self.engine.evaluate(unapproved_agent, PolicyTarget.AGENT)
        assert result["allowed"] is False
