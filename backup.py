#!/usr/bin/env python3
"""backup.py — zip Nethermind's irreplaceable state to ~/Documents/Nethermind Backups (keeps the newest 14).

    .venv/bin/python backup.py            back up now
    .venv/bin/python backup.py --if-due   only if today's backup is missing (the app runs this daily)

Backs up: cfg/, packaging/, LEARNINGS.md, TOPICS.md, inspiration/, out/*.json, out/*.jsonl, out/daily/,
out/feedback/, out/digest/. Never videos, assets, voice files or .env (those are re-makeable or secret).
Writes a summary to out/backups.json.
"""
import datetime, json, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DEST = Path.home() / "Documents" / "Nethermind Backups"
LOG = OUT / "backups.json"
KEEP = 14


def files():
    for d in ("cfg", "packaging", "inspiration", "out/daily", "out/feedback", "out/digest"):
        p = HERE / d
        if p.is_dir():
            yield from (f for f in sorted(p.rglob("*")) if f.is_file() and f.name != ".env" and not f.name.startswith("."))
    for name in ("LEARNINGS.md", "TOPICS.md"):
        if (HERE / name).is_file():
            yield HERE / name
    for pat in ("*.json", "*.jsonl"):
        yield from sorted(OUT.glob(pat))


def run():
    DEST.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    path, tmp = DEST / f"nethermind-{today}.zip", DEST / f".nethermind-{today}.zip.part"
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files():
            z.write(f, f.relative_to(HERE)); n += 1
    tmp.replace(path)
    old = sorted(DEST.glob("nethermind-*.zip"))[:-KEEP]
    for f in old:
        f.unlink()
    info = {"last": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "path": str(path),
            "bytes": path.stat().st_size, "files": n, "kept": len(sorted(DEST.glob("nethermind-*.zip"))), "folder": str(DEST)}
    LOG.write_text(json.dumps(info, indent=1) + "\n")
    return info


def due():
    return not (DEST / f"nethermind-{datetime.date.today().isoformat()}.zip").exists()


if __name__ == "__main__":
    if "--if-due" in sys.argv and not due():
        sys.exit(0)
    i = run()
    print(f"Backed up {i['files']} files ({i['bytes'] / 1e6:.1f} MB) to {i['path']}")
