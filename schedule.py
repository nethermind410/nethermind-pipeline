#!/usr/bin/env python3
"""schedule.py — install, remove, or inspect the Daily run's LaunchAgent (~/Library/LaunchAgents), the
same one install_daily.sh sets up: daily.py at a chosen time, plus a 90-minute catch-up if the Mac was
asleep or the morning run failed. Used by studio_ext_connect.py (Settings → Connections → Daily schedule).

    python3 schedule.py status            print status as JSON (never touches launchd)
    python3 schedule.py install [HH:MM]   install/update (default 07:00)
    python3 schedule.py remove            stop it

Never run this against a real Mac from a test — it edits ~/Library/LaunchAgents and calls launchctl.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

import channel

HERE = Path(__file__).resolve().parent


def _label():
    return str(channel.get("launchd_label") or "com.nether.daily")


def _plist_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{_label()}.plist"


def _python():
    venv = HERE / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else (shutil.which("python3") or sys.executable)


def _catchup(hour, minute):
    m = (hour * 60 + minute + 90) % (24 * 60)
    return m // 60, m % 60


def _last_run():
    try:
        import orchestrator
        d = orchestrator.last("control", "daily")
    except Exception:
        d = None
    return {"at": d["started"], "status": d["status"]} if d else None


def status():
    """Never fails, never touches launchd — safe to poll from the UI."""
    p = _plist_path()
    installed = p.exists()
    hour, minute = 7, 0
    if installed:
        try:
            import plistlib
            data = plistlib.loads(p.read_bytes())
            ivals = data.get("StartCalendarInterval") or []
            if ivals:
                hour, minute = int(ivals[0].get("Hour", 7)), int(ivals[0].get("Minute", 0))
        except Exception:
            pass
    return {"installed": installed, "time": f"{hour:02d}:{minute:02d}", "label": _label(), "last": _last_run()}


def install(time_str="07:00", *, run=subprocess.run):
    """Write the plist and (re)load it with launchctl — mirrors install_daily.sh exactly.
    Pass run=<stub> in tests so nothing real is touched."""
    try:
        hour, minute = (int(x) for x in str(time_str).strip().split(":", 1))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except Exception:
        raise ValueError("Give a time like 07:00.")
    label, plist = _label(), _plist_path()
    data_dir = os.environ.get("NETHER_DATA", "")
    logdir = (Path(data_dir) if data_dir else HERE) / "out"
    logdir.mkdir(parents=True, exist_ok=True)
    plist.parent.mkdir(parents=True, exist_ok=True)
    run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
    ch, cm = _catchup(hour, minute)
    env_line = f"<key>NETHER_DATA</key><string>{data_dir}</string>" if data_dir else ""
    plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array><string>{_python()}</string><string>{HERE / "daily.py"}</string></array>
  <key>WorkingDirectory</key><string>{HERE}</string>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>
    <dict><key>Hour</key><integer>{ch}</integer><key>Minute</key><integer>{cm}</integer></dict>
  </array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>{env_line}</dict>
  <key>StandardOutPath</key><string>{logdir}/daily.log</string>
  <key>StandardErrorPath</key><string>{logdir}/daily.log</string>
</dict></plist>
''')
    r = run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], capture_output=True, text=True)
    if getattr(r, "returncode", 0) not in (0, None):
        raise ValueError(f"launchctl said: {(r.stderr or r.stdout or '').strip()[:200]}")
    return status()


def remove(*, run=subprocess.run):
    run(["launchctl", "bootout", f"gui/{os.getuid()}/{_label()}"], capture_output=True)
    _plist_path().unlink(missing_ok=True)
    return status()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "install":
        print(json.dumps(install(sys.argv[2] if len(sys.argv) > 2 else "07:00")))
    elif cmd == "remove":
        print(json.dumps(remove()))
    else:
        print(json.dumps(status()))
