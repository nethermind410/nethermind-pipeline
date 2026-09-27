"""Studio extension: keeps out/jarvis_status.md (+ .json) fresh for Jarvis.

Jarvis (Courtney's voice assistant) reads out/jarvis_status.md read-only, no network back to
NETHER, so that file has to stay current on its own. studio.py already calls
nether_status.write() once on start and again after every job finishes; this extension is the
third call site — a quiet background refresh every 15 minutes, so the brief is never far stale
even on a day nothing else runs. No GET/POST here — a background thread, nothing more.
"""
import threading, time

import nether_status

INTERVAL_SECONDS = 15 * 60


def _loop():
    while True:
        time.sleep(INTERVAL_SECONDS)
        try:
            nether_status.write()
        except Exception:
            pass   # write() already never raises, but a thread dying silently would be worse


threading.Thread(target=_loop, daemon=True, name="jarvis-status-refresh").start()
