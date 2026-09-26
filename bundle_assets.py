#!/usr/bin/env python3
"""bundle_assets.py — pack the exact assets one video uses and put them on R2.

    python3 bundle_assets.py <id>              build + upload bundles/<id>.tar.gz
    python3 bundle_assets.py <id> --local      build only (out/<id>_assets.tar.gz)

assets/ is gitignored, and AI art can't be regenerated identically, so the
GitHub render workflow downloads this bundle instead of re-fetching/generating.
Contents: every "src" in cfg/<id>.json plus the packaging thumbnail src. Fonts
and public-domain NASA/NOAA files are fetched by the workflow separately.
"""
import json, sys, tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
A = DATA / "assets"


def files_for(vid):
    cfg = json.loads((DATA / "cfg" / f"{vid}.json").read_text())
    names = {s["vis"]["src"] for s in cfg["segments"] if s.get("vis", {}).get("src")}
    pkg = DATA / "packaging" / f"{vid}.json"
    if pkg.exists():
        t = json.loads(pkg.read_text()).get("thumbnail") or {}
        if t.get("src"):
            names.add(t["src"])
    missing = sorted(n for n in names if not (A / n).exists())
    if missing:
        sys.exit(f"missing from assets/: {', '.join(missing)}")
    return sorted(names)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    vid = sys.argv[1]
    out = DATA / "out" / f"{vid}_assets.tar.gz"
    names = files_for(vid)
    with tarfile.open(out, "w:gz") as tar:
        for n in names:
            tar.add(A / n, arcname=n)
    print(f"  bundled {len(names)} files -> {out.name} ({out.stat().st_size // 1024} KB)")
    if "--local" in sys.argv:
        return
    import buffer_post  # reuses its .env loading + R2 client
    env = buffer_post.load_env()
    import boto3
    from botocore.client import Config
    s3 = boto3.client("s3", endpoint_url=env["R2_ENDPOINT"],
                      aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                      config=Config(signature_version="s3v4"), region_name="auto")
    key = f"bundles/{vid}.tar.gz"
    s3.upload_file(str(out), env["R2_BUCKET"], key, ExtraArgs={"ContentType": "application/gzip"})
    print(f"  uploaded -> {env['R2_PUBLIC_BASE_URL'].rstrip('/')}/{key}")


if __name__ == "__main__":
    main()
