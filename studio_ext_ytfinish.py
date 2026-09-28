"""Studio extension: finish a live video on YouTube automatically — tags, the "synthetic content"
disclosure, the pinned comment's text (posting, not pinning), and its series playlist. Everything
else on the finish checklist (pinning the comment, the end screen, Related video, "check it plays")
stays a manual tick — the API doesn't support pinning/end-screens/Related-video, and "check it plays"
is on purpose always a human look.

GET  /api/ytfinish/status     {"connected", "channel", "needs_setup", "hint", "autorun"}
POST /api/ytfinish/connect     starts the Google sign-in (loopback flow); {"auth_url"} or a setup hint
POST /api/ytfinish/disconnect  forgets the stored token
POST /api/ytfinish/autorun     {"on": bool} — run automations by itself when a video goes live
POST /api/ytfinish/run         {"video": id} — run every automation for one live video now

Each automation reads the video's current state first and only writes when something's actually
different (idempotent) — see tags/disclosure/comment/playlist below. Every attempt is appended to
out/ytfinish_log.jsonl. autorun_check() is called from studio_ext_day.day() once per Today load, so
a newly-live video gets finished within the hour without anyone pressing a button (off by default).
"""
import datetime, json, re
from pathlib import Path

import channel
import intelligence
import studio_api as api
import youtube_auth as auth
from channel import DATA
from store import atomic_write_json, locked

OUT = DATA / "out"
PKG = DATA / "packaging"
SETTINGS_FILE = OUT / "ytfinish_settings.json"
AUTORUN_STATE_FILE = OUT / "ytfinish_autorun_state.json"
LOG_FILE = OUT / "ytfinish_log.jsonl"

STEP_KEYS = ("tags", "comment", "playlist", "disclosure")  # matches studio_api.FINISH_STEPS' keys


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _log(vid, step, action, detail=""):
    OUT.mkdir(parents=True, exist_ok=True)
    line = {"at": datetime.datetime.now().isoformat(timespec="seconds"), "video": vid, "step": step,
            "action": action, "detail": str(detail)[:300]}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(line) + "\n")
    return line


# ------------------------------------------------------------------ settings (autorun toggle)
def settings():
    return {"autorun": bool(jload(SETTINGS_FILE, {}).get("autorun", False))}


def set_autorun(body):
    on = bool((body or {}).get("on"))
    with locked(SETTINGS_FILE):
        atomic_write_json(SETTINGS_FILE, {"autorun": on})
    return settings()


# ------------------------------------------------------------------ status / connect
def status():
    st = auth.status()
    connecting = auth.connect_state()
    out = {"connected": bool(st.get("connected")), "channel": st.get("channel"),
           "needs_setup": False, "hint": None, **settings()}
    if not st.get("connected"):
        try:
            auth.client_config()
        except auth.SetupNeeded as e:
            out["needs_setup"] = True
            out["hint"] = str(e)
    if connecting and connecting.get("status") == "waiting":
        out["connecting"] = True
    elif connecting and connecting.get("status") == "error":
        out["error"] = connecting.get("message")
    return out


def connect(body=None):
    try:
        url = auth.begin_connect()
    except auth.SetupNeeded as e:
        raise ValueError(str(e))
    return {"auth_url": url}


def disconnect(body=None):
    return auth.disconnect()


# ------------------------------------------------------------------ finding the real YouTube video id
def youtube_id(vid):
    v = api.video(vid)
    for url in (v.get("youtube_url"), v.get("youtube_edit")):
        if not url:
            continue
        m = re.search(r"(?:v=|shorts/|video/)([\w-]{11})", url)
        if m:
            return m[1]
    return None


def series_label(title):
    lane = intelligence.lane_of(title or "")
    defs = channel.lane_defs()
    if lane in defs:
        return defs[lane]["label"]
    return "Other" if lane == "other" else lane.title()


# ------------------------------------------------------------------ automations (each idempotent)
def do_tags(vid, video_id, pkg):
    wanted = [t.strip() for t in re.split(r",\s*", pkg.get("youtube_tags") or "") if t.strip()]
    if not wanted:
        return _log(vid, "tags", "skipped", "no youtube_tags in packaging")
    d = auth.api_request("GET", "videos", params={"part": "snippet", "id": video_id})
    items = d.get("items") or []
    if not items:
        return _log(vid, "tags", "error", "video not found on YouTube")
    snippet = items[0]["snippet"]
    current = snippet.get("tags") or []
    if [t.lower() for t in current] == [t.lower() for t in wanted]:
        return _log(vid, "tags", "skipped", "already set")
    snippet["tags"] = wanted   # keep title/description/categoryId etc. exactly as fetched
    auth.api_request("PUT", "videos", params={"part": "snippet"},
                      json_body={"id": video_id, "snippet": snippet})
    api.set_done(f"finish:{vid}:tags", True)
    return _log(vid, "tags", "updated", f"{len(wanted)} tags")


def do_disclosure(vid, video_id, pkg):
    if not pkg.get("synthetic_disclosure"):
        return _log(vid, "disclosure", "skipped", "not flagged as synthetic media")
    d = auth.api_request("GET", "videos", params={"part": "status", "id": video_id})
    items = d.get("items") or []
    if not items:
        return _log(vid, "disclosure", "error", "video not found on YouTube")
    st = items[0]["status"]
    if st.get("containsSyntheticMedia") is True:
        return _log(vid, "disclosure", "skipped", "already set")
    st["containsSyntheticMedia"] = True   # keep privacyStatus etc. exactly as fetched
    auth.api_request("PUT", "videos", params={"part": "status"},
                      json_body={"id": video_id, "status": st})
    api.set_done(f"finish:{vid}:disclosure", True)
    return _log(vid, "disclosure", "updated", "containsSyntheticMedia=true")


def do_comment(vid, video_id, pkg):
    text = (pkg.get("pinned_comment") or "").strip()
    if not text:
        return _log(vid, "comment", "skipped", "no pinned_comment in packaging")
    d = auth.api_request("GET", "commentThreads", params={"part": "snippet", "videoId": video_id, "maxResults": 50})
    for t in d.get("items") or []:
        existing = t["snippet"]["topLevelComment"]["snippet"].get("textOriginal") or t["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
        if existing.strip() == text:
            return _log(vid, "comment", "skipped", "already posted")   # tick stays manual — pinning is
    auth.api_request("POST", "commentThreads", params={"part": "snippet"},
                      json_body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}})
    return _log(vid, "comment", "posted", "not pinned — pin it by hand, then tick it off")


def _find_playlist(title):
    page_token = None
    for _ in range(10):
        params = {"part": "snippet", "mine": "true", "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        d = auth.api_request("GET", "playlists", params=params)
        for p in d.get("items") or []:
            if p["snippet"]["title"] == title:
                return p["id"]
        page_token = d.get("nextPageToken")
        if not page_token:
            break
    return None


def _playlist_has(playlist_id, video_id):
    page_token = None
    for _ in range(20):
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token
        d = auth.api_request("GET", "playlistItems", params=params)
        if any(i["contentDetails"]["videoId"] == video_id for i in d.get("items") or []):
            return True
        page_token = d.get("nextPageToken")
        if not page_token:
            break
    return False


def do_playlist(vid, video_id, pkg):
    label = series_label(pkg.get("title") or "")
    playlist_id = _find_playlist(label)
    created = False
    if not playlist_id:
        d = auth.api_request("POST", "playlists", params={"part": "snippet,status"},
                              json_body={"snippet": {"title": label, "description": f"{label} — {channel.get('name')}"},
                                         "status": {"privacyStatus": "public"}})
        playlist_id = d["id"]
        created = True
    if _playlist_has(playlist_id, video_id):
        return _log(vid, "playlist", "skipped", f"already in '{label}'")
    auth.api_request("POST", "playlistItems", params={"part": "snippet"},
                      json_body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
    return _log(vid, "playlist", "created+added" if created else "added",
                f"'{label}' — still set the end screen by hand, the API can't do that")


AUTOMATIONS = {"tags": do_tags, "disclosure": do_disclosure, "comment": do_comment, "playlist": do_playlist}


def run_finish(vid):
    """Runs every automation for one video, in order. Returns a result per step; never raises for a
    single step's failure so the others still get a chance."""
    pkg = jload(PKG / f"{vid}.json")
    if pkg is None:
        raise ValueError(f"No packaging for '{vid}'.")
    video_id = youtube_id(vid)
    if not video_id:
        raise ValueError(f"'{vid}' doesn't have a YouTube URL yet — it may not be live.")
    results = {}
    for step, fn in AUTOMATIONS.items():
        try:
            results[step] = fn(vid, video_id, pkg)
        except Exception as e:
            results[step] = _log(vid, step, "error", str(e))
    return {"video": vid, "youtube_id": video_id, "results": results,
            "comment_text": pkg.get("pinned_comment"), "playlist": series_label(pkg.get("title") or "")}


def run(body):
    vid = str((body or {}).get("video") or "")
    if not re.fullmatch(r"[a-z0-9_]{1,64}", vid):
        raise ValueError("bad video id")
    if not auth.connected():
        raise ValueError("Not connected to YouTube yet.")
    return run_finish(vid)


# ------------------------------------------------------------------ autorun (called from studio_ext_day.day())
def _autorun_state():
    return jload(AUTORUN_STATE_FILE, {}) or {}


def autorun_check(finish_cards):
    """finish_cards: studio_api.today()'s cards with kind == "finish". Runs automations once per
    video that just went live, if autorun is on and we're connected — silent no-op otherwise."""
    if not settings().get("autorun") or not auth.connected():
        return
    done = _autorun_state()
    changed = False
    for c in finish_cards:
        vid = c.get("video")
        if not vid or vid in done:
            continue
        try:
            run_finish(vid)
        except Exception as e:
            _log(vid, "autorun", "error", str(e))
        done[vid] = datetime.datetime.now().isoformat(timespec="seconds")
        changed = True
    if changed:
        with locked(AUTORUN_STATE_FILE):
            atomic_write_json(AUTORUN_STATE_FILE, done)


GET = {"/api/ytfinish/status": status}
POST = {"/api/ytfinish/connect": connect, "/api/ytfinish/disconnect": disconnect,
        "/api/ytfinish/autorun": set_autorun, "/api/ytfinish/run": run}
