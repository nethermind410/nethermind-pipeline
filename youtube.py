#!/usr/bin/env python3
"""youtube.py — true channel numbers straight from the YouTube Data API (public data, API key).

    python3 youtube.py            refresh out/youtube.json (+ one line in out/youtube_history.jsonl)
    python3 youtube.py --comments also pull recent public comments on the newest videos

Uses YOUTUBE_API_KEY from .env and the channel id Buffer reports for the connected channel.
What this can and can't see (be honest in the UI):
  * subscriberCount is public but ROUNDED by YouTube to 3 significant figures.
  * view counts are lifetime per video. YouTube's official "Shorts views in the last 90 days"
    (the monetisation figure) lives only in YouTube Studio → Earn; we estimate it as views on
    Shorts published in the last 90 days, and label it as an estimate.
"""
import datetime, json, re, sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
from store import atomic_write_json
OUT = DATA / "out"
import channel
CHANNEL_ID = channel.get("youtube_channel_id")  # channel.json (the original install: Buffer's connected YouTube channel)
API = "https://www.googleapis.com/youtube/v3/"


def key():
    for line in (DATA / ".env").read_text().splitlines():
        if line.strip().startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("YOUTUBE_API_KEY missing from .env")


def call(endpoint, **params):
    r = requests.get(API + endpoint, params={**params, "key": key()}, timeout=30)
    if r.status_code != 200:
        msg = r.json().get("error", {}).get("message", r.text[:200])
        raise RuntimeError(f"YouTube API {endpoint}: {r.status_code} {re.sub('<[^>]+>', '', msg)}")
    return r.json()


def seconds(iso):  # PT1M5S -> 65
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return (int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)) if m else 0


def fetch(with_comments=False):
    if not CHANNEL_ID:
        sys.exit("No YouTube channel id yet — add it in Settings → Your channel.")
    ch = call("channels", part="snippet,statistics,contentDetails", id=CHANNEL_ID)["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        page = call("playlistItems", part="contentDetails", playlistId=uploads, maxResults=50,
                    **({"pageToken": token} if token else {}))
        ids += [i["contentDetails"]["videoId"] for i in page["items"]]
        token = page.get("nextPageToken")
        if not token or len(ids) >= 200:
            break
    videos = []
    for i in range(0, len(ids), 50):
        for v in call("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))["items"]:
            st = v["statistics"]
            videos.append({
                "id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"],
                "thumb": v["snippet"]["thumbnails"].get("medium", {}).get("url"),
                "seconds": seconds(v["contentDetails"]["duration"]),
                "views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
                "url": f"https://www.youtube.com/shorts/{v['id']}"})
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=90)
    shorts = [v for v in videos if v["seconds"] <= 180]  # Shorts can be up to 3 minutes
    recent = [v for v in shorts if datetime.datetime.fromisoformat(v["published"].replace("Z", "+00:00")) >= cutoff]
    s = ch["statistics"]
    data = {
        "fetched": now.astimezone().isoformat(timespec="minutes"),
        "channel": {"id": CHANNEL_ID, "title": ch["snippet"]["title"],
                    "handle": ch["snippet"].get("customUrl", ""),
                    "avatar": ch["snippet"]["thumbnails"].get("default", {}).get("url"),
                    "subscribers": int(s.get("subscriberCount", 0)), "subscribers_hidden": s.get("hiddenSubscriberCount", False),
                    "views": sum(v["views"] for v in videos),  # per-video counts update faster than the channel total
                    "views_channel_counter": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0))},
        "shorts_90d": {"views": sum(v["views"] for v in recent), "videos": len(recent),
                       "first": min((v["published"] for v in recent), default=None)},
        "videos": sorted(videos, key=lambda v: v["published"], reverse=True),
    }
    if with_comments:
        data["comments"] = comments(data["videos"][:12])
    else:  # keep the last comment pull so a plain refresh doesn't wipe the inbox
        old = json.loads((OUT / "youtube.json").read_text()) if (OUT / "youtube.json").exists() else {}
        if old.get("comments"):
            data["comments"] = old["comments"]
    return data


def comments(videos):
    out = []
    for v in videos:
        if not v["comments"]:
            continue
        try:
            page = call("commentThreads", part="snippet", videoId=v["id"], maxResults=20, order="time", textFormat="plainText")
        except RuntimeError:
            continue  # comments disabled etc.
        for t in page["items"]:
            c = t["snippet"]["topLevelComment"]["snippet"]
            out.append({"id": t["id"], "video": v["id"], "video_title": v["title"], "author": c["authorDisplayName"],
                        "text": c["textDisplay"][:1000], "likes": c.get("likeCount", 0), "at": c["publishedAt"],
                        "replies": t["snippet"].get("totalReplyCount", 0),
                        "link": f"https://www.youtube.com/watch?v={v['id']}&lc={t['id']}"})
    return sorted(out, key=lambda c: c["at"], reverse=True)


def main():
    data = fetch("--comments" in sys.argv)
    atomic_write_json(OUT / "youtube.json", data)
    snap = {"at": data["fetched"], "subscribers": data["channel"]["subscribers"], "views": data["channel"]["views"],
            "shorts_90d": data["shorts_90d"]["views"], "videos": {v["id"]: v["views"] for v in data["videos"]}}
    with open(OUT / "youtube_history.jsonl", "a") as f:
        f.write(json.dumps(snap) + "\n")
    c = data["channel"]
    print(f"{c['title']}: {c['subscribers']:,} subscribers (rounded by YouTube), {c['views']:,} lifetime views, "
          f"{c['videos']} videos. Shorts posted in last 90 days: {data['shorts_90d']['videos']} with "
          f"{data['shorts_90d']['views']:,} views. Comments cached: {len(data.get('comments', []))}.")


if __name__ == "__main__":
    main()
