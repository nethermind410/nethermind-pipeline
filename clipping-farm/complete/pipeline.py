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
from complete.intelligence.semantic_qc import semantic_qc


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
        "--remote-components",
        "ejs:github",
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


def generate_candidates(asset_id, path, max_candidates=5):
    """
    Intelligent candidate generation.

    Build 17 pipeline order:

        TRANSCRIPT
          -> RAW CANDIDATES
          -> BOUNDARY OPTIMISER
          -> DEDUPLICATION
          -> OPENING INTEGRITY / JEV
          -> CONTEXT REPAIR
          -> FINAL RANK

    Crucially, raw JEV_REJECT candidates are NOT discarded before
    boundary optimisation. The optimiser gets first opportunity to
    find a better transcript-aligned window around the same idea.
    """
    try:
        from complete.intelligence.engine import (
            transcribe,
            generate_candidates as intelligence_generate_candidates,
            generate_rhetorical_candidates,
        )
        from complete.intelligence.jev import score_candidate
        from complete.intelligence.boundary_optimizer import optimize_candidate
        from complete.intelligence.context_repair import repair_candidate

        # ---------------------------------------------------------
        # 1. TRANSCRIPT
        # ---------------------------------------------------------
        transcript = transcribe(path)

        # Generate a larger raw pool than the final requested count.
        # Boundary optimisation may cause several candidates to
        # converge on the same window.
        raw_limit = max(20, max_candidates * 5)

        raw_candidates = intelligence_generate_candidates(
            transcript,
            max_candidates=raw_limit,
        )

        # ---------------------------------------------------------
        # Supplemental editorial discovery.
        #
        # The normal generator finds broad transcript moments.
        # Rhetorical discovery specifically surfaces compact
        # statement -> question -> answer/payoff structures.
        # These then enter the SAME downstream optimisation,
        # JEV scoring and context-repair pipeline.
        # ---------------------------------------------------------
        rhetorical_candidates = generate_rhetorical_candidates(
            transcript.get("segments", []),
            max_candidates=30,
        )

        raw_candidates.extend(rhetorical_candidates)

        print(
            f"[INTELLIGENCE] raw candidates: {len(raw_candidates)}"
        )
        print(
            f"[INTELLIGENCE] rhetorical candidates: "
            f"{len(rhetorical_candidates)}"
        )

        # ---------------------------------------------------------
        # 2. BOUNDARY OPTIMISATION
        # ---------------------------------------------------------
        optimised = []

        for candidate in raw_candidates:
            try:
                result = optimize_candidate(
                    candidate,
                    transcript.get("segments", []),
                    score_candidate,
                )

                # Optimiser may return either the candidate itself
                # or a result containing an optimised candidate.
                if isinstance(result, dict):
                    optimised_candidate = result.get(
                        "candidate",
                        result,
                    )
                else:
                    optimised_candidate = candidate

                if not isinstance(optimised_candidate, dict):
                    optimised_candidate = candidate

                merged = dict(candidate)
                merged.update(optimised_candidate)

                # Preserve explicit optimisation metadata.
                if isinstance(result, dict):
                    if "boundary_optimization" in result:
                        merged["boundary_optimization"] = result[
                            "boundary_optimization"
                        ]

                optimised.append(merged)

            except Exception as exc:
                print(
                    "[BOUNDARY] candidate fallback:",
                    type(exc).__name__,
                    str(exc),
                )
                optimised.append(candidate)

        print(
            f"[BOUNDARY] optimised candidates: {len(optimised)}"
        )

        # ---------------------------------------------------------
        # 3. DEDUPLICATE AFTER OPTIMISATION
        # ---------------------------------------------------------
        # Several raw candidates can legitimately converge on the
        # exact same transcript window. Keep only one.
        unique = []
        seen = set()

        for candidate in optimised:
            start = round(
                float(candidate.get("start", 0)),
                2,
            )
            end = round(
                float(candidate.get("end", 0)),
                2,
            )

            key = (start, end)

            if key in seen:
                continue

            seen.add(key)

            candidate["start"] = start
            candidate["end"] = end

            unique.append(candidate)

        print(
            f"[BOUNDARY] unique windows: {len(unique)}"
        )

        # ---------------------------------------------------------
        # 4. JEV SCORING
        # ---------------------------------------------------------
        scored = []

        for candidate in unique:
            text_value = str(candidate.get("text", "")).strip()
            start = float(candidate.get("start", 0))
            end = float(candidate.get("end", start + 8))

            if not text_value:
                continue

            result = score_candidate(
                text_value,
                start,
                end,
            )

            item = dict(candidate)

            # JEV is the authoritative score from this point onward.
            item["jev_score"] = result["jev_score"]
            item["jev_verdict"] = result.get(
                "jev_verdict",
                result.get("verdict", "JEV_REJECT"),
            )
            item["jev_metrics"] = result.get(
                "jev_metrics",
                result.get("metrics", {}),
            )
            item["jev_risks"] = result.get(
                "jev_risks",
                result.get("risks", []),
            )

            # Keep compatibility with older pipeline consumers.
            item["score"] = result["jev_score"]

            scored.append(item)

        print(
            f"[JEV] scored candidates: {len(scored)}"
        )

        # ---------------------------------------------------------
        # 5. CONTEXT REPAIR
        # ---------------------------------------------------------
        repaired = []

        for candidate in scored:
            try:
                repaired_candidate = repair_candidate(
                    candidate,
                    transcript.get("segments", []),
                    score_candidate,
                )

                if not isinstance(repaired_candidate, dict):
                    repaired_candidate = candidate

                item = dict(candidate)
                item.update(repaired_candidate)

                # Preserve explicit repair metadata.
                if "context_repair" in repaired_candidate:
                    item["context_repair"] = repaired_candidate[
                        "context_repair"
                    ]

                # -------------------------------------------------
                # Re-score the repaired window.
                #
                # This is important: context repair may have moved
                # the timestamps/text, so the old JEV score must not
                # survive as the authoritative score.
                # -------------------------------------------------
                final_text = str(
                    item.get("text", "")
                ).strip()

                final_start = float(
                    item.get("start", 0)
                )

                final_end = float(
                    item.get(
                        "end",
                        final_start + 8,
                    )
                )

                if final_text:
                    final_score = score_candidate(
                        final_text,
                        final_start,
                        final_end,
                    )

                    item["jev_score"] = final_score["jev_score"]
                    item["jev_verdict"] = final_score.get(
                        "jev_verdict",
                        final_score.get(
                            "verdict",
                            "JEV_REJECT",
                        ),
                    )
                    item["jev_metrics"] = final_score.get(
                        "jev_metrics",
                        final_score.get(
                            "metrics",
                            {},
                        ),
                    )
                    item["jev_risks"] = final_score.get(
                        "jev_risks",
                        final_score.get(
                            "risks",
                            [],
                        ),
                    )

                    item["score"] = final_score["jev_score"]

                repaired.append(item)

            except Exception as exc:
                print(
                    "[CONTEXT] candidate fallback:",
                    type(exc).__name__,
                    str(exc),
                )
                repaired.append(candidate)

        print(
            f"[CONTEXT] repaired candidates: {len(repaired)}"
        )

        # ---------------------------------------------------------
        # 6. FINAL RANK
        # ---------------------------------------------------------
        repaired.sort(
            key=lambda x: x.get("jev_score", 0),
            reverse=True,
        )

        # ---------------------------------------------------------
        # 7. FINAL LIMIT
        # ---------------------------------------------------------
        # Preserve one strong rhetorical question/answer candidate when
        # available. This is editorial-format diversity, not score inflation:
        # the candidate keeps its genuine JEV score.
        rhetorical = [
            x for x in repaired
            if str(x.get("source", "")).lower() == "rhetorical"
            and str(x.get("discovery_reason", "")).lower() == "question_answer"
        ]

        final = []

        if rhetorical and max_candidates > 0:
            rhetorical.sort(
                key=lambda x: x.get("jev_score", 0),
                reverse=True,
            )
            final.append(rhetorical[0])

        for candidate in repaired:
            if len(final) >= max_candidates:
                break

            if final and candidate is final[0]:
                continue

            final.append(candidate)

        print(
            "[JEV] final candidates:",
            len(final),
        )

        for i, candidate in enumerate(final, 1):
            context = candidate.get(
                "context_repair",
                {},
            )

            print(
                f"  {i:02d} | "
                f"{candidate.get('start', 0):.2f}-"
                f"{candidate.get('end', 0):.2f}s | "
                f"JEV "
                f"{candidate.get('jev_score', 0):.2f} | "
                f"{candidate.get('jev_verdict', 'UNKNOWN')} | "
                f"CTX "
                f"{'REPAIRED' if context.get('applied') else 'UNCHANGED'}"
            )

        return final

    except Exception as exc:
        print(
            "[INTELLIGENCE] falling back to legacy candidate "
            "generation:",
            type(exc).__name__,
            str(exc),
        )

        return _generate_candidates_legacy(
            asset_id,
            path,
        )

def _generate_candidates_legacy(asset_id, path):
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

    for i, x in enumerate(candidates, 1):
        if not x.get("id"):
            x["id"] = (
                f"INT-{i:02d}-"
                f"{float(x.get('start', 0)):.2f}-"
                f"{float(x.get('end', 0)):.2f}"
            )

        print(
            f"[{x.get('score', x.get('jev_score', 0)):.1f}] "
            f"{x.get('start', 0):.1f}-"
            f"{x.get('end', 0):.1f}s "
            f"{x['id']}"
        )

    print("\n=== 6 CLIP / QC ===")

    exports = []

    # Load the cached transcript once for production-stage context repair.
    try:
        from complete.intelligence.engine import transcribe
        transcript = transcribe(video)
        segments = transcript.get("segments", [])
    except Exception as exc:
        print("TRANSCRIPT LOAD ERROR:", exc)
        segments = []

    for n, candidate in enumerate(candidates, 1):

        # ------------------------------------------------------------
        # CONTEXT REPAIR
        #
        # Candidate timestamps may be repaired using the transcript
        # before anything is rendered.
        #
        # No dialogue is invented or rewritten.
        # ------------------------------------------------------------
        original_candidate = dict(candidate)

        try:
            from complete.intelligence.context_repair import repair_candidate
            from complete.intelligence.jev import score_candidate

            candidate = repair_candidate(
                candidate,
                segments,
                score_candidate,
            )
        except Exception as exc:
            print("CONTEXT REPAIR ERROR:", exc)
            candidate = original_candidate

        if candidate.get("context_repair", {}).get("applied"):
            print(
                "CONTEXT REPAIR:",
                f"{candidate['context_repair']['original_start']:.2f}-"
                f"{candidate['context_repair']['original_end']:.2f}s",
                "->",
                f"{candidate['start']:.2f}-"
                f"{candidate['end']:.2f}s"
            )

        filename = (
            f"{n:02d}-"
            f"{slug(source_record['title'])[:45]}-"
            f"{int(candidate['start'])}-{int(candidate['end'])}.mp4"
        )

        out = EXPORTS / run_id / filename

        # ------------------------------------------------------------
        # RENDER
        # ------------------------------------------------------------
        render_clip(
            video,
            candidate["start"],
            candidate["end"],
            out
        )

        # ------------------------------------------------------------
        # MEDIA QC
        # ------------------------------------------------------------
        result = qc_clip(
            out,
            source_record["webpage_url"]
        )

        repaired_path = repair(out, result)

        # ------------------------------------------------------------
        # SEMANTIC QC
        # ------------------------------------------------------------
        semantic = semantic_qc(candidate)

        print(
            "MEDIA QC:",
            "PASS" if result["pass"] else "FAIL"
        )

        print(
            "SEMANTIC QC:",
            semantic["verdict"]
        )

        if semantic["reasons"]:
            print(
                "SEMANTIC REASONS:",
                "; ".join(semantic["reasons"])
            )

        # BOTH gates must pass before the clip is production-ready.
        production_ready = (
            result["pass"]
            and semantic["pass"]
        )

        exports.append({
            "candidate_id": candidate["id"],
            "original_start": original_candidate.get("start"),
            "original_end": original_candidate.get("end"),
            "start": candidate.get("start"),
            "end": candidate.get("end"),
            "path": str(repaired_path),
            "qc": result,
            "semantic_qc": semantic,
            "context_repair": candidate.get(
                "context_repair",
                {}
            ),
            "production_ready": production_ready
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
            (
                "PRODUCTION PASS"
                if production_ready
                else "PRODUCTION REVIEW"
            ),
            filename,
            (
                result["reasons"]
                + semantic["reasons"]
            )
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

    media_good = [
        x for x in exports
        if x.get("qc", {}).get("pass")
    ]

    semantic_good = [
        x for x in exports
        if x.get("semantic_qc", {}).get("pass")
    ]

    production_good = [
        x for x in exports
        if x.get("production_ready", False)
    ]

    print(
        "MEDIA QC PASSED:",
        len(media_good),
        "/",
        len(exports),
    )

    print(
        "SEMANTIC QC PASSED:",
        len(semantic_good),
        "/",
        len(exports),
    )

    print(
        "PRODUCTION PASSED:",
        len(production_good),
        "/",
        len(exports),
    )

    if production_good:
        print("\nFIRST USABLE CLIP:")
        print(production_good[0]["path"])
    elif media_good:
        print("\nMEDIA-QC-PASS CLIP AVAILABLE:")
        print(media_good[0]["path"])
        print("Semantic review remains required.")
    else:
        print("\nNo clip passed the deterministic media QC gate.")
        print("RESULTS contains the exact failure reasons.")

    return result



def complete_local(path, source_url=None, topic=None, max_candidates=5, run_id=None):
    """Run the complete 20.3 pipeline against an already-acquired local asset."""
    init_db()

    video = Path(path).resolve()
    if not video.exists():
        raise RuntimeError(f"local asset not found: {video}")

    run_id = run_id or ("RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== BUILD 20.3 / LOCAL ASSET ===")
    print("VIDEO:", video)

    source_record = {
        "webpage_url": source_url or "",
        "title": video.stem,
        "channel": None,
        "duration": duration(video),
    }

    asset_id = "ASSET-" + ident(str(video))
    asset = {
        "id": asset_id,
        "path": str(video),
        "title": source_record["title"],
        "duration": source_record["duration"],
        "source_url": source_url or "",
    }

    c=db()
    c.execute("""
    INSERT OR REPLACE INTO assets
    (id,created_at,source_url,path,title,duration,metadata)
    VALUES (?,?,?,?,?,?,?)
    """,(
        asset_id,
        now(),
        source_record["source_url"],
        str(video),
        source_record["title"],
        asset["duration"],
        json.dumps(source_record)
    ))
    c.commit()
    c.close()

    print("\n=== ANALYSE ===")
    print("Duration:", round(asset["duration"],2),"seconds")

    print("\n=== CANDIDATES ===")
    candidates=generate_candidates(asset_id,video,max_candidates=max_candidates)
    candidates=candidates[:max_candidates]

    print("Candidates:",len(candidates))

    # Continue through the existing 20.3 production/QC/export machinery.
    return _complete_from_asset(
        run_id=run_id,
        run_dir=run_dir,
        source=source_record,
        asset=asset,
        candidates=candidates
    )

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
