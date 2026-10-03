"""Provider-neutral Brain with deterministic-first escalation plumbing."""
from dataclasses import dataclass
@dataclass
class BrainDecision:
    decision:str; confidence:float; reason:str; evidence:list; scores:dict; escalate:bool=False; provider:str="deterministic"
class DeterministicBrain:
    REQUIRED_CONFIDENCE=.78
    def analyse(self,candidate,*,context=None,audio=None,scenes=None,frames=None):
        scores=dict(candidate.scores); evidence=[]
        if context:
            scores["standalone"]=max(scores.get("standalone",0),context.get("score",0)); evidence.extend(context.get("reasons",[]))
        if audio:
            peak=audio.get("peak",0); scores["audio"]=1.0 if peak>=.03 else .6; evidence.append({"type":"audio","peak":peak})
        if scenes is not None:
            scores["visual"]=min(1.0,.55+min(len(scenes),8)*.04); evidence.append({"type":"scenes","count":len(scenes)})
        if frames: evidence.append({"type":"frames","count":len(frames)})
        keys=("hook","payoff","context","standalone","information","novelty","visual","audio")
        total=float(sum(scores.get(k,0) for k in keys)/len(keys))
        # Accept: strong standalone + audio evidence (audio-only OK), or full multimodal threshold
        audio_strong = scores.get("audio",0) >= .8
        multimodal_ok = total >= .62 and scores.get("standalone",0) >= .65
        decision="accept" if (multimodal_ok or (audio_strong and scores.get("standalone",0) >= .65)) else "reject"
        confidence=float(min(.99,max(.5,total)))
        return BrainDecision(decision,round(confidence,3),"deterministic evidence threshold" if decision=="accept" else "insufficient standalone/evidence",evidence,{
            k: (
                v if isinstance(v, (dict, list, str, type(None), bool))
                else round(v, 3)
            )
            for k, v in scores.items()
        },confidence<.78)