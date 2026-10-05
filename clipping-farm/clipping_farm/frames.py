"""Deterministic cached frame sampling using ffmpeg."""
import hashlib, json, shutil, subprocess
from pathlib import Path

class FrameSampler:
    def __init__(self, db=None, workdir="clipping_farm_work"):
        self.db=db; self.workdir=Path(workdir)

    def _video_duration(self, path):
        """Get actual video duration via ffprobe."""
        try:
            r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],
                             capture_output=True,text=True,timeout=15)
            return float(r.stdout.strip()) if r.stdout.strip() else None
        except Exception:
            return None

    def sample(self, source_id, path, duration, count=12, start=0.0, end=None):
        if duration <= 0 or count <= 0: return []
        start=max(0.0,float(start))
        end=duration if end is None else min(duration,max(start,float(end)))
        # Cap to safe margin before actual video end (ffmpeg can't read last frame)
        actual_dur=self._video_duration(path)
        if actual_dur: end=min(end, actual_dur-0.5)
        else: end=min(end, duration-0.001)
        window=max(0.0,end-start)
        count=min(count, max(1,int(window)+1))
        if window <= 0:
            times=[start]; count=1
        else:
            times=[start+window*i/max(count-1,1) for i in range(count)]
        key=f"frames:{source_id}:{Path(path).stat().st_mtime_ns}:{Path(path).stat().st_size}:{count}:{start:.3f}:{end:.3f}"
        if self.db:
            try: cached=self.db.get_artifact(key)
            except TypeError: cached=self.db.get_artifact(key,"frames")
            if cached:
                try: return json.loads(cached["metadata"]).get("frames",[])
                except Exception: pass
        variant=hashlib.sha256(key.encode()).hexdigest()[:16]
        outdir=self.workdir/source_id/variant; outdir.mkdir(parents=True,exist_ok=True)
        frames=[]
        for i,t in enumerate(times):
            out=outdir/f"frame_{i:04d}.jpg"
            if not out.exists():
                if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg not installed")
                # Fast seek: -ss before -i (keyframe-tolerant)
                try:
                    subprocess.run(["ffmpeg","-y","-ss",f"{t:.3f}","-i",str(path),"-frames:v","1","-q:v","3",str(out)],
                                   capture_output=True,text=True,check=True,timeout=30)
                except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                    # Slow seek fallback — after -i (frame-accurate)
                    try:
                        subprocess.run(["ffmpeg","-y","-i",str(path),"-ss",f"{t:.3f}","-frames:v","1","-q:v","3",str(out)],
                                       capture_output=True,text=True,check=True,timeout=60)
                    except Exception:
                        continue
            if not out.exists(): continue
            h=hashlib.sha256(out.read_bytes()).hexdigest()
            frames.append({"index":i,"time":round(t,3),"path":str(out),"sha256":h})
        if self.db:
            digest=hashlib.sha256(json.dumps(frames,sort_keys=True).encode()).hexdigest()
            self.db.put_artifact(key,"frames",str(outdir),digest,{"frames":frames})
        return frames