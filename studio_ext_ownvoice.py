"""Studio extension: her own voiceover for the weekly long-form episode.

The weekly long-form is written by NETHER but voiced by the creator herself (not Kokoro). This
extension is the missing link between "script approved" and "render": upload ONE audio file for
the whole episode (m4a/wav/mp3 — however she recorded it) and it's split into the same per-line
cache voice.py's Record button already writes to (out/voice/<episode>/<line id>.mp3 + .json).
make_long.py's render already prefers a matching recording over Kokoro for every line (voice.apply,
unchanged) — so once this has run, rendering the episode uses her voice automatically, and the
Shorts episode.py cuts from it reuse the same recorded lines (make_long.py's reuse_narration/
voice.apply, also unchanged). No new render code; this only prepares the cache the old code reads.

Word timings: no transcription model ships in this app's venv (checked: no `whisper` package), so a
line's slice of the upload is sized proportionally to its share of the episode's word count, not
aligned to her actual speech. Good enough to pick the right ~10-30s window per line for a beat-timed
video; if a line runs noticeably long or short in her recording, re-cut episodes/<id>.json's beats
or trim the upload before re-uploading.

GET  /api/ownvoice/status/<episode>   coverage: total spoken lines, how many now carry her voice, seconds
POST /api/ownvoice/upload             {"episode", "data" (base64 audio), "mime"} → splits + saves
POST /api/ownvoice/clear              {"episode"} → throw away her voice for this episode (Kokoro reads again)
POST /api/ownvoice/render             {"episode"} → render now (Production; same job as /api/long/render)
"""
import base64, json, re, subprocess, tempfile
from pathlib import Path

from channel import DATA

ID_RE = re.compile(r"^[a-z0-9_]{3,60}$")
EPS = DATA / "episodes"
VOICE = DATA / "out" / "voice"
UPLOADS = DATA / "out" / "voice_uploads"


def _eid(body):
    eid = str(body.get("episode") or body.get("id") or "")
    if not (ID_RE.match(eid) and (EPS / f"{eid}.json").exists()):
        raise ValueError("Which episode?")
    return eid


def _load(eid):
    return json.loads((EPS / f"{eid}.json").read_text())


def _norm(t):
    return re.sub(r"\s+", " ", str(t)).strip()


def _lines(ep):
    """Every spoken line, in the order make_long.py's assemble() will play them — intro, each
    chapter's body, outro. A line's own "id" is what assemble() calls src_id, which is what
    voice.apply() looks the recording up by, so these ids must match episodes/<id>.json exactly."""
    out = list(ep.get("intro") or [])
    for c in ep.get("chapters") or []:
        out += c.get("segments") or []
    out += ep.get("outro") or []
    return [s for s in out if _norm(s.get("text", ""))]


def _dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


def status(eid):
    if not ID_RE.match(eid) or not (EPS / f"{eid}.json").exists():
        raise ValueError("Which episode?")
    ep = _load(eid)
    lines = _lines(ep)
    have = 0
    for s in lines:
        meta = VOICE / eid / f"{s['id']}.json"
        if meta.exists() and (VOICE / eid / f"{s['id']}.mp3").exists():
            try:
                if json.loads(meta.read_text()).get("text") == _norm(s["text"]):
                    have += 1
            except Exception:
                pass
    upload = next(iter(UPLOADS.glob(f"{eid}.*")), None)
    return {"episode": eid, "own_voice": bool(ep.get("own_voice")), "draft": bool(ep.get("draft")),
            "lines": len(lines), "recorded": have, "complete": have >= len(lines) > 0,
            "uploaded": bool(upload), "uploaded_at": upload.stat().st_mtime if upload else None,
            "method": "word-count-proportional (no speech alignment available)"}


def upload(body):
    eid = _eid(body)
    ep = _load(eid)
    if ep.get("draft"):
        raise ValueError("Approve the episode's script before recording — the lines could still change.")
    lines = _lines(ep)
    if not lines:
        raise ValueError("This episode has no spoken lines yet.")
    data = str(body.get("data") or "")
    if not data:
        raise ValueError("No audio came through — try the upload again.")
    try:
        raw = base64.b64decode(data.split(",", 1)[-1], validate=True)
    except Exception:
        raise ValueError("That doesn't look like an uploaded file — try again.")
    if len(raw) < 5000:
        raise ValueError("That file is too short to be a whole episode's narration.")
    if len(raw) > 400_000_000:
        raise ValueError("That file is too large (over 400 MB).")
    mime = str(body.get("mime") or "").lower()
    if "m4a" in mime or "mp4" in mime or "aac" in mime:
        ext = ".m4a"
    elif "wav" in mime:
        ext = ".wav"
    elif "mp3" in mime or "mpeg" in mime:
        ext = ".mp3"
    elif not mime or mime.startswith("audio/"):
        ext = ".mp3"          # unrecognised or missing mime (some browsers don't set one for m4a) — let ffprobe be the real gate
    else:
        raise ValueError("Upload an audio recording (m4a, wav or mp3) — that file's type doesn't look like audio.")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    tmp = UPLOADS / f"{eid}__uploading{ext}"           # validate before touching the old upload — a bad
    tmp.write_bytes(raw)                               # re-upload must never destroy the good original
    # ("__uploading" so this temp name never matches the "{eid}.*" cleanup glob below)
    try:
        total = _dur(tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise ValueError("That file doesn't look like a readable audio recording — try re-exporting it and upload again.")
    for old in UPLOADS.glob(f"{eid}.*"):                # only now that the new file is confirmed readable
        old.unlink(missing_ok=True)
    src = UPLOADS / f"{eid}{ext}"
    tmp.rename(src)

    words = [len(_norm(s["text"]).split()) for s in lines]
    total_words = sum(words) or len(words)
    dst = VOICE / eid
    dst.mkdir(parents=True, exist_ok=True)
    manual = set()                                      # line ids with a take that isn't this upload's own —
    for f in dst.glob("*.json"):                         # a ● Record button take (voice.save(), no "source" key)
        try:                                             # must survive both the clear below and the re-split loop.
            if json.loads(f.read_text()).get("source") == "upload":
                f.with_suffix(".mp3").unlink(missing_ok=True)
                f.unlink(missing_ok=True)
            else:
                manual.add(f.stem)
        except Exception:
            pass
    t = 0.0
    done = 0
    for s, w in zip(lines, words):
        secs = total * (w / total_words)
        if s["id"] in manual:                            # keep her individually-recorded take for this line
            t += secs
            continue
        out = dst / f"{s['id']}.mp3"
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-t", f"{max(secs, 0.2):.3f}", "-i", str(src),
                            "-ac", "1", "-ar", "48000", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-b:a", "192k", str(out)],
                           check=True, capture_output=True, timeout=60)
            clip_secs = _dur(out)
            (dst / f"{s['id']}.json").write_text(json.dumps({"text": _norm(s["text"]), "seconds": round(clip_secs, 2), "source": "upload"}))
            done += 1
        except Exception:
            out.unlink(missing_ok=True)
        t += secs
    return {"ok": True, "episode": eid, "lines": len(lines), "cut": done, "seconds": round(total, 1),
            "reply": f"Split your {round(total / 60, 1)}-minute recording into {done} of {len(lines)} lines "
                     "(timed by word count — re-cut a beat and re-upload if a line's window is off). "
                     "Render the episode when you're happy with it."}


def clear(body):
    eid = _eid(body)
    d = VOICE / eid
    for f in (d.glob("*.json") if d.exists() else []):
        # keep any per-line take recorded with the ● Record button (no "source" key) — Remove only
        # throws away what this upload split, matching what the panel says it does.
        try:
            if json.loads(f.read_text()).get("source") == "upload":
                f.with_suffix(".mp3").unlink(missing_ok=True)
                f.unlink(missing_ok=True)
        except Exception:
            pass
    for f in UPLOADS.glob(f"{eid}.*"):
        f.unlink(missing_ok=True)
    return {"ok": True, "reply": "Your uploaded recording was removed — any lines you recorded individually with ● Record are kept; Kokoro narrates the rest."}


def render(body):
    eid = _eid(body)
    st = status(eid)
    if st["draft"]:
        raise ValueError("Approve the episode first.")
    if not st["recorded"]:
        raise ValueError("Upload your recording first — there's no line with your voice on it yet.")
    missing = st["lines"] - st["recorded"]
    if missing and not body.get("confirm"):
        raise ValueError(f"{missing} of {st['lines']} line{'s' if missing != 1 else ''} will use the AI voice, not "
                          "your own recording. Render anyway?")
    import studio_ext_make
    return studio_ext_make.render_long({"id": eid})


GET_PREFIX = {"/api/ownvoice/status/": status}
POST = {"/api/ownvoice/upload": upload, "/api/ownvoice/clear": clear, "/api/ownvoice/render": render}
