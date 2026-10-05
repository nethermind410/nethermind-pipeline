"""Script writer agent — generates scripts from trending JEVs + source material.

Reads JEVs from the trending agent, combines with source material,
and produces a script. The content referencer agent reads this JEV
to build reference clips.

Each script includes:
- hook (first 3 seconds)
- body (main content)
- payoff (closing)
- JEV evidence trail
"""
from dataclasses import dataclass, field
from typing import Optional, List
import json
import time
import hashlib


@dataclass(frozen=True)
class ScriptStep:
    section: str  # "hook", "body", "payoff"
    text: str
    start_time: float
    duration: float
    evidence: list = field(default_factory=list)


@dataclass(frozen=True)
class Script:
    script_id: str
    source_id: str
    jev_id: str
    title: str
    steps: list  # list of ScriptStep dicts
    total_duration: float
    created_at: float = field(default_factory=time.time)
    quality_score: float = 0.0

    def to_dict(self):
        return {
            "script_id": self.script_id,
            "source_id": self.source_id,
            "jev_id": self.jev_id,
            "title": self.title,
            "steps": [s.__dict__ if hasattr(s, "__dict__") else s for s in self.steps],
            "total_duration": self.total_duration,
            "created_at": self.created_at,
            "quality_score": self.quality_score,
        }


class ScriptWriterAgent:
    """Generates scripts from trending JEVs."""

    VERSION = "script-writer-v1"

    def __init__(self, db, *, min_quality=0.5):
        self.db = db
        self.min_quality = min_quality

    def write_script(self, jev_id: str, source_material: Optional[dict] = None) -> Script:
        """Generate a script from a trending JEV.

        Args:
            jev_id: The trending JEV ID from the trending agent.
            source_material: Optional transcript/analysis data.

        Returns:
            Script with hook, body, payoff sections.
        """
        # Read the JEV
        jev_row = self.db.get_artifact(jev_id)
        if not jev_row:
            raise ValueError(f"JEV not found: {jev_id}")
        try:
            jev = json.loads(jev_row["metadata"])["jev"]
        except (KeyError, json.JSONDecodeError):
            jev = json.loads(jev_row["metadata"])

        source_id = jev["source_id"]
        title = jev.get("title", "Untitled")

        # Build script steps from source material or JEV
        steps = self._build_steps(jev, source_material)

        total_duration = sum(s.duration for s in steps)
        quality = self._score_script(steps)

        script_id = "script:" + hashlib.sha256(
            f"{jev_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        script = Script(
            script_id=script_id,
            source_id=source_id,
            jev_id=jev_id,
            title=title,
            steps=steps,
            total_duration=total_duration,
            quality_score=quality,
        )

        # Write the script JEV for downstream agents
        self._write_script_jev(script)
        return script

    def _build_steps(self, jev, source_material):
        """Build script steps from JEV and source material."""
        steps = []

        # Hook: first 3 seconds, grab attention
        hook_text = self._extract_hook(jev, source_material)
        steps.append(ScriptStep(
            section="hook",
            text=hook_text,
            start_time=0.0,
            duration=3.0,
            evidence=[{"source": "jev", "jev_id": jev["jev_id"]}],
        ))

        # Body: main content from source material
        body_text = self._extract_body(jev, source_material)
        body_duration = max(10.0, len(body_text) * 0.15)  # ~150wpm
        steps.append(ScriptStep(
            section="body",
            text=body_text,
            start_time=3.0,
            duration=body_duration,
            evidence=[{"source": "jev", "jev_id": jev["jev_id"]}],
        ))

        # Payoff: closing hook
        payoff_text = self._extract_payoff(jev, source_material)
        steps.append(ScriptStep(
            section="payoff",
            text=payoff_text,
            start_time=3.0 + body_duration,
            duration=3.0,
            evidence=[{"source": "jev", "jev_id": jev["jev_id"]}],
        ))

        return steps

    def _extract_hook(self, jev, source_material):
        """Extract or generate a hook from the JEV."""
        title = jev.get("title", "")
        if source_material:
            transcript = source_material.get("transcript", [])
            if transcript:
                first = transcript[0].get("text", "")
                if first:
                    return first[:100]
        return f"Did you know? {title}"[:100]

    def _extract_body(self, jev, source_material):
        """Extract body text from source material."""
        if source_material:
            transcript = source_material.get("transcript", [])
            texts = [t.get("text", "") for t in transcript if t.get("text")]
            if texts:
                return " ".join(texts)[:500]
        return jev.get("title", "Content")

    def _extract_payoff(self, jev, source_material):
        """Extract payoff from source material."""
        if source_material:
            transcript = source_material.get("transcript", [])
            if transcript:
                last = transcript[-1].get("text", "")
                if last:
                    return last[:100]
        return "Stay tuned for more."[:100]

    def _score_script(self, steps):
        """Score script quality."""
        score = 0.5
        for step in steps:
            if step.section == "hook" and len(step.text) > 10:
                score += 0.2
            if step.section == "body" and len(step.text) > 50:
                score += 0.2
            if step.section == "payoff" and len(step.text) > 10:
                score += 0.1
        return min(1.0, score)

    def _write_script_jev(self, script):
        """Write the script JEV for downstream agents."""
        jev_id = "jev:" + hashlib.sha256(
            f"{script.script_id}:script".encode()
        ).hexdigest()[:16]
        jev = {
            "jev_id": jev_id,
            "agent": "script_writer",
            "version": self.VERSION,
            "timestamp": time.time(),
            "script_id": script.script_id,
            "source_id": script.source_id,
            "title": script.title,
            "quality_score": script.quality_score,
            "decision": "script_written",
            "evidence": {
                "steps": len(script.steps),
                "total_duration": script.total_duration,
                "jev_id": script.jev_id,
            },
        }
        self.db.put_artifact(jev_id, "script_jev", script.source_id, jev_id, {"jev": jev})
        return jev_id

    def get_script(self, script_id):
        row = self.db.get_artifact(script_id)
        if not row:
            return None
        try:
            return json.loads(row["metadata"])["jev"]
        except (KeyError, json.JSONDecodeError):
            return json.loads(row["metadata"])

    def list_scripts(self, limit=20):
        rows = self.db.cx.execute(
            "SELECT id, metadata FROM artifacts WHERE kind='script_jev' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            try:
                result.append(json.loads(r["metadata"])["jev"])
            except (KeyError, json.JSONDecodeError):
                result.append(json.loads(r["metadata"]))
        return result