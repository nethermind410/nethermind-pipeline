#!/usr/bin/env python3
"""watchlist.py — follow specific YouTube channels: their latest uploads, median views and breakouts.

    .venv/bin/python watchlist.py          check every channel in watchlist.json → out/watchlist.json

Cheap on quota (YouTube Data API, key from .env via youtube.py — never printed):
  * a handle is resolved ONCE with channels?forHandle= (1 unit) and its id + uploads playlist cached;
  * each check then costs 1 unit for all channels' stats, and 2 units per channel
    (playlistItems for the latest ~10 uploads, videos.list for their views/durations).
A handle that doesn't resolve stays listed as "not found" — never guessed. Read-only: nothing is posted.
A breakout is an upload with ≥3× that channel's median views for its format (Short-length ≤3 min vs long)
over the same latest uploads — YouTube's API has no Shorts flag, so length is the honest proxy.
"""
import datetime, json, re, statistics, sys
from pathlib import Path

import youtube

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CONFIG = HERE / "watchlist.json"            # the channels you follow (tracked)
RESULT = OUT / "watchlist.json"             # the last check (ids cached here too)
HISTORY = OUT / "watchlist_history.jsonl"   # one line per check: each channel's median and per-video views
HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")
LATEST, BREAKOUT_X, SHORT_MAX = 10, 3, 180   # YouTube Shorts can run up to 3 minutes


def jload(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="minutes")


def clean_handle(h):
    h = str(h or "").strip()
    h = re.sub(r"^https?://(www\.)?youtube\.com/", "", h).split("/")[0].split("?")[0]
    h = h if h.startswith("@") else "@" + h
    if not HANDLE_RE.fullmatch(h):
        raise ValueError("That doesn't look like a YouTube handle (e.g. @mandjtv).")
    return h


def config():
    return jload(CONFIG, {"channels": []}).get("channels", [])


def save_config(chs):
    d = jload(CONFIG, {})
    d["channels"] = chs
    CONFIG.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


def add(handle, note=""):
    h = clean_handle(handle)
    chs = config()
    if any(c["handle"].lower() == h.lower() for c in chs):
        raise ValueError(f"{h} is already on the watchlist.")
    chs.append({"handle": h, "note": str(note or "").strip()[:120]})
    save_config(chs)
    return {"ok": True, "handle": h}


def remove(handle):
    h = clean_handle(handle)
    chs = config()
    left = [c for c in chs if c["handle"].lower() != h.lower()]
    if len(left) == len(chs):
        raise ValueError(f"{h} isn't on the watchlist.")
    save_config(left)
    return {"ok": True}


def resolve(handle, cache):
    """handle → {"id", "uploads"} (cached), or None when YouTube has no such handle."""
    key = handle.lower()
    if key in cache:
        return cache[key]
    items = youtube.call("channels", part="id,contentDetails", forHandle=handle).get("items") or []
    if not items:
        return None                              # not cached: a handle that appears later is picked up next check
    cache[key] = {"id": items[0]["id"], "uploads": items[0]["contentDetails"]["relatedPlaylists"]["uploads"]}
    return cache[key]


def latest(uploads):
    page = youtube.call("playlistItems", part="contentDetails", playlistId=uploads, maxResults=LATEST)
    ids = [i["contentDetails"]["videoId"] for i in page.get("items", [])]
    if not ids:
        return []
    vids = []
    for v in youtube.call("videos", part="snippet,statistics,contentDetails", id=",".join(ids)).get("items", []):
        secs = youtube.seconds(v["contentDetails"].get("duration"))
        vids.append({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"],
                     "views": int(v.get("statistics", {}).get("viewCount", 0)), "seconds": secs,
                     "kind": "short" if 0 < secs <= SHORT_MAX else "long",
                     "live": v["snippet"].get("liveBroadcastContent", "none") != "none",
                     "url": (f"https://www.youtube.com/shorts/{v['id']}" if 0 < secs <= SHORT_MAX
                             else f"https://www.youtube.com/watch?v={v['id']}")})
    return sorted(vids, key=lambda v: v["published"], reverse=True)


def summarise(vids):
    """Median views overall and per format; each upload is compared with the median of its own format
    (Shorts vs long videos behave differently) when that format has ≥3 uploads, else with the overall median."""
    counted = [v for v in vids if not v["live"]]
    med = statistics.median([v["views"] for v in counted]) if counted else 0
    by_kind = {k: statistics.median([v["views"] for v in counted if v["kind"] == k])
               for k in ("short", "long") if sum(v["kind"] == k for v in counted) >= 3}
    for v in vids:
        base = by_kind.get(v["kind"], med)
        v["vs"] = v["kind"] if v["kind"] in by_kind else "all"
        v["x"] = round(v["views"] / base, 1) if base and not v["live"] else None
    brk = [v for v in counted if v["x"] and v["x"] >= BREAKOUT_X]
    return med, by_kind, sorted(brk, key=lambda v: -v["x"])


def check(log=print):
    old = jload(RESULT, {})
    cache = old.get("resolved", {})
    rows, errors = [], []
    for c in config():
        h = c["handle"]
        row = {"handle": h, "note": c.get("note", ""), "status": "ok"}
        try:
            r = resolve(h, cache)
            if not r:
                row["status"] = "not found"
                log(f"{h}: not found on YouTube")
            else:
                row.update(id=r["id"], uploads=r["uploads"], videos=latest(r["uploads"]))
        except Exception as e:                   # one bad channel never sinks the rest
            row.update(status="error", error=re.sub(r"key=[^&\s]+", "key=…", str(e))[:200])
            errors.append(h)
            log(f"{h}: {row['error']}")
        rows.append(row)
    ids = [r["id"] for r in rows if r.get("id")]
    stats = {}
    for i in range(0, len(ids), 50):             # one call refreshes every channel's title + subscriber count
        for ch in youtube.call("channels", part="snippet,statistics", id=",".join(ids[i:i + 50])).get("items", []):
            stats[ch["id"]] = ch
    for r in rows:
        ch = stats.get(r.get("id"))
        if ch:
            s = ch["statistics"]
            r.update(title=ch["snippet"]["title"], custom=ch["snippet"].get("customUrl", ""),
                     avatar=ch["snippet"]["thumbnails"].get("default", {}).get("url"),
                     subscribers=None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0)),
                     total_videos=int(s.get("videoCount", 0)), url=f"https://www.youtube.com/channel/{r['id']}")
        if r.get("videos") is not None:
            r["median"], r["median_by_kind"], r["breakouts"] = summarise(r["videos"])
            r["breakouts"] = [v["id"] for v in r["breakouts"]]
    data = {"checked": now(), "channels": rows, "resolved": cache, "errors": errors,
            "rule": f"A breakout is at least {BREAKOUT_X}× the channel's median views for that format (Shorts or long) "
                    f"over its latest {LATEST} uploads"}
    OUT.mkdir(exist_ok=True)
    RESULT.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    with open(HISTORY, "a") as f:
        f.write(json.dumps({"at": data["checked"], "channels": {r["handle"]: {
            "median": r.get("median"), "subscribers": r.get("subscribers"),
            "views": {v["id"]: v["views"] for v in r.get("videos") or []}} for r in rows if r["status"] == "ok"}}) + "\n")
    for r in rows:
        if r["status"] == "ok":
            log(f"{r['handle']} ({r.get('title', '?')}): median {int(r['median']):,} views over {len(r['videos'])} uploads, "
                f"{len(r['breakouts'])} breakout(s)")
    return data


if __name__ == "__main__":
    check()
    sys.exit(0)
