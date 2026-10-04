import hashlib
import json

from clipping_farm.agent_handlers import LocalHandlers
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


def test_qc_artifact_gate_passes_for_intact_clip(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"valid clip bytes")

    content_hash = sha256(clip)

    db.put_artifact(
        cache_key="clip:test:1",
        kind="video_clip",
        path=str(clip),
        content_hash=content_hash,
        metadata={"source_id": "test-source", "clip_index": 1},
    )

    handlers = LocalHandlers(db)

    job = {
        "payload": {
            "source_id": "test-source",
        }
    }

    dependency = {
        "clips": [
            {
                "start": 0.0,
                "end": 8.0,
                "text": "This is a complete test sentence.",
                "scores": {"standalone": 0.9},
                "decision": "ACCEPT",
                "path": str(clip),
                "artifact_cache_key": "clip:test:1",
                "artifact_hash": content_hash,
            }
        ]
    }

    handlers._deps = lambda _: [dependency]

    result = handlers.qc(job)

    item = result["qc"][0]

    assert item["artifact_verification"]["valid"] is True
    assert item["artifact_verification"]["verification_target"] == "file"
    assert item["qc"]["visual"] == "PASS"


def test_qc_artifact_gate_fails_for_tampered_clip(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"original clip bytes")

    content_hash = sha256(clip)

    db.put_artifact(
        cache_key="clip:test:tampered",
        kind="video_clip",
        path=str(clip),
        content_hash=content_hash,
        metadata={"source_id": "test-source", "clip_index": 1},
    )

    clip.write_bytes(b"TAMPERED CLIP")

    handlers = LocalHandlers(db)

    job = {
        "payload": {
            "source_id": "test-source",
        }
    }

    dependency = {
        "clips": [
            {
                "start": 0.0,
                "end": 8.0,
                "text": "This is a complete test sentence.",
                "scores": {"standalone": 0.9},
                "decision": "ACCEPT",
                "path": str(clip),
                "artifact_cache_key": "clip:test:tampered",
                "artifact_hash": content_hash,
            }
        ]
    }

    handlers._deps = lambda _: [dependency]

    result = handlers.qc(job)

    item = result["qc"][0]

    assert item["artifact_verification"]["valid"] is False
    assert item["artifact_verification"]["expected_hash"] == content_hash
    assert item["artifact_verification"]["actual_hash"] != content_hash
    assert item["qc"]["visual"] == "FAIL"
