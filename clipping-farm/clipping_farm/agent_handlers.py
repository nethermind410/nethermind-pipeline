"""Concrete local handlers. Dependency results are persisted in SQLite; workers remain disposable."""
from pathlib import Path
from .analysis import MediaAnalyzer
from .audio import AudioAnalyzer
from .frames import FrameSampler
from .scenes import SceneDetector
from .transcript import FixtureTranscriber
from .candidates import generate_candidates,rank,Candidate
from .selection import select
from .brain import DeterministicBrain
from .adaptive_brain import AdaptiveBrain
from .mock_providers import CheapMockProvider, PremiumMockProvider
from .providers import DeterministicProvider
from .provider_adapters import build_configured_providers
from .context import standalone_evidence
from .evidence import build_packet
from .vision import VisionBrain
from .multimodal import MultimodalCandidateBrain
from .qc import run_qc
from .repair import repair_candidate
from .export import write_review_manifest
class LocalHandlers:
 def __init__(self,db,workdir="clipping_farm_work",transcriber=None):
  self.db=db; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True)
  self.transcriber=transcriber or FixtureTranscriber(); self.meta=MediaAnalyzer(db); self.audio=AudioAnalyzer(db); self.frames=FrameSampler(db); self.scenes=SceneDetector(db)
  self.vision=VisionBrain(db, max_frames=6); self.fusion=MultimodalCandidateBrain()
  self.brain=AdaptiveBrain(db)
  self.brain.register_provider(DeterministicProvider(DeterministicBrain()))
  for provider in build_configured_providers(): self.brain.register_provider(provider)
 def _path(self,j):
  p=Path(j["payload"].get("source_path") or "")
  if not p.exists(): raise FileNotFoundError(str(p))
  return p
 def _deps(self,j):
  import json
  out=[]
  for dep in json.loads(j["depends_on"] or "[]"):
   row=self.db.cx.execute("SELECT result,state FROM jobs WHERE id=?",(dep,)).fetchone()
   if not row or row["state"]!="COMPLETE": raise RuntimeError(f"dependency {dep} not complete")
   out.append(json.loads(row["result"] or "{}"))
  return out
 def _find(self,results,key,default=None):
  for r in results:
   if key in r:return r[key]
  return default
 def metadata(self,j): return {"decision":"complete","metadata":self.meta.metadata(j["payload"]["source_id"],self._path(j)),"actual_cost":0}
 def analyse_audio(self,j): return {"decision":"complete","audio":self.audio.analyse(j["payload"]["source_id"],self._path(j)),"actual_cost":0}
 def analyse_scenes(self,j): return {"decision":"complete","scenes":self.scenes.detect(self._path(j)),"actual_cost":0}
 def transcribe(self,j):
  tr=self.transcriber.transcribe(self._path(j))
  return {"decision":"complete","transcript":[s.__dict__ for s in tr.segments],"language":tr.language,"actual_cost":0}
 def generate_candidates(self,j):
  r=self._deps(j); cs=generate_candidates(self._find(r,"transcript",[]))
  return {"decision":"complete","candidates":[c.__dict__ for c in cs],"actual_cost":0}
 def score_candidates(self,j):
  r=self._deps(j); transcript=self._find(r,"transcript",[]); audio=self._find(r,"audio",{}); scenes=self._find(r,"scenes",[]); meta=self._find(r,"metadata",{})
  duration=float(meta.get("format",{}).get("duration",0) or 0)
  scored=[]
  for c in [Candidate(**x) for x in self._find(r,"candidates",[])]:
   ctx=standalone_evidence(c,transcript)
   frames=self.frames.sample(j["payload"]["source_id"],self._path(j),duration,count=12) if duration else []
   packet=build_packet(c,transcript,audio,scenes,frames,meta)
   d=self.brain.analyse(packet,job_id=j["id"],budget=float(j.get("budget") or 0))
   c.scores.update(d.result.scores); c.scores.update({"brain_confidence":d.result.confidence,"brain_decision":d.result.decision,"brain_evidence":d.result.evidence,"brain_provider":d.result.model,"brain_trace":d.trace,"evidence_digest":packet.digest()})
   scored.append(c.__dict__)
  return {"decision":"complete","candidates":scored,"actual_cost":0}
 def select_candidates(self,j):
  cs=[Candidate(**x) for x in self._find(self._deps(j),"candidates",[])]
  chosen=select(rank(cs),limit=10)
  return {"decision":"complete","selected":[c.__dict__ for c in chosen],"actual_cost":0}
 def produce_clips(self,j):
  from .media import FFmpegMedia
  media=FFmpegMedia(self.db); selected=self._find(self._deps(j),"selected",[]); source=j["payload"]["source_id"]; outdir=self.workdir/source/"clips"; outdir.mkdir(parents=True,exist_ok=True); results=[]
  for i,raw in enumerate(selected,1):
   c=Candidate(**raw); out=outdir/f"clip_{i:03d}.mp4"; media.cut(self._path(j),out,c.start,c.end); results.append({**raw,"path":str(out)})
  return {"decision":"complete","clips":results,"actual_cost":0}
 def qc(self,j):
  results=[]
  for raw in self._find(self._deps(j),"clips",[]):
   c=Candidate(**{k:v for k,v in raw.items() if k in {"start","end","text","scores","decision"}}); q=run_qc(c); results.append({"candidate":raw,"qc":q.asdict()})
  return {"decision":"complete","qc":results,"actual_cost":0}
 def repair(self,j):
  repaired=[]
  for item in self._find(self._deps(j),"qc",[]):
   c=Candidate(**item["candidate"]); q=run_qc(c)
   if not q.passed and q.repairable:c,q,_=repair_candidate(c,run_qc,max_repairs=2)
   repaired.append({"candidate":c.__dict__,"qc":q.asdict()})
  return {"decision":"complete","clips":repaired,"actual_cost":0}
 def export_review(self,j):
  source=j["payload"]["source_id"]; repaired=self._find(self._deps(j),"clips",[]); path=self.workdir/source/"review_manifest.json"; path.parent.mkdir(parents=True,exist_ok=True)
  return {"decision":"complete","manifest":write_review_manifest(path,source,repaired),"actual_cost":0}
 def handlers(self):
  return {"metadata":self.metadata,"analyse_audio":self.analyse_audio,"analyse_scenes":self.analyse_scenes,"transcribe":self.transcribe,"generate_candidates":self.generate_candidates,"score_candidates":self.score_candidates,"select_candidates":self.select_candidates,"produce_clips":self.produce_clips,"qc":self.qc,"repair":self.repair,"export_review":self.export_review}
