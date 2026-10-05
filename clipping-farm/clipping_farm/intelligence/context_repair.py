"""
Context Repair v2
-----------------

Transcript-backed timestamp repair.

The repair engine NEVER invents dialogue.

It only changes the candidate's start/end timestamps so the resulting
transcript window has a better chance of standing alone.

Strategy:
    1. Detect context-dependent openings.
    2. Search progressively earlier transcript windows.
    3. Also test modest forward expansion.
    4. Score every candidate.
    5. Prefer windows that remove context dependence.
    6. Accept only a materially better window.
"""

from __future__ import annotations

from typing import Any, Callable


LEADING_CONTEXT = {
    "however",
    "but",
    "and",
    "so",
    "because",
    "although",
    "though",
    "then",
    "also",
    "this",
    "that",
    "these",
    "those",
    "they",
    "it",
    "he",
    "she",
    "we",
    "given",
    "as",
    "which",
    "when",
    "while",
}

LEADING_PHRASES = (
    "however,",
    "but,",
    "and,",
    "so,",
    "because,",
    "given what",
    "as i mentioned",
    "as mentioned",
    "like i said",
    "as i said",
    "this is",
    "that is",
)


def looks_context_dependent(text: str) -> bool:
    text = " ".join(str(text or "").strip().split())

    if not text:
        return True

    lowered = text.lower()

    for phrase in LEADING_PHRASES:
        if lowered.startswith(phrase):
            return True

    first = lowered.split()[0].strip(".,!?;:\"'()[]{}")

    return first in LEADING_CONTEXT


def _segments_to_text(
    segments: list[dict[str, Any]],
    start: float,
    end: float,
) -> str:
    parts = []

    for segment in segments:
        seg_start = float(segment.get("start", 0) or 0)
        seg_end = float(segment.get("end", seg_start) or seg_start)

        if seg_end <= start:
            continue

        if seg_start >= end:
            break

        text = str(segment.get("text", "")).strip()

        if text:
            parts.append(text)

    return " ".join(parts).strip()


def _candidate_score(
    text: str,
    start: float,
    end: float,
    score_fn: Callable[[str, float, float], dict],
) -> dict:
    return score_fn(text, start, end)


def repair_candidate(
    candidate: dict,
    segments: list[dict[str, Any]],
    score_fn: Callable[[str, float, float], dict],
    max_duration: float = 60.0,
) -> dict:
    """
    Attempt transcript-backed timestamp repair.

    Returns the original candidate unchanged when no worthwhile repair
    is found.

    No text is generated or modified.
    """

    original = dict(candidate)

    original_start = float(original.get("start", 0) or 0)
    original_end = float(
        original.get("end", original_start) or original_start
    )
    original_text = str(original.get("text", "")).strip()

    original_score = _candidate_score(
        original_text,
        original_start,
        original_end,
        score_fn,
    )

    original_jev = float(
        original_score.get("jev_score", 0) or 0
    )

    if not looks_context_dependent(original_text):
        original["context_repair"] = {
            "attempted": False,
            "applied": False,
            "reason": "opening already appears context-independent",
        }
        return original

    candidates = []

    # Larger backward search is intentional.
    backward_offsets = (
        2.0,
        4.0,
        6.0,
        8.0,
        10.0,
        12.0,
        15.0,
        20.0,
        25.0,
        30.0,
    )

    forward_offsets = (
        0.0,
        2.0,
        4.0,
        6.0,
        8.0,
    )

    for back in backward_offsets:
        for forward in forward_offsets:
            new_start = max(0.0, original_start - back)
            new_end = original_end + forward

            if new_end - new_start > max_duration:
                continue

            text = _segments_to_text(
                segments,
                new_start,
                new_end,
            )

            if not text:
                continue

            scored = _candidate_score(
                text,
                new_start,
                new_end,
                score_fn,
            )

            jev = float(
                scored.get("jev_score", 0) or 0
            )

            context_free = not looks_context_dependent(text)

            candidates.append({
                "start": new_start,
                "end": new_end,
                "text": text,
                "score": scored,
                "jev": jev,
                "context_free": context_free,
            })

    if not candidates:
        original["context_repair"] = {
            "attempted": True,
            "applied": False,
            "reason": "no viable transcript windows found",
        }
        return original

    # Prefer windows that actually solve the problem.
    #
    # Among context-free windows, highest JEV wins.
    # Among context-dependent windows, highest JEV wins but they remain
    # REVIEW candidates.
    context_free = [
        x for x in candidates
        if x["context_free"]
    ]

    if context_free:
        best = max(
            context_free,
            key=lambda x: x["jev"],
        )
    else:
        best = max(
            candidates,
            key=lambda x: x["jev"],
        )

    best_jev = best["jev"]
    improvement = best_jev - original_jev

    # A context-free repair is valuable even if JEV improvement is small.
    # Otherwise require a meaningful score improvement.
    accept = (
        best["context_free"]
        and best["start"] < original_start
        and (
            improvement >= 0.15
            or best_jev >= original_jev
        )
    )

    if not accept:
        original["context_repair"] = {
            "attempted": True,
            "applied": False,
            "reason": "no sufficiently better standalone window found",
            "original_start": original_start,
            "original_end": original_end,
            "original_jev": round(original_jev, 3),
            "best_start": round(best["start"], 3),
            "best_end": round(best["end"], 3),
            "best_jev": round(best_jev, 3),
            "best_context_free": best["context_free"],
        }
        return original

    repaired = dict(original)

    repaired.update({
        "start": best["start"],
        "end": best["end"],
        "text": best["text"],
        "jev_score": best_jev,
        "jev_verdict": best["score"].get(
            "verdict",
            best["score"].get(
                "jev_verdict",
                original.get("jev_verdict", "JEV_REVIEW"),
            ),
        ),
        "jev_metrics": best["score"].get(
            "metrics",
            best["score"].get(
                "jev_metrics",
                original.get("jev_metrics", {}),
            ),
        ),
        "jev_risks": best["score"].get(
            "risks",
            best["score"].get(
                "jev_risks",
                original.get("jev_risks", []),
            ),
        ),
        "context_repair": {
            "attempted": True,
            "applied": True,
            "original_start": original_start,
            "original_end": original_end,
            "original_jev": round(original_jev, 3),
            "repaired_start": round(best["start"], 3),
            "repaired_end": round(best["end"], 3),
            "repaired_jev": round(best_jev, 3),
            "improvement": round(improvement, 3),
            "standalone_opening": True,
        },
    })

    return repaired
