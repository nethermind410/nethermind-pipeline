#!/usr/bin/env python3
"""channel.py — one channel's settings and where its data lives. Every module reads these from here.

    python3 channel.py            print the active channel settings and data folder (never keys)

Where data lives (the "data folder"):
  NETHER_DATA unset   this code folder, exactly as the pipeline always worked (out/, cfg/, packaging/,
                      episodes/, assets/, tts/, TOPICS.md, LEARNINGS.md, .env)
  NETHER_DATA=<dir>   the same layout inside <dir> — a packaged app, a second channel, or the demo

Which settings:
  <data>/channel.json                       written by the setup wizard (gitignored, one per install)
  channel_nethermind.json (this folder)     the original channel's values — used only when NETHER_DATA
                                            is unset and there's no channel.json, so that install
                                            behaves exactly as before. Not shipped in the product.
  otherwise                                 neutral defaults (see channel.example.json)
"""
import json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ["NETHER_DATA"]).expanduser().resolve() if os.environ.get("NETHER_DATA") else HERE
OUT, CFG, PKG, EPS = DATA / "out", DATA / "cfg", DATA / "packaging", DATA / "episodes"
ASSETS, TTS, ENV_FILE = DATA / "assets", DATA / "tts", DATA / ".env"
TOPICS, LEARNINGS = DATA / "TOPICS.md", DATA / "LEARNINGS.md"
CONFIG = DATA / "channel.json"
LEGACY = HERE / "channel_nethermind.json"

DEFAULTS = {
    "name": "Your channel",                # shown in the app, prompts, media kit
    "app_name": "Nether",                  # the Mac app / notifications
    "owner": "you",                        # how prompts refer to the person reviewing drafts
    "about": "",                           # one line: what the channel makes (built from lanes when empty)
    "lanes": [],                           # lane ids the channel makes (see LANE_LIBRARY / custom_lanes)
    "off_lanes": [],                       # lane ids it has decided against (ideas there get flagged)
    "custom_lanes": {},                    # {id: {"label", "words": "space separated keywords", "copyright": bool}}
    "custom_names": [],                    # extra trademarked names/marks to block in AI art & thumbnails (see BLOCKED_NAMES)
    "title_subjects": [],                  # words a good title names (title pre-check)
    "hashtag": "",                         # the channel's own hashtag, without # (added to every description)
    "subscribe_line": "",                  # long-form description sign-off
    "long_hashtags": "",                   # long-form description hashtags
    "replies_about": "",                   # comment replies: what the channel is about
    "reply_voice": "direct, warm, short, a little playful; never corporate; no hashtags; no emoji spam (max one)",
    "narration_voice": "am_liam",          # Kokoro voice id
    "youtube_channel_id": "",              # UC… — for true YouTube numbers (optional)
    "buffer_channels": {"youtube": "", "instagram": "", "tiktok": ""},   # Buffer's channel ids (setup finds them)
    "dashboard_url": "",                   # a phone dashboard link shown in Settings (optional)
    "goals": {"subscribers": 1000, "shorts_views_90d": 10_000_000},
    "jarvis": {"enabled": False, "dir": "", "url": "http://127.0.0.1:8765"},
    "backup_dir": "~/Documents/Nether Backups",
    "backup_prefix": "nether",
    "launchd_label": "com.nether.daily",
    "demo": False,                         # a demo data folder: every number is sample data
    "setup_complete": False,               # the first-run wizard has finished
}
# Lanes the idea scouts can recognise. First match wins, so order matters (a Marvel animal video is Marvel).
# "copyright": art must be original (no official stills or footage exist that a channel may use).
LANE_LIBRARY = {
    "marvel": {"label": "Marvel & comics", "copyright": True,
               "words": "marvel wolverine hulk x-men xmen mutant avengers spider-man spiderman daredevil stan lee comic comics superhero villain dc batman superman"},
    "anime": {"label": "Anime", "copyright": True,
              "words": "anime manga dragon ball naruto pokemon pokémon ghibli one piece attack on titan titan goku studio"},
    "gaming": {"label": "Gaming", "copyright": True,
               "words": "game games gaming nintendo mario sonic minecraft zelda halo playstation xbox speedrun arcade pac-man pacman"},
    "space": {"label": "Space", "copyright": False,
              "words": "space star planet galaxy nasa black hole universe moon mars jupiter neptune kepler voyager telescope nebula"},
    "ocean": {"label": "Ocean", "copyright": False,
              "words": "ocean deep sea shark whale jellyfish octopus squid fish reef trench abyss"},
    "creature": {"label": "Creatures / real biology", "copyright": False,
                 "words": "superpower superpowers animal creature species worm beetle frog bird insect spider snake lizard shrimp"},
}
# Trademarked characters and studio marks AI art / thumbnails must never depict by name, costume or logo
# (narration may still mention them — commentary, not imagery). "custom_names" in channel.json adds more,
# per channel; this base list is never removed, only added to.
BLOCKED_NAMES = [
    "spider-man", "spiderman", "spider man", "wolverine", "hulk", "iron man", "captain america", "thor",
    "black panther", "black widow", "hawkeye", "avengers", "x-men", "xmen", "deadpool", "thanos", "loki",
    "doctor strange", "scarlet witch", "groot", "rocket raccoon", "venom", "daredevil", "punisher",
    "batman", "superman", "wonder woman", "the flash", "green lantern", "aquaman", "harley quinn", "joker",
    "catwoman", "robin", "justice league", "teen titans",
    "pikachu", "pokemon", "pokémon", "mario", "luigi", "princess peach", "bowser", "sonic the hedgehog",
    "zelda", "link (nintendo)", "kirby", "donkey kong", "master chief", "pac-man", "pacman",
    "naruto", "goku", "dragon ball", "one piece", "luffy", "attack on titan", "totoro", "pikmin",
    "mickey mouse", "minnie mouse", "donald duck", "spongebob", "star wars", "darth vader", "luke skywalker",
    "elsa", "frozen (disney)", "simba", "woody", "buzz lightyear",
]
_norm = lambda s: re.sub(r"[^a-z0-9]+", "", str(s or "").lower())
_BLOCKED_NORM_BASE = {_norm(n) for n in BLOCKED_NAMES}


def blocked_names():
    """The base list plus this channel's own additions (channel.json "custom_names": [...])."""
    extra = [str(n) for n in (get("custom_names") or []) if isinstance(n, str)]
    return BLOCKED_NAMES + extra


def blocked_name_in(text):
    """The first blocked trademarked name/mark found in `text` (case/punctuation-insensitive substring
    match on normalized alphanumerics — catches "Spider-Man", "spiderman", "SPIDER MAN"), or None.
    Used to keep AI-art prompts and thumbnail text to archetypes only; narration may still name characters."""
    norm = _norm(text)
    if not norm:
        return None
    names = _BLOCKED_NORM_BASE | {_norm(n) for n in (get("custom_names") or []) if isinstance(n, str)}
    for n in sorted(names, key=len, reverse=True):     # longest first so "spiderman" beats a shorter partial hit
        if n and n in norm:
            return n
    return None


_cache = {}


def _merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k].update(v)
        elif k in out:
            out[k] = v
    return out


def source():
    """Which settings file is active: 'channel.json', 'legacy' or 'defaults'."""
    if CONFIG.exists():
        return "channel.json"
    if DATA == HERE and LEGACY.exists():
        return "legacy"
    return "defaults"


def get(key=None):
    src = source()
    path = CONFIG if src == "channel.json" else LEGACY if src == "legacy" else None
    stamp = (src, path.stat().st_mtime if path else 0)
    if _cache.get("stamp") != stamp:
        try:
            saved = json.loads(path.read_text()) if path else {}
        except Exception:
            saved = {}
        _cache.update(stamp=stamp, cfg=_merge(DEFAULTS, saved))
    c = _cache["cfg"]
    return c if key is None else c.get(key)


def lane_defs():
    """Every lane the scouts know: the library, then this channel's own custom lanes."""
    out = {k: dict(v) for k, v in LANE_LIBRARY.items()}
    for k, v in (get("custom_lanes") or {}).items():
        if re.fullmatch(r"[a-z0-9_]{2,24}", str(k)) and isinstance(v, dict):
            out[k] = {"label": str(v.get("label") or k)[:40], "words": str(v.get("words") or k).lower()[:600],
                      "copyright": bool(v.get("copyright"))}
    return out


def lanes():
    return [l for l in get("lanes") or [] if l in lane_defs()]


def off_lanes():
    return [l for l in get("off_lanes") or [] if l in lane_defs()]


def lane_labels():
    d = lane_defs()
    return [d[l]["label"] for l in lanes()]


def about():
    c = get()
    return c["about"] or ("faceless, fact-checked YouTube Shorts on " + ", ".join(lane_labels()) + "." if lanes()
                          else "faceless, fact-checked YouTube Shorts.")


def whose():
    """"Courtney's" / "Your" — for prompts that mention the reviewer's notes or taste."""
    o = str(get("owner") or "").strip()
    return "Your" if o.lower() in ("", "you") else f"{o}'s"


def tag():
    """The channel hashtag without '#', lower-case; '' when the channel has none."""
    return re.sub(r"[^a-z0-9_]", "", str(get("hashtag") or "").lower())


def jarvis():
    j = get("jarvis") or {}
    return {"enabled": bool(j.get("enabled")), "dir": Path(os.path.expanduser(j["dir"])) if j.get("dir") else None,
            "url": (j.get("url") or "http://127.0.0.1:8765").rstrip("/")}


def is_demo():
    return bool(get("demo"))


def needs_setup():
    """A fresh install whose wizard hasn't finished. Never for the original install (legacy) or the demo."""
    return source() != "legacy" and not is_demo() and not get("setup_complete")


def public():
    """What the UI may see (no paths beyond the data folder's name, never keys)."""
    c = get()
    return {"name": c["name"], "app_name": c["app_name"], "about": about(), "lanes": lanes(), "lane_labels": lane_labels(), "hashtag": tag(),
            "dashboard_url": c["dashboard_url"], "jarvis": jarvis()["enabled"], "demo": is_demo(),
            "source": source(), "needs_setup": needs_setup(), "data": DATA.name}


def save(values):
    """Write channel.json (only known keys). Keeps whatever was already there."""
    cur = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    for k, v in values.items():
        if k in DEFAULTS:
            cur[k] = v
    DATA.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cur, indent=1, ensure_ascii=False) + "\n")
    _cache.clear()
    return get()


if __name__ == "__main__":
    print(f"data folder: {DATA}\nsettings:    {source()}")
    json.dump(get(), sys.stdout, indent=1, ensure_ascii=False)
    print()
