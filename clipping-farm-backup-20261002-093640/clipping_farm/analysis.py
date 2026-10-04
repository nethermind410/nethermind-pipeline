"""Deterministic media-analysis adapters; optional tools stay optional."""
import hashlib,json,shutil,subprocess
from pathlib import Path
class MediaAnalyzer:
 def __init__(self,db): self.db=db
 def metadata(self,source_id,path):
  p=Path(path); key=f"metadata:{source_id}:{p.stat().st_mtime_ns}:{p.stat().st_size}"
  cached=self.db.get_artifact(key)
  if cached:
   try:return json.loads(cached["metadata"])
   except Exception:return cached["metadata"]
  ffprobe=shutil.which("ffprobe"); data={"path":str(path),"ffprobe_available":bool(ffprobe)}
  if ffprobe:
   out=subprocess.run([ffprobe,"-v","quiet","-print_format","json","-show_format","-show_streams",str(path)],capture_output=True,text=True,check=True)
   data.update(json.loads(out.stdout))
  digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
  self.db.put_artifact(key,"metadata",str(path),digest,data)
  return data
