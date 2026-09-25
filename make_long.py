#!/usr/bin/env python3
"""make_long.py — Production's long-form renderer: an episode → one 16:9 video with chapters.

    python3 make_long.py episodes/<id>.json              render out/<id>_long.mp4 (+ .srt, QA, thumbnail)
    python3 make_long.py episodes/<id>.json --preview    a frame every half second, no video (fast look)

One Production task with a step per stage, so a failure shows on the brain with the step that broke:
  Assemble     intro + a title card per chapter + the chapter's lines (tagged long) + outro → cfg/<id>_long.json
               ("format": "landscape": make_short.py renders 1920x1080, portrait art over a blurred fill)
  Narration    reuses the Shorts' recorded lines (same text, same voice) — only new lines are narrated
  Render       make_short.py (frames, captions, score, mix, subtitles)
  QA           qa_render.py (16:9 checks + contact sheet)
  Chapters     real timestamps from the narration → packaging/<id>_long.json (title, description with
               chapters and every chapter's sources, tags) + episodes/<id>.chapters.txt
  Thumbnail    make_thumb.py (1280x720)
Nothing is posted: the video appears in Production → Videos for review; ./post.sh <id>_long posts to YouTube only.
"""
import json, os, re, shutil, subprocess, sys, textwrap
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
CFG, PKG, TTS, OUT = HERE / "cfg", HERE / "packaging", HERE / "tts", HERE / "out"
PY = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable
TITLE_CARD = 2.6        # seconds a chapter title card holds (no narration)


def keep(seg):
    return "long" in seg.get("in", ["long", "short", "tiktok"])


def clean_vis(v):
    return {k: val for k, val in v.items() if k not in ("prompt", "real", "edit_from")}


def short_title(title):
    """The headline part of a packaging title: before the dash/colon ("Wolverine Wasn't Always a Mutant — Marvel…")."""
    return re.split(r"\s+[—–-]\s+|:\s+", title.strip(), maxsplit=1)[0]


def wrap_title(title, width=22, lines=3):
    out = textwrap.wrap(re.sub(r"\s+", " ", short_title(title)).upper(), width)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1].rstrip(",.;") + "…"
    return out


def sources_of(chapter_id, ep_id):
    """Chapter's own packaging (a made Short) → its title, tags and the 'Sources:' line of its description."""
    for cand in (chapter_id, f"{ep_id}__{chapter_id}"):
        p = PKG / f"{cand}.json"
        if p.exists():
            pk = json.loads(p.read_text())
            src = next((l.strip() for l in pk.get("youtube_description", "").splitlines() if l.strip().lower().startswith("sources")), "")
            return pk, src
    return {}, ""


def stills(ep):
    """Every photo/art still in the episode, in order (iceberg frames carry tier labels — not for cards)."""
    return [clean_vis(s["vis"]) for ch in ep["chapters"] for s in ch["segments"] if s.get("vis", {}).get("t") == "kb"]


def card_vis(v, fallback):
    return v if v.get("t") == "kb" else (dict(fallback) if fallback else v)


def assemble(ep):
    vid = f"{ep['id']}_long"
    pool = stills(ep)
    first_still, last_still = (pool[0], pool[-1]) if pool else (None, None)
    segs, marks, reuse, ice, skipped = [], [], [], None, []
    for s in ep.get("intro", []):
        if keep(s):
            segs.append({**s, "id": f"intro_{s['id']}", "vis": card_vis(clean_vis(s["vis"]), first_still)})
    if segs:
        marks.append(("Intro", segs[0]["id"]))
    for i, ch in enumerate(ep["chapters"]):
        body = [s for s in ch["segments"] if keep(s)]
        if not body:
            continue
        if any(s.get("vis", {}).get("t") == "ice" for s in body):     # an iceberg Short: its tiers come with it
            blk = ch.get("iceberg")
            if not blk:
                src = CFG / f"{ch['id']}.json"
                blk = json.loads(src.read_text()).get("iceberg") if src.exists() else None
            if not blk or (ice and blk != ice):          # the renderer draws one iceberg per video
                skipped.append(ch.get("title", ch["id"]))
                continue
            ice = blk
        cid = f"c{i + 1}"                        # by position: truncated names can collide (foo / foo_2)
        own = next((clean_vis(s["vis"]) for s in body if s["vis"].get("t") == "kb"), None)
        card = {"id": f"{cid}_title", "dur": TITLE_CARD, "gap": 0.2, "vis": own or card_vis(clean_vis(body[0]["vis"]), first_still),
                "hero": {"lines": wrap_title(ch.get("title", ch["id"])), "col": "a", "y": 660, "size": 118},
                "sub": f"CHAPTER {i + 1}", "srt": ch.get("title", "")}
        segs.append(card)
        marks.append((ch.get("title", ch["id"]), card["id"]))
        for s in body:
            n = {k: v for k, v in s.items() if k not in ("hook", "in")}
            n["id"], n["vis"] = f"{cid}_{s['id']}", clean_vis(s["vis"])
            segs.append(n)
            reuse.append((n["id"], s["id"], s.get("text", ""), [ch["id"], f"{ep['id']}__{ch['id']}"]))
    outro = [s for s in ep.get("outro", []) if keep(s)]
    for s in outro:
        segs.append({**s, "id": f"outro_{s['id']}", "vis": card_vis(clean_vis(s["vis"]), last_still)})
    if outro:
        marks.append(("Outro", segs[-len(outro)]["id"]))
    if len(marks) < 3:
        raise ValueError("A long-form needs at least 3 sections (YouTube chapters need 3).")
    cfg = {"id": vid, "file": vid, "format": "landscape", "palette": ep.get("palette", {}),
           "score": ep.get("score", "deep"), "credit": ep.get("credit", "SOURCES IN THE DESCRIPTION"),
           "hook": {"lines": []}, "episode": ep["id"],
           "end": {"at": 1.6, "lines": ["SUBSCRIBE FOR MORE", "NEXT WEEK:", str(ep.get("next", "MORE BURIED HISTORY")).upper()]},
           "segments": segs}
    if ice:
        cfg["iceberg"] = ice
    if skipped:
        print("left out (only one iceberg chart fits a video): " + "; ".join(skipped))
    return vid, cfg, marks, reuse


def reuse_narration(vid, reuse):
    """Copy a Short's recorded line when the text is identical — same voice, no re-recording."""
    dst = TTS / vid
    dst.mkdir(parents=True, exist_ok=True)
    got = 0
    for new_id, old_id, text, cands in reuse:
        if (dst / f"{new_id}.mp3").exists():
            got += 1
            continue
        for c in cands:
            src_cfg = CFG / f"{c}.json"
            mp3, js = TTS / c / f"{old_id}.mp3", TTS / c / f"{old_id}.json"
            if not (mp3.exists() and js.exists() and src_cfg.exists()):
                continue
            same = next((s for s in json.loads(src_cfg.read_text())["segments"] if s["id"] == old_id), {})
            if same.get("text", "").strip() == text.strip():
                shutil.copy(mp3, dst / f"{new_id}.mp3")
                shutil.copy(js, dst / f"{new_id}.json")
                got += 1
                break
    return got


def duration(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def timeline(vid, cfg):
    """Segment start times, computed exactly as make_short.py does."""
    t, starts = 0.0, {}
    for s in cfg["segments"]:
        d = (duration(TTS / vid / f"{s['id']}.mp3") + 0.05) if s.get("text") else s["dur"]
        starts[s["id"]] = t
        t += d + s.get("gap", 0.15)
    return starts, t + 0.25


def ts(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def thumb_for(ep, cfg, first, n):
    """Reuse the lead chapter's own thumbnail (its proven 2–3 words + image) and add "+N MORE"."""
    pk, _ = sources_of(ep["chapters"][0]["id"], ep["id"]) if ep.get("chapters") else ({}, "")
    th = dict(pk.get("thumbnail") or {})
    lines = [l for l in th.get("lines", []) if l][:2] or wrap_title(first, 12, 2)
    if n > 1:
        lines = lines + [f"+{n - 1} MORE"]
    src = th.get("src") or cfg["segments"][1 if len(cfg["segments"]) > 1 else 0]["vis"]["src"]
    return {"src": src, "lines": lines, "accent": len(lines) - 1, "cx": th.get("cx", 0.5), "cy": th.get("cy", 0.4),
            "zoom": th.get("zoom", 1.0)}


def package(ep, vid, cfg, marks, starts):
    chapters = [(0 if i == 0 else starts[sid], name) for i, (name, sid) in enumerate(marks)]
    lines = [f"{ts(t)} {name}" for t, name in chapters]
    tags, srcs, titles = [], [], []
    for ch in ep["chapters"]:
        pk, src = sources_of(ch["id"], ep["id"])
        titles.append(ch.get("title", ch["id"]))
        for tg in re.split(r",\s*", pk.get("youtube_tags", "")):
            if tg and tg.lower() not in [x.lower() for x in tags]:
                tags.append(tg)
        if src:
            src = re.sub(r"^sources:?\s*", "", src, flags=re.I)    # (kept out of the f-string: Python < 3.12)
            srcs.append(f"• {ch.get('title', ch['id'])}: {src}")
    intro = " ".join(s["text"] for s in ep.get("intro", []) if s.get("text"))
    first = titles[0].split(" — ")[0] if titles else ep["title"]
    title = f"{first} + {len(titles) - 1} More Stories the Fans Got Wrong" if len(titles) > 1 else ep["title"]
    desc = "\n".join([intro or ep["title"], "", "Chapters", *lines, "",
                      *([f"In this episode:"] + [f"• {t}" for t in titles]), "",
                      "Every story is fact-checked; sources per chapter:", *(srcs or ["(see each chapter's Short)"]), "",
                      "Subscribe for the buried history behind comics, anime, games and the real science hiding inside them.",
                      "", "#nethermind #comics #history #science"])
    pkg = {"title": title[:95], "title_options": [ep["title"][:95], f"{len(titles)} Buried Stories: {first}"[:95]],
           "youtube_description": desc, "youtube_tags": ", ".join((tags + ["nethermind", "long form"])[:15]),
           "pinned_comment": "Which of these did you already know? Tell me the one that surprised you most.",
           "thumbnail": thumb_for(ep, cfg, first, len(titles)),
           "episode": ep["id"]}
    (PKG / f"{vid}.json").write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
    (HERE / "episodes" / f"{ep['id']}.chapters.txt").write_text("\n".join(lines) + "\n")
    return pkg, lines


def run(cmd, tid):
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    log = (p.stdout + p.stderr)
    print(log[-2500:])
    if p.returncode:
        raise RuntimeError(log.strip().splitlines()[-1] if log.strip() else f"{cmd[1]} exited {p.returncode}")
    return log


def main(path, preview=False):
    ep = json.loads(Path(path).read_text())
    parent = nether.begin("production", f"Long-form: {ep['title']}", video=f"{ep['id']}_long",
                          retry={"kind": "long", "id": ep["id"]})
    cur = None
    try:
        cur = nether.begin("production", "Assemble the episode", sub="longform", parent=parent)
        vid, cfg, marks, reuse = assemble(ep)
        (CFG / f"{vid}.json").write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
        nether.finish(cur, {"sections": len(marks), "lines": sum(1 for s in cfg["segments"] if s.get("text"))})

        cur = nether.begin("production", "Narration (reuse the Shorts' voice)", sub="render", parent=parent)
        got = reuse_narration(vid, reuse)
        nether.finish(cur, {"reused": got, "of": len(reuse)})

        cur = nether.begin("production", "Render 16:9", sub="render", parent=parent)
        run([PY, "make_short.py", f"cfg/{vid}.json"] + (["--preview"] if preview else []), cur)
        nether.finish(cur)
        if preview:
            cur = None
            nether.finish(parent, {"preview": True})
            return vid

        cur = nether.begin("production", "QA", sub="qa", parent=parent)
        run([PY, "qa_render.py", f"cfg/{vid}.json"], cur)
        nether.finish(cur)

        cur = nether.begin("content", "Chapters + packaging", sub="packaging", parent=parent)
        starts, total = timeline(vid, cfg)
        pkg, lines = package(ep, vid, cfg, marks, starts)
        nether.finish(cur, {"chapters": lines, "length": ts(total)})

        cur = nether.begin("production", "Thumbnail", sub="thumbnail", parent=parent)
        run([PY, "make_thumb.py", f"packaging/{vid}.json"], cur)
        nether.finish(cur)
        cur = None
        nether.finish(parent, {"video": f"out/{vid}.mp4", "length": ts(total), "chapters": lines})
        print(f"\nDONE out/{vid}.mp4  ({ts(total)})\n" + "\n".join(lines))
        return vid
    except (Exception, SystemExit) as e:                # never leave a task stuck on "working"
        if cur:
            nether.fail(cur, f"{type(e).__name__}: {e}")
        nether.fail(parent, f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a:
        sys.exit(__doc__)
    main(a[0], preview="--preview" in sys.argv)
