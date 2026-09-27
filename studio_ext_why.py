"""Studio extension: the shared "Why?" + confidence + override-learning plumbing used by every
AI choice the user sees (topic, title, hook, posting time). No new AI calls — each caller hands
this module a plain confidence word from numbers it already has (sample size, score, verdict),
and this module downgrades it one step, with an honest note, once you've overridden the same
kind+lane 3+ times recently. That history is the whole "learning" here: nothing fancier.

POST /api/override   {"kind","lane","ai","user"} -> record one override (what AI chose, what you
                      picked instead, for which kind of choice and which lane/topic-area)
GET  /api/why/overrides  the last 100 overrides, for the brain / debugging

Written to out/overrides.json (atomic writes via store.py), capped at 500 rows.
"""
import datetime

from channel import DATA
from store import atomic_write_json, locked
import studio_api as api

OUT = DATA / "out" / "overrides.json"
WINDOW_DAYS = 60      # only recent overrides count toward the confidence nudge
NUDGE_AT = 3          # this many overrides of the same kind+lane -> drop confidence a level
LEVELS = ["low", "medium", "high"]


def _load():
    return api.jload(OUT, []) or []


def record(body):
    kind = str(body.get("kind", "")).strip()[:20]
    lane = str(body.get("lane", "") or "general").strip()[:40]
    ai_choice = str(body.get("ai", "")).strip()[:300]
    user_choice = str(body.get("user", "")).strip()[:300]
    if not kind or not user_choice:
        raise ValueError("Missing what was chosen.")
    with locked(OUT):
        rows = _load()
        rows.append({"kind": kind, "lane": lane, "ai": ai_choice, "user": user_choice,
                      "changed": ai_choice != "" and ai_choice != user_choice,
                      "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
        atomic_write_json(OUT, rows[-500:])
    return {"ok": True}


def recent_override_count(kind, lane):
    if not kind or not lane:
        return 0
    cutoff = (datetime.datetime.now().astimezone() - datetime.timedelta(days=WINDOW_DAYS)).isoformat()
    return sum(1 for r in _load()
               if r.get("kind") == kind and r.get("lane") == lane and r.get("changed") and r.get("at", "") >= cutoff)


def confidence(level, kind=None, lane=None):
    """level: "high"/"medium"/"low" from the caller's own numbers (sample size, score, verdict).
    Returns {"level": "High"/"Medium"/"Low", "note": ""} — note is set (and level dropped one
    step) once you've overridden this same kind+lane 3+ times in the last 60 days."""
    level = level if level in LEVELS else "medium"
    n = recent_override_count(kind, lane)
    note = ""
    if n >= NUDGE_AT:
        level = LEVELS[max(0, LEVELS.index(level) - 1)]
        note = f"you've changed this {n} times recently"
    return {"level": level.capitalize(), "note": note}


def overrides_view():
    return {"overrides": _load()[-100:]}


def confidence_path(rest):
    """GET /api/why/confidence/<kind>/<lane>/<level> -> confidence(), for a choice (like the topic
    picker) that already knows its own level client-side but needs the override-learning nudge."""
    parts = [p for p in rest.strip("/").split("/") if p]
    if len(parts) != 3:
        raise ValueError("Bad path — want /api/why/confidence/<kind>/<lane>/<level>.")
    kind, lane, level = parts
    return confidence(level, kind=kind, lane=lane)


GET = {"/api/why/overrides": overrides_view}
GET_PREFIX = {"/api/why/confidence/": confidence_path}
POST = {"/api/override": record}
