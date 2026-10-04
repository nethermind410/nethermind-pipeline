"""Source ingestion and provenance.

Ingestion records where media came from and what was actually retrieved.
Ingestion NEVER grants publishing rights.
"""

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from .library import AssetLibrary


@dataclass
class Source:
    source_id: str
    location: str
    kind: str = "file"
    metadata: dict | None = None


class SourceIngestor:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _source_metadata(path: Path) -> dict:
        stat = path.stat()
        mime, _ = mimetypes.guess_type(path.name)
        return {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "mime_type": mime or "application/octet-stream",
            "bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
        }

    def ingest_file(self, source: Source):
        rights = self.db.rights(source.source_id)
        if not rights or rights["state"] != "AUTHORISED":
            raise PermissionError(
                f"Source {source.source_id} is not AUTHORISED"
            )

        path = Path(source.location).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(path)

        sha256 = self._sha256(path)
        metadata = self._source_metadata(path)
        if source.metadata:
            metadata.update(source.metadata)

        now = self.db.now()

        # Persistent provenance registry.
        self.db.cx.execute(
            """
            INSERT INTO sources(
                source_id, location, kind, sha256, size_bytes,
                metadata, provenance, first_seen_at, last_seen_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                location=excluded.location,
                kind=excluded.kind,
                sha256=excluded.sha256,
                size_bytes=excluded.size_bytes,
                metadata=excluded.metadata,
                provenance=excluded.provenance,
                last_seen_at=excluded.last_seen_at
            """,
            (
                source.source_id,
                str(path),
                source.kind,
                sha256,
                path.stat().st_size,
                json.dumps(metadata),
                json.dumps(
                    {
                        "ingestion": "local_file",
                        "location": str(path),
                        "sha256": sha256,
                    }
                ),
                now,
                now,
            ),
        )

        # Detect the same physical media under another source ID.
        duplicate = self.db.cx.execute(
            """
            SELECT source_id
            FROM sources
            WHERE sha256=? AND source_id!=?
            ORDER BY first_seen_at
            LIMIT 1
            """,
            (sha256, source.source_id),
        ).fetchone()

        library = AssetLibrary()
        # Register every ingested file as an Asset while retaining the existing
        # source record and original path for backwards compatibility.
        existing = self.db.cx.execute(
            "SELECT asset_id FROM assets WHERE source_id=? ORDER BY created_at LIMIT 1",
            (source.source_id,),
        ).fetchone()
        asset_id = existing["asset_id"] if existing else None
        if not asset_id:
            asset, _ = self.db.create_asset(
                asset_id=None,
                source_id=source.source_id,
                source_type="local_file",
                purpose=source.metadata.get("purpose", "production_source") if source.metadata else "production_source",
                original_filename=path.name,
                title=metadata.get("title") or path.stem,
                media_type=metadata.get("mime_type"),
                local_path=str(path),
                sha256=sha256,
                metadata=metadata,
                provenance={
                    "method": "local_file",
                    "location": str(path),
                    "sha256": sha256,
                    "rights_state_at_ingestion": rights["state"],
                },
                # Each HUD upload/source gets its own Asset identity.
                # Physical-media duplication is tracked separately through
                # duplicate_of rather than collapsing the new source into
                # an existing Asset.
                dedupe=False,
            )
            asset_id=asset["asset_id"]
        else:
            asset=self.db.get_asset(asset_id)
        library.ensure(asset_id)
        stored_path = library.copy_original(asset_id, path)
        self.db.update_asset(
            asset_id,
            local_path=str(stored_path),
            rights_state=rights["state"],
            acquisition_state="ACQUIRED",
            metadata=metadata,
            provenance={
                **asset.get("provenance", {}),
                "library_original": str(stored_path),
            },
        )
        asset=self.db.get_asset(asset_id)
        library.manifest(asset)

        return {
            "asset_id": asset_id,
            "source_id": source.source_id,
            "path": str(path),
            "library_path": str(stored_path),
            "sha256": sha256,
            "bytes": path.stat().st_size,
            "kind": source.kind,
            "metadata": metadata,
            "duplicate_of": duplicate["source_id"] if duplicate else None,
        }

    def get_source(self, source_id: str):
        row = self.db.cx.execute(
            "SELECT * FROM sources WHERE source_id=?",
            (source_id,),
        ).fetchone()
        if not row:
            return None

        result = dict(row)
        result["metadata"] = json.loads(result["metadata"] or "{}")
        result["provenance"] = json.loads(result["provenance"] or "{}")
        return result
