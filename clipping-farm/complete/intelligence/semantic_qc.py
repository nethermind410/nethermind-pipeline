"""
Semantic QC v1
--------------

Transcript-backed semantic quality gate for rendered candidates.

This does NOT rewrite dialogue or invent context.

It evaluates:
- standalone opening
- JEV score
- context dependence
- minimum useful duration
- ending completeness
- semantic risks

Verdicts:
    SEMANTIC_PASS
    SEMANTIC_REVIEW
    SEMANTIC_REJECT
"""

from __future__ import annotations

from typing import Any

from complete.intelligence.context_repair import looks_context_dependent


def _text(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("text", "")).strip()
    return str(getattr(candidate, "text", "")).strip()


def semantic_qc(candidate: dict) -> dict:
    text = _text(candidate)

    start = float(candidate.get("start", 0) or 0)
    end = float(candidate.get("end", start) or start)
    duration = max(0.0, end - start)

    jev_score = float(
        candidate.get(
            "jev_score",
            candidate.get("score", 0),
        ) or 0
    )

    jev_verdict = candidate.get(
        "jev_verdict",
        candidate.get("verdict", ""),
    )

    risks = list(
        candidate.get(
            "jev_risks",
            candidate.get("risks", []),
        ) or []
    )

    checks = {
        "has_text": bool(text),
        "useful_duration": 8.0 <= duration <= 90.0,
        "standalone_opening": not looks_context_dependent(text),
        "jev_quality": jev_score >= 7.5,
        "no_trailing_fragment": "trailing_fragment" not in risks,
        "no_context_risk": "needs_context" not in risks,
    }

    reasons = []

    if not checks["has_text"]:
        reasons.append("missing transcript text")

    if not checks["useful_duration"]:
        reasons.append("duration outside semantic range")

    if not checks["standalone_opening"]:
        reasons.append("opening appears context-dependent")

    if not checks["jev_quality"]:
        reasons.append(f"JEV score below review threshold: {jev_score:.2f}")

    if not checks["no_trailing_fragment"]:
        reasons.append("transcript appears to end mid-thought")

    if not checks["no_context_risk"]:
        reasons.append("JEV identified context dependency")

    # Strong rejection conditions.
    if not checks["has_text"] or not checks["useful_duration"]:
        verdict = "SEMANTIC_REJECT"

    # Anything with explicit context problems remains reviewable,
    # because timestamp repair may still rescue it.
    elif (
        not checks["standalone_opening"]
        or not checks["no_trailing_fragment"]
        or not checks["no_context_risk"]
    ):
        verdict = "SEMANTIC_REVIEW"

    # High-quality candidates can pass directly.
    elif (
        checks["jev_quality"]
        and checks["standalone_opening"]
        and checks["no_trailing_fragment"]
        and checks["no_context_risk"]
    ):
        verdict = "SEMANTIC_PASS"

    else:
        verdict = "SEMANTIC_REVIEW"

    return {
        "verdict": verdict,
        "pass": verdict == "SEMANTIC_PASS",
        "checks": checks,
        "reasons": reasons,
        "jev_score": jev_score,
        "jev_verdict": jev_verdict,
        "duration": duration,
    }
