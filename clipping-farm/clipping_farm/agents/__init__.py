"""Trending agent — watches for new comics, trending topics, source material.

Writes a JEV when it finds trending content. The script writer agent reads
that JEV to generate scripts. This is the entry point for the content pipeline.

The trending agent does NOT process media — it discovers what to process.
"""
from dataclasses import dataclass, field
from typing import Optional
import json
import time
import hashlib


@dataclass(frozen=True)
class TrendingItem:
    title: str
    url: str
    source_type: str  # "comic", "video", "article", "social"
    topic: str
    hot_score: float  # 0..10
    discovered_at: float = field(default_factory=time.time)
    jev_id: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "topic": self.topic,
            "hot_score": self.hot_score,
            "discovered_at": self.discovered_at,
            "jev_id": self.jev_id,
        }


class TrendingAgent:
    """Discovers trending content and writes JEVs for downstream agents."""

    VERSION = "trending-v1"

    def __init__(self, db, *, min_hot_score=5.0, max_items=20):
        self.db = db
        self.min_hot_score = min_hot_score
        self.max_items = max_items

    def discover(self, sources=None):
        """Discover trending items from sources.

        sources: list of source dicts from the DB. If None, queries the DB.
        Returns list of TrendingItem with JEV IDs written to the DB.
        """
        if sources is None:
            sources = self._get_sources()

        items = []
        for source in sources:
            hot = self._score_source(source)
            if hot < self.min_hot_score:
                continue
            jev_id = self._write_jev(source, hot)
            item = TrendingItem(
                title=source.get("title", "unknown"),
                url=source.get("location", ""),
                source_type=source.get("kind", "file"),
                topic=source.get("metadata", "{}"),
                hot_score=hot,
                jev_id=jev_id,
            )
            items.append(item)

        return sorted(items, key=lambda x: -x.hot_score)[: self.max_items]

    def _get_sources(self):
        rows = self.db.cx.execute(
            "SELECT * FROM sources ORDER BY last_seen_at DESC LIMIT 100"
        ).fetchall()
        return [dict(r) for r in rows]

    def _score_source(self, source):
        """Score a source for trending relevance.

        Simple heuristic: recency + source type + metadata keywords.
        Real implementation would use external trending APIs.
        """
        score = 5.0  # base
        metadata = source.get("metadata", "{}")
        try:
            meta = json.loads(metadata) if isinstance(metadata, str) else metadata
            title = meta.get("title", source.get("location", "")).lower()
            # Comic/nerd culture keywords
            for kw in ["marvel", "dc", "comic", "anime", "gaming", "space", "science", "nature"]:
                if kw in title:
                    score += 1.5
            # Freshness
            last_seen = source.get("last_seen_at", 0)
            age_hours = (time.time() - last_seen) / 3600
            if age_hours < 24:
                score += 2.0
            elif age_hours < 72:
                score += 1.0
        except (json.JSONDecodeError, TypeError):
            pass
        return min(10.0, score)

    def _write_jev(self, source, hot_score):
        """Write a JEV (Job Evidence Vector) for this trending discovery."""
        jev_id = "jev:" + hashlib.sha256(
            f"{source['source_id']}:{time.time()}".encode()
        ).hexdigest()[:16]
        jev = {
            "jev_id": jev_id,
            "agent": "trending",
            "version": self.VERSION,
            "timestamp": time.time(),
            "source_id": source["source_id"],
            "title": source.get("location", ""),
            "hot_score": hot_score,
            "decision": "trending",
            "evidence": {
                "source_type": source.get("kind", "file"),
                "recency_hours": (time.time() - source.get("last_seen_at", time.time())) / 3600,
            },
        }
        self.db.put_artifact(jev_id, "trending_jev", source["source_id"], jev_id, jev)
        return jev_id

    def get_jev(self, jev_id):
        """Read a JEV by ID."""
        row = self.db.get_artifact(jev_id)
        if not row:
            return None
        return json.loads(row["metadata"])["jev"]

    def list_jevs(self, limit=20):
        """List recent JEVs."""
        rows = self.db.cx.execute(
            "SELECT key, metadata FROM artifacts WHERE agent='trending_jev' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(r["metadata"])["jev"] for r in rows]