"""Approval gate — human checkpoint before publishing.

Reads JEVs from downstream agents, presents for human review,
and records the approval decision in the database.

Approval states:
- PENDING: awaiting human review
- APPROVED: human approved
- REJECTED: human rejected
- EXPIRED: too old, needs re-review

The approval gate is the final checkpoint before platform posting.
"""
from dataclasses import dataclass, field
from typing import Optional, List
import json
import time
import hashlib
import uuid


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    jev_id: str
    agent: str
    title: str
    state: str  # PENDING, APPROVED, REJECTED, EXPIRED
    created_at: float
    reviewed_at: Optional[float] = None
    review_notes: str = ""

    def to_dict(self):
        return {
            "approval_id": self.approval_id,
            "jev_id": self.jev_id,
            "agent": self.agent,
            "title": self.title,
            "state": self.state,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "review_notes": self.review_notes,
        }


class ApprovalGate:
    """Human approval gate for the content pipeline."""

    VERSION = "approval-gate-v1"
    EXPIRY_HOURS = 48  # pending approvals expire after this

    def __init__(self, db):
        self.db = db
        self._ensure_table()

    def _ensure_table(self):
        """Create approvals table if it doesn't exist."""
        self.db.cx.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                approval_id TEXT PRIMARY KEY,
                jev_id TEXT NOT NULL,
                agent TEXT NOT NULL,
                title TEXT,
                state TEXT NOT NULL DEFAULT 'PENDING',
                created_at REAL NOT NULL,
                reviewed_at REAL,
                review_notes TEXT
            )
        """)
        self.db.cx.commit()

    def request_approval(self, jev_id: str, agent: str, title: str) -> ApprovalRequest:
        """Request human approval for a JEV.

        Args:
            jev_id: The JEV that needs approval.
            agent: The agent requesting approval.
            title: Human-readable title for the approval request.

        Returns:
            ApprovalRequest with PENDING state.
        """
        approval_id = "approval:" + hashlib.sha256(
            f"{jev_id}:{agent}:{time.time()}".encode()
        ).hexdigest()[:16]

        now = time.time()
        self.db.cx.execute(
            "INSERT INTO approvals(approval_id, jev_id, agent, title, state, created_at) VALUES(?,?,?,?,?,?)",
            (approval_id, jev_id, agent, title, "PENDING", now),
        )
        self.db.cx.commit()

        return ApprovalRequest(
            approval_id=approval_id,
            jev_id=jev_id,
            agent=agent,
            title=title,
            state="PENDING",
            created_at=now,
        )

    def review(self, approval_id: str, decision: str, notes: str = "") -> ApprovalRequest:
        """Record a human review decision.

        Args:
            approval_id: The approval request ID.
            decision: "APPROVED" or "REJECTED".
            notes: Optional review notes.

        Returns:
            Updated ApprovalRequest.
        """
        if decision.upper() not in ("APPROVED", "REJECTED"):
            raise ValueError(f"Invalid decision: {decision}")

        now = time.time()
        self.db.cx.execute(
            "UPDATE approvals SET state=?, reviewed_at=?, review_notes=? WHERE approval_id=?",
            (decision.upper(), now, notes, approval_id),
        )
        self.db.cx.commit()

        row = self.db.cx.execute(
            "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
        ).fetchone()
        return self._row_to_request(row)

    def get_pending(self) -> List[ApprovalRequest]:
        """Get all pending approvals."""
        rows = self.db.cx.execute(
            "SELECT * FROM approvals WHERE state='PENDING' ORDER BY created_at ASC"
        ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def get_approval(self, approval_id: str):
        row = self.db.cx.execute(
            "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
        ).fetchone()
        return self._row_to_request(row) if row else None

    def list_approvals(self, limit=20) -> List[ApprovalRequest]:
        """List recent approvals."""
        rows = self.db.cx.execute(
            "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def expire_old(self):
        """Expire pending approvals older than EXPIRY_HOURS."""
        cutoff = time.time() - (self.EXPIRY_HOURS * 3600)
        self.db.cx.execute(
            "UPDATE approvals SET state='EXPIRED' WHERE state='PENDING' AND created_at < ?",
            (cutoff,),
        )
        self.db.cx.commit()
        return self.db.cx.total_changes

    def _row_to_request(self, row):
        if not row:
            return None
        return ApprovalRequest(
            approval_id=row["approval_id"],
            jev_id=row["jev_id"],
            agent=row["agent"],
            title=row["title"],
            state=row["state"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
            review_notes=row["review_notes"] or "",
        )

    def stats(self):
        """Get approval statistics."""
        rows = self.db.cx.execute(
            "SELECT state, COUNT(*) c FROM approvals GROUP BY state"
        ).fetchall()
        return {r["state"]: r["c"] for r in rows}