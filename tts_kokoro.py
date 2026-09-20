"""
tts_kokoro.py — free, self-hosted narration backend for make_short.py, using Kokoro.

Drop-in replacement for tts_elevenlabs.py: same synthesize(text, mp3_path, voice_id=None)
interface, producing an MP3 file plus word-level timings
    [{"word": str, "start": seconds, "end": seconds}, ...]

Kokoro (MIT license, ~82M params) runs fully offline on CPU — no API key, no
per-character cost, no rate limit. Approved voice: am_liam (Courtney, 2026-09-21).

Setup (one-time, wherever this actually renders — e.g. a GitHub Actions runner):
    pip install kokoro-onnx soundfile --break-system-packages
    apt-get install -y espeak-ng ffmpeg

    # Model files (~200MB total), one-time download, placed next to this script:
    curl -L -o kokoro-v1.0.fp16.onnx \
        https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx
    curl -L -o voices-v1.0.bin \
        https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Word timings are ESTIMATED, not measured — Kokoro doesn't return the
character-level alignment ElevenLabs does. Each word gets a slice of the
total synthesized duration proportional to its character count, in reading
order. Good enough for kinetic captions; not frame-perfect the way the old
ElevenLabs alignment was. If caption sync ever looks off on a real render,
this estimator is the first place to improve.

voice_id: none of the existing cfg/*.json files set one (confirmed — no
per-video ElevenLabs voice IDs are baked in), so this always falls back to
DEFAULT_VOICE (am_liam) in practice. If a caller ever passes something that
isn't a real Kokoro voice name, it's used as-is and Kokoro will raise — that's
intentional, so a stale ElevenLabs ID doesn't silently narrate in the wrong
voice.
"""
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.environ.get("KOKORO_MODEL_PATH", os.path.join(HERE, "kokoro-v1.0.fp16.onnx"))
VOICES_PATH = os.environ.get("KOKORO_VOICES_PATH", os.path.join(HERE, "voices-v1.0.bin"))
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "am_liam")

_kokoro = None


def _kokoro_lazy():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        if not os.path.exists(MODEL_PATH) or not os.path.exists(VOICES_PATH):
            raise FileNotFoundError(
                f"Kokoro model files not found ({MODEL_PATH}, {VOICES_PATH}). "
                "See the setup instructions in this file's docstring."
            )
        _kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    return _kokoro


def _estimate_word_timings(text, total_duration):
    """Distribute total_duration across words, weighted by character count."""
    words = re.findall(r"\S+", text)
    if not words:
        return []
    weights = [len(w) for w in words]
    total_w = sum(weights) or len(words)
    timings, t = [], 0.0
    for w, wt in zip(words, weights):
        d = total_duration * (wt / total_w)
        timings.append({"word": w, "start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return timings


def synthesize(text, mp3_path, voice_id=None):
    """Write narration MP3 to mp3_path, return estimated word-level timings."""
    import soundfile as sf

    kokoro = _kokoro_lazy()
    samples, sample_rate = kokoro.create(text, voice=voice_id or DEFAULT_VOICE, speed=1.0, lang="en-us")

    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        sf.write(wav_path, samples, sample_rate)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
             "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path],
            check=True,
        )
    finally:
        os.unlink(wav_path)

    duration = len(samples) / sample_rate
    return _estimate_word_timings(text, duration)
