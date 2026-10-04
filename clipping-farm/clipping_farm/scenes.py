"""Lightweight scene-boundary detection using FFmpeg's scene score."""
import shutil, subprocess

SEGMENT_DURATION = 12  # seconds per scene if no scene changes detected

class SceneDetector:
    def __init__(self, db=None):
        self.db = db

    def detect(self, path, threshold=.35):
        if not shutil.which("ffmpeg"):
            return []
        cmd = ["ffmpeg", "-hide_banner", "-i", str(path),
               "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
        p = subprocess.run(cmd, capture_output=True, text=True)
        times = []
        for line in p.stderr.splitlines():
            if "pts_time:" in line:
                try:
                    times.append(float(line.split("pts_time:")[1].split()[0]))
                except (ValueError, IndexError):
                    pass
        times = sorted(set(times))
        scenes = [{"start": t, "end": times[i+1] if i+1 < len(times) else None}
                  for i, t in enumerate(times)]
        # Fallback: split video into equal-duration segments so the pipeline
        # always has scenes to work with, even for static/low-contrast content
        if not scenes:
            try:
                dur = float(subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                    capture_output=True, text=True, timeout=15
                ).stdout.strip())
            except Exception:
                dur = 0
            if dur > 0:
                for start in range(0, int(dur), SEGMENT_DURATION):
                    end = min(start + SEGMENT_DURATION, dur)
                    scenes.append({"start": float(start), "end": float(end)})
        return scenes