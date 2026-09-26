"""Studio extension: every sub-agent's desk — the one question it answers, what it has found, and what you can do.

GET  /api/desk/<agent>/<sub>     {"question", "stats", "panels", "actions", "tasks"} for that sub-agent
POST /api/desk/scout_backlog     Intelligence scouts the next 3 unscored ideas in the background

A desk is built from the sub-agent's own work (scorecards, drafts, renders, posts, numbers), so clicking any
sub-agent on the brain or in a hub shows what it knows, not a shared page. Rows can carry their own action
(Scout this, Make it, Open) so the desk is where the work happens.
"""
import datetime, json, re, statistics, threading
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
OUT, CFG, PKG, EPS = HERE / "out", HERE / "cfg", HERE / "packaging", HERE / "episodes"
LANE = {"marvel": "Marvel & comics", "anime": "Anime", "gaming": "Gaming", "space": "Space", "ocean": "Ocean",
        "creature": "Creatures / real biology", "other": "Other"}
CHANNEL_LANES = ["marvel", "anime", "gaming", "creature"]


def J(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def n(v):
    v = int(v or 0)
    return f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}k" if v >= 1e5 else f"{v / 1e3:.1f}k" if v >= 1e4 else f"{v:,}"


def row(main, sub="", badge=None, tone=None, **kw):
    return {"main": main, "sub": sub, "badge": badge, "tone": tone, **kw}


def panel(title, rows, empty, note=""):
    return {"title": title, "rows": rows, "empty": empty, "note": note}


def cards():
    import learning
    return sorted(learning._cards(), key=lambda c: c.get("at", ""), reverse=True)


def ev(c, k):
    return (c.get("evidence") or {}).get(k) or {}


def intel_row(c, badge, sub):
    return row(c["topic"], sub, badge, None, act={"label": "Scorecard", "go": "investigate"})


def idea_lane(section, hook):
    """An idea's lane: the section it sits in wins for the old backlogs (everything under Space is space), else its words."""
    import intelligence
    s = section.lower()
    if s.startswith(("space", "ocean")):
        return "space" if s.startswith("space") else "ocean"
    return intelligence.lane_of(hook)


def open_ideas():
    import studio_api
    return [(s["name"], i) for s in studio_api.ideas()["sections"] for i in s["items"] if not i["made"] and not i["dismissed"]]


def age_days(p):
    return (datetime.datetime.now().timestamp() - p.stat().st_mtime) / 86400


def short_cfgs(limit=12):
    out = []
    for p in sorted(CFG.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if p.stem.startswith(("_", "test")) or p.stem.endswith("_tiktok") or re.search(r"_t\d$", p.stem):
            continue
        c = J(p)
        if c and c.get("segments"):
            out.append((p.stem, c))
        if len(out) >= limit:
            break
    return out


def title_of(vid, cfg=None):
    if "__" in vid:                                        # a Short cut from a long-form chapter
        ep, ch = vid.split("__", 1)
        e = J(EPS / f"{ep}.json", {}) or {}
        c = next((c for c in e.get("chapters", []) if c.get("id") == ch), {})
        return f"{c.get('title') or ch} — from “{e.get('title', ep)}”"
    pk = J(PKG / f"{vid}.json", {}) or {}
    return pk.get("title") or ((cfg or {}).get("draft") or {}).get("topic") or vid.replace("_", " ")


# ------------------------------------------------------------------ Intelligence
def d_ideas():
    by = {c["slug"]: c for c in cards()}
    import intelligence
    items = []
    for sec, i in open_ideas():
        c = by.get(intelligence.slug(i["hook"]))
        items.append((c["score"] if c else -1, sec, i, c))
    order = CHANNEL_LANES + ["other", "space", "ocean"]            # unscouted: the channel's lanes first, old backlogs last
    items.sort(key=lambda x: (-x[0], order.index(idea_lane(x[1], x[2]["hook"])) if idea_lane(x[1], x[2]["hook"]) in order else 9))
    rows = []
    for score, sec, i, c in items[:15]:
        lane = idea_lane(sec, i["hook"])
        ice = "iceberg" in i["hook"].lower()
        if c:
            rows.append(row(i["hook"], f"{sec} · {c['verdict']}", f"{score}/100",
                            "good" if score >= 70 else "warn" if score < 50 else None,
                            act={"label": "Draft it", "post": "/api/make/draft",
                                 "body": {"topic": i["hook"], "kind": "long" if ice else "short", **({"style": "iceberg"} if ice else {})}}))
        else:
            where = sec if sec.lower().startswith(LANE.get(lane, lane).lower()[:5]) else f"{sec} · {LANE.get(lane, lane)}"
            rows.append(row(i["hook"], f"{where} · not scouted yet{' · long-form' if ice else ''}", None, None,
                            act={"label": "Scout", "post": "/api/intel/run", "body": {"topic": i["hook"]}}))
    scored = sum(1 for x in items if x[3])
    lanes = {}
    for _, sec, i, _ in items:
        l = idea_lane(sec, i["hook"])
        lanes[l] = lanes.get(l, 0) + 1
    return {"question": "Out of everything waiting, what should we make next — and is the backlog in the channel's lanes?",
            "stats": [{"k": "Open ideas", "v": len(items)}, {"k": "Scouted", "v": f"{scored} of {len(items)}"},
                      {"k": "In your lanes", "v": sum(v for k, v in lanes.items() if k in CHANNEL_LANES)},
                      {"k": "Off-lane (space/ocean)", "v": sum(v for k, v in lanes.items() if k in ("space", "ocean"))}],
            "panels": [panel("Ranked: scouted ideas first, by score", rows, "The backlog is empty — add ideas in Ideas.",
                             "Scouting an idea fills its score. Draft it sends it to Content.")],
            "actions": [{"label": "Scout the next 3", "post": "/api/desk/scout_backlog", "body": {}, "primary": True},
                        {"label": "Open the full backlog", "go": "ideas"}]}


def d_demand():
    cs = [c for c in cards() if ev(c, "demand")]
    ranked = sorted(cs, key=lambda c: -ev(c, "demand").get("median", 0))
    top = {}
    for c in cs[:20]:
        for v in ev(c, "demand").get("top", []):
            top.setdefault(v["url"], {**v, "topic": c["topic"]})
    top = sorted(top.values(), key=lambda v: -v["views"])[:8]
    meds = [ev(c, "demand").get("median", 0) for c in cs]
    return {"question": "Do people actually watch Shorts about this — right now, not years ago?",
            "stats": [{"k": "Topics checked", "v": len(cs)}, {"k": "Best median", "v": n(max(meds)) if meds else "—"},
                      {"k": "Typical median", "v": n(statistics.median(meds)) if meds else "—"},
                      {"k": "Scored as", "v": "≤1k = 0 · ≥1M = full"}],
            "panels": [panel("Topics by demand (median views of similar Shorts, last 12 months)",
                             [row(c["topic"], ev(c, "demand").get("say", ""), n(ev(c, "demand").get("median")),
                                  "good" if ev(c, "demand").get("median", 0) >= 100_000 else "warn" if ev(c, "demand").get("median", 0) < 5_000 else None)
                              for c in ranked[:12]], "No demand checked yet — check a topic below."),
                       panel("The most-watched Shorts it found — study their hooks",
                             [row(v["title"], f"{v['channel']} · for “{v['topic']}”", n(v["views"]), None, url=v["url"]) for v in top],
                             "Nothing yet.")],
            "actions": [{"label": "Check demand", "post": "/api/intel/run", "field": "topic",
                         "placeholder": "A topic, e.g. Goku's hair colour", "primary": True}]}


def d_competitors():
    cs = [c for c in cards() if ev(c, "competitors")]
    bo, seen = [], set()
    for c in cs:
        for b in ev(c, "competitors").get("breakouts", []):
            if b["url"] not in seen:
                seen.add(b["url"])
                bo.append({**b, "topic": c["topic"]})
    shares = [ev(c, "competitors").get("small_channel_share", 0) for c in cs]
    return {"question": "Can a small channel win this topic, or do big channels own it?",
            "stats": [{"k": "Topics checked", "v": len(cs)}, {"k": "Small-channel breakouts", "v": len(bo)},
                      {"k": "Avg share from small channels", "v": f"{statistics.mean(shares):.0%}" if shares else "—"}],
            "panels": [panel("Small channels (<100k subs) that broke 100k views — your models",
                             [row(b["title"], f"{b['channel']} · {n(b.get('subs'))} subs · for “{b['topic']}”", n(b["views"]), "good", url=b["url"])
                              for b in sorted(bo, key=lambda b: -b["views"])[:10]], "No breakouts found yet."),
                       panel("Most winnable topics",
                             [row(c["topic"], ev(c, "competitors").get("say", ""), f"{ev(c, 'competitors').get('score', 0):.0%}")
                              for c in sorted(cs, key=lambda c: -ev(c, "competitors").get("score", 0))[:10]], "Nothing checked yet.")],
            "actions": [{"label": "Check a topic", "post": "/api/intel/run", "field": "topic", "placeholder": "A topic", "primary": True}]}


def d_fit():
    import intelligence
    ours = intelligence._our_videos()
    avg = statistics.mean(v["views"] for v in ours) if ours else 0
    lanes = {}
    for v in ours:
        lanes.setdefault(v["lane"], []).append(v)
    rows = []
    for l in [] if not ours else sorted(set(lanes) | set(CHANNEL_LANES), key=lambda l: -statistics.mean([v["views"] for v in lanes[l]]) if l in lanes else 0):
        vs = lanes.get(l, [])
        if not vs:
            rows.append(row(LANE.get(l, l), "No videos yet — untested. A good lane to try next.", "new"))
            continue
        m = statistics.mean(v["views"] for v in vs)
        r = m / avg if avg else 1
        best = max(vs, key=lambda v: v["views"])
        rows.append(row(LANE.get(l, l), f"{len(vs)} video(s) · avg {n(m)} · best: {title_of(best['id'])} ({n(best['views'])})",
                        f"{r:.1f}×", "good" if r >= 1.2 else "warn" if r < 0.8 and len(vs) >= 2 else None))
    return {"question": "Does this kind of video work on YOUR channel — which lanes pull their weight?",
            "stats": [{"k": "Videos measured", "v": len(ours)}, {"k": "Channel average", "v": n(avg)},
                      {"k": "Lanes", "v": len(lanes)}],
            "panels": [panel("Lanes vs your channel average (1.0× = average)", rows,
                             "No numbers yet — refresh the numbers first.", "Needs 2+ videos in a lane to judge; fewer counts as neutral.")],
            "actions": [{"label": "Refresh numbers", "job": "stats", "primary": True}, {"label": "Open Brief", "go": "brief"}]}


def d_rights():
    cs = [c for c in cards() if ev(c, "rights")]
    today = datetime.date.today().isoformat()
    ai_today = sum(1 for p in (HERE / "assets").glob("*.jpg") if datetime.date.fromtimestamp(p.stat().st_mtime).isoformat() == today) \
        if (HERE / "assets").exists() else 0
    ex = []
    for c in cs[:10]:
        for e in ev(c, "rights").get("examples", []):
            ex.append(row(e["title"].replace("File:", ""), f"{e['license']} · for “{c['topic']}”", None, None, url=e["page"]))
    return {"question": "Can we show this without a copyright strike — real public-domain photos, or original AI art?",
            "stats": [{"k": "Topics checked", "v": len(cs)}, {"k": "Images made today", "v": f"{ai_today} (~30/day free)"},
                      {"k": "Rule", "v": "Characters → original AI art only"}],
            "panels": [panel("Topics by usable visuals",
                             [row(c["topic"], ev(c, "rights").get("say", ""), f"{ev(c, 'rights').get('usable', 0)} photos",
                                  "warn" if ev(c, "rights").get("usable", 0) < 3 and not ev(c, "rights").get("copyright_lane") else None)
                              for c in cs[:12]], "Nothing checked yet."),
                       panel("Public-domain / CC photos it found", ex[:10], "None yet.")],
            "actions": [{"label": "Check a topic", "post": "/api/intel/run", "field": "topic", "placeholder": "A topic", "primary": True}]}


def d_sources():
    cs = [c for c in cards() if ev(c, "sources")]
    rows = []
    for c in cs[:12]:
        arts = ev(c, "sources").get("articles", [])
        if arts:
            rows.append(row(c["topic"], " · ".join(a["title"] for a in arts), f"{len(arts)}", None, url=arts[0]["url"]))
        else:
            rows.append(row(c["topic"], "No Wikipedia article — sourcing will be slow.", "0", "warn"))
    return {"question": "Where does fact-checking start — is there a solid source trail?",
            "stats": [{"k": "Topics checked", "v": len(cs)},
                      {"k": "No source found", "v": sum(1 for c in cs if not ev(c, "sources").get("articles"))}],
            "panels": [panel("Starting points (then follow their citations)", rows, "Nothing checked yet.",
                             "The Researcher verifies every claim against primary sources before a script is written.")],
            "actions": [{"label": "Check a topic", "post": "/api/intel/run", "field": "topic", "placeholder": "A topic", "primary": True}]}


# ------------------------------------------------------------------ Content
def all_drafts():
    import drafter, drafter_long
    return [dict(d, kind="short") for d in drafter.drafts()] + [dict(d, kind="long") for d in drafter_long.drafts()]


def d_research():
    import drafter
    rows = []
    for p in sorted((OUT / "drafts").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10] if (OUT / "drafts").exists() else []:
        r = (J(p, {}) or {}).get("research") or {}
        facts = r.get("facts") or []
        if not facts:
            continue
        rows.append(row(r.get("angle") or p.stem, f"True version: {r.get('true_version', '—')}"[:220],
                        f"{len(facts)} facts", None, go=f"draft/{p.stem}" if (CFG / f"{p.stem}.json").exists() or (EPS / f"{p.stem}.json").exists() else None))
    return {"question": "Is every claim true — and where's the proof?",
            "stats": [{"k": "Researched", "v": len(rows)}, {"k": "Minimum", "v": "3 sourced facts or it stops"},
                      {"k": "Sources", "v": "primary, publishers, papers — no fan wikis"}],
            "panels": [panel("Recent research (angle · the true version · facts with sources)", rows,
                             "No research yet — draft a video and it starts here.")],
            "actions": [{"label": "Draft a Short", "post": "/api/make/draft", "field": "topic", "placeholder": "Topic", "primary": True}]}


def d_script():
    ds = all_drafts()
    rows = [row(d.get("title") or d.get("topic"), f"{'Long-form' if d['kind'] == 'long' else 'Short'} · {len(d.get('lines', []))} lines · drafted {str(d.get('at', ''))[:10]}",
                "waiting", "warn", act={"label": "Review", "go": f"draft/{d['id']}"}) for d in ds]
    made = [p for p in CFG.glob("*.json") if age_days(p) < 7 and not p.stem.endswith("_tiktok") and not (J(p, {}) or {}).get("draft")]
    return {"question": "What's written and waiting for your approval?",
            "stats": [{"k": "Waiting for you", "v": len(ds)}, {"k": "Approved this week", "v": len(made)},
                      {"k": "Target", "v": "7 Shorts + 1 long-form a week"}],
            "panels": [panel("Scripts waiting for you", rows, "Nothing waiting — the daily run drafts the next one at 7:00.")],
            "actions": [{"label": "Draft a Short", "post": "/api/make/draft", "field": "topic", "placeholder": "Topic", "primary": True},
                        {"label": "Open Make", "go": "make"}]}


def d_packaging():
    rows = []
    for vid, cfg in short_cfgs(12):
        pk = J(PKG / f"{vid}.json")
        if not pk:
            rows.append(row(title_of(vid, cfg), "No packaging — no title, description or tags yet.", "missing", "warn"))
            continue
        desc = pk.get("youtube_description", "")
        miss = [k for k, ok in (("title options", len(pk.get("title_options", [])) >= 2), ("tags", bool(pk.get("tags") or pk.get("youtube_tags"))),
                                ("pinned comment", bool(pk.get("pinned_comment"))), ("links", "── links ──" in desc)) if not ok]
        rows.append(row(pk.get("title", vid), "Missing: " + ", ".join(miss) if miss else "Title options, description, tags, pinned comment, links",
                        "ok" if not miss else f"{len(miss)} gap(s)", "good" if not miss else "warn",
                        act={"label": "Open", "go": f"draft/{vid}" if cfg.get("draft") else f"video/{vid}"}))
    return {"question": "Will people click it — and can they find it?",
            "stats": [{"k": "Recent videos", "v": len(rows)}, {"k": "Complete", "v": sum(1 for r in rows if r["tone"] == "good")}],
            "panels": [panel("Packaging per video", rows, "No videos yet.")],
            "actions": [{"label": "Refresh links on all", "post": "/api/business/links", "body": {}}]}


def d_hooks():
    import retention
    rows = []
    for vid, cfg in short_cfgs(12):
        if cfg.get("format") == "landscape":
            continue
        score, checks = retention.check(cfg)
        bad = [m for ok, m in checks if not ok]
        rows.append(row(title_of(vid, cfg), bad[0] if bad else "Passes every pacing rule", f"{score}",
                        "good" if not bad else "warn", act={"label": "Open", "go": f"draft/{vid}" if cfg.get("draft") else "retention"}))
    return {"question": "Will people keep watching past the first 3 seconds?",
            "stats": [{"k": "Checked", "v": len(rows)}, {"k": "Pass every rule", "v": sum(1 for r in rows if r["tone"] == "good")}],
            "panels": [panel("Pacing check per video (first failing rule shown)", rows, "No videos yet.")],
            "actions": [{"label": "Open Retention", "go": "retention", "primary": True}]}


def d_titles():
    bal = J(OUT / "vidiq_balance.json", {}) or {}
    rows = []
    for vid, cfg in short_cfgs(12):
        pk = J(PKG / f"{vid}.json", {}) or {}
        opts = [o if isinstance(o, dict) else {"title": o} for o in pk.get("title_options", [])]
        sc = [o for o in opts if o.get("score") is not None]
        if not opts:
            continue
        best = max(sc, key=lambda o: o["score"]) if sc else None
        rows.append(row(pk.get("title", vid), f"Best scored: {best['title']} — {best.get('note', '')}" if best else f"{len(opts)} options, not scored yet",
                        f"{best['score']}" if best else "—", "good" if best and best["score"] >= 70 else None,
                        act=None if sc else {"label": "Score", "job": "score", "id": vid}))
    return {"question": "Which title gets the click?",
            "stats": [{"k": "vidIQ credits", "v": bal.get("credits", "?")}, {"k": "Cost", "v": "5 credits per title"}],
            "panels": [panel("Title options per video", rows, "No title options yet.")],
            "actions": []}


def d_episodes():
    import drafter_long
    eps = [p for p in EPS.glob("*.json") if not p.stem.startswith("_")]
    rows = []
    for p in sorted(eps, key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
        e = J(p, {}) or {}
        state = "draft" if e.get("draft") else "rendered" if (OUT / f"{p.stem}_long.mp4").exists() else "approved"
        rows.append(row(e.get("title", p.stem), f"{'Iceberg · ' if e.get('style') == 'iceberg' else ''}{len(e.get('chapters', []))} chapters",
                        state, "warn" if state == "draft" else "good" if state == "rendered" else None,
                        act={"label": "Review" if state == "draft" else "Open", "go": f"draft/{p.stem}" if state == "draft" else "make"}))
    from daily import pick_long_topic
    nxt, why = pick_long_topic()
    return {"question": "What's this week's long-form — and is it on track for Sunday?",
            "stats": [{"k": "Episodes", "v": len(eps)}, {"k": "Next up", "v": nxt or "—"}, {"k": "Why", "v": why}],
            "panels": [panel("Long-form episodes", rows, "None yet — draft one below, or Sunday's run drafts one.")],
            "actions": [{"label": "Draft as iceberg", "post": "/api/make/draft", "field": "topic", "extra": {"kind": "long", "style": "iceberg"},
                         "placeholder": "Any topic — e.g. Pokémon, Dragon Ball, cancelled games", "primary": True},
                        {"label": "Draft as episode", "post": "/api/make/draft", "field": "topic", "extra": {"kind": "long"}, "placeholder": "Topic"}]}


# ------------------------------------------------------------------ Production
def vids():
    import studio_api
    return studio_api.videos()


def d_videos():
    vs = vids()
    stages = {}
    for v in vs:
        stages[v["stage"]] = stages.get(v["stage"], 0) + 1
    act = [v for v in vs if v["stage"] in ("making", "ready", "draft")]
    return {"question": "Where is every video, from script to live?",
            "stats": [{"k": s.capitalize(), "v": stages.get(s, 0)} for s in ("draft", "making", "ready", "scheduled", "live")],
            "panels": [panel("Needs a push", [row(v["title"], {"draft": "Script waiting for you", "making": "Not rendered yet",
                                                                "ready": "Rendered + checked — ready to post"}[v["stage"]], v["stage"],
                                                  "good" if v["stage"] == "ready" else "warn",
                                                  act={"label": "Open", "go": f"draft/{v['id']}" if v["stage"] == "draft" else f"video/{v['id']}"})
                                              for v in act[:12]], "Nothing stuck.")],
            "actions": [{"label": "Open Videos", "go": "videos", "primary": True}]}


def recent_tasks(agent, sub, k=8):
    """This sub-agent's tasks; a step inherits its parent job's retry, so Retry re-runs the whole job."""
    with nether.db() as c:
        out = [nether._row(r) for r in c.execute("SELECT * FROM tasks WHERE agent=? AND sub=? ORDER BY id DESC LIMIT ?", (agent, sub, k))]
        for t in out:
            if t.get("parent") and not t.get("retry"):
                p = c.execute("SELECT retry FROM tasks WHERE id=?", (t["parent"],)).fetchone()
                t["retry"] = json.loads(p[0]) if p and p[0] else None
        return out


def fail_panel(agent, sub, what):
    bad = [t for t in recent_tasks(agent, sub, 20) if t["status"] == "failed"][:5]
    return panel(f"Recent {what} failures", [row(t["title"] + (f" · {t['video']}" if t.get("video") else ""), (t.get("error") or "").strip().splitlines()[-1][:200] if t.get("error") else "",
                                                 "failed", "bad") for t in bad], "No failures recently.")


def d_visuals():
    today = datetime.date.today().isoformat()
    a = list((HERE / "assets").glob("*.jpg")) if (HERE / "assets").exists() else []
    made = sum(1 for p in a if datetime.date.fromtimestamp(p.stat().st_mtime).isoformat() == today)
    return {"question": "Does every beat have a picture — real where possible, original art where not?",
            "stats": [{"k": "Images in the library", "v": len(a)}, {"k": "Made today", "v": f"{made} of ~30 free"},
                      {"k": "Real photos", "v": "Wikimedia Commons, PD / CC only"}],
            "panels": [fail_panel("production", "visuals", "visuals")], "actions": []}


def d_tiktok():
    import retention
    rows = []
    for vid, cfg in short_cfgs(12):
        tk = J(CFG / f"{vid}_tiktok.json")
        if cfg.get("format") == "landscape":
            continue
        if not tk:
            rows.append(row(title_of(vid, cfg), "No TikTok cut yet — it's made when the video builds.", "—"))
            continue
        a, b = retention.total(cfg), retention.total(tk)
        rows.append(row(title_of(vid, cfg), f"{a:.0f}s → {b:.0f}s · cold-open number, punch-ins, tight gaps", f"-{a - b:.0f}s",
                        "good" if b <= 35 else "warn"))
    return {"question": "Is the TikTok version tight enough for TikTok's swipe speed?",
            "stats": [{"k": "Target", "v": "≤35s, number in the first second"}],
            "panels": [panel("Main cut → TikTok cut", rows, "No videos yet.")],
            "actions": [{"label": "Open Retention", "go": "retention", "primary": True}]}


def mp4s(pattern="*.mp4", k=10):
    return sorted((p for p in OUT.glob(pattern) if "_preview" not in p.stem), key=lambda p: p.stat().st_mtime, reverse=True)[:k]


def dur(p):
    import subprocess
    try:
        return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                             timeout=5).decode().strip())
    except Exception:
        return None


def d_render():
    rows = []
    for p in mp4s():
        d = dur(p)
        rows.append(row(title_of(p.stem.removesuffix("_tiktok").removesuffix("_long")), f"{p.name} · {p.stat().st_size / 1e6:.0f} MB · "
                        f"{datetime.datetime.fromtimestamp(p.stat().st_mtime):%a %-d %b %H:%M}", f"{int(d // 60)}:{int(d % 60):02d}" if d else "—"))
    return {"question": "Did the video come out — narration, captions, motion, score and mix?",
            "stats": [{"k": "Renders on disk", "v": len(list(OUT.glob('*.mp4')))}],
            "panels": [panel("Latest renders", rows, "Nothing rendered yet."), fail_panel("production", "render", "render")], "actions": []}


def d_qa():
    rows = [row(title_of(p.stem.removesuffix("_qa_contact")), "Contact sheet — one frame per beat. Look for blank frames or text off-screen.",
                None, None, img=p.name, act={"label": "Open", "go": f"video/{p.stem.removesuffix('_qa_contact')}"})
            for p in sorted(OUT.glob("*_qa_contact.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]]
    return {"question": "Is every render actually right before you see it — sizes, length, blank frames?",
            "stats": [{"k": "Checked", "v": len(list(OUT.glob('*_qa_contact.jpg')))}],
            "panels": [panel("Latest contact sheets", rows, "No QA yet."), fail_panel("production", "qa", "QA")], "actions": []}


def d_thumbnail():
    ps = sorted(OUT.glob("*_thumb*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[:9]
    rows = [row(title_of(re.sub(r"_thumb\d?$", "", p.stem).removesuffix("_long")),
                "Test & Compare option " + (re.search(r"\d$", p.stem)[0] if re.search(r"thumb\d$", p.stem) else "1"), None, None, img=p.name) for p in ps]
    return {"question": "Will the thumbnail win the click at phone size?",
            "stats": [{"k": "Thumbnails", "v": len(list(OUT.glob('*_thumb*.jpg')))}, {"k": "Long-form", "v": "3 options for Test & Compare"}],
            "panels": [panel("Latest thumbnails", rows, "None yet.")], "actions": []}


def d_bundle():
    import studio_api
    env = studio_api.env_names()
    ok = all(env.get(k) for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET", "R2_PUBLIC_BASE_URL"))
    return {"question": "Are the video files hosted so Buffer can post them?",
            "stats": [{"k": "R2 hosting", "v": "connected" if ok else "not set up"}],
            "panels": [fail_panel("production", "bundle", "upload")],
            "actions": [{"label": "Open Settings", "go": "settings", "primary": not ok}]}


def d_longform():
    rows = []
    for p in mp4s("*_long.mp4", 6):
        vid = p.stem
        d = dur(p)
        th = len(list(OUT.glob(f"{vid}_thumb*.jpg")))
        rows.append(row(title_of(vid), f"{th} thumbnail(s) · chapters in the description", f"{int(d // 60)}:{int(d % 60):02d}" if d else "—",
                        "good" if d and d >= 480 else "warn" if d else None))
    return {"question": "Is the weekly long-form rendered, 8+ minutes, with chapters and 3 thumbnails?",
            "stats": [{"k": "Rendered", "v": len(rows)}, {"k": "Why 8+ min", "v": "mid-roll ads + watch hours"}],
            "panels": [panel("Long-form renders", rows, "None yet — approve a long-form draft and it renders."),
                       fail_panel("production", "longform", "long-form")],
            "actions": [{"label": "Open Make", "go": "make", "primary": True}]}


# ------------------------------------------------------------------ Publishing
def d_calendar():
    import studio_channel
    cal = studio_channel.calendar(days_back=0, days_ahead=7)
    days = {}
    for i in cal["items"]:
        days.setdefault(i["at"][:10], []).append(i)
    rows = []
    for k in range(7):
        d = (datetime.date.today() + datetime.timedelta(days=k)).isoformat()
        it = days.get(d, [])
        label = datetime.date.fromisoformat(d).strftime("%a %-d %b")
        rows.append(row(label, " · ".join(sorted({x["title"] for x in it})) or "Nothing going out — a gap.",
                        f"{len(it)} post(s)" if it else "gap", None if it else "warn"))
    return {"question": "Is something going out every day this week?",
            "stats": [{"k": "Days covered", "v": f"{sum(1 for r in rows if r['tone'] != 'warn')} of 7"}],
            "panels": [panel("Next 7 days", rows, "")],
            "actions": [{"label": "Open Calendar", "go": "calendar", "primary": True}]}


def d_schedule():
    vs = vids()
    ready = [v for v in vs if v["stage"] == "ready"]
    import studio_channel
    q = [i for i in studio_channel.calendar(0, 30)["items"] if i["state"] == "scheduled"]
    return {"question": "What's ready to go out — and what's already queued? (Nothing posts without you.)",
            "stats": [{"k": "Ready to post", "v": len(ready)}, {"k": "Queued", "v": len(q)}],
            "panels": [panel("Ready — press Post on the video", [row(v["title"], "Rendered, checked, packaged", "ready", "good",
                                                                     act={"label": "Open", "go": f"video/{v['id']}"}) for v in ready], "Nothing ready."),
                       panel("Queued on Buffer (move or pull from the calendar)",
                             [row(i["title"], f"{i['platform']} · {i['at'][:16].replace('T', ' ')}") for i in q[:12]], "Queue is empty.")],
            "actions": [{"label": "Open Calendar", "go": "calendar"}]}


# ------------------------------------------------------------------ Analytics
def d_performance():
    import studio_api
    p = studio_api.performance()
    rs = p["rows"]
    tot = sum(r["views"] for r in rs)
    return {"question": "What's working — and what isn't?",
            "stats": [{"k": "Total views", "v": n(tot)}, *[{"k": k.capitalize(), "v": n(v)} for k, v in p["platforms"].items()]],
            "panels": [panel("Top 5", [row(r["title"], ", ".join(sorted({x["platform"] for x in r["posts"]})), n(r["views"]), "good",
                                           act={"label": "Open", "go": f"video/{r['id']}"}) for r in rs[:5]], "No numbers yet."),
                       panel("Bottom 5 — what do they share?", [row(r["title"], ", ".join(sorted({x["platform"] for x in r["posts"]})), n(r["views"]), "warn",
                                                                  act={"label": "Open", "go": f"video/{r['id']}"}) for r in rs[-5:][::-1]] if len(rs) > 5 else [], "Needs 6+ videos.")],
            "actions": [{"label": "Open Performance", "go": "performance", "primary": True}]}


def d_retention_a():
    stats = (J(OUT / "stats.json", {}) or {}).get("videos", {})
    rows = []
    import retention
    for vid, cfg in short_cfgs(30):
        ps = [p for p in stats.get(vid, []) if p.get("averageTimeWatched") is not None]
        if not ps:
            continue
        w = statistics.mean(p["averageTimeWatched"] for p in ps)
        L = retention.total(cfg)
        rows.append(row(title_of(vid, cfg), f"avg watched {w:.1f}s of {L:.0f}s ({', '.join(sorted({p['platform'] for p in ps}))})",
                        f"{w / L:.0%}" if L else "—", "good" if L and w / L >= 0.7 else "warn" if L and w / L < 0.4 else None))
    rows.sort(key=lambda r: r["badge"] or "", reverse=True)
    return {"question": "How much of each video do people actually watch?",
            "stats": [{"k": "Videos with watch time", "v": len(rows)}, {"k": "Good", "v": "70%+ watched"}],
            "panels": [panel("Share of the video watched (TikTok/Instagram via Buffer)", rows, "No watch-time data yet — refresh the numbers.")],
            "actions": [{"label": "Open Retention", "go": "retention", "primary": True}]}


def d_stats():
    s, y = J(OUT / "stats.json", {}) or {}, J(OUT / "youtube.json", {}) or {}
    import studio_api
    return {"question": "Are the numbers fresh and true?",
            "stats": [{"k": "Buffer (TikTok/IG)", "v": studio_api.when(s.get("updated")) or "never"},
                      {"k": "YouTube", "v": studio_api.when(y.get("fetched")) or "never"},
                      {"k": "Videos tracked", "v": len(s.get("videos", {}))}],
            "panels": [fail_panel("analytics", "stats", "refresh")],
            "actions": [{"label": "Refresh numbers", "job": "stats", "primary": True}]}


def d_learning():
    import learning
    L = learning.summary()
    cs = L["cards"]
    linked = [c for c in cs if c.get("views") is not None]
    rows = [row(k, f"started at {L['default'][k]}", f"{v:g}", "good" if v > L["default"][k] else "warn" if v < L["default"][k] else None)
            for k, v in L["weights"].items()]
    return {"question": "Is the system getting smarter — do its predictions match real views?",
            "stats": [{"k": "Scorecards", "v": len(cs)}, {"k": "Checked against real views", "v": len(linked)},
                      {"k": "Your calls", "v": sum(1 for c in cs if c.get("decision"))}],
            "panels": [panel("What it has learned", [row(l) for l in L["lessons"]], "Needs 4+ scorecards made into videos with real views."),
                       panel("Score weights now vs the start", rows, ""),
                       panel("Predictions vs results", [row(c["topic"], f"predicted {c['score']}/100", n(c["views"]) + " views") for c in linked[:8]],
                             "No predictions linked to real videos yet.")],
            "actions": [{"label": "Re-learn now", "post": "/api/learning/run", "body": {}, "primary": True}]}


# ------------------------------------------------------------------ Business
def d_community():
    import studio_api, studio_channel
    c = studio_channel.comments(studio_api.done_map())
    wait = [x for x in c["comments"] if not x["done"]]
    return {"question": "Who's waiting for a reply? (Early replies build the loyal core.)",
            "stats": [{"k": "Waiting", "v": len(wait)}, {"k": "Fetched", "v": studio_api.when(c.get("fetched")) or "never"}],
            "panels": [panel("Waiting for a reply", [row(x.get("text", "")[:160], f"{x.get('author', '')} · {len(x.get('drafts', []))} drafted repl(ies)")
                                                     for x in wait[:10]], "Nobody waiting.")],
            "actions": [{"label": "Draft replies", "job": "replies", "primary": bool(wait)}, {"label": "Open Comments", "go": "comments"}]}


def d_monetisation():
    import business
    m = business.money()
    P, rows = m["plan"], []
    if P.get("ready"):
        for M in (P["first"], P["ads"]):
            rows.append(row(f"{M['name']} — {M['pays']}", "Reached" if M["done"] else f"Holding it back: {M['bottleneck']}",
                            f"{M['pct']:.0%}", "good" if M["done"] else "warn" if M["key"] == P["next"] else None))
    return {"question": "How close is the channel to getting paid — and what's holding it back?",
            "stats": [{"k": "Next", "v": ("First money (500 subs)" if P.get("next") == "fan" else "Ad revenue") if P.get("ready") else "—"},
                      {"k": "Streams on", "v": f"{sum(1 for s in m['streams'] if s['on'])} of {len(m['streams'])}"}],
            "panels": [panel("The road", rows, "Refresh numbers first.", P.get("tip", "")),
                       panel("Money you can make now", [row(s["name"], s["how"], "on" if s["on"] else "off", "good" if s["on"] else "warn") for s in m["streams"]], "")],
            "actions": [{"label": "Open Money", "go": "money", "primary": True}]}


def d_affiliates():
    import business
    s = business.settings()
    ps = [J(p, {}) or {} for p in PKG.glob("*.json") if not p.stem.startswith("_")]
    has = sum(1 for p in ps if "── links ──" in p.get("youtube_description", ""))
    on = bool(s["amazon_tag"] or s["links"] or s["newsletter_url"])
    return {"question": "Is every description earning — links to the source material it covers?",
            "stats": [{"k": "Links set up", "v": "yes" if on else "no"}, {"k": "Descriptions with links", "v": f"{has} of {len(ps)}"},
                      {"k": "Amazon tag", "v": s["amazon_tag"] or "—"}],
            "panels": [panel("Your links", [row(l.get("label", ""), l.get("url", ""), ", ".join(l.get("lanes", [])) or "all")
                                            for l in s["links"]], "No links yet — add them on the Money page.")],
            "actions": [{"label": "Refresh links on all", "post": "/api/business/links", "body": {}, "primary": on},
                        {"label": "Set up links", "go": "money", "primary": not on}]}


def d_sponsors():
    import business
    s = business.settings()
    kit = OUT / "media_kit.html"
    return {"question": "Are we ready to pitch a sponsor?",
            "stats": [{"k": "Media kit", "v": studio_when(kit) if kit.exists() else "not built"},
                      {"k": "Sponsor email", "v": s["sponsor_email"] or "—"}],
            "panels": [panel("What a sponsor looks at", [row("Views per video, by platform"), row("Engagement (likes, comments, shares)"),
                                                        row("Audience lanes — Marvel, anime, gaming, real biology"),
                                                        row("A contact that answers")], "")],
            "actions": [{"label": "Build media kit", "post": "/api/business/kit", "body": {}, "primary": True}]}


def studio_when(p):
    return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("built %a %-d %b")


# ------------------------------------------------------------------ Control
def d_tasks():
    week = (datetime.datetime.now().astimezone() - datetime.timedelta(days=7)).isoformat()
    with nether.db() as c:
        bad = [nether._row(r) for r in c.execute("SELECT * FROM tasks WHERE status='failed' AND created>=? ORDER BY id DESC LIMIT 12", (week,))]
        by = dict(c.execute("SELECT agent, COUNT(*) FROM tasks WHERE status='failed' AND created>=? GROUP BY agent", (week,)).fetchall())
        tot = c.execute("SELECT COUNT(*) FROM tasks WHERE created>=?", (week,)).fetchone()[0]
    return {"question": "What broke this week — and has it been retried?",
            "stats": [{"k": "Tasks this week", "v": tot}, {"k": "Failed", "v": len(bad)},
                      *[{"k": nether.AGENTS[a]["name"], "v": f"{k} failed"} for a, k in by.items() if a in nether.AGENTS]],
            "panels": [panel("Failures this week", [row(f"{nether.AGENTS.get(t['agent'], {}).get('name', t['agent'])} · {t['title']}",
                                                        (t.get("error") or "").strip().splitlines()[-1][:200] if t.get("error") else "", "failed", "bad")
                                                    for t in bad], "Nothing failed this week.")],
            "actions": [{"label": "Open Task log", "go": "agents", "primary": True}, {"label": "Fix tickets", "go": "fixes"}]}


def d_daily():
    with nether.db() as c:
        runs = [nether._row(r) for r in c.execute("SELECT * FROM tasks WHERE agent='control' AND sub='daily' AND parent IS NULL ORDER BY id DESC LIMIT 7")]
    rows = []
    for t in runs:
        o = t.get("output") or {}
        rows.append(row(t["created"][:10], " · ".join(f"{k}: {v}" for k, v in o.items() if k in ("draft", "long", "scouted", "refresh"))[:220] or t.get("error", "")[-200:],
                        t["status"], "good" if t["status"] == "complete" else "bad" if t["status"] == "failed" else None))
    return {"question": "Did today's 7:00 run happen — refresh, learn, scout, draft?",
            "stats": [{"k": "Schedule", "v": "7:00 + 20:30 catch-up"}, {"k": "Sundays", "v": "also drafts the long-form"}],
            "panels": [panel("Last 7 runs", rows, "Hasn't run yet — install it once with ./install_daily.sh")],
            "actions": [{"label": "Run now", "post": "/api/daily/run", "body": {}, "primary": True}]}


def d_settings():
    import studio_api
    h = studio_api.health()
    return {"question": "Is every connection working?",
            "stats": [{"k": "Working", "v": f"{sum(1 for x in h if x['ok'])} of {len(h)}"}],
            "panels": [panel("Connections", [row(x["name"], x["detail"], "ok" if x["ok"] else "fix", "good" if x["ok"] else "warn") for x in h], "")],
            "actions": [{"label": "Open Settings", "go": "settings", "primary": True}]}


def d_engines():
    import llm
    s, u = llm.status(), llm.usage()
    rows = [row(v["what"], " → ".join(llm.ENGINES[e]["name"] for e in v["chain"]), "web" if v["web"] else None) for v in s["jobs"].values()]
    eng = [row(llm.ENGINES[k]["name"], f"{b['ok']} answered · {b['failed']} failed · ${b['cost']:.2f}", f"{b['calls']} calls",
               "warn" if b["failed"] > b["ok"] else None) for k, b in u["engines"].items()]
    share = u["claude_share"]
    return {"question": "Is Claude doing only the jobs that need it — and what does the writing cost?",
            "stats": [{"k": "Claude's share (7 days)", "v": f"{share:.0%}" if share is not None else "—"},
                      {"k": "API spend (7 days)", "v": f"${u['cost']:.2f}"},
                      {"k": "Preset", "v": (s["presets"].get(s["preset"]) or {}).get("name", "Custom")}],
            "panels": [panel("Who writes what (first engine, then its fallbacks)", rows, ""),
                       panel("Last 7 days by engine", eng, "Nothing written yet this week.")],
            "actions": [{"label": "Open AI engines", "go": "engines", "primary": True}]}


def d_repair():
    import repair
    ts = repair.tickets()
    st = {"open": ("filed", None), "working": ("repairing", None), "ready": ("review", "warn"), "nofix": ("no code change", None), "applied": ("applied", "good")}
    return {"question": "What was sent back to be fixed — and is the repair ready for you?",
            "stats": [{"k": "Open tickets", "v": sum(1 for t in ts if t["state"] in ("open", "working", "ready"))},
                      {"k": "Ready to review", "v": sum(1 for t in ts if t["state"] == "ready")}],
            "panels": [panel("Fix tickets", [row(f"#{t['n']} · {t['department']} · {t['title']}", t.get("summary") or t.get("error") or "",
                                                 *st.get(t["state"], (t["state"], None))) for t in ts],
                             "Nothing sent to fix. When a task fails, tap Why? · Fix and choose Send to fix.")],
            "actions": [{"label": "Open fix tickets", "go": "fixes", "primary": True}]}


DESKS = {("intelligence", "ideas"): d_ideas, ("intelligence", "demand"): d_demand, ("intelligence", "competitors"): d_competitors,
         ("intelligence", "fit"): d_fit, ("intelligence", "rights"): d_rights, ("intelligence", "sources"): d_sources,
         ("content", "research"): d_research, ("content", "script"): d_script, ("content", "packaging"): d_packaging,
         ("content", "hooks"): d_hooks, ("content", "titles"): d_titles, ("content", "episodes"): d_episodes,
         ("production", "videos"): d_videos, ("production", "visuals"): d_visuals, ("production", "tiktok"): d_tiktok,
         ("production", "render"): d_render, ("production", "qa"): d_qa, ("production", "thumbnail"): d_thumbnail,
         ("production", "bundle"): d_bundle, ("production", "longform"): d_longform,
         ("publishing", "calendar"): d_calendar, ("publishing", "schedule"): d_schedule,
         ("analytics", "performance"): d_performance, ("analytics", "retention"): d_retention_a,
         ("analytics", "stats"): d_stats, ("analytics", "learning"): d_learning,
         ("business", "community"): d_community, ("business", "monetisation"): d_monetisation,
         ("business", "affiliates"): d_affiliates, ("business", "sponsors"): d_sponsors,
         ("control", "tasks"): d_tasks, ("control", "daily"): d_daily, ("control", "settings"): d_settings,
         ("control", "engines"): d_engines, ("control", "repair"): d_repair}


def desk(agent, sub):
    f = DESKS.get((agent, sub))
    if not f:
        raise ValueError("No such sub-agent.")
    try:
        d = f()
    except Exception as e:                 # a desk that can't read its data still shows its purpose and tasks
        d = {"question": "", "stats": [], "panels": [], "actions": [], "error": f"{type(e).__name__}: {e}"}
    d["tasks"] = [{k: t.get(k) for k in ("id", "title", "status", "error", "created", "finished", "video", "retry")}
                  for t in recent_tasks(agent, sub)]
    return d


_SCOUT = {"on": False}


def scout_backlog(body):
    import studio_ext_nether as nx
    if _SCOUT["on"] or nx._RUNNING["topic"]:
        raise ValueError("Intelligence is already investigating — one at a time.")

    def run():
        try:
            import daily
            nx._RUNNING["topic"] = "the next 3 backlog ideas"
            daily.scout_backlog(3)
        finally:
            _SCOUT["on"], nx._RUNNING["topic"] = False, None
    _SCOUT["on"] = True
    threading.Thread(target=run, daemon=True).start()
    return {"ok": True, "reply": "Scouting the next 3 ideas — scores appear here as each finishes (about a minute each)."}


def desk_path(rest):
    agent, _, sub = rest.partition("/")
    return desk(agent, sub)


GET_PREFIX = {"/api/desk/": desk_path}
POST = {"/api/desk/scout_backlog": scout_backlog}


# ------------------------------------------------------------------ the week board (home screen)
def lined_up(v):
    """Can this video fill a coming day? Scripts waiting and ready videos, yes; something half-made is only lined up
    if it's recent (touched in the last 7 days) and in the channel's lanes — old space/ocean builds never come back."""
    import intelligence
    if v["stage"] in ("draft", "ready"):
        return True
    p = CFG / f"{v['id']}.json"
    fresh = p.exists() and age_days(p) <= 7
    return fresh and intelligence.lane_of(v["title"] + " " + v["id"].replace("_", " ")) not in ("space", "ocean")
RANK = {"live": 5, "scheduled": 4, "ready": 3, "making": 2, "draft": 1}


def week():
    """This week at a glance: 7 Short slots (Mon–Sun) + 1 long-form, each at its furthest stage, and the streak.
    A posted or scheduled Short sits on its day; anything still in the pipeline fills the next open days."""
    import studio_api
    today = datetime.date.today()
    mon = today - datetime.timedelta(days=today.weekday())
    days = [mon + datetime.timedelta(days=i) for i in range(7)]
    local = lambda iso: studio_api.parse_dt(iso).astimezone().date() if studio_api.parse_dt(iso) else None
    slots = {d: None for d in days}
    pipeline, long, sent_days = [], None, set()
    for v in studio_api.videos():
        if v["id"].endswith("_tiktok") or v["stage"] == "earlier":
            continue
        if "__" in v["id"]:
            v["title"] = title_of(v["id"])
        dates = [local(p.get("sentAt")) for p in v["posts"] if p.get("sentAt")]
        sent_days.update(d for d in dates if d)
        if v.get("format") == "landscape":
            if v["stage"] != "live" or any(d and d >= mon for d in dates):
                if not long or RANK.get(v["stage"], 0) > RANK.get(long["stage"], 0):
                    long = {"id": v["id"], "title": v["title"], "stage": v["stage"]}
            continue
        when = min([d for d in dates if d] + [local(s.get("dueAt")) for s in v["scheduled"] if local(s.get("dueAt"))], default=None)
        if when in slots and not slots[when]:
            slots[when] = {"id": v["id"], "title": v["title"], "stage": v["stage"]}
        elif when is None and v["stage"] in ("draft", "making", "ready") and lined_up(v):
            pipeline.append({"id": v["id"], "title": v["title"], "stage": v["stage"], "planned": True})
    for d in (EPS.glob("*.json") if not long else []):             # a long-form still at the script stage
        e = J(d, {}) or {}
        if e.get("draft"):
            long = {"id": d.stem, "title": e.get("title", d.stem), "stage": "draft"}
    pipeline.sort(key=lambda x: -RANK[x["stage"]])
    for d in days:                                             # the pipeline fills today and the days ahead
        if d >= today and not slots[d] and pipeline:
            slots[d] = pipeline.pop(0)
    streak, d = 0, today if today in sent_days else today - datetime.timedelta(days=1)
    while d in sent_days:
        streak, d = streak + 1, d - datetime.timedelta(days=1)
    out = [{"date": d.isoformat(), "day": d.strftime("%a"), "today": d == today, "past": d < today, **(slots[d] or {})} for d in days]
    return {"days": out, "long": long, "streak": streak,
            "out": sum(1 for x in out if x.get("stage") in ("live", "scheduled")),
            "left": len(pipeline)}


GET = {"/api/week": week}
