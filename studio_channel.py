"""studio_channel.py — Channel, Calendar, Comments, Digest and title checks for the app.

Every number here carries its source and time. Sources, in order of trust:
  YouTube Data API (out/youtube.json)  — YouTube views/likes/comments, subscribers
  Buffer (out/stats.json)              — TikTok + Instagram numbers, the posting queue
  vidIQ (only when a job actually ran) — title/thumbnail scores, stamped with a date
Nothing is estimated silently; estimates are labelled as such.
"""
import datetime, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
GOAL_SUBS, GOAL_VIEWS = 1000, 10_000_000  # YouTube Partner Program via Shorts


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def parse(ts):
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def history(name):
    rows = []
    p = OUT / name
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


# ------------------------------------------------------------------ YouTube truth
def yt():
    return jload(OUT / "youtube.json", {}) or {}


def yt_match(title, buffer_posts):
    """The YouTube video for one of our videos: by the id in Buffer's link, else by title."""
    data = yt()
    vids = data.get("videos", [])
    for p in buffer_posts:
        m = re.search(r"(?:v=|shorts/)([\w-]{6,})", p.get("url") or "")
        if p.get("platform") == "youtube" and m:
            hit = next((v for v in vids if v["id"] == m[1]), None)
            if hit:
                return hit
    t = norm(title)
    return next((v for v in vids if t and (norm(v["title"]) == t or norm(v["title"]).startswith(t[:40]))), None)


def true_posts(title, buffer_posts):
    """Buffer's per-platform posts, with YouTube numbers replaced by YouTube's own."""
    v = yt_match(title, buffer_posts)
    posts = [dict(p, source="Buffer") for p in buffer_posts if p.get("platform") != "youtube"]
    if v:
        yb = next((p for p in buffer_posts if p.get("platform") == "youtube"), {})
        posts.insert(0, {"platform": "youtube", "views": v["views"], "reactions": v["likes"], "comments": v["comments"],
                         "shares": None, "saves": None, "averageTimeWatched": None,
                         "sentAt": yb.get("sentAt") or v["published"], "url": v["url"], "source": "YouTube"})
    else:
        posts[:0] = [dict(p, source="Buffer") for p in buffer_posts if p.get("platform") == "youtube"]
    return posts


# ------------------------------------------------------------------ Channel (home)
def pace(hist, field):
    """Growth per day from snapshots at least 20h apart; None until there's enough history."""
    pts = [(parse(h["at"]), h.get(field)) for h in hist if h.get(field) is not None and parse(h["at"])]
    if len(pts) < 2:
        return None
    (t0, v0), (t1, v1) = pts[0], pts[-1]
    days = (t1 - t0).total_seconds() / 86400
    return (v1 - v0) / days if days >= 0.8 else None


def channel():
    d = yt()
    if not d:
        return {"ready": False}
    c, s90 = d["channel"], d["shorts_90d"]
    hist = history("youtube_history.jsonl")
    sub_pace, view_pace = pace(hist, "subscribers"), pace(hist, "views")

    def eta(current, goal, per_day):
        if not per_day or per_day <= 0:
            return None
        days = (goal - current) / per_day
        return (datetime.date.today() + datetime.timedelta(days=int(days))).isoformat() if days < 3650 else "10+ years"

    week_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    last_week = [h for h in hist if (parse(h["at"]) or week_ago) <= week_ago]
    weekly = None
    if last_week:
        base = last_week[-1]
        weekly = {"subscribers": c["subscribers"] - base["subscribers"], "views": c["views"] - base["views"], "since": base["at"]}
    top = sorted(d["videos"], key=lambda v: -v["views"])[:5]
    return {
        "ready": True, "fetched": d["fetched"], "channel": c,
        "goals": [
            {"key": "subs", "label": "Subscribers", "value": c["subscribers"], "goal": GOAL_SUBS,
             "note": "Public count, rounded by YouTube.", "per_day": sub_pace, "eta": eta(c["subscribers"], GOAL_SUBS, sub_pace)},
            {"key": "views", "label": "Shorts views, last 90 days", "value": s90["views"], "goal": GOAL_VIEWS,
             "note": f"Estimate: views on the {s90['videos']} Shorts posted in the last 90 days. YouTube Studio → Earn has the official figure.",
             "per_day": None, "eta": None},
        ],
        "weekly": weekly, "top": top, "avg_views": round(sum(v["views"] for v in d["videos"]) / max(1, len(d["videos"]))),
        "digest": latest_digest(),
    }


def latest_digest():
    files = sorted((OUT / "digest").glob("*.md")) if (OUT / "digest").exists() else []
    return {"date": files[-1].stem, "text": files[-1].read_text()} if files else None


# ------------------------------------------------------------------ Calendar
def calendar(days_back=14, days_ahead=21):
    """Sent + scheduled posts in a window, grouped by local date. Scheduled ones can be moved."""
    stats = jload(OUT / "stats.json", {}) or {}
    titles = {}
    for p in (HERE / "packaging").glob("*.json"):
        titles[p.stem] = (jload(p, {}) or {}).get("title", p.stem)
    now = datetime.datetime.now().astimezone()
    lo, hi = now - datetime.timedelta(days=days_back), now + datetime.timedelta(days=days_ahead)
    items = []
    for vid, posts in stats.get("videos", {}).items():
        for p in posts:
            t = parse(p.get("sentAt"))
            if t and lo <= t <= hi:
                items.append({"video": vid, "title": titles.get(vid, vid), "platform": p["platform"], "at": t.astimezone().isoformat(),
                              "state": "sent", "url": p.get("url")})
    for s in stats.get("scheduled", []):
        t = parse(s.get("dueAt"))
        if t:
            items.append({"video": s["video"], "title": titles.get(s["video"], s["video"]), "platform": s["platform"],
                          "at": t.astimezone().isoformat(), "state": "scheduled", "post_id": s.get("id")})
    return {"items": sorted(items, key=lambda i: i["at"]), "from": lo.date().isoformat(), "to": hi.date().isoformat(),
            "updated": stats.get("updated")}


# ------------------------------------------------------------------ Comments
def comments(done):
    d = yt()
    own = norm(d.get("channel", {}).get("handle", "")).replace(" ", "")
    drafts = jload(OUT / "comment_drafts.json", {}) or {}
    out = []
    for c in d.get("comments", []):
        if own and norm(c["author"]).replace(" ", "") == own:
            continue  # our own comments (e.g. the pinned question)
        out.append(dict(c, done=f"comment:{slug(c['id'])}" in done, drafts=drafts.get(c["id"], [])))
    return {"comments": out, "fetched": d.get("fetched")}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:60]


# ------------------------------------------------------------------ Title / thumbnail pre-check
def title_checklist(title):
    """Rule-based checks (not a prediction), from what LEARNINGS/packaging rules ask for."""
    t = title or ""
    return [
        {"ok": len(t) <= 70, "label": f"Short enough to read on a phone ({len(t)}/70 characters)"},
        {"ok": bool(re.search(r"\d", t)), "label": "Has a hard number"},
        {"ok": bool(re.search(r"marvel|wolverine|hulk|x-men|mutant|spider", t, re.I)) or bool(re.search(r"star|planet|ocean|sea|worm|shark|fish|shrimp", t, re.I)),
         "label": "Names the subject people search for"},
        {"ok": "—" in t or ":" in t or "?" in t, "label": "Has a twist or reveal after the hook"},
        {"ok": not re.search(r"\b(you won't believe|shocking|insane)\b", t, re.I), "label": "No clickbait phrases"},
    ]


def precheck(pkg):
    opts = [o if isinstance(o, dict) else {"title": o} for o in (pkg or {}).get("title_options", [])]
    current = (pkg or {}).get("title")
    if current and not any(o["title"] == current for o in opts):
        opts.insert(0, {"title": current})
    for o in opts:
        o["checks"] = title_checklist(o["title"])
        o["passed"] = sum(c["ok"] for c in o["checks"])
        o["current"] = o["title"] == current
    thumbs = (pkg or {}).get("thumb_options", [])
    return {"titles": opts, "thumbs": thumbs, "vidiq_note": vidiq_note()}


def vidiq_note():
    b = jload(OUT / "vidiq_balance.json", None)
    if not b:
        return "vidIQ scores run when you tap Score (5 credits each)."
    if b.get("credits", 0) < 5:
        return f"vidIQ has {b.get('credits', 0)} credits left (needs 5 per score) — refills {b.get('resets', 'next cycle')[:10]}. Showing the checklist only."
    return f"vidIQ: {b['credits']} credits left (5 per score), checked {b.get('at', '')[:16]}."
