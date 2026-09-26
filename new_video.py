#!/usr/bin/env python3
"""
new_video.py — scaffold a new video config so you never start from a blank file.

    python3 new_video.py fact     my_topic  # narrated fact/story video (8 beats)
    python3 new_video.py ice      my_topic  # iceberg chart (5 tiers, no media needed)
    python3 new_video.py creature my_topic  # creature reveal (8 beats)
    python3 new_video.py hero     my_topic  # superhero-trivia reveal, Gemini art (8 beats)

Writes cfg/<id>.json. Narration voice defaults to ELEVENLABS_VOICE_ID in .env;
set a per-video "voice_id" in the config to override it.

Fill in the text and the "src" image names, then either drop your own photos
in assets/ or, for "hero" (and any "kb" segment with a "prompt"), run:

    python3 gen_visuals.py cfg/<id>.json
    python3 make_short.py cfg/<id>.json
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)

FACT = {
    "palette": {"accent": [200, 120, 255], "accent2": [255, 140, 40]},
    "credit": "SOURCE: ", "score": "space",
    "hook": {"lines": [["LINE ONE", "w"], ["LINE TWO", "w"], ["THE PAYOFF.", "a"]], "size": 146, "y": 600},
    "end": {"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "NEXT:", "THE NEXT VIDEO'S TOPIC"]},
    "segments": [
        {"id": "s1", "text": "Spoken hook — say the same thing the hook text says.", "hook": True,
         "vis": {"t": "kb", "src": "IMAGE.jpg", "prompt": "describe the scene, or delete this key and drop your own photo in assets/", "z0": 1.38, "z1": 1.14, "cx": 0.5, "cy": 0.45}, "gap": 0.18},
        {"id": "s2", "text": "Set up the situation in one sentence.",
         "vis": {"t": "kb", "src": "IMAGE.jpg", "prompt": "same scene, different framing", "z0": 1.1, "z1": 1.32, "cx": 0.5, "cy": 0.45}, "gap": 0.15},
        {"id": "s3", "text": "First hard number goes here.",
         "vis": {"t": "kb", "src": "IMAGE.jpg", "z0": 1.34, "z1": 1.12, "cx": 0.45, "cy": 0.4},
         "hero": {"at": 2, "lines": ["THE", "NUMBER"], "col": "a2", "y": 390, "size": 130}, "gap": 0.15},
        {"id": "s4", "text": "The mechanism — how it actually works.",
         "vis": {"t": "kb", "src": "IMAGE2.jpg", "prompt": "describe the mechanism scene", "z0": 1.05, "z1": 1.34, "cx": 0.5, "cy": 0.5}, "gap": 0.15},
        {"id": "s5", "text": "Escalate. The bigger, stranger consequence.",
         "vis": {"t": "kb", "src": "IMAGE2.jpg", "z0": 1.32, "z1": 1.08, "cx": 0.5, "cy": 0.48},
         "hero": {"at": 4, "lines": ["SECOND", "NUMBER"], "col": "a", "y": 390, "size": 132}, "gap": 0.15},
        {"id": "s6", "text": "The honest caveat — what we do not actually know.",
         "vis": {"t": "kb", "src": "IMAGE.jpg", "z0": 1.16, "z1": 1.36, "cx": 0.56, "cy": 0.5}, "gap": 0.15},
        {"id": "s7", "text": "Land it. One short line that reframes everything above.",
         "vis": {"t": "kb", "src": "IMAGE.jpg", "z0": 1.3, "z1": 1.06, "cx": 0.5, "cy": 0.45}, "gap": 0.3}
    ]}

ICE = {
    "palette": {"accent": [110, 220, 255], "accent2": [255, 140, 40]},
    "credit": "EACH TIER LABELLED BY HOW CERTAIN IT IS", "score": "deep", "cap_y": 1130,
    "hook": {"lines": [["THE TOPIC", "w"], ["ICEBERG", "a"]], "size": 150, "y": 700},
    "iceberg": {"tiers": [
        {"label": "Tier One", "depth": "COMMON KNOWLEDGE", "col": "a"},
        {"label": "Tier Two", "depth": "LESS KNOWN", "col": "a"},
        {"label": "Tier Three", "depth": "OBSCURE", "col": "a"},
        {"label": "Tier Four", "depth": "DISTURBING", "col": "a2"},
        {"label": "Tier Five", "depth": "THE BOTTOM", "col": "a2"}]},
    "end": {"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "NEXT:", "THE NEXT VIDEO'S TOPIC"]},
    "segments": [
        {"id": "h", "text": "One line describing what the five tiers are.", "hook": True,
         "vis": {"t": "ice", "tier": 0}, "gap": 0.2},
        {"id": "t1", "text": "Tier one fact.", "vis": {"t": "ice", "tier": 0}, "gap": 0.2},
        {"id": "t2", "text": "Tier two fact.", "vis": {"t": "ice", "tier": 1}, "gap": 0.2},
        {"id": "t3", "text": "Tier three fact.", "vis": {"t": "ice", "tier": 2}, "gap": 0.2},
        {"id": "t4", "text": "Tier four fact.", "vis": {"t": "ice", "tier": 3}, "gap": 0.2},
        {"id": "t5", "text": "Tier five fact — the worst one.", "vis": {"t": "ice", "tier": 4}, "gap": 0.25},
        {"id": "e", "text": "One closing line.", "vis": {"t": "ice", "tier": 4}, "gap": 0.3}
    ]}

CREATURE = json.loads(json.dumps(FACT))
CREATURE["palette"] = {"accent": [255, 90, 120], "accent2": [255, 180, 60]}
CREATURE["score"] = "deep"
CREATURE["credit"] = "IMAGES: NOAA OCEAN EXPLORATION"
CREATURE["end"] = {"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "FOLLOW FOR MORE:", "THINGS THAT SHOULDN'T EXIST"]}

# Superhero-trivia reveal. Every "src" needs a "prompt" — there's no public-domain
# photo path for this vertical, so gen_visuals.py (Gemini) is the only source.
# Keep prompts to archetypes/poses/palettes, not named characters or exact
# costume/logo details — see gen_visuals.py's STYLE_PREFIX for why.
HERO = json.loads(json.dumps(FACT))
HERO["palette"] = {"accent": [255, 60, 70], "accent2": [60, 140, 255]}
HERO["score"] = "deep"
HERO["credit"] = "ART: ORIGINAL, AI-GENERATED"
HERO["end"] = {"at": 1.4, "lines": ["SUBSCRIBE FOR MORE", "NEXT:", "THE NEXT VIDEO'S TOPIC"]}
for _s in HERO["segments"]:
    if _s["vis"]["t"] == "kb" and "prompt" not in _s["vis"]:
        _s["vis"]["prompt"] = "describe this beat's scene — archetype, pose, palette, mood, no named characters"

TPL = {"fact": FACT, "ice": ICE, "creature": CREATURE, "hero": HERO}

if len(sys.argv) < 3 or sys.argv[1] not in TPL:
    print(__doc__); sys.exit(1)
kind, vid = sys.argv[1], sys.argv[2]
cfg = json.loads(json.dumps(TPL[kind]))
cfg = {"id": vid, "file": vid, **cfg}
path = os.path.join(DATA, "cfg", vid + ".json")
if os.path.exists(path):
    print(f"refusing to overwrite {path}"); sys.exit(1)
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(cfg, open(path, "w"), indent=1)
print(f"wrote {path}\n\nNow: fill in the text + image names, then\n  python3 make_short.py cfg/{vid}.json")
