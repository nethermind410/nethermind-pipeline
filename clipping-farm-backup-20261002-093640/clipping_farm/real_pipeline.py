"""Local end-to-end runner for authorised files.

This intentionally stops at review/export. It never publishes.
"""
from pathlib import Path
from .ingest import Source, SourceIngestor
from .media import FFmpegMedia, wav_stats
from .transcript import Transcriber
from .candidates import generate_candidates, rank
from .selection import select
from .qc import run_qc
from .repair import repair_candidate

class LocalClipRunner:
    def __init__(self,db,transcriber:Transcriber,workdir="clipping_farm_work"):
        self.db=db; self.transcriber=transcriber; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True)
        self.media=FFmpegMedia(db)

    def run(self,source_id,path,limit=10):
        SourceIngestor(self.db).ingest_file(Source(source_id,str(path)))
        meta=self.media.probe(path)
        transcript=self.transcriber.transcribe(path)
        candidates=select(rank(generate_candidates([s.__dict__ for s in transcript.segments])),limit=limit)
        results=[]
        for i,c in enumerate(candidates,1):
            out=self.workdir/f"{source_id}_clip_{i:02d}.mp4"
            try:
                self.media.cut(path,out,c.start,c.end)
                q=run_qc(c)
                if not q.passed:
                    c,q,_=repair_candidate(c,run_qc,max_repairs=2)
                results.append({"id":f"{source_id}-clip-{i:02d}","start":c.start,"end":c.end,
                                "path":str(out),"qc":q.asdict()})
            except Exception as e:
                results.append({"id":f"{source_id}-clip-{i:02d}","error":f"{type(e).__name__}: {e}"})
        return {"source_id":source_id,"metadata":meta,"clips":results}
