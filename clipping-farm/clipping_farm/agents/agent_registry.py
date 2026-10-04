"""Agent registry — tracks all agents, their capabilities, and status.

Replaces the conceptual "System Manifest + Capability Registry" from
the brief with a concrete, queryable agent registry.

Each agent has:
- agent_id
- name
- version
- capabilities
- status (ACTIVE, IDLE, ERROR, OFFLINE)
- last_heartbeat
- current_job
- health

The registry answers: "What agents are available right now?"
"""
from dataclasses import dataclass, field
from typing import Optional, List
import json
import time
import hashlib


@dataclass(frozen=True)
class AgentInfo:
    agent_id: str
    name: str
    version: str
    capabilities: list
    status: str  # ACTIVE, IDLE, ERROR, OFFLINE
    last_heartbeat: float
    current_job: Optional[str] = None
    health: str = "HEALTHY"  # HEALTHY, DEGRADED, FAILED

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat,
            "current_job": self.current_job,
            "health": self.health,
        }


class AgentRegistry:
    """Canonical registry of all agents and their capabilities."""

    VERSION = "agent-registry-v1"

    # Known agents and their capabilities
    KNOWN_AGENTS = {
        "trending": {
            "name": "Trending Agent",
            "version": "trending-v1",
            "capabilities": ["discover", "score", "jev-write"],
            "description": "Watches for trending content and writes JEVs",
        },
        "script_writer": {
            "name": "Script Writer Agent",
            "version": "script-writer-v1",
            "capabilities": ["script-write", "jev-write"],
            "description": "Generates scripts from trending JEVs",
        },
        "content_referencer": {
            "name": "Content Referencer Agent",
            "version": "content-referencer-v1",
            "capabilities": ["pack-build", "jev-write"],
            "description": "Builds reference packs from script JEVs",
        },
        "downloader": {
            "name": "Downloader Agent",
            "version": "downloader-v1",
            "capabilities": ["acquire", "download"],
            "description": "Downloads source material from URLs",
        },
        "editor": {
            "name": "Editor Agent",
            "version": "editor-v1",
            "capabilities": ["clip", "format", "tts", "render"],
            "description": "Edits content for short-form platforms",
        },
        "metadata_agent": {
            "name": "Metadata Agent",
            "version": "metadata-v1",
            "capabilities": ["title", "seo", "tags", "description"],
            "description": "Generates platform metadata packages",
        },
        "platform_poster": {
            "name": "Platform Poster Agent",
            "version": "platform-poster-v1",
            "capabilities": ["post", "schedule", "track"],
            "description": "Posts content to platforms",
        },
    }

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        """Create agent_registry table if it doesn't exist."""
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS agent_registry (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OFFLINE',
                last_heartbeat REAL,
                current_job TEXT,
                health TEXT DEFAULT 'HEALTHY',
                description TEXT,
                updated_at REAL NOT NULL
            )
        """)
        self.db.cx.commit()

    def register(self, agent_id: str) -> AgentInfo:
        """Register an agent in the registry."""
        info = self.KNOWN_AGENTS.get(agent_id, {})
        now = time.time()
        self.db.cx.execute(
            "INSERT OR REPLACE INTO agent_registry"
            "(agent_id, name, version, capabilities, status, last_heartbeat, health, description, updated_at)"
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                agent_id,
                info.get("name", agent_id),
                info.get("version", "unknown"),
                json.dumps(info.get("capabilities", [])),
                "ACTIVE",
                now,
                "HEALTHY",
                info.get("description", ""),
                now,
            ),
        )
        self.db.cx.commit()
        return self.get(agent_id)

    def heartbeat(self, agent_id: str, status: str = "ACTIVE", health: str = "HEALTHY", current_job: Optional[str] = None):
        """Update an agent's heartbeat."""
        now = time.time()
        self.db.cx.execute(
            "UPDATE agent_registry SET status=?, health=?, last_heartbeat=?, current_job=?, updated_at=? WHERE agent_id=?",
            (status, health, now, current_job, now, agent_id),
        )
        self.db.cx.commit()

    def get(self, agent_id: str) -> Optional[AgentInfo]:
        """Get an agent by ID."""
        row = self.db.cx.execute(
            "SELECT * FROM agent_registry WHERE agent_id=?", (agent_id,)
        ).fetchone()
        if not row:
            return None
        return AgentInfo(
            agent_id=row["agent_id"],
            name=row["name"],
            version=row["version"],
            capabilities=json.loads(row["capabilities"]),
            status=row["status"],
            last_heartbeat=row["last_heartbeat"],
            current_job=row["current_job"],
            health=row["health"],
        )

    def list_agents(self, status: Optional[str] = None) -> List[AgentInfo]:
        """List agents, optionally filtered by status."""
        if status:
            rows = self.db.cx.execute(
                "SELECT * FROM agent_registry WHERE status=? ORDER BY name", (status,)
            ).fetchall()
        else:
            rows = self.db.cx.execute(
                "SELECT * FROM agent_registry ORDER BY name"
            ).fetchall()
        return [self._row_to_info(r) for r in rows]

    def available(self) -> List[AgentInfo]:
        """Get all ACTIVE, HEALTHY agents."""
        rows = self.db.cx.execute(
            "SELECT * FROM agent_registry WHERE status='ACTIVE' AND health='HEALTHY' ORDER BY name"
        ).fetchall()
        return [self._row_to_info(r) for r in rows]

    def fail(self, agent_id: str, reason: str = ""):
        """Mark an agent as failed."""
        self.db.cx.execute(
            "UPDATE agent_registry SET status='ERROR', health='FAILED', current_job=NULL, updated_at=? WHERE agent_id=?",
            (time.time(), agent_id),
        )
        self.db.cx.commit()

    def offline(self, agent_id: str):
        """Mark an agent as offline."""
        self.db.cx.execute(
            "UPDATE agent_registry SET status='OFFLINE', health='FAILED', current_job=NULL, updated_at=? WHERE agent_id=?",
            (time.time(), agent_id),
        )
        self.db.cx.commit()

    def _row_to_info(self, row):
        if not row:
            return None
        return AgentInfo(
            agent_id=row["agent_id"],
            name=row["name"],
            version=row["version"],
            capabilities=json.loads(row["capabilities"]),
            status=row["status"],
            last_heartbeat=row["last_heartbeat"],
            current_job=row["current_job"],
            health=row["health"],
        )

    def stats(self):
        """Get registry statistics."""
        rows = self.db.cx.execute(
            "SELECT status, health, COUNT(*) c FROM agent_registry GROUP BY status, health"
        ).fetchall()
        return {f"{r['status']}/{r['health']}": r["c"] for r in rows}