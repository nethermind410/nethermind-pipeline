"""Deterministic cached frame sampling using ffmpeg."""
import hashlib, json, shutil, subprocess
from pathlib import Path

class FrameSampler:
    def __init__(self, db=None, workdir="clipping_farm_work/frames"):
        self.db=db; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True)

    def sample(self, source_id, path, duration, count=12):
        if duration <= 0 or count <= 0: return []
        count=min(count, max(1,int(duration)+1))
        key=f"frames:{source_id}:{Path(path).stat().st_mtime_ns}:{Path(path).stat().st_size}:{count}"
        if self.db:
            cached=self.db.get_artifact(key)
            if cached and Path(cached["path"]).exists():
                try: return json.loads(cached["metadata"]).get("frames",[])
                except Exception: pass
        outdir=self.workdir/source_id; outdir.mkdir(parents=True,exist_ok=True)
        times=[0.0 if count==1 else duration*i/(count-1) for i in range(count)]
        frames=[]
        for i,t in enumerate(times):
            out=outdir/f"frame_{i:04d}.jpg"
            if not out.exists():
                if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg not installed")
                subprocess.run(["ffmpeg","-y","-ss",f"{t:.3f}","-i",str(path),"-frames:v","1","-q:v","3",str(out)],
                               capture_output=True,text=True,check=True)
            h=hashlib.sha256(out.read_bytes()).hexdigest()
            frames.append({"index":i,"time":round(t,3),"path":str(out),"sha256":h})
        if self.db:
            digest=hashlib.sha256(json.dumps(frames,sort_keys=True).encode()).hexdigest()
            self.db.put_artifact(key,"frames",str(outdir),digest,{"frames":frames})
        return frames
