from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


HOOK_WORDS = {
    "why", "how", "secret", "truth", "actually", "never", "wrong",
    "weird", "strange", "crazy", "unexpected", "but", "however",
    "problem", "mistake", "hidden", "nobody", "everyone", "really",
    "important", "surprising", "turns", "found", "discovered",
}

PAYOFF_WORDS = {
    "because", "means", "reason", "result", "therefore", "so",
    "explains", "explained", "reveals", "found", "discovered",
    "turns out", "difference", "cause", "caused", "solution",
}

TENSION_PHRASES = {
    "but", "however", "instead", "actually", "not convinced",
    "the problem", "the strange thing", "what i found",
    "what nobody", "you might think", "turns out",
}


def clamp(v: float, lo=0.0, hi=10.0) -> float:
    return max(lo, min(hi, v))


def words(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", text.lower())


def phrase_count(text: str, phrases) -> int:
    low = text.lower()
    return sum(1 for p in phrases if p in low)



def opening_integrity(text: str) -> dict[str, Any]:
    """
    Evaluate whether the beginning of a transcript window behaves
    like a standalone editorial opening.

    This is separate from hook scoring because a clip can contain
    excellent information while still starting halfway through
    an argument.
    """
    low = text.lower().strip()

    if not low:
        return {
            "score": 0.0,
            "verdict": "OPENING_REJECT",
            "reason": "empty opening",
        }

    hard_patterns = [
        r"^however\b",
        r"^but\b",
        r"^and\b",
        r"^so\b",
        r"^because\b",
        r"^then\b",
        r"^which\b",
        r"^that\b",
        r"^is what\b",
        r"^was what\b",
        r"^were what\b",
        r"^for yourself\b",
        r"^come back\b",
        r"^as i said\b",
        r"^as mentioned\b",
        r"^given what\b",
        r"^like i said\b",
    ]

    soft_patterns = [
        r"^now,?\s+of course\b",
        r"^i hope you can see\b",
        r"^this is\b",
        r"^that is\b",
        r"^this means\b",
        r"^that means\b",
    ]

    strong_patterns = [
        r"^why\b",
        r"^how\b",
        r"^what happens\b",
        r"^what if\b",
        r"^the reason\b",
        r"^the problem\b",
        r"^the strange thing\b",
        r"^some of the most\b",
        r"^nobody\b",
        r"^everyone\b",
    ]

    for pattern in hard_patterns:
        if re.search(pattern, low):
            return {
                "score": 3.5,
                "verdict": "OPENING_REVIEW",
                "reason": "opening appears to begin mid-thought",
            }

    for pattern in soft_patterns:
        if re.search(pattern, low):
            return {
                "score": 5.5,
                "verdict": "OPENING_REVIEW",
                "reason": "opening appears conversational or conclusion-dependent",
            }

    for pattern in strong_patterns:
        if re.search(pattern, low):
            return {
                "score": 9.0,
                "verdict": "OPENING_PASS",
                "reason": "opening has explicit hook structure",
            }

    # Transcript fragments often begin with a lowercase word.
    stripped = text.strip()
    if stripped and stripped[0].islower():
        return {
            "score": 4.0,
            "verdict": "OPENING_REVIEW",
            "reason": "opening begins with apparent sentence fragment",
        }

    return {
        "score": 7.0,
        "verdict": "OPENING_PASS",
        "reason": "opening appears grammatically self-contained",
    }


def detect_micro_payoff(text: str) -> bool:
    """
    Detect a compact question -> answer/payoff structure.

    Examples:
        "Why? It's culture."
        "Why? Tradition."
        "How? Technology."
        "What's the reason? Because..."
    """
    low = text.lower().strip()

    if not low or "?" not in low:
        return False

    for match in re.finditer(r"\?", low):
        remainder = low[match.end():].strip()

        if not remainder:
            continue

        # Only inspect the immediate response after the question.
        answer = re.split(r"[.!?]", remainder, maxsplit=1)[0].strip()

        if not answer:
            continue

        answer_words = words(answer)

        if not (1 <= len(answer_words) <= 18):
            continue

        explicit_starters = (
            "it's ",
            "it is ",
            "because ",
            "since ",
            "the reason ",
            "the answer ",
            "this is ",
            "that is ",
            "this means ",
            "that means ",
            "by ",
            "through ",
        )

        if answer.startswith(explicit_starters):
            return True

        # A very short declarative answer can itself be the payoff:
        # "Why? Culture."
        # "Why? Tradition."
        # "How? Technology."
        if len(answer_words) <= 6:
            return True

    return False


def detect_question_answer(text: str) -> bool:
    """
    Detect a compact question -> answer/payoff structure.

    Examples:
        "Why? It's culture."
        "Why does this happen? Because..."
        "What's the reason? The answer is..."
        "How? By..."
        "The reason? ..."
    """

    low = text.lower().strip()

    if not low:
        return False

    # Direct question followed by a short answer.
    direct_patterns = [
        r"\?\s+(?:it['’]s|it's)\s+",
        r"\?\s+(?:because|since|the reason is|the answer is)\b",
        r"\?\s+(?:this is|that is|this means|that means)\b",
        r"\?\s+(?:by|through)\s+",
    ]

    if any(re.search(pattern, low) for pattern in direct_patterns):
        return True

    # Question followed by a compact declarative payoff.
    # Keep this deliberately conservative so ordinary questions
    # do not receive the bonus.
    question_positions = [
        match.end()
        for match in re.finditer(r"\?", low)
    ]

    for position in question_positions:
        remainder = low[position:].strip()

        if not remainder:
            continue

        words_after = words(remainder)

        if 1 <= len(words_after) <= 18:
            payoff_starters = (
                "the ",
                "it's ",
                "it is ",
                "because ",
                "this ",
                "that ",
                "they ",
                "we ",
                "the answer ",
                "the reason ",
            )

            if remainder.startswith(payoff_starters):
                return True

    return False



def score_candidate(text: str, start: float, end: float) -> dict[str, Any]:
    low = text.lower()
    ws = words(text)
    n = len(ws)
    duration = max(0.1, end - start)

    hook_hits = sum(w in HOOK_WORDS for w in ws[:45])
    payoff_hits = sum(w in PAYOFF_WORDS for w in ws)
    tension_hits = phrase_count(text, TENSION_PHRASES)

    # Hook: disproportionately weighted toward the first ~8 seconds.
    first = " ".join(ws[:24])
    first_hits = sum(w in HOOK_WORDS for w in words(first))
    question = "?" in text
    question_answer = detect_question_answer(text)
    micro_payoff = detect_micro_payoff(text)

    opening = opening_integrity(text)

    hook = (
        4.5
        + min(3.0, first_hits * 0.8)
        + (1.0 if question else 0)
        + (0.5 if question_answer else 0)
    )
    if n < 8:
        hook -= 2.5

    # Opening integrity is deliberately separate from generic hook
    # scoring. A strong body must not hide a broken clip opening.
    if opening["verdict"] == "OPENING_REVIEW":
        hook -= 0.75
    if re.match(r"^(and|so|but|because|then|which|that)\b", low.strip()):
        hook -= 1.5
    hook = clamp(hook)

    payoff = clamp(
        4.0
        + min(3.5, payoff_hits * 0.65)
        + min(1.5, tension_hits * 0.5)
        + (2.5 if question_answer else 0)
        + (1.0 if micro_payoff else 0)
    )

    # Short-form sweet spot.
    if 12 <= duration <= 35:
        length = 9.5
    elif 8 <= duration <= 45:
        length = 8.5
    elif 45 < duration <= 60:
        length = 7.0
    elif duration < 8:
        length = 4.0
    else:
        length = 5.5

    standalone = 8.0

    # Penalise obvious references to missing context.
    context_penalty = 0
    context_flags = [
        "as i said", "as mentioned", "this video", "that video",
        "the previous", "earlier i", "like i said", "you saw",
        "as you can see", "in the last video",
    ]
    for p in context_flags:
        if p in low:
            context_penalty += 1.5

    if low.startswith(("he ", "she ", "they ", "it ")):
        context_penalty += 0.75

    standalone = clamp(standalone - context_penalty)

    specificity = 5.5
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?\b", text))
    properish = len(re.findall(r"\b[A-Z][a-z]{3,}\b", text))
    specificity += min(2.0, numbers * 0.7)
    specificity += min(1.5, properish * 0.15)
    specificity = clamp(specificity)

    curiosity = clamp(
        5.0
        + min(2.0, tension_hits * 0.7)
        + min(1.5, first_hits * 0.4)
        + (1.0 if question else 0)
        + (0.5 if question_answer else 0)
    )

    editability = 9.0
    if duration > 60:
        editability -= 2
    if duration < 8:
        editability -= 3

    # Speech density: extremely sparse windows tend to be poor clips.
    wpm = n / duration * 60
    if 100 <= wpm <= 190:
        speech = 9.0
    elif 80 <= wpm <= 220:
        speech = 7.5
    else:
        speech = 5.5

    risks = []

    if context_penalty >= 1.5:
        risks.append("needs_context")

    if re.search(r"\b(and|but|so|because|which|that)\s*$", low):
        risks.append("trailing_fragment")

    if low.startswith(("and ", "but ", "so ", "because ")):
        risks.append("weak_open")

    if n < 12:
        risks.append("too_short")

    if duration > 60:
        risks.append("long_window")

    if wpm < 80:
        risks.append("slow_speech")

    if wpm > 220:
        risks.append("dense_speech")

    # JEV-style weighted composite.
    score = (
        hook * 0.22 +
        payoff * 0.16 +
        standalone * 0.16 +
        curiosity * 0.14 +
        specificity * 0.10 +
        length * 0.10 +
        editability * 0.07 +
        speech * 0.05
    )

    if "needs_context" in risks:
        score -= 1.0
    if "weak_open" in risks:
        score -= 0.75
    if "trailing_fragment" in risks:
        score -= 0.5

    if opening["verdict"] == "OPENING_REVIEW":
        score -= 0.75
        risks.append("opening_integrity_review")

    score = clamp(score)

    if score >= 8.5:
        verdict = "JEV_PASS"
    elif score >= 7.5:
        verdict = "JEV_REVIEW"
    else:
        verdict = "JEV_REJECT"

    return {
        "jev_score": round(score, 2),
        "verdict": verdict,
        "duration": round(duration, 2),
        "metrics": {
            "hook": round(hook, 2),
                "opening_integrity": round(opening["score"], 2),
                "opening_verdict": opening["verdict"],
            "payoff": round(payoff, 2),
            "question_answer": question_answer,
                "micro_payoff": micro_payoff,
            "standalone": round(standalone, 2),
            "curiosity": round(curiosity, 2),
            "specificity": round(specificity, 2),
            "short_form_fit": round(length, 2),
            "editability": round(editability, 2),
            "speech": round(speech, 2),
        },
        "risks": risks,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_candidates(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        for key in ("candidates", "moments", "results"):
            value = data.get(key)
            if isinstance(value, list) and value:
                return value

        for value in data.values():
            found = find_candidates(value)
            if found:
                return found

    elif isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data):
            if any(
                ("start" in x or "start_time" in x) and
                ("end" in x or "end_time" in x)
                for x in data
            ):
                return data

        for value in data:
            found = find_candidates(value)
            if found:
                return found

    return []


def candidate_text(c: dict[str, Any]) -> str:
    for key in ("text", "transcript", "snippet", "quote", "content"):
        if c.get(key):
            return str(c[key])

    segments = c.get("segments")
    if isinstance(segments, list):
        return " ".join(
            str(s.get("text", ""))
            for s in segments
            if isinstance(s, dict)
        ).strip()

    return ""


def candidate_times(c: dict[str, Any]) -> tuple[float, float]:
    start = c.get("start", c.get("start_time", 0))
    end = c.get("end", c.get("end_time", 0))

    try:
        return float(start), float(end)
    except Exception:
        return 0.0, 0.0


def sort_candidates(analysis_file: str | Path, limit: int = 20) -> dict[str, Any]:
    path = Path(analysis_file)
    data = load_json(path)
    raw = find_candidates(data)

    scored = []

    for idx, c in enumerate(raw):
        text = candidate_text(c)
        start, end = candidate_times(c)

        if not text or end <= start:
            continue

        result = score_candidate(text, start, end)

        scored.append({
            "rank_source": idx,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": text.strip(),
            **result,
        })

    # Deduplicate heavily overlapping moments.
    scored.sort(key=lambda x: x["jev_score"], reverse=True)

    selected = []

    for c in scored:
        overlap = False

        for s in selected:
            inter = max(0.0, min(c["end"], s["end"]) - max(c["start"], s["start"]))
            shorter = min(c["end"] - c["start"], s["end"] - s["start"])

            if shorter > 0 and inter / shorter >= 0.65:
                overlap = True
                break

        if not overlap:
            selected.append(c)

        if len(selected) >= limit:
            break

    for rank, c in enumerate(selected, 1):
        c["jev_rank"] = rank

    return {
        "sorter": "JEV-style candidate sorter",
        "version": "1.0",
        "source_analysis": str(path),
        "candidate_count": len(scored),
        "selected_count": len(selected),
        "candidates": selected,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_file")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output")
    args = parser.parse_args()

    result = sort_candidates(args.analysis_file, args.limit)

    if args.output:
        out = Path(args.output)
    else:
        src = Path(args.analysis_file)
        out = src.with_name(src.stem + ".jev.json")

    out.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=== JEV SORT ===")
    print(f"Analysed candidates: {result['candidate_count']}")
    print(f"Selected:            {result['selected_count']}")
    print()

    for c in result["candidates"]:
        print(
            f"[{c['jev_score']:>4.2f}] "
            f"{c['start']:>7.1f}-{c['end']:<7.1f} "
            f"{c['verdict']:<10} "
            f"{c['text'][:110]}"
        )
        print(
            f"       hook={c['metrics']['hook']:.1f} "
            f"payoff={c['metrics']['payoff']:.1f} "
            f"standalone={c['metrics']['standalone']:.1f} "
            f"curiosity={c['metrics']['curiosity']:.1f} "
            f"fit={c['metrics']['short_form_fit']:.1f}"
        )

    print()
    print(f"JEV file: {out}")


if __name__ == "__main__":
    main()
