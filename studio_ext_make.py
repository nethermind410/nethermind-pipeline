"""Studio extension: the Make flow — Content drafts, you approve, Production builds.

GET  /api/drafts            drafts waiting for you (script lines, visuals plan, research + sources, checks),
                            what's being drafted right now, and the episodes
POST /api/make/draft        {"topic"} → Content researches and writes a draft (background, one at a time)
POST /api/make/redraft      {"id", "notes"} → rewrite with your notes; research is kept
POST /api/make/approve      {"id"} → the draft becomes a video; the page then starts the build
POST /api/make/discard      {"id"} → throw an unapproved draft away
POST /api/episode/week      this week's Shorts → the weekly long-form episode plan
POST /api/daily/run         run the daily run now (Control)
Editing a line uses the existing /api/script; picking a title uses /api/choose_title.
"""
import re, subprocess, sys, threading
from pathlib import Path

import drafter

HERE = Path(__file__).parent
_BUSY = {"what": None}


def _bg(label, fn, *a):
    if _BUSY["what"]:
        raise ValueError(f"Content is still busy: {_BUSY['what']}. One at a time.")
    _BUSY["what"] = label

    def run():
        try:
            fn(*a)
        except Exception:
            pass                     # the failure is on the task (Agents / the brain show it)
        finally:
            _BUSY["what"] = None
    threading.Thread(target=run, daemon=True).start()


def _id(body):
    vid = str(body.get("id", ""))
    if not re.fullmatch(r"[a-z0-9_]{3,48}", vid):
        raise ValueError("Which draft?")
    return vid


def drafts():
    eps = []
    for p in sorted((HERE / "episodes").glob("*.plan.md"), reverse=True)[:6]:
        eps.append({"id": p.name[:-8], "plan": p.read_text()[:6000]})
    return {"busy": _BUSY["what"], "drafts": drafter.drafts(), "episodes": eps}


def make(body):
    topic = re.sub(r"\s+", " ", str(body.get("topic", ""))).strip()[:160]
    if not topic:
        raise ValueError("What should the video be about?")
    _bg(f"drafting “{topic}”", drafter.draft, topic)
    return {"ok": True, "reply": "Content is researching and writing it — usually 3–6 minutes. It'll land in Today."}


def redraft(body):
    vid, notes = _id(body), str(body.get("notes", "")).strip()[:1500]
    if not notes:
        raise ValueError("Say what should change.")
    if not drafter.is_draft(vid):
        raise ValueError("Only a draft waiting for approval can be redrafted.")
    _bg(f"redrafting {vid}", drafter.draft, "", notes, vid)
    return {"ok": True, "reply": "Rewriting with your notes — a few minutes."}


def approve(body):
    return {**drafter.approve(_id(body)), "reply": "Approved — Production is building it."}


def discard(body):
    return {**drafter.discard(_id(body)), "reply": "Draft thrown away."}


def week(body):
    import episode
    try:
        eid = episode.weekly()
    except ValueError as e:
        raise ValueError(str(e))
    return {"ok": True, "id": eid, "reply": f"Episode planned: {eid}."}


def daily(body):
    if _BUSY["what"]:
        raise ValueError(f"Content is still busy: {_BUSY['what']}.")
    py = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable
    _bg("the daily run", lambda: subprocess.run([py, "daily.py"], cwd=HERE, capture_output=True, timeout=3600))
    return {"ok": True, "reply": "Daily run started — refresh, learn, draft. Watch it on the brain."}


GET = {"/api/drafts": drafts}
POST = {"/api/make/draft": make, "/api/make/redraft": redraft, "/api/make/approve": approve,
        "/api/make/discard": discard, "/api/episode/week": week, "/api/daily/run": daily}
