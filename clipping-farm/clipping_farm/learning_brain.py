"""Learning Brain — advisory only.

Learns from accepted/rejected candidates, QC outcomes, repair outcomes,
production outcomes, content performance, human decisions, provider
performance, capability performance.

Recommends: candidate thresholds, provider selection, routing,
production patterns, content opportunities, workflow improvements.

Every recommendation traceable to evidence.
MAY NOT override hard gates.
"""
import json, time, hashlib
from typing import Optional, List
from dataclasses import dataclass


@dataclass(frozen=True)
class LearningEvent:
    event_id: str
    event_type: str  # candidate_accepted, candidate_rejected, qc_pass, qc_fail, repair, human_decision, provider_performance
    source: str
    data: dict
    timestamp: float
    evidence: dict


class LearningBrain:
    """Advisory learning system.

    Observes pipeline outcomes and learns patterns.
    Never overrides hard gates — only recommends.
    """

    VERSION = "learning-brain-v1"

    EVENT_TYPES = {
        "candidate_accepted", "candidate_rejected",
        "qc_pass", "qc_fail", "repair",
        "human_decision", "provider_performance",
        "capability_performance", "content_opportunity",
    }

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS learning_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                timestamp REAL NOT NULL,
                evidence TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self.db.cx.commit()

    def record(self, event_type: str, source: str,
                data: dict = None, evidence: dict = None):
        """Record a learning event."""
        if event_type not in self.EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")

        event_id = "learn:" + hashlib.sha256(
            f"{event_type}:{source}:{time.time()}".encode()
        ).hexdigest()[:16]

        now = time.time()
        self.db.cx.execute(
            "INSERT INTO learning_events VALUES(?,?,?,?,?,?)",
            (event_id, event_type, source,
             json.dumps(data or {}), now,
             json.dumps(evidence or {})),
        )
        self.db.cx.commit()
        return event_id

    def get_events(self, event_type: str = None, source: str = None,
                    limit: int = 50):
        """Query learning events."""
        query = "SELECT * FROM learning_events WHERE 1=1"
        params = []
        if event_type:
            query += " AND event_type=?"
            params.append(event_type)
        if source:
            query += " AND source=?"
            params.append(source)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self.db.cx.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def summarize(self, event_type: str = None):
        """Summarize learning events by type."""
        query = "SELECT event_type, COUNT(*) c, AVG(JSON_EXTRACT(data, '$.score')) avg_score FROM learning_events"
        params = []
        if event_type:
            query += " WHERE event_type=?"
            params.append(event_type)
        query += " GROUP BY event_type"

        rows = self.db.cx.execute(query, params).fetchall()
        return [
            {"event_type": r[0], "count": r[1], "avg_score": r[2]}
            for r in rows
        ]

    def recommend_threshold(self, capability: str,
                             quality_required: float = 0.7):
        """Recommend candidate threshold based on historical outcomes."""
        events = self.get_events(source=capability, limit=100)
        if not events:
            return {"recommendation": quality_required, "confidence": 0.0,
                    "reason": "no historical data"}

        # Analyze pass/fail rates
        qc_pass = sum(1 for e in events if e.event_type == "qc_pass")
        qc_fail = sum(1 for e in events if e.event_type == "qc_fail")
        total = qc_pass + qc_fail

        if total == 0:
            return {"recommendation": quality_required, "confidence": 0.0,
                    "reason": "no QC data"}

        pass_rate = qc_pass / total
        if pass_rate > 0.8:
            return {"recommendation": max(0.6, quality_required - 0.05),
                    "confidence": pass_rate,
                    "reason": f"high pass rate ({pass_rate:.0%}), lower threshold OK"}
        elif pass_rate < 0.3:
            return {"recommendation": min(0.95, quality_required + 0.05),
                    "confidence": pass_rate,
                    "reason": f"low pass rate ({pass_rate:.0%}), raise threshold"}
        else:
            return {"recommendation": quality_required, "confidence": pass_rate,
                    "reason": f"moderate pass rate ({pass_rate:.0%}), keep threshold"}

    def recommend_provider(self, capability: str):
        """Recommend provider based on historical performance."""
        events = self.get_events(
            event_type="provider_performance",
            source=capability,
            limit=50,
        )
        if not events:
            return {"reason": "no provider performance data"}

        # Calculate average cost and quality per provider
        providers = {}
        for event in events:
            provider = event.data.get("provider", "unknown")
            if provider not in providers:
                providers[provider] = {"costs": [], "qualities": []}
            providers[provider]["costs"].append(event.data.get("cost", 0))
            providers[provider]["qualities"].append(event.data.get("quality", 0))

        # Best provider: highest quality/cost ratio
        best = None
        best_ratio = -1
        for provider, stats in providers.items():
            avg_quality = sum(stats["qualities"]) / len(stats["qualities"]) if stats["qualities"] else 0
            avg_cost = sum(stats["costs"]) / len(stats["costs"]) if stats["costs"] else 0
            ratio = avg_quality / avg_cost if avg_cost > 0 else avg_quality
            if ratio > best_ratio:
                best_ratio = ratio
                best = provider

        return {
            "recommended_provider": best,
            "reason": f"best quality/cost ratio ({best_ratio:.2f})",
            "providers_analyzed": len(providers),
        }

    def recommend_workflow(self):
        """Recommend workflow improvements based on events."""
        events = self.get_events(limit=200)
        if not events:
            return {"reason": "no events to analyze"}

        recommendations = []

        # Check failure patterns
        failures = [e for e in events if e.event_type in ("qc_fail", "repair")]
        if len(failures) > 10:
            recommendations.append({
                "type": "warning",
                "reason": f"high failure rate ({len(failures)} failures in {len(events)} events)",
                "action": "review QC criteria",
            })

        # Check repair patterns
        repairs = [e for e in events if e.event_type == "repair"]
        if len(repairs) > len(failures) * 0.5:
            recommendations.append({
                "type": "info",
                "reason": "many repairs after failures",
                "action": "improve upstream quality",
            })

        return {
            "recommendations": recommendations,
            "total_events": len(events),
        }

    def learn_from_pipeline(self, pipeline_state):
        """Learn from a completed pipeline run."""
        events = []

        # Record pipeline completion
        event_id = self.record(
            "human_decision",
            "pipeline",
            data={"pipeline_id": pipeline_state.get("pipeline_id"),
                   "status": pipeline_state.get("status")},
            evidence={"pipeline": pipeline_state},
        )
        events.append(event_id)

        return events

    def get_stats(self):
        """Get learning brain statistics."""
        rows = self.db.cx.execute(
            "SELECT event_type, COUNT(*) c FROM learning_events GROUP BY event_type"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def _row_to_event(self, row):
        if not row:
            return None
        return LearningEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            source=row["source"],
            data=json.loads(row["data"] or "{}"),
            timestamp=row["timestamp"],
            evidence=json.loads(row["evidence"] or "{}"),
        )