"""studio_create.py — the "make better videos" tools behind the app.

  Inspiration board  out/inspiration.json + inspiration/<id>.<ext>   (the daily build reads it for art direction)
  Script workshop    edit a video's lines in cfg/<id>.json; re-render re-records only changed lines
  Hook options       packaging/<id>.json "hook_options" (written by the daily build); picking one sets line 1
  Series planner     out/series.json — ordered runs of ideas; the build makes the next unmade one
"""
import base64, datetime, json, re, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
from store import atomic_write_json, atomic_write_text
OUT, CFG, PKG = DATA / "out", DATA / "cfg", DATA / "packaging"
INSP_DIR, INSP = DATA / "inspiration", OUT / "inspiration.json"
SERIES = OUT / "series.json"
ID_RE = re.compile(r"^[a-z0-9_]+$")


def jload(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def now():
    return datetime.datetime.now().isoformat(timespec="minutes")


# ------------------------------------------------------------------ inspiration board
def inspiration():
    return jload(INSP, [])


def add_inspiration(data_url, note, url=""):
    items = inspiration()
    item = {"id": uuid.uuid4().hex[:12], "note": str(note or "").strip()[:400], "at": now()}
    if data_url:
        m = re.fullmatch(r"data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=]+)", data_url or "")
        if not m:
            raise ValueError("Only PNG, JPG, WebP or GIF images.")
        raw = base64.b64decode(m[2])
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("That image is over 12 MB.")
        INSP_DIR.mkdir(exist_ok=True)
        ext = "jpg" if m[1] == "jpeg" else m[1]
        (INSP_DIR / f"{item['id']}.{ext}").write_bytes(raw)
        item["file"] = f"{item['id']}.{ext}"
    elif url and re.match(r"^https?://", url):
        item["url"] = url[:500]
    else:
        raise ValueError("Add an image or a link.")
    items.insert(0, item)
    atomic_write_json(INSP, items)
    return item


def remove_inspiration(iid):
    items = inspiration()
    keep = [i for i in items if i["id"] != iid]
    for i in items:
        if i["id"] == iid and i.get("file"):
            (INSP_DIR / i["file"]).unlink(missing_ok=True)
    atomic_write_json(INSP, keep)
    return {"ok": True}


# ------------------------------------------------------------------ script workshop + hooks
def save_script(vid, lines):
    """lines: {segment_id: text}. Only text changes; visuals/timing stay. Returns what changed."""
    p = CFG / f"{vid}.json"
    if not (ID_RE.match(vid) and p.exists()):
        raise ValueError("Unknown video.")
    cfg = json.loads(p.read_text())
    changed = []
    for s in cfg["segments"]:
        new = str(lines.get(s["id"], s["text"])).strip()
        if not new:
            raise ValueError(f"Line {s['id']} can't be empty.")
        if len(new) > 600:
            raise ValueError(f"Line {s['id']} is too long.")
        if new != s["text"]:
            changed.append(s["id"])
            s["text"] = new
    atomic_write_text(p, json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    return {"ok": True, "changed": changed}


def hooks(vid):
    """Hook options for a video, plus the real first lines + YouTube views of past videos as reference."""
    pkg = jload(PKG / f"{vid}.json", {}) or {}
    cfg = jload(CFG / f"{vid}.json", {}) or {}
    current = (cfg.get("segments") or [{}])[0].get("text", "")
    opts = [o for o in pkg.get("hook_options", []) if isinstance(o, str)]
    if current and current not in opts:
        opts.insert(0, current)
    import studio_api
    past = []
    for v in studio_api.videos():
        if v["id"] == vid or not v["posts"] or not v["script"]:
            continue
        yt = next((p["views"] for p in v["posts"] if p.get("platform") == "youtube" and p.get("source") == "YouTube"), None)
        if yt is not None:
            past.append({"title": v["title"], "hook": v["script"][0], "views": yt})
    past.sort(key=lambda x: -x["views"])
    return {"options": [{"text": o, "current": o == current} for o in opts], "past": past[:6]}


def choose_hook(vid, text):
    h = hooks(vid)
    if text not in [o["text"] for o in h["options"]]:
        raise ValueError("Pick one of the listed hooks.")
    first = (jload(CFG / f"{vid}.json", {})["segments"][0]["id"])
    return save_script(vid, {first: text})


# ------------------------------------------------------------------ series planner
def series():
    return jload(SERIES, [])


def save_series(data):
    clean = []
    for s in data[:20]:
        name = str(s.get("name", "")).strip()[:80]
        if not name:
            continue
        items = [{"hook": str(i.get("hook", "")).strip()[:200], "video": i.get("video") if ID_RE.match(str(i.get("video") or "")) else None}
                 for i in s.get("items", [])[:30] if str(i.get("hook", "")).strip()]
        clean.append({"id": s.get("id") or uuid.uuid4().hex[:8], "name": name, "active": bool(s.get("active")),
                      "note": str(s.get("note", ""))[:300], "items": items})
    if sum(s["active"] for s in clean) > 1:  # only one series drives the build at a time
        first = next(i for i, s in enumerate(clean) if s["active"])
        for i, s in enumerate(clean):
            s["active"] = i == first
    atomic_write_json(SERIES, clean)
    return {"ok": True, "series": clean}
