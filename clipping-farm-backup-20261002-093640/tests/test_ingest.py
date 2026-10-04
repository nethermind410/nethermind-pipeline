import json

import pytest

from clipping_farm.db import DB
from clipping_farm.ingest import Source, SourceIngestor


def test_ingest_requires_authorisation(tmp_path):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"test-video")

    db = DB(tmp_path / "db.sqlite")
    ingestor = SourceIngestor(db)

    with pytest.raises(PermissionError):
        ingestor.ingest_file(
            Source("source-1", str(media))
        )


def test_ingest_records_hash_and_provenance(tmp_path):
    media = tmp_path / "video.mp4"
    media.write_bytes(b"test-video")

    db = DB(tmp_path / "db.sqlite")
    db.set_rights("source-1", "AUTHORISED", {"basis": "test"})

    result = SourceIngestor(db).ingest_file(
        Source("source-1", str(media))
    )

    assert result["source_id"] == "source-1"
    assert result["bytes"] == len(b"test-video")
    assert len(result["sha256"]) == 64
    assert result["duplicate_of"] is None

    stored = SourceIngestor(db).get_source("source-1")

    assert stored["sha256"] == result["sha256"]
    assert stored["kind"] == "file"
    assert stored["metadata"]["filename"] == "video.mp4"
    assert stored["provenance"]["ingestion"] == "local_file"


def test_ingest_detects_duplicate_media(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"

    first.write_bytes(b"identical-media")
    second.write_bytes(b"identical-media")

    db = DB(tmp_path / "db.sqlite")
    db.set_rights("source-1", "AUTHORISED")
    db.set_rights("source-2", "AUTHORISED")

    ingestor = SourceIngestor(db)

    a = ingestor.ingest_file(Source("source-1", str(first)))
    b = ingestor.ingest_file(Source("source-2", str(second)))

    assert a["duplicate_of"] is None
    assert b["duplicate_of"] == "source-1"
    assert a["sha256"] == b["sha256"]
