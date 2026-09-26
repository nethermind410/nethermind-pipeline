#!/usr/bin/env python3
"""idea_demand.py — real demand evidence for ideas, from YouTube search (not a guess).

    python3 idea_demand.py              check ideas not checked in the last 7 days (max 15 per run)
    python3 idea_demand.py <slug>       check one idea now

For each idea: search YouTube for Shorts on that topic from the last 12 months, fetch their
real view counts, and store the median + the top 3 as proof. Written to out/idea_demand.json:
  {slug: {"median": int, "top": [{title, channel, views, url}], "results": n, "query": str, "at": iso}}
YouTube API cost: ~101 quota units per idea (10,000/day free).
"""
import datetime, json, re, statistics, sys, time
from pathlib import Path

import studio_api
from youtube import call
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)

OUT = DATA / "out" / "idea_demand.json"
STOP = set("the a an of in on is are was were to for and or it its this that with at by from be has have had your you "
           "why how what who can could would still we our they them".split())


def query_for(hook):
    words = [w for w in re.findall(r"[A-Za-z0-9']+", hook) if w.lower() not in STOP]
    return " ".join(words[:7])


def check(item):
    q = query_for(item["hook"])
    after = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = call("search", part="snippet", q=q, type="video", videoDuration="short", maxResults=15,
                 publishedAfter=after, order="relevance", relevanceLanguage="en")["items"]
    ids = [f["id"]["videoId"] for f in found]
    stats = call("videos", part="statistics,snippet", id=",".join(ids))["items"] if ids else []
    vids = sorted(({"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
                    "views": int(v["statistics"].get("viewCount", 0)), "url": f"https://www.youtube.com/shorts/{v['id']}"}
                   for v in stats), key=lambda v: -v["views"])
    return {"median": int(statistics.median([v["views"] for v in vids])) if vids else 0, "top": vids[:3],
            "results": len(vids), "query": q, "at": datetime.datetime.now().astimezone().isoformat(timespec="minutes")}


def main():
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    items = [i for s in studio_api.ideas()["sections"] for i in s["items"] if not i["made"] and not i["dismissed"]]
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        items = [i for i in items if i["slug"] == sys.argv[1]] or sys.exit("No open idea with that id.")
    else:
        week = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        items = [i for i in items if data.get(i["slug"], {}).get("at", "") < week][:15 if "--all" not in sys.argv else 200]
    for i in items:
        try:
            data[i["slug"]] = check(i)
            d = data[i["slug"]]
            print(f"{i['hook'][:60]}: median {d['median']:,} views across {d['results']} Shorts")
        except Exception as e:
            print(f"{i['hook'][:60]}: couldn't check ({e})")
        OUT.write_text(json.dumps(data, indent=1))
        time.sleep(0.3)
    print(f"Checked {len(items)} idea(s).")


if __name__ == "__main__":
    main()
