from clipping_farm.db import DB
from clipping_farm.runner import PipelineRunner


def test_runner_drains_ready_jobs(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    first, _ = db.add_job(
        "first",
        "agent",
        {},
        idempotency_key="first",
    )
    second, _ = db.add_job(
        "second",
        "agent",
        {},
        idempotency_key="second",
        depends_on=[first["id"]],
    )

    calls = []

    def handler(job):
        calls.append(job["task"])
        return {"decision": "complete", "actual_cost": 0}

    runner = PipelineRunner(
        db,
        {"first": handler, "second": handler},
        capabilities=["first", "second"],
    )

    result = runner.run(
        "test-source",
        {"first": first["id"], "second": second["id"]},
    )

    assert result.state == "COMPLETE"
    assert result.processed == 2
    assert calls == ["first", "second"]
    assert result.jobs["first"]["state"] == "COMPLETE"
    assert result.jobs["second"]["state"] == "COMPLETE"


def test_runner_reports_dead_letter(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    job, _ = db.add_job(
        "broken",
        "agent",
        {},
        idempotency_key="broken",
        max_attempts=1,
    )

    def handler(job):
        raise RuntimeError("intentional failure")

    runner = PipelineRunner(
        db,
        {"broken": handler},
        capabilities=["broken"],
    )

    result = runner.run("test-source", {"broken": job["id"]})

    assert result.state == "FAILED"
    assert result.processed == 1
    assert result.jobs["broken"]["state"] == "DEAD_LETTER"


def test_runner_reports_stalled_pipeline(tmp_path):
    db = DB(tmp_path / "db.sqlite")

    missing_dependency = "does-not-exist"

    job, _ = db.add_job(
        "blocked",
        "agent",
        {},
        idempotency_key="blocked",
        depends_on=[missing_dependency],
    )

    runner = PipelineRunner(
        db,
        {"blocked": lambda job: {"actual_cost": 0}},
        capabilities=["blocked"],
    )

    result = runner.run("test-source", {"blocked": job["id"]})

    assert result.state == "STALLED"
    assert result.processed == 0
    assert result.jobs["blocked"]["state"] == "PENDING"
