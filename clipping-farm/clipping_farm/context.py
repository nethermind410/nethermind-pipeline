"""Candidate context expansion and deterministic standalone checks."""
from dataclasses import replace

def expand_window(candidate, transcript_segments, scenes=None, pre=3.0, post=5.0):
    start=max(0.0,candidate.start-pre); end=candidate.end+post
    if scenes:
        bounds=[s.get("start") for s in scenes if s.get("start") is not None]+[s.get("end") for s in scenes if s.get("end") is not None]
        for b in bounds:
            if b <= candidate.start and candidate.start-b <= 4: start=min(start,b)
            if b >= candidate.end and b-candidate.end <= 4: end=max(end,b)
    return start,end

def standalone_evidence(candidate, transcript_segments, *, min_words=8):
    text=(getattr(candidate,"text","") or "").strip()
    words=len(text.split())
    first=text[:1]
    bad_start=first in {",",".",":",";"} or text.lower().startswith(("and ","but ","so ","because ","which "))
    refs=("this","that","he","she","they","it","there","here")
    starts_ref=any(text.lower().startswith(x+" ") for x in refs)
    score=1.0
    reasons=[]
    if words < min_words: score-=.25; reasons.append("too_short")
    if bad_start: score-=.25; reasons.append("starts_mid_sentence")
    if starts_ref: score-=.15; reasons.append("pronoun_or_deictic_start")
    return {"score":max(0,round(score,3)),"standalone":score>=.65,"reasons":reasons}
