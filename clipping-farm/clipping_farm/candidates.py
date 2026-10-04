"""Deterministic-first candidate generation and scoring."""
from dataclasses import dataclass, asdict
from typing import Iterable
import re

@dataclass
class Candidate:
    start: float
    end: float
    text: str
    scores: dict
    decision: str = "REVIEW"
    source_modality: str = "speech"

    @property
    def duration(self): return max(0.0, self.end - self.start)

    def asdict(self): return asdict(self)

def generate_candidates(segments: Iterable[dict], *, min_seconds=8, max_seconds=75):
    segs=list(segments)
    out=[]
    for i,s in enumerate(segs):
        text=(s.get("text") or "").strip()
        if not text: continue
        start=float(s["start"]); end=float(s["end"])
        if end-start < min_seconds:
            j=i+1
            while j<len(segs) and end-start < min_seconds:
                text += " " + (segs[j].get("text") or "").strip()
                end=float(segs[j]["end"]); j+=1
        if min_seconds <= end-start <= max_seconds:
            out.append(Candidate(start,end,text,score_candidate(text)))
    return out

def score_candidate(text: str):
    words=re.findall(r"\b[\w’'-]+\b", text)
    n=len(words); low=text.lower()
    hook_terms=("why","how","never","secret","actually","but","because","the truth","you")
    payoff_terms=("so","therefore","means","result","turns out","which is why","finally")
    hook=min(1.0, (sum(t in low for t in hook_terms)/3)+min(n/80,0.25))
    payoff=min(1.0, sum(t in low for t in payoff_terms)/3 + min(n/120,0.2))
    context=0.75 if text[:1].isupper() and not low.startswith(("and ","but ","so ","because ","which ")) else 0.45
    standalone=min(1.0, context + (0.15 if n>=35 else 0))
    information=min(1.0, 0.25 + min(n/90,0.5) + (0.2 if any(c.isdigit() for c in text) else 0))
    novelty=min(1.0, 0.35 + 0.25*len(set(words))/max(n,1))
    return {"hook":round(hook,3),"payoff":round(payoff,3),"context":round(context,3),
            "standalone":round(standalone,3),"information":round(information,3),
            "novelty":round(novelty,3)}

def rank(candidates):
    weights={"hook":.20,"payoff":.20,"context":.15,"standalone":.20,"information":.15,"novelty":.10}
    for c in candidates:
        c.scores["total"]=round(sum(c.scores[k]*v for k,v in weights.items()),3)
    return sorted(candidates,key=lambda c:c.scores["total"],reverse=True)
