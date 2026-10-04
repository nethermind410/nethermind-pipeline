"""Compact, cacheable evidence packets for Brain/provider calls."""
from dataclasses import dataclass, asdict
import hashlib, json
@dataclass
class EvidencePacket:
    candidate: dict; transcript:list; context_before:str; context_after:str; audio:dict; scenes:list; frames:list; source_metadata:dict
    def to_dict(self): return asdict(self)
    def digest(self): return hashlib.sha256(json.dumps(self.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def build_packet(candidate, transcript, audio, scenes, frames, metadata=None, context_seconds=12):
    before=[]; after=[]
    for s in transcript:
        if float(s["end"]) <= candidate.start and candidate.start-float(s["end"]) <= context_seconds: before.append(s.get("text",""))
        elif float(s["start"]) >= candidate.end and float(s["start"])-candidate.end <= context_seconds: after.append(s.get("text",""))
    relevant=[f for f in frames if candidate.start-1 <= float(f["time"]) <= candidate.end+1]
    return EvidencePacket(candidate.__dict__,transcript," ".join(before)," ".join(after),audio or {},scenes or [],relevant,metadata or {})
