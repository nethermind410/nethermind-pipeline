"""Studio extension: record your own narration, line by line (optional — Kokoro reads any line you skip).

POST /api/voice/save     {"owner", "line", "text", "data" (base64 audio), "mime"} → cleaned mp3 in out/voice/
POST /api/voice/delete   {"owner", "line"}
POST /api/voice/status   {"owner", "lines": {line id: text}} → {line id: "ok" | "stale"}
POST /api/voice/play     {"owner", "line"} → the recording as a data URL, to listen back
"""
import base64

import voice


def save(body):
    return voice.save(str(body.get("owner", "")), str(body.get("line", "")), str(body.get("text", "")),
                      str(body.get("data", "")), str(body.get("mime", "")))


def delete(body):
    return voice.delete(str(body.get("owner", "")), str(body.get("line", "")))


def status(body):
    lines = body.get("lines") or {}
    return voice.status(str(body.get("owner", "")), {str(k): str(v) for k, v in lines.items()} if isinstance(lines, dict) else {})


def play(body):
    owner, line = str(body.get("owner", "")), str(body.get("line", ""))
    if not (voice.ID_RE.match(owner) and voice.ID_RE.match(line)):
        raise ValueError("Bad recording id.")
    p = voice.VOICE / owner / f"{line}.mp3"
    if not p.exists():
        raise ValueError("No recording for that line.")
    return {"data": "data:audio/mpeg;base64," + base64.b64encode(p.read_bytes()).decode()}


POST = {"/api/voice/save": save, "/api/voice/delete": delete, "/api/voice/status": status, "/api/voice/play": play}
