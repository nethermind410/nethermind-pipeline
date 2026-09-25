"""
Duration estimates made before any narration is recorded.

  seconds = spoken words / words_per_second + pauses at punctuation

DEFAULT_WPS (2.6 words/s, about 155 wpm) is a typical narration pace. Kokoro
am_liam at speed=1.0 has not been measured yet: after the first real render,
set "words_per_second" in the brief to the measured value (words / seconds
from tts/<id>/*.json). Estimates only plan the edit and the clip lengths to
request; make_short.py always uses the real TTS timing.
"""
import math

from .text import is_word

DEFAULT_WPS = 2.6
PAUSE_CLAUSE = 0.18    # , ; : and dashes
PAUSE_SENTENCE = 0.35  # . ! ?

# Clip lengths video models commonly accept. The request is rounded up to one of these.
MODEL_CLIP_LENGTHS = (3, 4, 5, 6, 8, 10)
TRIM_HANDLE_S = 0.5    # extra length so the edit can trim the start and end

MIN_SHOT_S = 1.2       # shorter than this is hard to read on screen
HARD_MIN_SHOT_S = 0.8  # shorter than this is an error


def estimate(toks, wps=DEFAULT_WPS):
    words = sum(1 for t in toks if is_word(t))
    pause = 0.0
    for t in toks:
        if t.rstrip("\"')”’").endswith((".", "!", "?")):
            pause += PAUSE_SENTENCE
        elif t.endswith((",", ";", ":", "—", "–")) or t in ("—", "–", "-", "--"):
            pause += PAUSE_CLAUSE
    return round(words / wps + pause, 2)


def generate_length(est_s):
    need = est_s + TRIM_HANDLE_S
    for L in MODEL_CLIP_LENGTHS:
        if L >= need:
            return float(L)
    return float(math.ceil(need))
