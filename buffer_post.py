#!/usr/bin/env python3
"""
buffer_post.py — Nethermind local posting pipeline.

Uploads a rendered video to Cloudflare R2 (for a stable public URL) and
schedules it on Buffer for Instagram / TikTok / YouTube, using the same
`createPost` GraphQL shape proven out in the Claude/Buffer cloud connector
sessions (see claude/buffer-integration-plan.md in the YOUTUBE project).

Setup (one-time):
    pip3 install boto3 requests python-dotenv
    Fill in .env in this folder (BUFFER_API_KEY + R2_* vars) — already done
    as of 2026-09-20.

Usage:
    # Post to Instagram + TikTok using a packaging JSON (see packaging_example.json)
    python3 buffer_post.py --video out/some_video.mp4 \\
        --tiktok-video out/some_video_tiktok.mp4 \\
        --packaging packaging/some_video.json \\
        --platforms instagram,tiktok

    # Quick one-off, captions inline
    python3 buffer_post.py --video out/some_video.mp4 \\
        --platforms tiktok \\
        --tiktok-caption "Caption here #nethermind"

Packaging JSON shape (matches claude/content-packaging-format.md):
    {
      "title": "...",
      "youtube_description": "...",
      "youtube_tags": "...",
      "tiktok_caption": "...",
      "instagram_caption": "...",
      "pinned_comment": "..."
    }
The pinned comment is NOT auto-posted — Buffer's Free plan doesn't support
first-comment automation. It's printed at the end as a manual to-do.

YouTube is opt-in here (--platforms youtube); ./post.sh <id> includes it. Buffer's
YouTube input has no tags field, so youtube_tags still go in by hand in Studio.
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests
import boto3
from botocore.client import Config

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"

CHANNELS = {
    "tiktok": "6aaf9711ea19ca0bde942596",
    "instagram": "6aaf96f6ea19ca0bde9424ed",
    "youtube": "6aaf9694ea19ca0bde942237",
}

BUFFER_GRAPHQL_URL = "https://api.buffer.com/graphql"


def load_env(strict=True):
    env = {}
    if not ENV_PATH.exists() and not strict:
        return env
    if not ENV_PATH.exists():
        print(f"ERROR: {ENV_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    required = ["BUFFER_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "R2_ENDPOINT", "R2_BUCKET", "R2_PUBLIC_BASE_URL"]
    missing = [k for k in required if not env.get(k)]
    if missing and strict:
        print(f"ERROR: missing from .env: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return env


def upload_to_r2(env, local_path: Path) -> str:
    """Upload a file to the R2 bucket and return its public URL."""
    s3 = boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    key = f"videos/{local_path.name}"
    content_type = mimetypes.guess_type(local_path.name)[0] or "video/mp4"
    print(f"Uploading {local_path.name} to R2 as {key} ...")
    s3.upload_file(str(local_path), env["R2_BUCKET"], key,
                    ExtraArgs={"ContentType": content_type})
    url = f"{env['R2_PUBLIC_BASE_URL'].rstrip('/')}/{key}"
    print(f"  -> {url}")
    return url


def buffer_create_post(env, channel_id: str, text: str, video_url: str,
                        mode: str, metadata: dict | None = None):
    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text dueAt } }
        ... on MutationError { message }
      }
    }
    """
    variables = {
        "input": {
            "text": text,
            "channelId": channel_id,
            "schedulingType": "automatic",
            "mode": mode,
            "assets": [
                {"video": {"url": video_url, "metadata": {"thumbnailOffset": 2000}}}
            ],
        }
    }
    if metadata:
        variables["input"]["metadata"] = metadata

    resp = requests.post(
        BUFFER_GRAPHQL_URL,
        headers={
            "Authorization": f"Bearer {env['BUFFER_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Buffer GraphQL error: {data['errors']}")
    result = data["data"]["createPost"]
    if result.get("message"):
        raise RuntimeError(f"Buffer rejected the post: {result['message']}")
    return result["post"]


POSTED = HERE / "out" / "posted.json"


def posted_record(vid):
    """out/posted.json: {video_id: {"at": iso, "posts": {platform: buffer_post_id}}}."""
    d = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    rec = d.get(vid) or {}
    return rec if isinstance(rec, dict) else {"at": rec, "posts": {}}  # old format was a bare timestamp


def save_posted(vid, platform, post_id):
    import datetime
    d = json.loads(POSTED.read_text()) if POSTED.exists() else {}
    rec = posted_record(vid)
    rec.setdefault("posts", {})[platform] = post_id
    rec["at"] = datetime.datetime.now().isoformat(timespec="minutes")
    d[vid] = rec
    POSTED.write_text(json.dumps(d, indent=1))


def main():
    ap = argparse.ArgumentParser(description="Post a Nethermind video to Buffer via R2 hosting.")
    ap.add_argument("--video", required=True, help="Path to the main video file (used for Instagram/YouTube).")
    ap.add_argument("--tiktok-video", help="Path to the short TikTok-cut video, if different from --video.")
    ap.add_argument("--platforms", default="instagram,tiktok",
                     help="Comma-separated: instagram,tiktok,youtube (default: instagram,tiktok — YouTube stays manual by default).")
    ap.add_argument("--packaging", help="Path to a packaging JSON (see module docstring for shape).")
    ap.add_argument("--instagram-caption", help="Override/standalone Instagram caption.")
    ap.add_argument("--tiktok-caption", help="Override/standalone TikTok caption.")
    ap.add_argument("--youtube-title", help="YouTube title (only used if youtube is in --platforms).")
    ap.add_argument("--youtube-category", default="24", help="YouTube category ID (default 24 = Entertainment).")
    ap.add_argument("--mode", default="addToQueue", choices=["addToQueue", "shareNow"],
                     help="addToQueue = Buffer's own recommended next slot (default). shareNow = publish immediately.")
    ap.add_argument("--record", metavar="VIDEO_ID",
                     help="Track per-platform post ids in out/posted.json and skip platforms already posted "
                          "(makes a re-run after a partial failure safe).")
    ap.add_argument("--force", action="store_true", help="With --record: post even to platforms already recorded.")
    ap.add_argument("--dry-run", action="store_true", help="Upload to R2 and print what would be posted, without calling Buffer.")
    args = ap.parse_args()

    env = load_env(strict=not args.dry_run)

    packaging = {}
    if args.packaging:
        packaging = json.loads(Path(args.packaging).read_text())

    ig_caption = args.instagram_caption or packaging.get("instagram_caption")
    tt_caption = args.tiktok_caption or packaging.get("tiktok_caption")
    yt_title = args.youtube_title or packaging.get("title")
    pinned = packaging.get("pinned_comment")

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: video not found: {video_path}", file=sys.stderr)
        sys.exit(1)
    tiktok_path = Path(args.tiktok_video) if args.tiktok_video else video_path
    if not tiktok_path.exists():
        print(f"ERROR: tiktok video not found: {tiktok_path}", file=sys.stderr)
        sys.exit(1)

    main_url = None
    tiktok_url = None
    results = []

    done = posted_record(args.record).get("posts", {}) if args.record else {}
    for platform in platforms:
        if platform in done and not args.force:
            print(f"Skipping {platform}: already posted as {done[platform]} (use --force to post again).")
            continue
        if platform not in CHANNELS:
            print(f"Skipping unknown platform: {platform}", file=sys.stderr)
            continue

        if platform == "tiktok":
            if tiktok_url is None:
                tiktok_url = upload_to_r2(env, tiktok_path) if not args.dry_run else f"[dry-run] {tiktok_path}"
            video_url = tiktok_url
            text = tt_caption or ""
            metadata = {"tiktok": {"isAiGenerated": True}}
        elif platform == "instagram":
            if main_url is None:
                main_url = upload_to_r2(env, video_path) if not args.dry_run else f"[dry-run] {video_path}"
            video_url = main_url
            text = ig_caption or ""
            metadata = {"instagram": {"type": "reel", "shouldShareToFeed": True, "isAiGenerated": True}}
        elif platform == "youtube":
            if main_url is None:
                main_url = upload_to_r2(env, video_path) if not args.dry_run else f"[dry-run] {video_path}"
            video_url = main_url
            text = packaging.get("youtube_description", "")
            metadata = {"youtube": {
                "title": yt_title or video_path.stem,
                "categoryId": args.youtube_category,
                "privacy": "public",
                "madeForKids": False,
                "isAiGenerated": True,
            }}

        if not text:
            print(f"WARNING: no caption/text for {platform} — posting with empty text.", file=sys.stderr)

        if args.dry_run:
            print(f"\n[DRY RUN] Would post to {platform} ({CHANNELS[platform]}):")
            print(f"  video_url: {video_url}")
            print(f"  text: {text[:200]}{'...' if len(text) > 200 else ''}")
            print(f"  metadata: {metadata}")
            continue

        print(f"\nPosting to {platform} (mode={args.mode}) ...")
        post = buffer_create_post(env, CHANNELS[platform], text, video_url, args.mode, metadata)
        print(f"  -> post id {post['id']}, due {post.get('dueAt')}")
        results.append((platform, post))
        if args.record:
            save_posted(args.record, platform, post["id"])

    if pinned and not args.dry_run and results:
        print(f"\nDon't forget — pinned comment to post manually once each video is live:\n  \"{pinned}\"")

    print("\nDone." if not args.dry_run else "\nDry run complete — nothing was posted.")


if __name__ == "__main__":
    main()
