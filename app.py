#!/usr/bin/env python3
"""app.py — Nethermind as a Mac app (launched by /Applications/Nethermind.app).

Opens one native window on the Studio UI and quietly runs what it needs behind it:
  * the Studio server (studio.py) on 127.0.0.1:8766
  * Jarvis's brain on :8765 if it isn't already running — started with the Claude
    app's own login variables removed, so Jarvis uses the user's claude.ai login
  * a watcher that posts a Mac notification when a new video is ready to review
Anything this app started is stopped when the window closes.
"""
import json, os, subprocess, sys, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))
LOG = HERE / "out" / "app.log"
JARVIS_DIR = Path.home() / "Developer" / "jarvis"
SEEN = HERE / "out" / "notified.json"
children = []


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def up(url):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def start_studio():
    import studio
    srv = studio.serve(open_browser=False)
    if srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        log("studio server started")
    else:
        log("studio server already running — reusing it")


def start_jarvis():
    if up("http://127.0.0.1:8765/health"):
        return log("jarvis already running")
    uvicorn = JARVIS_DIR / ".venv" / "bin" / "uvicorn"
    if not uvicorn.exists():
        return log("jarvis not installed — skipped")
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")}
    env["PATH"] = f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "/usr/bin:/bin")
    p = subprocess.Popen([str(uvicorn), "brain:app", "--host", "127.0.0.1", "--port", "8765"], cwd=JARVIS_DIR,
                         env=env, stdout=open(HERE / "out" / "jarvis.log", "a"), stderr=subprocess.STDOUT)
    children.append(p)
    log(f"jarvis brain started (pid {p.pid})")


def notify(title, text):
    script = f'display notification {json.dumps(text)} with title {json.dumps(title)} sound name "Glass"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def watch_ready():
    """Every 5 minutes: notify once per video that newly became ready for review."""
    import studio_api
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else None
    while True:
        try:
            ready = {c["key"]: c["title"] for c in studio_api.today()["cards"] if c["kind"] == "ready"}
            if seen is None:  # first launch ever: don't announce what's already there
                seen = set(ready)
            for key, title in ready.items():
                if key not in seen:
                    notify("A new video is ready", title)
                    seen.add(key)
            SEEN.write_text(json.dumps(sorted(seen)))
        except Exception as e:
            log(f"watcher: {e}")
        time.sleep(300)


def watch_health():
    """Every 30 minutes: back up once a day, and notify when a connection breaks or recovers (once per change)."""
    import alerts, backup, studio_api
    while True:
        try:
            if backup.due():
                i = backup.run()
                log(f"backup: {i['files']} files, {i['bytes'] // 1024} KB")
        except Exception as e:
            log(f"backup: {e}")
        try:
            for a in alerts.check(studio_api.health()):
                notify(*alerts.message(a))
        except Exception as e:
            log(f"alerts: {e}")
        time.sleep(1800)


def set_dock_icon():
    try:
        from AppKit import NSApplication, NSImage
        img = NSImage.alloc().initWithContentsOfFile_(str(HERE / "studio" / "icon.png"))
        NSApplication.sharedApplication().setApplicationIconImage_(img)
    except Exception as e:
        log(f"dock icon: {e}")


def main():
    import webview
    start_studio()
    threading.Thread(target=start_jarvis, daemon=True).start()
    threading.Thread(target=watch_ready, daemon=True).start()
    threading.Thread(target=watch_health, daemon=True).start()
    for _ in range(40):
        if up("http://127.0.0.1:8766/api/health"):
            break
        time.sleep(0.25)
    webview.create_window("Nethermind", "http://127.0.0.1:8766/", width=1240, height=820,
                          min_size=(760, 520), background_color="#1C1C1E", text_select=True)
    try:
        webview.start(set_dock_icon, private_mode=False, storage_path=str(HERE / "out" / "webview"))  # keep settings like the brain look
    finally:
        for p in children:
            p.terminate()
        log("app closed")


if __name__ == "__main__":
    main()
