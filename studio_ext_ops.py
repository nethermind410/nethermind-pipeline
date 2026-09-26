"""Studio extension: backups and health alerts (Settings).

GET  /api/ops             last backup + recent alerts
POST /api/backup/run      back up now
POST /api/backup/show     reveal the newest backup in Finder
POST /api/alerts/clear    {"id"} → tick an alert off
"""
import json, subprocess

import alerts
import backup


def status():
    try:
        last = json.loads(backup.LOG.read_text())
    except Exception:
        last = None
    return {"backup": last, "folder": str(backup.DEST), "alerts": alerts.load().get("alerts", [])[:12]}


def run(_b):
    i = backup.run()
    return {"ok": True, "reply": f"Backed up {i['files']} files ({i['bytes'] / 1e6:.1f} MB).", "backup": i}


def show(_b):
    newest = sorted(backup.DEST.glob(f"{backup.PRE}-*.zip"))
    subprocess.run(["open", "-R", str(newest[-1])] if newest else ["open", str(backup.DEST)])
    return {"ok": True}


GET = {"/api/ops": status}
POST = {"/api/backup/run": run, "/api/backup/show": show, "/api/alerts/clear": lambda b: alerts.clear(str(b.get("id", "")))}
