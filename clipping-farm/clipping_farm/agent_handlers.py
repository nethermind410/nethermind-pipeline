"""Concrete local handlers for the current DAG. External model calls are deliberately absent."""
import json
from pathlib import Path
from .analysis import MediaAnalyzer
from .audio import AudioAnalyzer
from .frames import FrameSampler
from .scenes import SceneDetector
from .transcript import FixtureTranscriber, WhisperTranscriber
from .candidates import generate_candidates, rank
from .selection import select
from .brain import DeterministicBrain
from .context import standalone_evidence
from .qc import run_qc
from .repair import repair_candidate
from .export import write_review_manifest

class LocalHandlers:
    def __init__(self, db, workdir="clipping_farm_work", transcriber=None):
        self.db=db; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True)
        self.transcriber=transcriber
        self.meta=MediaAnalyzer(db); self.audio=AudioAnalyzer(db); self.frames=FrameSampler(db)
        self.scenes=SceneDetector(db); self.brain=DeterministicBrain()
        self.cache={}

    def _path(self,j):
        p=j["payload"]; path=p.get("source_path")
        if not path: raise RuntimeError("source_path required for local execution")
        if not Path(path).exists(): raise FileNotFoundError(path)
        return Path(path)

    def metadata(self,j):
        path=self._path(j); return {"decision":"complete","metadata":self.meta.metadata(j["payload"]["source_id"],path),"actual_cost":0}

    def analyse_audio(self,j):
        path=self._path(j); data=self.audio.analyse(j["payload"]["source_id"],path)
        self.cache["audio"]=data; return {"decision":"complete","audio":data,"actual_cost":0}

    def analyse_scenes(self,j):
        path=self._path(j); data=self.scenes.detect(path)
        self.cache["scenes"]=data; return {"decision":"complete","scenes":data,"actual_cost":0}

    def transcribe(self,j):
        path=self._path(j)
        tr=self.transcriber or FixtureTranscriber()
        data=tr.transcribe(path)
        serial=[s.__dict__ for s in data.segments]
        self.cache["transcript"]=serial
        return {"decision":"complete","transcript":serial,"actual_cost":0}

    def generate_candidates(self,j):
        tr=self.cache.get("transcript")
        if tr is None: raise RuntimeError("transcript not available")
        candidates=generate_candidates(tr)
        data=[c.__dict__ for c in candidates]
        self.cache["candidates"]=data
        return {"decision":"complete","candidates":data,"actual_cost":0}

    def score_candidates(self,j):
        candidates=self.cache.get("candidates",[])
        audio=self.cache.get("audio"); scenes=self.cache.get("scenes",[])
        scored=[]
        for raw in candidates:
            from .candidates import Candidate
            c=Candidate(**raw)
            ctx=standalone_evidence(c,self.cache.get("transcript",[]))
            d=self.brain.analyse(c,context=ctx,audio=audio,scenes=scenes,frames=[])
            c.scores.update(d.scores); c.scores["brain_confidence"]=d.confidence
            c.scores["brain_decision"]=d.decision; c.scores["brain_evidence"]=d.evidence
            scored.append(c.__dict__)
        self.cache["scored"]=scored
        return {"decision":"complete","candidates":scored,"actual_cost":0}

    def select_candidates(self,j):
        from .candidates import Candidate
        source=[Candidate(**x) for x in self.cache.get("scored",[])]
        chosen=select(rank(source),limit=10)
        self.cache["selected"]=[c.__dict__ for c in chosen]
        return {"decision":"complete","selected":self.cache["selected"],"actual_cost":0}

    def produce_clips(self,j):
        from .media import FFmpegMedia
        from .candidates import Candidate
        media=FFmpegMedia(self.db); path=self._path(j); source=j["payload"]["source_id"]
        outdir=self.workdir/source/"clips"; outdir.mkdir(parents=True,exist_ok=True)
        results=[]
        for i,raw in enumerate(self.cache.get("selected",[]),1):
            c=Candidate(**raw); out=outdir/f"clip_{i:03d}.mp4"
            media.cut(path,out,c.start,c.end); results.append({**raw,"path":str(out)})
        self.cache["produced"]=results
        return {"decision":"complete","clips":results,"actual_cost":0}

    def qc(self,j):
        from .candidates import Candidate
        results=[]
        for raw in self.cache.get("produced",[]):
            c=Candidate(**raw); q=run_qc(c)
            results.append({"candidate":raw,"qc":q.asdict()})
        self.cache["qc"]=results
        return {"decision":"complete","qc":results,"actual_cost":0}

    def repair(self,j):
        from .candidates import Candidate
        repaired=[]
        for item in self.cache.get("qc",[]):
            c=Candidate(**item["candidate"]); q=run_qc(c)
            if not q.passed and q.repairable:
                c,q,_=repair_candidate(c,run_qc,max_repairs=2)
            repaired.append({"candidate":c.__dict__,"qc":q.asdict()})
        self.cache["repaired"]=repaired
        return {"decision":"complete","clips":repaired,"actual_cost":0}

    def export_review(self,j):
        path=self.workdir/j["payload"]["source_id"]/"review_manifest.json"
        manifest=write_review_manifest(j["payload"]["source_id"],self.cache.get("repaired",[]),path)
        return {"decision":"complete","manifest":manifest,"actual_cost":0}

    def handlers(self):
        return {"metadata":self.metadata,"analyse_audio":self.analyse_audio,"analyse_scenes":self.analyse_scenes,
                "transcribe":self.transcribe,"generate_candidates":self.generate_candidates,
                "score_candidates":self.score_candidates,"select_candidates":self.select_candidates,
                "produce_clips":self.produce_clips,"qc":self.qc,"repair":self.repair,
                "export_review":self.export_review}
