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

# ax/ay: where the agent sits inside the brain drawing (same 0–1 box as the brain's sections)
AGENTS = {
    "intelligence": {"name": "Intelligence", "role": "Finds topics worth making", "ax": 0.3, "ay": 0.43,
                     "subs": {"demand": "Demand scout", "competitors": "Competitor scout", "fit": "Channel-fit scout",
                              "rights": "Visuals & rights scout", "sources": "Source scout"}},
    "content": {"name": "Content", "role": "Scripts, hooks and packaging", "ax": 0.43, "ay": 0.31,
                "subs": {"script": "Script writer", "hooks": "Hook & retention check", "packaging": "Packaging",
                         "titles": "Title scoring", "episodes": "Episode planner"}},
    "production": {"name": "Production", "role": "Makes the videos", "ax": 0.62, "ay": 0.37,
                   "subs": {"visuals": "Visuals", "tiktok": "TikTok cut", "render": "Renderer", "qa": "QA",
                            "thumbnail": "Thumbnail", "bundle": "Asset upload"}},
    "publishing": {"name": "Publishing", "role": "Queues and moves posts", "ax": 0.74, "ay": 0.53,
                   "subs": {"schedule": "Scheduler", "undo": "Undo", "reschedule": "Reschedule"}},
    "analytics": {"name": "Analytics", "role": "Pulls the real numbers", "ax": 0.56, "ay": 0.53,
                  "subs": {"stats": "Numbers refresh", "retention": "Retention report", "learning": "Learning loop"}},
    "business": {"name": "Business", "role": "Community and money", "ax": 0.42, "ay": 0.58,
                 "subs": {"community": "Comment replies", "monetisation": "Monetisation tracker"}},
}

# Studio's job buttons → (agent, sub-agent). build/build_nofetch report themselves from build.sh.
STUDIO_ACTIONS = {"post_dry": ("publishing", "schedule"), "post_live": ("publishing", "schedule"),
                  "undo": ("publishing", "undo"), "reschedule": ("publishing", "reschedule"),
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
    c.execute("UPDATE tasks SET status=?, output=COALESCE(?, output), error=COALESCE(?, error), finished=? WHERE id=?",
              (status, _j(output), error, now(), tid))


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
    return {"ok": True}


def step(parent, name):
    """Close the parent's running step and open the next one (used by build.sh between stages)."""
    with db() as c:
        p = c.execute("SELECT agent FROM tasks WHERE id=?", (parent,)).fetchone()
        if not p:
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
        for sk, name in a["subs"].items():
            rec = latest.get((key, sk))
            subs.append({"key": sk, "name": name, "state": state(rec),
                         "last": {k: rec[k] for k in ("id", "title", "status", "finished", "error")} if rec else None})
        last = top.get(key)
        st = "working" if latest.get((key, "__working")) else state(last)
        agents.append({"key": key, "name": a["name"], "role": a["role"], "ax": a["ax"], "ay": a["ay"], "state": st,
                       "active": latest.get((key, "__working"), 0), "subs": subs,
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
