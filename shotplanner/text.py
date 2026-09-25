"""
Script text handling: tokens, sentences, word counts, and matching each shot's
narration to its exact place in the script.

Tokens are whitespace-separated, the same split tts_kokoro.py uses for word
timings, so a shot's word_start/word_end lines up with the TTS words later.
"""
import re

_SENT_END = re.compile(r"[.!?][\"')\]”’]*$")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def tokens(text):
    return re.findall(r"\S+", text)


def is_word(tok):
    """A spoken word, not a stray dash or ellipsis token."""
    return any(c.isalnum() for c in tok)


def word_count(toks):
    return sum(1 for t in toks if is_word(t))


def match_key(tok):
    """Loose comparison key: case, curly quotes and edge punctuation ignored."""
    t = tok.translate(_QUOTES).lower()
    return re.sub(r"^[^\w]+|[^\w]+$", "", t)


def sentences(toks):
    """[(start, end_exclusive)] token ranges, one per sentence."""
    out, start = [], 0
    for i, t in enumerate(toks):
        if _SENT_END.search(t):
            out.append((start, i + 1))
            start = i + 1
    if start < len(toks):
        out.append((start, len(toks)))
    return out


def align_spans(script_toks, spans):
    """Place each narration span in the script, in order.

    Returns ([(word_start, word_end)], errors). The spans must join to make
    the whole script, with no gaps or overlaps. Matching ignores case, curly
    quotes and surrounding punctuation, so the script is always the source of
    the exact wording.
    """
    keys = [match_key(t) for t in script_toks]
    pos, ranges, errors = 0, [], []
    for n, span in enumerate(spans, 1):
        sk = [match_key(t) for t in tokens(span)]
        sk = [k for k in sk if k] or sk
        # compare only tokens that carry a word; stray dashes may differ
        j, i, ok = pos, 0, True
        while i < len(sk):
            while j < len(keys) and not keys[j]:
                j += 1
            if j >= len(keys) or keys[j] != sk[i]:
                ok = False
                break
            i += 1
            j += 1
        if not ok:
            expected = " ".join(script_toks[pos:pos + max(len(sk), 6)])
            errors.append(f"shot {n}: narration {span!r} does not continue the script; "
                          f"expected it to start with {expected!r}")
            return ranges, errors
        # swallow trailing punctuation-only tokens (e.g. a lone dash) into this span
        while j < len(keys) and not keys[j]:
            j += 1
        ranges.append((pos, j))
        pos = j
    if pos < len(script_toks):
        errors.append(f"script words not covered by any shot: {' '.join(script_toks[pos:])!r}")
    return ranges, errors
