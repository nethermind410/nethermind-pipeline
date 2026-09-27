"""
quality_gate.py — a cheap, local, no-paid-AI check that a video is actually ready to post.

    python3 quality_gate.py cfg/<id>.json     # or just the id
    quality_gate.check("anglerfish") -> {"pass": bool, "score": 0-100, "checks": [...]}

Why: qa_render.py's contact sheet still needs a human to look at it, retention.py's score
is a pacing checklist she can ignore, and the packaging/thumbnail/disclosure steps are just
checklist items on Today. Nothing actually stops a bad upload — post_live/post_now/post_at
all only require confirm:true. This is the thing studio.py's /api/run asks before any of
those three actions run (see studio_ext_gate.py), so "always the best" is enforced, not hoped.

Every check here is local: ffprobe/ffmpeg on the rendered file, and reading the same cfg/
packaging JSON the rest of the app already reads. No vidIQ, no Claude call, nothing that
costs money or needs the network — those stay exactly where they already are (claude_task.py
score, the vidIQ button in studio_channel.py's precheck).

Each check is {"name", "ok", "level": "block"|"warn", "detail", "fix"}. "block" means
studio.py refuses the post unless she types a reason (gate_override); "warn" ships but is
shown so nothing is a surprise. pass = no failing "block" check. score is 100 minus a fixed
deduction per failing check (blocks cost more), floored at 0 — a number for the checklist
card's header, not a prediction of anything.
"""
import json, os, re, subprocess, sys

from channel import DATA
CFG, OUT, PKG = DATA / "cfg", DATA / "out", DATA / "packaging"

try:
    from qa_render import ffprobe          # same ffprobe helper qa_render.py already uses/tests
except Exception:                          # pragma: no cover — qa_render still importable without ffmpeg present
    ffprobe = None

import retention
from studio_channel import title_checklist  # reuses the same clickbait/length rules the title picker shows

BLOCK_PENALTY, WARN_PENALTY = 18, 8
CONFIRM_MARK = "[CONFIRM"


def _row(name, ok, level, detail, fix=""):
    return {"name": name, "ok": bool(ok), "level": level, "detail": detail, "fix": "" if ok else fix}


def _mp4_path(cfg, vid):
    return OUT / f"{cfg.get('file', vid)}.mp4"


def _loudness(mp4):
    """Runs ffmpeg's loudnorm filter in measure-only mode (one pass — no output file written)
    and pulls the measured integrated loudness out of the JSON block it prints to stderr.
    Returns None if ffmpeg isn't available or the probe fails — caller treats that as "can't tell"."""
    try:
        p = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", str(mp4), "-af", "loudnorm=I=-14:TP=-1.0:LRA=9:print_format=json",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def _has_audio_stream(mp4):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name",
             "-of", "csv=p=0", str(mp4)],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        return bool(out)
    except Exception:
        return None  # can't tell (ffprobe missing) — not the same as "no audio"


def _confirm_markers(cfg, pkg):
    hits = []
    for s in cfg.get("segments", []):
        if CONFIRM_MARK in (s.get("text") or ""):
            hits.append(s.get("id", "?"))
    for l in cfg.get("hook", {}).get("lines", []):
        if CONFIRM_MARK in (l[0] if l else ""):
            hits.append("hook")
    for k in ("title", "youtube_description", "tiktok_caption", "instagram_caption", "pinned_comment"):
        if CONFIRM_MARK in str((pkg or {}).get(k) or ""):
            hits.append(k)
    return hits


def _has_source_note(cfg, pkg):
    """This pipeline doesn't store a per-fact citation field — sources live as a "Sources:"-style
    line in the YouTube description (see packaging/mantis_shrimp_punch.json for the pattern).
    A video only needs one if it's actually making a factual claim (has an on-screen hero stat) —
    a plain "look at this" visual beat doesn't need a citation."""
    has_claim = any(s.get("hero") for s in cfg.get("segments", []))
    if not has_claim:
        return True, "no on-screen stat claims to source"
    desc = str((pkg or {}).get("youtube_description") or "")
    found = bool(re.search(r"source", desc, re.I))
    return found, ("has a Sources: line" if found else "makes an on-screen stat claim with no Sources: line in the description")


def check(id_or_cfg_path):
    vid = os.path.basename(str(id_or_cfg_path)).removesuffix(".json") if str(id_or_cfg_path).endswith(".json") else str(id_or_cfg_path)
    cfg_path = CFG / f"{vid}.json"
    checks = []

    if not cfg_path.exists():
        return {"pass": False, "score": 0,
                "checks": [_row("Script exists", False, "block", f"{cfg_path} does not exist",
                                 "This id doesn't have a script — nothing to gate.")]}
    cfg = json.loads(cfg_path.read_text())
    pkg = json.loads((PKG / f"{vid}.json").read_text()) if (PKG / f"{vid}.json").exists() else None
    landscape = cfg.get("format") == "landscape"
    mp4 = _mp4_path(cfg, vid)

    rendered = mp4.exists()
    checks.append(_row("Rendered", rendered, "block",
                        f"{mp4.name} exists" if rendered else f"{mp4.name} hasn't been rendered yet",
                        "Press Make video, then come back here."))

    if rendered and ffprobe is not None:
        try:
            info = ffprobe(str(mp4), "stream=width,height,codec_name", "format=duration,bit_rate")
            w, h = int(info.get("width", 0)), int(info.get("height", 0))
            dur = float(info.get("duration", 0))
            br = int(info.get("bit_rate", 0))
            want = (1920, 1080) if landscape else (1080, 1920)
            checks.append(_row("Frame size", (w, h) == want, "block", f"{w}x{h} (want {want[0]}x{want[1]})",
                                "The render used the wrong aspect ratio — re-make it."))
            checks.append(_row("Bitrate", br > 1_000_000, "block", f"{br/1e6:.1f} Mbps (floor 1.0 Mbps)",
                                "This looks like a crushed re-encode, not the real render — re-make it."))
            plaus = (60 <= dur <= 4 * 3600) if landscape else (3 <= dur <= 180)
            checks.append(_row("Duration", plaus, "block", f"{dur:.0f}s",
                                "Duration is outside what YouTube/TikTok/Instagram accept for this format — re-render."))
            audio = _has_audio_stream(mp4)
            if audio is None:
                checks.append(_row("Audio present", True, "warn", "couldn't check (ffprobe unavailable)",
                                    "Install ffmpeg to verify audio automatically."))
            else:
                checks.append(_row("Audio present", audio, "block", "has an audio track" if audio else "no audio track at all",
                                    "The render has no sound — re-make it."))
                if audio:
                    ln = _loudness(mp4)
                    if ln is None:
                        checks.append(_row("Loudness", True, "warn", "couldn't measure (ffmpeg probe failed)",
                                            "Re-run the gate once ffmpeg can read the file."))
                    else:
                        i = float(ln.get("input_i", -99))
                        sane = -30 <= i <= -6
                        checks.append(_row("Loudness", sane, "warn", f"measured {i:.1f} LUFS (sane range -30 to -6)",
                                            "Silent or near-silent audio — check the render." if i < -30 else
                                            "Audio is very hot/loud — check for clipping."))
        except Exception as e:
            checks.append(_row("Render checks", False, "warn", f"couldn't probe the file: {e}",
                                "Re-run the gate; if this keeps happening, check ffmpeg is installed."))
    elif rendered:
        checks.append(_row("Render checks", True, "warn", "ffmpeg/ffprobe not importable — skipped",
                            "Install ffmpeg to get the full render QA."))

    contact = OUT / f"{vid}_qa_contact.jpg"
    checks.append(_row("Contact sheet looked at", contact.exists(), "warn",
                        "a contact sheet exists (doesn't mean anyone looked — glance at it)" if contact.exists()
                        else "no contact sheet yet",
                        "Run: python3 qa_render.py cfg/%s.json — then actually look at it." % vid))

    hits = _confirm_markers(cfg, pkg)
    checks.append(_row("No unresolved confirms", not hits, "block",
                        "clean" if not hits else f"{CONFIRM_MARK}...] left in: {', '.join(hits)}",
                        "Resolve every [CONFIRM...] marker before this ships."))

    sourced, why = _has_source_note(cfg, pkg)
    checks.append(_row("Facts are sourced", sourced, "block", why,
                        "Add a \"Sources:\" line to the YouTube description naming where the stat came from."))

    score10, rows = retention.check(cfg)
    first = (cfg.get("segments") or [{}])[0]
    first_words = len((first.get("text") or "").split())
    lands_fast = first_words / retention.WPS <= 2.5 if first_words else False
    checks.append(_row("Hook lands fast", lands_fast,
                        "warn", f"first line is ~{first_words / retention.WPS:.1f}s of speech (want ≤2.5s)",
                        "Shorten the first spoken line — the swipe happens before 3s."))
    misses = [m for ok, m in rows if not ok]
    checks.append(_row("Retention checklist", score10 >= 7, "warn", f"{score10}/10" + (f" — {misses[0]}" if misses else ""),
                        "Run: python3 retention.py check cfg/%s.json — for every miss." % vid))

    title = (pkg or {}).get("title") or ""
    checks.append(_row("Has a title", bool(title), "block", "titled" if title else "packaging has no title yet",
                        "Finish packaging before scheduling."))
    if title:
        tchecks = title_checklist(title)
        failed = [c["label"] for c in tchecks if not c["ok"]]
        checks.append(_row("Title reads clean", not failed, "warn",
                            "passes the title checklist" if not failed else "; ".join(failed),
                            "Pick a different title option or edit it — see the title checklist on this page."))

    desc = (pkg or {}).get("youtube_description") or ""
    checks.append(_row("Description written", bool(desc.strip()), "warn",
                        "has a description" if desc.strip() else "empty description",
                        "Packaging didn't write a description — redraft or edit it by hand."))

    thumb = OUT / f"{vid}_thumb.jpg"
    checks.append(_row("Thumbnail exists", thumb.exists(), "warn",
                        thumb.name if thumb.exists() else "no thumbnail file",
                        "Make video generates one automatically — re-make if it's missing."))

    if pkg is not None:
        needs_disc = bool(pkg.get("synthetic_disclosure", True))  # TTS narration means almost every video needs it
        checks.append(_row("AI disclosure flagged", needs_disc, "warn",
                            "flagged for YouTube's synthetic-content disclosure" if needs_disc
                            else "not flagged — check this is really a real-voice video",
                            "Set synthetic_disclosure and mark it in YouTube Studio → Details → Show more."))

    blockers_failed = sum(1 for c in checks if not c["ok"] and c["level"] == "block")
    warns_failed = sum(1 for c in checks if not c["ok"] and c["level"] == "warn")
    score = max(0, 100 - blockers_failed * BLOCK_PENALTY - warns_failed * WARN_PENALTY)
    return {"pass": blockers_failed == 0, "score": score, "checks": checks}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    result = check(sys.argv[1])
    print(f"{'PASS' if result['pass'] else 'BLOCK'} — score {result['score']}/100")
    for c in result["checks"]:
        mark = "ok  " if c["ok"] else ("FAIL" if c["level"] == "block" else "warn")
        print(f"  {mark}  {c['name']} — {c['detail']}" + ("" if c["ok"] else f"  ->  {c['fix']}"))
    sys.exit(0 if result["pass"] else 1)
