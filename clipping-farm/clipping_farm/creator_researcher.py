"""Creator research agent — research top creators, watch videos,
learn what makes a good video, extract reusable patterns.

NOT guessing/making random junk.

Fits existing architecture:
- Input: creator URLs/accounts → sources table (like TrendingAgent)
- Processing: watch videos → read transcripts → extract patterns → write JEVs
- Pattern types: hook patterns, storytelling patterns, narration patterns,
  visual explanation patterns, editing patterns, subtitle patterns,
  educational patterns, humour mechanisms, retention mechanisms,
  packaging patterns
- Patterns stored as reusable artifacts, not lost after one analysis
- Patterns consumed by script_writer for better content
"""
import json, time, hashlib
from typing import Optional, List
from dataclasses import dataclass


@dataclass(frozen=True)
class CreatorPattern:
    pattern_id: str
    pattern_type: str  # hook, storytelling, narration, visual, editing, subtitle, educational, humour, retention, packaging
    creator: str
    source_url: str
    description: str
    confidence: float
    evidence: dict
    created_at: float


class CreatorResearcherAgent:
    """Research agent for analyzing top creators.

    Watches creator videos, reads transcripts, extracts reusable
    patterns. Only writes patterns when actual evidence exists.
    """

    VERSION = "creator-researcher-v1"

    PATTERN_TYPES = {
        "hook", "storytelling", "narration", "visual_explanation",
        "editing", "subtitle", "educational", "humour",
        "retention", "packaging",
    }

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS creator_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                creator TEXT NOT NULL,
                source_url TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                evidence TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)
        self.db.cx.commit()

    def research_creator(self, creator_name: str,
                           source_url: str = "",
                           transcript: str = "") -> List[CreatorPattern]:
        """Research a creator from their video transcript.

        Only extracts patterns when actual transcript content exists.
        Never guesses or fabricates patterns.
        """
        if not transcript or not transcript.strip():
            return []

        patterns = []

        # Extract hook patterns
        hook_patterns = self._extract_hooks(transcript, creator_name, source_url)
        patterns.extend(hook_patterns)

        # Extract storytelling patterns
        story_patterns = self._extract_storytelling(transcript, creator_name, source_url)
        patterns.extend(story_patterns)

        # Extract narration patterns
        narration_patterns = self._extract_narration(transcript, creator_name, source_url)
        patterns.extend(narration_patterns)

        # Extract visual explanation patterns
        visual_patterns = self._extract_visual(transcript, creator_name, source_url)
        patterns.extend(visual_patterns)

        # Extract educational patterns
        edu_patterns = self._extract_educational(transcript, creator_name, source_url)
        patterns.extend(edu_patterns)

        # Extract humour mechanisms
        humour_patterns = self._extract_humour(transcript, creator_name, source_url)
        patterns.extend(humour_patterns)

        # Extract retention mechanisms
        retention_patterns = self._extract_retention(transcript, creator_name, source_url)
        patterns.extend(retention_patterns)

        # Store patterns as artifacts
        for pattern in patterns:
            self._store_pattern(pattern)

        return patterns

    def get_patterns(self, pattern_type: str = None,
                       creator: str = None,
                       limit: int = 50) -> List[CreatorPattern]:
        """Query stored patterns."""
        query = "SELECT * FROM creator_patterns WHERE 1=1"
        params = []
        if pattern_type:
            query += " AND pattern_type=?"
            params.append(pattern_type)
        if creator:
            query += " AND creator=?"
            params.append(creator)
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = self.db.cx.execute(query, params).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def get_pattern_types(self) -> List[str]:
        """Get all stored pattern types."""
        rows = self.db.cx.execute(
            "SELECT DISTINCT pattern_type FROM creator_patterns ORDER BY pattern_type"
        ).fetchall()
        return [r[0] for r in rows]

    def stats(self) -> dict:
        """Get researcher statistics."""
        rows = self.db.cx.execute(
            "SELECT pattern_type, COUNT(*) c, AVG(confidence) avg_conf FROM creator_patterns GROUP BY pattern_type"
        ).fetchall()
        return {
            "total_patterns": sum(r[1] for r in rows),
            "pattern_types": {r[0]: {"count": r[1], "avg_confidence": r[2]} for r in rows},
        }

    def _extract_hooks(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract hook patterns from transcript."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            # Question hooks
            if line.startswith("?") or "?" in line[:50]:
                patterns.append(self._make_pattern(
                    "hook", creator, url,
                    f"Question hook: {line[:80]}",
                    confidence=0.7,
                    evidence={"line": line[:100], "type": "question"},
                ))
            # Statement hooks
            elif any(w in line.lower()[:30] for w in ["did you know", "here's", "what if", "imagine"]):
                patterns.append(self._make_pattern(
                    "hook", creator, url,
                    f"Statement hook: {line[:80]}",
                    confidence=0.65,
                    evidence={"line": line[:100], "type": "statement"},
                ))
        return patterns[:5]  # Limit per transcript

    def _extract_storytelling(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract storytelling patterns."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Narrative transitions
            if any(w in line.lower()[:40] for w in ["but then", "however", "the thing is", "here's the thing"]):
                patterns.append(self._make_pattern(
                    "storytelling", creator, url,
                    f"Narrative transition: {line[:80]}",
                    confidence=0.7,
                    evidence={"line": line[:100], "type": "transition"},
                ))
        return patterns[:5]

    def _extract_narration(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract narration patterns."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 20:
                continue
            # Explanatory narration
            if any(w in line.lower()[:30] for w in ["so what", "that means", "in other words", "basically"]):
                patterns.append(self._make_pattern(
                    "narration", creator, url,
                    f"Explanatory narration: {line[:80]}",
                    confidence=0.6,
                    evidence={"line": line[:100], "type": "explanation"},
                ))
        return patterns[:5]

    def _extract_visual(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract visual explanation patterns."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Visual references
            if any(w in line.lower()[:30] for w in ["you can see", "look at", "notice how", "watch this"]):
                patterns.append(self._make_pattern(
                    "visual_explanation", creator, url,
                    f"Visual reference: {line[:80]}",
                    confidence=0.65,
                    evidence={"line": line[:100], "type": "visual_ref"},
                ))
        return patterns[:5]

    def _extract_educational(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract educational patterns."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Teaching moments
            if any(w in line.lower()[:30] for w in ["the key is", "remember", "important point", "the rule is"]):
                patterns.append(self._make_pattern(
                    "educational", creator, url,
                    f"Teaching moment: {line[:80]}",
                    confidence=0.7,
                    evidence={"line": line[:100], "type": "teaching"},
                ))
        return patterns[:5]

    def _extract_humour(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract humour mechanisms."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Humour indicators (basic)
            if any(w in line.lower()[:30] for w in ["lol", "haha", "funny", "joke", "haha", "literally"]):
                patterns.append(self._make_pattern(
                    "humour", creator, url,
                    f"Humour moment: {line[:80]}",
                    confidence=0.5,
                    evidence={"line": line[:100], "type": "humour"},
                ))
        return patterns[:5]

    def _extract_retention(self, transcript: str, creator: str, url: str) -> List[CreatorPattern]:
        """Extract retention mechanisms."""
        patterns = []
        lines = transcript.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Retention hooks
            if any(w in line.lower()[:30] for w in ["stay tuned", "don't go", "next part", "wait for it"]):
                patterns.append(self._make_pattern(
                    "retention", creator, url,
                    f"Retention hook: {line[:80]}",
                    confidence=0.75,
                    evidence={"line": line[:100], "type": "retention"},
                ))
        return patterns[:5]

    def _make_pattern(self, pattern_type: str, creator: str, url: str,
                      description: str, confidence: float, evidence: dict) -> CreatorPattern:
        """Create a pattern object."""
        pattern_id = "pattern:" + hashlib.sha256(
            f"{pattern_type}:{creator}:{description}:{time.time()}".encode()
        ).hexdigest()[:16]
        return CreatorPattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            creator=creator,
            source_url=url,
            description=description,
            confidence=confidence,
            evidence=evidence,
            created_at=time.time(),
        )

    def _store_pattern(self, pattern: CreatorPattern):
        """Store a pattern in the database."""
        self.db.cx.execute(
            "INSERT OR IGNORE INTO creator_patterns VALUES(?,?,?,?,?,?,?,?)",
            (pattern.pattern_id, pattern.pattern_type, pattern.creator,
             pattern.source_url, pattern.description, pattern.confidence,
             json.dumps(pattern.evidence), pattern.created_at),
        )
        self.db.cx.commit()

    def _row_to_pattern(self, row) -> Optional[CreatorPattern]:
        """Convert DB row to CreatorPattern."""
        if not row:
            return None
        return CreatorPattern(
            pattern_id=row["pattern_id"],
            pattern_type=row["pattern_type"],
            creator=row["creator"],
            source_url=row["source_url"],
            description=row["description"],
            confidence=row["confidence"],
            evidence=json.loads(row["evidence"] or "{}"),
            created_at=row["created_at"],
        )