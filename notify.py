"""notify.py — one place for NETHER's Mac notifications.

Uses osascript's `display notification`, so macOS files them under Script Editor: clicking one
opens Script Editor. Harmless — close it. (A native notification from Nethermind.app itself would
need the app to be signed; see docs/PRODUCT.md "Before selling".)
"""
import json, shutil, subprocess


def send(title, text, subtitle=None, sound="Glass"):
    if not shutil.which("osascript"):
        return
    script = f"display notification {json.dumps(text[:220])} with title {json.dumps(title)}"
    if subtitle:
        script += f" subtitle {json.dumps(subtitle)}"
    if sound:
        script += f' sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except Exception:
        pass
