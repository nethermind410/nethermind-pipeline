"""Studio extension: Insights — best posting times from your own numbers, a channel watchlist, and ideas from comments.

GET  /api/insights/times                 per platform: each posted video's real publish time vs its real views at a comparable age
GET  /api/insights/watchlist             the last watchlist check (out/watchlist.json) + whether a check is running
POST /api/insights/watchlist/check       run watchlist.py in a background thread (read-only YouTube API calls)
POST /api/insights/watchlist/add         {"handle": "@x", "note": ""}
POST /api/insights/watchlist/remove      {"handle": "@x"}
GET  /api/insights/comment_ideas         real comments that ask, request, dispute or name something → suggested ideas
Truth first: every number comes from out/ files with their fetch time; nothing is posted, queued or replied to.
"""
import datetime, json, re, statistics, threading
from pathlib import Path

import studio_api as api
import studio_channel as chan
import watchlist as wl

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
OUT = DATA / "out"
MIN_VIDEOS = 8                    # below this, no pattern is called
AGE_MIN, AGE_MAX = 2.0, 7.0       # "comparable age": views measured when the video was 2–7 days old
BANDS = [(0, 6, "Night", "12–6 AM"), (6, 12, "Morning", "6 AM–12"), (12, 18, "Afternoon", "12–6 PM"), (18, 24, "Evening", "6 PM–12")]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
GENERAL = ("Neither YouTube, TikTok nor Instagram publishes a single best time. "
           "Most creator guides suggest posting a little before your audience is most active — often late afternoon "
           "to evening in their time zone. YouTube Studio → Analytics → Audience shows \"When your viewers are on YouTube\" "
           "once a channel has enough viewers; that is the first place your own answer will appear.")


def parse(ts):
    """ISO time → aware datetime. Naive stamps (stats.py writes local time) are read as this Mac's local time."""
    d = chan.parse(ts)
    return (d.astimezone() if d.tzinfo is None else d) if d else None


def band(h):
    return next(i for i, b in enumerate(BANDS) if b[0] <= h < b[1])


def dot(platform, title, vid, url, posted, views, measured, source):
    loc = posted.astimezone()
    age = (measured - posted).total_seconds() / 86400
    return {"platform": platform, "title": title, "video": vid, "url": url, "posted": posted.isoformat(),
            "day": loc.weekday(), "band": band(loc.hour), "local": loc.strftime("%a %-d %b, %-I:%M %p"),
            "views": views, "measured": measured.isoformat(timespec="minutes"), "age_days": round(age, 1),
            "comparable": AGE_MIN <= age <= AGE_MAX, "source": source}


def youtube_dots():
    """YouTube: publishedAt from the Data API; views from the first snapshot (out/youtube_history.jsonl)
    taken when the video was at least 2 days old — comparable only if that snapshot fell within 2–7 days."""
    d = chan.yt()
    snaps = sorted(((parse(r["at"]), r["videos"]) for r in chan.history("youtube_history.jsonl") if r.get("videos") and parse(r.get("at"))),
                   key=lambda x: x[0])
    dots = []
    for v in d.get("videos", []):
        pub = parse(v["published"])
        if not pub:
            continue
        hit = next(((at, vs[v["id"]]) for at, vs in snaps if v["id"] in vs and (at - pub).total_seconds() >= AGE_MIN * 86400), None)
        if hit:
            dots.append(dot("youtube", v["title"], v["id"], v["url"], pub, hit[1], hit[0], "YouTube API snapshot"))
        elif parse(d.get("fetched")):   # too young for a 2-day snapshot yet: show it, not comparable
            dots.append(dot("youtube", v["title"], v["id"], v["url"], pub, v["views"], parse(d["fetched"]), "YouTube API (latest)"))
    return dots, d.get("fetched")


def buffer_dots(platform):
    """TikTok / Instagram: Buffer's sentAt and the views Buffer reported at out/stats.json's update time.
    Buffer history (stats_history.jsonl) is summed across platforms, so each post has one measurement: now."""
    s = api.jload(OUT / "stats.json", {}) or {}
    measured = parse(s.get("updated"))
    titles = {r["id"]: r["title"] for r in (api.performance().get("rows") or [])} if measured else {}
    yt = {v["id"]: v["title"] for v in chan.yt().get("videos", [])}
    for vid, posts in (s.get("videos") or {}).items():   # the live YouTube title beats a script's working name
        m = next((re.search(r"(?:v=|shorts/)([\w-]{6,})", p.get("url") or "") for p in posts if p.get("platform") == "youtube"), None)
        if m and m[1] in yt:
            titles[vid] = yt[m[1]]
    best = {}
    for vid, posts in (s.get("videos") or {}).items():
        for p in posts:
            if p.get("platform") != platform or p.get("views") is None or not parse(p.get("sentAt")):
                continue
            if vid not in best or p["views"] > best[vid]["views"]:    # a re-post of the same video counts once
                best[vid] = p
    dots = [dot(platform, titles.get(vid, vid.replace("_", " ")), vid, p.get("url"), parse(p["sentAt"]), int(p["views"]),
                measured, "Buffer") for vid, p in best.items()]
    return dots, s.get("updated")


def verdict(dots):
    comp = [d for d in dots if d["comparable"]]
    n = len(comp)
    if n < MIN_VIDEOS:
        return {"call": False, "text": f"{n} video{'s' if n != 1 else ''} measured at a comparable age — too few to call a pattern. "
                f"It takes {MIN_VIDEOS}; until then any \"best time\" would be noise."}
    overall = statistics.median(d["views"] for d in comp)
    groups = {}
    for d in comp:
        groups.setdefault(d["band"], []).append(d["views"])
    ranked = sorted(((statistics.median(v), b, len(v)) for b, v in groups.items() if len(v) >= 3), reverse=True)
    if ranked and ranked[0][0] >= 1.5 * overall:
        med, b, k = ranked[0]
        return {"call": True, "band": b, "text": f"{BANDS[b][2]} posts ({BANDS[b][3]}) do best so far: median {int(med):,} views "
                f"across {k} videos, vs {int(overall):,} for all {n}. A lean, not a law — keep testing other times."}
    return {"call": False, "text": f"{n} videos measured, no clear pattern: no time band beats the overall median "
            f"({int(overall):,} views) by 1.5× with at least 3 videos in it."}


def times():
    tz = datetime.datetime.now().astimezone()
    yt, yt_at = youtube_dots()
    plats = [("youtube", "YouTube", yt, yt_at, "YouTube Data API publish times; views from the app's own snapshots")]
    for k, name in (("tiktok", "TikTok"), ("instagram", "Instagram")):
        ds, at = buffer_dots(k)
        plats.append((k, name, ds, at, "Buffer send times and views (one measurement per post — no per-platform history yet)"))
    out = []
    for k, name, ds, at, src in plats:
        ds.sort(key=lambda d: d["posted"])
        out.append({"key": k, "name": name, "dots": ds, "as_of": at, "source": src, "videos": len(ds),
                    "comparable": sum(d["comparable"] for d in ds), "verdict": verdict(ds)})
    return {"platforms": out, "bands": [{"name": b[2], "hours": b[3]} for b in BANDS], "days": DAYS,
            "tz": tz.tzname() or tz.strftime("UTC%z"), "min_videos": MIN_VIDEOS,
            "window": f"views when the video was {AGE_MIN:g}–{AGE_MAX:g} days old", "general": GENERAL}


# ------------------------------------------------------------------ watchlist (background check)
RUN = {"running": False, "started": None, "finished": None, "error": None, "log": ""}
RLOCK = threading.Lock()


def watch_state():
    d = api.jload(OUT / "watchlist.json", {}) or {}
    cfg = wl.config()
    got = {c["handle"].lower(): c for c in d.get("channels", [])}
    rows = []
    for c in cfg:                                    # the config decides who is listed; the last check fills them in
        r = got.get(c["handle"].lower())
        rows.append(dict(r, note=c.get("note", "")) if r else {"handle": c["handle"], "note": c.get("note", ""), "status": "unchecked"})
    for r in rows:
        vids = {v["id"]: v for v in r.get("videos") or []}
        r["breakouts"] = [vids[i] for i in r.get("breakouts", []) if isinstance(i, str) and i in vids]
    with RLOCK:
        run = dict(RUN)
    return {"checked": d.get("checked"), "rule": d.get("rule"), "channels": rows, "run": run}


def watch_check(body):
    with RLOCK:
        if RUN["running"]:
            return {"ok": True, "already": True}
        RUN.update(running=True, started=api.now_iso(), finished=None, error=None, log="")

    def go():
        lines = []
        try:
            wl.check(log=lines.append)
        except Exception as e:
            with RLOCK:
                RUN["error"] = re.sub(r"key=[^&\s]+", "key=…", str(e))[:300]
        finally:
            with RLOCK:
                RUN.update(running=False, finished=api.now_iso(), log="\n".join(lines)[-3000:])
    threading.Thread(target=go, daemon=True).start()
    return {"ok": True}


def watch_add(body):
    r = wl.add(body.get("handle"), body.get("note", ""))
    return dict(r, reply=f"{r['handle']} added. Press Check now to fetch it.")


def watch_remove(body):
    return dict(wl.remove(body.get("handle")), reply="Removed from the watchlist.")


# ------------------------------------------------------------------ ideas from comments
# Deterministic: a comment qualifies when it asks a question, requests a topic, disputes a fact, or names a
# character / animal / game from this list. The comment is quoted exactly; only the suggested hook is written here.
NAMES = {   # pattern → (display name, lane)
    r"falcon punch|captain falcon": ("Captain Falcon's Falcon Punch", "game"), r"wolverine|logan": ("Wolverine", "hero"),
    r"hulk": ("the Hulk", "hero"), r"spider-?man|peter parker": ("Spider-Man", "hero"), r"deadpool": ("Deadpool", "hero"),
    r"magneto": ("Magneto", "hero"), r"iron ?man|tony stark": ("Iron Man", "hero"), r"\bthor\b": ("Thor", "hero"),
    r"captain america": ("Captain America", "hero"), r"\bstorm\b": ("Storm", "hero"), r"cyclops": ("Cyclops", "hero"),
    r"\bvenom\b": ("Venom", "hero"), r"black panther|vibranium": ("Black Panther", "hero"), r"ant-?man": ("Ant-Man", "hero"),
    r"doctor strange": ("Doctor Strange", "hero"), r"thanos": ("Thanos", "hero"), r"\bgroot\b": ("Groot", "hero"),
    r"maggott": ("Maggott", "hero"), r"x-?men|mutant": ("the X-Men", "hero"), r"superman": ("Superman", "hero"),
    r"batman": ("Batman", "hero"), r"\bthe flash\b": ("the Flash", "hero"), r"aquaman": ("Aquaman", "hero"),
    r"pok[eé]mon|pikachu": ("Pokémon", "game"), r"minecraft": ("Minecraft", "game"), r"valorant": ("Valorant", "game"),
    r"fortnite": ("Fortnite", "game"), r"zelda|\blink\b": ("Zelda", "game"), r"\bmario\b": ("Mario", "game"),
    r"\bsonic\b": ("Sonic", "game"), r"\bhalo\b|master chief": ("Halo", "game"), r"elden ring": ("Elden Ring", "game"),
    r"roblox": ("Roblox", "game"), r"subnautica": ("Subnautica", "game"), r"dead space": ("Dead Space", "game"),
    r"mantis shrimp|pistol shrimp": ("the mantis shrimp", "creature"), r"octopus|octopi": ("the octopus", "creature"),
    r"\bsquid\b": ("the giant squid", "creature"), r"axolotl": ("the axolotl", "creature"), r"tardigrade|water bear": ("the tardigrade", "creature"),
    r"anglerfish": ("the anglerfish", "creature"), r"jellyfish": ("the immortal jellyfish", "creature"), r"\bshark": ("sharks", "creature"),
    r"\bwhale": ("whales", "creature"), r"platypus": ("the platypus", "creature"), r"\bcrab\b": ("crabs", "creature"),
    r"black hole": ("black holes", "space"), r"neutron star|pulsar": ("neutron stars", "space"),
}
Q_RE = re.compile(r"\?|^(who|what|why|how|when|where|which|is|are|can|could|does|do|did|would|will)\b", re.I)
REQ_RE = re.compile(r"\b(what about|how about|do (one|a video) on|make (one|a video) on|you should (do|make|cover)|"
                    r"can you (do|make|cover|explain)|please (do|make|cover)|part 2|next video|(do|cover) .{2,40} next)\b", re.I)
DISPUTE_RE = re.compile(r"\b(actually|not true|isn'?t true|that'?s wrong|you'?re wrong|wrong|incorrect|false|myth|debunked|"
                        r"not accurate|misinformation|correction|fake)\b", re.I)
LANE_SECTION = {"hero": ("Marvel / Hero", "hero"), "game": ("Gaming", "fact"), "creature": ("Creatures", "creature"),
                "space": ("Space", "fact")}


def lane_of(text):
    t = text.lower()
    return next((lane for pat, (_, lane) in NAMES.items() if re.search(pat, t)), None)


def shorten(t, n=70):
    t = re.sub(r"\s+", " ", t).strip().rstrip(".!")
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def classify(text):
    kinds, names = [], []
    if Q_RE.search(text.strip()):
        kinds.append("question")
    if REQ_RE.search(text):
        kinds.append("request")
    if DISPUTE_RE.search(text):
        kinds.append("dispute")
    for pat, (name, lane) in NAMES.items():
        if re.search(pat, text, re.I) and name not in [x[0] for x in names]:
            names.append((name, lane))
    if names:
        kinds.append("names")
    return kinds, names


def hook_for(kinds, names, text, video_title):
    topic = shorten(re.sub(r"#\S+", "", video_title or ""), 60)
    if "request" in kinds:
        m = re.search(r"(?:what about|how about|do (?:one|a video) on|make (?:one|a video) on|cover|do)\s+(.{3,60}?)(?:\s+next\b|[?.!]|$)", text, re.I)
        want = shorten(m[1], 50) if m else (names[0][0] if names else topic)
        return f"You asked for it: the real science behind {want}"
    if "dispute" in kinds:
        return f"Fact-check: {topic} — what the evidence really says"
    if names:
        name, lane = names[0]
        return {"game": f"Could {name} work in real life? The real science behind it",
                "hero": f"{name[0].upper() + name[1:]}'s powers vs real science",
                "creature": f"The real science behind {name}",
                "space": f"The real science behind {name}"}[lane]
    return f"Your question, answered: {shorten(text, 70)}"


def comment_ideas(done):
    d = chan.comments(done)                       # already excludes the channel's own comments
    cs = d.get("comments", [])
    ideas, cache = [], []
    for c in cs:
        text = c.get("text") or ""
        kinds, names = classify(text)
        if not kinds:
            continue
        key = f"cidea:{chan.slug(c['id'])}"
        lane = (names[0][1] if names else None) or lane_of(c.get("video_title", "")) or "creature"
        section, fmt = LANE_SECTION[lane]
        why = {"question": "asks a question", "request": "asks for a topic", "dispute": "disputes a fact",
               "names": "names " + ", ".join(n for n, _ in names[:3])}
        item = {"key": key, "hook": hook_for(kinds, names, text, c.get("video_title")), "quote": text, "author": c.get("author"),
                "at": c.get("at"), "likes": c.get("likes", 0), "video_title": c.get("video_title"), "link": c.get("link"),
                "video_url": f"https://www.youtube.com/watch?v={c.get('video')}", "why": [why[k] for k in kinds],
                "section": section, "format": fmt, "dismissed": key in done}
        cache.append({k: item[k] for k in ("key", "hook", "quote", "author", "link", "why", "section")})
        ideas.append(item)
    OUT.mkdir(exist_ok=True)
    (OUT / "community_ideas.json").write_text(json.dumps({"at": api.now_iso(), "checked": len(cs), "comments_fetched": d.get("fetched"),
                                                          "ideas": cache}, indent=1, ensure_ascii=False))
    topics = (DATA / "TOPICS.md").read_text() if (DATA / "TOPICS.md").exists() else ""
    for i in ideas:                               # already added: its comment link is the idea's source in TOPICS.md
        i["added"] = bool(i["link"]) and i["link"] in topics
    return {"ideas": ideas, "checked": len(cs), "fetched": d.get("fetched"),
            "rule": "asks a question, asks for a topic, disputes a fact, or names a character, animal or game"}


GET = {"/api/insights/times": times, "/api/insights/watchlist": watch_state,
       "/api/insights/comment_ideas": lambda: comment_ideas(api.done_map())}
POST = {"/api/insights/watchlist/check": watch_check, "/api/insights/watchlist/add": watch_add,
        "/api/insights/watchlist/remove": watch_remove}
