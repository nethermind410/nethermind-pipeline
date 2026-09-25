#!/usr/bin/env python3
"""
calibrate_tts.py — measure the narration voice so the Shot Planner's timing
estimates match real audio.

    python3 tools/calibrate_tts.py [--voice am_liam] [--limit 40]

Synthesizes the narration segments in cfg/*.json with the same Kokoro call
tts_kokoro.py uses, then fits
    seconds = spoken letters / letters_per_second + sentence_ends * pause
by least squares and prints the values to put in shotplanner/timing.py
(DEFAULT_LPS, PAUSE_SENTENCE) or in a brief ("letters_per_second").
Needs the Kokoro setup from tts_kokoro.py (kokoro-onnx, soundfile, model files).
Takes about 1.5 s of CPU per segment.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tts_kokoro  # noqa: E402
from shotplanner.text import _ends_sentence, tokens  # noqa: E402
from shotplanner.timing import DEFAULT_LPS, PAUSE_SENTENCE, estimate, generate_length, spoken_letters  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default=tts_kokoro.DEFAULT_VOICE)
    ap.add_argument("--limit", type=int, default=0, help="only the first N segments (0 = all)")
    a = ap.parse_args()

    texts = []
    for p in sorted(glob.glob(os.path.join(ROOT, "cfg", "*.json"))):
        if p.endswith("_tiktok.json"):  # same text as the main cut
            continue
        texts += [s["text"] for s in json.load(open(p))["segments"] if s.get("text")]
    if a.limit:
        texts = texts[:a.limit]

    k = tts_kokoro._kokoro_lazy()
    real, feats = [], []
    for i, t in enumerate(texts, 1):
        samples, sr = k.create(t, voice=a.voice, speed=1.0, lang="en-us")  # same call as tts_kokoro.synthesize
        real.append(len(samples) / sr)
        tk = tokens(t)
        feats.append((spoken_letters(tk), sum(_ends_sentence(x, tk[j + 1] if j + 1 < len(tk) else None)
                                            for j, x in enumerate(tk))))
        print(f"\r  {i}/{len(texts)} segments", end="", flush=True)
    print()
    y, A = np.array(real), np.array(feats, float)
    (inv_lps, pause), *_ = np.linalg.lstsq(A, y, rcond=None)
    fit = A @ [inv_lps, pause]
    cur = np.array([estimate(tokens(t)) for t in texts])
    ratio = y / fit
    print(f"voice {a.voice}: {len(texts)} segments, {y.sum():.1f} s of audio")
    print(f"  current  ({DEFAULT_LPS} letters/s, pause {PAUSE_SENTENCE}s): mean abs err {np.abs(cur - y).mean():.2f}s, "
          f"total {(cur.sum() / y.sum() - 1) * 100:+.1f}%")
    print(f"  measured ({1 / inv_lps:.1f} letters/s, pause {pause:.2f}s): mean abs err {np.abs(fit - y).mean():.2f}s, "
          f"worst real/estimate {ratio.max():.2f}")
    covered = np.mean([generate_length(e) >= r for e, r in zip(cur, y)]) * 100
    print(f"  clip requests (generate_length) long enough for the real audio: {covered:.0f}% of segments"
          + ("" if covered == 100 else "  <- raise timing.SAFETY"))
    print(f"\n  -> set DEFAULT_LPS = {1 / inv_lps:.1f} and PAUSE_SENTENCE = {max(pause, 0):.2f} in shotplanner/timing.py")


if __name__ == "__main__":
    main()
