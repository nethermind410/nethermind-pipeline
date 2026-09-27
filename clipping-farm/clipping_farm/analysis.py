"""Deterministic media-analysis adapters; optional tools stay optional."""
import json, shutil, subprocess
from pathlib import Path

class MediaAnalyzer:
    def __init__(self, db): self.db=db

    def metadata(self, source_id, path):
        key=f"metadata:{source_id}:{Path(path).stat().st_mtime_ns}:{Path(path).stat().st_size}"
        cached=self.db.get_artifact(key)
        if cached:return cached["metadata"]
        ffprobe=shutil.which("ffprobe")
        data={"path":str(path),"ffprobe_available":bool(ffprobe)}
        if ffprobe:
            p=subprocess.run([ffprobe,"-v","quiet","-print_format","json","-show_format","-show_streams",str(path)],
                             capture_output=True,text=True,check=True)
            data.update(json.loads(p.stdout))
        return data
