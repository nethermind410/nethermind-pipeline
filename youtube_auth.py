#!/usr/bin/env python3
"""youtube_auth.py — Google OAuth (installed-app / loopback flow) so NETHER can act on YouTube
on Courtney's behalf, not just read it (youtube.py stays read-only, API-key based).

Scope: https://www.googleapis.com/auth/youtube.force-ssl

Where things live:
  client secrets    the .env var YOUTUBE_OAUTH_CLIENT (a path), else out/secrets/youtube_client.json
                     — the OAuth client Courtney creates herself in Google Cloud Console (Desktop app
                     type). Never committed; out/ is gitignored.
  token             out/secrets/youtube_token.json (refresh_token + cached access_token), chmod 600,
                     also under out/ so it's gitignored.

Uses plain `requests` against Google's OAuth endpoints — google-auth-oauthlib / googleapiclient are
NOT installed in this project's .venv (see requirements.txt), so this avoids adding a new dependency.

    python3 youtube_auth.py status         connected?, as which channel
    python3 youtube_auth.py disconnect      forget the stored token
"""
import datetime, http.server, json, os, socket, stat, sys, threading, time, urllib.parse, webbrowser
from pathlib import Path

import requests

from channel import DATA
from store import atomic_write_json, locked

OUT = DATA / "out"
SECRETS = OUT / "secrets"
CLIENT_FILE = SECRETS / "youtube_client.json"
TOKEN_FILE = SECRETS / "youtube_token.json"
STATE_FILE = SECRETS / "youtube_connect_state.json"   # transient: progress of an in-flight connect

SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3/"

CONNECT_TIMEOUT = 300  # seconds to wait on the loopback callback before giving up


class SetupNeeded(Exception):
    """No OAuth client configured yet — the caller should show setup instructions."""


def env_client_path():
    envf = DATA / ".env"
    if not envf.exists():
        return None
    for line in envf.read_text().splitlines():
        if line.strip().startswith("YOUTUBE_OAUTH_CLIENT="):
            p = line.split("=", 1)[1].strip().strip('"').strip("'")
            return Path(p).expanduser() if p else None
    return None


def client_path():
    p = env_client_path()
    if p and p.exists():
        return p
    if CLIENT_FILE.exists():
        return CLIENT_FILE
    return None


def client_config():
    p = client_path()
    if not p:
        raise SetupNeeded(f"No OAuth client yet — drop the downloaded JSON at {CLIENT_FILE}, "
                           "or set YOUTUBE_OAUTH_CLIENT in .env to its path.")
    try:
        raw = json.loads(p.read_text())
    except Exception as e:
        raise SetupNeeded(f"{p} isn't valid JSON ({e}).")
    cfg = raw.get("installed") or raw.get("web")
    if not cfg or not cfg.get("client_id") or not cfg.get("client_secret"):
        raise SetupNeeded(f"{p} doesn't look like a Google OAuth client (missing client_id/client_secret).")
    return cfg


# ------------------------------------------------------------------ token storage
def _load_token():
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


def _save_token(tok):
    with locked(TOKEN_FILE):
        atomic_write_json(TOKEN_FILE, tok)
    try:
        os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass


def connected():
    return _load_token() is not None


def disconnect():
    for f in (TOKEN_FILE, STATE_FILE):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    return {"ok": True}


# ------------------------------------------------------------------ token exchange / refresh
def _post_form(url, data):
    r = requests.post(url, data=data, timeout=30)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    if r.status_code != 200:
        raise RuntimeError(body.get("error_description") or body.get("error") or r.text[:200])
    return body


def _exchange_code(code, redirect_uri):
    cfg = client_config()
    body = _post_form(TOKEN_URL, {"code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                                   "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    if not body.get("refresh_token"):
        raise RuntimeError("Google didn't return a refresh token — try disconnecting in Google Account "
                            "permissions and connecting again (offline access must be granted fresh).")
    tok = {"refresh_token": body["refresh_token"], "access_token": body.get("access_token"),
           "expires_at": time.time() + int(body.get("expires_in", 3600)) - 60}
    _save_token(tok)
    return tok


def _refresh(tok):
    cfg = client_config()
    body = _post_form(TOKEN_URL, {"refresh_token": tok["refresh_token"], "client_id": cfg["client_id"],
                                   "client_secret": cfg["client_secret"], "grant_type": "refresh_token"})
    tok = {**tok, "access_token": body.get("access_token"), "expires_at": time.time() + int(body.get("expires_in", 3600)) - 60}
    _save_token(tok)
    return tok


def access_token():
    tok = _load_token()
    if not tok:
        raise SetupNeeded("Not connected to YouTube yet.")
    if not tok.get("access_token") or time.time() >= tok.get("expires_at", 0):
        tok = _refresh(tok)
    return tok["access_token"]


# ------------------------------------------------------------------ loopback (installed-app) flow
class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.result = {"code": qs.get("code", [None])[0], "error": qs.get("error", [None])[0]}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        msg = "Connected — you can close this tab." if self.server.result.get("code") else "Something went wrong — you can close this tab."
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px'><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *a):
        pass  # quiet — this is a one-shot local callback receiver


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_state(**kw):
    SECRETS.mkdir(parents=True, exist_ok=True)
    atomic_write_json(STATE_FILE, {"at": datetime.datetime.now().isoformat(timespec="seconds"), **kw})


def connect_state():
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def begin_connect(open_browser=True):
    """Starts the loopback listener + a background thread that waits for Google's redirect,
    exchanges the code, and stores the refresh token. Returns the auth URL to open (or send
    the user to). Raises SetupNeeded if no client JSON is configured."""
    cfg = client_config()  # raises SetupNeeded early, before opening anything
    port = _free_port()
    redirect_uri = f"http://127.0.0.1:{port}/"
    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = CONNECT_TIMEOUT
    server.result = None
    params = {"client_id": cfg["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
              "scope": SCOPE, "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    _write_state(status="waiting")

    def _run():
        try:
            deadline = time.time() + CONNECT_TIMEOUT
            while server.result is None and time.time() < deadline:
                server.handle_request()
            if server.result is None:
                return _write_state(status="error", message="Timed out waiting for Google — try again.")
            if server.result.get("error"):
                return _write_state(status="error", message=server.result["error"])
            _exchange_code(server.result["code"], redirect_uri)
            _write_state(status="connected", message="Connected.")
        except Exception as e:
            _write_state(status="error", message=str(e))
        finally:
            try:
                server.server_close()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass
    return auth_url


# ------------------------------------------------------------------ thin YouTube Data API v3 client
def api_request(method, path, params=None, json_body=None):
    token = access_token()
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.request(method, API + path, params=params or {}, json=json_body, headers=headers, timeout=30)
    if r.status_code == 401:  # token revoked/expired oddly — one retry after a forced refresh
        tok = _refresh(_load_token())
        headers["Authorization"] = f"Bearer {tok['access_token']}"
        r = requests.request(method, API + path, params=params or {}, json=json_body, headers=headers, timeout=30)
    if r.status_code >= 300:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"YouTube API {method} {path}: {r.status_code} {msg}")
    return r.json() if r.text else {}


def my_channel():
    d = api_request("GET", "channels", params={"part": "snippet", "mine": "true"})
    items = d.get("items") or []
    return items[0] if items else None


def status():
    if not connected():
        return {"connected": False}
    try:
        ch = my_channel()
    except Exception as e:
        return {"connected": False, "error": str(e)}
    if not ch:
        return {"connected": False}
    return {"connected": True, "channel": ch["snippet"]["title"]}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "disconnect":
        print(disconnect())
    else:
        print(json.dumps(status(), indent=2))
