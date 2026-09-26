#!/usr/bin/env python3
"""voice.py — your own narration, line by line (optional; Kokoro reads any line you haven't recorded).

    python3 voice.py apply cfg/<id>.json     copy your recordings into the narration cache before a render

Why: YouTube's rules against mass-produced content single out AI narration over stills; a real human voice
is the clearest sign of original work, and the proven comic channels all use one.

Recordings made in Studio (the Record button on each line of a draft) are cleaned — mono, loudness-levelled,
silence trimmed — and kept in out/voice/<video or episode id>/<line id>.mp3 with the exact text you read.
At render time a recording is used only while the line's text still matches; edit the line and it falls back
to Kokoro until you record it again. Word timings for the captions are estimated from the recording's length.
"""
import base64, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
VOICE, TTS = DATA / "out" / "voice", DATA / "tts"
ID_RE = re.compile(r"^[a-z0-9_]{1,80}$")


def _dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).decode().strip())


def _norm(t):
    return re.sub(r"\s+", " ", str(t)).strip()


def save(owner, line, text, data_b64, mime=""):
    """A take from the browser → out/voice/<owner>/<line>.mp3 (+ .json with the text it was read from)."""
    if not (ID_RE.match(owner) and ID_RE.match(line)):
        raise ValueError("Bad recording id.")
    raw = base64.b64decode(data_b64.split(",", 1)[-1])
    if len(raw) < 2000:
        raise ValueError("That recording was empty — check the microphone.")
    if len(raw) > 25_000_000:
        raise ValueError("That recording is too long for one line.")
    d = VOICE / owner
    d.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if "mp4" in mime or "aac" in mime else ".ogg" if "ogg" in mime else ".webm"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(raw)
        src = f.name
    out = d / f"{line}.mp3"
    try:
        # mono 48k · trim leading/trailing silence · level to -16 LUFS (the render's master mixes it with the score)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "48000", "-af",
                        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,"
                        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
                        "loudnorm=I=-16:TP=-1.5:LRA=11", "-b:a", "192k", str(out)], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise ValueError("Couldn't read that recording: " + (e.stderr or b"").decode(errors="replace")[-200:])
    finally:
        Path(src).unlink(missing_ok=True)
    secs = _dur(out)
    (d / f"{line}.json").write_text(json.dumps({"text": _norm(text), "seconds": round(secs, 2)}))
    return {"ok": True, "seconds": round(secs, 1)}


def delete(owner, line):
    if not (ID_RE.match(owner) and ID_RE.match(line)):
        raise ValueError("Bad recording id.")
    for ext in (".mp3", ".json"):
        (VOICE / owner / f"{line}{ext}").unlink(missing_ok=True)
    return {"ok": True}


def status(owner, lines):
    """{line id: "ok" | "stale" (text changed since recording)} for the lines that have a recording."""
    out = {}
    for lid, text in lines.items():
        meta = VOICE / owner / f"{lid}.json"
        if meta.exists() and (VOICE / owner / f"{lid}.mp3").exists():
            out[lid] = "ok" if json.loads(meta.read_text()).get("text") == _norm(text) else "stale"
    return out


def timings(text, secs):
    try:
        import tts_kokoro
        return tts_kokoro._estimate_word_timings(text, secs)
    except Exception:
        words = text.split()
        step = secs / max(len(words), 1)
        return [{"word": w, "start": round(i * step, 3), "end": round((i + 1) * step, 3)} for i, w in enumerate(words)]


def apply(cfg_path):
    """Before a render: for each line with a matching recording, put it in the narration cache (tts/<id>/).
    Looks in the video's own recordings, then the episode it was cut from (<episode>__<chapter> or "episode")."""
    cfg = json.loads(Path(cfg_path).read_text())
    vid = cfg["id"]
    owners = [vid.removesuffix("_tiktok")]
    if "__" in vid:
        owners.append(vid.split("__")[0])
    if cfg.get("episode"):
        owners.append(cfg["episode"])
    used, dst = 0, TTS / vid
    for s in cfg.get("segments", []):
        if not s.get("text"):
            continue
        lid, sid = s.get("src_id") or s["id"], s["id"]
        hit = None
        for o in owners:
            mp3, meta = VOICE / o / f"{lid}.mp3", VOICE / o / f"{lid}.json"
            if mp3.exists() and meta.exists() and json.loads(meta.read_text()).get("text") == _norm(s["text"]):
                hit = mp3
                break
        if hit:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy(hit, dst / f"{sid}.mp3")
            (dst / f"{sid}.json").write_text(json.dumps(timings(s["text"], _dur(hit))))
            (dst / f"{sid}.txt").write_text(s["text"])       # make_short keeps a cached line only if this matches
            (dst / f"{sid}.voice").write_text(str(hit))      # marks the cache entry as your take
            used += 1
        elif (dst / f"{sid}.voice").exists():                # your take was removed or the line changed:
            for ext in (".mp3", ".json", ".txt", ".voice"):  # clear it so Kokoro reads the line again
                (dst / f"{sid}{ext}").unlink(missing_ok=True)
    return used


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "apply":
        n = apply(sys.argv[2])
        print(f"your voice on {n} line(s)" if n else "no recordings for this video — Kokoro narrates")
    else:
        sys.exit(__doc__)
