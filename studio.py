#!/usr/bin/env python3
"""studio.py — the local server behind Nethermind (the Mac app) and Studio in a browser.

    .venv/bin/python studio.py        serves http://127.0.0.1:8766 and opens it

Screens and their data come from studio_api.py; this file is routing, the one-at-a-time
job runner (build / post / undo / stats), media serving with Range support, and the
Jarvis proxy. Localhost only; state-changing requests need the X-Studio header.
"""
import json, os, re, subprocess, sys, threading, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import studio_api as api
import studio_channel as chan

HERE = Path(__file__).resolve().parent
OUT, CFG = HERE / "out", HERE / "cfg"
UI = HERE / "studio"
PORT = int(os.environ.get("STUDIO_PORT", 8766))  # 8765 belongs to Jarvis
ID_RE = re.compile(r"^[a-z0-9_]+$")
PY = str(HERE / ".venv" / "bin" / "python")
ACTIONS = {
    "build": lambda i: ["./build.sh", i],
    "build_nofetch": lambda i: ["./build.sh", i, "--no-fetch"],
    "post_dry": lambda i: ["./post.sh", i],
    "post_live": lambda i: ["./post.sh", i, "--live"],
    "undo": lambda i: [PY, "undo_post.py", i],
    "stats": lambda i: ["./refresh.sh"],
    "demand": lambda i: [PY, "idea_demand.py"] + ([i] if i else []),
    "replies": lambda i: [PY, "claude_task.py", "replies", i],
    "score": lambda i: [PY, "claude_task.py", "score", i],
    "reschedule": lambda i: [PY, "reschedule_post.py", *i.split("|", 1)],
}
FREE_ARG = {"stats": r"^$", "demand": r"^[a-z0-9_]{0,48}$", "replies": r"^[A-Za-z0-9_-]{10,80}$",
            "reschedule": r"^[a-f0-9]{24}\|\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?(\.\d+)?(Z|[+-]\d\d:\d\d)$"}
LABELS = {"build": "Making", "build_nofetch": "Re-making", "post_dry": "Checking the post for",
          "post_live": "Scheduling", "undo": "Taking back", "stats": "Refreshing numbers from YouTube and Buffer",
          "demand": "Checking YouTube demand", "replies": "Drafting replies", "score": "Scoring titles with vidIQ",
          "reschedule": "Moving the post"}
JOB = {"id": 0, "action": "", "video": "", "label": "", "log": "", "done": True, "code": None, "friendly": None}
LOCK = threading.Lock()
STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/app.css": ("app.css", "text/css"),
          "/app.js": ("app.js", "text/javascript"), "/app2.js": ("app2.js", "text/javascript"),
          "/brain.js": ("brain.js", "text/javascript"), "/neural.js": ("neural.js", "text/javascript"), "/theme.css": ("theme.css", "text/css"), "/brain.jpg": ("brain.jpg", "image/jpeg"), "/icon.png": ("icon.png", "image/png")}
MEDIA = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png", ".srt": "text/plain"}
JARVIS = "http://127.0.0.1:8765/ask"


def run_job(action, vid):
    cmd = ACTIONS[action](vid)
    code = 1
    try:
        p = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            with LOCK:
                JOB["log"] += line
        code = p.wait()
    except Exception as e:  # never leave the app stuck on "working"
        with LOCK:
            JOB["log"] += f"\nCould not run {cmd[0]}: {e}\n"
    finally:
        with LOCK:
            JOB.update(done=True, code=code, friendly=api.friendly(JOB["log"], code))
        if action == "post_live" and code == 0:
            api.set_done(f"ready:{vid}")
        if action in ("build", "build_nofetch") and code == 0:
            api.set_done(f"ready:{vid}", False)  # a fresh build needs a fresh review


def ask_jarvis(text):
    import urllib.request, urllib.error
    req = urllib.request.Request(JARVIS, data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return 200, json.loads(r.read())
    except urllib.error.URLError:
        return 503, {"reply": "Jarvis isn't running yet. Open Nethermind from the Dock and it starts automatically."}
    except Exception as e:
        return 502, {"reply": f"Jarvis didn't answer: {e}"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, f, ctype):
        """Serve with HTTP Range support — WebKit won't play <video> without it."""
        size = f.stat().st_size
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        start, end = 0, size - 1
        if rng and (rng[1] or rng[2]):
            if rng[1]:
                start, end = int(rng[1]), int(rng[2]) if rng[2] else size - 1
            else:
                start = max(0, size - int(rng[2]))
            end = min(end, size - 1)
        with open(f, "rb") as fh:
            fh.seek(start)
            data = fh.read(end - start + 1)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(data)))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 2) or b"{}")

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path in STATIC:
            name, ctype = STATIC[path]
            f = UI / name
            return self.send_file(f, ctype) if f.exists() else self.send(404, {"error": "not found"})
        routes = {"/api/today": api.today, "/api/videos": api.videos, "/api/performance": api.performance,
                  "/api/ideas": api.ideas, "/api/health": api.health, "/api/channel": chan.channel,
                  "/api/calendar": chan.calendar, "/api/comments": lambda: chan.comments(api.done_map()),
                  "/api/demand": lambda: api.jload(OUT / "idea_demand.json", {})}
        if path in routes:
            return self.send(200, routes[path]())
        m = re.fullmatch(r"/api/video/([a-z0-9_]+)", path)
        if m and (CFG / f"{m[1]}.json").exists():
            v = api.video(m[1])
            v["precheck"] = chan.precheck(v["packaging"]) if v["packaging"] else None
            return self.send(200, v)
        if path == "/api/job":
            with LOCK:
                return self.send(200, dict(JOB))
        m = re.fullmatch(r"/media/([A-Za-z0-9_.\-]+)", path)
        if m and (OUT / m[1]).is_file() and (OUT / m[1]).suffix in MEDIA:
            return self.send_file(OUT / m[1], MEDIA[(OUT / m[1]).suffix])
        self.send(404, {"error": "not found"})

    def do_POST(self):
        # same-origin + custom header: stops other web pages triggering anything
        origin = self.headers.get("Origin", "")
        if self.headers.get("X-Studio") != "1" or (origin and origin != f"http://127.0.0.1:{PORT}"):
            return self.send(403, {"error": "forbidden"})
        b = self.body()
        if self.path == "/api/jarvis":
            text = str(b.get("text", "")).strip()[:500]
            return self.send(*ask_jarvis(text)) if text else self.send(400, {"reply": "Type a question first."})
        if self.path == "/api/done":
            key = str(b.get("key", ""))
            if not re.fullmatch(r"[a-z]+:[a-z0-9_]{1,60}(:[a-z]+)?", key):
                return self.send(400, {"error": "bad key"})
            api.set_done(key, bool(b.get("done", True)))
            return self.send(200, {"ok": True})
        if self.path == "/api/feedback":
            vid, note = b.get("id", ""), str(b.get("note", "")).strip()[:2000]
            if not (ID_RE.match(vid) and (CFG / f"{vid}.json").exists() and note):
                return self.send(400, {"error": "Say what should change."})
            return self.send(200, api.add_feedback(vid, note))
        if self.path == "/api/next":
            sl = str(b.get("slug") or "")
            if sl and not re.fullmatch(r"[a-z0-9_]{1,48}", sl):
                return self.send(400, {"error": "bad idea"})
            return self.send(200, api.set_next(sl, str(b.get("hook", ""))[:300]))
        if self.path == "/api/choose_title":
            vid, title = b.get("id", ""), str(b.get("title", "")).strip()
            pkg_path = HERE / "packaging" / f"{vid}.json"
            if not (ID_RE.match(vid) and pkg_path.exists() and title):
                return self.send(400, {"error": "bad title"})
            pkg = json.loads(pkg_path.read_text())
            opts = [o["title"] if isinstance(o, dict) else o for o in pkg.get("title_options", [])]
            if title not in opts + [pkg.get("title")]:
                return self.send(400, {"error": "Pick one of the listed titles."})
            pkg["title"] = title
            pkg_path.write_text(json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
            return self.send(200, {"ok": True})
        if self.path == "/api/idea":
            try:
                return self.send(200, api.add_idea(str(b.get("section", "")), b.get("hook", ""), b.get("format", ""), b.get("source", "")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if self.path != "/api/run":
            return self.send(404, {"error": "not found"})
        action, vid = b.get("action"), str(b.get("id", ""))
        ok_arg = re.match(FREE_ARG[action], vid) if action in FREE_ARG else (ID_RE.match(vid) and (CFG / f"{vid}.json").exists())
        if action not in ACTIONS or not ok_arg:
            return self.send(400, {"error": "bad action or video"})
        if action == "post_live" and b.get("confirm") is not True:
            return self.send(400, {"error": "Confirm the schedule first."})
        with LOCK:
            if not JOB["done"]:
                return self.send(409, {"error": f"Still busy: {JOB['label']}. Try again when it finishes."})
            JOB.update(id=JOB["id"] + 1, action=action, video=vid, label=(LABELS[action] if action in FREE_ARG else f"{LABELS[action]} {vid}").strip(),
                       log="", done=False, code=None, friendly=None)
        threading.Thread(target=run_job, args=(action, vid), daemon=True).start()
        self.send(200, {"ok": True})


def serve(open_browser=True):
    url = f"http://127.0.0.1:{PORT}"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        print(f"Studio already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return None
    print(f"Nethermind Studio on {url}")
    if open_browser and not os.environ.get("STUDIO_NO_BROWSER"):
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    return srv


if __name__ == "__main__":
    s = serve()
    if s:
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            pass
    sys.exit(0)
