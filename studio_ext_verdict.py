"""Studio extension: every page opens with its answer.

GET  /api/verdict/<page>       {"q", "answer", "detail", "tone": good|warn|bad|info, "actions": [...]}
POST /api/videos/archive       {"ids": [...]} → moves stale videos' files into cfg/archive/ (reversible: move them back)
POST /api/ideas/dismiss_offlane  dismiss every open idea outside the channel's lanes (space, ocean)
GET  /api/recap                last week in 30 seconds + this week's plan (the brain shows it on Mondays)

A page earns its spot by answering one question the moment it opens — "Is today's Short out?", "What's stuck?",
"Where are the gaps?" — with the next action right there. The detail below it is for when you want to dig.
"""
import datetime, json, re, shutil, statistics
from pathlib import Path

import studio_ext_desk as desk

HERE = Path(__file__).resolve().parent
OUT, CFG, PKG = HERE / "out", HERE / "cfg", HERE / "packaging"
OFF_LANES = ("space", "ocean")


def V(q, answer, detail="", tone="info", actions=()):
    return {"q": q, "answer": answer, "detail": detail, "tone": tone, "actions": list(actions)}


def age_days(p):
    return (datetime.datetime.now().timestamp() - p.stat().st_mtime) / 86400


# ------------------------------------------------------------------ one per page
def v_today():
    import studio_ext_day
    d = studio_ext_day.day()
    p, left = d["post"], d["left"]
    if p["done"]:
        return V("Is today's Short out?", p["title"] + " ✓", f"{d['out']} of 7 out this week" + (f" · {d['streak']}-day streak" if d["streak"] else "")
                 + (f" · {left} other job{'s' if left != 1 else ''} below" if left else " · nothing else needs you"), "good",
                 [{"label": "Start today's run", "run": True}] if left else [])
    return V("Is today's Short out?", "Not yet — " + p["title"][0].lower() + p["title"][1:], p["why"], "warn",
             [{"label": "Do it now", "go": p["go"], "primary": True}, {"label": f"Walk me through all {left}", "run": True}])


def stale_videos():
    """Never-posted videos that are in the way: anything off the channel's lanes (old space/ocean builds), at any age,
    plus in-lane videos nobody has touched in 7+ days. Live and scheduled videos are never offered."""
    import studio_api, intelligence
    out = []
    for v in studio_api.videos():
        if v["stage"] not in ("making", "earlier", "ready") or v["id"].endswith("_tiktok") or "__" in v["id"] or v["posts"] or v["scheduled"]:
            continue
        lane = intelligence.lane_of(v["title"] + " " + v["id"].replace("_", " "))
        p = CFG / f"{v['id']}.json"
        old = p.exists() and age_days(p) > 7
        if lane in OFF_LANES or old:
            out.append({"id": v["id"], "title": v["title"], "days": int(age_days(p)) if p.exists() else 0, "lane": lane, "off": lane in OFF_LANES})
    return out


def v_videos():
    import studio_api
    vs = [v for v in studio_api.videos() if not v["id"].endswith("_tiktok")]
    c = lambda s: sum(1 for v in vs if v["stage"] == s)
    stale = stale_videos()
    parts = [f"{c('ready')} ready to post", f"{c('draft')} script{'s' if c('draft') != 1 else ''} waiting", f"{c('making')} being made"]
    acts = []
    if c("ready"):
        r = next(v for v in vs if v["stage"] == "ready")
        acts.append({"label": f"Post “{r['title'][:40]}”", "go": f"video/{r['id']}", "primary": True})
    if stale:
        acts.append({"label": f"Archive {len(stale)} stale video{'s' if len(stale) != 1 else ''}", "post": "/api/videos/archive", "body": {"ids": [s["id"] for s in stale]},
                     "confirm": "Archive these never-posted videos?\n\n" + "\n".join(f"• {s['title'][:70]}" for s in stale[:12])
                                + ("\n…" if len(stale) > 12 else "") + "\n\nTheir files move to cfg/archive/ — nothing is deleted."})
    off = sum(1 for s in stale if s["off"])
    old = len(stale) - off
    bits = ([f"{off} off-channel (old space/ocean) video{'s' if off != 1 else ''} never posted"] if off else []) + \
           ([f"{old} in-lane video{'s' if old != 1 else ''} untouched for 7+ days"] if old else [])
    detail = (" · ".join(bits) + " — archive them to clear the way (nothing is deleted).") if stale else "Nothing stuck."
    return V("What's ready, and what's stuck?", " · ".join(parts), detail, "warn" if stale or c("ready") else "good", acts)


def v_calendar():
    w = desk.week()
    today = datetime.date.today().isoformat()
    gaps = [d for d in w["days"] if d["date"] >= today and d.get("stage") not in ("live", "scheduled")]
    covered = sum(1 for d in w["days"] if d.get("stage") in ("live", "scheduled"))
    if not gaps:
        return V("Is something going out every day?", f"Yes — {covered} of 7 this week", "Every day left this week has a post.", "good")
    names = ", ".join(d["day"] for d in gaps)
    return V("Is something going out every day?", f"{len(gaps)} gap{'s' if len(gaps) != 1 else ''} left this week: {names}",
             f"{covered} of 7 days covered so far. One Short a day is the cadence the algorithm rewards.", "warn",
             [{"label": "Fill the next gap", "go": "make", "primary": True}])


def v_performance():
    import studio_api, studio_ext_nether
    rows = studio_api.performance()["rows"]
    if not rows:
        return V("What's working?", "No numbers yet", "Refresh the numbers and this answers itself.", "info", [{"label": "Refresh numbers", "job": "stats", "primary": True}])
    avg = statistics.mean(r["views"] for r in rows)
    best = rows[0]
    b = studio_ext_nether.brief()
    lanes = [l for l in b["lanes"] if l["videos"] >= 2]
    lane = f" {desk.LANE.get(lanes[0]['lane'], lanes[0]['lane'])} is your strongest lane ({lanes[0]['ratio']}× average)." if lanes else ""
    return V("What's working?", f"Best: “{best['title'][:70]}” — {best['views'] / avg:.1f}× your average" if avg else best["title"],
             f"{len(rows)} videos, {desk.n(avg)} views each on average.{lane}", "good",
             [{"label": "See the Brief", "go": "brief"}])


RULE_WORDS = ["the first spoken line is over 8 words — it has to land before the swipe",
              "the on-screen hook doesn't match what's said", "the first on-screen number comes after 3 seconds",
              "the opening frame is too still", "it runs longer than the platform's sweet spot",
              "one picture is held over 6 seconds", "the end card doesn't name the next video"]


def v_retention():
    import retention
    fails, n = [0] * len(RULE_WORDS), 0
    for vid, cfg in desk.short_cfgs(15):
        if cfg.get("format") == "landscape":
            continue
        n += 1
        for i, (ok, _) in enumerate(retention.check(cfg)[1]):
            fails[i] += not ok
    if not n:
        return V("Where do viewers leave?", "No videos yet", "", "info")
    if not any(fails):
        return V("Where do viewers leave?", "Every recent video passes the pacing rules", "Now the real watch time is the judge — check it after the numbers refresh.", "good")
    i = max(range(len(fails)), key=lambda k: fails[k])
    return V("Where do viewers leave?", f"Most common problem: {RULE_WORDS[i]}", f"{fails[i]} of your last {n} Shorts. "
             "New drafts are checked for this before they reach you — fix older ones in the draft or before re-rendering.", "warn",
             [{"label": "Open the Hook check", "go": "desk/content/hooks", "primary": True}])


def v_channel():
    import studio_channel
    c = studio_channel.channel()
    if not c.get("ready"):
        return V("Is the channel growing?", "No channel numbers yet", "Get them once and they stay fresh.", "info")
    w = c.get("weekly")
    if not w:
        return V("Is the channel growing?", f"{desk.n(c['channel']['subscribers'])} subscribers · {desk.n(c['channel']['views'])} views",
                 "Week-on-week growth appears after 7 days of history.", "info", [{"label": "The road to getting paid", "go": "money"}])
    return V("Is the channel growing?", f"This week: {w['subscribers']:+,} subscribers · {w['views']:+,} views",
             f"{desk.n(c['channel']['subscribers'])} subscribers in total.", "good" if w["subscribers"] > 0 else "warn",
             [{"label": "The road to getting paid", "go": "money"}])


def v_agents():
    d = desk.d_tasks()
    bad = d["panels"][0]["rows"]
    if not bad:
        return V("Is everything running?", "Yes — nothing broke this week", "", "good")
    return V("Is everything running?", f"{len(bad)} thing{'s' if len(bad) != 1 else ''} broke this week", f"Newest: {bad[0]['main']} — {bad[0]['sub']}", "bad",
             [{"label": "See what broke", "go": "desk/control/tasks", "primary": True}])


PRIORITY = [  # what each connection blocks, most important first
    ("Drafting (Claude)", "writing scripts"), ("Rendering (ffmpeg)", "making any video"), ("Narration voice", "narration"),
    ("Fonts", "captions and titles"), ("Buffer", "posting"), ("Video hosting (R2)", "posting"), ("Daily run (7:00)", "the automatic daily run and reminders"),
    ("YouTube (true numbers)", "learning what works"), ("Stats", "learning what works"), ("AI art (Cloudflare)", "original character art"),
    ("vidIQ (title scores)", "title scores"), ("Jarvis", "asking questions (⌘K)"), ("Disk space", "rendering")]


def v_settings():
    import studio_api
    h = {x["name"]: x for x in studio_api.health()}
    broken = [(n, why) for n, why in PRIORITY if n in h and not h[n]["ok"]]
    ok = sum(1 for x in h.values() if x["ok"])
    if not broken:
        return V("Is everything connected?", f"Yes — all {len(h)} working", "", "good")
    n, why = broken[0]
    rest = ", ".join(b[0] for b in broken[1:4])
    return V("Is everything connected?", f"Fix {n} first — it blocks {why}", f"{ok} of {len(h)} working. {h[n]['detail']}." + (f" Then: {rest}." if rest else ""),
             "bad" if why in ("writing scripts", "making any video", "posting", "narration") else "warn")


def v_ideas():
    import intelligence
    items = desk.open_ideas()
    off = [i for s, i in items if desk.idea_lane(s, i["hook"]) in OFF_LANES]
    lanes = sum(1 for s, i in items if desk.idea_lane(s, i["hook"]) in desk.CHANNEL_LANES)
    acts = [{"label": "Scout the next 3", "post": "/api/desk/scout_backlog", "body": {}, "primary": True}]
    if off:
        acts.append({"label": f"Dismiss {len(off)} off-lane ideas", "post": "/api/ideas/dismiss_offlane", "body": {},
                     "confirm": f"Dismiss {len(off)} space/ocean ideas? They stay in TOPICS.md and can be restored from Ideas."})
    return V("Is the backlog full of the right ideas?", f"{lanes} ideas in your lanes · {len(off)} off-lane",
             "Off-lane ideas (old space/ocean backlog) never get picked for Shorts, but they clutter this list." if off else "The backlog is on-channel.",
             "warn" if off else "good", acts)


def v_comments():
    import studio_api, studio_channel
    c = studio_channel.comments(studio_api.done_map())
    wait = [x for x in c["comments"] if not x["done"]]
    if not c.get("fetched"):
        return V("Who's waiting for a reply?", "Comments haven't been fetched yet", "Refresh numbers pulls them from YouTube.", "info",
                 [{"label": "Refresh numbers", "job": "stats", "primary": True}])
    if not wait:
        return V("Who's waiting for a reply?", "Nobody — you're all caught up", "Replying in the first hour tells YouTube the video has a conversation going.", "good")
    return V("Who's waiting for a reply?", f"{len(wait)} comment{'s' if len(wait) != 1 else ''} waiting",
             f"Oldest: “{wait[-1].get('text', '')[:90]}” — {wait[-1].get('author', '')}", "warn",
             [{"label": "Draft replies for me", "job": "replies", "primary": True}])


PAGES = {"comments": v_comments, "today": v_today, "videos": v_videos, "calendar": v_calendar, "performance": v_performance, "retention": v_retention,
         "channel": v_channel, "agents": v_agents, "settings": v_settings, "ideas": v_ideas}


def verdict(page):
    f = PAGES.get(page)
    if not f:
        raise ValueError("No verdict for this page.")
    try:
        return f()
    except Exception as e:
        return V("", "", f"Couldn't work this out: {type(e).__name__}: {e}", "info")


# ------------------------------------------------------------------ actions
def archive(body):
    ids = [i for i in body.get("ids", []) if re.fullmatch(r"[a-z0-9_]+", str(i))]
    dest = CFG / "archive"
    dest.mkdir(exist_ok=True)
    moved = 0
    for vid in ids:
        for src in (CFG / f"{vid}.json", CFG / f"{vid}_tiktok.json", PKG / f"{vid}.json"):
            if src.exists():
                shutil.move(str(src), str(dest / (src.name if src.parent == CFG else f"packaging__{src.name}")))
                moved += src.parent == CFG and not src.stem.endswith("_tiktok")
    return {"ok": True, "reply": f"Archived {moved} video{'s' if moved != 1 else ''} — files are in cfg/archive/ if you want one back."}


def dismiss_offlane(body):
    import intelligence, studio_api
    n = 0
    for s, i in desk.open_ideas():
        if desk.idea_lane(s, i["hook"]) in OFF_LANES:
            studio_api.set_done(f"idea:{i['slug']}")
            n += 1
    return {"ok": True, "reply": f"Dismissed {n} off-lane idea{'s' if n != 1 else ''}."}


# ------------------------------------------------------------------ Monday recap
def recap():
    """Last week in 30 seconds: what went out, the best one, what the system learned — and this week's plan."""
    import studio_api, learning, daily
    today = datetime.date.today()
    mon = today - datetime.timedelta(days=today.weekday())
    last_mon = mon - datetime.timedelta(days=7)
    out, best = [], None
    for v in studio_api.videos():
        sent = [studio_api.parse_dt(p.get("sentAt")) for p in v["posts"] if p.get("sentAt")]
        if any(s and last_mon <= s.astimezone().date() < mon for s in sent):
            out.append(v)
            if not best or v["views"] > best["views"]:
                best = v
    L = learning.summary()
    nxt, why = daily.pick_topic()
    nxt_long, _ = daily.pick_long_topic()
    return {"week": last_mon.isoformat(), "label": f"{last_mon:%-d %b} – {(mon - datetime.timedelta(days=1)):%-d %b}",
            "out": len(out), "best": {"id": best["id"], "title": best["title"], "views": best["views"], "picture": best.get("picture")} if best else None,
            "lesson": (L["lessons"] or [None])[0],
            "plan": {"short": nxt, "why": why, "long": nxt_long}}


GET_PREFIX = {"/api/verdict/": verdict}
GET = {"/api/recap": recap}
POST = {"/api/videos/archive": archive, "/api/ideas/dismiss_offlane": dismiss_offlane}
