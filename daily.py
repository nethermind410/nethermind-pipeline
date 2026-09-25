#!/usr/bin/env python3
"""daily.py — the Control agent's daily run (7:00 via launchd; see install_daily.sh).

    python3 daily.py            refresh → learn → draft the next video → (Sundays) plan the weekly episode
    python3 daily.py --dry      say what it would draft, change nothing

It never builds or posts: the draft waits in Today for your approval (Draft → you approve → build).
Which topic: the idea you pinned "Make this next", else your newest "Make it" scorecard not yet made,
else the top of TOPICS.md → Intelligence picks, else the first open idea. If a draft is already
waiting for you, it doesn't pile another one on top.
If the Mac was asleep at 7:00, launchd runs it on wake; if it still hasn't run for 26 hours,
Today says so.
"""
import datetime, json, subprocess, sys
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
PY = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable


def pick_topic():
    import studio_api, learning
    nxt = studio_api.jload(studio_api.NEXT, None)
    if nxt and nxt.get("hook"):
        return nxt["hook"], "you pinned it as Make this next"
    made = {p.stem for p in (HERE / "cfg").glob("*.json")}
    for c in sorted(learning._cards(), key=lambda c: c.get("at", ""), reverse=True):
        d = c.get("decision") or {}
        if d.get("choice") == "make" and not c.get("made_as") and c["slug"] not in made:
            return c["topic"], f"you said Make it to its scorecard ({c['score']}/100)"
    sections = studio_api.ideas()["sections"]
    for s in sections:
        if s["name"].startswith("Intelligence picks"):
            for i in s["items"]:
                if not i["dismissed"] and i["slug"] not in made:
                    return i["hook"], "top of Intelligence picks"
    for s in sections:
        for i in s["items"]:
            if not i["made"] and not i["dismissed"] and i["slug"] not in made:
                return i["hook"], f"first open idea ({s['name']})"
    return None, "no open ideas left"


def main(dry=False):
    import drafter
    if dry:
        topic, why = pick_topic()
        waiting = [d["id"] for d in drafter.drafts()]
        print(f"would draft: {topic!r} — {why}" + (f" (but {waiting} still waiting, so it would skip)" if waiting else ""))
        return
    parent = nether.begin("control", f"Daily run {datetime.date.today():%a %-d %b}", sub="daily",
                          retry={"kind": "daily"})
    report, cur = {}, None
    try:
        cur = nether.begin("analytics", "Numbers refresh + learning loop", sub="stats", parent=parent)
        r = subprocess.run(["./refresh.sh"], cwd=HERE, capture_output=True, text=True, timeout=900, env={"PY": PY, **__import__("os").environ})
        (nether.finish if r.returncode == 0 else nether.fail)(cur, (r.stdout + r.stderr)[-2000:])
        report["refresh"] = r.returncode == 0

        waiting = [d["id"] for d in drafter.drafts()]
        cur = nether.begin("content", "Draft the next video", sub="script", parent=parent)
        if waiting:
            nether.finish(cur, {"skipped": f"{waiting[0]} is still waiting for your approval"})
            report["draft"] = f"skipped — {waiting[0]} still waiting for you"
        else:
            topic, why = pick_topic()
            if not topic:
                nether.finish(cur, {"skipped": why})
                report["draft"] = why
            else:
                cur_topic = topic
                nether.finish(cur, {"topic": topic, "why": why})
                cur = None
                vid = drafter.draft(cur_topic)          # its own Content task, with research/script/packaging steps
                report["draft"] = f"{vid} ({why})"
        if datetime.date.today().weekday() == 6:
            import episode
            cur = nether.begin("content", "Plan the weekly episode", sub="episodes", parent=parent)
            try:
                eid = episode.weekly()
                nether.finish(cur, {"episode": eid})
                report["episode"] = eid
            except ValueError as e:                     # too few Shorts this week isn't a failure of the run
                nether.finish(cur, {"skipped": str(e)})
                report["episode"] = str(e)
        cur = None
        nether.finish(parent, report)
        print(json.dumps(report, indent=1))
    except Exception as e:
        if cur:
            nether.fail(cur, f"{type(e).__name__}: {e}")
        nether.fail(parent, f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
