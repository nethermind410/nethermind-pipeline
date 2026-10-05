import json

from clipping_farm.db import DB


def test_put_and_get_artifact_round_trip(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    row, created = db.put_artifact(
        "test-cache-key",
        "metadata",
        "cache://test-cache-key",
        "abc123",
        {"source_id": "test-source", "version": 1},
    )

    assert created is False
    assert row["cache_key"] == "test-cache-key"
    assert row["kind"] == "metadata"
    assert row["path"] == "cache://test-cache-key"
    assert row["content_hash"] == "abc123"

    fetched = db.get_artifact("test-cache-key")

    assert fetched is not None
    assert fetched["cache_key"] == "test-cache-key"
    assert fetched["metadata"] == json.dumps(
        {"source_id": "test-source", "version": 1}
    )


def test_put_artifact_is_idempotent(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    first, created_first = db.put_artifact(
        "same-key",
        "metadata",
        "cache://same-key",
        "hash-one",
        {"version": 1},
    )

    second, created_second = db.put_artifact(
        "same-key",
        "different-kind",
        "different-path",
        "hash-two",
        {"version": 2},
    )

    assert created_first is False
    assert created_second is True
    assert second["id"] == first["id"]
    assert second["kind"] == "metadata"
    assert second["path"] == "cache://same-key"
    assert second["content_hash"] == "hash-one"


def test_get_missing_artifact_returns_none(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    assert db.get_artifact("does-not-exist") is None


def test_verify_virtual_artifact(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    db.put_artifact(
        "virtual-key",
        "provider_result",
        "cache://virtual-key",
        "abc123",
        {},
    )

    result = db.verify_artifact("virtual-key")

    assert result["exists"] is True
    assert result["valid"] is True
    assert result["virtual"] is True


def test_verify_file_artifact(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    artifact = tmp_path / "artifact.txt"
    artifact.write_text("hello artifact")

    import hashlib
    expected = hashlib.sha256(b"hello artifact").hexdigest()

    db.put_artifact(
        "file-key",
        "text",
        str(artifact),
        expected,
        {},
    )

    result = db.verify_artifact("file-key")

    assert result["exists"] is True
    assert result["valid"] is True
    assert result["virtual"] is False


def test_verify_detects_changed_file(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    artifact = tmp_path / "artifact.txt"
    artifact.write_text("original")

    import hashlib
    expected = hashlib.sha256(b"original").hexdigest()

    db.put_artifact(
        "changed-key",
        "text",
        str(artifact),
        expected,
        {},
    )

    artifact.write_text("changed")

    result = db.verify_artifact("changed-key")

    assert result["exists"] is True
    assert result["valid"] is False
