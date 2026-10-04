"""Tests for Hermes Adapter (Phase 5)."""
import pytest
from clipping_farm.hermes_adapter import HermesAdapter
from clipping_farm.db import DB
import tempfile


class TestHermesAdapter:
    @pytest.fixture
    def db(self):
        f = tempfile.NamedTemporaryFile(suffix=".db")
        database = DB(f.name)
        database.set_rights("test-source", "AUTHORISED", {"basis": "fixture"})
        database.cx.execute(
            "INSERT INTO sources(source_id, location, kind, sha256, size_bytes, metadata, provenance, first_seen_at, last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)",
            ("test-source", "/tmp/test.mp4", "file", "abc123", 1000, '{"title": "Test"}', '{"ingestion":"local"}', 1000000, 1000000),
        )
        database.cx.commit()
        return database

    def test_adapter_init(self, db):
        adapter = HermesAdapter(db)
        assert adapter.db is db
        assert adapter.VERSION == "hermes-adapter-v1"

    def test_inspect_capabilities(self, db):
        from clipping_farm.capability_registry import CapabilityRegistry
        registry = CapabilityRegistry(db=db)
        adapter = HermesAdapter(db, registry=registry)
        caps = adapter.inspect_capabilities()
        assert "capabilities" in caps
        assert "summary" in caps

    def test_plan_with_preflight(self, db):
        from clipping_farm.preflight import PreflightGate
        gate = PreflightGate(db=db)
        adapter = HermesAdapter(db, preflight=gate)
        plan = adapter.plan("test-source", title="Test")
        assert plan["blocked"] is False
        assert plan["plan"]["source_id"] == "test-source"

    def test_plan_blocked_no_source(self, db):
        from clipping_farm.preflight import PreflightGate
        gate = PreflightGate(db=db)
        adapter = HermesAdapter(db, preflight=gate)
        with pytest.raises(Exception):
            adapter.plan("nonexistent-source")

    def test_submit(self, db):
        adapter = HermesAdapter(db)
        result = adapter.submit("test-source", title="Test")
        assert result["status"] == "APPROVING_SCRIPT"
        assert result["pipeline_id"] is not None

    def test_status(self, db):
        adapter = HermesAdapter(db)
        submitted = adapter.submit("test-source", title="Test")
        status = adapter.status(submitted["pipeline_id"])
        assert status["pipeline_id"] == submitted["pipeline_id"]
        assert status["status"] == "APPROVING_SCRIPT"

    def test_status_not_found(self, db):
        adapter = HermesAdapter(db)
        status = adapter.status("nonexistent-pipeline")
        assert status["status"] == "NOT_FOUND"

    def test_result(self, db):
        adapter = HermesAdapter(db)
        submitted = adapter.submit("test-source", title="Test")
        result = adapter.result(submitted["pipeline_id"])
        assert result["pipeline_id"] == submitted["pipeline_id"]

    def test_result_not_found(self, db):
        adapter = HermesAdapter(db)
        result = adapter.result("nonexistent-pipeline")
        assert result["status"] == "NOT_FOUND"

    def test_cancel(self, db):
        adapter = HermesAdapter(db)
        submitted = adapter.submit("test-source", title="Test")
        cancelled = adapter.cancel(submitted["pipeline_id"])
        assert cancelled["status"] == "CANCELLED"

    def test_cancel_not_found(self, db):
        adapter = HermesAdapter(db)
        # pipelines table created by Orchestrator
        from clipping_farm.agents.orchestrator import Orchestrator
        orch = Orchestrator(db)
        result = adapter.cancel("nonexistent-pipeline")
        assert result["status"] == "NOT_FOUND"

    def test_cleanup(self, db):
        adapter = HermesAdapter(db)
        submitted = adapter.submit("test-source", title="Test")
        cleaned = adapter.cleanup(submitted["pipeline_id"])
        assert cleaned["cleaned_up"] is True

    def test_run_full_cycle(self, db):
        adapter = HermesAdapter(db)
        result = adapter.run_full_cycle("test-source", title="Test")
        assert result["cycle"] == "complete"
        assert "capabilities" in result
        assert "plan" in result
        assert "submitted" in result
        assert "final_status" in result

    def test_run_full_cycle_blocked(self, db):
        from clipping_farm.preflight import PreflightGate
        gate = PreflightGate(db=db)
        adapter = HermesAdapter(db, preflight=gate)
        result = adapter.run_full_cycle("nonexistent-source")
        assert result["cycle"] == "blocked"

    def test_plan_no_preflight(self, db):
        adapter = HermesAdapter(db)
        plan = adapter.plan("test-source")
        assert plan["blocked"] is False