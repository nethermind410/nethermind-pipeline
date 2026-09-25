#!/usr/bin/env python3
"""
episode.py — one research pass in, a long-form episode plus its Shorts out.

    python3 episode.py episodes/<id>.json

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

    for i, ch in enumerate(chapters):
        cid = f"{ep['id']}__{ch['id']}"
        segs = [dict(s) for s in ch["segments"] if keep(s, "short")]
        if not segs:
            sys.exit(f"chapter {ch['id']} has no segments tagged for 'short'")
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
    print(f"build each:  ./build.sh {ep['id']}__<chapter>   (Short + TikTok cut + QA + thumbnail)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
