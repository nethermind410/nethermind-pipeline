"""Review export and hard publish approval gate."""
import json
from pathlib import Path

def write_review_manifest(path, source_id, clips, review_candidates=None):
    payload={"state":"READY_FOR_REVIEW","source_id":source_id,"clips":clips,"review_candidates":review_candidates or []}
    Path(path).write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return payload

def assert_publishable(db, job_id):
    row=db.cx.execute("SELECT state FROM approvals WHERE approval_id=? OR jev_id=?",(job_id,job_id)).fetchone()
    if not row or row["state"]!="APPROVED":
        raise PermissionError("Publishing blocked: explicit human approval required")
    return True
