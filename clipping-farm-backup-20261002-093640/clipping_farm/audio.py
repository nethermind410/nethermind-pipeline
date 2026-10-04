"""Deterministic audio intelligence. No model/API required."""
import hashlib, json, math, struct, wave
from pathlib import Path
from .media import FFmpegMedia

class AudioAnalyzer:
    def __init__(self, db=None, workdir="clipping_farm_work/audio"):
        self.db=db; self.workdir=Path(workdir); self.workdir.mkdir(parents=True,exist_ok=True); self.media=FFmpegMedia(db)

    def analyse(self, source_id, path):
        src=Path(path)
        key=f"audio:{source_id}:{src.stat().st_mtime_ns}:{src.stat().st_size}"
        if self.db:
            cached=self.db.get_artifact(key)
            if cached:
                try: return json.loads(cached["metadata"])
                except Exception: pass
        wav=self.workdir/f"{source_id}.wav"
        self.media.extract_audio_wav(path,wav)
        with wave.open(str(wav),"rb") as w:
            rate=w.getframerate(); n=w.getnframes(); raw=w.readframes(n)
        vals=struct.unpack("<"+"h"*(len(raw)//2),raw) if raw else []
        duration=n/rate if rate else 0
        window=max(1,int(rate*0.5))
        windows=[]
        for i in range(0,len(vals),window):
            chunk=vals[i:i+window]
            if not chunk: continue
            rms=math.sqrt(sum(v*v for v in chunk)/len(chunk))/32768
            windows.append({"start":i/rate,"end":min(duration,(i+len(chunk))/rate),"rms":round(rms,6)})
        silence=[{"start":w["start"],"end":w["end"]} for w in windows if w["rms"] < 0.008]
        data={"duration":round(duration,3),"rms":round(math.sqrt(sum(v*v for v in vals)/len(vals))/32768,6) if vals else 0,
              "peak":round(max((abs(v) for v in vals),default=0)/32768,6),
              "windows":windows,"silence_windows":silence}
        if self.db:
            digest=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            self.db.put_artifact(key,"audio_analysis",str(wav),digest,data)
        return data
