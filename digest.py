#!/usr/bin/env python3
"""digest.py — the weekly digest's facts, computed from recorded numbers only.

    python3 digest.py        writes out/digest/<YYYY-MM-DD>.md (facts) and prints it

Compares the newest YouTube snapshot with the one closest to 7 days earlier
(out/youtube_history.jsonl), adds Buffer's TikTok/Instagram totals, and lists what was
posted this week. The Sunday task then adds a short "why" and next week's plan
underneath, clearly separated from these facts.
"""
import datetime, json
from pathlib import Path

import studio_api, studio_channel

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def main():
    hist = [h for h in studio_channel.history("youtube_history.jsonl") if h.get("videos")]  # per-video snapshots only
    yt = studio_channel.yt()
    if not hist or not yt:
        raise SystemExit("No YouTube history yet — run ./refresh.sh first.")
    now = hist[-1]
    t_now = studio_channel.parse(now["at"])
    target = t_now - datetime.timedelta(days=7)
    base = min(hist, key=lambda h: abs((studio_channel.parse(h["at"]) - target).total_seconds()))
    span = (t_now - studio_channel.parse(base["at"])).total_seconds() / 86400
    titles = {v["id"]: v["title"] for v in yt["videos"]}
    lines = [f"# Week to {t_now.date().isoformat()}", "",
             f"_Facts only, from YouTube (views, subscribers) and Buffer (TikTok, Instagram). Compared over {span:.1f} days._", ""]
    if span < 3:
        lines += ["Not enough history for a week-on-week comparison yet — these are the totals so far.", ""]
    total = sum(now["videos"].values())
    lines += ["## Growth",
              f"- Subscribers: {now['subscribers']:,}" + (f" ({now['subscribers'] - base['subscribers']:+,})" if span >= 3 else "")
              + f" — {now['subscribers'] / 10:.1f}% of the 1,000 needed",
              f"- YouTube views, all videos: {total:,}" + (f" ({total - sum(base['videos'].values()):+,} this week)" if span >= 3 else ""),
              f"- Shorts views, last 90 days (estimate): {now.get('shorts_90d', 0):,} of 10,000,000", ""]
    if span >= 3:
        gains = sorted(((vid, v - base["videos"].get(vid, 0)) for vid, v in now["videos"].items()), key=lambda x: -x[1])
        if gains and gains[0][1] > 0:
            lines += ["## Biggest movers on YouTube"] + [f"- {titles.get(vid, vid)}: {g:+,} views" for vid, g in gains[:3] if g > 0] + [""]
    perf = studio_api.performance()
    names = {"youtube": "YouTube", "tiktok": "TikTok", "instagram": "Instagram"}
    lines += ["## Videos made with Nethermind Studio, by platform (all time)"] + [
        f"- {names.get(k, k)}: {v:,} views" for k, v in sorted(perf["platforms"].items(), key=lambda x: -x[1])] + [""]
    week_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    posted = [v for v in yt["videos"] if studio_channel.parse(v["published"]) >= week_ago]
    lines += ["## Posted this week"] + ([f"- {v['title']} — {v['views']:,} views so far" for v in posted] or ["- Nothing new on YouTube."]) + [""]
    open_comments = [c for c in studio_channel.comments(studio_api.done_map())["comments"] if not c["done"]]
    lines += [f"## Waiting on you", f"- {len(open_comments)} comment(s) not marked handled",
              f"- {len(studio_api.today()['cards'])} item(s) on Today", ""]
    (OUT / "digest").mkdir(exist_ok=True)
    path = OUT / "digest" / f"{t_now.date().isoformat()}.md"
    path.write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
