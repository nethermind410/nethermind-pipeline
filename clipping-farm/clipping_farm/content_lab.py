"""Content Lab integration — bridges Clipping Farm outputs to production objects.

Preserves identity bridge: job→run→asset→clip→production→content.
Moves from analysed clip into production object without manually
reconstructing provenance. Retains source provenance, transcript/analysis,
evidence, candidate scores, JEV info, semantic QC, vision evidence, QC
results, derived clip metadata.
"""
import json, time, hashlib
from pathlib import Path
from typing import Optional


class ContentLab:
    """Integrates Clipping Farm outputs into Content Lab."""

    VERSION = "content-lab-v1"

    def __init__(self, db):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self):
        """Create content_lab table if it doesn't exist."""
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS content_lab (
                production_id TEXT PRIMARY KEY,
                asset_id TEXT,
                source_id TEXT,
                pipeline_id TEXT,
                job_id TEXT,
                clip_id TEXT,
                title TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                content_metadata TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '{}',
                qc_result TEXT,
                approval_id TEXT,
                rights_state TEXT DEFAULT 'UNKNOWN',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self.db.cx.commit()

    def create_production(self, asset_id: str, source_id: str,
                          pipeline_id: str = "", job_id: str = "",
                          clip_id: str = "", title: str = "",
                          metadata: dict = None, provenance: dict = None):
        """Create a production object from an analysed clip.

        Preserves identity bridge: job→run→asset→clip→production→content.
        """
        production_id = "prod:" + hashlib.sha256(
            f"{asset_id}:{source_id}:{time.time()}".encode()
        ).hexdigest()[:16]

        now = time.time()
        self.db.cx.execute("""
            INSERT INTO content_lab(
                production_id, asset_id, source_id, pipeline_id, job_id,
                clip_id, title, status, content_metadata, provenance,
                rights_state, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            production_id, asset_id, source_id, pipeline_id, job_id,
            clip_id, title, "PENDING",
            json.dumps(metadata or {}, ensure_ascii=False),
            json.dumps(provenance or {}, ensure_ascii=False),
            "UNKNOWN", now, now,
        ))
        self.db.cx.commit()

        return self.get_production(production_id)

    def get_production(self, production_id: str):
        """Get a production object by ID."""
        row = self.db.cx.execute(
            "SELECT * FROM content_lab WHERE production_id=?",
            (production_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_production(row)

    def update_production(self, production_id: str, **fields):
        """Update a production object."""
        allowed = {
            "title", "status", "content_metadata", "provenance",
            "qc_result", "approval_id", "rights_state", "pipeline_id",
            "job_id", "clip_id",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown fields: {sorted(unknown)}")

        for key in ("content_metadata", "provenance"):
            if key in fields and isinstance(fields[key], dict):
                fields[key] = json.dumps(fields[key], ensure_ascii=False)

        fields["updated_at"] = time.time()
        assignments = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [production_id]
        self.db.cx.execute(
            f"UPDATE content_lab SET {assignments} WHERE production_id=?",
            values,
        )
        self.db.cx.commit()
        return self.get_production(production_id)

    def link_approval(self, production_id: str, approval_id: str):
        """Link an approval to a production."""
        return self.update_production(
            production_id, approval_id=approval_id
        )

    def link_qc(self, production_id: str, qc_result: dict):
        """Link QC results to a production."""
        return self.update_production(
            production_id, qc_result=json.dumps(qc_result, ensure_ascii=False)
        )

    def set_status(self, production_id: str, status: str):
        """Set production status."""
        valid_statuses = {"PENDING", "PROCESSING", "QC_PASS", "QC_FAIL",
                          "APPROVED", "REJECTED", "PUBLISHED", "ARCHIVED"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")
        return self.update_production(production_id, status=status)

    def get_asset_productions(self, asset_id: str):
        """Get all productions for an asset."""
        rows = self.db.cx.execute(
            "SELECT * FROM content_lab WHERE asset_id=? ORDER BY created_at DESC",
            (asset_id,),
        ).fetchall()
        return [self._row_to_production(r) for r in rows]

    def get_source_productions(self, source_id: str):
        """Get all productions for a source."""
        rows = self.db.cx.execute(
            "SELECT * FROM content_lab WHERE source_id=? ORDER BY created_at DESC",
            (source_id,),
        ).fetchall()
        return [self._row_to_production(r) for r in rows]

    def list_productions(self, status=None, limit=50):
        """List productions, optionally filtered by status."""
        if status:
            rows = self.db.cx.execute(
                "SELECT * FROM content_lab WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.db.cx.execute(
                "SELECT * FROM content_lab ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_production(r) for r in rows]

    def snapshot(self, production_id: str):
        """Return a full snapshot: production + asset + jobs + artifacts."""
        production = self.get_production(production_id)
        if not production:
            return None

        asset_id = production.get("asset_id")
        source_id = production.get("source_id")

        snapshot = {
            "production": production,
            "asset": None,
            "jobs": [],
            "artifacts": [],
        }

        if asset_id:
            asset = self.db.get_asset(asset_id)
            snapshot["asset"] = asset

        if source_id:
            jobs = self.db.cx.execute(
                "SELECT id, task, agent, state, attempts, actual_cost, error, created_at FROM jobs WHERE json_extract(payload, '$.source_id')=? ORDER BY created_at",
                (source_id,),
            ).fetchall()
            snapshot["jobs"] = [dict(r) for r in jobs]

            artifacts = self.db.cx.execute(
                "SELECT kind, path, content_hash, metadata, created_at FROM artifacts WHERE json_extract(metadata, '$.source_id')=? ORDER BY created_at",
                (source_id,),
            ).fetchall()
            snapshot["artifacts"] = [dict(r) for r in artifacts]

        return snapshot

    def _row_to_production(self, row):
        if not row:
            return None
        return {
            "production_id": row["production_id"],
            "asset_id": row["asset_id"],
            "source_id": row["source_id"],
            "pipeline_id": row["pipeline_id"],
            "job_id": row["job_id"],
            "clip_id": row["clip_id"],
            "title": row["title"],
            "status": row["status"],
            "content_metadata": json.loads(row["content_metadata"] or "{}"),
            "provenance": json.loads(row["provenance"] or "{}"),
            "qc_result": json.loads(row["qc_result"] or "null"),
            "approval_id": row["approval_id"],
            "rights_state": row["rights_state"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }