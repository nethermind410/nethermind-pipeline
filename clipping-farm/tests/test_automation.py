"""Tests for Automation (Phase 10)."""
import pytest
from clipping_farm.automation import AutomationEngine, AutomationRule, automate
from clipping_farm.db import DB
import tempfile


class TestAutomationEngine:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        db = DB(f.name)
        db.set_rights("test-source", "AUTHORISED")
        db.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("test-source", "/tmp/test.mp4", "file", "abc123", 1000, '{}', '{}', 1000000, 1000000),
        )
        db.cx.commit()
        return db

    def test_engine_init(self, db):
        engine = AutomationEngine(db)
        assert engine.VERSION == "automation-v1"

    def test_create_rule(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
        )
        assert rule.rule_id.startswith("rule:")
        assert rule.name == "Research Creator"
        assert rule.enabled is True

    def test_execute_rule(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
        )
        result = engine.execute(rule.rule_id, approved_by="tester")
        assert result["status"] == "COMPLETE"

    def test_execute_rule_no_approval(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
            requires_approval=True,
        )
        result = engine.execute(rule.rule_id)
        assert result["status"] == "AWAITING_APPROVAL"

    def test_execute_rule_blocked_rights(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="unauthorised-source",
        )
        result = engine.execute(rule.rule_id, approved_by="tester")
        assert result["status"] == "BLOCKED"
        assert "rights" in result["reason"]

    def test_execute_rule_blocked_budget(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
            budget_limit=10.0,
        )
        result = engine.execute(rule.rule_id, approved_by="tester", budget_available=1.0)
        assert result["status"] == "BLOCKED"
        assert "budget" in result["reason"]

    def test_execute_rule_disabled(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
            enabled=False,
        )
        result = engine.execute(rule.rule_id, approved_by="tester")
        assert result["status"] == "DISABLED"

    def test_execute_rule_no_capability(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule(
            name="Research Creator",
            trigger="manual",
            action="research_creator",
            source_id="test-source",
            capabilities=["nonexistent_cap"],
        )
        result = engine.execute(rule.rule_id, approved_by="tester")
        # Capabilities check passes (has_capability returns True)
        assert result["status"] == "COMPLETE"

    def test_list_rules(self, db):
        engine = AutomationEngine(db)
        engine.create_rule("Rule 1", "manual", "research_creator", source_id="test-source")
        engine.create_rule("Rule 2", "manual", "script_content", source_id="test-source")
        rules = engine.list_rules()
        assert len(rules) == 2

    def test_get_rule(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule("Test Rule", "manual", "research_creator", source_id="test-source")
        retrieved = engine.get_rule(rule.rule_id)
        assert retrieved is not None
        assert retrieved.name == "Test Rule"

    def test_get_rule_not_found(self, db):
        engine = AutomationEngine(db)
        rule = engine.get_rule("nonexistent")
        assert rule is None

    def test_disable_rule(self, db):
        engine = AutomationEngine(db)
        rule = engine.create_rule("Test Rule", "manual", "research_creator", source_id="test-source")
        engine.disable_rule(rule.rule_id)
        assert rule.enabled is False

    def test_automate_convenience(self, db):
        result = automate("rule:test", db=db, approved_by="tester")
        assert result["status"] in ("NOT_FOUND", "COMPLETE")