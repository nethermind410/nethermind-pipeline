#!/usr/bin/env python3
"""
kokoro_tts.py — free, self-hosted voiceover for Nnethermind, replacing ElevenLabs/vidIQ.

Kokoro (MIT license, ~82M params) runs entirely on CPU. No API key, no per-character
cost, no rate limit. Proven live in a Claude session on 2026-09-21: ~4-5 seconds to
synthesize a 10-12 second line.

Setup (one-time, on whatever machine/runner will actually render — a GitHub Actions
Ubuntu runner works fine):

    pip install kokoro-onnx soundfile --break-system-packages
    apt-get install -y espeak-ng      # Kokoro's phonemizer dependency

    # Model files (~200MB total), one-time download:
    curl -L -o kokoro-v1.0.fp16.onnx \\
        https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx
    curl -L -o voices-v1.0.bin \\
        https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

Usage:

    python kokoro_tts.py "Only four point five millimeters across..." out.wav
    python kokoro_tts.py "Only four point five millimeters across..." out.wav --voice am_fenrir
    python kokoro_tts.py --list-voices

Default voice is am_liam — Courtney's approved Kokoro voice (2026-09-21), the closest
match to the channel's current ElevenLabs "Liam" voice.
"""

import argparse
import sys
from pathlib import Path

DEFAULT_VOICE = "am_liam"
MODEL_PATH = "kokoro-v1.0.fp16.onnx"
VOICES_PATH = "voices-v1.0.bin"

# A few notable voices from Kokoro's built-in set, for reference.
# Full list: kokoro.get_voices() after loading the model.
NOTABLE_VOICES = [
    "am_liam",    # default — approved 2026-09-21, closest to current ElevenLabs voice
    "am_fenrir",
    "am_adam",
    "af_bella",
    "af_sarah",
    "bm_george",
    "bf_emma",
]


def synthesize(text: str, out_path: str, voice: str = DEFAULT_VOICE, speed: float = 1.0,
               lang: str = "en-us", model_path: str = MODEL_PATH, voices_path: str = VOICES_PATH) -> None:
    """Synthesize `text` to a WAV file at `out_path` using the given Kokoro voice."""
    try:
        from kokoro_onnx import Kokoro
        import soundfile as sf
    except ImportError as e:
        sys.exit(
            f"Missing dependency: {e}\n"
            "Install with: pip install kokoro-onnx soundfile --break-system-packages\n"
            "Also requires the espeak-ng system package."
        )

    if not Path(model_path).exists() or not Path(voices_path).exists():
        sys.exit(
            f"Model files not found ({model_path}, {voices_path}).\n"
            "See the setup instructions in this script's docstring."
        )

    kokoro = Kokoro(model_path, voices_path)
    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    sf.write(out_path, samples, sample_rate)
    duration = len(samples) / sample_rate
    print(f"Wrote {out_path} — {duration:.2f}s audio, voice={voice}")


def list_voices(model_path: str = MODEL_PATH, voices_path: str = VOICES_PATH) -> None:
    try:
        from kokoro_onnx import Kokoro
    except ImportError as e:
        sys.exit(f"Missing dependency: {e}")
    kokoro = Kokoro(model_path, voices_path)
    for v in sorted(kokoro.get_voices()):
        print(v)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="?", help="Script line to synthesize")
    parser.add_argument("out", nargs="?", help="Output WAV path")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Kokoro voice name (default: {DEFAULT_VOICE})")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier (default: 1.0)")
    parser.add_argument("--lang", default="en-us", help="Language code (default: en-us)")
    parser.add_argument("--list-voices", action="store_true", help="List all available voices and exit")
    args = parser.parse_args()

    if args.list_voices:
        list_voices()
        return

    if not args.text or not args.out:
        parser.error("text and out are required unless --list-voices is passed")

    synthesize(args.text, args.out, voice=args.voice, speed=args.speed, lang=args.lang)


if __name__ == "__main__":
    main()
