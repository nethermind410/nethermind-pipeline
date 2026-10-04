"""Tests for Preflight Gate."""
import pytest
import tempfile
from clipping_farm.preflight import PreflightGate, PreflightError, preflight_passed
from clipping_farm.db import DB


class TestPreflightGate:
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

    @pytest.fixture
    def gate(self, db):
        return PreflightGate(db=db)

    def test_check_passes_with_source(self, gate):
        ok, checks = gate.check("test-source")
        assert ok is True
        assert checks["source_exists"]["ok"] is True

    def test_check_fails_missing_source(self, db):
        gate = PreflightGate(db=db)
        with pytest.raises(PreflightError) as exc:
            gate.check("nonexistent-source")
        assert "not found" in str(exc.value)

    def test_check_source_exists(self, gate):
        result = gate._check_source("test-source")
        assert result["ok"] is True

    def test_check_source_missing(self, gate):
        result = gate._check_source("nonexistent")
        assert result["ok"] is False
        assert "not found" in result["reason"]

    def test_check_asset_exists(self, db):
        gate = PreflightGate(db=db)
        # test-source was inserted as a source, not an asset
        result = gate._check_asset("nonexistent-asset")
        assert result["ok"] is False
        assert "not found" in result["reason"]

    def test_check_rights_ok(self, gate):
        result = gate._check_rights("test-source", "AUTHORISED")
        assert result["ok"] is True

    def test_check_rights_wrong_state(self, gate):
        result = gate._check_rights("test-source", "PENDING")
        assert result["ok"] is False

    def test_check_rights_no_record(self, gate):
        result = gate._check_rights("no-rights-source")
        assert result["ok"] is False

    def test_check_capabilities_missing_registry(self, db):
        gate = PreflightGate(db=db)
        result = gate._check_capabilities(["transcription"])
        assert result["ok"] is True  # skipped without registry

    def test_check_ffmpeg(self, gate):
        result = gate._check_ffmpeg()
        assert "ok" in result

    def test_check_storage(self, gate):
        result = gate._check_storage()
        assert "ok" in result
        assert "free" in result.get("reason", "").lower() or result["ok"] is False

    def test_check_budget_sufficient(self, gate):
        result = gate._check_budget(1.0, 0.5)
        assert result["ok"] is True

    def test_check_budget_insufficient_quality(self, gate):
        result = gate._check_budget(0.0, 0.8)
        assert result["ok"] is False

    def test_check_budget_negative(self, gate):
        result = gate._check_budget(-1.0, 0.5)
        assert result["ok"] is False

    def test_check_output(self, gate):
        result = gate._check_output()
        assert result["ok"] is True

    def test_preflight_passed_true(self, db):
        ok, reason = preflight_passed("test-source", db=db)
        assert ok is True

    def test_preflight_passed_false(self, db):
        ok, reason = preflight_passed("nonexistent", db=db)
        assert ok is False

    def test_check_source_rights(self, db):
        gate = PreflightGate(db=db)
        ok, checks = gate.check_source_rights("test-source")
        assert ok is True

    def test_version(self, gate):
        assert gate.VERSION == "preflight-v1"

    def test_min_storage_constants(self):
        assert PreflightGate.MIN_STORAGE_GB == 1.0
        assert PreflightGate.MIN_STORAGE_PERCENT == 5.0

    def test_check_no_db_skips_source(self):
        gate = PreflightGate(db=None)
        result = gate._check_source("anything")
        assert result["ok"] is True
        assert "skipped" in result["reason"]

    def test_check_no_db_skips_rights(self):
        gate = PreflightGate(db=None)
        result = gate._check_rights("anything")
        assert result["ok"] is True
        assert "skipped" in result["reason"]

    def test_check_no_db_skips_providers(self):
        gate = PreflightGate(db=None)
        result = gate._check_providers()
        assert result["ok"] is True
        assert "skipped" in result["reason"]