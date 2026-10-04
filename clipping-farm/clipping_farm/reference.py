"""Reference-video ingestion via yt-dlp.

This module retrieves reference media/metadata only.
Retrieval does NOT establish publishing rights.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json

import yt_dlp

from .library import AssetLibrary


class ReferenceError(RuntimeError):
    """Base error for reference ingestion."""


class ReferenceInspector:
    """Inspect a URL without downloading media."""

    def inspect(self, url: str) -> dict:
        if not url:
            raise ValueError("url is required")

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise ReferenceError(
                f"Unable to inspect reference URL: {exc}"
            ) from exc

        return self._normalise(info, url)

    @staticmethod
    def _normalise(info: dict, url: str) -> dict:
        return {
            "source_url": url,
            "extractor": info.get("extractor"),
            "extractor_key": info.get("extractor_key"),
            "id": info.get("id"),
            "title": info.get("title"),
            "description": (info.get("description") or "")[:1000],
            "uploader": info.get("uploader"),
            "uploader_id": info.get("uploader_id"),
            "channel": info.get("channel"),
            "channel_id": info.get("channel_id"),
            "duration": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "timestamp": info.get("timestamp"),
            "webpage_url": info.get("webpage_url") or url,
            "thumbnail": info.get("thumbnail"),
            "is_live": info.get("is_live"),
            "availability": info.get("availability"),
        }


    def persist(self, db, metadata: dict) -> dict:
        """Persist inspected reference metadata without granting rights."""
        from time import time

        source_id = (
            f"reference:{metadata.get('extractor_key') or metadata.get('extractor')}:"
            f"{metadata.get('id') or metadata.get('source_url')}"
        )

        now = db.now() if hasattr(db, "now") else time()

        provenance = {
            "method": "yt-dlp",
            "source_url": metadata["source_url"],
            "rights_established": False,
            "rights_state": "UNKNOWN",
        }

        db.cx.execute(
            """
            INSERT INTO sources(
                source_id, location, kind, sha256, size_bytes,
                metadata, provenance, first_seen_at, last_seen_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                location=excluded.location,
                kind=excluded.kind,
                metadata=excluded.metadata,
                provenance=excluded.provenance,
                last_seen_at=excluded.last_seen_at
            """,
            (
                source_id,
                metadata["source_url"],
                "reference_url",
                None,
                None,
                json.dumps(metadata, ensure_ascii=False),
                json.dumps(provenance, ensure_ascii=False),
                now,
                now,
            ),
        )

        # The rights table is authoritative. Inspection never establishes
        # rights, but it must not erase an existing explicit authorisation.
        existing_rights = db.rights(source_id)
        if not existing_rights or existing_rights["state"] != "AUTHORISED":
            db.set_rights(
                source_id,
                "UNKNOWN",
                {
                    "basis": "reference URL inspected via yt-dlp",
                    "source_url": metadata["source_url"],
                    "rights_established": False,
                },
            )

        return {
            "source_id": source_id,
            "kind": "reference_url",
            "location": metadata["source_url"],
            "rights_state": "UNKNOWN",
            "metadata": metadata,
            "provenance": provenance,
        }


class ReferenceDownloader:
    """Download a reference copy after explicit caller authorisation."""

    def download(
        self,
        url: str,
        output_dir: str | Path,
        *,
        authorised: bool = False,
    ) -> dict:
        if not authorised:
            raise PermissionError(
                "Reference download requires explicit authorisation"
            )

        if not url:
            raise ValueError("url is required")

        destination = Path(output_dir).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)

        output_template = str(destination / "%(id)s.%(ext)s")

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": output_template,
            "restrictfilenames": True,
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                path = Path(ydl.prepare_filename(info))
        except Exception as exc:
            raise ReferenceError(
                f"Unable to download reference URL: {exc}"
            ) from exc

        if not path.is_file():
            raise ReferenceError(
                f"yt-dlp completed but expected file was not found: {path}"
            )

        sha256 = self._sha256(path)

        return {
            "source_url": url,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256,
            "metadata": ReferenceInspector._normalise(info, url),
            "provenance": {
                "method": "yt-dlp",
                "retrieved_file": str(path),
                "sha256": sha256,
                "rights_established": False,
            },
        }

    def acquire(self, db, url: str, *, purpose="reference", asset_id=None):
        """Inspect and acquire a URL into the Asset Library after DB authorisation."""
        inspected = ReferenceInspector().inspect(url)
        persisted = ReferenceInspector().persist(db, inspected)
        source_id = persisted["source_id"]
        rights = db.rights(source_id)
        if not rights or rights["state"] != "AUTHORISED":
            raise PermissionError(
                f"URL {url} is not AUTHORISED; inspect first, then explicitly authorise {source_id}"
            )

        aid = asset_id
        existing = db.cx.execute(
            "SELECT asset_id FROM assets WHERE source_url=? LIMIT 1", (url,)
        ).fetchone()
        if existing:
            aid = existing["asset_id"]
        else:
            asset, _ = db.create_asset(
                asset_id=aid,
                source_id=source_id,
                source_url=url,
                source_type="url",
                purpose=purpose,
                original_filename=None,
                title=inspected.get("title"),
                creator=inspected.get("uploader") or inspected.get("channel"),
                media_type="video",
                duration=inspected.get("duration"),
                metadata=inspected,
                provenance={
                    "method": "yt-dlp",
                    "source_url": url,
                    "rights_state_at_acquisition": rights["state"],
                },
            )
            aid=asset["asset_id"]

        library=AssetLibrary()
        paths=library.ensure(aid)
        result=self.download(url, paths["original"], authorised=True)
        downloaded=Path(result["path"])
        # yt-dlp may choose a container extension different from the URL.
        db.update_asset(
            aid,
            original_filename=downloaded.name,
            local_path=str(downloaded),
            sha256=result["sha256"],
            duration=inspected.get("duration"),
            title=inspected.get("title"),
            creator=inspected.get("uploader") or inspected.get("channel"),
            rights_state=rights["state"],
            acquisition_state="ACQUIRED",
            metadata=inspected,
            provenance={
                **persisted["provenance"],
                **result["provenance"],
                "rights_state_at_acquisition": rights["state"],
            },
        )
        asset=db.get_asset(aid)
        library.manifest(asset)
        return {"asset": asset, "download": result}

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
