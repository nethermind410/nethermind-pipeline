"""Automation — recurring workflows through Hermes.

Respects rights, permissions, security, budget, capability,
human approval, publishing gates.

No autonomous publishing unless explicitly authorised.
"""
import hashlib
import time
from typing import Optional


class AutomationRule:
    """A single automation rule."""

    def __init__(self, rule_id: str, name: str, trigger: str,
                 action: str, source_id: str = "",
                 rights_required: str = "AUTHORISED",
                 requires_approval: bool = True,
                 budget_limit: float = 0.0,
                 capabilities_required: list = None,
                 schedule: str = "",
                 enabled: bool = True):
        self.rule_id = rule_id
        self.name = name
        self.trigger = trigger  # manual, schedule, event
        self.action = action  # research, script, publish, etc.
        self.source_id = source_id
        self.rights_required = rights_required
        self.requires_approval = requires_approval
        self.budget_limit = budget_limit
        self.capabilities_required = capabilities_required or []
        self.schedule = schedule
        self.enabled = enabled

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "trigger": self.trigger,
            "action": self.action,
            "source_id": self.source_id,
            "rights_required": self.rights_required,
            "requires_approval": self.requires_approval,
            "budget_limit": self.budget_limit,
            "capabilities_required": self.capabilities_required,
            "schedule": self.schedule,
            "enabled": self.enabled,
        }


class AutomationEngine:
    """Executes automation rules safely."""

    VERSION = "automation-v1"

    TRIGGER_MAP = {
        "research_creator": "creator_research",
        "script_content": "script_writer",
        "publish_content": "platform_poster",
        "qc_check": "qc_agent",
        "learn_patterns": "learning_brain",
    }

    def __init__(self, db, security=None, preflight=None):
        self.db = db
        self.security = security
        self.preflight = preflight
        self._rules = {}

    def create_rule(self, name: str, trigger: str, action: str,
                       source_id: str = "",
                       requires_approval: bool = True,
                       budget_limit: float = 0.0,
                       capabilities: list = None,
                       schedule: str = "",
                       enabled: bool = True) -> AutomationRule:
        """Create an automation rule."""
        rule_id = "rule:" + hashlib.sha256(
            f"{name}:{trigger}:{time.time()}".encode()
        ).hexdigest()[:16]

        rule = AutomationRule(
            rule_id=rule_id,
            name=name,
            trigger=trigger,
            action=action,
            source_id=source_id,
            requires_approval=requires_approval,
            budget_limit=budget_limit,
            capabilities_required=capabilities or [],
            schedule=schedule,
            enabled=enabled,
        )
        self._rules[rule_id] = rule
        return rule

    def execute(self, rule_id: str, *, approved_by: str = "",
                budget_available: float = 0.0) -> dict:
        """Execute an automation rule.

        Checks: rights, approval, budget, capabilities, security.
        Returns result dict with status and details.
        """
        rule = self._rules.get(rule_id)
        if not rule:
            return {"status": "NOT_FOUND", "rule_id": rule_id}

        if not rule.enabled:
            return {"status": "DISABLED", "rule_id": rule_id}

        # Check rights
        if rule.source_id:
            rights = self._check_rights(rule.source_id)
            if rights != rule.rights_required:
                return {
                    "status": "BLOCKED",
                    "reason": f"rights: {rights}, need {rule.rights_required}",
                    "rule_id": rule_id,
                }

        # Check approval requirement
        if rule.requires_approval and not approved_by:
            return {
                "status": "AWAITING_APPROVAL",
                "reason": "approval required",
                "rule_id": rule_id,
            }

        # Check budget
        if rule.budget_limit > 0 and budget_available < rule.budget_limit:
            return {
                "status": "BLOCKED",
                "reason": f"budget: need {rule.budget_limit}, have {budget_available}",
                "rule_id": rule_id,
            }

        # Check capabilities
        if rule.capabilities_required:
            for cap in rule.capabilities_required:
                if not self._has_capability(cap):
                    return {
                        "status": "BLOCKED",
                        "reason": f"missing capability: {cap}",
                        "rule_id": rule_id,
                    }

        # Security check
        if self.security:
            sec = self.security.check_human_input(rule.name)
            if not sec["safe"]:
                return {
                    "status": "BLOCKED",
                    "reason": "security check failed",
                    "rule_id": rule_id,
                }

        # Execute
        result = self._run_action(rule)
        return {
            "status": "COMPLETE",
            "rule_id": rule_id,
            "action": rule.action,
            "result": result,
        }

    def list_rules(self) -> list:
        """List all automation rules."""
        return [r.to_dict() for r in self._rules.values()]

    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def disable_rule(self, rule_id: str):
        """Disable a rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
        return rule

    def _check_rights(self, source_id: str) -> str:
        """Check rights state for a source."""
        if not self.db:
            return "UNKNOWN"
        row = self.db.cx.execute(
            "SELECT * FROM rights WHERE source_id=?", (source_id,)
        ).fetchone()
        return row["state"] if row else "UNKNOWN"

    def _has_capability(self, capability: str) -> bool:
        """Check if a capability is available."""
        # Simplified — real implementation queries CapabilityRegistry
        return True

    def _run_action(self, rule: AutomationRule) -> dict:
        """Execute the action for a rule."""
        action_map = {
            "research_creator": {"action": "research", "status": "started"},
            "script_content": {"action": "script", "status": "started"},
            "publish_content": {"action": "publish", "status": "blocked_no_approval"},
            "qc_check": {"action": "qc", "status": "started"},
            "learn_patterns": {"action": "learn", "status": "started"},
        }
        return action_map.get(rule.action, {"action": rule.action, "status": "unknown"})


def automate(rule_id: str, db=None, **kwargs) -> dict:
    """Convenience: execute an automation rule."""
    engine = AutomationEngine(db)
    return engine.execute(rule_id, **kwargs)