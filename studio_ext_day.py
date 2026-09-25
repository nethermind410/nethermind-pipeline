"""Studio extension: Today's run — one tap walks you through everything today needs, posting first.

GET  /api/day        {"date", "post": the baseline (is today's Short out?), "steps": [...], "left": n}

The baseline is the cadence: one Short goes out every day, so step 1 is always about today's Short — post it,
finish building it, approve its script, or draft one — until it's live or scheduled. Then the rest of today's
jobs, in the order that matters: the long-form, scripts to approve, finishing live videos, Intelligence's calls,
comments, and anything broken.

    python3 studio_ext_day.py remind      a macOS notification if today's Short isn't out (daily.py runs this
                                          at 7:00 and at the 20:30 catch-up)
"""
import datetime, shutil, subprocess, sys

import studio_ext_desk as desk


def _step(key, title, why, go, kind, done=False):
    return {"key": key, "title": title, "why": why, "go": go, "kind": kind, "done": done}


def post_step():
    w = desk.week()
    today = next(d for d in w["days"] if d["today"])
    st, t, vid = today.get("stage"), today.get("title", ""), today.get("id", "")
    if st in ("live", "scheduled"):
        return _step("post", f"Today's Short is {'live' if st == 'live' else 'queued'}", f"“{t}” — nice. That's {w['out']} of 7 this week.",
                     f"video/{vid}", "post", True), w
    if st == "ready":
        return _step("post", "Post today's Short", f"“{t}” is rendered and checked. Open it and press Post — Buffer sends it to every platform.",
                     f"video/{vid}", "post"), w
    if st == "making":
        return _step("post", "Build today's Short", f"“{t}” is approved but not rendered yet. Open it and press Make video (about 5 minutes), then post it.",
                     f"video/{vid}", "post"), w
    if st == "draft":
        return _step("post", "Approve today's script", f"“{t}” is written. Read it, fix any line, approve — it builds, then you post it.",
                     f"draft/{vid}", "post"), w
    return _step("post", "Make today's Short", "Nothing is lined up for today. Draft one from the top idea (3–6 minutes), approve it, build, post.",
                 "make", "post"), w


def day():
    import studio_api
    first, w = post_step()
    steps, seen = [first], {first["go"].split("/")[-1]}
    if w.get("long") is None and datetime.date.today().weekday() >= 4:
        steps.append(_step("long", "Line up this week's long-form", "Nothing started yet — draft an iceberg or episode so Sunday has something to render.",
                           "desk/content/episodes", "make"))
    elif w.get("long") and w["long"]["stage"] in ("draft", "ready"):
        lg = w["long"]
        steps.append(_step("long", "Approve the long-form" if lg["stage"] == "draft" else "Post the long-form",
                           f"“{lg['title']}” — {'read the chapters and approve it to render' if lg['stage'] == 'draft' else 'rendered: upload to YouTube with its 3 thumbnails for Test & Compare'}.",
                           f"draft/{lg['id']}" if lg["stage"] == "draft" else f"video/{lg['id']}", "post"))
        seen.add(lg["id"])
    t = studio_api.today()
    for c in t["cards"]:
        vid = c.get("video") or ""
        if vid and vid in seen:
            continue
        k = c["kind"]
        if k == "draft":
            steps.append(_step(c["key"], "Approve a script", f"“{c['title']}” {c['text'].lstrip('— ')}", f"draft/{vid}", "approve"))
        elif k == "ready":
            steps.append(_step(c["key"], "Review a finished video", f"“{c['title']}” is ready — watch it and queue it for a coming day.", f"video/{vid}", "approve"))
        elif k == "finish":
            left = [s["label"] for s in c.get("steps", []) if not s["done"]]
            steps.append(_step(c["key"], "Finish a live video", f"“{c['title']}”: " + "; ".join(left[:3]), f"video/{vid}", "finish"))
        elif k == "queued":
            steps.append(_step(c["key"], "Check the queue", f"“{c['title']}” is waiting in Buffer — make sure the times look right.", f"video/{vid}", "finish"))
        elif k == "intel":
            steps.append(_step(c["key"], "Make a call on the scorecards", f"{c['title']} {c['text']}", "brief", "decide"))
        elif k == "missed":
            steps.append(_step(c["key"], "The daily run is quiet", c["text"], "desk/control/daily", "fix"))
        if vid:
            seen.add(vid)
    try:
        import studio_channel
        n = sum(1 for x in studio_channel.comments(studio_api.done_map())["comments"] if not x["done"])
        if n:
            steps.append(_step(f"comments:{n}", f"Reply to {n} comment{'s' if n > 1 else ''}", "Early replies turn viewers into regulars.", "comments", "nice"))
    except Exception:
        pass
    try:                                   # one money step a day, until the setup list is done
        import business
        todo = next((s for s in business.money()["setup"] if not s["done"]), None)
        if todo:
            steps.append(_step(f"setup:{todo['key']}", f"One money step: {todo['title']}", todo["how"], "money", "nice"))
    except Exception:
        pass
    try:
        import orchestrator
        bad = [a["name"] for a in orchestrator.system()["agents"] if a["state"] == "failed"]
        if bad:
            steps.append(_step("failed:" + ",".join(bad), f"{', '.join(bad)} need{'s' if len(bad) == 1 else ''} a look",
                               "Something broke — the Task log shows which step, with Retry.", "agents", "fix"))
    except Exception:
        pass
    return {"date": datetime.date.today().isoformat(), "post": first, "steps": steps,
            "left": sum(1 for s in steps if not s["done"]), "streak": w["streak"], "out": w["out"]}


def remind():
    """A Mac notification when today's Short isn't out yet. Quiet if it is, or if this isn't a Mac."""
    first, _ = post_step()
    if first["done"] or not shutil.which("osascript"):
        return first
    late = datetime.datetime.now().hour >= 18
    title = "Nothing's gone out today yet" if late else first["title"]
    body = first["why"].replace('"', "'")[:180]
    subprocess.run(["osascript", "-e", f'display notification "{body}" with title "Nethermind" subtitle "{title}" sound name "Glass"'],
                   capture_output=True, timeout=10)
    return first


GET = {"/api/day": day}

if __name__ == "__main__":
    if sys.argv[1:] == ["remind"]:
        print(remind()["title"])
    else:
        sys.exit(__doc__)
