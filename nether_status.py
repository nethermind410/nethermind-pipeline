#!/usr/bin/env python3
"""nether_status.py — out/jarvis_status.md (+ .json): a plain-English brief Jarvis reads aloud
when Courtney asks what NETHER wants today, whether a video is ready, or when it posts.

Jarvis only reads files under out/ — no network to NETHER — so this is the one file it starts
with. write() rebuilds it from the same data Today already reads (studio_ext_day, studio_api,
quality_gate, best_times, studio_ext_desk, studio_ext_ownvoice, the job queue, orchestrator,
alerts, repair) and nothing else: no network calls, no paid AI, nothing that costs money.

Every section is wrapped in its own try/except — one broken section says so in one plain
sentence instead of stopping the rest of the brief from being written. write() itself never
raises; call it and move on.

    python3 nether_status.py        write both files now, print the markdown

Called from:
  studio.py               once when the server starts, and again after every job finishes
  studio_ext_status.py    a daemon thread, every 15 minutes
  daily.py                once at the end of the morning run
"""
import datetime, json, sys
from pathlib import Path

from channel import DATA
from store import atomic_write_text, atomic_write_json

OUT = DATA / "out"
MD = OUT / "jarvis_status.md"
JS = OUT / "jarvis_status.json"


def _now():
    return datetime.datetime.now().astimezone()


def _spoken_time(dt):
    """"Sunday 4:30 PM" — no seconds, no timezone, nothing a voice would stumble on."""
    return dt.strftime("%A %-I:%M %p")


def _spoken_when(dt, now):
    """"today 4:30 PM" / "tomorrow 11:00 AM" / "Tuesday 7:00 PM" — same words best_times.py uses."""
    if dt is None:
        return None
    if dt.date() == now.date():
        day = "today"
    elif dt.date() == (now.date() + datetime.timedelta(days=1)):
        day = "tomorrow"
    else:
        day = dt.strftime("%A")
    return f"{day} {dt.strftime('%-I:%M %p')}"


PLATFORM_NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


# ------------------------------------------------------------------ gather (each piece is cheap: local files only)
def _gather_next_step():
    import studio_ext_day as day
    d = day.day()
    first = d["post"]
    return {"title": first["title"], "why": first["why"], "done": bool(first["done"]),
            "left": d.get("left"), "streak": d.get("streak"), "out": d.get("out")}


def _gather_reviews(vids):
    import quality_gate
    out = []
    for v in vids:
        if v["stage"] != "ready":
            continue
        try:
            g = quality_gate.check(v["id"])
            blockers = [c["detail"] for c in g["checks"] if not c["ok"] and c["level"] == "block"]
            out.append({"id": v["id"], "title": v["title"], "pass": g["pass"], "score": g["score"], "blockers": blockers})
        except Exception as e:
            out.append({"id": v["id"], "title": v["title"], "pass": None, "score": None,
                        "blockers": [f"the quality check itself failed ({type(e).__name__})"]})
    return out


def _gather_scheduled(vids, now):
    import studio_api
    scheduled = []
    ready_unscheduled = []
    for v in vids:
        if v["scheduled"]:
            for s in v["scheduled"]:
                dt = studio_api.parse_dt(s.get("dueAt"))
                scheduled.append({"video": v["id"], "title": v["title"], "platform": s.get("platform"),
                                  "when_iso": s.get("dueAt"), "when_spoken": _spoken_when(dt, now) if dt else None})
        elif v["stage"] == "ready":
            ready_unscheduled.append(v)
    scheduled.sort(key=lambda s: s["when_iso"] or "")
    next_slots = []
    if ready_unscheduled:
        import best_times
        for v in ready_unscheduled:
            slots = {}
            for plat in ("youtube", "tiktok", "instagram"):
                try:
                    slots[plat] = best_times.describe(plat, now)["local"]
                except Exception:
                    pass
            if slots:
                next_slots.append({"video": v["id"], "title": v["title"], "slots": slots})
    return scheduled, next_slots


def _gather_long():
    import studio_ext_desk as desk
    w = desk.week()
    long = w.get("long")
    if not long:
        return None
    info = {"id": long["id"], "title": long["title"], "stage": long["stage"], "voice": None, "needs_checking": None}
    if long["stage"] in ("ready", "scheduled", "live"):
        info["render"] = "rendered"
    elif long["stage"] == "making":
        info["render"] = "not rendered yet"
    else:
        info["render"] = "still a script"
    try:
        import studio_ext_ownvoice as ownvoice
        st = ownvoice.status(long["id"])
        if st["own_voice"]:
            info["voice"] = "recorded" if st["complete"] else ("partly recorded" if st["recorded"] else "needs recording")
    except Exception:
        pass
    try:
        ep_path = DATA / "episodes" / f"{long['id']}.json"
        ep = json.loads(ep_path.read_text()) if ep_path.exists() else {}
        info["needs_checking"] = bool(ep.get("confirm"))
    except Exception:
        pass
    return info


def _gather_queue(by_id):
    def title_for(raw):
        vid = str(raw or "").split("|", 1)[0]
        return (by_id.get(vid) or {}).get("title") or vid

    def relabel(q):
        raw, label = str(q.get("video") or ""), str(q.get("label") or "")
        title = title_for(raw)
        return label.replace(raw, f'"{title}"') if raw and raw in label else label

    try:
        q = json.loads((OUT / "queue.json").read_text())
    except Exception:
        return {"running": None, "queued": []}
    running = q.get("running")
    return {"running": {"label": relabel(running)} if running else None,
            "queued": [{"label": relabel(x)} for x in (q.get("queue") or [])]}


def _gather_broken():
    out = []
    try:
        import alerts
        state = alerts.load().get("state") or {}
        out += [f"{name} needs a look." for name, ok in state.items() if not ok]
    except Exception as e:
        out.append(f"I couldn't check alerts ({type(e).__name__}).")
    try:
        import orchestrator
        for a in orchestrator.system()["agents"]:
            if a["state"] == "failed":
                out.append(f"{a['name']} failed on its last run.")
    except Exception as e:
        out.append(f"I couldn't check the agents ({type(e).__name__}).")
    try:
        import repair
        for t in repair.tickets():
            if t.get("state") in ("open", "working"):
                out.append(f"Fix ticket open: {t['title']}.")
    except Exception as e:
        out.append(f"I couldn't check fix tickets ({type(e).__name__}).")
    return out


# ------------------------------------------------------------------ build
def _build(now):
    data = {"updated": now.isoformat(timespec="minutes"), "updated_spoken": _spoken_time(now), "errors": []}

    def section(key, fn, *args):
        try:
            data[key] = fn(*args)
        except Exception as e:
            data[key] = None
            data["errors"].append(f"I couldn't check {key.replace('_', ' ')} ({type(e).__name__}).")

    section("next_step", _gather_next_step)

    vids, by_id = [], {}
    try:
        import studio_api
        vids = studio_api.videos()
        by_id = {v["id"]: v for v in vids}
    except Exception as e:
        data["errors"].append(f"I couldn't read the video list ({type(e).__name__}).")

    section("reviews", _gather_reviews, vids)
    try:
        data["scheduled"], data["next_slots"] = _gather_scheduled(vids, now)
    except Exception as e:
        data["scheduled"], data["next_slots"] = [], []
        data["errors"].append(f"I couldn't check scheduled posts ({type(e).__name__}).")
    section("long_form", _gather_long)
    section("queue", _gather_queue, by_id)
    section("broken", _gather_broken)
    return data


def _md(data):
    p = [f"Updated {data['updated_spoken']}.", ""]

    ns = data.get("next_step")
    if ns:
        p.append(f"Today's next step: {ns['title']}. {ns['why']}")
        extra = (ns.get("left") or 0) - (0 if ns.get("done") else 1)
        if extra > 0:
            p.append(f"There {'is' if extra == 1 else 'are'} also {extra} other thing{'' if extra == 1 else 's'} on today's list.")
    else:
        p.append("I couldn't check today's next step.")
    p.append("")

    reviews = data.get("reviews") or []
    if reviews:
        p.append(f"{len(reviews)} video{'' if len(reviews) == 1 else 's'} waiting for your review.")
        for r in reviews:
            if r["pass"] is None:
                p.append(f"\"{r['title']}\": {r['blockers'][0]}")
            elif r["pass"]:
                p.append(f"\"{r['title']}\" is ready to post, quality score {r['score']} out of 100.")
            else:
                p.append(f"\"{r['title']}\" is not ready, quality score {r['score']} out of 100. "
                         f"Blocked by: {'; '.join(r['blockers']) or 'an unresolved check'}.")
    else:
        p.append("Nothing is waiting for review right now.")
    p.append("")

    sched = data.get("scheduled") or []
    if sched:
        p.append("Scheduled posts:")
        for s in sched:
            plat = PLATFORM_NAMES.get(s["platform"], s["platform"] or "a platform")
            when = s["when_spoken"] or "at an unknown time"
            p.append(f"\"{s['title']}\" goes out on {plat} {when}.")
    slots = data.get("next_slots") or []
    for n in slots:
        parts = [f"{PLATFORM_NAMES.get(k, k)} {v}" for k, v in n["slots"].items()]
        p.append(f"\"{n['title']}\" is ready but not scheduled — if you schedule it now: " + ", ".join(parts) + ".")
    if not sched and not slots:
        p.append("Nothing is scheduled, and nothing is waiting to be scheduled.")
    p.append("")

    lf = data.get("long_form")
    if lf:
        bits = [f"This week's long-form is \"{lf['title']}\"."]
        if lf.get("voice") == "needs recording":
            bits.append("It's approved and waiting for your voiceover.")
        elif lf.get("voice") == "partly recorded":
            bits.append("Your recording is partly in — some lines still need it.")
        elif lf.get("voice") == "recorded":
            bits.append("Your recording is in.")
        bits.append("It has been rendered." if lf.get("render") == "rendered"
                    else "It hasn't been rendered yet." if lf.get("render") == "not rendered yet"
                    else "It's still a script, waiting for approval.")
        if lf.get("needs_checking"):
            bits.append("It has facts flagged to double check before it goes out.")
        p.append(" ".join(bits))
    else:
        p.append("No long-form episode is in progress this week.")
    p.append("")

    q = data.get("queue") or {"running": None, "queued": []}
    if q.get("running"):
        p.append(f"Right now, running: {q['running']['label']}.")
    else:
        p.append("Nothing is running right now.")
    if q.get("queued"):
        p.append(f"{len(q['queued'])} job{'' if len(q['queued']) == 1 else 's'} queued: " +
                 "; ".join(x["label"] for x in q["queued"]) + ".")
    p.append("")

    broken = data.get("broken") or []
    if broken:
        p.append("Things that need a look:")
        p.extend(broken)
    else:
        p.append("Nothing is broken right now.")

    if data.get("errors"):
        p.append("")
        p.extend(data["errors"])

    return "\n".join(p).strip() + "\n"


def write(now=None):
    """Rebuild out/jarvis_status.md and .json. Never raises — a total failure still leaves a
    short, honest note in place of the usual brief."""
    try:
        data = _build(now or _now())
        md = _md(data)
        atomic_write_text(MD, md)
        atomic_write_json(JS, data)
        return md
    except Exception as e:
        try:
            atomic_write_text(MD, f"I couldn't build NETHER's status brief right now ({type(e).__name__}). "
                                  "Open Nethermind Studio to see what's going on.\n")
        except Exception:
            pass
        return None


if __name__ == "__main__":
    out = write()
    print(out if out else "write() failed — see out/jarvis_status.md for the fallback note.", end="")
    sys.exit(0)
