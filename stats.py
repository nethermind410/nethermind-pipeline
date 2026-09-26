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
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
from store import atomic_write_json
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
    for p in (DATA / "packaging").glob("*.json"):
        if p.stem.startswith("_"):
            continue
        d = json.loads(p.read_text())
        for f in ("youtube_description", "tiktok_caption", "instagram_caption"):
            if d.get(f):
                keys[norm(d[f])] = p.stem
    return keys


STOP = set("the a an of in on is are was were to for and or it its this that with at by from be has have had your you "
           "why how what who can could would still we our they them not just his her their one more than into out about "
           "follow send friend thinks know nethermind shorts".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 and w not in STOP}


def load_fuzzy():
    """Each video's distinctive words (title + description + captions) for posts whose text was edited by hand."""
    docs = {}
    for p in (DATA / "cfg").glob("*.json"):                # every video: its script, plus packaging when it has one
        if p.stem.startswith(("_", "test")) or p.stem.endswith("_tiktok") or "__" in p.stem:
            continue
        try:
            c = json.loads(p.read_text())
        except Exception:
            continue
        if c.get("draft") or c.get("format") == "landscape":   # long-form repeats every chapter's words
            continue
        text = " ".join(s.get("text", "") for s in c.get("segments", [])) + " " + p.stem.replace("_", " ")
        pk = DATA / "packaging" / f"{p.stem}.json"
        if pk.exists():
            d = json.loads(pk.read_text())
            text += " " + " ".join(str(d.get(f, "")) for f in ("title", "youtube_description", "tiktok_caption",
                                                                "instagram_caption", "youtube_tags"))
        docs[p.stem] = words(text)
    df = {}
    for ws in docs.values():
        for w in ws:
            df[w] = df.get(w, 0) + 1
    return docs, df


def fuzzy_match(text, docs, df):
    """Link a post to a video only when its rare shared words clearly point at one video."""
    pw = words(text)
    scores = sorted(((sum(1 / df[w] for w in pw & ws), vid) for vid, ws in docs.items()), reverse=True)
    if not scores:
        return None
    best, vid = scores[0]
    runner = scores[1][0] if len(scores) > 1 else 0
    return vid if best >= 3.5 and best >= 2.0 * runner else None     # tuned on real posts: precise beats greedy


def siblings(nodes, match, hours=3):
    """A video goes out to every platform together: an unmatched post takes the video of the posts on OTHER
    platforms sent within `hours` of it — only when they all agree."""
    import datetime
    at = lambda n: datetime.datetime.fromisoformat(n["sentAt"].replace("Z", "+00:00"))
    out = dict(match)
    for n in nodes:
        if match.get(n["id"]):
            continue
        near = {match[o["id"]] for o in nodes if match.get(o["id"]) and o["channelService"] != n["channelService"]
                and abs((at(o) - at(n)).total_seconds()) <= hours * 3600}
        if len(near) == 1:
            out[n["id"]] = near.pop()
    return out


def main():
    env = buffer_post.load_env()
    org = gql(env, "{ account { organizations { id } } }")["account"]["organizations"][0]["id"]
    keys = load_packaging()
    fuzzy = load_fuzzy()
    posted = json.loads((DATA / "out" / "posted.json").read_text()) if (DATA / "out" / "posted.json").exists() else {}
    by_id = {pid: vid for vid, rec in posted.items() if isinstance(rec, dict)
             for pid in rec.get("posts", {}).values()}
    videos, unmatched, after, nodes = {}, 0, None, []
    for _ in range(10):  # up to 500 posts
        page = gql(env, QUERY, {"o": org, "after": after})["posts"]
        nodes += [e["node"] for e in page["edges"]]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    match = {n["id"]: by_id.get(n["id"]) or keys.get(norm(n["text"])) or fuzzy_match(n["text"], *fuzzy) for n in nodes}
    match = siblings(nodes, match)
    for n in nodes:
        vid = match.get(n["id"])
        if not vid:
            unmatched += 1
            continue
        m = {x["type"]: x["value"] for x in (n.get("metrics") or [])}
        videos.setdefault(vid, []).append({
            "platform": n["channelService"], "sentAt": n["sentAt"], "url": n["externalLink"],
            **{k: m.get(k) for k in KEEP}})
    sched = gql(env, QUERY.replace("status: [sent]", "status: [scheduled]").replace("direction: desc", "direction: asc"),
                {"o": org, "after": None})["posts"]["edges"]
    scheduled = [{"id": e["node"]["id"], "video": by_id.get(e["node"]["id"]) or keys.get(norm(e["node"]["text"])) or "unknown",
                  "platform": e["node"]["channelService"], "dueAt": e["node"].get("dueAt") or e["node"]["sentAt"]}
                 for e in sched]
    import datetime
    out = {"videos": videos, "scheduled": scheduled, "unmatched_posts": unmatched,
           "updated": datetime.datetime.now().isoformat(timespec="minutes")}
    atomic_write_json(DATA / "out" / "stats.json", out)
    # one line per run, so the app can draw trends: {"at": ..., "views": {video: total}}
    snap = {"at": out["updated"], "views": {v: int(sum(p["views"] or 0 for p in ps)) for v, ps in videos.items()}}
    with open(DATA / "out" / "stats_history.jsonl", "a") as f:
        f.write(json.dumps(snap) + "\n")
    rank = sorted(videos.items(), key=lambda kv: -sum(p["views"] or 0 for p in kv[1]))
    print(f"{'video':32} {'views':>8} {'shares':>7} {'saves':>6}")
    for vid, posts in rank:
        tot = lambda k: int(sum(p[k] or 0 for p in posts))
        print(f"{vid:32} {tot('views'):>8} {tot('shares'):>7} {tot('saves'):>6}")
    print(f"\n{unmatched} sent posts had no packaging file (older videos) — written to out/stats.json")


if __name__ == "__main__":
    sys.exit(main())
