from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from hashlib import sha1


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "transcripts"
RUNS = ROOT / "intelligence_runs"


def _run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(
            "COMMAND FAILED\n\n"
            + " ".join(map(str, cmd))
            + "\n\n"
            + p.stderr[-6000:]
        )
    return p.stdout


def media_duration(path: str) -> float:
    out = _run([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ])
    return float(out.strip())


def transcribe(path: str, model: str = "mlx-community/whisper-large-v3-turbo") -> dict:
    """
    Local Apple-Silicon transcription.

    The model is downloaded by mlx-whisper on first use and then cached
    locally by Hugging Face.
    """
    import mlx_whisper

    source = Path(path)
    digest = sha1(str(source.resolve()).encode()).hexdigest()[:12]
    output = TRANSCRIPTS / f"{source.stem}-{digest}.json"

    if output.exists():
        return json.loads(output.read_text())

    result = mlx_whisper.transcribe(
        str(source),
        path_or_hf_repo=model,
        word_timestamps=True,
        verbose=False,
    )

    payload = {
        "source": str(source.resolve()),
        "model": model,
        "language": result.get("language"),
        "text": result.get("text", "").strip(),
        "segments": result.get("segments", []),
    }

    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return payload


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text.lower())


def _sentence_units(transcript: dict) -> list[dict]:
    """
    Convert Whisper segments into larger sentence-like units.
    We deliberately retain timestamps from Whisper rather than inventing
    fixed 45-second windows.
    """
    units = []

    for seg in transcript.get("segments", []):
        text = _clean(seg.get("text", ""))
        if not text:
            continue

        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))

        units.append({
            "start": start,
            "end": end,
            "text": text,
        })

    return units


HOOK_WORDS = {
    "why", "how", "actually", "secret", "weird", "strange",
    "forgotten", "hidden", "never", "nobody", "everyone",
    "changed", "because", "turns", "turned", "discovered",
    "real", "truth", "reason", "problem", "surprising",
    "originally", "apparently", "interesting",
}

PAYOFF_WORDS = {
    "because", "which", "means", "therefore", "so",
    "that's why", "the reason", "it turns out", "in other words",
    "essentially", "ultimately", "instead",
}

CONTEXT_WORDS = {
    "first", "then", "finally", "but", "however", "although",
    "for example", "specifically", "this", "that", "they",
}


def score_unit(text: str, duration: float) -> tuple[float, list[str]]:
    low = text.lower()
    words = _words(text)
    reasons = []
    score = 4.0

    hook_hits = sum(1 for w in HOOK_WORDS if re.search(r"\b" + re.escape(w) + r"\b", low))
    payoff_hits = sum(1 for phrase in PAYOFF_WORDS if phrase in low)
    context_hits = sum(1 for phrase in CONTEXT_WORDS if phrase in low)

    if hook_hits:
        score += min(2.0, hook_hits * 0.5)
        reasons.append(f"hook-language={hook_hits}")

    if payoff_hits:
        score += min(1.5, payoff_hits * 0.5)
        reasons.append(f"payoff-language={payoff_hits}")

    if context_hits:
        score += min(0.75, context_hits * 0.25)
        reasons.append(f"context-language={context_hits}")

    if 8 <= len(words) <= 90:
        score += 0.5
        reasons.append("natural-speaking-length")

    if 12 <= duration <= 60:
        score += 0.5
        reasons.append("short-form-compatible")

    if "?" in text:
        score += 0.4
        reasons.append("question-hook")

    if any(x in low for x in [
        "you might not know",
        "you probably don't know",
        "what happened",
        "the reason",
        "the weird thing",
        "what's interesting",
        "the interesting thing",
    ]):
        score += 0.8
        reasons.append("explicit-hook-pattern")

    return round(min(score, 10.0), 2), reasons



def _rhetorical_sentence_start(segment: dict[str, Any], fallback: float) -> float:
    """
    Return the word-level start of the final sentence in a transcript
    segment. This lets rhetorical candidates begin at the actual
    statement rather than at an earlier unrelated sentence.
    """
    words = segment.get("words") or []
    if not words:
        return fallback

    last_sentence_start = None

    for i, word in enumerate(words):
        token = str(word.get("word", "")).strip()

        if i == 0:
            last_sentence_start = float(word.get("start", fallback))

        if token.endswith((".", "!", "?")) and i + 1 < len(words):
            last_sentence_start = float(
                words[i + 1].get("start", fallback)
            )

    return (
        float(last_sentence_start)
        if last_sentence_start is not None
        else fallback
    )


def generate_rhetorical_candidates(
    segments: list[dict[str, Any]],
    max_candidates: int = 30,
) -> list[dict[str, Any]]:
    """
    Discover compact editorial moments built around a statement,
    question, and/or immediate answer/payoff.

    This is deliberately independent of JEV scoring. Its job is
    candidate discovery, not candidate selection.
    """
    candidates = []

    if not segments:
        return candidates

    for i, seg in enumerate(segments):
        text = str(seg.get("text", "")).strip()
        if not text or "?" not in text:
            continue

        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))

        # Pull the immediate transcript neighbourhood so a rhetorical
        # moment can span segment boundaries.
        #
        # If this segment contains the question, include the immediately
        # preceding transcript segment as setup. This preserves the
        # complete editorial statement -> question -> payoff unit.
        parts = [text]
        window_start = start
        window_end = end

        if i > 0:
            prev = segments[i - 1]
            prev_start = float(prev.get("start", 0))
            prev_end = float(prev.get("end", prev_start))

            if start - prev_end <= 4.0:
                prev_text = str(prev.get("text", "")).strip()
                if prev_text:
                    # If the previous segment contains multiple sentences,
                    # keep only the final sentence as rhetorical setup.
                    # Use Whisper word timestamps for the exact media boundary.
                    window_start = _rhetorical_sentence_start(
                        prev,
                        prev_start,
                    )

                    prev_words = prev.get("words") or []

                    if prev_words:
                        start_index = 0

                        for k, word in enumerate(prev_words):
                            word_start = float(
                                word.get("start", prev_start)
                            )

                            if word_start >= window_start - 0.01:
                                start_index = k
                                break

                        trimmed_words = prev_words[start_index:]
                        prev_text = " ".join(
                            str(w.get("word", "")).strip()
                            for w in trimmed_words
                            if str(w.get("word", "")).strip()
                        )

                    parts.insert(0, prev_text)

        for j in range(i + 1, min(len(segments), i + 4)):
            nxt = segments[j]
            nxt_start = float(nxt.get("start", 0))
            nxt_end = float(nxt.get("end", nxt_start))

            # Speech/transcript segmentation can leave a short gap
            # between a rhetorical question and its spoken payoff.
            # Allow up to 4 seconds so question -> answer moments
            # remain a single editorial candidate.
            if nxt_start - window_end > 4.0:
                break

            parts.append(str(nxt.get("text", "")).strip())
            window_end = nxt_end

            joined = " ".join(x for x in parts if x)

            if len(joined.split()) > 75 or window_end - window_start > 35:
                break

            # Once we have a question followed by a compact answer,
            # this is exactly the kind of editorial unit we want.
            qpos = joined.find("?")
            if qpos >= 0:
                remainder = joined[qpos + 1:].strip()

                if remainder:
                    answer_words = remainder.split()

                    # Immediate rhetorical payoff.
                    if len(answer_words) <= 18:
                        candidates.append({
                            "start": window_start,
                            "end": window_end,
                            "text": joined,
                            "source": "rhetorical",
                            "discovery_reason": "question_answer",
                        })
                        break

        # Also capture questions ending the current segment.
        if text.rstrip().endswith("?"):
            candidates.append({
                "start": start,
                "end": end,
                "text": text,
                "source": "rhetorical",
                "discovery_reason": "question",
            })

    # Deduplicate windows.
    unique = {}
    for c in candidates:
        key = (
            round(float(c["start"]), 2),
            round(float(c["end"]), 2),
        )
        unique[key] = c

    return list(unique.values())[:max_candidates]

def generate_candidates(transcript: dict, max_candidates: int = 20) -> list[dict]:
    """
    Generate variable-length candidate windows from transcript segments.

    This is intentionally deterministic and local. It does not pretend
    keyword scoring is semantic AI; the output is a candidate layer that
    can later be upgraded with a vision/LLM scorer.
    """
    units = _sentence_units(transcript)
    candidates = []

    for i, unit in enumerate(units):
        start = unit["start"]
        end = unit["end"]

        # Build a small context window around each promising sentence.
        for left, right in [(0, 0), (1, 1), (1, 2)]:
            lo = max(0, i - left)
            hi = min(len(units) - 1, i + right)

            text = _clean(" ".join(x["text"] for x in units[lo:hi + 1]))
            if not text:
                continue

            s = units[lo]["start"]
            e = units[hi]["end"]
            duration = e - s

            if duration < 8 or duration > 75:
                continue

            score, reasons = score_unit(text, duration)

            candidates.append({
                "start": round(s, 3),
                "end": round(e, 3),
                "duration": round(duration, 3),
                "score": score,
                "text": text,
                "reasons": reasons,
            })

    # Deduplicate overlapping candidates.
    candidates.sort(key=lambda x: (-x["score"], x["start"]))
    selected = []

    for candidate in candidates:
        overlap = False

        for existing in selected:
            a = max(candidate["start"], existing["start"])
            b = min(candidate["end"], existing["end"])
            intersection = max(0, b - a)

            shortest = min(
                candidate["duration"],
                existing["duration"],
            )

            if shortest and intersection / shortest > 0.65:
                overlap = True
                break

        if not overlap:
            candidate["id"] = (
                "INT-"
                + sha1(
                    f'{candidate["start"]}:{candidate["end"]}:{candidate["text"]}'.encode()
                ).hexdigest()[:14]
            )
            selected.append(candidate)

        if len(selected) >= max_candidates:
            break

    return selected


def analyse(path: str, model: str = "mlx-community/whisper-large-v3-turbo",
            max_candidates: int = 20) -> dict:

    transcript = transcribe(path, model=model)
    candidates = generate_candidates(
        transcript,
        max_candidates=max_candidates,
    )

    payload = {
        "source": str(Path(path).resolve()),
        "model": model,
        "duration": media_duration(path),
        "transcript": transcript,
        "candidates": candidates,
    }

    digest = sha1(str(Path(path).resolve()).encode()).hexdigest()[:12]
    output = RUNS / f"INT-{digest}.json"
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )

    return payload
