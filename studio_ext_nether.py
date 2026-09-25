"""Studio extension: NETHER — agents, tasks, Intelligence scorecards and what the system has learned.

GET  /api/system            every agent + sub-agent's live state (working / failed / ready) and task counts
GET  /api/tasks             recent tasks with their steps, errors and retry info
GET  /api/learning          scorecards, your decisions, current score weights, lessons
POST /api/intel/run         {"topic"} → starts an investigation in the background
POST /api/intel/decide      {"slug", "choice": "make"|"skip", "reason"} → your call on a scorecard
POST /api/tasks/cancel      {"id"} → cancel a stuck task
POST /api/learning/run      re-link, re-weight and rewrite the lessons now

Retrying a Studio job (build, post, refresh…) goes through the existing /api/run
with the task's stored retry {"action", "id"}; an investigation re-runs here.
"""
import threading

import intelligence
import learning
import orchestrator as nether

_RUNNING = {"topic": None}


def _investigate(topic):
    try:
        intelligence.investigate(topic)
    except Exception:
        pass            # the failure is already on the task; the page shows it
    finally:
        _RUNNING["topic"] = None


def system():
    s = nether.system()
    s["investigating"] = _RUNNING["topic"]
    return s


def run_intel(body):
    topic = str(body.get("topic", "")).strip()[:120]
    if not topic:
        raise ValueError("Type a topic first.")
    if _RUNNING["topic"]:
        raise ValueError(f"Still investigating \"{_RUNNING['topic']}\" — one at a time.")
    _RUNNING["topic"] = topic
    threading.Thread(target=_investigate, args=(topic,), daemon=True).start()
    return {"ok": True, "reply": f"Intelligence is on it: {topic}"}


def decide(body):
    return learning.decide(str(body.get("slug", "")), str(body.get("choice", "")), body.get("reason", ""))


def cancel(body):
    try:
        return nether.cancel(int(body.get("id")))
    except (TypeError, ValueError):
        raise ValueError("Which task?")


def relearn(body):
    r = learning.run()
    return {"ok": True, "reply": f"Learning loop done — {len(r['linked'])} new link(s).", **r}


GET = {"/api/system": system, "/api/tasks": lambda: nether.tasks(25), "/api/learning": learning.summary}
POST = {"/api/intel/run": run_intel, "/api/intel/decide": decide, "/api/tasks/cancel": cancel,
        "/api/learning/run": relearn}
