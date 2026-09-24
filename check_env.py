#!/usr/bin/env python3
"""check_env.py — list which .env keys are set. Prints names only, never values."""
from pathlib import Path

NEEDED = {
    "Posting (Buffer)": ["BUFFER_API_KEY"],
    "Video hosting (Cloudflare R2)": ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT",
                                      "R2_BUCKET", "R2_PUBLIC_BASE_URL"],
    "AI art (Cloudflare Workers AI)": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
}

env = {}
p = Path(__file__).resolve().parent / ".env"
if p.exists():
    for line in p.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
else:
    print(".env not found")

for group, keys in NEEDED.items():
    print(group)
    for k in keys:
        print(f"  {'OK     ' if env.get(k) else 'MISSING'}  {k}")

# names only — helps spot typos like "export BUFFER_API_KEY" or "BUFFER_KEY"
wanted = {k for ks in NEEDED.values() for k in ks}
extra = [k for k in env if k not in wanted]
if extra:
    print("\nOther names found in .env (check for typos):")
    for k in extra:
        print(f"  {k!r}{'  <- empty value' if not env[k] else ''}")
empty = [k for k in wanted if k in env and not env[k]]
for k in empty:
    print(f"\n{k} is in the file but has nothing after the '='")
