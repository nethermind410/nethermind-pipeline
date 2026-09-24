#!/usr/bin/env python3
"""stats.py — pull performance for every sent Buffer post and tie it back to a video.

    python3 stats.py            writes out/stats.json and prints a leaderboard

Each sent post is matched to a video by the Buffer post id recorded in
out/posted.json (post.sh --live writes it), falling back to caption text. Only posts that went out through Buffer are seen
(a manual YouTube upload won't appear). Buffer refreshes metrics a few times a day.
"""
import json, re, sys
from pathlib import Path

import requests
import buffer_post

HERE = Path(__file__).resolve().parent
QUERY = """
query($o: OrganizationId!, $after: String) {
  posts(first: 50, after: $after, input: {organizationId: $o, filter: {status: [sent]},
        sort: [{field: dueAt, direction: desc}]}) {
    edges { node { id channelService sentAt dueAt externalLink text metrics { type value } } }
    pageInfo { hasNextPage endCursor }
  }
}"""
KEEP = ["views", "reactions", "comments", "shares", "saves", "averageTimeWatched", "follows"]


def gql(env, query, variables=None):
    r = requests.post(buffer_post.BUFFER_GRAPHQL_URL, timeout=60,
                      headers={"Authorization": f"Bearer {env['BUFFER_API_KEY']}"},
                      json={"query": query, "variables": variables or {}})
    r.raise_for_status()
    d = r.json()
    if d.get("errors"):
        raise RuntimeError(d["errors"])
    return d["data"]


def norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()[:60]


def load_packaging():
    keys = {}
    for p in (HERE / "packaging").glob("*.json"):
        if p.stem.startswith("_"):
            continue
        d = json.loads(p.read_text())
        for f in ("youtube_description", "tiktok_caption", "instagram_caption"):
            if d.get(f):
                keys[norm(d[f])] = p.stem
    return keys


def main():
    env = buffer_post.load_env()
    org = gql(env, "{ account { organizations { id } } }")["account"]["organizations"][0]["id"]
    keys = load_packaging()
    posted = json.loads((HERE / "out" / "posted.json").read_text()) if (HERE / "out" / "posted.json").exists() else {}
    by_id = {pid: vid for vid, rec in posted.items() if isinstance(rec, dict)
             for pid in rec.get("posts", {}).values()}
    videos, unmatched, after = {}, 0, None
    for _ in range(10):  # up to 500 posts
        page = gql(env, QUERY, {"o": org, "after": after})["posts"]
        for e in page["edges"]:
            n = e["node"]
            vid = by_id.get(n["id"]) or keys.get(norm(n["text"]))
            if not vid:
                unmatched += 1
                continue
            m = {x["type"]: x["value"] for x in (n.get("metrics") or [])}
            videos.setdefault(vid, []).append({
                "platform": n["channelService"], "sentAt": n["sentAt"], "url": n["externalLink"],
                **{k: m.get(k) for k in KEEP}})
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    sched = gql(env, QUERY.replace("status: [sent]", "status: [scheduled]").replace("direction: desc", "direction: asc"),
                {"o": org, "after": None})["posts"]["edges"]
    scheduled = [{"id": e["node"]["id"], "video": by_id.get(e["node"]["id"]) or keys.get(norm(e["node"]["text"])) or "unknown",
                  "platform": e["node"]["channelService"], "dueAt": e["node"].get("dueAt") or e["node"]["sentAt"]}
                 for e in sched]
    import datetime
    out = {"videos": videos, "scheduled": scheduled, "unmatched_posts": unmatched,
           "updated": datetime.datetime.now().isoformat(timespec="minutes")}
    (HERE / "out" / "stats.json").write_text(json.dumps(out, indent=1))
    # one line per run, so the app can draw trends: {"at": ..., "views": {video: total}}
    snap = {"at": out["updated"], "views": {v: int(sum(p["views"] or 0 for p in ps)) for v, ps in videos.items()}}
    with open(HERE / "out" / "stats_history.jsonl", "a") as f:
        f.write(json.dumps(snap) + "\n")
    rank = sorted(videos.items(), key=lambda kv: -sum(p["views"] or 0 for p in kv[1]))
    print(f"{'video':32} {'views':>8} {'shares':>7} {'saves':>6}")
    for vid, posts in rank:
        tot = lambda k: int(sum(p[k] or 0 for p in posts))
        print(f"{vid:32} {tot('views'):>8} {tot('shares'):>7} {tot('saves'):>6}")
    print(f"\n{unmatched} sent posts had no packaging file (older videos) — written to out/stats.json")


if __name__ == "__main__":
    sys.exit(main())
