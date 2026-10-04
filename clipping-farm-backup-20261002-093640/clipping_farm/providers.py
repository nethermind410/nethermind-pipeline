"""Provider contract. No provider is called by default."""
from dataclasses import dataclass
@dataclass
class ProviderResult:
    decision:str; confidence:float; reason:str; evidence:list; scores:dict; model:str; estimated_cost:float=0.0; actual_cost:float=0.0
class BrainProvider:
    name="base"; modality="text"
    def analyse(self,packet): raise NotImplementedError
class DeterministicProvider(BrainProvider):
    name="deterministic"; modality="multimodal"
    def __init__(self,brain): self.brain=brain
    def analyse(self,packet):
        from .candidates import Candidate
        c=Candidate(**packet.candidate)
        d=self.brain.analyse(c,context={"score":c.scores.get("standalone",0),"reasons":[]},audio=packet.audio,scenes=packet.scenes,frames=packet.frames)
        return ProviderResult(d.decision,d.confidence,d.reason,d.evidence,d.scores,self.name)
