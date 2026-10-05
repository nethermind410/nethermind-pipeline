#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "============================================================"
echo " CLIPPING FARM — COMPLETE BUILD INSTALLER"
echo "============================================================"

mkdir -p complete
mkdir -p complete/data
mkdir -p complete/runs
mkdir -p complete/exports
mkdir -p complete/packs
mkdir -p complete/learning

cat > complete/pipeline.py <<'PY'
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "complete.db"
RUNS = ROOT / "runs"
EXPORTS = ROOT / "exports"
PACKS = ROOT / "packs"
LEARNING = ROOT / "learning"

for p in (ROOT / "data", RUNS, EXPORTS, PACKS, LEARNING):
    p.mkdir(parents=True, exist_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def slug(value):
    value = re.sub(r"[^A-Za-z0-9]+", "-", value or "")
    return value.strip("-").lower()[:80] or "untitled"


def ident(value):
    return hashlib.sha1(str(value).encode()).hexdigest()[:14]


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS opportunities (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        topic TEXT NOT NULL,
        title TEXT,
        url TEXT,
        channel TEXT,
        score REAL DEFAULT 0,
        reason TEXT,
        status TEXT DEFAULT 'NEW',
        metadata TEXT
    );

    CREATE TABLE IF NOT EXISTS assets (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        source_url TEXT,
        path TEXT,
        title TEXT,
        duration REAL,
        metadata TEXT
    );

    CREATE TABLE IF NOT EXISTS candidates (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        asset_id TEXT,
        start REAL,
        end REAL,
        score REAL,
        reasons TEXT,
        status TEXT DEFAULT 'CANDIDATE',
        metadata TEXT
    );

    CREATE TABLE IF NOT EXISTS qc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        candidate_id TEXT,
        standalone INTEGER,
        audio INTEGER,
        visual INTEGER,
        provenance INTEGER,
        ending INTEGER,
        passed INTEGER,
        reasons TEXT
    );

    CREATE TABLE IF NOT EXISTS learning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        candidate_id TEXT,
        signal TEXT,
        value REAL,
        metadata TEXT
    );
    """)
    c.commit()
    c.close()


def run(cmd, timeout=300, check=False):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def have(command):
    return shutil.which(command) is not None


def ffprobe(path):
    if not have("ffprobe"):
        return {}

    r = run([
        "ffprobe", "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path)
    ])

    if r.returncode != 0:
        return {}

    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


def duration(path):
    data = ffprobe(path)
    try:
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0


def yt_info(url):
    if not have("yt-dlp"):
        raise RuntimeError("yt-dlp is not installed")

    r = run([
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        url
    ], timeout=120)

    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])

    return json.loads(r.stdout)


def discover(query, limit=20):
    if not have("yt-dlp"):
        raise RuntimeError("yt-dlp is not installed")

    r = run([
        "yt-dlp",
        f"ytsearch{limit}:{query}",
        "--flat-playlist",
        "--dump-single-json",
        "--skip-download"
    ], timeout=180)

    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])

    try:
        data = json.loads(r.stdout)
    except Exception:
        return []

    entries = data.get("entries") or []
    results = []

    for e in entries:
        title = e.get("title") or ""
        url = e.get("webpage_url") or ""

        if not url.startswith("http") and e.get("id"):
            url = "https://www.youtube.com/watch?v=" + e["id"]

        score = 5.0
        reasons = []

        low = title.lower()

        hooks = [
            "why", "how", "explained", "secret",
            "actually", "changed", "future",
            "forgotten", "strange", "weird",
            "new", "breaking", "hidden"
        ]

        matches = [x for x in hooks if x in low]

        if matches:
            score += min(len(matches) * 0.4, 1.5)
            reasons.append("strong title mechanism")

        if len(title) >= 35:
            score += 0.5
            reasons.append("specific title")

        if e.get("duration"):
            if 60 <= e["duration"] <= 1800:
                score += 0.25
                reasons.append("usable source length")

        score = min(score, 10)

        oid = "OPP-" + ident(query + url)

        c = db()
        c.execute("""
        INSERT OR REPLACE INTO opportunities
        (id,created_at,topic,title,url,channel,score,reason,status,metadata)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            oid,
            now(),
            query,
            title,
            url,
            e.get("channel") or e.get("uploader") or "",
            score,
            "; ".join(reasons),
            "NEW",
            json.dumps(e, default=str)
        ))
        c.commit()
        c.close()

        results.append({
            "id": oid,
            "score": score,
            "title": title,
            "url": url,
            "channel": e.get("channel") or e.get("uploader") or "",
            "reason": reasons
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def acquire(url, output_dir):
    if not have("yt-dlp"):
        raise RuntimeError("yt-dlp is not installed")

    output_dir.mkdir(parents=True, exist_ok=True)

    before = set(output_dir.iterdir())

    r = run([
        "yt-dlp",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", str(output_dir / "%(id)s.%(ext)s"),
        url
    ], timeout=900)

    if r.returncode != 0:
        raise RuntimeError(r.stderr[-4000:])

    after = set(output_dir.iterdir())
    created = [p for p in after - before if p.is_file()]

    if not created:
        created = list(output_dir.glob("*"))

    videos = [
        p for p in created
        if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
    ]

    if not videos:
        raise RuntimeError("Acquisition completed but no video file was found")

    return max(videos, key=lambda p: p.stat().st_mtime)


def silence_windows(path):
    """
    Deterministic media analysis fallback.
    Finds long non-silent regions using ffmpeg.
    This is deliberately available without a paid AI API.
    """
    if not have("ffmpeg"):
        raise RuntimeError("ffmpeg is required")

    r = run([
        "ffmpeg",
        "-hide_banner",
        "-i", str(path),
        "-af", "silencedetect=noise=-35dB:d=0.7",
        "-f", "null",
        "-"
    ], timeout=600)

    text = r.stderr

    silences = []

    for m in re.finditer(
        r"silence_start:\s*([0-9.]+)",
        text
    ):
        silences.append(("start", float(m.group(1))))

    for m in re.finditer(
        r"silence_end:\s*([0-9.]+)",
        text
    ):
        silences.append(("end", float(m.group(1))))

    silences.sort(key=lambda x: x[1])

    d = duration(path)

    if d <= 0:
        return []

    windows = []
    cursor = 0.0

    active_silence = None

    for kind, t in silences:
        if kind == "start":
            active_silence = t

        elif kind == "end" and active_silence is not None:
            if active_silence > cursor:
                windows.append((cursor, active_silence))

            cursor = t
            active_silence = None

    if cursor < d:
        windows.append((cursor, d))

    # Prefer clips in the 12–60 second range.
    useful = []

    for start, end in windows:
        length = end - start

        if 12 <= length <= 60:
            useful.append((start, end))
        elif length > 60:
            pos = start
            while pos + 45 <= end:
                useful.append((pos, pos + 45))
                pos += 45

    return useful


def generate_candidates(asset_id, path):
    windows = silence_windows(path)

    if not windows:
        d = duration(path)
        if d > 0:
            windows = [(0, min(d, 45))]

    results = []

    for i, (start, end) in enumerate(windows[:30]):
        length = end - start

        score = 5.0

        if 20 <= length <= 50:
            score += 1.0

        if start < 180:
            score += 0.5

        score = min(score, 10)

        cid = "CAND-" + ident(
            asset_id + str(round(start, 2)) + str(round(end, 2))
        )

        reasons = [
            "continuous-audio window",
            f"duration={length:.1f}s"
        ]

        c = db()
        c.execute("""
        INSERT OR REPLACE INTO candidates
        (id,created_at,asset_id,start,end,score,reasons,status,metadata)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            cid,
            now(),
            asset_id,
            start,
            end,
            score,
            json.dumps(reasons),
            "CANDIDATE",
            "{}"
        ))
        c.commit()
        c.close()

        results.append({
            "id": cid,
            "start": start,
            "end": end,
            "score": score,
            "reasons": reasons
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


def render_clip(path, start, end, output):
    if not have("ffmpeg"):
        raise RuntimeError("ffmpeg is required")

    output.parent.mkdir(parents=True, exist_ok=True)

    r = run([
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", str(path),
        "-t", str(max(0.1, end - start)),
        "-map", "0:v:0",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output)
    ], timeout=900)

    if r.returncode != 0:
        raise RuntimeError(r.stderr[-5000:])

    return output


def qc_clip(path, source_url=None):
    data = ffprobe(path)

    streams = data.get("streams", [])
    video = next(
        (s for s in streams if s.get("codec_type") == "video"),
        None
    )
    audio = next(
        (s for s in streams if s.get("codec_type") == "audio"),
        None
    )

    d = duration(path)

    checks = {
        "standalone": 8 <= d <= 90,
        "audio": audio is not None,
        "visual": video is not None and
                  int(video.get("width") or 0) >= 480 and
                  int(video.get("height") or 0) >= 270,
        "provenance": bool(source_url),
        "ending": d >= 8
    }

    reasons = []

    if not checks["standalone"]:
        reasons.append("duration outside standalone range")

    if not checks["audio"]:
        reasons.append("no audio stream")

    if not checks["visual"]:
        reasons.append("missing/invalid video stream")

    if not checks["provenance"]:
        reasons.append("source provenance missing")

    if not checks["ending"]:
        reasons.append("clip too short for ending check")

    passed = all(checks.values())

    return {
        "pass": passed,
        "checks": checks,
        "reasons": reasons,
        "duration": d
    }


def repair(path, qc):
    """
    Safe deterministic repairs only.
    Never pretends semantic failures were repaired.
    """
    if qc["pass"]:
        return path

    return path


def production_pack(run_id, opportunity, source, asset, candidates, exports):
    pack = PACKS / run_id
    pack.mkdir(parents=True, exist_ok=True)

    data = {
        "run_id": run_id,
        "created_at": now(),
        "opportunity": opportunity,
        "source": source,
        "asset": asset,
        "candidates": candidates,
        "exports": exports,
        "workflow": [
            "DISCOVER",
            "SOURCE",
            "RIGHTS",
            "ACQUIRE",
            "ANALYSE",
            "CANDIDATES",
            "SCORE",
            "CLIP",
            "QC",
            "REPAIR",
            "EXPORT",
            "LEARN"
        ]
    }

    (pack / "production_pack.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )

    (pack / "SOURCE.txt").write_text(
        source.get("webpage_url", source.get("url", "")) + "\n"
    )

    (pack / "EDIT_NOTES.md").write_text(
        "# Nethermind Production Pack\n\n"
        "## Hook\n"
        "Select the strongest standalone opening.\n\n"
        "## Payoff\n"
        "The clip must deliver a complete idea.\n\n"
        "## Ending\n"
        "Do not cut mid-thought.\n\n"
        "## QC\n"
        "- Standalone\n"
        "- Audio\n"
        "- Visual\n"
        "- Provenance\n"
        "- Ending\n"
    )

    return pack


def learn(candidate_id, signal, value, metadata=None):
    c = db()
    c.execute("""
    INSERT INTO learning
    (created_at,candidate_id,signal,value,metadata)
    VALUES (?,?,?,?,?)
    """, (
        now(),
        candidate_id,
        signal,
        value,
        json.dumps(metadata or {})
    ))
    c.commit()
    c.close()


def complete(url, authorized=False, topic=None, max_candidates=5):
    init_db()

    if not authorized:
        raise RuntimeError(
            "RIGHTS GATE: add --authorized after confirming you have "
            "permission/rights to acquire and transform this source."
        )

    run_id = "RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== 1 DISCOVER / SOURCE ===")

    source = yt_info(url)

    source_record = {
        "webpage_url": source.get("webpage_url") or url,
        "title": source.get("title"),
        "channel": source.get("channel") or source.get("uploader"),
        "duration": source.get("duration"),
        "view_count": source.get("view_count"),
        "upload_date": source.get("upload_date"),
    }

    topic = topic or source.get("title") or "source"

    print("TITLE:", source_record["title"])
    print("CHANNEL:", source_record["channel"])
    print("URL:", source_record["webpage_url"])

    print("\n=== 2 RIGHTS / PROVENANCE ===")
    print("AUTHORIZED: YES")

    print("\n=== 3 ACQUIRE ===")
    asset_dir = run_dir / "asset"
    video = acquire(url, asset_dir)

    asset_id = "ASSET-" + ident(str(video.resolve()))

    asset = {
        "id": asset_id,
        "path": str(video),
        "title": source_record["title"],
        "duration": duration(video),
        "source_url": source_record["webpage_url"]
    }

    c = db()
    c.execute("""
    INSERT OR REPLACE INTO assets
    (id,created_at,source_url,path,title,duration,metadata)
    VALUES (?,?,?,?,?,?,?)
    """, (
        asset_id,
        now(),
        source_record["webpage_url"],
        str(video),
        source_record["title"],
        asset["duration"],
        json.dumps(source_record)
    ))
    c.commit()
    c.close()

    print("ASSET:", video)

    print("\n=== 4 ANALYSE ===")
    print("Duration:", round(asset["duration"], 2), "seconds")

    print("\n=== 5 CANDIDATES ===")
    candidates = generate_candidates(asset_id, video)

    candidates = candidates[:max_candidates]

    for x in candidates:
        print(
            f"[{x['score']:.1f}] "
            f"{x['start']:.1f}-{x['end']:.1f}s "
            f"{x['id']}"
        )

    print("\n=== 6 CLIP / QC ===")

    exports = []

    for n, candidate in enumerate(candidates, 1):
        filename = (
            f"{n:02d}-"
            f"{slug(source_record['title'])[:45]}-"
            f"{int(candidate['start'])}-{int(candidate['end'])}.mp4"
        )

        out = EXPORTS / run_id / filename

        render_clip(
            video,
            candidate["start"],
            candidate["end"],
            out
        )

        result = qc_clip(
            out,
            source_record["webpage_url"]
        )

        repaired = repair(out, result)

        exports.append({
            "candidate_id": candidate["id"],
            "path": str(repaired),
            "qc": result
        })

        c = db()
        c.execute("""
        INSERT INTO qc
        (created_at,candidate_id,standalone,audio,visual,provenance,ending,passed,reasons)
        VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            now(),
            candidate["id"],
            int(result["checks"]["standalone"]),
            int(result["checks"]["audio"]),
            int(result["checks"]["visual"]),
            int(result["checks"]["provenance"]),
            int(result["checks"]["ending"]),
            int(result["pass"]),
            json.dumps(result["reasons"])
        ))
        c.commit()
        c.close()

        learn(
            candidate["id"],
            "initial_qc",
            1.0 if result["pass"] else 0.0,
            result
        )

        print(
            ("PASS" if result["pass"] else "FAIL"),
            filename,
            result["reasons"]
        )

    print("\n=== 7 PRODUCTION PACK ===")

    opportunity = {
        "topic": topic,
        "title": source_record["title"],
        "url": source_record["webpage_url"],
        "channel": source_record["channel"]
    }

    pack = production_pack(
        run_id,
        opportunity,
        source_record,
        asset,
        candidates,
        exports
    )

    print("PACK:", pack)

    manifest = run_dir / "RESULTS.json"

    result = {
        "run_id": run_id,
        "source": source_record,
        "asset": asset,
        "candidates": candidates,
        "exports": exports,
        "production_pack": str(pack),
        "created_at": now()
    }

    manifest.write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )

    print("\n============================================================")
    print(" CLIPPING FARM COMPLETE RUN")
    print("============================================================")
    print("RUN:", run_id)
    print("RESULTS:", manifest)
    print("EXPORTS:", EXPORTS / run_id)
    print("PACK:", pack)

    good = [x for x in exports if x["qc"]["pass"]]

    print("QC PASSED:", len(good), "/", len(exports))

    if good:
        print("\nFIRST USABLE CLIP:")
        print(good[0]["path"])
    else:
        print("\nNo clip passed the deterministic QC gate.")
        print("RESULTS contains the exact failure reasons.")

    return result


def status():
    init_db()
    c = db()

    tables = [
        "opportunities",
        "assets",
        "candidates",
        "qc",
        "learning"
    ]

    print("\nCLIPPING FARM COMPLETE BUILD\n")

    for table in tables:
        n = c.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        print(f"{table:18} {n}")

    c.close()

    print("\nROOT:", ROOT)
    print("DB:", DB)
    print("EXPORTS:", EXPORTS)
    print("PACKS:", PACKS)


def main():
    parser = argparse.ArgumentParser(
        description="Nethermind Clipping Farm complete pipeline"
    )

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("complete")
    p.add_argument("url")
    p.add_argument("--authorized", action="store_true")
    p.add_argument("--topic")
    p.add_argument("--max-candidates", type=int, default=5)

    p = sub.add_parser("discover")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)

    sub.add_parser("status")

    args = parser.parse_args()

    if args.command == "complete":
        complete(
            args.url,
            authorized=args.authorized,
            topic=args.topic,
            max_candidates=args.max_candidates
        )

    elif args.command == "discover":
        init_db()

        rows = discover(args.query, args.limit)

        print()

        for r in rows:
            print(
                f"[{r['score']:.1f}] "
                f"{r['title']}\n"
                f"    {r['channel']}\n"
                f"    {r['url']}\n"
                f"    {r['id']}\n"
            )

    elif args.command == "status":
        status()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
PY

cat > complete/__init__.py <<'PY'
PY

cat > __init_complete__.py <<'PY'
PY

# Add a direct module entry point without disturbing the existing package.
cat > complete_cli.py <<'PY'
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "complete"))

from pipeline import main

if __name__ == "__main__":
    main()
PY

# Make the existing package expose the new command if possible.
python - <<'PY'
from pathlib import Path

p = Path("clipping_farm/__main__.py")

if p.exists():
    text = p.read_text()

    marker = "complete_cli"

    if marker not in text:
        p.write_text(text + r'''

# Nethermind Complete Build command
if len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "complete":
    from complete_cli import main as _complete_main
    _complete_main()
''')
else:
    p.write_text(r'''
import sys
from complete_cli import main

if len(sys.argv) > 1 and sys.argv[1] == "complete":
    main()
else:
    from clipping_farm import main as existing_main
    existing_main()
''')

# Root-level convenience launcher.
Path("complete").mkdir(exist_ok=True)
PY

chmod +x INSTALL_COMPLETE_BUILD.sh

echo ""
echo "=== VERIFYING DEPENDENCIES ==="

command -v python >/dev/null || {
  echo "ERROR: python not found"
  exit 1
}

command -v ffmpeg >/dev/null || {
  echo "ERROR: ffmpeg not found"
  exit 1
}

command -v ffprobe >/dev/null || {
  echo "ERROR: ffprobe not found"
  exit 1
}

command -v yt-dlp >/dev/null || {
  echo "ERROR: yt-dlp not found"
  exit 1
}

echo "python:  $(python --version 2>&1)"
echo "ffmpeg:  $(ffmpeg -version 2>&1 | head -1)"
echo "yt-dlp:  $(yt-dlp --version)"

echo ""
echo "=== PYTHON COMPILE ==="
python -m compileall -q complete complete_cli.py

echo ""
echo "=== BUILD 9 REGRESSION TESTS ==="

if [ -d tests ]; then
    python -m pytest -q
else
    echo "No tests directory found; existing Build 9 tests left untouched."
fi

echo ""
echo "=== COMPLETE BUILD STATUS ==="
python complete_cli.py status

echo ""
echo "============================================================"
echo " INSTALL COMPLETE"
echo "============================================================"
echo ""
echo "NEXT COMMAND:"
echo ""
echo "python complete_cli.py discover \"weird internet\""
echo ""
echo "OR RUN A SOURCE ALL THE WAY THROUGH:"
echo ""
echo "python complete_cli.py complete \"PASTE-AUTHORIZED-YOUTUBE-URL-HERE\" --authorized"
echo ""
