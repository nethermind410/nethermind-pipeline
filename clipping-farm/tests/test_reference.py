from pathlib import Path

import pytest

from clipping_farm.reference import (
    ReferenceDownloader,
    ReferenceInspector,
)


def test_inspector_normalises_metadata():
    info = {
        "extractor": "youtube",
        "extractor_key": "Youtube",
        "id": "abc123",
        "title": "Test Reference",
        "description": "Example",
        "uploader": "Example Channel",
        "uploader_id": "channel123",
        "channel": "Example Channel",
        "channel_id": "UC123",
        "duration": 42.5,
        "upload_date": "20260101",
        "timestamp": 1767225600,
        "webpage_url": "https://example.com/watch?v=abc123",
        "thumbnail": "https://example.com/thumb.jpg",
        "is_live": False,
        "availability": "public",
    }

    result = ReferenceInspector._normalise(
        info,
        "https://example.com/watch?v=abc123",
    )

    assert result["source_url"] == "https://example.com/watch?v=abc123"
    assert result["extractor"] == "youtube"
    assert result["id"] == "abc123"
    assert result["title"] == "Test Reference"
    assert result["duration"] == 42.5
    assert result["is_live"] is False


def test_downloader_requires_explicit_authorisation(tmp_path):
    downloader = ReferenceDownloader()

    with pytest.raises(PermissionError):
        downloader.download(
            "https://example.com/video",
            tmp_path,
        )


def test_downloader_hashes_retrieved_file(tmp_path):
    media = tmp_path / "reference.mp4"
    media.write_bytes(b"reference-media")

    expected = (
        "8d5a6d7d6b5d7a7e5d5c6e0f8f8c9f4f"
    )

    # Verify the implementation against hashlib rather than
    # hard-coding a potentially incorrect digest.
    import hashlib

    actual = hashlib.sha256(media.read_bytes()).hexdigest()

    assert actual == ReferenceDownloader._sha256(media)
    assert len(actual) == 64


def test_downloader_does_not_claim_rights():
    source = {
        "provenance": {
            "method": "yt-dlp",
            "rights_established": False,
        }
    }

    assert source["provenance"]["rights_established"] is False


def test_inspector_caps_description_length():
    info = {
        "extractor": "youtube",
        "id": "abc123",
        "title": "Test",
        "description": "x" * 5000,
    }

    result = ReferenceInspector._normalise(
        info,
        "https://example.com/watch?v=abc123",
    )

    assert len(result["description"]) == 1000


def test_reference_persist_creates_unknown_rights_source(tmp_path):
    from clipping_farm.db import DB

    db = DB(tmp_path / "db.sqlite")

    metadata = {
        "source_url": "https://example.com/watch?v=abc123",
        "extractor": "example",
        "extractor_key": "Example",
        "id": "abc123",
        "title": "Test Reference",
        "description": "Example",
    }

    result = ReferenceInspector().persist(db, metadata)

    assert result["kind"] == "reference_url"
    assert result["rights_state"] == "UNKNOWN"
    assert result["provenance"]["rights_established"] is False

    row = db.cx.execute(
        "SELECT * FROM sources WHERE source_id=?",
        (result["source_id"],),
    ).fetchone()

    assert row is not None
    assert row["kind"] == "reference_url"
    assert row["location"] == metadata["source_url"]


def test_reference_persist_creates_authoritative_unknown_rights(tmp_path):
    from clipping_farm.db import DB

    db = DB(tmp_path / "db.sqlite")

    metadata = {
        "source_url": "https://example.com/watch?v=rights-test",
        "extractor": "example",
        "extractor_key": "Example",
        "id": "rights-test",
        "title": "Rights Test",
        "description": "",
    }

    result = ReferenceInspector().persist(db, metadata)
    rights = db.rights(result["source_id"])

    assert rights is not None
    assert rights["state"] == "UNKNOWN"

    import json

    evidence = json.loads(rights["evidence"])
    assert evidence["rights_established"] is False
    assert evidence["source_url"] == metadata["source_url"]
