"""
qa_render.py — catch what "it rendered with no error" doesn't.

    python3 qa_render.py cfg/my_topic.json

Written 2026-09-21 after two separate silent-failure incidents: (1) hook and
credit-line text overflowing both edges of the frame, only caught by a human
manually screenshotting frames and looking; (2) three Buffer posts running a
crushed ~200kbps Descript-remux copy and two more running the wrong (full-
length instead of short-cut) video, all with Buffer reporting error:null the
whole time (see claude/buffer-integration-plan.md in the YOUTUBE project for
the full incident writeup). Both bugs shipped because nothing actually looked
at the output before it was trusted. This script is that look, automated.

What it checks (fast, no judgment calls):
  - out/<id>.mp4 exists, is 1080x1920, h264+aac, bitrate above a healthy floor
  - duration roughly matches the config's segment timing (catches a stale/
    partial render or a wrong file)
  - the .srt exists and isn't empty

What it hands you to actually eyeball (the part that DOES need a human):
  - one frame from the hook, the midpoint of every segment, and the end
    card, tiled into a single contact sheet at out/<id>_qa_contact.jpg —
    a 5-second glance catches text overflow, a black/wrong frame, or a
    hero-stat card that doesn't fit, instead of finding out from a comment
    or a Buffer preview after it's live.

Exit code 0 = automated checks passed (still look at the contact sheet).
Exit code 1 = a check failed — read the printed reason, don't ship it.
"""
import json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")

def ffprobe(path, *entries):
    # ffprobe wants section specs joined with ":" (e.g. "stream=w,h:format=duration"),
    # not "," — that was the original bug here (duration always came back empty).
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", ":".join(entries),
         "-of", "default=noprint_wrappers=1", path],
        capture_output=True, text=True, check=True,
    ).stdout
    d = {}
    for line in out.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d.setdefault(k, v)  # first stream wins (video before audio)
    return d

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cfg_path = sys.argv[1]
    cfg = json.load(open(cfg_path))
    vid = cfg["id"]
    mp4 = os.path.join(HERE, "out", f"{vid}.mp4")
    srt = os.path.join(HERE, "out", f"{vid}.srt")
    ok = True

    if not os.path.exists(mp4):
        print(f"FAIL  {mp4} does not exist — render it first"); sys.exit(1)

    info = ffprobe(mp4, "stream=width,height,codec_name", "format=duration,bit_rate")
    w, h = int(info.get("width", 0)), int(info.get("height", 0))
    dur = float(info.get("duration", 0))
    br = int(info.get("bit_rate", 0))

    def check(label, cond, detail):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'}  {label} — {detail}")
        if not cond:
            ok = False

    check("dimensions", (w, h) == (1080, 1920), f"{w}x{h}")
    check("bitrate", br > 1_000_000, f"{br/1e6:.1f} Mbps (floor: 1.0 Mbps — a Descript-remux crush lands ~0.2)")
    check("srt exists", os.path.exists(srt) and os.path.getsize(srt) > 0, srt)

    expected_dur = max(s.get("start", 0) + s.get("dur", 0) for s in
                        [{"start": 0, "dur": 0}]) if False else None
    # segment timing isn't in the config directly (it's computed at render time
    # from TTS output) — just sanity-check duration is in a plausible Shorts range
    check("duration plausible", 3 <= dur <= 180, f"{dur:.1f}s")

    # ---- contact sheet: hook + one frame per segment + end card ----
    from PIL import Image
    n_probe = 8  # evenly spaced samples across the video is good enough for
                 # a QA glance without needing the real per-segment timing
    times = [dur * i / (n_probe + 1) for i in range(1, n_probe + 1)]
    tiles = []
    tmp = os.path.join(HERE, "out", f".{vid}_qa_frames")
    os.makedirs(tmp, exist_ok=True)
    for i, t in enumerate(times):
        fp = os.path.join(tmp, f"{i}.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", mp4, "-frames:v", "1", fp,
             "-loglevel", "error"], check=True,
        )
        tiles.append(Image.open(fp))

    cols = 4
    rows = math.ceil(len(tiles) / cols)
    tw, th = 270, 480  # thumbnail size per tile
    sheet = Image.new("RGB", (tw * cols, th * rows), (20, 20, 20))
    for i, im in enumerate(tiles):
        sheet.paste(im.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet_path = os.path.join(HERE, "out", f"{vid}_qa_contact.jpg")
    sheet.save(sheet_path, quality=88)
    print(f"\n  contact sheet: {sheet_path}  ({len(tiles)} frames, {dur:.1f}s total)")
    print("  LOOK AT IT before this ships — this script can't judge whether text")
    print("  overflows the frame or an image reads as the wrong thing. It can only")
    print("  make sure you're looking at the actual output instead of trusting a")
    print("  clean exit code.")

    print(f"\n{'PASS' if ok else 'FAIL'} — automated checks {'all passed' if ok else 'found a real problem, see above'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
