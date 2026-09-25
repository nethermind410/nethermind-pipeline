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


def brief():
    """Intelligence's brief: what to make next and why, how each lane really performs, what's working elsewhere."""
    import statistics, studio_api
    cards = learning._cards()
    views = learning._views()
    ours = intelligence._our_videos()
    avg = statistics.mean(v["views"] for v in ours) if ours else 0
    lanes = {}
    for v in ours:
        lanes.setdefault(v["lane"], []).append(v["views"])
    lane_rows = sorted(({"lane": k, "videos": len(vs), "avg": round(statistics.mean(vs)), "ratio": round(statistics.mean(vs) / avg, 2) if avg else None}
                        for k, vs in lanes.items()), key=lambda r: -r["avg"])
    # a weekly mix that follows the numbers: 7 slots, ≥1 for any lane with 2+ videos, the rest by performance
    proven = [r for r in lane_rows if r["videos"] >= 2]
    mix = {}
    if proven:
        mix = {r["lane"]: 1 for r in proven}
        weight = {r["lane"]: max(r["ratio"] or 0, 0.1) for r in proven}
        for _ in range(max(0, 7 - len(mix))):
            best = max(weight, key=lambda k: weight[k] / (mix[k] + 1))
            mix[best] += 1
    open_cards = sorted((c for c in cards if not c.get("decision")), key=lambda c: -c.get("score", 0))
    recs = [{"topic": c["topic"], "slug": c["slug"], "score": c["score"], "lane": c["lane"], "verdict": c["verdict"],
             "why": c["reasons"][:3], "failed": list(c.get("failed", {}))} for c in open_cards[:3]]
    breakouts, seen = [], set()
    for c in sorted(cards, key=lambda c: c.get("at", ""), reverse=True):
        for b in (c.get("evidence", {}).get("competitors", {}) or {}).get("breakouts", []):
            if b.get("url") not in seen:
                seen.add(b.get("url"))
                breakouts.append({**b, "topic": c["topic"]})
    ideas = [i for s in studio_api.ideas()["sections"] for i in s["items"] if not i["made"] and not i["dismissed"]]
    scored = {c["slug"] for c in cards}
    L = learning.summary()
    return {"recommendations": recs, "lanes": lane_rows, "channel_avg": round(avg), "mix": mix,
            "breakouts": breakouts[:6], "backlog": {"open": len(ideas), "scored": sum(1 for i in ideas if intelligence.slug(i["hook"]) in scored)},
            "decided": sum(1 for c in cards if c.get("decision")), "linked": sum(1 for c in cards if c.get("made_as") in views),
            "weights": L["weights"], "default": L["default"], "lessons": L["lessons"][:4],
            "investigating": _RUNNING["topic"]}


GET = {"/api/system": system, "/api/intel/brief": brief, "/api/tasks": lambda: nether.tasks(25), "/api/learning": learning.summary}
POST = {"/api/intel/run": run_intel, "/api/intel/decide": decide, "/api/tasks/cancel": cancel,
        "/api/learning/run": relearn}
