#!/usr/bin/env python3
"""
episode.py — one research pass in, a long-form episode plus its Shorts out.

    python3 episode.py episodes/<id>.json
    python3 episode.py --week          this week's finished Shorts → one long-form episode plan

Write the episode once as chapters. Each chapter is a complete Short-sized
story with its own hook; the long-form video is the chapters in order with an
intro and outro around them. This writes:

    cfg/<ep>__<chapter>.json          vertical Short for each chapter
    cfg/<ep>__<chapter>_tiktok.json   TikTok retention cut of it (see retention.py)
    episodes/<ep>.plan.md             long-form script, YouTube chapter
                                      timestamps, the Shorts list and their
                                      retention scores

Every segment can carry "in": ["long", "short", "tiktok"] to say where it
appears (default: everywhere). Use it for the extra depth the long-form gets
and the Shorts don't — the Shorts stay tight, the episode gets the detail.

Each Short's end card points at the next chapter's Short, and the last one at
the episode's "next", so the Shorts chain into each other and into the episode.

Build each chapter with ./build.sh <ep>__<chapter> — it renders the Short and
its TikTok cut, reusing the Short's narration for the cut.

The long-form (16:9) render itself is not wired yet: make_short.py is fixed
at 1080x1920. The plan file is the script and chapter list for it meanwhile.
"""
import json, os, sys
from retention import tiktok, check, est

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = ("palette", "score", "credit", "voice_id", "cap_y")


def keep(seg, where):
    return where in seg.get("in", ["long", "short", "tiktok"])


def ts(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def main(path):
    ep = json.load(open(path))
    chapters = ep["chapters"]
    os.makedirs(os.path.join(HERE, "cfg"), exist_ok=True)
    written, rows = [], []

    for i, ch in enumerate(chapters if ep.get("shorts", True) else []):   # a weekly episode's chapters ARE made Shorts
        cid = f"{ep['id']}__{ch['id']}"
        segs = [dict(s) for s in ch["segments"] if keep(s, "short")]
        if not segs:
            print(f"skipped chapter {ch['id']}: every line is long-form only")
            continue
        segs[0]["hook"] = True
        nxt = chapters[i + 1]["title"] if i + 1 < len(chapters) else ep.get("next", "PART 2")
        cfg = {"id": cid, "file": cid,
               **{k: ch.get(k, ep[k]) for k in SHARED if k in ch or k in ep},
               "hook": ch["hook"],
               "end": {"at": 1.4, "lines": ["FULL EPISODE ON THE CHANNEL", "NEXT:", nxt.upper()]},
               # the TikTok cut filters on "in" itself, so keep the tags on the full list
               "segments": segs}
        short_path = os.path.join(HERE, "cfg", cid + ".json")
        json.dump(cfg, open(short_path, "w"), indent=1, ensure_ascii=False)

        full = {**cfg, "segments": [dict(s) for s in ch["segments"] if keep(s, "short") or keep(s, "tiktok")]}
        full["segments"][0]["hook"] = True
        tk = tiktok(full, 30)
        tk_path = os.path.join(HERE, "cfg", tk["file"] + ".json")
        json.dump(tk, open(tk_path, "w"), indent=1, ensure_ascii=False)

        written += [short_path, tk_path]
        rows.append((ch, cid, check(cfg)[0], check(tk)[0]))

    # ---- long-form plan
    t, lines, marks = 0.0, [], []
    for block, segs in [("Intro", ep.get("intro", []))] + [(c["title"], c["segments"]) for c in chapters] \
                       + [("Outro", ep.get("outro", []))]:
        segs = [s for s in segs if keep(s, "long")]
        if not segs: continue
        marks.append((t, block))
        lines.append(f"\n## {ts(t)} — {block}\n")
        for s in segs:
            lines.append(f"- {s.get('text', '[' + s['vis'].get('t', '') + ' ' + str(s.get('dur', '')) + 's]')}")
            t += est(s)
    if marks and marks[0][0] != 0:
        marks[0] = (0, marks[0][1])

    plan = [f"# {ep['title']}\n",
            f"Estimated long-form length: **{ts(t)}** (at ~2.8 words/sec; the render sets the real timestamps).\n",
            "## YouTube description chapters\n", "```"]
    plan += [f"{ts(m)} {name}" for m, name in marks]
    plan += ["```\n",
             "YouTube needs the first chapter at 0:00, at least three chapters, each at least 10 seconds.\n",
             "## Shorts from this episode\n",
             "| Chapter | Short config | Score | TikTok score |", "|---|---|---|---|"]
    plan += [f"| {c['title']} | `cfg/{cid}.json` | {s}/10 | {k}/10 |" for c, cid, s, k in rows]
    plan += ["\nScores come from `retention.py check`: a pacing checklist, not a view prediction.\n",
             "## Long-form script"] + lines
    plan_path = os.path.join(os.path.dirname(os.path.abspath(path)), ep["id"] + ".plan.md")
    open(plan_path, "w").write("\n".join(plan) + "\n")

    print(f"{ep['title']}: {len(chapters)} chapters, long-form ≈ {ts(t)}")
    for c, cid, s, k in rows:
        print(f"  {cid:40s} short {s}/10   tiktok {k}/10")
    print(f"\nwrote {len(written)} configs + {os.path.relpath(plan_path, HERE)}")
    if written:
        print(f"build each:  ./build.sh {ep['id']}__<chapter>   (Short + TikTok cut + QA + thumbnail)")
    print(f"long-form:   python3 make_long.py {os.path.relpath(path, HERE)}   (16:9, chapters, packaging, thumbnail)")


def weekly(days=7):
    """The Episode planner's weekly job: this week's made Shorts become the chapters of one long-form
    episode (no new Shorts are cut — they already exist). Writes episodes/week_<year>_<week>.json + plan."""
    import datetime
    from pathlib import Path
    here = Path(HERE)
    cut = datetime.datetime.now().timestamp() - days * 86400
    picks = []
    for p in sorted((here / "cfg").glob("*.json"), key=lambda p: p.stat().st_mtime):
        c = json.load(open(p))
        if (p.stat().st_mtime < cut or p.stem.endswith("_tiktok") or "__" in p.stem or p.stem.startswith(("test", "_"))
                or c.get("draft") or c.get("format") == "landscape" or not (here / "packaging" / f"{p.stem}.json").exists()):
            continue
        picks.append((p.stem, c, json.load(open(here / "packaging" / f"{p.stem}.json"))))
    if len(picks) < 3:
        raise ValueError(f"Only {len(picks)} finished Short(s) from the last {days} days — an episode needs at least 3 chapters.")
    y, w, _ = datetime.date.today().isocalendar()
    eid = f"week_{y}_{w:02d}"
    titles = [pk.get("title", vid) for vid, _, pk in picks]
    ep = {"id": eid, "title": f"Nethermind — week {w}: " + " · ".join(t.split(" — ")[0] for t in titles[:3]),
          "shorts": False, "next": "NEXT WEEK'S EPISODE",
          **{k: picks[0][1][k] for k in SHARED if k in picks[0][1]},
          "intro": [{"id": "i1", "in": ["long"], "vis": dict(next((s["vis"] for _, c, _ in picks for s in c["segments"]
                                                                   if s["vis"].get("t") == "kb"), picks[0][1]["segments"][0]["vis"])), "gap": 0.3,
                     "text": f"This week: {len(picks)} stories where the popular version is wrong. Starting with this one."}],
          "chapters": [{"id": vid, "title": pk.get("title", vid), "hook": c.get("hook", {"lines": []}),
                        **({"iceberg": c["iceberg"]} if c.get("iceberg") else {}),
                        "segments": [s for s in c["segments"]]} for vid, c, pk in picks],
          "outro": [{"id": "o1", "in": ["long"], "vis": dict(next((s["vis"] for _, c, _ in reversed(picks) for s in reversed(c["segments"])
                                                                   if s["vis"].get("t") == "kb"), picks[-1][1]["segments"][-1]["vis"])), "gap": 0.3,
                     "text": "That's the week. Subscribe, and next week there's another round of buried history."}]}
    path = here / "episodes" / f"{eid}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(ep, indent=1, ensure_ascii=False))
    main(str(path))
    return eid


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--week":
        print(weekly())
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        sys.exit(__doc__)
