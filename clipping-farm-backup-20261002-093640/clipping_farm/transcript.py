"""Transcription contract with optional local Whisper adapter."""
from dataclasses import dataclass

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
