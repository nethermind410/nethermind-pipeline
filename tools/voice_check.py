#!/usr/bin/env python3
"""
voice_check.py — check a script against Courtney's voice sheet (VOICE.md).

    python3 tools/voice_check.py scripts/some_script.md [more.md ...]

Reads only the spoken part of each file (between "## Script" and
"## Facts to check"; stage labels like **[COLD OPEN]** are ignored).

FAIL (exit 1)  a locked banned word, or "Gear Second"-style naming.
WARN           a word from the "would not sound like her" list, or a
               sentence longer than 28 words.
Also prints the word count and the running time at 167 words a minute,
the pace of "Why Did Luffy Stop Using 2nd Gear?" (1,629 words in 9:46).

Text only. No rendering, no network.
"""
import re
import sys

LOCKED = ["mate", "bastard", "bloke", "hype"]

# Courtney's own additions go here (and in VOICE.md) as she gives them.
COURTNEY_NEVER = []

SOUNDS_WRONG = [
    "delve", "tapestry", "testament", "realm", "unleash", "moreover",
    "furthermore", "crucial", "pivotal", "intricate", "journey", "landscape",
    "navigate", "unpack", "dive in", "deep dive", "in conclusion",
    "it's worth noting", "game-changer", "masterclass", "truly", "indeed",
    "ultimately", "arguably", "undeniably", "showcase", "elevate", "embark",
    "beloved", "captivating", "breathtaking", "whilst", "thus", "hence",
    "folks", "guys", "lads", "bro", "epic", "insane", "literally",
    "legendary",
]

GEAR_WRONG = re.compile(
    r"\bgear\s+(second|third|fourth|fifth|sixth|two|three|four|five|six)\b", re.I
)
WPM = 167
LONG_SENTENCE = 28


def spoken(text):
    if "## Script" in text:
        text = text.split("## Script", 1)[1]
    if "## Facts to check" in text:
        text = text.split("## Facts to check", 1)[0]
    return re.sub(r"\*\*\[.*?\]\*\*", "", text)


def find(words, body):
    hits = []
    for w in words:
        for m in re.finditer(r"(?<![\w'])" + re.escape(w) + r"(?![\w'])", body, re.I):
            line = body.count("\n", 0, m.start()) + 1
            hits.append((w, line, body.splitlines()[line - 1].strip()[:70]))
    return hits


def check(path):
    body = spoken(open(path, encoding="utf-8").read())
    n = len(body.split())
    print(f"\n{path}\n  {n} words, about {n / WPM:.1f} minutes")
    failed = False
    for w, _, ctx in find(LOCKED + COURTNEY_NEVER, body):
        print(f"  FAIL  banned word '{w}': {ctx}")
        failed = True
    for m in GEAR_WRONG.finditer(body):
        print(f"  FAIL  gear naming '{m.group(0)}' (use '2nd Gear' form)")
        failed = True
    for w, _, ctx in find(SOUNDS_WRONG, body):
        print(f"  WARN  '{w}' may not sound like her: {ctx}")
    for s in re.split(r"(?<=[.?!])\s+", " ".join(body.split())):
        k = len(s.split())
        if k > LONG_SENTENCE:
            print(f"  WARN  {k}-word sentence: {s[:70]}...")
    if not failed:
        print("  locked-word check: clean")
    return failed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(1 if any([check(p) for p in sys.argv[1:]]) else 0)
