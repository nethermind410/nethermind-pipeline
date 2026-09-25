"""studio_api.py — the data behind Nethermind Studio's screens.

Everything here reads the pipeline's own files (cfg/, packaging/, out/) and returns plain
dicts for studio.py to serve as JSON. Anything the user can tick off lives in out/done.json;
"Needs changes" notes live in out/feedback/<id>.md.
"""
import datetime, json, re, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT, CFG, PKG = HERE / "out", HERE / "cfg", HERE / "packaging"
DONE = OUT / "done.json"
FEEDBACK = OUT / "feedback"
SKIP = ("test", "zz")


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def mtime(p):
    return int(p.stat().st_mtime) if p.exists() else None


def now_iso():
    return datetime.datetime.now().isoformat(timespec="minutes")


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


# ------------------------------------------------------------------ ticks (done.json)
def done_map():
    return jload(DONE, {}) or {}


def set_done(key, done=True):
    d = done_map()
    if done:
        d[key] = now_iso()
    else:
        d.pop(key, None)
    DONE.write_text(json.dumps(d, indent=1))
    return d


# ------------------------------------------------------------------ videos
def video_ids():
    ids = [p.stem for p in CFG.glob("*.json") if not p.stem.endswith("_tiktok") and not p.stem.startswith(SKIP)]
    return sorted(ids, key=lambda i: -(mtime(CFG / f"{i}.json") or 0))


def youtube_urls(posts):
    for p in posts:
        m = re.search(r"(?:v=|shorts/)([\w-]{6,})", p.get("url") or "")
        if p.get("platform") == "youtube" and m:
            return f"https://www.youtube.com/watch?v={m[1]}", f"https://studio.youtube.com/video/{m[1]}/edit"
    return None, None


def video(vid):
    cfg = jload(CFG / f"{vid}.json", {}) or {}
    pkg = jload(PKG / f"{vid}.json")
    f = cfg.get("file", vid)
    rec = (jload(OUT / "posted.json", {}) or {}).get(vid)
    rec = rec if isinstance(rec, dict) else ({"at": rec, "posts": {}} if rec else None)
    stats = jload(OUT / "stats.json", {}) or {}
    import studio_channel
    title0 = (pkg or {}).get("title") or ""
    posts = studio_channel.true_posts(title0, stats.get("videos", {}).get(vid, []))
    sched = [s for s in stats.get("scheduled", []) if s.get("video") == vid]
    rendered, qa = (OUT / f"{f}.mp4").exists(), (OUT / f"{vid}_qa_contact.jpg").exists()
    if cfg.get("draft"):
        stage = "draft"                     # a script the Content agent wrote, waiting for your approval
    elif [p for p in posts if p.get("sentAt")] and (rec or stats.get("videos", {}).get(vid)):
        stage = "live"
    elif rec or sched:
        stage = "scheduled"
    elif rendered and qa and pkg:
        stage = "ready"
    elif not pkg and (datetime.datetime.now().timestamp() - (mtime(CFG / f"{vid}.json") or 0)) > 2 * 86400:
        stage = "earlier"  # made before this app tracked posting
    else:
        stage = "making"
    yt, yt_edit = youtube_urls(posts)
    title = (pkg or {}).get("title") or vid.replace("_", " ").capitalize()
    return {
        "id": vid, "title": title, "stage": stage, "file": f, "format": cfg.get("format", "vertical"),
        "thumb": f"{vid}_thumb.jpg" if (OUT / f"{vid}_thumb.jpg").exists() else None,
        "cover": f"{vid}_cover.jpg" if (OUT / f"{vid}_cover.jpg").exists() else None,
        "video": f"{f}.mp4" if rendered else None,
        "tiktok": f"{vid}_tiktok.mp4" if (OUT / f"{vid}_tiktok.mp4").exists() else None,
        "qa": f"{vid}_qa_contact.jpg" if qa else None,
        "packaging": pkg, "script": [s.get("text", "") for s in cfg.get("segments", [])],
        "script_ids": [s.get("id") for s in cfg.get("segments", [])],
        "posted": rec, "scheduled": sched, "posts": posts,
        "views": int(sum(p.get("views") or 0 for p in posts)),
        "youtube_url": yt, "youtube_edit": yt_edit,
        "feedback": (FEEDBACK / f"{vid}.md").read_text() if (FEEDBACK / f"{vid}.md").exists() else None,
        "updated": mtime(OUT / f"{f}.mp4") or mtime(CFG / f"{vid}.json"),
    }


def videos():
    return [video(v) for v in video_ids()]


# ------------------------------------------------------------------ Today: things that need you
PLATFORMS = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}
FINISH_STEPS = [("tags", "Paste the tags into YouTube Studio"),
                ("comment", "Post and pin the comment"),
                ("playlist", "Add it to its series playlist and set an end screen (next video)"),
                ("check", "Check the video plays and looks right")]
LONG_STEPS = [("testcompare", "Test & Compare: add the 3 thumbnails (out/<id>_thumb, _thumb2, _thumb3)")]


def when(iso):
    d = parse_dt(iso)
    return d.astimezone().strftime("%a %-d %b, %-I:%M %p") if d else ""


def today():
    """Cards that need the user, newest-first. Each tickable card has a stable `key`;
    ticking it (done.json) hides it. Cards also disappear when the real thing happens."""
    done, cards, vids = done_map(), [], videos()
    for v in vids:
        if v["stage"] == "draft":
            cards.append({"key": f"draft:{v['id']}", "kind": "draft", "video": v["id"], "title": v["title"],
                          "thumb": None, "text": "— the script is drafted. Read it, edit any line, and approve it to build."})
        if v["stage"] == "ready" and not v["feedback"]:
            cards.append({"key": f"ready:{v['id']}", "kind": "ready", "video": v["id"], "title": v["title"],
                          "thumb": v["thumb"], "text": "is ready for you to review.",
                          "action": "Review"})
        if v["feedback"] and v["stage"] in ("ready", "making"):
            cards.append({"key": f"fixing:{v['id']}", "kind": "fixing", "video": v["id"], "title": v["title"],
                          "thumb": v["thumb"], "text": "has your change notes. The next daily build will redo it."})
        if v["scheduled"]:
            steps = [{"key": f"queued:{v['id']}:{s['platform']}", "done": f"queued:{v['id']}:{s['platform']}" in done,
                      "label": f"{PLATFORMS.get(s['platform'], s['platform'])} · {when(s['dueAt'])}"} for s in v["scheduled"]]
            if not all(s["done"] for s in steps):
                cards.append({"key": f"queued:{v['id']}", "kind": "queued", "video": v["id"], "title": v["title"],
                              "thumb": v["thumb"], "text": "is waiting in Buffer's queue:", "steps": steps})
        week = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        recent = [p for p in v["posts"] if p.get("platform") == "youtube" and (parse_dt(p.get("sentAt")) or week) > week]
        if recent:
            steps = [{"key": f"finish:{v['id']}:{k}", "label": label.replace("<id>", v["id"]), "done": f"finish:{v['id']}:{k}" in done}
                     for k, label in FINISH_STEPS + (LONG_STEPS if v.get("format") == "landscape" else [])]
            if not all(s["done"] for s in steps):
                pkg = v["packaging"] or {}
                cards.append({"key": f"finish:{v['id']}", "kind": "finish", "video": v["id"], "title": v["title"],
                              "thumb": v["thumb"], "text": "is live on YouTube. Finish it:", "steps": steps,
                              "tags": pkg.get("youtube_tags"), "comment": pkg.get("pinned_comment"),
                              "link": v["youtube_edit"], "watch": v["youtube_url"]})
    try:                                    # a long-form episode script waiting for approval
        import drafter_long
        for d in drafter_long.drafts():
            cards.append({"key": f"draft:{d['id'][:60]}", "kind": "draft", "video": d["id"], "thumb": None,
                          "title": d["title"] or d["topic"],
                          "text": f"— the {d['minutes']:.0f}-minute episode is drafted ({len(d['chapters'])} chapters). Read it and approve it to render."})
    except Exception:
        pass
    try:                                    # Intelligence scored ideas: your call decides what's drafted next
        import learning
        open_cards = [c for c in learning._cards() if not c.get("decision")]
        if open_cards:
            best = max(open_cards, key=lambda c: c.get("score", 0))
            cards.append({"key": f"intel:n{len(open_cards)}_{best['slug'][:40]}", "kind": "intel", "video": "", "thumb": None,
                          "title": f"{len(open_cards)} scorecard{'s' if len(open_cards) > 1 else ''}",
                          "text": f"need your call — best: “{best['topic'][:70]}” ({best['score']}/100). Make it, or not for us?"})
    except Exception:
        pass
    try:                                    # the daily run went quiet: say so instead of silently skipping a day
        import orchestrator
        last = orchestrator.last("control", "daily")
        if last and (datetime.datetime.now().astimezone() - parse_dt(last["started"])).total_seconds() > 26 * 3600:
            cards.append({"key": f"missed:d{last['started'][:10].replace('-', '_')}", "kind": "missed", "video": "", "title": "The daily run",
                          "thumb": None, "text": f"hasn't run since {when(last['started'])}. Is the Mac asleep at 7:00? "
                                                 "Control → Daily run → Run now."})
    except Exception:
        pass
    cards = [c for c in cards if c["key"] not in done]
    ranked = sorted([v for v in vids if v["views"]], key=lambda v: -v["views"])
    highlight = None
    if ranked:
        avg = sum(v["views"] for v in ranked) / len(ranked)
        best = ranked[0]
        highlight = {"title": best["title"], "video": best["id"], "views": best["views"],
                     "ratio": round(best["views"] / avg, 1) if avg else None}
    nxt = jload(NEXT, None)
    return {"cards": cards, "highlight": highlight, "insight": insight(), "next": nxt}


# ------------------------------------------------------------------ performance
def insight():
    txt = (HERE / "LEARNINGS.md").read_text() if (HERE / "LEARNINGS.md").exists() else ""
    m = re.search(r"## Working hypotheses.*?\n- \*\*(.+?)\*\*(.*?)(?:\n|$)", txt, re.S)
    if not m:
        return None
    first = re.split(r"(?<=\.)\s", (m[1] + m[2]).strip())[0]  # one sentence is enough on screen
    return first.replace("**", "")


def performance():
    hist = []
    p = OUT / "stats_history.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                hist.append(json.loads(line))
            except Exception:
                pass
    vids = {v["id"]: v for v in videos()}
    platforms = {}
    for v in vids.values():
        for post in v["posts"]:
            platforms[post["platform"]] = platforms.get(post["platform"], 0) + int(post.get("views") or 0)
    rows = []
    for vid, v in vids.items():
        if not v["posts"]:
            continue
        import studio_channel
        m = studio_channel.yt_match(v["title"], [p for p in v["posts"] if p.get("platform") == "youtube"])
        series = [h["videos"][m["id"]] for h in studio_channel.history("youtube_history.jsonl")
                  if m and m["id"] in h.get("videos", {})]
        rows.append({"id": vid, "title": v["title"], "thumb": v["thumb"], "views": v["views"],
                     "series": series[-30:], "posts": v["posts"]})
    rows.sort(key=lambda r: -r["views"])
    import studio_channel
    total = [h["views"] for h in studio_channel.history("youtube_history.jsonl")][-30:]
    return {"rows": rows, "platforms": platforms, "total": total, "insight": insight(),
            "updated": (jload(OUT / "stats.json", {}) or {}).get("updated"),
            "youtube_updated": (jload(OUT / "youtube.json", {}) or {}).get("fetched"),
            "sources": "YouTube numbers: YouTube API · TikTok & Instagram: Buffer"}


# ------------------------------------------------------------------ ideas (TOPICS.md)
NEXT = OUT / "next.json"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48] or "idea"


def ideas():
    """TOPICS.md tables -> sections of idea cards. Dismissed ideas (done.json idea:<slug>) are
    flagged; the one pinned as "Make this next" comes back separately."""
    done, sections, cur = done_map(), [], None
    for line in (HERE / "TOPICS.md").read_text().splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            cur = {"name": name.split(" — ")[0].split(" / ")[0], "note": name.split(" — ")[1] if " — " in name else "",
                   "title": name, "items": []}
            sections.append(cur)
        elif cur and line.startswith("|") and not re.match(r"^\|\s*(Hook|---|:?-)", line):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0]:
                sl = slug(cells[0])
                cur["items"].append({"slug": sl, "hook": cells[0], "format": cells[1] if len(cells) > 1 else "",
                                     "source": cells[2] if len(cells) > 2 else "",
                                     "dismissed": f"idea:{sl}" in done, "made": cur["name"].lower().startswith("made")})
    return {"sections": [s for s in sections if s["items"]], "next": jload(NEXT, None)}


def set_next(sl, hook):
    if not sl:
        NEXT.unlink(missing_ok=True)
        return {"ok": True}
    NEXT.write_text(json.dumps({"slug": sl, "hook": hook, "at": now_iso()}, indent=1))
    return {"ok": True}


def add_idea(section, hook, fmt, source):
    """Append a row to the matching TOPICS.md table (after its last row)."""
    clean = lambda t: re.sub(r"[|\n\r]+", " ", str(t)).strip()[:200]
    hook, fmt, source = clean(hook), clean(fmt) or "fact", clean(source) or "to verify"
    if not hook:
        raise ValueError("Write the idea first.")
    lines = (HERE / "TOPICS.md").read_text().splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("## ") and l[3:].startswith(section)), None)
    if start is None:
        raise ValueError("Pick a category.")
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    last = max((i for i in range(start, end) if lines[i].startswith("|")), default=None)
    if last is None:
        raise ValueError("That category has no table to add to.")
    lines.insert(last + 1, f"| {hook} | {fmt} | {source} |")
    (HERE / "TOPICS.md").write_text("\n".join(lines) + "\n")
    return {"ok": True, "slug": slug(hook)}


# ------------------------------------------------------------------ feedback ("Needs changes")
def add_feedback(vid, note):
    FEEDBACK.mkdir(exist_ok=True)
    stamp = now_iso()
    with open(FEEDBACK / f"{vid}.md", "a") as f:
        f.write(f"- {stamp}: {note}\n")
    lp = HERE / "LEARNINGS.md"
    txt = lp.read_text() if lp.exists() else ""
    if "## Reviewer notes" not in txt:
        txt = txt.rstrip() + "\n\n## Reviewer notes\n\nWhat the user asked to change on review — patterns here should shape future builds.\n\n"
    lp.write_text(txt + f"- {stamp[:10]} {vid}: {note}\n")
    return {"ok": True}


# ------------------------------------------------------------------ health (Settings)
def env_names():
    env = {}
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = bool(v.strip())
    return env


def jarvis_up():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def health():
    env = env_names()
    has = lambda *ks: all(env.get(k) for k in ks)
    logs = sorted((OUT / "daily").glob("*.md")) if (OUT / "daily").exists() else []
    stats = jload(OUT / "stats.json", {}) or {}
    last = logs[-1].stem if logs else None
    fresh = bool(last) and last >= (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    return [
        {"name": "Buffer", "ok": has("BUFFER_API_KEY"), "detail": "Posting and stats" if has("BUFFER_API_KEY") else "Add BUFFER_API_KEY to .env"},
        {"name": "Video hosting (R2)", "ok": has("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET", "R2_PUBLIC_BASE_URL"),
         "detail": "Uploads for posting"},
        {"name": "AI art (Cloudflare)", "ok": has("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"), "detail": "Comic-panel images"},
        {"name": "YouTube (true numbers)", "ok": has("YOUTUBE_API_KEY") and bool((jload(OUT / "youtube.json", {}) or {}).get("fetched")),
         "detail": f"Views, subscribers, comments · fetched {when((jload(OUT / 'youtube.json', {}) or {}).get('fetched'))}" if (OUT / "youtube.json").exists() else "Tap Refresh on Home"},
        {"name": "vidIQ (title scores)", "ok": (jload(OUT / "vidiq_balance.json", {}) or {}).get("credits", 0) >= 5,
         "detail": (lambda b: f"{b.get('credits', '?')} credits (5 per score) · refills {str(b.get('resets', ''))[:10]}")(jload(OUT / "vidiq_balance.json", {}) or {})},
        {"name": "Jarvis", "ok": jarvis_up(), "detail": "Answers questions (⌘K)" if jarvis_up() else "Not running. Nethermind starts it for you."},
        *daily_and_tools(),
        {"name": "Stats", "ok": bool(stats.get("updated")), "detail": f"Updated {when(stats.get('updated'))}" if stats.get("updated") else "Never refreshed"},
    ]


def daily_and_tools():
    """What the agents need on this Mac: the 7:00 run, drafting, rendering. Plain-English fixes."""
    import shutil
    out = []
    try:
        import orchestrator
        d = orchestrator.last("control", "daily")
    except Exception:
        d = None
    plist = Path.home() / "Library" / "LaunchAgents" / "com.nethermind.daily.plist"
    if d:
        age = (datetime.datetime.now().astimezone() - parse_dt(d["started"])).total_seconds() / 3600
        out.append({"name": "Daily run (7:00)", "ok": age < 26 and d["status"] != "failed" and plist.exists(),
                    "detail": f"Last ran {when(d['started'])} · {d['status']}" + ("" if plist.exists() else " · not installed: run ./install_daily.sh")})
    else:
        out.append({"name": "Daily run (7:00)", "ok": plist.exists(),
                    "detail": "Installed — first run at 7:00" if plist.exists() else "Not installed: run ./install_daily.sh once"})
    claude = shutil.which("claude") or next((str(p) for p in (Path.home() / ".local/bin/claude", Path("/opt/homebrew/bin/claude"),
                                                                Path("/usr/local/bin/claude")) if p.exists()), None)
    out.append({"name": "Drafting (Claude)", "ok": bool(claude),
                "detail": "Content agent writes scripts with your Claude login" if claude else "Install Claude Code (the claude command) to draft scripts"})
    out.append({"name": "Rendering (ffmpeg)", "ok": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
                "detail": "Video and audio" if shutil.which("ffprobe") else "Install ffmpeg: brew install ffmpeg"})
    try:
        import tts_kokoro                              # honours KOKORO_MODEL_PATH / KOKORO_VOICES_PATH
        voice = Path(tts_kokoro.MODEL_PATH).exists() and Path(tts_kokoro.VOICES_PATH).exists()
    except Exception:
        voice = False
    out.append({"name": "Narration voice", "ok": voice, "detail": "Kokoro model present" if voice else "Voice model missing — see SETUP.md (Kokoro files)"})
    fonts = (HERE / "assets" / "Anton-Regular.ttf").exists() and (HERE / "assets" / "BebasNeue-Regular.ttf").exists()
    out.append({"name": "Fonts", "ok": fonts, "detail": "Anton + Bebas Neue" if fonts else "Fonts missing — run ./fetch_assets.sh"})
    free = shutil.disk_usage(HERE).free / 1e9
    out.append({"name": "Disk space", "ok": free > 5, "detail": f"{free:.0f} GB free" + ("" if free > 5 else " — renders need room; clear old out/ files")})
    return out


# ------------------------------------------------------------------ plain-English errors
FRIENDLY = [
    (r"BUFFER_API_KEY", "Buffer isn't connected. Add your Buffer key in Settings."),
    (r"R2_|NoCredentialsError|InvalidAccessKeyId", "Video hosting (R2) isn't set up correctly. Check Settings."),
    (r"429|Too Many Requests|rate.?limit", "A website asked us to slow down. Wait a few minutes and try again."),
    (r"ConnectionError|Max retries|Name or service not known|timed out", "Couldn't reach the internet. Check your connection and try again."),
    (r"missing out/|run \./build\.sh", "This video hasn't been made yet. Tap Make video first."),
    (r"missing from assets/|FileNotFoundError", "A picture or clip for this video is missing. Tap Make video to fetch it again."),
    (r"Buffer rejected the post|MutationError", "Buffer refused the post. Open Buffer to see why."),
    (r"ModuleNotFoundError", "Part of Nethermind's toolkit is missing. Ask Claude to repair the setup."),
    (r"weekly limit|usage limit|hit your .*limit", "Your Claude usage limit is used up for now. It resets on its own — press Retry after the reset time shown."),
]


def friendly(log, code):
    if code == 0:
        return None
    for pat, msg in FRIENDLY:
        if re.search(pat, log or "", re.I):
            return msg
    return "Something went wrong. Open Details to see what happened, or ask Claude."
