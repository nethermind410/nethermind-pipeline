"""Content referencer agent — builds reference packs from scripts.

Reads JEVs from the script writer agent, finds matching
reference material (clips, stills, comics), and builds
a reference pack for production.

The reference pack includes:
- Matching clips from the library
- Still frames
- Comic pages (if applicable)
- Provenance chain
"""
from dataclasses import dataclass, field
from typing import Optional, List
import json
import time
import hashlib


@dataclass(frozen=True)
class ReferenceItem:
    asset_id: str
    reference_type: str  # "clip", "still", "comic", "transcript"
    relevance_score: float
    source_id: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "asset_id": self.asset_id,
            "reference_type": self.reference_type,
            "relevance_score": self.relevance_score,
            "source_id": self.source_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ReferencePack:
    pack_id: str
    script_id: str
    jev_id: str
    items: list  # list of ReferenceItem dicts
    total_relevance: float
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "pack_id": self.pack_id,
            "script_id": self.script_id,
            "jev_id": self.jev_id,
            "items": [i.__dict__ if hasattr(i, "__dict__") else i for i in self.items],
            "total_relevance": self.total_relevance,
            "created_at": self.created_at,
        }


class ContentReferencerAgent:
    """Builds reference packs from script JEVs."""

    VERSION = "content-referencer-v1"

    def __init__(self, db, *, min_relevance=0.3):
        self.db = db
        self.min_relevance = min_relevance

    def build_pack(self, script_jev_id: str) -> ReferencePack:
        """Build a reference pack from a script JEV.

        Args:
            script_jev_id: The script JEV ID from the script writer.

        Returns:
            ReferencePack with matching reference items.
        """
        # Read the script JEV
        script_row = self.db.get_artifact(script_jev_id)
        if not script_row:
            raise ValueError(f"Script JEV not found: {script_jev_id}")
        try:
            script = json.loads(script_row["metadata"])["jev"]
        except (KeyError, json.JSONDecodeError):
            script = json.loads(script_row["metadata"])

        script_id = script["script_id"]
        source_id = script["source_id"]
        title = script.get("title", "")

        # Find matching references
        items = self._find_references(source_id, title)

        total_relevance = sum(i.relevance_score for i in items)

        pack_id = "pack:" + hashlib.sha256(
            f"{script_jev_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        pack = ReferencePack(
            pack_id=pack_id,
            script_id=script_id,
            jev_id=script_jev_id,
            items=items,
            total_relevance=total_relevance,
        )

        # Write the pack JEV for downstream agents
        self._write_pack_jev(pack)
        return pack

    def _find_references(self, source_id, title):
        """Find matching reference items from the library."""
        items = []

        # Query assets related to this source
        rows = self.db.cx.execute(
            "SELECT asset_id, source_id, title, purpose FROM assets WHERE source_id=? OR title LIKE ?",
            (source_id, f"%{title[:20]}%"),
        ).fetchall()

        for row in rows:
            relevance = self._score_relevance(row, title)
            if relevance >= self.min_relevance:
                items.append(ReferenceItem(
                    asset_id=row["asset_id"],
                    reference_type="clip" if row["purpose"] == "production_source" else "still",
                    relevance_score=relevance,
                    source_id=row["source_id"],
                ))

        # Also check reference assets
        ref_rows = self.db.cx.execute(
            "SELECT asset_id, source_id, title, purpose FROM assets WHERE purpose='reference'"
        ).fetchall()

        for row in ref_rows:
            relevance = self._score_relevance(row, title) * 0.8  # references are less relevant
            if relevance >= self.min_relevance:
                items.append(ReferenceItem(
                    asset_id=row["asset_id"],
                    reference_type="clip",
                    relevance_score=relevance,
                    source_id=row["source_id"],
                ))

        return sorted(items, key=lambda x: -x.relevance_score)[:10]

    def _score_relevance(self, asset, title):
        """Score an asset's relevance to the script title."""
        score = 0.3  # base
        asset_title = asset.get("title", "").lower()
        title_lower = title.lower()

        # Title match
        if title_lower in asset_title or asset_title in title_lower:
            score += 0.5

        # Word overlap
        title_words = set(title_lower.split())
        asset_words = set(asset_title.split())
        overlap = title_words & asset_words
        score += min(0.3, len(overlap) * 0.1)

        # Purpose bonus
        if asset.get("purpose") == "production_source":
            score += 0.2

        return min(1.0, score)

    def _write_pack_jev(self, pack):
        """Write the pack JEV for downstream agents."""
        jev_id = "jev:" + hashlib.sha256(
            f"{pack.pack_id}:ref".encode()
        ).hexdigest()[:16]
        jev = {
            "jev_id": jev_id,
            "agent": "content_referencer",
            "version": self.VERSION,
            "timestamp": time.time(),
            "pack_id": pack.pack_id,
            "script_id": pack.script_id,
            "title": pack.jev_id,
            "total_relevance": pack.total_relevance,
            "decision": "pack_built",
            "evidence": {
                "items": len(pack.items),
                "jev_id": pack.jev_id,
            },
        }
        self.db.put_artifact(jev_id, "pack_jev", pack.script_id, jev_id, {"jev": jev})
        return jev_id

    def get_pack(self, pack_id):
        row = self.db.get_artifact(pack_id)
        if not row:
            return None
        try:
            return json.loads(row["metadata"])["jev"]
        except (KeyError, json.JSONDecodeError):
            return json.loads(row["metadata"])

    def list_packs(self, limit=20):
        """List recent pack JEVs."""
        rows = self.db.cx.execute(
            "SELECT key, metadata FROM artifacts WHERE agent='pack_jev' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(r["metadata"])["jev"] for r in rows]