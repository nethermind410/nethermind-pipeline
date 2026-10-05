"""Real local-media adapters with deterministic fallbacks.

No network access is performed here. Inputs must already be authorised and local.
"""
import shutil, subprocess, json, wave, math
from pathlib import Path

class FFmpegMedia:
    def __init__(self, db=None): self.db=db

    def _run(self,args):
        if not shutil.which(args[0]): raise RuntimeError(f"{args[0]} not installed")
        return subprocess.run(args,capture_output=True,text=True,check=True)

    def probe(self,path):
        p=self._run(["ffprobe","-v","error","-print_format","json","-show_format","-show_streams",str(path)])
        return json.loads(p.stdout)

    def extract_audio_wav(self,path,out,rate=16000):
        self._run(["ffmpeg","-y","-i",str(path),"-vn","-ac","1","-ar",str(rate),"-c:a","pcm_s16le",str(out)])
        return str(out)

    def cut(self,path,out,start,end):
        if end <= start: raise ValueError("end must be greater than start")
        try:
            self._run(["ffmpeg","-y","-ss",str(start),"-i",str(path),"-t",str(end-start),
                       "-vf","scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2",
                       "-c:v","libx264","-c:a","aac",str(out)])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"cut failed: {e.stderr or e}") from e
        return str(out)

def wav_stats(path):
    with wave.open(str(path),"rb") as w:
        n=w.getnframes(); rate=w.getframerate(); width=w.getsampwidth()
        raw=w.readframes(n)
    if not n:return {"duration":0,"rms":0,"peak":0}
    import struct
    vals=struct.unpack("<"+"h"*(len(raw)//2),raw) if width==2 else []
    if not vals:return {"duration":n/rate,"rms":0,"peak":0}
    rms=math.sqrt(sum(v*v for v in vals)/len(vals))/32768
    peak=max(abs(v) for v in vals)/32768
    return {"duration":n/rate,"rms":round(rms,6),"peak":round(peak,6)}
