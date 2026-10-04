"""Lightweight scene-boundary detection using FFmpeg's scene score."""
import shutil, subprocess
class SceneDetector:
 def __init__(self,db=None): self.db=db
 def detect(self,path,threshold=.35):
  if not shutil.which("ffmpeg"): return []
  cmd=["ffmpeg","-hide_banner","-i",str(path),"-vf",f"select='gt(scene,{threshold})',showinfo","-f","null","-"]
  p=subprocess.run(cmd,capture_output=True,text=True)
  times=[]
  for line in p.stderr.splitlines():
   if "pts_time:" in line:
    try: times.append(float(line.split("pts_time:")[1].split()[0]))
    except (ValueError,IndexError): pass
  times=sorted(set(times))
  return [{"start":t,"end":times[i+1] if i+1<len(times) else None} for i,t in enumerate(times)]
