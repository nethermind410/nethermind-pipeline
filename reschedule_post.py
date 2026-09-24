#!/usr/bin/env python3
"""reschedule_post.py — move a still-scheduled Buffer post to a new time (the calendar's drag).

    python3 reschedule_post.py <buffer_post_id> <iso-datetime> [--dry-run]

Only touches posts that are still "scheduled"; anything already sent is refused.
"""
import sys

import buffer_post
from stats import gql


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pid, when, dry = sys.argv[1], sys.argv[2], "--dry-run" in sys.argv
    env = buffer_post.load_env()
    post = gql(env, "query($i: PostId!) { post(input: {id: $i}) { status dueAt channelService } }", {"i": pid})["post"]
    if post["status"] != "scheduled":
        sys.exit(f"That post is already {post['status']}, so it can't be moved.")
    if dry:
        return print(f"Would move {post['channelService']} post from {post['dueAt']} to {when}.")
    res = gql(env, """mutation($i: PostId!, $d: DateTime!) { editPost(input: {id: $i, dueAt: $d, mode: customScheduled,
              schedulingType: automatic}) { ... on PostActionSuccess { post { dueAt } } ... on MutationError { message } } }""",
              {"i": pid, "d": when})["editPost"]
    if res.get("message"):
        sys.exit(f"Buffer refused: {res['message']}")
    print(f"Moved {post['channelService']} post to {res['post']['dueAt']}.")


if __name__ == "__main__":
    main()
