#!/usr/bin/env python3
"""undo_post.py — take a video's posts back out of Buffer's queue.

    python3 undo_post.py <id>            remove every still-scheduled post for <id>
    python3 undo_post.py <id> --dry-run  show what would be removed

Only posts recorded in out/posted.json AND still "scheduled" in Buffer are deleted;
anything already sent is left alone (it's live — delete it on the platform itself).
"""
import json, sys
from pathlib import Path

import buffer_post
from stats import gql

HERE = Path(__file__).resolve().parent
POSTED = HERE / "out" / "posted.json"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    vid, dry = sys.argv[1], "--dry-run" in sys.argv
    posted = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    rec = posted.get(vid)
    if not isinstance(rec, dict) or not rec.get("posts"):
        sys.exit(f"Nothing recorded as posted for {vid}.")
    env = buffer_post.load_env()
    kept = {}
    for platform, pid in rec["posts"].items():
        status = gql(env, "query($i: PostId!) { post(input: {id: $i}) { status } }", {"i": pid})["post"]["status"]
        if status != "scheduled":
            print(f"{platform}: already {status} — left as is")
            kept[platform] = pid
            continue
        if dry:
            print(f"{platform}: would remove scheduled post {pid}")
            kept[platform] = pid
            continue
        res = gql(env, "mutation($i: PostId!) { deletePost(input: {id: $i}) { ... on DeletePostSuccess { id } "
                       "... on VoidMutationError { message } } }", {"i": pid})["deletePost"]
        if res.get("message"):
            print(f"{platform}: Buffer refused — {res['message']}")
            kept[platform] = pid
        else:
            print(f"{platform}: removed from the queue")
    if dry:
        return
    if kept:
        rec["posts"] = kept
        posted[vid] = rec
    else:
        posted.pop(vid, None)
    POSTED.write_text(json.dumps(posted, indent=1))
    print("Done." if not kept else "Done — some posts were already live and were kept.")


if __name__ == "__main__":
    main()
