"""Studio extension: Control's repair desk — why a job failed, and sending it back to be fixed.

GET  /api/fixes            open fix tickets (newest first)
POST /api/fix/diagnose     {"task"} or {"job": true} → department, what happened, what fixes it
POST /api/fix/send         {"task"} → retry advice, or a fix ticket for broken code
POST /api/fix/start        {"n"} → Claude repairs ticket n on its own branch (never your checkout)
POST /api/fix/apply        {"n"} → merge the finished repair (you approved it)
POST /api/fix/discard      {"n"} → throw the repair away and clear the ticket
"""
import datetime

import orchestrator as nether
import repair


def _job_task():
    import sys
    studio = next(m for m in (sys.modules.get("studio"), sys.modules.get("__main__")) if m is not None and hasattr(m, "JOB"))
    with studio.LOCK:                                   # the running server's job (app.py imports studio; `python studio.py` is __main__)
        job = dict(studio.JOB)
    if job.get("task"):
        return nether.task(job["task"])
    since = (datetime.datetime.now().astimezone() - datetime.timedelta(minutes=15)).isoformat()
    for t in nether.tasks(10):
        if t["status"] == "failed" and (t.get("finished") or t["created"]) >= since:
            return t
    return {"id": 0, "agent": "control", "sub": None, "title": job.get("label") or "Last job", "steps": [],
            "error": ((job.get("friendly") or "") + "\n" + (job.get("log") or ""))[-4000:], "retry": {"action": job.get("action"), "id": job.get("video")}}


def diagnose(b):
    t = _job_task() if b.get("job") else nether.task(int(b.get("task") or 0))
    if not t:
        raise ValueError("That task isn't in the log any more.")
    return repair.diagnose(t)


def send(b):
    tid = b.get("task")
    if not tid and b.get("job"):
        tid = (_job_task() or {}).get("id")
    if not tid:
        raise ValueError("This job wasn't logged as a task, so it can't be sent to fix — Retry it instead.")
    return repair.send(int(tid))


GET = {"/api/fixes": repair.tickets}
POST = {"/api/fix/diagnose": diagnose, "/api/fix/send": send, "/api/fix/start": lambda b: repair.start_fix(b.get("n")),
        "/api/fix/apply": lambda b: repair.apply(b.get("n")), "/api/fix/discard": lambda b: repair.discard(b.get("n"))}
