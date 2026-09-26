#!/usr/bin/env python3
"""business.py — the Business agent: money beyond ad revenue, and how close the channel is to getting paid.

    python3 business.py kit        write out/media_kit.html — a one-page sponsor kit from your real numbers
    python3 business.py links      add the links block to every packaging file that hasn't been posted yet

For many faceless channels, ads are just one revenue stream among several — typical splits vary a lot by
niche and audience, and nothing here is guaranteed. The others this agent helps with: affiliate links, a
newsletter and sponsors.
Settings live in out/business.json (edit them in Studio → Business → Money):
  amazon_tag       your Amazon Associates tag — every video gets a search link for what it covers
                   (e.g. the collected editions of the comic in the video)
  newsletter_url   where the newsletter signs up (Beehiiv, Substack, ConvertKit…)
  links            extra links, each {"label", "url", "lanes": ["marvel", …]} (lanes optional = every video)
  sponsor_email    shown on the media kit
  disclosure       the affiliate disclosure line (required by Amazon and the FTC — kept on by default)
The links block goes at the end of each YouTube description, between two markers, so it can be refreshed
without touching the rest. Nothing is posted — the next post picks it up.
"""
import datetime, html, json, re, statistics, sys
from pathlib import Path
from urllib.parse import quote_plus

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
import channel
OUT, PKG = DATA / "out", DATA / "packaging"
SETTINGS = OUT / "business.json"
START, END = "── links ──", "── end links ──"
DEFAULTS = {"amazon_tag": "", "newsletter_url": "", "links": [], "sponsor_email": "",
            "disclosure": "As an Amazon Associate I earn from qualifying purchases."}
SETUP = [  # one-time switches that grow reach or revenue; ticked in Studio (done.json keys setup:<key>)
    ("dubbing", "Turn on auto-dubbing", "YouTube Studio → Settings → Upload defaults → Advanced → allow automatic dubbing. "
                                        "Creators see 25%+ of watch time from other languages."),
    ("testcompare", "Use Test & Compare on long-form", "After a long-form uploads: Studio → the video → Test & Compare → "
                                                      "add the 3 thumbnails NETHER rendered (out/<id>_thumb, _thumb2, _thumb3)."),
    ("playlists", "Make series playlists", "One playlist per lane (Marvel, Anime, Gaming, Icebergs) — binge sessions are watch time."),
    ("associates", "Join Amazon Associates", "affiliate-program.amazon.com → add your tag here; links appear in every description."),
    ("newsletter", "Start the newsletter", "A free Beehiiv or Substack; paste the signup link here. You own this audience."),
    ("kit", "Send the media kit to 5 sponsors", "Business → Money → Media kit. Comic shops, card-game and collectible brands fit the lanes."),
]


def settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS.read_text())}
    except Exception:
        return dict(DEFAULTS)


MEDIA_KIT_ABOUT = ("Fact-checked short and long-form videos on the buried history of comics, anime and games — and the real science\n"
                   "hiding inside them. Every video cites its sources.") if channel.source() == "legacy" else \
                  (channel.about()[:1].upper() + channel.about()[1:] + " Every video cites its sources.")


def save_settings(new):
    s = settings()
    for k in ("amazon_tag", "newsletter_url", "sponsor_email", "disclosure"):
        if k in new:
            s[k] = str(new[k]).strip()[:300]
    if s["amazon_tag"] and not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", s["amazon_tag"]):
        raise ValueError("That doesn't look like an Amazon tag (e.g. yourchannel-20).")
    for k in ("newsletter_url",):
        if s[k] and not re.match(r"https?://", s[k]):
            raise ValueError("The newsletter link needs to start with https://")
    if "links" in new:
        links = []
        for l in new["links"] or []:
            url = str(l.get("url", "")).strip()
            if url and re.match(r"https?://", url):
                links.append({"label": str(l.get("label", "")).strip()[:60] or url,
                              "url": url[:400], "lanes": [x for x in l.get("lanes", []) if isinstance(x, str)][:6]})
        s["links"] = links[:10]
    OUT.mkdir(exist_ok=True)
    SETTINGS.write_text(json.dumps(s, indent=1))
    return s


def _search_terms(topic, lane):
    words = [w for w in re.findall(r"[A-Za-z0-9'’-]+", topic) if len(w) > 2][:6]
    extra = {"marvel": "comics collected edition", "anime": "manga", "gaming": "game guide art book"}.get(lane, "book")
    return " ".join(words + [extra])


def links_block(topic, lane):
    """The block appended to a YouTube description (empty when nothing is set up yet)."""
    s, lines = settings(), []
    if s["newsletter_url"]:
        lines.append(f"📬 The buried-history newsletter (free): {s['newsletter_url']}")
    if s["amazon_tag"]:
        q = quote_plus(_search_terms(topic, lane))
        lines.append(f"📚 Read the source material: https://www.amazon.com/s?k={q}&tag={s['amazon_tag']}")
    for l in s["links"]:
        if not l.get("lanes") or lane in l["lanes"]:
            lines.append(f"🔗 {l['label']}: {l['url']}")
    if not lines:
        return ""
    if s["amazon_tag"] and s["disclosure"]:
        lines.append(s["disclosure"])
    return f"\n\n{START}\n" + "\n".join(lines) + f"\n{END}"


def apply_links(pkg, topic, lane):
    """Replace (or add) the links block in a packaging dict's YouTube description. Returns True if it changed."""
    desc = pkg.get("youtube_description", "")
    base = re.sub(rf"\n*{re.escape(START)}.*?{re.escape(END)}", "", desc, flags=re.S).rstrip()
    new = base + links_block(topic, lane)
    if new != desc:
        pkg["youtube_description"] = new
        return True
    return False


def refresh_all():
    """Links on every packaging file not yet posted (posted videos keep what went out)."""
    import intelligence
    posted = {}
    for f in ("posted.json", "stats.json"):             # recorded posts, and anything live that stats.py linked
        try:
            d = json.loads((OUT / f).read_text())
            posted.update(d.get("videos", {}) if f == "stats.json" else d)
        except Exception:
            pass
    changed = []
    for p in PKG.glob("*.json"):
        if p.stem.startswith("_") or p.stem in posted or re.search(r"_t\d$", p.stem):
            continue
        pkg = json.loads(p.read_text())
        topic = pkg.get("title", p.stem.replace("_", " "))
        lane = intelligence.lane_of(topic + " " + p.stem.replace("_", " "))
        dirty = False
        if pkg.get("youtube_description_template"):       # a long-form's description is rebuilt from this at render
            tmpl = {"youtube_description": pkg["youtube_description_template"]}
            if apply_links(tmpl, topic, lane):
                pkg["youtube_description_template"], dirty = tmpl["youtube_description"], True
        if apply_links(pkg, topic, lane) or dirty:
            p.write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
            changed.append(p.stem)
    return changed


# ------------------------------------------------------------------ money
def money():
    """Where the money is: monetisation progress (both YouTube routes), revenue streams, one-time setup."""
    import studio_api, studio_channel
    ch = studio_channel.channel()
    goals = ch.get("goals", []) if ch.get("ready") else []
    yt = studio_api.jload(OUT / "youtube.json", {}) or {}
    longs = [v for v in yt.get("videos", []) if v.get("seconds", 0) > 180]
    # watch hours route (4,000 hrs / 12 months): public data has views + length, not watch time, so this is a rough
    # estimate at a typical 35% average view duration — YouTube Studio → Earn has the real number
    est_hours = round(sum(v.get("views", 0) * v.get("seconds", 0) * 0.35 for v in longs) / 3600)
    s, done = settings(), studio_api.done_map()
    streams = [
        {"name": "Ads (YouTube Partner Program)", "on": bool(goals) and all(g["value"] >= g["goal"] for g in goals[:1]),
         "how": "1,000 subscribers + {:,} watch hours or {:g}M Shorts views — see the road above.".format(ad_bar()[0], ad_bar()[1] / 1e6)},
        {"name": "Affiliate links", "on": bool(s["amazon_tag"] or s["links"]), "how": "Every description links the source material it covers."},
        {"name": "Newsletter", "on": bool(s["newsletter_url"]), "how": "Owned audience; sponsors pay per subscriber even when small."},
        {"name": "Sponsors", "on": bool(s["sponsor_email"]), "how": "Build media kit (top right) makes a one-page kit from your real numbers."},
    ]
    return {"plan": plan(), "goals": goals, "watch_hours_est": est_hours, "watch_goal": 4000, "long_videos": len(longs),
            "streams": streams, "settings": s,
            "setup": [{"key": k, "title": t, "how": h, "done": f"setup:{k}" in done} for k, t, h in SETUP]}


# YouTube Partner Program thresholds (announced 10 Aug 2026: ad-revenue bars double for NEW applicants from 1 Feb 2027;
# fan funding / Shopping stays at 500 subs + 3,000 hours or 3M Shorts views)
YPP_CHANGE = datetime.date(2027, 2, 1)


def ad_bar(today=None):
    today = today or datetime.date.today()
    return (4000, 10_000_000) if today < YPP_CHANGE else (8000, 20_000_000)


def plan():
    """The road to getting paid, in plain numbers: two milestones, what's blocking each, and what moves it fastest."""
    import studio_api, studio_channel
    ch = studio_channel.channel()
    if not ch.get("ready"):
        return {"ready": False}
    yt = studio_api.jload(OUT / "youtube.json", {}) or {}
    g = {x["key"]: x for x in ch["goals"]}
    subs, sub_day = g["subs"]["value"], g["subs"].get("per_day")
    views90 = g["views"]["value"]
    longs = [v for v in yt.get("videos", []) if v.get("seconds", 0) > 180]
    hours = sum(v.get("views", 0) * v.get("seconds", 0) * 0.35 for v in longs) / 3600
    avg_long = (sum(v.get("views", 0) for v in longs) / len(longs)) if longs else None
    ep_hours = (avg_long or 1000) * 600 * 0.35 / 3600          # one 10-minute episode at your average (or 1,000) views
    shorts_day, hours_day = views90 / 90, hours / 365
    before = datetime.date.today() < YPP_CHANGE
    ad_h, ad_v = ad_bar()

    def req(label, value, goal, unit, need_day=None, have_day=None, eta=None):
        return {"label": label, "value": round(value), "goal": goal, "unit": unit, "pct": min(1, value / goal) if goal else 0,
                "done": value >= goal, "need_day": need_day, "have_day": have_day, "eta": eta}

    def milestone(key, name, pays, sub_goal, h_goal, v_goal):
        s = req(f"{sub_goal:,} subscribers", subs, sub_goal, "subs", None, sub_day,
                g["subs"].get("eta") if sub_goal == 1000 else None)
        h = req(f"{h_goal:,} watch hours (long-form, 12 months)", hours, h_goal, "hours", h_goal / 365, hours_day)
        v = req(f"{v_goal / 1e6:g}M Shorts views (90 days)", views90, v_goal, "views", v_goal / 90, shorts_day)
        route = max((h, v), key=lambda r: r["pct"])
        block = min((s, route), key=lambda r: r["pct"])
        return {"key": key, "name": name, "pays": pays, "subs": s, "hours": h, "views": v, "route": "hours" if route is h else "views",
                "pct": min(s["pct"], route["pct"]), "done": s["done"] and route["done"], "bottleneck": block["label"]}

    first = milestone("fan", "First money", "Channel memberships, Super Thanks/Chat, YouTube Shopping", 500, 3000, 3_000_000)
    ads = milestone("ads", "Ad revenue", "A share of the ads on your videos (Shorts and long-form)", 1000, ad_h, ad_v)
    nxt = first if not first["done"] else ads
    # the fastest road: whichever route is closer to its daily need
    r_h = hours_day / (nxt["hours"]["goal"] / 365) if nxt["hours"]["goal"] else 0
    r_v = shorts_day / (nxt["views"]["goal"] / 90) if nxt["views"]["goal"] else 0
    eps = max(0, (nxt["hours"]["goal"] - hours)) / ep_hours if ep_hours else None
    if r_h >= r_v:
        tip = (f"Long-form is your fastest road: a 10-minute episode at {'your average ' + format(round(avg_long), ',') if avg_long else '1,000'} "
               f"views earns about {ep_hours:,.0f} watch hours — about {eps:,.0f} of those gets you to {nxt['hours']['goal']:,} hours.")
    else:
        tip = (f"Shorts are your fastest road: you average {shorts_day:,.0f} Shorts views a day; "
               f"{nxt['name'].lower()} needs {nxt['views']['goal'] / 90:,.0f} a day, every day, for 90 days.")
    return {"ready": True, "subs": subs, "first": first, "ads": ads, "next": nxt["key"], "tip": tip,
            "rule_change": {"date": YPP_CHANGE.isoformat(), "before": before,
                            "say": ("From 1 Feb 2027 new channels need double for ad revenue: 8,000 watch hours or 20M Shorts views. "
                                    "Channels already in the programme keep their place; the first-money tier doesn't change.") if before else
                                   "Since 1 Feb 2027 new channels need 8,000 watch hours or 20M Shorts views for ad revenue."}}


def media_kit():
    """A one-page sponsor kit from the real numbers (views, platforms, engagement, lanes). Returns the HTML path."""
    import studio_api, intelligence
    stats = studio_api.jload(OUT / "stats.json", {}) or {}
    yt = studio_api.jload(OUT / "youtube.json", {}) or {}
    posts = [p for ps in stats.get("videos", {}).values() for p in ps]
    views = sum(int(p.get("views") or 0) for p in posts)
    by = {}
    for p in posts:
        by[p.get("platform", "?")] = by.get(p.get("platform", "?"), 0) + int(p.get("views") or 0)
    eng = [((p.get("reactions") or 0) + (p.get("comments") or 0) + (p.get("shares") or 0) + (p.get("saves") or 0)) / p["views"]
           for p in posts if p.get("views")]
    ours = intelligence._our_videos()
    lanes = {}
    for v in ours:
        lanes.setdefault(v["lane"], []).append(v["views"])
    lane_txt = ", ".join(f"{k} ({statistics.mean(v):,.0f} avg views)" for k, v in sorted(lanes.items(), key=lambda kv: -statistics.mean(kv[1])))
    subs = (yt.get("channel") or {}).get("subscribers")
    s = settings()
    e = html.escape
    rows = "".join(f"<tr><td>{e(k.title())}</td><td>{v:,}</td></tr>" for k, v in sorted(by.items(), key=lambda kv: -kv[1]))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(channel.get('name'))} — media kit</title><style>
:root{{--ink:#15130F;--muted:#6B665C;--accent:#E0294B;--bg:#FAF8F3}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,Helvetica,Arial,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:48px 24px}}h1{{font-size:44px;margin:0;letter-spacing:-.03em}}
.k{{color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.12em}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:28px 0}}
.t{{background:#fff;border:1px solid #E7E2D8;border-radius:12px;padding:16px}}.t b{{display:block;font-size:30px}}
table{{width:100%;border-collapse:collapse;margin-top:8px}}td{{padding:8px 0;border-bottom:1px solid #E7E2D8}}td+td{{text-align:right}}
a{{color:var(--accent)}}</style></head><body><main>
<span class="k">Media kit · {datetime.date.today():%B %Y}</span><h1>{e(channel.get('name'))}</h1>
<p>{e(MEDIA_KIT_ABOUT)}</p>
<div class="tiles"><div class="t"><span class="k">Views, all posts</span><b>{views:,}</b></div>
<div class="t"><span class="k">YouTube subscribers</span><b>{f"{subs:,}" if subs is not None else "—"}</b></div>
<div class="t"><span class="k">Engagement</span><b>{(statistics.mean(eng) * 100 if eng else 0):.1f}%</b></div>
<div class="t"><span class="k">Videos</span><b>{len(stats.get("videos", {}))}</b></div></div>
<span class="k">Views by platform</span><table>{rows}</table>
<p><span class="k">Strongest topics</span><br>{e(lane_txt) or "—"}</p>
<p><span class="k">Formats</span><br>Integrated read (15–30s) in a weekly 10–12 minute episode · dedicated Short · pinned-comment link.</p>
<p><span class="k">Contact</span><br>{f'<a href="mailto:{e(s["sponsor_email"])}">{e(s["sponsor_email"])}</a>' if s["sponsor_email"] else "Add your sponsor email in Studio → Business → Money."}</p>
<p class="k">Numbers from YouTube and Buffer, {e(str(stats.get("updated", "")))}. Engagement = (likes + comments + shares + saves) ÷ views.</p>
</main></body></html>"""
    path = OUT / "media_kit.html"
    OUT.mkdir(exist_ok=True)
    path.write_text(page)
    return path


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "kit":
        print(media_kit())
    elif cmd == "links":
        print("updated:", ", ".join(refresh_all()) or "nothing")
    else:
        sys.exit(__doc__)
