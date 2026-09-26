#!/usr/bin/env python3
"""backup.py — zip the channel's irreplaceable state to its backup folder (channel.json "backup_dir";
~/Documents/Nethermind Backups on the original install). Keeps the newest 14.

    .venv/bin/python backup.py            back up now
    .venv/bin/python backup.py --if-due   only if today's backup is missing (the app runs this daily)

Backs up: cfg/, packaging/, LEARNINGS.md, TOPICS.md, inspiration/, out/*.json, out/*.jsonl, out/daily/,
out/feedback/, out/digest/, out/intel/, out/learning/, out/nether.db. Never videos, assets, voice files or .env (those are re-makeable or secret).
Writes a summary to out/backups.json.
"""
import datetime, json, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
OUT = DATA / "out"
import channel
DEST = Path(channel.get("backup_dir")).expanduser()
PRE = channel.get("backup_prefix") or "nether"
LOG = OUT / "backups.json"
KEEP = 14


def files():
    for d in ("cfg", "packaging", "inspiration", "out/daily", "out/feedback", "out/digest",
              "out/intel", "out/learning"):   # NETHER scorecards + your decisions: what it has learned
        p = DATA / d
        if p.is_dir():
            yield from (f for f in sorted(p.rglob("*")) if f.is_file() and f.name != ".env" and not f.name.startswith("."))
    for name in ("LEARNINGS.md", "TOPICS.md"):
        if (DATA / name).is_file():
            yield DATA / name
    for pat in ("*.json", "*.jsonl", "nether.db"):
        yield from sorted(OUT.glob(pat))


def run():
    DEST.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    path, tmp = DEST / f"{PRE}-{today}.zip", DEST / f".{PRE}-{today}.zip.part"
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files():
            z.write(f, f.relative_to(DATA)); n += 1
    tmp.replace(path)
    old = sorted(DEST.glob(f"{PRE}-*.zip"))[:-KEEP]
    for f in old:
        f.unlink()
    info = {"last": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "path": str(path),
            "bytes": path.stat().st_size, "files": n, "kept": len(sorted(DEST.glob(f"{PRE}-*.zip"))), "folder": str(DEST)}
    LOG.write_text(json.dumps(info, indent=1) + "\n")
    return info


def due():
    return not (DEST / f"{PRE}-{datetime.date.today().isoformat()}.zip").exists()


if __name__ == "__main__":
    if "--if-due" in sys.argv and not due():
        sys.exit(0)
    i = run()
    print(f"Backed up {i['files']} files ({i['bytes'] / 1e6:.1f} MB) to {i['path']}")
