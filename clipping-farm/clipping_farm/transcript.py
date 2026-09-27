"""Transcription contract. Providers can be local or remote without changing the pipeline."""
from dataclasses import dataclass, asdict

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
        raise NotImplementedError("Install/configure a transcription provider adapter")

class FixtureTranscriber(Transcriber):
    def transcribe(self, path) -> Transcript:
        return Transcript([TranscriptSegment(0,12,"Example opening with a complete thought."),
                           TranscriptSegment(12,27,"Here is the surprising part, and this is why it matters.")])
