#!/usr/bin/env python3
"""best_times.py — the best time of day to post, per platform.

    next_slot("youtube")   -> {"when": <aware datetime>, "why": "...", "confidence": "...",
                                "band": "Morning (6 AM-12)"|None, "source": "..."}

Two sources, tried in this order:

  1. Your own numbers — studio_ext_insights.verdict() for that platform, once it has
     enough measured videos (MIN_VIDEOS) and one time band clearly outperforms the rest.
     Uses the middle of that winning band. The channel's own data beats general research.
  2. General research (used until #1 has enough data to call a pattern):
       YouTube Shorts   11:00  Buffer's analysis of 1.8M YouTube videos: Shorts do best
                                late morning (~11 AM-12 PM), with a second peak around
                                4 PM; Monday, Wednesday and Friday are the strongest days.
       TikTok           19:00  A 2026 study of 2M+ TikTok posts from 92,000 accounts found
                                6-8 PM performs best, with Sunday evening the strongest slot.
       Instagram Reels  12:00  A common finding across creator research: 10 AM-2 PM,
                                Tuesday through Thursday, performs best for Reels.

Pure and cheap: no network calls, no AI calls — just the clock and whatever
studio_ext_insights has already computed from local files (out/*.json).
"""
import datetime

MIN_AHEAD_MINUTES = 20  # if today's slot is closer than this, push it to tomorrow instead

RESEARCH = {
    "youtube": (11, 0, "Buffer's analysis of 1.8M YouTube videos: Shorts do best late morning "
                        "(~11 AM-12 PM), with a second peak around 4 PM; Monday, Wednesday and "
                        "Friday are the strongest days."),
    "tiktok": (19, 0, "A 2026 study of 2M+ TikTok posts from 92,000 accounts found 6-8 PM "
                       "performs best, with Sunday evening the strongest single slot."),
    "instagram": (12, 0, "A common finding across creator research: 10 AM-2 PM, Tuesday "
                          "through Thursday, performs best for Reels."),
}


def _now(now=None):
    if now is None:
        return datetime.datetime.now().astimezone()
    return now.astimezone() if now.tzinfo else now.astimezone()


def _at(now, hour, minute):
    """Today at hour:minute, unless that's under MIN_AHEAD_MINUTES away — then tomorrow."""
    cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if (cand - now).total_seconds() < MIN_AHEAD_MINUTES * 60:
        cand += datetime.timedelta(days=1)
    return cand


def _own_numbers(platform, now):
    """The channel's own measured best band for `platform`, if studio_ext_insights has
    called one (enough videos, one band clearly ahead). None otherwise — falls back to
    general research. All local file reads; no network."""
    try:
        import studio_ext_insights as insights
    except Exception:
        return None
    try:
        data = insights.times()
    except Exception:
        return None
    row = next((p for p in data["platforms"] if p["key"] == platform), None)
    verdict = row and row.get("verdict")
    if not verdict or not verdict.get("call"):
        return None
    lo, hi = insights.BANDS[verdict["band"]][:2]
    mid_hour = (lo + hi) // 2
    b = data["bands"][verdict["band"]]
    return {
        "when": _at(now, mid_hour, 0),
        "why": verdict["text"],
        "confidence": "your own numbers",
        "band": f"{b['name']} ({b['hours']})",
        "source": "your channel's measured posting history",
    }


def next_slot(platform, now=None):
    """The next good time to post to `platform`: today if at least MIN_AHEAD_MINUTES
    away, otherwise tomorrow. Prefers the channel's own measured pattern over the
    general research default, once studio_ext_insights has called one."""
    now = _now(now)
    own = _own_numbers(platform, now)
    if own:
        return own
    hour, minute, why = RESEARCH.get(platform, RESEARCH["youtube"])
    return {
        "when": _at(now, hour, minute),
        "why": why,
        "confidence": "general research",
        "band": None,
        "source": "general research (no channel default yet — too few videos measured, or no band clearly ahead)",
    }


def local_words(dt, now=None):
    """Plain words for a slot's date: "today 11:00 AM" / "tomorrow 7:00 PM" / "Mon 5 Oct, 11:00 AM"."""
    now = _now(now)
    if dt.date() == now.date():
        day = "today"
    elif dt.date() == (now.date() + datetime.timedelta(days=1)):
        day = "tomorrow"
    else:
        day = dt.strftime("%a %-d %b")
    return f"{day} {dt.strftime('%-I:%M %p')}"


def describe(platform, now=None):
    """next_slot(), plus plain-words "local" time and a "label" for display."""
    now = _now(now)
    slot = next_slot(platform, now)
    slot = dict(slot, local=local_words(slot["when"], now))
    slot["platform"] = platform
    return slot
