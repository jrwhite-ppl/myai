"""
Policy enforcement engine for MyAI enterprise features.

This module provides policy definition, validation, and enforcement
capabilities for enterprise deployments.
"""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from myai.models.agent import AgentSpecification


class PolicyAction(Enum):
    """Actions that can be taken when a policy is violated."""

    ALLOW = "allow"  # Allow the action
    WARN = "warn"  # Allow with warning
    BLOCK = "block"  # Block the action
    QUARANTINE = "quarantine"  # Move to quarantine
    LOG_ONLY = "log_only"  # Log but allow
    REQUIRE_APPROVAL = "require_approval"  # Require manual approval


class PolicyTarget(Enum):
    """Targets that policies can apply to."""

    AGENT = "agent"
    CONFIG = "config"
    USER = "user"
    TOOL = "tool"
    INTEGRATION = "integration"
    COMMAND = "command"
    AGENTS = "agents"  # For compatibility


class PolicyCondition(Enum):
    """Policy condition types."""

    EQUALS = "equals"
    CONTAINS = "contains"
    NOT_EMPTY = "not_empty"


class PolicyRule(BaseModel):
    """A single policy rule with conditions and actions."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Human-readable name for the rule")
    description: Optional[str] = Field(None, description="Detailed description of the rule")
    target: PolicyTarget = Field(..., description="What the rule applies to")
    condition: Dict[str, Any] = Field(..., description="Conditions that trigger the rule")
    action: PolicyAction = Field(..., description="Action to take when rule matches")
    enabled: bool = Field(True, description="Whether the rule is active")
    priority: int = Field(5, description="Rule priority (lower number = higher priority)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Execution tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executions: int = Field(0, description="Number of times rule has been triggered")
    violations: int = Field(0, description="Number of violations detected")

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v):
        """Validate condition structure."""
        if not isinstance(v, dict):
            msg = "Condition must be a dictionary"
            raise ValueError(msg)
        return v

    def matches(self, target_data: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if this rule matches the given target data."""
        context = context or {}

        try:
            # Increment execution counter
            self.executions += 1

            # Check condition based on target type
            if self.target == PolicyTarget.AGENT:
                return self._matches_agent(target_data, context)
            elif self.target == PolicyTarget.CONFIG:
                return self._matches_config(target_data, context)
            elif self.target == PolicyTarget.USER:
                return self._matches_user(target_data, context)
            elif self.target == PolicyTarget.COMMAND:
                return self._matches_command(target_data, context)
            else:
                return self._matches_generic(target_data, context)

        except Exception as e:
            print(f"Error evaluating policy rule {self.id}: {e}")
            return False

    def _matches_agent(self, agent: Union[AgentSpecification, Dict[str, Any]], _context: Dict[str, Any]) -> bool:
        """Check if rule matches an agent."""
        agent_dict = agent.dict() if hasattr(agent, "dict") else agent

        # Check common agent conditions
        conditions = self.condition

        # Name pattern matching
        if "name_pattern" in conditions:
            name = agent_dict.get("metadata", {}).get("name", "")
            pattern = conditions["name_pattern"]
            if not re.match(pattern, name):
                return False

        # Category restrictions
        if "allowed_categories" in conditions:
            category = agent_dict.get("metadata", {}).get("category", "")
            if category not in conditions["allowed_categories"]:
                return True  # Not in allowed categories = violation
            else:
                return False  # In allowed categories = no violation

        # Content restrictions
        if "forbidden_content" in conditions:
            content = agent_dict.get("content", "")
            for forbidden in conditions["forbidden_content"]:
                if forbidden.lower() in content.lower():
                    return True  # Match means violation

        # Size restrictions
        if "max_content_length" in conditions:
            content = agent_dict.get("content", "")
            if len(content) > conditions["max_content_length"]:
                return True  # Match means violation

        # Tag requirements
        if "required_tags" in conditions:
            agent_tags = set(agent_dict.get("metadata", {}).get("tags", []))
            required_tags = set(conditions["required_tags"])
            if not required_tags.issubset(agent_tags):
                return True  # Match means violation

        # If we got here, no violations were found
        return False

    def _matches_config(self, config: Dict[str, Any], _context: Dict[str, Any]) -> bool:
        """Check if rule matches a configuration."""
        conditions = self.condition

        # Check for forbidden keys
        if "forbidden_keys" in conditions:
            for key in conditions["forbidden_keys"]:
                if key in config:
                    return True  # Match means violation

        # Check for required keys
        if "required_keys" in conditions:
            for key in conditions["required_keys"]:
                if key not in config:
                    return True  # Match means violation

        # Value restrictions
        if "value_restrictions" in conditions:
            for key, restriction in conditions["value_restrictions"].items():
                if key in config:
                    value = config[key]
                    if "max_value" in restriction and value > restriction["max_value"]:
                        return True
                    if "min_value" in restriction and value < restriction["min_value"]:
                        return True
                    if "allowed_values" in restriction and value not in restriction["allowed_values"]:
                        return True

        return False

    def _matches_user(self, user_data: Dict[str, Any], _context: Dict[str, Any]) -> bool:
        """Check if rule matches user data."""
        conditions = self.condition

        # Role-based restrictions
        if "allowed_roles" in conditions:
            user_role = user_data.get("role", "user")
            if user_role not in conditions["allowed_roles"]:
                return True

        # Time-based restrictions
        if "allowed_hours" in conditions:
            current_hour = datetime.now(timezone.utc).hour
            allowed_hours = conditions["allowed_hours"]
            if current_hour not in allowed_hours:
                return True

        return False

    def _matches_command(self, command_data: Dict[str, Any], _context: Dict[str, Any]) -> bool:
        """Check if rule matches a command."""
        conditions = self.condition

        # Command name restrictions
        if "forbidden_commands" in conditions:
            command_name = command_data.get("command", "")
            if command_name in conditions["forbidden_commands"]:
                return True

        # Argument restrictions
        if "forbidden_args" in conditions:
            args = command_data.get("args", [])
            for forbidden_arg in conditions["forbidden_args"]:
                if forbidden_arg in args:
                    return True

        return False

    def _matches_generic(self, data: Any, _context: Dict[str, Any]) -> bool:
        """Generic condition matching."""
        conditions = self.condition

        # Simple key-value matching
        if isinstance(data, dict):
            for key, expected_value in conditions.items():
                if key in data and data[key] != expected_value:
                    return True

        return False


class Policy(BaseModel):
    """A policy containing multiple rules."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., description="Policy name")
    description: Optional[str] = Field(None, description="Policy description")
    version: str = Field("1.0.0", description="Policy version")
    rules: List[PolicyRule] = Field(default_factory=list, description="Policy rules")
    enabled: bool = Field(True, description="Whether policy is active")
    enforcement_mode: str = Field("enforce", description="How to enforce policy (enforce, warn, log)")

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_modified: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = Field(None, description="Who created the policy")
    tags: List[str] = Field(default_factory=list, description="Policy tags")

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a rule to this policy."""
        self.rules.append(rule)
        self.last_modified = datetime.now(timezone.utc)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule from this policy."""
        for i, rule in enumerate(self.rules):
            if rule.id == rule_id:
                del self.rules[i]
                self.last_modified = datetime.now(timezone.utc)
                return True
        return False

    def get_violations(self, target_data: Any, context: Optional[Dict[str, Any]] = None) -> List[PolicyRule]:
        """Get all rules that are violated by the target data."""
        violations: List[PolicyRule] = []

        if not self.enabled:
            return violations

        # Sort rules by priority
        sorted_rules = sorted([r for r in self.rules if r.enabled], key=lambda x: x.priority)

        for rule in sorted_rules:
            if rule.matches(target_data, context):
                rule.violations += 1
                violations.append(rule)

        return violations


class PolicyEngine:
    """Main policy enforcement engine."""

    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.stats = {
            "evaluations": 0,
            "violations": 0,
            "blocks": 0,
            "warnings": 0,
        }

    def load_policy(self, policy: Policy) -> None:
        """Load a policy into the engine."""
        self.policies[policy.id] = policy

    def load_policy_from_dict(self, policy_data: Dict[str, Any]) -> str:
        """Load a policy from dictionary data."""
        # Convert rule data to PolicyRule objects
        if "rules" in policy_data:
            rules = []
            for rule_data in policy_data["rules"]:
                rule = PolicyRule(**rule_data)
                rules.append(rule)
            policy_data["rules"] = rules

        policy = Policy(**policy_data)
        self.load_policy(policy)
        return policy.id

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy from the engine."""
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False

    def evaluate(
        self,
        target_data: Any,
        target_type: PolicyTarget,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate policies against target data."""
        self.stats["evaluations"] += 1
        context = context or {}

        result: Dict[str, Any] = {
            "allowed": True,
            "action": PolicyAction.ALLOW,
            "violations": [],
            "messages": [],
            "policy_results": {},
        }

        # Find applicable policies
        applicable_policies = [
            p for p in self.policies.values() if p.enabled and any(r.target == target_type for r in p.rules)
        ]

        all_violations = []

        for policy in applicable_policies:
            violations = policy.get_violations(target_data, context)

            policy_result = {
                "policy_id": policy.id,
                "policy_name": policy.name,
                "violations": [
                    {
                        "rule_id": v.id,
                        "rule_name": v.name,
                        "action": v.action.value,
                        "description": v.description,
                    }
                    for v in violations
                ],
                "enforcement_mode": policy.enforcement_mode,
            }

            result["policy_results"][policy.id] = policy_result
            all_violations.extend(violations)

        # Determine overall action based on violations
        if all_violations:
            self.stats["violations"] += len(all_violations)

            # Get the most restrictive action
            actions = [v.action for v in all_violations]

            if PolicyAction.BLOCK in actions:
                result["allowed"] = False
                result["action"] = PolicyAction.BLOCK
                self.stats["blocks"] += 1
            elif PolicyAction.QUARANTINE in actions:
                result["allowed"] = False
                result["action"] = PolicyAction.QUARANTINE
            elif PolicyAction.REQUIRE_APPROVAL in actions:
                result["allowed"] = False
                result["action"] = PolicyAction.REQUIRE_APPROVAL
            elif PolicyAction.WARN in actions:
                result["action"] = PolicyAction.WARN
                self.stats["warnings"] += 1
            else:
                result["action"] = PolicyAction.LOG_ONLY

            # Collect violation messages
            result["violations"] = all_violations
            result["messages"] = [f"Policy violation: {v.name} - {v.description}" for v in all_violations]

        # Log the evaluation
        self._log_evaluation(target_type, result, context)

        return result

    def _log_evaluation(
        self,
        target_type: PolicyTarget,
        result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """Log a policy evaluation."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_type": target_type.value,
            "allowed": result["allowed"],
            "action": result["action"].value,
            "violation_count": len(result["violations"]),
            "context": context,
        }

        self.audit_log.append(log_entry)

        # Keep only last 1000 entries
        max_audit_log_entries = 1000
        if len(self.audit_log) > max_audit_log_entries:
            self.audit_log = self.audit_log[-max_audit_log_entries:]

    def get_compliance_report(self) -> Dict[str, Any]:
        """Generate a compliance report."""
        total_evaluations = self.stats["evaluations"]
        total_violations = self.stats["violations"]

        # Calculate compliance rate
        compliance_rate = ((total_evaluations - total_violations) / max(total_evaluations, 1)) * 100

        # Policy effectiveness
        policy_stats = {}
        for policy in self.policies.values():
            rule_stats = {}
            for rule in policy.rules:
                rule_stats[rule.id] = {
                    "name": rule.name,
                    "executions": rule.executions,
                    "violations": rule.violations,
                    "violation_rate": rule.violations / max(rule.executions, 1) * 100,
                }

            policy_stats[policy.id] = {
                "name": policy.name,
                "enabled": policy.enabled,
                "rule_count": len(policy.rules),
                "rules": rule_stats,
            }

        return {
            "overview": {
                "total_evaluations": total_evaluations,
                "total_violations": total_violations,
                "compliance_rate": compliance_rate,
                "blocks": self.stats["blocks"],
                "warnings": self.stats["warnings"],
            },
            "policies": policy_stats,
            "recent_violations": [entry for entry in self.audit_log[-50:] if entry["violation_count"] > 0],
        }

    def create_default_policies(self) -> List[str]:
        """Create default enterprise policies."""
        policies = []

        # Security policy
        security_policy = Policy(
            name="Security Policy",
            description="Basic security requirements for agents and configurations",
            version="1.0.0",
            enabled=True,
            enforcement_mode="enforce",
            created_by=None,
            tags=["security", "compliance"],
        )

        # No secrets in agent content
        security_policy.add_rule(
            PolicyRule(
                name="No Secrets in Content",
                description="Prevent secrets from being stored in agent content",
                target=PolicyTarget.AGENT,
                condition={
                    "forbidden_content": [
                        "api_key",
                        "password",
                        "secret",
                        "token",
                        "private_key",
                        "auth_token",
                        "bearer_token",
                    ]
                },
                action=PolicyAction.BLOCK,
                enabled=True,
                executions=0,
                violations=0,
                priority=1,
            )
        )

        # Agent content length limit
        security_policy.add_rule(
            PolicyRule(
                name="Content Length Limit",
                description="Limit agent content to prevent excessive resource usage",
                target=PolicyTarget.AGENT,
                condition={"max_content_length": 50000},  # 50KB limit
                action=PolicyAction.WARN,
                enabled=True,
                executions=0,
                violations=0,
                priority=5,
            )
        )

        policies.append(security_policy.id)
        self.load_policy(security_policy)

        # Quality policy
        quality_policy = Policy(
            name="Quality Policy",
            description="Quality standards for agents",
            version="1.0.0",
            enabled=True,
            enforcement_mode="enforce",
            created_by=None,
            tags=["quality", "standards"],
        )

        # Required tags for agents
        quality_policy.add_rule(
            PolicyRule(
                name="Required Agent Tags",
                description="All agents must have appropriate tags",
                target=PolicyTarget.AGENT,
                condition={"required_tags": ["category"]},
                action=PolicyAction.WARN,
                enabled=True,
                executions=0,
                violations=0,
                priority=3,
            )
        )

        policies.append(quality_policy.id)
        self.load_policy(quality_policy)

        return policies

    def export_policies(self) -> List[Dict[str, Any]]:
        """Export all policies to dictionaries."""
        return [policy.dict() for policy in self.policies.values()]

    def import_policies(self, policies_data: List[Dict[str, Any]]) -> List[str]:
        """Import policies from dictionaries."""
        imported_ids = []

        for policy_data in policies_data:
            try:
                policy_id = self.load_policy_from_dict(policy_data)
                imported_ids.append(policy_id)
            except Exception as e:
                print(f"Error importing policy: {e}")

        return imported_ids


# Global policy engine instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance."""
    global _policy_engine  # noqa: PLW0603
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
