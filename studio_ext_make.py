"""Studio extension: the Make flow — Content drafts, you approve, Production builds.

GET  /api/drafts            drafts waiting for you (script lines, visuals plan, research + sources, checks),
                            what's being drafted right now, and the episodes
POST /api/make/draft        {"topic"} → Content researches and writes a draft (background, one at a time)
POST /api/make/redraft      {"id", "notes"} → rewrite with your notes; research is kept
POST /api/make/approve      {"id"} → the draft becomes a video; the page then starts the build
POST /api/make/discard      {"id"} → throw an unapproved draft away
POST /api/episode/week      this week's Shorts → the weekly long-form episode plan
POST /api/daily/run         run the daily run now (Control)
POST /api/long/render       {"id"} → Production renders the episode in 16:9 (make_long.py), in the background
Editing a line uses the existing /api/script; picking a title uses /api/choose_title.
"""
import re, subprocess, sys, threading
from pathlib import Path

import drafter
import drafter_long

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


_LONG = {"what": None}


def episodes():
    import json
    out = []
    for p in sorted((HERE / "episodes").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
        if p.stem.startswith("_"):
            continue
        try:
            ep = json.loads(p.read_text())
        except Exception:
            continue
        vid = f"{p.stem}_long"
        mp4 = HERE / "out" / f"{vid}.mp4"
        chap = HERE / "episodes" / f"{p.stem}.chapters.txt"
        plan = HERE / "episodes" / f"{p.stem}.plan.md"
        if ep.get("draft"):
            continue                                   # still a script: it's under "Scripts waiting for you"
        pk = json.loads((HERE / "packaging" / f"{vid}.json").read_text()) if (HERE / "packaging" / f"{vid}.json").exists() else {}
        shorts = sorted(q.stem for q in (HERE / "cfg").glob(f"{p.stem}__*.json") if not q.stem.endswith("_tiktok"))
        out.append({"id": p.stem, "title": pk.get("title") or ep.get("title", p.stem), "video": vid,
                    "kind": ep.get("kind", "recap"), "style": ep.get("style", ""), "shorts": shorts,
                    "chapters": [c.get("title", c.get("id")) for c in ep.get("chapters", [])],
                    "rendered": mp4.exists(), "timestamps": chap.read_text() if chap.exists() else "",
                    "plan": plan.read_text()[:6000] if plan.exists() else "",
                    "rendering": _LONG["what"] == p.stem})
    return out


def drafts():
    return {"busy": _BUSY["what"], "drafts": drafter_long.drafts() + drafter.drafts(), "episodes": episodes(),
            "rendering": _LONG["what"]}


def render_long(body):
    eid = str(body.get("id", ""))
    if not re.fullmatch(r"[a-z0-9_]{3,60}", eid) or not (HERE / "episodes" / f"{eid}.json").exists():
        raise ValueError("Which episode?")
    if _LONG["what"]:
        raise ValueError(f"Production is already rendering {_LONG['what']}.")
    _LONG["what"] = eid
    py = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable

    def run():
        try:
            subprocess.run([py, "make_long.py", f"episodes/{eid}.json"], cwd=HERE, capture_output=True, timeout=4 * 3600)
        finally:
            _LONG["what"] = None
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "reply": "Production is rendering the long-form — roughly 5–15 minutes. Watch it on the brain."}


def make(body):
    topic = re.sub(r"\s+", " ", str(body.get("topic", ""))).strip()[:160]
    if not topic:
        raise ValueError("What should the video be about?")
    if body.get("kind") == "long":
        style = "iceberg" if body.get("style") == "iceberg" else None
        _bg(f"drafting the long-form “{topic}”", drafter_long.draft, topic, None, None, style)
        return {"ok": True, "reply": "Content is researching and writing a 10–12 minute episode — usually 8–15 minutes. It'll land in Today."}
    _bg(f"drafting “{topic}”", drafter.draft, topic)
    return {"ok": True, "reply": "Content is researching and writing it — usually 3–6 minutes. It'll land in Today."}


def redraft(body):
    vid, notes = str(body.get("id", "")), str(body.get("notes", "")).strip()[:1500]
    if not notes:
        raise ValueError("Say what should change.")
    if drafter_long.is_draft(vid):
        _bg(f"redrafting {vid}", drafter_long.draft, "", notes, vid)
        return {"ok": True, "reply": "Rewriting the episode with your notes — 5–10 minutes."}
    vid = _id(body)
    if not drafter.is_draft(vid):
        raise ValueError("Only a draft waiting for approval can be redrafted.")
    _bg(f"redrafting {vid}", drafter.draft, "", notes, vid)
    return {"ok": True, "reply": "Rewriting with your notes — a few minutes."}


def approve(body):
    vid = str(body.get("id", ""))
    if drafter_long.is_draft(vid):
        r = drafter_long.approve(vid)
        render_long({"id": vid})                        # Production: visuals, 16:9 render, QA, chapters, thumbnails
        return {**r, "reply": "Approved — Production is fetching the visuals and rendering the episode (20–45 min)."}
    return {**drafter.approve(_id(body)), "reply": "Approved — Production is building it."}


def discard(body):
    vid = str(body.get("id", ""))
    if drafter_long.is_draft(vid):
        return {**drafter_long.discard(vid), "reply": "Draft thrown away."}
    return {**drafter.discard(_id(body)), "reply": "Draft thrown away."}


def lines(body):
    """Edit a long-form draft's lines (Shorts use /api/script)."""
    ls = body.get("lines") or {}
    if not isinstance(ls, dict):
        raise ValueError("Bad lines.")
    return drafter_long.save_lines(str(body.get("id", "")), ls)


def cut_shorts(body):
    """Content cuts a Short (+ TikTok cut) from each chapter of an approved episode — build them from Production."""
    import episode, io, contextlib
    eid = str(body.get("id", ""))
    p = HERE / "episodes" / f"{eid}.json"
    if not re.fullmatch(r"[a-z0-9_]{3,60}", eid) or not p.exists():
        raise ValueError("Which episode?")
    if drafter_long.is_draft(eid):
        raise ValueError("Approve the episode first.")
    with contextlib.redirect_stdout(io.StringIO()):
        episode.main(str(p))
    n = len([q for q in (HERE / "cfg").glob(f"{eid}__*.json") if not q.stem.endswith("_tiktok")])
    return {"ok": True, "reply": f"{n} Shorts cut from the chapters — they're in Production → Videos, ready to build."}


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
    _bg("the daily run", lambda: subprocess.run([py, "daily.py", "--force"], cwd=HERE, capture_output=True, timeout=4 * 3600))   # Sundays include the long-form render
    return {"ok": True, "reply": "Daily run started — refresh, learn, draft. Watch it on the brain."}


GET = {"/api/drafts": drafts}
POST = {"/api/make/draft": make, "/api/make/redraft": redraft, "/api/make/approve": approve,
        "/api/make/discard": discard, "/api/episode/week": week, "/api/daily/run": daily,
        "/api/long/render": render_long, "/api/make/lines": lines, "/api/episode/shorts": cut_shorts}
