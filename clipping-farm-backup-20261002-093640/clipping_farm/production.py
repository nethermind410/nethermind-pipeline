"""Render-plan layer. It describes work before invoking FFmpeg."""
from dataclasses import dataclass, asdict

@dataclass
class RenderPlan:
    input_path: str
    output_path: str
    start: float
    end: float
    width: int=1080
    height: int=1920
    captions_path: str|None=None

    def ffmpeg_args(self):
        return ["ffmpeg","-y","-ss",str(self.start),"-i",self.input_path,
                "-t",str(self.end-self.start),"-vf",
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease",
                "-c:v","libx264","-c:a","aac",self.output_path]

    def asdict(self): return asdict(self)
