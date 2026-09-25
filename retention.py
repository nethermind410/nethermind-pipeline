#!/usr/bin/env python3
"""
retention.py — score a config's hook/pacing, and build a TikTok retention cut.

    python3 retention.py check  cfg/<id>.json            # score + fixes, no files written
    python3 retention.py tiktok cfg/<id>.json [--max 30]  # writes cfg/<file>_tiktok.json

Why: TikTok average watch time on the current cuts is 4–9s — viewers leave
before the payoff. The old _tiktok configs only dropped middle beats; they kept
the YouTube hook and the slow opening zoom. This cut changes the first second:

  1. Cold-open number — the video's first hero number is on screen at frame 0.
  2. Punch-in — the opening Ken Burns move is at least 0.35 zoom, so frame 0 moves.
  3. Tight gaps — 0.08s between beats (dead air is where the swipe happens).
  4. Length check — if it runs over --max seconds, names the longest optional
     beats to tag out. It never drops a beat itself (that breaks the story).
  5. Follow end card — names the next video as a numbered follow, not "subscribe".
  6. No long holds — any beat over ~6s is split at a clause break and the second
     half re-frames the still, so the picture changes every few seconds.

Wording is never changed. The cut gets its own id (<id>_tiktok); copy
tts/<id>/ into tts/<id>_tiktok/ first (build.sh does) and every beat kept whole
reuses the main narration. Split beats get new ids (s7_p1/s7_p2), so only those
are re-narrated by Kokoro.

The check score is a pacing checklist, not a prediction. Against real results it
doesn't hold up yet: the old hulk TikTok cut scores 8/10 but averaged 3.8s
watched; wolverine scores 1/10 and was the best performer (8.6s on TikTok,
2,430 IG views). Treat the TikTok cut as an experiment and judge it on stats.py
average watch time, not on this score.

Segments can carry "in": ["long", "short", "tiktok"] to say where they appear;
a segment without "in" appears everywhere.
"""
import copy, json, os, sys

WPS = 2.8          # Kokoro am_liam speaks ~2.8 words/sec (measured on hulk_color_origin_tiktok)
END_HOLD = 1.4


def est(seg):
    """Estimated seconds for one segment, including its gap."""
    if seg.get("text"):
        return len(seg["text"].split()) / WPS + 0.05 + seg.get("gap", 0.15)
    return seg.get("dur", 0) + seg.get("gap", 0.15)


def total(cfg):
    return sum(est(s) for s in cfg["segments"]) + 0.25


def essential(seg, i, n):
    return i == 0 or i == n - 1 or seg.get("hook") or seg.get("hero") or seg.get("payoff")


def check(cfg, target=None):
    """Return (score out of 10, list of (ok, message))."""
    segs = cfg["segments"]
    target = target or (35 if cfg.get("file", "").endswith("_tiktok") else 60)
    out = []

    first = (segs[0].get("text") or "").split()
    out.append((len(first) <= 8, f"first spoken line is {len(first)} words (≤8 lands before the swipe)"))

    hook_words = {w.strip(".,!?—'").lower() for l in cfg.get("hook", {}).get("lines", []) for w in l[0].split()}
    said = {w.strip(".,!?—'").lower() for w in first}
    overlap = len(hook_words & said) / max(len(hook_words), 1)
    out.append((overlap >= .5, f"hook text matches the voice ({overlap:.0%} word overlap, want ≥50%)"))

    t, hero_t = 0.0, None
    for s in segs:
        if s.get("hero"):
            words = (s.get("text") or "").split()
            hero_t = t + min(s["hero"]["at"], max(len(words) - 1, 0)) / WPS
            break
        t += est(s)
    out.append((hero_t is not None and hero_t <= 3.0,
                "first on-screen number at " + (f"{hero_t:.1f}s" if hero_t is not None else "never") + " (want ≤3s)"))

    z = segs[0].get("vis", {})
    motion = abs(z.get("z0", 1) - z.get("z1", 1)) if z.get("t") == "kb" else 1
    out.append((motion >= .3, f"opening zoom moves {motion:.2f} (≥0.30 so frame 0 isn't a still)"))

    dur = total(cfg)
    out.append((dur <= target, f"estimated length {dur:.0f}s (target ≤{target}s)"))

    longest = max(segs, key=est)
    out.append((est(longest) <= 6, f"longest single beat '{longest['id']}' holds one visual {est(longest):.1f}s (≤6s)"))

    end = cfg.get("end", {}).get("lines", [])
    out.append((any("NEXT" in l for l in end), "end card names the next video"))

    weights = [2, 1, 2, 1, 2, 1, 1]
    score = sum(w for (ok, _), w in zip(out, weights) if ok)
    return score, out


def split_long(segs, max_beat=6.0):
    """Split any beat longer than max_beat at the clause break nearest its middle,
    so the picture changes. The second half re-frames the same still (reversed
    zoom, shifted centre). New segment ids mean new narration for those halves only."""
    out = []
    for s in segs:
        words = (s.get("text") or "").split()
        if est(s) <= max_beat or len(words) < 8 or s.get("hook") or s.get("vis", {}).get("t") != "kb":
            out.append(s); continue
        mid = len(words) // 2
        breaks = [i + 1 for i, w in enumerate(words[:-3]) if i >= 2 and w[-1] in ",;:—" or w in ("—", "-")]
        cut = min(breaks, key=lambda i: abs(i - mid)) if breaks else mid
        a, b = copy.deepcopy(s), copy.deepcopy(s)
        a["id"], b["id"] = s["id"] + "_p1", s["id"] + "_p2"   # _p: can't collide with hand-named s4b etc.
        a["text"], b["text"] = " ".join(words[:cut]), " ".join(words[cut:])
        a["gap"] = 0.04
        if s.get("hero"):
            if s["hero"]["at"] >= cut:
                a.pop("hero"); b["hero"] = {**s["hero"], "at": s["hero"]["at"] - cut}
            else:
                b.pop("hero")
        for k in ("hook",): b.pop(k, None)
        v = b["vis"]
        v["z0"], v["z1"] = v.get("z1", 1.1) + .15, v.get("z0", 1.3)
        v["cx"] = round(min(max(v.get("cx", .5) + (.12 if v.get("cx", .5) <= .5 else -.12), .15), .85), 2)
        out += split_long([a, b], max_beat)
    return out


def tiktok(cfg, max_s=30):
    c = copy.deepcopy(cfg)
    # own id: make_short.py names the .srt and qa_render.py finds the .mp4 by id,
    # so sharing the main id would overwrite the main video's subtitles
    c["id"] = c["file"] = cfg["id"].removesuffix("_tiktok") + "_tiktok"
    segs = [s for s in c["segments"] if "tiktok" in s.get("in", ["tiktok"])]
    for s in segs:
        s.pop("prompt", None); s.get("vis", {}).pop("prompt", None)
        s.get("vis", {}).pop("real", None); s.get("vis", {}).pop("edit_from", None)
        s["gap"] = min(s.get("gap", 0.15), 0.08)

    # 4. length: suggest cuts, never make them — dropping a beat automatically
    #    breaks the story (a later line refers back to it). Tag the beat with
    #    "in": ["long", "short"] to leave it out of the TikTok cut.
    over = sum(est(s) for s in segs) + END_HOLD - max_s
    if over > 0:
        cands = sorted(((est(s), s["id"]) for i, s in enumerate(segs) if not essential(s, i, len(segs))), reverse=True)
        print(f"\n! TikTok cut is ~{over:.0f}s over {max_s:.0f}s. Longest optional beats: "
              + ", ".join(f"{i} ({d:.1f}s)" for d, i in cands[:4])
              + '\n  add "in": ["long", "short"] to the ones the story survives without, then re-run.')

    # 6. no single still held longer than ~6s
    segs = split_long(segs)

    # 1. cold-open number: show the first hero on frame 0 of the hook beat
    hero = next((s["hero"] for s in segs if s.get("hero")), None)
    if hero and not segs[0].get("hero"):
        segs[0]["hero"] = {**hero, "at": 0}

    # 2. punch-in on the opening still
    v = segs[0].get("vis", {})
    if v.get("t") == "kb" and abs(v.get("z0", 1) - v.get("z1", 1)) < .35:
        v["z0"], v["z1"] = round(v.get("z1", 1.1) + .4, 2), v.get("z1", 1.1)

    # 5. follow end card
    end = c.get("end", {"at": 1.4, "lines": []})
    nxt = end["lines"][-1] if end.get("lines") else "PART 2"
    c["end"] = {"at": 0.9, "lines": ["FOLLOW FOR", "NEXT:", nxt]}

    c["segments"] = segs
    return c


def report(path, cfg):
    score, rows = check(cfg)
    print(f"\n{os.path.basename(path)}  —  retention score {score}/10")
    for ok, msg in rows:
        print(f"  {'✓' if ok else '✗'} {msg}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "tiktok"):
        sys.exit(__doc__)
    mode, path = sys.argv[1], sys.argv[2]
    cfg = json.load(open(path))
    if mode == "check":
        report(path, cfg)
    else:
        mx = float(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 30
        cut = tiktok(cfg, mx)
        dst = os.path.join(os.path.dirname(path), cut["file"] + ".json")
        json.dump(cut, open(dst, "w"), indent=1, ensure_ascii=False)
        report(path, cfg)
        report(dst, cut)
        print(f"\nwrote {dst}\n  render: python3 make_short.py {dst}")
