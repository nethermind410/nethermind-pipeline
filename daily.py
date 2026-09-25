#!/usr/bin/env python3
"""daily.py — the Control agent's daily run (7:00 via launchd; see install_daily.sh).

    python3 daily.py            refresh → learn → scout 3 ideas → draft the next Short → (Sundays) draft the week's long-form
    python3 daily.py --dry      say what it would draft, change nothing

It never builds or posts: the draft waits in Today for your approval (Draft → you approve → build).
Which topic: the idea you pinned "Make this next", else your newest "Make it" scorecard not yet made,
else the top of TOPICS.md → Intelligence picks, else the first open idea. If a draft is already
waiting for you, it doesn't pile another one on top.
Runs at 7:00 and again at 20:30: the evening slot does nothing if the morning run completed, and
retries it if it failed (e.g. the Claude usage limit, which resets during the day). If the Mac was
asleep, launchd runs it on wake; if it still hasn't run for 26 hours, Today says so.
"""
import datetime, json, re, subprocess, sys
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
PY = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable


def _norm(t):
    return re.sub(r"[^a-z0-9]+", " ", str(t).lower()).strip()


def drafted_topics():
    """Every topic the Content agent has already drafted (waiting, approved or built) — by topic text, not by
    slug, because cfg ids and idea slugs are cut to different lengths."""
    seen = set()
    for p in (HERE / "out" / "drafts").glob("*.json") if (HERE / "out" / "drafts").exists() else []:
        try:
            seen.add(_norm(json.loads(p.read_text()).get("topic", "")))
        except Exception:
            pass
    for p in (HERE / "cfg").glob("*.json"):
        seen.add(_norm(p.stem.replace("_", " ")))
        try:
            d = json.loads(p.read_text()).get("draft")
            if d:
                seen.add(_norm(d.get("topic", "")))
        except Exception:
            pass
    seen.discard("")
    return seen


def pick_topic(skip=()):
    import studio_api, learning
    done = drafted_topics() | {_norm(t) for t in skip}
    fresh = lambda t: _norm(t) not in done
    nxt = studio_api.jload(studio_api.NEXT, None)
    if nxt and nxt.get("hook") and fresh(nxt["hook"]):
        return nxt["hook"], "you pinned it as Make this next"
    for c in sorted(learning._cards(), key=lambda c: c.get("at", ""), reverse=True):
        d = c.get("decision") or {}
        if d.get("choice") == "make" and not c.get("made_as") and fresh(c["topic"]):
            return c["topic"], f"you said Make it to its scorecard ({c['score']}/100)"
    sections = studio_api.ideas()["sections"]
    for s in sections:
        if s["name"].startswith("Intelligence picks"):
            for i in s["items"]:
                if not i["dismissed"] and fresh(i["hook"]):
                    return i["hook"], "top of Intelligence picks"
    lanes = ("marvel", "anime", "gaming")                # the channel's lanes first — never drift back to old backlogs
    rank = lambda s: next((n for n, k in enumerate(lanes) if s["name"].lower().startswith(k)), len(lanes))
    for s in sorted(sections, key=rank):
        for i in s["items"]:
            if not i["made"] and not i["dismissed"] and fresh(i["hook"]):
                return i["hook"], f"next open idea in {s['name']}"
    return None, "no open ideas left"


def scout_backlog(n=3):
    """Investigate up to n open ideas that have no scorecard yet. A failing scout never stops the run."""
    import studio_api, intelligence
    have = {p.stem for p in (HERE / "out" / "intel").glob("*.json")} if (HERE / "out" / "intel").exists() else set()
    done = []
    lanes = ("intelligence picks", "marvel", "anime", "gaming")     # score the channel's lanes first
    rank = lambda s: next((k for k, name in enumerate(lanes) if s["name"].lower().startswith(name)), len(lanes))
    for s in sorted(studio_api.ideas()["sections"], key=rank):
        for i in s["items"]:
            if len(done) >= n:
                return done
            if i["made"] or i["dismissed"] or intelligence.slug(i["hook"]) in have:
                continue
            try:
                c = intelligence.investigate(i["hook"])
                done.append(f"{c['score']}/100 {i['hook'][:60]}")
            except (Exception, SystemExit) as e:
                done.append(f"failed: {i['hook'][:40]} ({type(e).__name__})")
                if "quota" in str(e).lower():
                    return done
    return done


def pick_long_topic():
    """A long-form wants a big topic: an iceberg idea from the backlog first, else the best open idea."""
    import studio_api
    done = drafted_topics() | {_norm(json.loads(p.read_text()).get("draft", {}).get("topic", ""))
                               for p in (HERE / "episodes").glob("*.json") if not p.stem.startswith("_")}
    items = [(s["name"], i) for s in studio_api.ideas()["sections"] for i in s["items"]
             if not i["made"] and not i["dismissed"] and _norm(i["hook"]) not in done]
    for name, i in items:
        if "iceberg" in i["hook"].lower() and any(k in (name + i["hook"]).lower() for k in ("marvel", "gaming", "game", "anime", "comic")):
            return i["hook"], "an iceberg idea in your lanes"
    for name, i in items:
        if name.lower().startswith(("marvel", "anime", "gaming", "intelligence")):
            return i["hook"], f"open idea ({name})"
    return (items[0][1]["hook"], "first open idea") if items else (None, "no open ideas")


def main(dry=False):
    import drafter
    if dry:
        topic, why = pick_topic()
        waiting = [d["id"] for d in drafter.drafts()]
        print(f"would draft: {topic!r} — {why}" + (f" (but {waiting} still waiting, so it would skip)" if waiting else ""))
        return
    last = nether.last("control", "daily")
    if last and last["status"] == "complete" and last["started"][:10] == nether.now()[:10] and "--force" not in sys.argv:
        print("Today's run already completed — nothing to do (this is the 20:30 catch-up slot).")
        return
    parent = nether.begin("control", f"Daily run {datetime.date.today():%a %-d %b}", sub="daily",
                          retry={"kind": "daily"})
    report, cur = {}, None
    try:
        cur = nether.begin("analytics", "Numbers refresh + learning loop", sub="stats", parent=parent)
        r = subprocess.run(["./refresh.sh"], cwd=HERE, capture_output=True, text=True, timeout=900, env={"PY": PY, **__import__("os").environ})
        (nether.finish if r.returncode == 0 else nether.fail)(cur, (r.stdout + r.stderr)[-2000:])
        report["refresh"] = r.returncode == 0

        cur = nether.begin("intelligence", "Scout 3 backlog ideas", sub="demand", parent=parent)
        scouted = scout_backlog(3)                      # scorecards for you to call (YouTube quota only, no Claude)
        nether.finish(cur, {"scouted": scouted})
        report["scouted"] = scouted

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
                if why.startswith("you pinned"):          # the pin is used up: tomorrow picks the next topic
                    import studio_api
                    studio_api.set_next("", "")
        if datetime.date.today().weekday() == 6:          # Sundays: the week's long-form, written for your approval
            import drafter_long
            cur = nether.begin("content", "Draft the weekly long-form", sub="episodes", parent=parent)
            if drafter_long.drafts():
                nether.finish(cur, {"skipped": "a long-form is still waiting for your approval"})
                report["long"] = "skipped — one is still waiting for you"
            else:
                topic, why = pick_long_topic()
                nether.finish(cur, {"topic": topic, "why": why})
                cur = None
                if topic:
                    try:
                        report["long"] = drafter_long.draft(topic)   # its own Content task shows any failure
                    except (Exception, SystemExit) as e:
                        report["long"] = f"failed: {type(e).__name__}: {e}"
        cur = None
        nether.finish(parent, report)
        print(json.dumps(report, indent=1))
    except (Exception, SystemExit) as e:                # never leave the run stuck on "working"
        if cur:
            nether.fail(cur, f"{type(e).__name__}: {e}")
        nether.fail(parent, f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
