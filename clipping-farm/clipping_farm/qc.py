"""Publish-gate QC. Results are explicit PASS/FAIL, not a single opaque score."""
from dataclasses import dataclass, asdict

@dataclass
class QCResult:
    standalone: str
    audio: str
    visual: str
    rights: str
    opening: str
    ending: str
    caption: str
    context: str
    repairable: bool
    repairs: list

    @property
    def passed(self):
        return all(getattr(self,k)=="PASS" for k in
                   ("standalone","audio","visual","rights","opening","ending","caption","context"))

    def asdict(self): return asdict(self)

def run_qc(candidate, *, rights_authorised=True, audio_ok=True, visual_ok=True,
           captions_ok=True, context_ok=True):
    text=(getattr(candidate,"text","") or "").strip()
    standalone="PASS" if candidate.scores.get("standalone",0)>=.65 else "FAIL"
    opening="PASS" if candidate.duration>=8 and len(text.split())>=8 else "FAIL"
    ending="PASS" if text[-1:] in ".!?)]”'" else "FAIL"
    return QCResult(
        standalone, "PASS" if audio_ok else "FAIL", "PASS" if visual_ok else "FAIL",
        "PASS" if rights_authorised else "FAIL", opening, ending,
        "PASS" if captions_ok else "FAIL", "PASS" if context_ok else "FAIL",
        not (opening=="FAIL" and candidate.duration<5),
        ["extend_start_or_end"] if ending=="FAIL" else []
    )

def render_qc_text(q):
    return "\n".join(f"{k.replace('_',' ').title():<16} {v}"
                      for k,v in asdict(q).items() if k not in ("repairable","repairs"))
