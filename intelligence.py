#!/usr/bin/env python3
"""intelligence.py — NETHER's Intelligence agent: is this topic worth making?

    python3 intelligence.py "immortal jellyfish"

One investigation = one Intelligence task with a child task per scout, so a
scout that breaks shows up on the brain with its error and the rest still run:

  Demand scout       YouTube Shorts on the topic from the last 12 months: median and top views
  Competitor scout   who made them: channel sizes, small channels breaking out (= winnable)
  Channel-fit scout  how this topic's lane (Marvel, anime, space…) has done on YOUR channel
  Visuals & rights   public-domain photos on Wikimedia Commons, or "AI art only" for characters
  Source scout       a Wikipedia article to start fact-checking from

The scorecard also has "Your taste": how often you've said "Make it" to this
lane before (learning.py). Every scorecard is saved as a prediction in
out/intel/<slug>.json; learning.py later checks it against the real views and
re-weights the score toward what actually works on this channel.
Costs ~102 YouTube API units per investigation (10,000/day free).
"""
import datetime, json, math, re, statistics, sys
from pathlib import Path

import requests

import orchestrator as nether

HERE = Path(__file__).resolve().parent
INTEL = HERE / "out" / "intel"
UA = "NethermindStudio/1.0 (single-operator research/educational use)"

LANES = {  # first match wins; order matters (a Marvel animal video is Marvel)
    "marvel": "marvel wolverine hulk x-men xmen mutant avengers spider-man spiderman daredevil stan lee comic comics superhero villain dc batman superman",
    "anime": "anime manga dragon ball naruto pokemon pokémon ghibli one piece attack on titan titan goku studio",
    "gaming": "game games gaming nintendo mario sonic minecraft zelda halo playstation xbox speedrun arcade pac-man pacman",
    "space": "space star planet galaxy nasa black hole universe moon mars jupiter neptune kepler voyager telescope nebula",
    "ocean": "ocean deep sea shark whale jellyfish octopus squid fish reef trench abyss",
    "creature": "superpower superpowers animal creature species worm beetle frog bird insect spider snake lizard shrimp",
}
COPYRIGHT_LANES = {"marvel", "anime", "gaming"}
DEFAULT_WEIGHTS = {"demand": 30, "competition": 15, "fit": 20, "taste": 10, "visuals": 15, "sources": 10}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48] or "topic"


def lane_of(text):
    low = f" {text.lower()} "
    for lane, words in LANES.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words.split()):
            return lane
    return "other"


def weights():
    p = HERE / "out" / "intel_weights.json"
    try:
        return json.loads(p.read_text())["weights"]
    except Exception:
        return dict(DEFAULT_WEIGHTS)


# ------------------------------------------------------------------ scouts
def scout_demand(topic):
    from youtube import call
    from idea_demand import query_for
    q = query_for(topic) or topic
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = call("search", part="snippet", q=q, type="video", videoDuration="short", maxResults=15,
                 publishedAfter=after, order="relevance", relevanceLanguage="en")["items"]
    ids = [f["id"]["videoId"] for f in found]
    items = call("videos", part="statistics,snippet", id=",".join(ids))["items"] if ids else []
    vids = sorted(({"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
                    "channel_id": v["snippet"]["channelId"], "views": int(v["statistics"].get("viewCount", 0)),
                    "url": f"https://www.youtube.com/shorts/{v['id']}"} for v in items), key=lambda v: -v["views"])
    med = int(statistics.median([v["views"] for v in vids])) if vids else 0
    # 0 at ≤1k median views, full marks at ≥1M
    score = min(max((math.log10(med) - 3) / 3, 0), 1) if med > 0 else 0
    return {"query": q, "results": len(vids), "median": med, "top": vids[:5], "videos": vids, "score": round(score, 2),
            "say": f"Similar Shorts from the last year get a median of {med:,} views ({len(vids)} found)."}


def scout_competitors(demand):
    from youtube import call
    vids = demand["videos"]
    chans = sorted({v["channel_id"] for v in vids})
    subs = {}
    if chans:
        for c in call("channels", part="statistics", id=",".join(chans[:50]))["items"]:
            s = c["statistics"]
            subs[c["id"]] = None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0))
    small = [v for v in vids if subs.get(v["channel_id"]) is not None and subs[v["channel_id"]] < 100_000]
    breakouts = [v for v in small if v["views"] >= 100_000]
    share = len(small) / len(vids) if vids else 0
    score = min(1, share + 0.15 * len(breakouts)) if vids else 0
    return {"channels": len(chans), "small_channel_share": round(share, 2),
            "breakouts": [{**{k: v[k] for k in ("title", "channel", "views", "url")}, "subs": subs[v["channel_id"]]}
                          for v in breakouts[:3]],
            "score": round(score, 2),
            "say": (f"{len(small)} of {len(vids)} come from channels under 100k subscribers"
                    + (f"; {len(breakouts)} of those broke 100k views — winnable." if breakouts else "; no small-channel breakouts yet."))}


def _our_videos():
    stats = {}
    try:
        stats = json.loads((HERE / "out" / "stats.json").read_text()).get("videos", {})
    except Exception:
        pass
    out = []
    for vid, posts in stats.items():
        text = vid.replace("_", " ")
        pk = HERE / "packaging" / f"{vid}.json"
        if pk.exists():
            try:
                text += " " + json.loads(pk.read_text()).get("title", "")
            except Exception:
                pass
        out.append({"id": vid, "lane": lane_of(text), "views": int(sum(p.get("views") or 0 for p in posts))})
    return out


def scout_fit(topic):
    lane = lane_of(topic)
    ours = _our_videos()
    if not ours:
        return {"lane": lane, "score": 0.5, "say": "No stats yet (run Refresh numbers) — fit counted as neutral."}
    avg = statistics.mean(v["views"] for v in ours)
    mine = [v["views"] for v in ours if v["lane"] == lane]
    if len(mine) < 2:
        return {"lane": lane, "videos_in_lane": len(mine), "channel_avg": round(avg), "score": 0.5,
                "say": f"Only {len(mine)} {lane} video(s) so far — too few to judge, counted as neutral. A good test of a new lane."}
    ratio = statistics.mean(mine) / avg if avg else 1
    return {"lane": lane, "videos_in_lane": len(mine), "lane_avg": round(statistics.mean(mine)), "channel_avg": round(avg),
            "score": round(min(ratio / 1.5, 1), 2),
            "say": f"Your {lane} videos average {statistics.mean(mine):,.0f} views vs {avg:,.0f} channel-wide ({ratio:.1f}×)."}


def scout_rights(topic):
    lane = lane_of(topic)
    import fetch_real
    try:
        found = fetch_real.search(topic, limit=20)
    except Exception as e:
        found, err = [], str(e)
    else:
        err = None
    ok = [f for f in found if fetch_real._license_ok(f["license"])]
    if lane in COPYRIGHT_LANES:
        score = 0.6 + min(len(ok), 4) * 0.1   # AI art covers the characters; real PD photos of the science side add to it
        say = (f"Characters are copyrighted — original AI art for those beats. {len(ok)} public-domain/CC photos found "
               "for the real-world side.")
    else:
        score = min(len(ok) / 4, 1)
        say = f"{len(ok)} public-domain/CC photos on Wikimedia Commons." + (" Thin — may need AI art or a different angle." if len(ok) < 3 else "")
    if err:
        say += f" (Commons search failed: {err[:80]})"
    return {"lane": lane, "copyright_lane": lane in COPYRIGHT_LANES, "usable": len(ok),
            "examples": [{k: f[k] for k in ("title", "license", "page")} for f in ok[:3]], "score": round(score, 2), "say": say}


def scout_sources(topic):
    r = requests.get("https://en.wikipedia.org/w/api.php", headers={"User-Agent": UA}, timeout=15,
                     params={"action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 3})
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])
    arts = [{"title": h["title"], "url": "https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_"),
             "snippet": re.sub(r"<[^>]+>", "", h.get("snippet", ""))} for h in hits]
    return {"articles": arts, "score": 1.0 if arts else 0.0,
            "say": (f"Start fact-checking at Wikipedia: {arts[0]['title']} (then its cited sources)." if arts
                    else "No Wikipedia article — sourcing will be slow; be careful.")}


def scout_taste(topic):
    import learning
    return learning.taste(lane_of(topic))


# ------------------------------------------------------------------ the investigation
SCOUTS = [("demand", "Demand scout"), ("competitors", "Competitor scout"), ("fit", "Channel-fit scout"),
          ("rights", "Visuals & rights scout"), ("sources", "Source scout")]
COMPONENT = {"demand": "demand", "competitors": "competition", "fit": "fit", "rights": "visuals", "sources": "sources"}


def verdict(total):
    return ("Strong — make it" if total >= 70 else "Worth a try" if total >= 50 else "Skip, or find a sharper angle")


def investigate(topic):
    topic = re.sub(r"\s+", " ", str(topic)).strip()[:120]
    if not topic:
        raise ValueError("Type a topic first.")
    parent = nether.begin("intelligence", f"Investigate: {topic}", input={"topic": topic},
                          retry={"kind": "intel", "topic": topic})
    found, errors = {}, {}
    for key, name in SCOUTS:
        tid = nether.begin("intelligence", name, sub=key, parent=parent)
        try:
            if key == "demand":
                found[key] = scout_demand(topic)
            elif key == "competitors":
                if "demand" not in found:
                    raise RuntimeError("Needs the Demand scout's results, which failed.")
                found[key] = scout_competitors(found["demand"])
            else:
                found[key] = {"fit": scout_fit, "rights": scout_rights, "sources": scout_sources}[key](topic)
            out = {k: v for k, v in found[key].items() if k != "videos"}
            nether.finish(tid, out)
        except (Exception, SystemExit) as e:          # youtube.py exits when the key is missing — contain it
            errors[key] = f"{type(e).__name__}: {e}"
            nether.fail(tid, errors[key])
    taste = scout_taste(topic)

    w = weights()
    parts = {COMPONENT[k]: found[k]["score"] for k in found}
    parts["taste"] = taste["score"]
    got = sum(w[c] for c in parts)            # a failed scout is left out, not scored as zero
    total = round(sum(w[c] * s for c, s in parts.items()) / got * 100) if got else 0
    card = {"topic": topic, "slug": slug(topic), "lane": lane_of(topic), "at": nether.now(), "task": parent,
            "score": total, "verdict": verdict(total), "weights": w,
            "components": {c: {"score": parts.get(c), "weight": w[c]} for c in w},
            "reasons": [found[k]["say"] for k, _ in SCOUTS if k in found] + [taste["say"]],
            "failed": errors, "evidence": {k: {kk: vv for kk, vv in v.items() if kk != "videos"} for k, v in found.items()},
            "decision": None, "made_as": None}
    INTEL.mkdir(parents=True, exist_ok=True)
    (INTEL / f"{card['slug']}.json").write_text(json.dumps(card, indent=1, ensure_ascii=False))
    if errors and len(errors) == len(SCOUTS):
        nether.fail(parent, "Every scout failed: " + "; ".join(errors.values()), card)
    else:
        nether.finish(parent, {"score": total, "verdict": card["verdict"], "slug": card["slug"], "failed": list(errors)})
    return card


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    c = investigate(" ".join(sys.argv[1:]))
    print(f"\n{c['topic']}  —  {c['score']}/100  {c['verdict']}  (lane: {c['lane']})")
    for r in c["reasons"]:
        print("  •", r)
    for k, e in c["failed"].items():
        print(f"  ✗ {k} scout failed: {e}")
