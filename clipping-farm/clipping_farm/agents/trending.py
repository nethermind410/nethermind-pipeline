"""Trending agent — watches for new comics, trending topics, source material."""
from dataclasses import dataclass, field
from typing import Optional
import json
import time
import hashlib


@dataclass(frozen=True)
class TrendingItem:
    title: str
    url: str
    source_type: str
    topic: str
    hot_score: float
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
    VERSION = "trending-v1"

    def __init__(self, db, *, min_hot_score=5.0, max_items=20):
        self.db = db
        self.min_hot_score = min_hot_score
        self.max_items = max_items

    def discover(self, sources=None):
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
        score = 5.0
        metadata = source.get("metadata", "{}")
        try:
            meta = json.loads(metadata) if isinstance(metadata, str) else metadata
            title = meta.get("title", source.get("location", "")).lower()
            for kw in ["marvel", "dc", "comic", "anime", "gaming", "space", "science", "nature"]:
                if kw in title:
                    score += 1.5
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
        row = self.db.get_artifact(jev_id)
        if not row:
            return None
        try:
            return json.loads(row["metadata"])["jev"]
        except (KeyError, json.JSONDecodeError):
            return json.loads(row["metadata"])

    def list_jevs(self, limit=20):
        rows = self.db.cx.execute(
            "SELECT id, metadata FROM artifacts WHERE kind='trending_jev' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            try:
                result.append(json.loads(r["metadata"])["jev"])
            except (KeyError, json.JSONDecodeError):
                result.append(json.loads(r["metadata"]))
        return result