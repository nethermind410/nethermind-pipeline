"""Transcription contract with optional local Whisper adapter."""
from dataclasses import dataclass
import os
import platform

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str|None=None

@dataclass
class Transcript:
    segments: list[TranscriptSegment]
    language: str="en"

class Transcriber:
    def transcribe(self, path) -> Transcript:
        raise NotImplementedError

class FixtureTranscriber(Transcriber):
    def transcribe(self, path) -> Transcript:
        return Transcript([
            TranscriptSegment(0,12,"Example opening with a complete thought."),
            TranscriptSegment(12,27,"Here is the surprising part, and this is why it matters.")
        ])

class WhisperTranscriber(Transcriber):
    def __init__(self, model="base"): self.model_name=model
    def transcribe(self, path) -> Transcript:
        try:
            import whisper
        except ImportError as e:
            raise RuntimeError("Whisper adapter requested but openai-whisper is not installed") from e
        model=whisper.load_model(self.model_name)
        result=model.transcribe(str(path),word_timestamps=False)
        return Transcript([TranscriptSegment(float(s["start"]),float(s["end"]),s["text"].strip())
                           for s in result.get("segments",[])],result.get("language","en"))

class MLXWhisperTranscriber(Transcriber):
    def __init__(self, model="mlx-community/whisper-large-v3-turbo"):
        self.model_name=model

    def transcribe(self, path) -> Transcript:
        try:
            import mlx_whisper
        except ImportError as e:
            raise RuntimeError("MLX Whisper selected but mlx-whisper is not installed; install the asr-mlx extra") from e
        result=mlx_whisper.transcribe(
            str(path),
            path_or_hf_repo=self.model_name,
            verbose=False,
            word_timestamps=False,
        )
        segments=[]
        for s in result.get("segments",[]):
            text=s.get("text","").strip()
            if not text:
                continue
            if float(s.get("no_speech_prob",0.0)) >= 0.6:
                continue
            if float(s.get("compression_ratio",0.0)) > 2.4:
                continue
            segments.append(TranscriptSegment(float(s["start"]),float(s["end"]),text))
        return Transcript(
            segments,
            result.get("language","en"),
        )

def build_transcriber(backend=None, model=None):
    backend=(backend or os.environ.get("CLIP_FARM_TRANSCRIBER") or "").strip().lower()
    if not backend:
        backend="mlx" if platform.system()=="Darwin" and platform.machine().lower() in {"arm64","aarch64"} else "whisper"
    model=model or os.environ.get("CLIP_FARM_WHISPER_MODEL")
    if backend=="fixture":
        return FixtureTranscriber()
    if backend in {"mlx","mlx-whisper"}:
        return MLXWhisperTranscriber(model or "mlx-community/whisper-small-mlx")
    if backend in {"whisper","openai-whisper"}:
        return WhisperTranscriber(model or "base")
    raise ValueError("CLIP_FARM_TRANSCRIBER must be fixture, mlx, or whisper")
