#!/usr/bin/env python3
"""orchestrator.py — NETHER's agents, sub-agents and the task log behind them.

Every job the pipeline runs is a task owned by an agent and one of its
sub-agents. A multi-step job (a build, an investigation) is a parent task with
one child task per step, so when something breaks you can see which step it
was, the error it left, and retry it — from Studio's Agents page or the brain.

Task states: queued → working → waiting → complete | failed | cancelled

    python3 orchestrator.py                          agent status + recent tasks
    python3 orchestrator.py begin <agent> "<title>" [--video id] [--retry json]   prints task id
    python3 orchestrator.py step  <task> "<step name>"    closes the running step, opens the next
    python3 orchestrator.py end   <task> <exit code> [log file]   closes the task (fails the step that broke)

build.sh reports through the CLI; Studio's job runner and intelligence.py
through the functions. The log lives in out/nether.db (SQLite).
"""
import datetime, json, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "out" / "nether.db"
STALE_HOURS = 6        # a task still "working" after this long stopped without reporting (app closed mid-job)

# The whole system as agents. Each is a region of the brain (ax/ay: its anchor in the brain drawing,
# same 0–1 box as brain.js) and owns sub-agents. A sub-agent is (name, Studio page it opens or None,
# what it does). Pages are how you work with a sub-agent; tasks are how it reports its work.
AGENTS = {
    "intelligence": {"name": "Intelligence", "lobe": "Frontal lobe · planning", "role": "Finds topics worth making",
                     "ax": 0.3, "ay": 0.4, "subs": {
        "ideas": ("Ideas backlog", "ideas", "Every topic waiting to be made, ranked by real demand."),
        "demand": ("Demand scout", "investigate", "How many views similar Shorts got in the last year."),
        "competitors": ("Competitor scout", "investigate", "Who made them, and whether small channels are winning."),
        "fit": ("Channel-fit scout", "investigate", "How this lane has done on your own channel."),
        "rights": ("Visuals & rights scout", "investigate", "Public-domain photos, or AI art only for characters."),
        "sources": ("Source scout", "investigate", "Where fact-checking starts.")}},
    "content": {"name": "Content", "lobe": "Temporal lobe · language", "role": "Researches and writes the videos",
                "ax": 0.36, "ay": 0.64, "subs": {
        "research": ("Researcher", "make", "Finds and checks the facts, with sources, before a word is written."),
        "script": ("Script writer", "make", "Writes the draft script, visuals plan and end card for you to approve."),
        "packaging": ("Packaging", "make", "Titles, descriptions, captions, tags and the pinned comment."),
        "hooks": ("Hook & retention check", "retention", "Checks the first seconds and pacing against the rules."),
        "titles": ("Title scoring", None, "Scores title options with vidIQ."),
        "episodes": ("Episode planner", "make", "Turns the week's Shorts into the weekly long-form episode.")}},
    "production": {"name": "Production", "lobe": "Occipital lobe · vision", "role": "Makes the videos",
                   "ax": 0.85, "ay": 0.46, "subs": {
        "videos": ("Videos", "videos", "Every video, from being made to live."),
        "visuals": ("Visuals", None, "Fetches real photos and generates the art."),
        "tiktok": ("TikTok cut", "retention", "Builds the TikTok retention cut."),
        "render": ("Renderer", None, "Narration, captions, motion, score and mix."),
        "qa": ("QA", None, "Checks every render before you see it."),
        "thumbnail": ("Thumbnail", None, "Thumbnail and vertical cover."),
        "bundle": ("Asset upload", None, "Backs the assets up to R2 for the cloud workflow."),
        "longform": ("Long-form renderer", "make", "Renders the weekly episode in 16:9 with chapter cards and timestamps.")}},
    "publishing": {"name": "Publishing", "lobe": "Motor cortex · action", "role": "Gets videos out",
                   "ax": 0.47, "ay": 0.22, "subs": {
        "calendar": ("Calendar", "calendar", "Posted and scheduled, across every platform."),
        "schedule": ("Scheduler", "calendar", "Queues videos on Buffer when you press Post — and moves or pulls them back out.")}},
    "analytics": {"name": "Analytics", "lobe": "Parietal lobe · numbers", "role": "Measures and learns",
                  "ax": 0.7, "ay": 0.29, "subs": {
        "performance": ("Performance", "performance", "Views, watch time and engagement per video and platform."),
        "retention": ("Retention", "retention", "Pacing checklist beside real watch time."),
        "stats": ("Numbers refresh", "performance", "Pulls the true numbers from YouTube and Buffer."),
        "learning": ("Learning loop", "investigate", "Checks predictions against results and re-weights.")}},
    "business": {"name": "Business", "lobe": "Limbic system · relationships", "role": "Audience and money",
                 "ax": 0.53, "ay": 0.6, "subs": {
        "community": ("Comments", "comments", "Comments waiting for a reply, with drafted answers."),
        "monetisation": ("Monetisation", "money", "How close the channel is to getting paid, by both YouTube routes."),
        "affiliates": ("Affiliate links", "money", "Adds the source-material and newsletter links to every description."),
        "sponsors": ("Sponsor kit", "money", "A one-page media kit built from your real numbers.")}},
    "control": {"name": "Control", "lobe": "Cerebellum · coordination", "role": "Keeps every agent running",
                "ax": 0.74, "ay": 0.72, "subs": {
        "tasks": ("Task log", "agents", "Every task every agent ran — what broke, and Retry."),
        "daily": ("Daily run", "agents", "The 7:00 run: refresh, learn, draft the next video."),
        "settings": ("Settings", "settings", "Connections and keys, and whether each one works."),
        "repair": ("Repair", "fixes", "Failures sent to fix: what broke, why, and a repair you approve before it's applied."),
        "engines": ("AI engines", "engines", "Which engine writes each job — Claude, an API key or a free local model — with automatic fallback.")}},
}

# Studio's job buttons → (agent, sub-agent). build/build_nofetch report themselves from build.sh.
STUDIO_ACTIONS = {"post_dry": ("publishing", "schedule"), "post_live": ("publishing", "schedule"),
                  "undo": ("publishing", "schedule"), "reschedule": ("publishing", "schedule"),
                  "stats": ("analytics", "stats"), "demand": ("intelligence", "demand"),
                  "replies": ("business", "community"), "score": ("content", "titles")}

# build.sh step names → production sub-agents
BUILD_STEPS = [("real photos", "visuals"), ("generated art", "visuals"), ("tiktok", "tiktok"), ("render", "render"),
               ("qa", "qa"), ("thumbnail", "thumbnail"), ("asset bundle", "bundle")]


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def db():
    DB.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY, parent INTEGER, agent TEXT NOT NULL, sub TEXT, title TEXT NOT NULL,
        status TEXT NOT NULL, video TEXT, input TEXT, output TEXT, error TEXT, retry TEXT,
        created TEXT, started TEXT, finished TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS tasks_parent ON tasks(parent)")
    c.execute("CREATE INDEX IF NOT EXISTS tasks_agent ON tasks(agent, id)")
    return c


def _j(x):
    return None if x is None else json.dumps(x, ensure_ascii=False)


def begin(agent, title, sub=None, parent=None, video=None, input=None, retry=None, status="working"):
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent}")
    with db() as c:
        t = now()
        return c.execute("INSERT INTO tasks (parent, agent, sub, title, status, video, input, retry, created, started) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (parent, agent, sub, title, status, video, _j(input), _j(retry), t,
                          t if status == "working" else None)).lastrowid


def _close(c, tid, status, output=None, error=None):
    c.execute("UPDATE tasks SET status=?, output=COALESCE(?, output), error=COALESCE(?, error), finished=? "
              "WHERE id=? AND status != 'cancelled'", (status, _j(output), error, now(), tid))   # a cancel sticks


def finish(tid, output=None):
    with db() as c:
        _close(c, tid, "complete", output)


def fail(tid, error, output=None):
    with db() as c:
        _close(c, tid, "failed", output, str(error)[-4000:])


def cancel(tid):
    with db() as c:
        for r in c.execute("SELECT id FROM tasks WHERE (id=? OR parent=?) AND status IN ('queued','working','waiting')",
                           (tid, tid)).fetchall():
            _close(c, r["id"], "cancelled")
    # the process itself isn't killed (a render mid-frame is safe to let finish); its later reports can't
    # un-cancel the task, and steps it opens under a cancelled parent are cancelled on arrival (step()).
    return {"ok": True}


def step(parent, name):
    """Close the parent's running step and open the next one (used by build.sh between stages)."""
    with db() as c:
        p = c.execute("SELECT agent, status FROM tasks WHERE id=?", (parent,)).fetchone()
        if not p or p["status"] == "cancelled":
            return None
        for r in c.execute("SELECT id FROM tasks WHERE parent=? AND status='working'", (parent,)).fetchall():
            _close(c, r["id"], "complete")
    low = name.lower()
    sub = next((s for k, s in BUILD_STEPS if low.startswith(k)), None)
    return begin(p["agent"], name, sub=sub, parent=parent)


def end(tid, code, log=""):
    """Close a task from its exit code. On failure the running step is the one that broke."""
    tail = "\n".join(log.strip().splitlines()[-30:])
    with db() as c:
        running = c.execute("SELECT id FROM tasks WHERE parent=? AND status='working'", (tid,)).fetchall()
        for r in running:
            if code:
                _close(c, r["id"], "failed", error=tail)
            else:
                _close(c, r["id"], "complete")
        if code:
            _close(c, tid, "failed", error=tail or f"exit code {code}")
        else:
            _close(c, tid, "complete")


def _sweep(c):
    cut = (datetime.datetime.now().astimezone() - datetime.timedelta(hours=STALE_HOURS)).isoformat(timespec="seconds")
    c.execute("UPDATE tasks SET status='failed', finished=?, error=COALESCE(error, ?) "
              "WHERE status='working' AND started < ?", (now(), "Stopped without reporting back (the app or Mac may "
                                                         "have closed mid-job). Retry it.", cut))


def _row(r):
    d = dict(r)
    for k in ("input", "output", "retry"):
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


def tasks(limit=30, agent=None, top_only=True):
    with db() as c:
        _sweep(c)
        q, a = "SELECT * FROM tasks WHERE 1=1", []
        if top_only:
            q += " AND parent IS NULL"
        if agent:
            q += " AND agent=?"; a.append(agent)
        rows = [_row(r) for r in c.execute(q + " ORDER BY id DESC LIMIT ?", (*a, limit))]
        for r in rows:
            r["steps"] = [_row(x) for x in c.execute("SELECT * FROM tasks WHERE parent=? ORDER BY id", (r["id"],))]
        return rows


def last(agent, sub=None):
    """The most recent top-level task of an agent (and sub-agent), or None."""
    with db() as c:
        q = "SELECT * FROM tasks WHERE agent=? AND parent IS NULL" + (" AND sub=?" if sub else "") + " ORDER BY id DESC LIMIT 1"
        r = c.execute(q, (agent, sub) if sub else (agent,)).fetchone()
        return _row(r) if r else None


def task(tid):
    with db() as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        if not r:
            return None
        d = _row(r)
        d["steps"] = [_row(x) for x in c.execute("SELECT * FROM tasks WHERE parent=? ORDER BY id", (tid,))]
        return d


def system():
    """Each agent and sub-agent's live state: working, failed (its latest task broke), or ready."""
    with db() as c:
        _sweep(c)
        latest = {}
        for r in c.execute("SELECT agent, sub, status, title, finished, started, error, id FROM tasks ORDER BY id"):
            if r["sub"]:
                latest[(r["agent"], r["sub"])] = dict(r)
            if r["status"] == "working":
                latest[(r["agent"], "__working")] = latest.get((r["agent"], "__working"), 0) + 1
        hist, subhist = {}, {}                          # run history for the dots: oldest → newest
        for r in c.execute("SELECT id, agent, sub, parent, status, title, finished FROM tasks WHERE status != 'working' ORDER BY id"):
            rec = {"id": r["id"], "status": r["status"], "title": r["title"], "finished": r["finished"]}
            if r["parent"] is None:
                hist.setdefault(r["agent"], []).append(rec)
            if r["sub"]:
                subhist.setdefault((r["agent"], r["sub"]), []).append(rec)
        top = {r["agent"]: dict(r) for r in c.execute(
            "SELECT * FROM tasks WHERE id IN (SELECT MAX(id) FROM tasks WHERE parent IS NULL GROUP BY agent)")}
        counts = dict(c.execute("SELECT status, COUNT(*) FROM tasks WHERE parent IS NULL GROUP BY status").fetchall())

    def state(rec):
        if not rec:
            return "ready"
        return {"working": "working", "queued": "working", "waiting": "working", "failed": "failed"}.get(rec["status"], "ready")

    agents = []
    for key, a in AGENTS.items():
        subs = []
        for sk, (name, page, what) in a["subs"].items():
            rec = latest.get((key, sk))
            subs.append({"key": sk, "name": name, "page": page, "what": what, "state": state(rec),
                         "recent": subhist.get((key, sk), [])[-8:],
                         "last": {k: rec[k] for k in ("id", "title", "status", "finished", "error")} if rec else None})
        last = top.get(key)
        st = "working" if latest.get((key, "__working")) else state(last)
        agents.append({"key": key, "name": a["name"], "lobe": a["lobe"], "role": a["role"], "ax": a["ax"], "ay": a["ay"], "state": st,
                       "active": latest.get((key, "__working"), 0), "subs": subs, "recent": hist.get(key, [])[-10:],
                       "last": {k: last[k] for k in ("id", "title", "status", "finished")} if last else None})
    return {"online": True, "agents": agents, "counts": {s: counts.get(s, 0) for s in
                                                          ("working", "complete", "failed", "cancelled")}}


def _cli():
    a = sys.argv[1:]
    if not a:
        s = system()
        print(f"NETHER  {s['counts']}")
        for ag in s["agents"]:
            print(f"  {ag['name']:13s} {ag['state']:8s} " + " ".join(f"{x['name']}:{x['state']}" for x in ag["subs"]))
        for t in tasks(10):
            print(f"  #{t['id']:<4} {t['status']:9s} {t['agent']:12s} {t['title']}")
        return
    cmd = a[0]
    opt = lambda k: a[a.index(k) + 1] if k in a else None
    if cmd == "begin":
        print(begin(a[1], a[2], video=opt("--video"), retry=json.loads(opt("--retry")) if opt("--retry") else None))
    elif cmd == "step":
        step(int(a[1]), a[2])
    elif cmd == "end":
        log = Path(a[3]).read_text(errors="replace") if len(a) > 3 and Path(a[3]).exists() else ""
        end(int(a[1]), int(a[2]), log)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    _cli()
