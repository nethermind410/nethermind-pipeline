import hashlib

from clipping_farm.db import DB


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def test_file_artifact_verifies_and_detects_tampering(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    artifact = tmp_path / "clip.mp4"
    artifact.write_bytes(b"original clip bytes")

    original_hash = sha256(artifact)

    stored, created = db.put_artifact(
        cache_key="clip:test:1",
        kind="video_clip",
        path=str(artifact),
        content_hash=original_hash,
        metadata={
            "source_id": "test-source",
            "clip_index": 1,
        },
    )

    assert created is False or created is True
    assert stored["kind"] == "video_clip"

    verification = db.verify_artifact("clip:test:1")

    assert verification["exists"] is True
    assert verification["valid"] is True
    assert verification["verification_target"] == "file"
    assert verification["expected_hash"] == original_hash
    assert verification["actual_hash"] == original_hash

    artifact.write_bytes(b"tampered clip bytes")

    tampered = db.verify_artifact("clip:test:1")

    assert tampered["exists"] is True
    assert tampered["valid"] is False
    assert tampered["expected_hash"] == original_hash
    assert tampered["actual_hash"] != original_hash
