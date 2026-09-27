"""Studio extension: her own photos/video per scene, for both the Short and the long-form episode.

Every scripted scene (a segment's "vis") either searches Wikimedia for a real photo, generates AI
art, or (for a "vid" scene) plays a video clip — see drafter.py/drafter_long.py and make_short.py's
docstring. This extension lets her replace any one scene's picture or clip with her own upload, so
the finished video uses real footage/photos where she has them instead of a stand-in.

  GET  /api/scenes/<id>              every scene of a Short (cfg/<id>.json) or an episode — resolved
                                      from either a draft/episode id or an already-rendered video's id
  POST /api/scenes/upload            {"id","key","data" (base64),"mime","rights"?,"ss"?} → replace one
                                      scene's vis with her photo (kb) or video (vid)
  POST /api/scenes/remove            {"id","key"} → restore the scene's original vis, delete her file
  POST /api/scenes/start             {"id","key","ss"} → change an uploaded video's start second

A long-form episode's chapters are re-assembled into cfg/<id>_long.json from episodes/<id>.json on
every render (make_long.py's assemble()), so edits here always go to the episode file, never to the
rendered cfg — otherwise a re-render would silently throw them away. A Short's cfg/<id>.json IS the
source, so edits go there directly. Scene "key" is the segment id for a Short, or "<chapter id>:<segment
id>" for an episode (chapter ids repeat "s1", "s2"... across chapters, so the bare id isn't unique).
"""
import base64
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from channel import DATA

CFG = DATA / "cfg"
EPS = DATA / "episodes"
ASSETS = DATA / "assets"
DRAFTS = DATA / "out" / "drafts"

ID_RE = re.compile(r"^[a-z0-9_]{1,80}$")
KEY_RE = re.compile(r"^[a-z0-9_]{1,40}(:[a-z0-9_]{1,40})?$")
FNAME_RE = re.compile(r"^[a-z0-9_]{3,140}\.(jpg|png|webp|mp4|mov|m4v)$")

PHOTO_MAX = 25 * 1024 * 1024
VIDEO_MAX = 500 * 1024 * 1024
PHOTO_MIME = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "heic": "heic", "heif": "heic"}
VIDEO_MIME = {"mp4": "mp4", "quicktime": "mov", "mov": "mov", "x-m4v": "m4v", "m4v": "m4v"}


def _vid(id_):
    v = str(id_ or "")
    if not ID_RE.match(v):
        raise ValueError("Which video?")
    return v


def _key(k):
    k = str(k or "")
    if not KEY_RE.match(k):
        raise ValueError("Which scene?")
    return k


def _target(vid):
    """(kind, id-to-save-under, path-to-read-and-write) for a Short or an episode, from any id a
    draft page, an episode page or an already-rendered video's page would pass in."""
    cfg_p = CFG / f"{vid}.json"
    if cfg_p.exists():
        try:
            cfg = json.loads(cfg_p.read_text())
        except Exception:
            cfg = {}
        ep_id = cfg.get("episode")
        if ep_id and (EPS / f"{ep_id}.json").exists():
            return "long", ep_id, EPS / f"{ep_id}.json"
        return "short", vid, cfg_p
    ep_p = EPS / f"{vid}.json"
    if ep_p.exists():
        return "long", vid, ep_p
    raise ValueError("No such video or episode.")


def _iter(kind, data):
    """(key, chapter label or None, segment dict) for every scene, in script order."""
    if kind == "short":
        for s in data.get("segments") or []:
            yield s["id"], None, s
        return
    for s in data.get("intro") or []:
        yield f"intro:{s['id']}", "Intro", s
    for c in data.get("chapters") or []:
        for s in c.get("segments") or []:
            yield f"{c['id']}:{s['id']}", c.get("title", c["id"]), s
    for s in data.get("outro") or []:
        yield f"outro:{s['id']}", "Outro", s


def _find(kind, data, key):
    for k, _, seg in _iter(kind, data):
        if k == key:
            return seg
    raise ValueError("That scene isn't part of this video any more.")


def _save(path, data):
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def _thumb_name(src):
    return re.sub(r"\.[^.]+$", "", src) + "_thumb.jpg"


def _thumb(v):
    t = v.get("t")
    src = v.get("src")
    if t == "kb" and src:
        return f"/asset/{src}"
    if t == "vid" and src:
        tn = _thumb_name(src)
        tp = ASSETS / tn
        sp = ASSETS / src
        if not tp.exists() and sp.exists():
            try:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(v.get("ss", 0) or 0), "-i", str(sp),
                                 "-frames:v", "1", "-vf", "scale=320:-2", str(tp)], check=True, timeout=25, capture_output=True)
            except Exception:
                return None
        return f"/asset/{tn}" if tp.exists() else None
    return None


def _source(v):
    if v.get("own"):
        return "own"
    t = v.get("t")
    if t == "kb":
        return "wikimedia" if v.get("real") else "ai" if v.get("prompt") else "reused"
    if t == "vid":
        return "reused"          # a scripted video clip that isn't (yet) marked as her own upload
    return "none"


def _hint(v):
    if v.get("real"):
        return v["real"].get("query")
    return v.get("prompt")


def _facts(base, data):
    try:
        rec = json.loads((DRAFTS / f"{base}.json").read_text())
        facts = (rec.get("research") or {}).get("facts")
        if facts:
            return facts
    except Exception:
        pass
    return (data.get("research") or {}).get("facts") or []


def _match_fact(hint, facts):
    if not hint:
        return None
    words = {w.lower() for w in re.findall(r"[a-zA-Z]{4,}", hint)}
    if not words:
        return None
    for f in facts:
        claim = f.get("claim", "")
        if words & {w.lower() for w in re.findall(r"[a-zA-Z]{4,}", claim)}:
            return claim
    return None


def scenes(vid):
    vid = _vid(vid)
    kind, base, path = _target(vid)
    data = json.loads(path.read_text())
    facts = _facts(base, data)
    out = []
    for key, chapter, seg in _iter(kind, data):
        v = seg.get("vis") or {}
        hint = _hint(v)
        out.append({"key": key, "chapter": chapter, "text": seg.get("text", ""), "type": v.get("t"),
                    "thumb": _thumb(v), "source": _source(v), "hint": hint, "fact": _match_fact(hint, facts),
                    "own_media_rights": seg.get("own_media_rights"), "ss": v.get("ss") if v.get("t") == "vid" else None})
    return {"id": vid, "kind": kind, "scenes": out}


def _decode(body):
    data = str(body.get("data") or "")
    if not data:
        raise ValueError("No file came through — try again.")
    try:
        return base64.b64decode(data.split(",", 1)[-1], validate=True)
    except Exception:
        raise ValueError("That doesn't look like an uploaded file — try again.")


def _ext_for(mime):
    """(kind "photo"/"video", extension) from an allow-listed mime type, or a ValueError."""
    mime = str(mime or "").lower()
    if mime.startswith("image/"):
        sub = mime.split("/", 1)[1]
        if sub in PHOTO_MIME:
            return "photo", PHOTO_MIME[sub]
        raise ValueError("Upload a photo — jpg, png, webp or heic.")
    if mime.startswith("video/"):
        sub = mime.split("/", 1)[1]
        if sub in VIDEO_MIME:
            return "video", VIDEO_MIME[sub]
        raise ValueError("Upload a video — mp4, mov or m4v.")
    raise ValueError("That file's type isn't a photo or a video NETHER recognises.")


def _ffprobe_has_video(p):
    try:
        out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                       "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(p)],
                                      timeout=20).decode().strip()
        return out == "video"
    except Exception:
        return False


def upload(body):
    vid = _vid(body.get("id"))
    key = _key(body.get("key"))
    kind, base, path = _target(vid)
    data = json.loads(path.read_text())
    seg = _find(kind, data, key)
    raw = _decode(body)
    media_kind, ext = _ext_for(body.get("mime"))
    if media_kind == "photo" and len(raw) > PHOTO_MAX:
        raise ValueError("That photo is too large (over 25 MB).")
    if media_kind == "video" and len(raw) > VIDEO_MAX:
        raise ValueError("That video is too large (over 500 MB).")
    if len(raw) < 200:
        raise ValueError("That file looks empty — try uploading it again.")

    safe_key = key.replace(":", "_")
    ASSETS.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkstemp(dir=ASSETS, suffix=f".{ext}")[1])
    tmp.write_bytes(raw)
    try:
        if media_kind == "photo":
            if ext == "heic":
                jp = tmp.with_suffix(".jpg")
                try:
                    subprocess.run(["sips", "-s", "format", "jpeg", str(tmp), "--out", str(jp)],
                                   check=True, timeout=30, capture_output=True)
                except Exception:
                    raise ValueError("That HEIC photo didn't convert — save it as JPG (e.g. from Photos) and upload that instead.")
                tmp.unlink(missing_ok=True)
                tmp, ext = jp, "jpg"
            try:
                with Image.open(tmp) as im:
                    im.verify()
            except Exception:
                raise ValueError("That doesn't look like a readable photo — try a different file.")
        else:
            if not _ffprobe_has_video(tmp):
                raise ValueError("That doesn't look like a readable video — try a different file.")

        fname = f"{vid}_{safe_key}_own.{ext}"
        if not FNAME_RE.match(fname):
            raise ValueError("That scene can't be named safely — try a different id.")
        dst = ASSETS / fname
        for old in ASSETS.glob(f"{vid}_{safe_key}_own.*"):    # a previous own-upload for this exact scene
            if old != tmp:
                old.unlink(missing_ok=True)
        for old in ASSETS.glob(f"{vid}_{safe_key}_own_thumb.jpg"):
            old.unlink(missing_ok=True)
        shutil.move(str(tmp), str(dst))
    finally:
        tmp.unlink(missing_ok=True)   # no-op once moved

    rights = seg.get("own_media_rights")
    if not rights:
        rights = str(body.get("rights") or "")
        if rights not in ("own", "free"):
            dst.unlink(missing_ok=True)
            raise ValueError("Is this your own photo/video, or free to use? Say which, then upload again.")
        seg["own_media_rights"] = rights

    if "_prev_vis" not in seg:
        seg["_prev_vis"] = dict(seg.get("vis") or {})
    prev = seg.get("vis") or {}
    if media_kind == "photo":
        new_vis = {"t": "kb", "src": fname, "z0": prev.get("z0", 1.05) if prev.get("t") == "kb" else 1.05,
                   "z1": prev.get("z1", 1.05) if prev.get("t") == "kb" else 1.05,
                   "cx": prev.get("cx", 0.5), "cy": prev.get("cy", 0.5), "own": True}
    else:
        try:
            ss = max(0.0, float(body.get("ss") or 0))
        except (TypeError, ValueError):
            ss = 0.0
        new_vis = {"t": "vid", "src": fname, "ss": ss, "fit": "cover", "own": True}
    seg["vis"] = new_vis
    _save(path, data)
    return {"ok": True, "id": vid, "key": key, "thumb": _thumb(new_vis), "source": "own",
            "own_media_rights": seg["own_media_rights"], "reply": "Saved — the next render uses it."}


def start(body):
    vid = _vid(body.get("id"))
    key = _key(body.get("key"))
    kind, base, path = _target(vid)
    data = json.loads(path.read_text())
    seg = _find(kind, data, key)
    v = seg.get("vis") or {}
    if v.get("t") != "vid" or not v.get("own"):
        raise ValueError("This scene doesn't have your own video on it.")
    try:
        ss = max(0.0, float(body.get("ss") or 0))
    except (TypeError, ValueError):
        raise ValueError("That start time doesn't look like a number.")
    v["ss"] = ss
    (ASSETS / _thumb_name(v["src"])).unlink(missing_ok=True)   # regenerate at the new start next time it's shown
    _save(path, data)
    return {"ok": True, "thumb": _thumb(v), "ss": ss}


def remove(body):
    vid = _vid(body.get("id"))
    key = _key(body.get("key"))
    kind, base, path = _target(vid)
    data = json.loads(path.read_text())
    seg = _find(kind, data, key)
    if "_prev_vis" not in seg:
        raise ValueError("This scene isn't using your own media.")
    old = seg.get("vis") or {}
    safe_key = key.replace(":", "_")
    if old.get("own") and old.get("src"):
        for old_f in ASSETS.glob(f"{vid}_{safe_key}_own.*"):
            old_f.unlink(missing_ok=True)
        (ASSETS / _thumb_name(old["src"])).unlink(missing_ok=True)
    seg["vis"] = seg.pop("_prev_vis")
    seg.pop("own_media_rights", None)
    _save(path, data)
    v = seg["vis"]
    hint = _hint(v)
    return {"ok": True, "vis": {"type": v.get("t"), "thumb": _thumb(v), "source": _source(v), "hint": hint}}


GET_PREFIX = {"/api/scenes/": scenes}
POST = {"/api/scenes/upload": upload, "/api/scenes/start": start, "/api/scenes/remove": remove}
