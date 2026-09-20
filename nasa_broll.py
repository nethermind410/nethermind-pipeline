#!/usr/bin/env python3
"""
nasa_broll.py — free B-roll sourcing for Nnethermind, replacing vidIQ's generic AI broll generator.

Uses NASA's Image and Video Library API (images-api.nasa.gov). No API key required —
confirmed live in a Claude session on 2026-09-21 (316 real hits on a plain "nebula" query).
All NASA imagery is U.S. government work: public domain, free for any use including
commercial, with one courtesy rule — don't use NASA's insignia/logo in a way that implies
NASA endorsement of the video.

This is a better fit than a generic AI broll tool for this channel specifically, since the
stated sourcing practice (per START-HERE.md) is real verified NASA/NOAA imagery, not
AI-generated visuals.

Usage:

    python nasa_broll.py "immortal jellyfish" --media-type image --limit 5 --download ./broll
    python nasa_broll.py "great attractor" --media-type image,video --limit 10

Without --download, just prints the matching NASA IDs, titles, and preview URLs so you can
pick before pulling full files.
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SEARCH_URL = "https://images-api.nasa.gov/search"
ASSET_URL = "https://images-api.nasa.gov/asset/{nasa_id}"


def search(query: str, media_type: str = "image", limit: int = 10) -> list[dict]:
    params = {"q": query, "media_type": media_type}
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)

    items = data.get("collection", {}).get("items", [])
    results = []
    for item in items[:limit]:
        meta = item.get("data", [{}])[0]
        links = item.get("links", [{}])
        preview = links[0].get("href") if links else None
        results.append({
            "nasa_id": meta.get("nasa_id"),
            "title": meta.get("title"),
            "description": meta.get("description", "")[:200],
            "media_type": meta.get("media_type"),
            "date_created": meta.get("date_created"),
            "preview_url": preview,
        })
    return results


def get_best_asset_url(nasa_id: str) -> str | None:
    """Fetch the full asset manifest for a NASA ID and return the highest-quality file URL."""
    url = ASSET_URL.format(nasa_id=nasa_id)
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.load(resp)
    items = data.get("collection", {}).get("items", [])
    if not items:
        return None
    # Prefer ~orig, then ~large, else first item
    for suffix in ("~orig.jpg", "~orig.png", "~orig.mp4", "~large.jpg", "~large.png"):
        for item in items:
            href = item.get("href", "")
            if href.endswith(suffix):
                return href
    return items[0].get("href")


def download(nasa_id: str, out_dir: Path) -> Path | None:
    asset_url = get_best_asset_url(nasa_id)
    if not asset_url:
        print(f"  no downloadable asset found for {nasa_id}", file=sys.stderr)
        return None
    filename = asset_url.split("/")[-1]
    out_path = out_dir / filename
    urllib.request.urlretrieve(asset_url, out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="Search term, e.g. 'immortal jellyfish' or 'great attractor'")
    parser.add_argument("--media-type", default="image", help="Comma-separated: image,video (default: image)")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--download", metavar="DIR", help="Download the matched assets into this directory")
    args = parser.parse_args()

    results = search(args.query, media_type=args.media_type, limit=args.limit)
    if not results:
        print("No results. Try a broader query.")
        return

    for r in results:
        print(f"[{r['nasa_id']}] {r['title']} ({r['media_type']}, {r['date_created']})")
        if r["description"]:
            print(f"    {r['description']}")

    if args.download:
        out_dir = Path(args.download)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nDownloading {len(results)} asset(s) to {out_dir}/ ...")
        for r in results:
            path = download(r["nasa_id"], out_dir)
            if path:
                print(f"  saved {path}")


if __name__ == "__main__":
    main()
