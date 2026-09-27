"""Concrete local handlers for the current DAG. Results are read from the DB, so workers are disposable."""
from pathlib import Path
from .analysis import MediaAnalyzer
from .audio import AudioAnalyzer
from .frames import FrameSampler
from .scenes import SceneDetector
from .transcript import FixtureTranscriber, WhisperTranscriber
from .candidates import generate_candidates, rank, Candidate
from .selection import select
from .brain import DeterministicBrain
from .context import standalone_evidence
from .qc import run_qc
from .repair import repair_candidate
from .export import write_review_manifest

class LocalHandlers:
    def __init__(self, db, workdir="clipping_farm_work", transcriber=None):
        self.db=db; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True)
        self.transcriber=transcriber or FixtureTranscriber()
        self.meta=MediaAnalyzer(db); self.audio=AudioAnalyzer(db); self.frames=FrameSampler(db)
        self.scenes=SceneDetector(db); self.brain=DeterministicBrain()

    def _path(self,j):
        path=j["payload"].get("source_path")
        if not path: raise RuntimeError("source_path required for local execution")
        p=Path(path)
        if not p.exists(): raise FileNotFoundError(path)
        return p

    def _dependency_results(self,j):
        out=[]
        import json
        for dep in json.loads(j["depends_on"] or "[]"):
            row=self.db.cx.execute("SELECT result,state FROM jobs WHERE id=?",(dep,)).fetchone()
            if not row or row["state"]!="COMPLETE": raise RuntimeError(f"dependency {dep} not complete")
            out.append(json.loads(row["result"] or "{}"))
        return out

    def _find(self,results,key,default=None):
        for r in results:
            if key in r: return r[key]
        return default

    def metadata(self,j):
        path=self._path(j)
        return {"decision":"complete","metadata":self.meta.metadata(j["payload"]["source_id"],path),"actual_cost":0}

    def analyse_audio(self,j):
        data=self.audio.analyse(j["payload"]["source_id"],self._path(j))
        return {"decision":"complete","audio":data,"actual_cost":0}

    def analyse_scenes(self,j):
        data=self.scenes.detect(self._path(j))
        return {"decision":"complete","scenes":data,"actual_cost":0}

    def transcribe(self,j):
        tr=self.transcriber.transcribe(self._path(j))
        serial=[s.__dict__ for s in tr.segments]
        return {"decision":"complete","transcript":serial,"language":tr.language,"actual_cost":0}

    def generate_candidates(self,j):
        results=self._dependency_results(j)
        transcript=self._find(results,"transcript",[])
        audio=self._find(results,"audio",{})
        scenes=self._find(results,"scenes",[])
        candidates=generate_candidates(transcript)
        return {"decision":"complete","candidates":[c.__dict__ for c in candidates],
                "evidence_summary":{"audio":audio,"scene_count":len(scenes)},"actual_cost":0}

    def score_candidates(self,j):
        results=self._dependency_results(j)
        candidates=[Candidate(**x) for x in self._find(results,"candidates",[])]
        transcript=self._find(results,"transcript",[])
        audio=self._find(results,"audio",{})
        scenes=self._find(results,"scenes",[])
        scored=[]
        for c in candidates:
            ctx=standalone_evidence(c,transcript)
            d=self.brain.analyse(c,context=ctx,audio=audio,scenes=scenes,frames=[])
            c.scores.update(d.scores); c.scores["brain_confidence"]=d.confidence
            c.scores["brain_decision"]=d.decision; c.scores["brain_evidence"]=d.evidence
            scored.append(c.__dict__)
        return {"decision":"complete","candidates":scored,"actual_cost":0}

    def select_candidates(self,j):
        results=self._dependency_results(j)
        source=[Candidate(**x) for x in self._find(results,"candidates",[])]
        chosen=select(rank(source),limit=10)
        return {"decision":"complete","selected":[c.__dict__ for c in chosen],"actual_cost":0}

    def produce_clips(self,j):
        from .media import FFmpegMedia
        media=FFmpegMedia(self.db); path=self._path(j); source=j["payload"]["source_id"]
        selected=self._find(self._dependency_results(j),"selected",[])
        outdir=self.workdir/source/"clips"; outdir.mkdir(parents=True,exist_ok=True)
        results=[]
        for i,raw in enumerate(selected,1):
            c=Candidate(**raw); out=outdir/f"clip_{i:03d}.mp4"
            media.cut(path,out,c.start,c.end); results.append({**raw,"path":str(out)})
        return {"decision":"complete","clips":results,"actual_cost":0}

    def qc(self,j):
        results=[]
        for raw in self._find(self._dependency_results(j),"clips",[]):
            c=Candidate(**{k:v for k,v in raw.items() if k in {"start","end","text","scores","decision"}})
            q=run_qc(c)
            results.append({"candidate":raw,"qc":q.asdict()})
        return {"decision":"complete","qc":results,"actual_cost":0}

    def repair(self,j):
        repaired=[]
        for item in self._find(self._dependency_results(j),"qc",[]):
            c=Candidate(**item["candidate"]); q=run_qc(c)
            if not q.passed and q.repairable:
                c,q,_=repair_candidate(c,run_qc,max_repairs=2)
            repaired.append({"candidate":c.__dict__,"qc":q.asdict()})
        return {"decision":"complete","clips":repaired,"actual_cost":0}

    def export_review(self,j):
        source=j["payload"]["source_id"]
        repaired=self._find(self._dependency_results(j),"clips",[])
        path=self.workdir/source/"review_manifest.json"; path.parent.mkdir(parents=True,exist_ok=True)
        manifest=write_review_manifest(path,source,repaired)
        return {"decision":"complete","manifest":manifest,"actual_cost":0}

    def handlers(self):
        return {"metadata":self.metadata,"analyse_audio":self.analyse_audio,"analyse_scenes":self.analyse_scenes,
                "transcribe":self.transcribe,"generate_candidates":self.generate_candidates,
                "score_candidates":self.score_candidates,"select_candidates":self.select_candidates,
                "produce_clips":self.produce_clips,"qc":self.qc,"repair":self.repair,
                "export_review":self.export_review}
