#!/usr/bin/env python3
"""studio.py — the local server behind the Mac app (app.py) and Studio in a browser.

    .venv/bin/python studio.py        serves http://127.0.0.1:8766 and opens it

Screens and their data come from studio_api.py; this file is routing, the one-at-a-time
job runner (build / post / undo / stats), media serving with Range support, and the
Jarvis proxy. Localhost only; state-changing requests need the X-Studio header.
"""
import datetime, json, logging, logging.handlers, os, re, subprocess, sys, threading, traceback, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import studio_api as api
import studio_channel as chan
import studio_create as create
import orchestrator as nether
from store import atomic_write_text

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
import channel as chcfg
OUT, CFG = DATA / "out", DATA / "cfg"
LOGDIR = OUT / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("studio")
log.setLevel(logging.ERROR)
_h = logging.handlers.RotatingFileHandler(LOGDIR / "server.log", maxBytes=1_000_000, backupCount=3)
_h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
log.addHandler(_h)
UI = HERE / "studio"
PORT = int(os.environ.get("STUDIO_PORT", 8766))  # 8765 belongs to Jarvis
ID_RE = re.compile(r"^[a-z0-9_]+$")
PY = str(HERE / ".venv" / "bin" / "python") if (HERE / ".venv" / "bin" / "python").exists() else sys.executable  # packaged app: its own python
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
QUEUE = []   # jobs waiting their turn: one runs at a time (renders need the whole Mac), the rest line up here
QSEQ = [0]


def label_for(action, vid):
    return (LABELS[action] if action in FREE_ARG else f"{LABELS[action]} {vid}").strip()


def start_job(action, vid):
    """Start a job now. Caller holds LOCK and has checked nothing is running."""
    JOB.update(id=JOB["id"] + 1, action=action, video=vid, task=None, label=label_for(action, vid),
               log="", done=False, code=None, friendly=None)
    threading.Thread(target=run_job, args=(action, vid), daemon=True).start()


def queue_view():
    return [{k: q[k] for k in ("qid", "action", "video", "label", "added")} for q in QUEUE]
STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/app.css": ("app.css", "text/css"),
          "/app.js": ("app.js", "text/javascript"), "/app2.js": ("app2.js", "text/javascript"),
          "/brain.js": ("brain.js", "text/javascript"), "/neural.js": ("neural.js", "text/javascript"), "/app3.js": ("app3.js", "text/javascript"), "/theme.css": ("theme.css", "text/css"), "/brain.jpg": ("brain.jpg", "image/jpeg"), "/icon.png": ("icon.png", "image/png")}
# Extensions: any studio_ext_<name>.py may define GET = {"/api/x": fn} and POST = {"/api/x": fn(body) -> dict}
# (raise ValueError for a 400). Any studio/ext_<name>.js / .css is served and loaded by the page via /ext.js.
import importlib
EXT, EXT_ERRORS = [], []
for _p in sorted(HERE.glob("studio_ext_*.py")):
    try:
        EXT.append(importlib.import_module(_p.stem))
    except Exception as _e:
        log.error("extension %s failed to load:\n%s", _p.stem, traceback.format_exc())
        EXT_ERRORS.append({"name": _p.stem, "error": str(_e)})
for f in sorted(UI.glob("ext_*.js")) + sorted(UI.glob("ext_*.css")):
    STATIC["/" + f.name] = (f.name, "text/javascript" if f.suffix == ".js" else "text/css")
EXT_GET = {k: v for m in EXT for k, v in getattr(m, "GET", {}).items()}
EXT_POST = {k: v for m in EXT for k, v in getattr(m, "POST", {}).items()}
EXT_PREFIX = {k: v for m in EXT for k, v in getattr(m, "GET_PREFIX", {}).items()}   # "/api/x/" → f(rest of path)
MEDIA = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png", ".srt": "text/plain"}
MUSIC_DIR, TRACKS = DATA / "music", {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg"}
JARVIS = chcfg.jarvis()["url"] + "/ask"   # optional (channel.json "jarvis")


def run_job(action, vid):
    cmd = ACTIONS[action](vid)
    code = 1
    task = None                                    # NETHER: this job is a task of the agent that owns it
    if action in nether.STUDIO_ACTIONS:            # (builds report their own steps from build.sh)
        agent, sub = nether.STUDIO_ACTIONS[action]
        try:
            task = nether.begin(agent, JOB["label"], sub=sub, video=vid or None, retry={"action": action, "id": vid})
            with LOCK:
                JOB["task"] = task
        except Exception:
            pass
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
        if task:
            try:
                nether.end(task, code, (JOB["friendly"] + "\n\n" if code and JOB["friendly"] else "") + JOB["log"])
            except Exception:
                pass
        if action == "post_live" and code == 0:
            api.set_done(f"ready:{vid}")
        if action in ("build", "build_nofetch") and code == 0:
            api.set_done(f"ready:{vid}", False)  # a fresh build needs a fresh review
        with LOCK:                               # next in line
            if QUEUE and JOB["done"]:
                q = QUEUE.pop(0)
                start_job(q["action"], q["video"])


def ask_jarvis(text):
    import urllib.request, urllib.error
    if not chcfg.jarvis()["enabled"]:
        return 503, {"reply": "Jarvis isn't set up for this channel. It's optional — turn it on in channel.json if you use it."}
    req = urllib.request.Request(JARVIS, data=json.dumps({"text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return 200, json.loads(r.read())
    except urllib.error.URLError:
        return 503, {"reply": f"Jarvis isn't running yet. Open {chcfg.get('app_name')} from the Dock and it starts automatically."}
    except Exception as e:
        return 502, {"reply": f"Jarvis didn't answer: {e}"}


class BadJSON(Exception):
    pass


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
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)) or 2) or b"{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise BadJSON()

    def _host_ok(self):
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self._host_ok():
            return self.send(403, {"error": "forbidden"})
        try:
            return self._do_GET()
        except Exception:
            log.error("GET %s failed:\n%s", self.path, traceback.format_exc())
            return self.send(500, {"error": "Something went wrong handling that request — see out/logs/server.log."})

    def _do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path in STATIC:
            name, ctype = STATIC[path]
            f = UI / name
            return self.send_file(f, ctype) if f.exists() else self.send(404, {"error": "not found"})
        routes = {"/api/today": api.today, "/api/videos": api.videos, "/api/performance": api.performance,
                  "/api/ideas": api.ideas, "/api/health": api.health, "/api/channel": chan.channel,
                  "/api/calendar": chan.calendar, "/api/comments": lambda: chan.comments(api.done_map()),
                  "/api/demand": lambda: api.jload(OUT / "idea_demand.json", {}),
                  "/api/inspiration": create.inspiration, "/api/series": create.series,
                  "/api/ext_errors": lambda: EXT_ERRORS}
        if path == "/ext.js":                               # loads every extension's script and stylesheet
            names = sorted(k[1:] for k in STATIC if k.startswith("/ext_"))
            js = "".join(f'document.head.insertAdjacentHTML("beforeend",\'<link rel="stylesheet" href="/{n}">\');' if n.endswith(".css")
                         else f'document.write(\'<script src="/{n}"><\\/script>\');' for n in names)
            data = js.encode()
            self.send_response(200); self.send_header("Content-Type", "text/javascript"); self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store"); self.end_headers(); return self.wfile.write(data)
        routes.update(EXT_GET)
        if path in routes:
            return self.send(200, routes[path]())
        for pre, f in EXT_PREFIX.items():
            if path.startswith(pre):
                try:
                    return self.send(200, f(path[len(pre):]))
                except ValueError as e:
                    return self.send(400, {"error": str(e)})
        m = re.fullmatch(r"/api/video/([a-z0-9_]+)", path)
        if m and (CFG / f"{m[1]}.json").exists():
            v = api.video(m[1])
            v["precheck"] = chan.precheck(v["packaging"]) if v["packaging"] else None
            return self.send(200, v)
        m = re.fullmatch(r"/api/hooks/([a-z0-9_]+)", path)
        if m and (CFG / f"{m[1]}.json").exists():
            return self.send(200, create.hooks(m[1]))
        m = re.fullmatch(r"/insp/([a-f0-9]{12}\.(?:png|jpg|webp|gif))", path)
        if m and (create.INSP_DIR / m[1]).is_file():
            return self.send_file(create.INSP_DIR / m[1], {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}[m[1].rsplit(".", 1)[1]])
        if path == "/api/job":
            with LOCK:
                return self.send(200, {**JOB, "queue": queue_view()})
        if path == "/api/music":                             # your own tracks for the interface's music player
            return self.send(200, {"tracks": sorted(p.name for p in MUSIC_DIR.glob("*") if p.suffix.lower() in TRACKS)
                                   if MUSIC_DIR.is_dir() else []})
        m = re.fullmatch(r"/asset/([A-Za-z0-9_.\-]+\.(?:jpg|jpeg|png|webp))", path)   # a video's own artwork
        if m and (DATA / "assets" / m[1]).is_file():
            return self.send_file(DATA / "assets" / m[1], {"png": "image/png", "webp": "image/webp"}.get(m[1].rsplit(".", 1)[1], "image/jpeg"))
        m = re.fullmatch(r"/music/([^/]+)", path)
        if m and (MUSIC_DIR / m[1]).is_file() and (MUSIC_DIR / m[1]).suffix.lower() in TRACKS and (MUSIC_DIR / m[1]).resolve().parent == MUSIC_DIR.resolve():
            return self.send_file(MUSIC_DIR / m[1], TRACKS[(MUSIC_DIR / m[1]).suffix.lower()])
        m = re.fullmatch(r"/media/([A-Za-z0-9_.\-]+)", path)
        if m and (OUT / m[1]).is_file() and (OUT / m[1]).suffix in MEDIA:
            return self.send_file(OUT / m[1], MEDIA[(OUT / m[1]).suffix])
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self.send(403, {"error": "forbidden"})
        try:
            return self._do_POST()
        except BadJSON:
            return self.send(400, {"error": "bad JSON body"})
        except Exception:
            log.error("POST %s failed:\n%s", self.path, traceback.format_exc())
            return self.send(500, {"error": "Something went wrong handling that request — see out/logs/server.log."})

    def _do_POST(self):
        # same-origin + custom header: stops other web pages triggering anything
        origin = self.headers.get("Origin", "")
        ok_origins = (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")
        if self.headers.get("X-Studio") != "1" or (origin and origin not in ok_origins):
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
            pkg_path = DATA / "packaging" / f"{vid}.json"
            if not (ID_RE.match(vid) and pkg_path.exists() and title):
                return self.send(400, {"error": "bad title"})
            pkg = json.loads(pkg_path.read_text())
            opts = [o["title"] if isinstance(o, dict) else o for o in pkg.get("title_options", [])]
            if title not in opts + [pkg.get("title")]:
                return self.send(400, {"error": "Pick one of the listed titles."})
            pkg["title"] = title
            atomic_write_text(pkg_path, json.dumps(pkg, indent=1, ensure_ascii=False) + "\n")
            return self.send(200, {"ok": True})
        try:
            if self.path == "/api/inspiration":
                return self.send(200, create.add_inspiration(b.get("image"), b.get("note"), b.get("url", "")))
            if self.path == "/api/inspiration/remove":
                return self.send(200, create.remove_inspiration(str(b.get("id", ""))))
            if self.path == "/api/script":
                return self.send(200, create.save_script(str(b.get("id", "")), b.get("lines") or {}))
            if self.path == "/api/hook":
                return self.send(200, create.choose_hook(str(b.get("id", "")), str(b.get("text", ""))))
            if self.path == "/api/series":
                return self.send(200, create.save_series(b.get("series") or []))
            if self.path in EXT_POST:
                return self.send(200, EXT_POST[self.path](b))
        except ValueError as e:
            return self.send(400, {"error": str(e)})
        if self.path == "/api/idea":
            try:
                return self.send(200, api.add_idea(str(b.get("section", "")), b.get("hook", ""), b.get("format", ""), b.get("source", "")))
            except ValueError as e:
                return self.send(400, {"error": str(e)})
        if self.path == "/api/queue":                      # {"op": "remove"|"up"|"down"|"clear", "qid"}
            op, qid = b.get("op"), b.get("qid")
            with LOCK:
                i = next((k for k, q in enumerate(QUEUE) if q["qid"] == qid), None)
                if op == "clear":
                    QUEUE.clear()
                elif i is None:
                    return self.send(400, {"error": "That job already started or left the queue."})
                elif op == "remove":
                    QUEUE.pop(i)
                elif op == "up" and i > 0:
                    QUEUE[i - 1], QUEUE[i] = QUEUE[i], QUEUE[i - 1]
                elif op == "down" and i < len(QUEUE) - 1:
                    QUEUE[i + 1], QUEUE[i] = QUEUE[i], QUEUE[i + 1]
                return self.send(200, {"ok": True, "queue": queue_view()})
        if self.path != "/api/run":
            return self.send(404, {"error": "not found"})
        action, vid = b.get("action"), str(b.get("id", ""))
        ok_arg = re.match(FREE_ARG[action], vid) if action in FREE_ARG else (ID_RE.match(vid) and (CFG / f"{vid}.json").exists())
        if action not in ACTIONS or not ok_arg:
            return self.send(400, {"error": "bad action or video"})
        if action == "post_live" and b.get("confirm") is not True:
            return self.send(400, {"error": "Confirm the schedule first."})
        with LOCK:
            if JOB["done"] and not QUEUE:
                start_job(action, vid)
                return self.send(200, {"ok": True, "queued": 0})
            if (not JOB["done"] and JOB["action"] == action and JOB["video"] == vid) or any(q["action"] == action and q["video"] == vid for q in QUEUE):
                return self.send(200, {"ok": True, "queued": -1, "reply": f"{label_for(action, vid)} is already lined up."})
            QSEQ[0] += 1
            QUEUE.append({"qid": QSEQ[0], "action": action, "video": vid, "label": label_for(action, vid),
                          "added": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
            n = len(QUEUE)
        self.send(200, {"ok": True, "queued": n, "reply": f"Queued — {label_for(action, vid)} starts after {'the current job' if n == 1 else f'{n - 1} other' + ('s' if n > 2 else '') + ' in line'}."})


def serve(open_browser=True):
    url = f"http://127.0.0.1:{PORT}"
    try:
        nether.mark_interrupted()
    except Exception:
        pass
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        print(f"Studio already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return None
    print(f"{chcfg.get('app_name')} Studio on {url}" + (f"  (data: {chcfg.DATA})" if chcfg.DATA != HERE else ""))
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
