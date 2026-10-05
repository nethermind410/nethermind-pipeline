"""Deterministic local Asset Library."""

from __future__ import annotations
from pathlib import Path
import hashlib, json, mimetypes, shutil
from datetime import datetime, timezone

DEFAULT_ROOT = "clipping_farm_library"

SUBDIRS = (
    "original", "metadata", "transcript", "analysis", "scenes",
    "audio", "clips", "qc", "references", "dna", "manifests",
)

class AssetLibrary:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = Path(root).expanduser().resolve()

    def asset_dir(self, asset_id):
        return self.root / "assets" / asset_id

    def paths(self, asset_id):
        base=self.asset_dir(asset_id)
        return {name: base/name for name in SUBDIRS} | {"root":base}

    def ensure(self, asset_id):
        paths=self.paths(asset_id)
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return paths

    @staticmethod
    def sha256(path):
        digest=hashlib.sha256()
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024*1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def copy_original(self, asset_id, source_path):
        paths=self.ensure(asset_id)
        src=Path(source_path).expanduser().resolve()
        if not src.is_file(): raise FileNotFoundError(src)
        dest=paths["original"]/src.name
        if src != dest:
            shutil.copy2(src,dest)
        return dest

    def manifest(self, asset, extra=None):
        paths=self.ensure(asset["asset_id"])
        payload={
            "asset_id":asset["asset_id"],
            "source_id":asset.get("source_id"),
            "source_url":asset.get("source_url"),
            "source_type":asset.get("source_type"),
            "purpose":asset.get("purpose"),
            "rights_state":asset.get("rights_state"),
            "acquisition_state":asset.get("acquisition_state"),
            "original_filename":asset.get("original_filename"),
            "title":asset.get("title"),
            "creator":asset.get("creator"),
            "media_type":asset.get("media_type"),
            "local_path":asset.get("local_path"),
            "sha256":asset.get("sha256"),
            "duration":asset.get("duration"),
            "metadata":asset.get("metadata",{}),
            "provenance":asset.get("provenance",{}),
            "paths":{k:str(v) for k,v in paths.items()},
            "updated_at":datetime.now(timezone.utc).isoformat(),
        }
        if extra: payload.update(extra)
        target=paths["manifests"]/"asset_manifest.json"
        target.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        return target
