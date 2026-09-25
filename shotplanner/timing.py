"""
Duration estimates made before any narration is recorded.

  seconds = spoken letters / letters_per_second + pause per sentence end
  (a digit counts as DIGIT_LETTERS letters: "1996" is said "nineteen ninety-six")

Calibrated 2026-09-25 against real Kokoro audio (am_liam, speed=1.0, the
tts_kokoro.py call): all 104 narration segments in cfg/ (1,696 words, 545 s),
fitted by least squares. Mean error is 0.21 s per segment, and 97% of
estimates land within 1 s. The older word-count estimate (2.6 words/s) came
out 36% too long. Letters beat words because Kokoro's audio length follows
how much text there is to pronounce.
Kokoro makes no measurable pause at commas, so there is no clause pause.

Change the voice or speed? Re-run tools/calibrate_tts.py and put the printed
values in the brief ("letters_per_second") or here. make_short.py always
uses the real TTS timing; these estimates plan the edit and size the clips.
"""
import math

from .text import _ends_sentence

DEFAULT_LPS = 14.8     # spoken letters per second, Kokoro am_liam @ speed 1.0
DIGIT_LETTERS = 5      # letters a digit adds when spoken
PAUSE_SENTENCE = 0.08  # . ! ? (extra, beyond the letters)

# Clip lengths video models commonly accept. The request is rounded up to one of these.
MODEL_CLIP_LENGTHS = (3, 4, 5, 6, 8, 10)
TRIM_HANDLE_S = 0.5    # extra length so the edit can trim the start and end
SAFETY = 1.1           # real audio ran up to 1.25x the estimate; x1.1 + 0.5 s covered all 104 measured segments

MIN_SHOT_S = 1.2       # shorter than this is hard to read on screen
HARD_MIN_SHOT_S = 0.8  # shorter than this is an error
SOFT_MAX_SHOT_S = 6.0  # longer than this breaks the "new picture about every 2 s" rule (README rule 6)
MAX_SHOT_S = 10.0      # longer than the longest clip most video models offer: an error, split the shot


def spoken_letters(toks):
    return sum(sum(c.isalpha() for c in t) + DIGIT_LETTERS * sum(c.isdigit() for c in t) for t in toks)


def estimate(toks, lps=DEFAULT_LPS):
    # the last token of a span is judged without its next word, so a span ending in "Dr." still pauses
    ends = sum(_ends_sentence(t, toks[i + 1] if i + 1 < len(toks) else None) for i, t in enumerate(toks))
    return round(spoken_letters(toks) / lps + ends * PAUSE_SENTENCE, 2)


def generate_length(est_s):
    need = est_s * SAFETY + TRIM_HANDLE_S
    for L in MODEL_CLIP_LENGTHS:
        if L >= need:
            return float(L)
    return float(math.ceil(need))
