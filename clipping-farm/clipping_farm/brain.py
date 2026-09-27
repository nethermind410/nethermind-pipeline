"""Provider-neutral Brain. Deterministic first; model providers can plug in later."""
from dataclasses import dataclass, asdict

@dataclass
class BrainDecision:
    decision: str
    confidence: float
    reason: str
    evidence: list
    scores: dict
    escalate: bool=False

class DeterministicBrain:
    def analyse(self, candidate, *, context=None, audio=None, scenes=None, frames=None):
        scores=dict(candidate.scores)
        evidence=[]
        if context:
            scores["standalone"]=max(scores.get("standalone",0),context.get("score",0))
            evidence.extend(context.get("reasons",[]))
        if audio:
            peak=audio.get("peak",0)
            scores["audio"]=1.0 if peak>=0.03 else 0.6
            evidence.append({"audio_peak":peak})
        if scenes is not None:
            scores["visual"]=min(1.0,0.55+min(len(scenes),8)*0.04)
            evidence.append({"scene_count":len(scenes)})
        if frames:
            evidence.append({"frame_count":len(frames)})
        total=sum(scores.get(k,0) for k in ("hook","payoff","context","standalone","information","novelty","visual","audio"))/8
        decision="accept" if total>=0.62 and scores.get("standalone",0)>=.65 else "reject"
        confidence=min(0.99,max(0.5,total))
        return BrainDecision(decision,round(confidence,3),
                             "deterministic evidence threshold" if decision=="accept" else "insufficient standalone/evidence",
                             evidence,{k:round(v,3) for k,v in scores.items()},
                             escalate=confidence<0.78)
