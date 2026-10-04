
from clipping_farm.db import DB


def test_finish_clears_previous_error(tmp_path):
    db = DB(tmp_path / "test.db")

    job, _ = db.add_job(
        "metadata",
        "media_agent",
        {"source_id": "test-source"},
    )

    worker = "test-worker"
    db.cx.execute(
        "UPDATE jobs SET state='RUNNING', lease_owner=?, error=? WHERE id=?",
        (worker, "old failure", job["id"]),
    )

    db.finish(
        job["id"],
        worker,
        {"decision": "complete"},
    )

    row = db.cx.execute(
        "SELECT state, error FROM jobs WHERE id=?",
        (job["id"],),
    ).fetchone()

    assert row["state"] == "COMPLETE"
    assert row["error"] is None
