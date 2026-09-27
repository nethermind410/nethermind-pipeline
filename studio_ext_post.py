"""Studio extension: Post — what "Schedule" actually does, before you press it.

GET /api/post/plan/<id>   per-platform best-time-to-post plan for one video: only the
                           platforms that video will actually go to (landscape videos are
                           YouTube only — see post.sh), each with its planned time, plain-
                           words "why", and a confidence ("general research" vs "your own
                           numbers"). Same source as post.sh --when best / buffer_post.py;
                           nothing here posts, uploads, or calls Buffer.
"""
import json
import re

import best_times
from channel import DATA

CFG = DATA / "cfg"
PLAT_NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}


def _platforms_for(cfg):
    return ["youtube"] if cfg.get("format") == "landscape" else ["youtube", "instagram", "tiktok"]


def plan(vid):
    if not re.match(r"^[a-z0-9_]+$", vid or ""):
        raise ValueError("Bad video id.")
    f = CFG / f"{vid}.json"
    if not f.exists():
        raise ValueError("No such video.")
    cfg = json.loads(f.read_text())
    rows = []
    for key in _platforms_for(cfg):
        slot = best_times.describe(key)
        rows.append({
            "key": key, "name": PLAT_NAMES[key], "when": slot["when"].isoformat(),
            "local": slot["local"], "why": slot["why"], "confidence": slot["confidence"],
            "band": slot["band"], "label": f"{PLAT_NAMES[key]} — {slot['local']}",
        })
    return {"id": vid, "platforms": rows}


GET_PREFIX = {"/api/post/plan/": plan}
