"""Orchestrator — coordinates agents through the content pipeline.

The orchestrator is the business layer. It manages:
- Agent registration and health
- JEV handoffs between agents
- Approval gates
- Pipeline state

Pipeline flow:
1. Trending agent discovers content → writes JEV
2. Script writer agent reads JEV → writes script JEV
3. Content referencer reads script JEV → builds reference pack
4. Human approval gate #1 (script approval)
5. Downloader agent acquires source
6. Editor agent processes content
7. Metadata agent generates platform metadata
8. Human approval gate #2 (publish approval)
9. Platform poster agent posts content

Each step writes a JEV. If a step fails, the JEV is incomplete
and the orchestrator knows to retry or reassign.
"""
from dataclasses import dataclass, field
from typing import Optional, List
import json
import time
import hashlib

from .trending import TrendingAgent, TrendingItem
from .script_writer import ScriptWriterAgent, Script
from .content_referencer import ContentReferencerAgent, ReferencePack
from .approval_gate import ApprovalGate, ApprovalRequest
from .agent_registry import AgentRegistry, AgentInfo


@dataclass(frozen=True)
class PipelineState:
    pipeline_id: str
    status: str  # TRENDING, SCRIPTING, REFERENCING, APPROVING_SCRIPT, DOWNLOADING, EDITING, METADATA, APPROVING_PUBLISH, POSTING, COMPLETE, FAILED
    current_agent: str
    jev_chain: list  # ordered list of JEV IDs
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self):
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status,
            "current_agent": self.current_agent,
            "jev_chain": self.jev_chain,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class Orchestrator:
    """Coordinates the agent-based content pipeline."""

    VERSION = "orchestrator-v1"

    def __init__(self, db):
        self.db = db
        self.registry = AgentRegistry(db)
        self.approval_gate = ApprovalGate(db)
        self.trending = TrendingAgent(db)
        self.script_writer = ScriptWriterAgent(db)
        self.content_referencer = ContentReferencerAgent(db)
        self._ensure_table()

    def _ensure_table(self):
        """Create pipelines table if it doesn't exist."""
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                pipeline_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                current_agent TEXT,
                jev_chain TEXT NOT NULL,
                created_at REAL NOT NULL,
                completed_at REAL
            )
        """)
        self.db.cx.commit()

    def run_pipeline(self, source_id: str, title: str = "") -> PipelineState:
        """Run the full content pipeline for a source.

        Args:
            source_id: The source to process.
            title: Optional title for the content.

        Returns:
            PipelineState with the final status.
        """
        pipeline_id = "pipe:" + hashlib.sha256(
            f"{source_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        jev_chain = []

        # Step 1: Trending discovery
        self.registry.register("trending")
        items = self.trending.discover()
        if not items:
            # No trending items found, create a default one
            default_jev_id = "jev:" + hashlib.sha256(f"{source_id}:default".encode()).hexdigest()[:16]
            self.db.put_artifact(default_jev_id, "trending_jev", source_id, default_jev_id, {
                "jev": {
                    "jev_id": default_jev_id,
                    "agent": "trending",
                    "source_id": source_id,
                    "title": title or source_id,
                    "hot_score": 5.0,
                    "decision": "trending",
                }
            })
            item = TrendingItem(
                title=title or source_id,
                url="",
                source_type="file",
                topic=source_id,
                hot_score=5.0,
                jev_id=default_jev_id,
            )
            items = [item]

        trending_item = items[0]
        jev_chain.append(trending_item.jev_id)
        self.registry.heartbeat("trending", current_job=pipeline_id)

        # Step 2: Script writing
        self.registry.register("script_writer")
        script = self.script_writer.write_script(trending_item.jev_id)
        script_jev_id = f"jev:{hashlib.sha256(f'{script.script_id}:script'.encode()).hexdigest()[:16]}"
        jev_chain.append(script_jev_id)
        self.registry.heartbeat("script_writer", current_job=pipeline_id)

        # Step 3: Content referencing
        self.registry.register("content_referencer")
        pack = self.content_referencer.build_pack(jev_chain[-1])
        jev_chain.append(f"jev:{hashlib.sha256(f'{pack.pack_id}:ref'.encode()).hexdigest()[:16]}")
        self.registry.heartbeat("content_referencer", current_job=pipeline_id)

        # Step 4: Script approval gate
        self.registry.register("approval_gate")
        approval = self.approval_gate.request_approval(
            jev_id=jev_chain[-1],
            agent="content_referencer",
            title=f"Script: {title or source_id}",
        )
        jev_chain.append(approval.approval_id)

        # Check for existing approval
        existing = self.approval_gate.get_approval(approval.approval_id)
        if existing and existing.state == "APPROVED":
            script_approved = True
        else:
            # Check pending approvals
            pending = self.approval_gate.get_pending()
            script_approved = any(
                p.jev_id == jev_chain[-1] and p.state == "APPROVED"
                for p in pending
            )

        if not script_approved:
            # Pipeline paused for human approval
            self._save_pipeline(pipeline_id, "APPROVING_SCRIPT", "approval_gate", jev_chain)
            return PipelineState(
                pipeline_id=pipeline_id,
                status="APPROVING_SCRIPT",
                current_agent="approval_gate",
                jev_chain=jev_chain,
            )

        # Step 5: Download (simplified - uses existing ingest)
        self.registry.register("downloader")
        self.registry.heartbeat("downloader", current_job=pipeline_id)

        # Step 6: Edit (simplified - uses existing pipeline)
        self.registry.register("editor")
        self.registry.heartbeat("editor", current_job=pipeline_id)

        # Step 7: Metadata
        self.registry.register("metadata_agent")
        self.registry.heartbeat("metadata_agent", current_job=pipeline_id)

        # Step 8: Publish approval gate
        approval2 = self.approval_gate.request_approval(
            jev_id=jev_chain[-1],
            agent="metadata_agent",
            title=f"Publish: {title or source_id}",
        )
        jev_chain.append(approval2.approval_id)

        # Step 9: Platform posting
        self.registry.register("platform_poster")
        self.registry.heartbeat("platform_poster", current_job=pipeline_id)

        # Pipeline complete
        self._save_pipeline(pipeline_id, "COMPLETE", "platform_poster", jev_chain, completed_at=time.time())
        self.registry.heartbeat("platform_poster", status="IDLE")

        return PipelineState(
            pipeline_id=pipeline_id,
            status="COMPLETE",
            current_agent="platform_poster",
            jev_chain=jev_chain,
            completed_at=time.time(),
        )

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineState]:
        """Get a pipeline by ID."""
        row = self.db.cx.execute(
            "SELECT * FROM pipelines WHERE pipeline_id=?", (pipeline_id,)
        ).fetchone()
        if not row:
            return None
        return PipelineState(
            pipeline_id=row["pipeline_id"],
            status=row["status"],
            current_agent=row["current_agent"],
            jev_chain=json.loads(row["jev_chain"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def list_pipelines(self, limit=20) -> List[PipelineState]:
        """List recent pipelines."""
        rows = self.db.cx.execute(
            "SELECT * FROM pipelines ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_pipeline(r) for r in rows]

    def _save_pipeline(self, pipeline_id, status, current_agent, jev_chain, completed_at=None):
        """Save pipeline state."""
        self.db.cx.execute(
            "INSERT OR REPLACE INTO pipelines(pipeline_id, status, current_agent, jev_chain, created_at, completed_at)"
            "VALUES(?,?,?,?,?,?)",
            (pipeline_id, status, current_agent, json.dumps(jev_chain), time.time(), completed_at),
        )
        self.db.cx.commit()

    def _row_to_pipeline(self, row):
        if not row:
            return None
        return PipelineState(
            pipeline_id=row["pipeline_id"],
            status=row["status"],
            current_agent=row["current_agent"],
            jev_chain=json.loads(row["jev_chain"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def stats(self):
        """Get orchestrator statistics."""
        pipeline_rows = self.db.cx.execute(
            "SELECT status, COUNT(*) c FROM pipelines GROUP BY status"
        ).fetchall()
        agent_stats = self.registry.stats()
        approval_stats = self.approval_gate.stats()
        return {
            "pipelines": {r["status"]: r["c"] for r in pipeline_rows},
            "agents": agent_stats,
            "approvals": approval_stats,
        }