#!/usr/bin/env python3
"""demo_data.py — a realistic, clearly-labelled sample channel so a buyer can explore without any keys.

    python3 demo_data.py <folder> [--fresh]      build (or top up) a demo data folder
    NETHER_DATA=<folder> STUDIO_NO_BROWSER=1 .venv/bin/python studio.py      then open it

Everything in it is invented: the channel ("Deep Current"), its videos, views, comments and scorecards. The folder's
channel.json says "demo": true, so the app shows "Demo data" on every page and never offers to post. No keys, no
network. Dates are relative to today, so the demo always looks current. Nothing outside <folder> is touched.
"""
import datetime, json, os, random, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO_TAG = "Demo data"
CHANNEL = {"name": "Deep Current", "app_name": "Nether", "owner": "you", "demo": True, "setup_complete": True,
           "about": "", "lanes": ["ocean", "creature", "space"], "off_lanes": [], "hashtag": "deepcurrent",
           "title_subjects": ["shark", "ocean", "jellyfish", "shrimp", "planet", "star", "worm", "fish", "axolotl", "tardigrade"],
           "replies_about": "ocean science, strange animals and space",
           "subscribe_line": "Subscribe for the true version of the stories everyone half-remembers.",
           "long_hashtags": "#deepcurrent #science #nature", "youtube_channel_id": "", "dashboard_url": "",
           "jarvis": {"enabled": False, "dir": "", "url": "http://127.0.0.1:8765"}, "backup_dir": "~/Documents/Nether Backups (demo)"}
# id, title, lane, stage, days since posted (negative = scheduled ahead), YouTube / TikTok / Instagram views
VIDEOS = [
    ("greenland_shark_age", "This Shark Was Swimming Before the Pilgrims Landed (Probably)", "ocean", "live", 24, 48200, 91000, 12400),
    ("mantis_shrimp_punch", "The Shrimp That Punches Like a .22 Bullet", "creature", "live", 19, 127400, 210000, 30500),
    ("glass_rain", "It Rains Glass Sideways on This Planet", "space", "live", 14, 22100, 35000, 5400),
    ("immortal_jellyfish", "The Jellyfish That Ages Backwards", "ocean", "live", 10, 64800, 88000, 15100),
    ("tardigrade_space", "Tardigrades Survived 10 Days in Open Space", "creature", "live", 6, 18300, 26000, 4100),
    ("axolotl_regrow", "The Axolotl Regrows Parts of Its Own Brain", "creature", "live", 3, 9100, 14200, 2300),
    ("boyajian_star", "The Star That Dims 22% and Nobody Knows Why", "space", "scheduled", -1, 0, 0, 0),
    ("bone_worm", "The Worm That Eats Whale Bones With Acid", "ocean", "ready", None, 0, 0, 0),
    ("walking_fish", "The Fish That Walks on the Sea Floor", "ocean", "draft", None, 0, 0, 0),
]
LINES = {
    "greenland_shark_age": ["This shark could be four hundred years old.", "Scientists dated the eye lenses of twenty eight Greenland sharks.",
                            "The biggest came out at about three hundred and ninety two years.", "But the honest range is two hundred seventy two to five hundred twelve.",
                            "They grow about a centimetre a year."],
    "walking_fish": ["This fish walks instead of swimming.", "The red-lipped batfish props itself up on stiff fins.",
                     "It shuffles across the sea floor, two hundred metres down.", "Nobody is sure what the red lips are for.",
                     "Next: the fish with a see-through head."],
}
COMMENTS = [("mantis_shrimp_punch", "Marine Mo", "Wait, does it really boil the water around its claw??"),
            ("immortal_jellyfish", "Sam R.", "So it's technically immortal but still gets eaten. Nature is brutal."),
            ("greenland_shark_age", "oceanfan_22", "Love that you gave the actual range instead of just 500 years."),
            ("glass_rain", "Priya", "How do they know the wind speed on a planet that far away?"),
            ("tardigrade_space", "Leo", "Water bears are the real final boss"),
            ("axolotl_regrow", "Dana K.", "Do the regrown parts work as well as the originals?")]
IDEAS = {
    "ocean": [("The deepest fish ever filmed was 8,336 metres down", "fact", "Univ. of Western Australia, 2023"),
              ("Some octopuses punch fish for no clear reason", "creature", "Sampaio et al., Ecology (2020)"),
              ("Sea otters hold hands so they don't drift apart", "creature", "Monterey Bay Aquarium — check how common")],
    "creature": [("Wood frogs freeze solid and thaw back to life", "creature", "Storey lab, Carleton University"),
                 ("The pistol shrimp's snap is briefly as hot as the Sun's surface", "creature", "Lohse et al., Nature (2001)")],
    "space": [("A day on Venus is longer than its year", "fact", "NASA Venus facts"),
              ("Voyager 1 is still sending data from interstellar space", "fact", "voyager.jpl.nasa.gov")],
    "iceberg": [("The Deep Sea Iceberg", "iceberg", "NOAA Ocean Exploration + primary papers per tier")],
}


def iso(days=0, hours=0, base=None):
    t = (base or datetime.datetime.now().astimezone()) - datetime.timedelta(days=days, hours=hours)
    return t.isoformat(timespec="seconds")


def dump(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def cfg_for(vid, title, lane, draft=False):
    lines = LINES.get(vid) or [title + ".", "Here is what the popular version gets wrong.", "The real number is smaller — and stranger.",
                               "Scientists only worked it out recently.", "Next: another one from the deep."]
    segs = [{"id": f"s{i + 1}", "text": t, "vis": {"t": "kb", "src": f"{vid}.jpg", "z0": 1.3, "z1": 1.1, "cx": 0.5, "cy": 0.45,
                                                   **({"real": {"query": f"{title} photo"}} if i == 0 else {})}} for i, t in enumerate(lines)]
    segs[0]["hook"] = True
    c = {"id": vid, "file": vid, "demo": True, "palette": {"accent": [224, 41, 75], "accent2": [255, 180, 80]}, "credit": "DEMO — NO REAL MEDIA",
         "score": "deep", "hook": {"lines": [[w.upper(), "w"] for w in title.split(" ")[:3]], "size": 120, "y": 610},
         "end": {"at": 1.4, "lines": ["NEXT:", "ANOTHER ONE FROM THE DEEP"]}, "segments": segs}
    if draft:
        c["draft"] = {"at": iso(hours=3), "topic": title, "task": None}
    return c


def pkg_for(vid, title, lane):
    return {"title": title, "title_options": [title, title.replace("The ", "This ", 1), f"{title.split(' ')[1].title()}: the true story"],
            "hook_options": [title[:40]], "demo": True,
            "youtube_description": f"{DEMO_TAG} — a sample video description.\n\n{title}. The popular version is close, but the true one is stranger.\n\n"
                                   "Subscribe for the true version of the stories everyone half-remembers.\n\nSources: (demo)\n\n#deepcurrent #science",
            "youtube_tags": f"{lane}, science, facts, deepcurrent", "tiktok_caption": f"{title} #deepcurrent #science #facts",
            "instagram_caption": f"Send this to the friend who loves {lane} facts. #deepcurrent #science #facts",
            "pinned_comment": "Which part surprised you most?", "thumbnail": {"lines": title.upper().split(" ")[:3], "accent": 2}}


def picture(path, title, size, seed):
    """A calm gradient card with the title and a DEMO mark. Needs Pillow (already in the venv); skipped without it."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return
    rnd = random.Random(seed)
    w, h = size
    top, bot = (rnd.randint(10, 40), rnd.randint(30, 70), rnd.randint(70, 120)), (rnd.randint(0, 20), rnd.randint(5, 25), rnd.randint(25, 50))
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3)))
    font = next((ImageFont.truetype(f, int(w / 11)) for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/System/Library/Fonts/Helvetica.ttc") if os.path.exists(f)), None) or ImageFont.load_default()
    small = next((ImageFont.truetype(f, int(w / 24)) for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "/System/Library/Fonts/Helvetica.ttc") if os.path.exists(f)), None) or ImageFont.load_default()
    words, lines, cur = title.upper().split(), [], ""
    for wd in words:
        if len(cur) + len(wd) > 12 and cur:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    y = h * 0.34
    for i, ln in enumerate(lines[:5]):
        d.text((w * 0.08, y), ln, fill=(224, 41, 75) if i == 1 else (245, 245, 247), font=font)
        y += w / 9.5
    d.rounded_rectangle([w * 0.06, h * 0.06, w * 0.06 + w * 0.34, h * 0.06 + w / 14], radius=int(w / 60), fill=(224, 41, 75))
    d.text((w * 0.085, h * 0.06 + w / 90), "DEMO DATA", fill=(255, 255, 255), font=small)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, quality=86)


def sample_video(path, title):
    """A 4-second placeholder clip for the one video that's 'ready for review' (needs ffmpeg; skipped without it)."""
    ff = shutil.which("ffmpeg")
    if not ff:
        return False
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x1C1C1E:s=540x960:d=4", "-f", "lavfi",
                        "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(path)], capture_output=True, timeout=60)
    return r.returncode == 0


def build_files(d, now):
    out = d / "out"
    for sub in ("cfg", "packaging", "episodes", "assets", "tts", "music", "out/intel", "out/digest", "out/daily", "out/drafts", "out/learning"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    stats, posted, ytv, sched = {}, {}, [], []
    for n, (vid, title, lane, stage, ago, yv, tv, iv) in enumerate(VIDEOS):
        dump(d / "cfg" / f"{vid}.json", cfg_for(vid, title, lane, draft=stage == "draft"))
        dump(d / "packaging" / f"{vid}.json", pkg_for(vid, title, lane))
        if stage != "draft":
            picture(out / f"{vid}_cover.jpg", title, (540, 960), vid)
            picture(out / f"{vid}_thumb.jpg", title, (640, 360), vid + "t")
            picture(d / "assets" / f"{vid}.jpg", title, (540, 960), vid)
        if stage == "ready":
            if sample_video(out / f"{vid}.mp4", title):
                shutil.copy(out / f"{vid}_thumb.jpg", out / f"{vid}_qa_contact.jpg")
        if stage == "live":
            ytid = f"demo{n:07d}"
            sent = iso(ago, base=now)
            posts = [{"platform": "youtube", "sentAt": sent, "url": f"https://www.youtube.com/shorts/{ytid}", "views": yv,
                      "reactions": yv // 28, "comments": yv // 900, "shares": None, "saves": None, "averageTimeWatched": None, "follows": None}]
            for plat, v in (("tiktok", tv), ("instagram", iv)):
                posts.append({"platform": plat, "sentAt": iso(ago, hours=-1, base=now), "url": f"https://example.com/demo/{plat}/{vid}",
                              "views": v, "reactions": v // 20, "comments": v // 700, "shares": v // 120, "saves": v // 150,
                              "averageTimeWatched": round(9 + (v % 17) / 2, 1), "follows": v // 800})
            stats[vid] = posts
            posted[vid] = {"at": sent, "posts": {p: f"{n:02d}" + "demo" * 5 for p in ("youtube", "tiktok", "instagram")}}
            ytv.append({"id": ytid, "title": title, "published": sent, "thumb": None, "seconds": 52, "views": yv, "likes": yv // 28,
                        "comments": yv // 900, "url": f"https://www.youtube.com/shorts/{ytid}"})
        if stage == "scheduled":
            posted[vid] = {"at": iso(hours=5, base=now), "posts": {}}
            for i, plat in enumerate(("youtube", "tiktok", "instagram")):
                sched.append({"id": f"{i}{n:02d}" + "d" * 21, "video": vid, "platform": plat, "dueAt": iso(-1, hours=-2, base=now)})
    stamp = now.isoformat(timespec="minutes")
    dump(out / "stats.json", {"videos": stats, "scheduled": sched, "unmatched_posts": 0, "updated": stamp, "demo": True})
    dump(out / "posted.json", posted)
    subs_now, total = 742, sum(v["views"] for v in ytv)
    dump(out / "youtube.json", {
        "fetched": stamp, "demo": True,
        "channel": {"id": "UCdemo", "title": "Deep Current (demo)", "handle": "@deepcurrent-demo", "avatar": None, "subscribers": subs_now,
                    "subscribers_hidden": False, "views": total, "views_channel_counter": total, "videos": len(ytv)},
        "shorts_90d": {"views": total, "videos": len(ytv), "first": ytv[-1]["published"] if ytv else None},
        "videos": sorted(ytv, key=lambda v: v["published"], reverse=True),
        "comments": [{"id": f"demo_c{i}", "video": next(v["id"] for v in ytv if v["title"] == dict((x[0], x[1]) for x in VIDEOS)[vid]),
                      "video_title": dict((x[0], x[1]) for x in VIDEOS)[vid], "author": a, "text": t, "likes": 3 + i * 2,
                      "at": iso(i, hours=2, base=now), "replies": 0, "link": "https://example.com/demo/comment"} for i, (vid, a, t) in enumerate(COMMENTS)]})
    with open(out / "youtube_history.jsonl", "w") as yh, open(out / "stats_history.jsonl", "w") as sh:
        for day in range(30, -1, -1):
            k = (30 - day) / 30
            at = iso(day, base=now)
            live = [v for v in ytv if v["published"] <= at]
            yh.write(json.dumps({"at": at, "subscribers": int(180 + (subs_now - 180) * k ** 1.3), "views": int(total * k ** 1.5),
                                 "shorts_90d": int(total * k ** 1.5), "videos": {v["id"]: int(v["views"] * k ** 1.5) for v in live}}) + "\n")
            sh.write(json.dumps({"at": at, "views": {vid: int(sum(p["views"] or 0 for p in ps) * k ** 1.5) for vid, ps in stats.items()}}) + "\n")
    import workspace                                         # TOPICS.md with sample ideas in the demo's lanes
    (d / "TOPICS.md").write_text(workspace.topics_md(IDEAS))
    (d / "LEARNINGS.md").write_text(f"""# What's working — Deep Current ({DEMO_TAG})

## Evidence so far ({now:%Y-%m-%d}, {DEMO_TAG.lower()})

- Creature videos average 2.1× the channel's views; space averages 0.6×.

## Working hypotheses (not yet proven)

- **A real animal with a "superpower" beats a pure space fact.** The mantis shrimp and the jellyfish lead on every platform.
- **A hard number in the first line holds viewers past three seconds.**

## Production rules (from your feedback — not up for A/B testing)

- Say the honest range, not the headline number.

## Reviewer notes

What the user asked to change on review — patterns here should shape future builds.
""")
    dump(out / "next.json", {"slug": "the_pistol_shrimp_s_snap_is_briefly_as_hot_as_the_sun_s_surface",
                             "hook": IDEAS["creature"][1][0], "at": iso(hours=20, base=now)[:16]})
    cards = [("The pistol shrimp's snap is briefly as hot as the Sun's surface", "creature", 84, None),
             ("Wood frogs freeze solid and thaw back to life", "creature", 77, None),
             ("A day on Venus is longer than its year", "space", 58, None),
             ("The immortal jellyfish ages backwards", "ocean", 81, {"choice": "make", "reason": "Strong animal superpower", "at": iso(12, base=now)})]
    for topic, lane, score, decision in cards:
        slug = "".join(ch if ch.isalnum() else "_" for ch in topic.lower()).strip("_")[:48]
        dump(out / "intel" / f"{slug}.json", {
            "topic": topic, "slug": slug, "lane": lane, "at": iso(2, base=now), "task": None, "score": score, "demo": True,
            "verdict": "Strong — make it" if score >= 75 else "Maybe — only with a strong angle",
            "weights": {"demand": 30, "competition": 15, "fit": 20, "taste": 10, "visuals": 15, "sources": 10},
            "components": {c: {"score": round(min(1, score / 100 + (i - 3) * 0.04), 2), "weight": w} for i, (c, w) in
                           enumerate({"demand": 30, "competition": 15, "fit": 20, "taste": 10, "visuals": 15, "sources": 10}.items())},
            "reasons": [f"{DEMO_TAG}: similar Shorts averaged 180K views last year.", "Small channels are breaking out on this.",
                        f"{lane.title()} videos beat your average.", "Public-domain photos exist.", "Two primary sources found."],
            "failed": {}, "evidence": {}, "decision": decision, "made_as": "immortal_jellyfish" if decision else None})
    dump(out / "drafts" / "walking_fish.json", {"demo": True, "notes": [], "check": {"score": 86, "rows": [[True, "Line 1 is 8 words or fewer"],
         [True, "A hero number in the first 3 seconds"], [False, "One still is held for 7 seconds — add a new framing"]]},
         "research": {"angle": "It walks because swimming is expensive at depth.", "true_version": "It shuffles on modified fins; it can still swim.",
                      "hero_number": "200 METRES", "facts": [{"claim": f"{DEMO_TAG}: sample fact {i + 1}", "source_url": "https://example.com/demo",
                                                              "source_title": "Demo source"} for i in range(3)]}})
    (out / "digest" / f"{now:%Y-%m-%d}.md").write_text(f"# Last week in 30 seconds ({DEMO_TAG})\n\n- YouTube subscribers: {subs_now} (+64 this week)\n"
                                                      "- Best video: The Shrimp That Punches Like a .22 Bullet\n- Plan: two creature Shorts, one ocean.\n")
    (out / "daily" / f"{now:%Y-%m-%d}.md").write_text(f"# Daily run ({DEMO_TAG})\n\n- Refreshed numbers\n- Drafted: The Fish That Walks on the Sea Floor\n")
    with open(out / "llm_usage.jsonl", "w") as f:
        for i, (job, eng, cost) in enumerate([("research", "claude", 0), ("script", "claude", 0), ("packaging", "claude", 0),
                                              ("replies", "anthropic", 0.012), ("research", "claude", 0), ("script", "claude", 0)]):
            f.write(json.dumps({"at": iso(i, hours=3, base=now), "job": job, "engine": eng, "fallback": False, "model": "subscription" if eng == "claude"
                                else "claude-sonnet-5", "cost": cost, "ok": True, "secs": 40 + i * 7, "demo": True}) + "\n")
    dump(out / "vidiq_balance.json", {"credits": 0, "resets": iso(-9, base=now)[:10], "at": stamp, "demo": True})


def build_tasks():
    """Agent history in out/nether.db, through orchestrator itself (this process runs with NETHER_DATA = the demo)."""
    import orchestrator as o
    if o.tasks(limit=1):
        return
    def done(agent, title, sub=None, parent=None, video=None, output=None, failed=None):
        t = o.begin(agent, title, sub=sub, parent=parent, video=video)
        (o.fail(t, failed) if failed else o.finish(t, output or {"demo": True}))
        return t
    p = o.begin("intelligence", "Investigate: The pistol shrimp's snap")
    for sub, name in (("demand", "Demand scout"), ("competitors", "Competitor scout"), ("fit", "Channel-fit scout"),
                      ("rights", "Visuals & rights scout"), ("sources", "Source scout")):
        done("intelligence", name, sub, p)
    o.finish(p, {"score": 84, "demo": True})
    p = o.begin("content", "Draft: The Fish That Walks on the Sea Floor", video="walking_fish")
    for sub, name in (("research", "Researcher"), ("script", "Script writer"), ("packaging", "Packaging"), ("hooks", "Hook & retention check")):
        done("content", name, sub, p)
    o.finish(p, {"id": "walking_fish", "demo": True})
    p = o.begin("production", "Build bone_worm", video="bone_worm")
    for name in ("real photos (fetch_real)", "narration (your voice where recorded)", "render bone_worm", "QA bone_worm", "thumbnail"):
        o.step(p, name)
    o.end(p, 0)
    done("publishing", "Scheduling boyajian_star", "schedule", video="boyajian_star")
    done("analytics", "Refreshing numbers from YouTube and Buffer", "stats")
    p = o.begin("production", "Build tardigrade_space", video="tardigrade_space")
    o.step(p, "generated art (gen_visuals)")
    o.end(p, 1, f"{DEMO_TAG}: the image service asked us to slow down (429). Retry in a few minutes.")
    done("control", "Daily run", "daily", output={"demo": True, "drafted": "walking_fish"})


def build(folder, fresh=False):
    """Build the demo in `folder` by running this file with NETHER_DATA=folder, so every module writes there."""
    folder = Path(folder).expanduser().resolve()
    if fresh and folder.exists() and (folder / "channel.json").exists() and json.loads((folder / "channel.json").read_text()).get("demo"):
        shutil.rmtree(folder)
    if (folder / "channel.json").exists() and not json.loads((folder / "channel.json").read_text()).get("demo"):
        raise ValueError(f"{folder} holds a real channel — the demo only goes in an empty or demo folder.")
    env = {**os.environ, "NETHER_DATA": str(folder)}
    r = subprocess.run([sys.executable, str(HERE / "demo_data.py"), str(folder)], env=env, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise ValueError("The demo couldn't be built: " + (r.stderr or r.stdout)[-400:])
    return folder


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1]).expanduser().resolve()
    if os.environ.get("NETHER_DATA") and Path(os.environ["NETHER_DATA"]).expanduser().resolve() == folder:
        if (folder / "channel.json").exists() and not json.loads((folder / "channel.json").read_text()).get("demo"):
            sys.exit(f"{folder} holds a real channel — refusing.")
        if (folder / ".env").exists():
            sys.exit(f"{folder} has a .env — the demo never goes next to real keys.")
        folder.mkdir(parents=True, exist_ok=True)
        dump(folder / "channel.json", CHANNEL)
        build_files(folder, datetime.datetime.now().astimezone())
        build_tasks()
        print(f"Demo data folder ready: {folder}")
        return
    print(build(folder, fresh="--fresh" in sys.argv))


if __name__ == "__main__":
    main()
