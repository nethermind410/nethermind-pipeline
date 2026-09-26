"""Studio extension: Retention & Episodes page.

GET  /api/retention           every video's pacing checklist beside its real TikTok/IG watch time
POST /api/retention/tiktok    {"id"} → writes cfg/<id>_tiktok.json (the retention cut), returns its checklist
POST /api/episode/build       {"id"} → runs episode.py on episodes/<id>.json, returns the chapters

Real watch time comes from out/stats.json (stats.py), so the page shows whether
the checklist and the results agree — the checklist alone predicts nothing yet.
"""
import json, re, subprocess, sys
from pathlib import Path

import retention

HERE = Path(__file__).parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
CFG, EPS, OUT = DATA / "cfg", DATA / "episodes", DATA / "out"


def _load(p, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _rows(cfg):
    score, rows = retention.check(cfg)
    return {"score": score, "rows": [{"ok": ok, "msg": m} for ok, m in rows],
            "length": round(retention.total(cfg))}


def _watch(posts, platform):
    ps = [p for p in posts if p.get("platform") == platform]
    if not ps:
        return None
    w = [p["averageTimeWatched"] for p in ps if p.get("averageTimeWatched") is not None]
    return {"views": int(sum(p.get("views") or 0 for p in ps)),
            "avg_watch": round(sum(w) / len(w), 1) if w else None}


def overview():
    stats = (_load(OUT / "stats.json", {}) or {}).get("videos", {})
    vids = []
    for p in sorted(CFG.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        vid = p.stem
        if vid.endswith("_tiktok") or vid.startswith(("test", "_")):
            continue
        cfg = _load(p)
        if not cfg or "segments" not in cfg or cfg.get("format") == "landscape":   # long-form isn't a Short
            continue
        tk = _load(CFG / f"{vid}_tiktok.json")
        posts = stats.get(vid, [])
        title = (_load(DATA / "packaging" / f"{vid}.json", {}) or {}).get("title") \
            or " ".join(l[0] for l in cfg.get("hook", {}).get("lines", [])) or vid.replace("_", " ")
        vids.append({"id": vid, "hook": title,
                     "main": _rows(cfg), "tiktok": _rows(tk) if tk else None,
                     "real": {k: _watch(posts, k) for k in ("youtube", "tiktok", "instagram")}})
    eps = []
    for p in sorted(EPS.glob("*.json")):
        if p.stem.startswith("_"):
            continue
        ep = _load(p, {})
        eps.append({"id": p.stem, "title": ep.get("title", p.stem),
                    "chapters": [c.get("title", c.get("id")) for c in ep.get("chapters", [])],
                    "planned": (EPS / f"{p.stem}.plan.md").exists()})
    return {"videos": vids, "episodes": eps, "stats_updated": (_load(OUT / "stats.json", {}) or {}).get("updated")}


def _id(body):
    vid = str(body.get("id", ""))
    if not re.fullmatch(r"[a-z0-9_]+", vid):
        raise ValueError("That id isn't valid.")
    return vid


def make_tiktok(body):
    vid = _id(body)
    cfg = _load(CFG / f"{vid}.json")
    if not cfg:
        raise ValueError(f"No cfg/{vid}.json.")
    cut = retention.tiktok(cfg, float(body.get("max", 35)))
    (CFG / f"{cut['id']}.json").write_text(json.dumps(cut, indent=1, ensure_ascii=False) + "\n")
    return {"ok": True, "id": cut["id"], **_rows(cut),
            "reply": f"TikTok cut written. Build it with ./build.sh {vid} --no-fetch."}


def build_episode(body):
    eid = _id(body)
    path = EPS / f"{eid}.json"
    if not path.exists():
        raise ValueError(f"No episodes/{eid}.json.")
    r = subprocess.run([sys.executable, str(HERE / "episode.py"), str(path)],
                       capture_output=True, text=True, cwd=HERE, timeout=60)
    if r.returncode:
        raise ValueError((r.stderr or r.stdout).strip()[-400:])
    return {"ok": True, "log": r.stdout, "plan": (EPS / f"{eid}.plan.md").read_text()}


GET = {"/api/retention": overview}
POST = {"/api/retention/tiktok": make_tiktok, "/api/episode/build": build_episode}
