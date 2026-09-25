#!/usr/bin/env python3
"""alerts.py — turn Settings health checks into Mac notifications, once per change.

check(health) compares the checks with the last saved state (out/alerts.json) and returns the new
alerts: a check that starts failing ("broke") or starts working again ("fixed"). The first run only
records the state, so opening the app never floods you with old problems.
"""
import datetime, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "out" / "alerts.json"
KEEP = 30


def load():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"state": None, "alerts": []}


def check(health, now=None):
    now = now or datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    s = load()
    cur = {h["name"]: bool(h["ok"]) for h in health}
    new = []
    if s.get("state") is not None:
        for h in health:
            was = s["state"].get(h["name"])
            if was is True and not h["ok"]:
                new.append({"id": f"{now}|{h['name']}", "at": now, "name": h["name"], "kind": "broke", "detail": h.get("detail", "")})
            elif was is False and h["ok"]:
                new.append({"id": f"{now}|{h['name']}", "at": now, "name": h["name"], "kind": "fixed", "detail": h.get("detail", "")})
    s["state"] = cur
    s["alerts"] = (new[::-1] + s.get("alerts", []))[:KEEP]
    STATE.write_text(json.dumps(s, indent=1) + "\n")
    return new


def message(a):
    if a["kind"] == "fixed":
        return f"{a['name']} is working again", "Fixed"
    return f"{a['name']} needs a look", a["detail"] or "Open Settings in Nethermind"


def clear(alert_id):
    s = load()
    s["alerts"] = [a for a in s.get("alerts", []) if a["id"] != alert_id]
    STATE.write_text(json.dumps(s, indent=1) + "\n")
    return {"ok": True}
