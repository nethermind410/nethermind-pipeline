"""Tests for Content Lab Integration (Phase 8)."""
import pytest
from clipping_farm.content_lab import ContentLab
from clipping_farm.db import DB
import tempfile


class TestContentLab:
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

    def test_lab_init(self, db):
        lab = ContentLab(db)
        assert lab.VERSION == "content-lab-v1"

    def test_create_production(self, db):
        lab = ContentLab(db)
        prod = lab.create_production(
            asset_id="ASSET-000001",
            source_id="test-source",
            title="Test Production",
        )
        assert prod is not None
        assert prod["production_id"].startswith("prod:")
        assert prod["status"] == "PENDING"
        assert prod["title"] == "Test Production"

    def test_create_production_with_metadata(self, db):
        lab = ContentLab(db)
        metadata = {"key": "value", "nested": {"a": 1}}
        prod = lab.create_production(
            asset_id="ASSET-000002",
            source_id="test-source",
            metadata=metadata,
        )
        assert prod["content_metadata"]["key"] == "value"
        assert prod["content_metadata"]["nested"]["a"] == 1

    def test_get_production(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000003",
            source_id="test-source",
            title="Get Test",
        )
        retrieved = lab.get_production(created["production_id"])
        assert retrieved is not None
        assert retrieved["production_id"] == created["production_id"]
        assert retrieved["title"] == "Get Test"

    def test_get_production_not_found(self, db):
        lab = ContentLab(db)
        result = lab.get_production("nonexistent")
        assert result is None

    def test_update_production(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000004",
            source_id="test-source",
        )
        updated = lab.update_production(
            created["production_id"],
            title="Updated Title",
        )
        assert updated["title"] == "Updated Title"
        assert updated["status"] == "PENDING"

    def test_update_production_invalid_field(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000005",
            source_id="test-source",
        )
        with pytest.raises(ValueError):
            lab.update_production(created["production_id"], invalid_field="x")

    def test_link_approval(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000006",
            source_id="test-source",
        )
        linked = lab.link_approval(created["production_id"], "approval:abc123")
        assert linked["approval_id"] == "approval:abc123"

    def test_link_qc(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000007",
            source_id="test-source",
        )
        qc = {"score": 0.95, "passed": True}
        linked = lab.link_qc(created["production_id"], qc)
        assert linked["qc_result"]["score"] == 0.95

    def test_set_status(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000008",
            source_id="test-source",
        )
        updated = lab.set_status(created["production_id"], "QC_PASS")
        assert updated["status"] == "QC_PASS"

    def test_set_status_invalid(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000009",
            source_id="test-source",
        )
        with pytest.raises(ValueError):
            lab.set_status(created["production_id"], "INVALID_STATUS")

    def test_get_asset_productions(self, db):
        lab = ContentLab(db)
        lab.create_production(asset_id="ASSET-000010", source_id="test-source")
        lab.create_production(asset_id="ASSET-000010", source_id="test-source")
        productions = lab.get_asset_productions("ASSET-000010")
        assert len(productions) == 2

    def test_get_source_productions(self, db):
        lab = ContentLab(db)
        lab.create_production(asset_id="ASSET-000011", source_id="test-source")
        productions = lab.get_source_productions("test-source")
        assert len(productions) >= 1

    def test_list_productions(self, db):
        lab = ContentLab(db)
        lab.create_production(asset_id="ASSET-000012", source_id="test-source")
        productions = lab.list_productions()
        assert len(productions) >= 1

    def test_list_productions_filtered(self, db):
        lab = ContentLab(db)
        lab.create_production(asset_id="ASSET-000013", source_id="test-source")
        pending = lab.list_productions(status="PENDING")
        assert isinstance(pending, list)

    def test_snapshot(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000014",
            source_id="test-source",
            title="Snapshot Test",
        )
        snap = lab.snapshot(created["production_id"])
        assert snap is not None
        assert snap["production"]["title"] == "Snapshot Test"
        assert snap["asset"] is None  # asset not in DB
        assert isinstance(snap["jobs"], list)
        assert isinstance(snap["artifacts"], list)

    def test_snapshot_not_found(self, db):
        lab = ContentLab(db)
        snap = lab.snapshot("nonexistent")
        assert snap is None

    def test_version(self, db):
        lab = ContentLab(db)
        assert lab.VERSION == "content-lab-v1"

    def test_create_production_with_provenance(self, db):
        lab = ContentLab(db)
        provenance = {"source": "trending", "agent": "trending_agent"}
        created = lab.create_production(
            asset_id="ASSET-000015",
            source_id="test-source",
            provenance=provenance,
        )
        assert created["provenance"]["source"] == "trending"

    def test_update_production_rights_state(self, db):
        lab = ContentLab(db)
        created = lab.create_production(
            asset_id="ASSET-000016",
            source_id="test-source",
        )
        updated = lab.update_production(
            created["production_id"], rights_state="AUTHORISED"
        )
        assert updated["rights_state"] == "AUTHORISED"