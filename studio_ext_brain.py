"""Studio extension: NETHER's body and memory.

GET  /api/organ             the organ NETHER takes the form of now (organs/<name>.json), plus every choice
GET  /api/organ/<name>      one organ's shape file (to preview it in Settings)
POST /api/organ             {"name"} → sets the form; stored in out/brain_state.json
GET  /api/brain/actions     Studio job action → the agent that does it (so a running job pulses its region)
GET  /api/memory            LEARNINGS.md as a brain: every rule/hypothesis/lesson/evidence row sorted into a
                            theme (a brain region), with how sure NETHER is and what it actually does about it.
                            Only what the file and out/ actually say — nothing is summarised or invented.
POST /api/memory/decide     {"id", "decision": "keep"|"test"|"drop"} → out/memory_decisions.json
"""
import json
import re
from datetime import datetime
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
ORGANS = HERE / "organs"
STATE = DATA / "out" / "brain_state.json"
LEARN = DATA / "LEARNINGS.md"
DECISIONS = DATA / "out" / "memory_decisions.json"
WEIGHTS_F = DATA / "out" / "intel_weights.json"
STATS_F = DATA / "out" / "stats.json"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def _choices():
    out = []
    for p in sorted(ORGANS.glob("*.json")):
        try:
            o = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        out.append({"name": p.stem, "title": o.get("title", p.stem.title()), "blurb": o.get("blurb", "")})
    return sorted(out, key=lambda c: (c["name"] != "brain", c["title"]))


def _organ(name):
    if not NAME_RE.match(name or "") or not (ORGANS / f"{name}.json").is_file():
        raise ValueError("No such form.")
    o = json.loads((ORGANS / f"{name}.json").read_text())
    if name != "brain":            # the brain's section anchors, so callers' brain coordinates map onto this organ
        b = json.loads((ORGANS / "brain.json").read_text())
        pts = [pt for part in b["parts"] for pt in part["poly"]]
        o["canon"] = {"sections": {k: [b["regions"][r]["ax"], b["regions"][r]["ay"]] for k, r in b["sections"].items()},
                      "bbox": [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]}
    return o


def organ():
    name = _state().get("organ", "brain")
    try:
        o = _organ(name)
    except (ValueError, OSError):
        name, o = "brain", _organ("brain")
    return {"name": name, "organ": o, "choices": _choices()}


def set_organ(body):
    name = str(body.get("name", "")).strip().lower()
    o = _organ(name)
    s = _state()
    s["organ"] = name
    s["organ_set"] = datetime.now().isoformat(timespec="seconds")
    STATE.write_text(json.dumps(s, indent=1) + "\n")
    return {"ok": True, "name": name, "reply": f"NETHER now takes the form of {'a' if name != 'eye' else 'an'} {o.get('title', name).lower()}."}


def actions():
    return {a: agent for a, (agent, _sub) in nether.STUDIO_ACTIONS.items()} | {"build": "production", "build_nofetch": "production"}


# ---------- memory ----------
STOP = set("""the and for that with this from are was were been have has had not but you your our its it's they them their
there than then when what which who will would should could can into onto over under about after before only also just more
most less very each every any all some one two three per via like same other such does did done make made making video videos
views total notes note so far yet here read write written update updated numbers number say says said day days week""".split())
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b|\b(\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\b")

# ---- themes: brain regions LEARNINGS.md's ideas get sorted into. Deterministic keyword rules, checked in this
# order (first match wins) — a note about "verifying a fact" outranks one about "footage" outranks a platform
# name, etc., because the earlier categories are more specific. Anything matching nothing is "other".
# ax/ay are the same coordinates orchestrator.AGENTS/brain.json use for the home brain's regions, so a learning
# lights up literally the same patch of cortex the matching Studio section already sits on.
THEMES = [
    ("trust",      "Accuracy & trust",      0.53, 0.60, ["verify", "fact", "source", "accuracy", "rank agreement", "review"]),
    ("production", "Production & visuals",  0.85, 0.46, ["footage", "photo", "wikimedia", "ai art", "gutenberg", "public-domain", "visuals"]),
    ("timing",     "Timing",                 0.74, 0.72, ["queued", "posted", "schedule", "cadence", "streak", "too early"]),
    ("hooks",      "Hooks & format",         0.36, 0.64, ["hook", "title", "thumbnail", "end card", "format", "chain", "opening", "caption"]),
    ("topics",     "Topics",                 0.30, 0.40, ["topic", "marvel", "anime", "gaming", "lane", "hero", "animal", "taste", "demand", "competition", "fit"]),
    ("platforms",  "Platforms",              0.70, 0.29, ["youtube", "tiktok", "instagram", "platform", "buffer"]),
]
THEME_BY_ID = {t[0]: t for t in THEMES}
OTHER = ("other", "Other", 0.47, 0.22, [])


def classify(text):
    low = text.lower()
    for tid, _label, _ax, _ay, kws in THEMES:
        if any(k in low for k in kws):
            return tid
    return OTHER[0]


def _plain(s):
    return re.sub(r"\*\*|`", "", s).strip()


def _title(s):
    b = re.search(r"\*\*(.+?)\*\*", s)
    t = _plain(b[1] if b else s)
    return t if len(t) <= 72 else t[:70].rsplit(" ", 1)[0] + "…"


def _decisions():
    try:
        return json.loads(DECISIONS.read_text())
    except (OSError, ValueError):
        return {}


def decide_memory(body):
    nid = str(body.get("id", ""))
    choice = str(body.get("decision", ""))
    if choice not in ("keep", "test", "drop") or not re.fullmatch(r"[a-zA-Z0-9:_-]{1,40}", nid or ""):
        raise ValueError("Pick Keep, Test more, or Drop.")
    d = _decisions()
    d[nid] = {"decision": choice, "at": datetime.now().isoformat(timespec="seconds")}
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(json.dumps(d, indent=1))
    return {"ok": True, "id": nid, "decision": choice}


def _weights():
    try:
        return json.loads(WEIGHTS_F.read_text())
    except (OSError, ValueError):
        return {"weights": {}, "history": [], "checked": 0, "rank_agreement": None}


def _views():
    try:
        vids = json.loads(STATS_F.read_text()).get("videos", {})
    except (OSError, ValueError):
        return {}
    return {v: int(sum(p.get("views") or 0 for p in ps)) for v, ps in vids.items()}


WEIGHT_WORDS = ("demand", "competition", "fit", "taste", "visuals", "sources")


def _used_text(n, theme, weights):
    """What NETHER actually does with a learning — grounded in real code/config, never invented."""
    low = n["text"].lower()
    if n["kind"] == "rule":
        if any(k in low for k in ("footage", "photo", "wikimedia", "ai art")):
            return "Enforced by fetch_real.py: real-animal videos pull Wikimedia footage and public-domain photos automatically."
        if "verify" in low or "source" in low or "fact" in low:
            return "drafter.py checks facts against a source while scripting — the final read is still yours."
        if "end card" in low or "chain" in low:
            return "episode.py and drafter.py write each video's end card to point at the next one."
        if "post automatically" in low or "reviews and posts" in low:
            return "Nothing in Studio posts without your click — every publish action waits for you."
        return "Your rule — followed on every video; nothing here checks it for you automatically."
    if n["kind"] == "lesson":
        if "rank agreement" in low:
            acc = weights.get("rank_agreement")
            return (f"Feeds NETHER's own scoring accuracy check — currently {acc:+.2f}." if acc is not None
                     else "Would feed NETHER's scoring accuracy check, once enough videos are linked.")
        if "nothing learned yet" in low:
            return "Not used yet — no lessons recorded."
        hit = next((w for w in WEIGHT_WORDS if w in low), None)
        if hit and hit in weights.get("weights", {}):
            default = {"demand": 30.0, "competition": 15.0, "fit": 20.0, "taste": 10.0, "visuals": 15.0, "sources": 10.0}.get(hit)
            now = weights["weights"][hit]
            if default is not None and abs(now - default) > 0.05:
                return f"NETHER's topic scoring now weighs \"{hit}\" at {now:g}% (was {default:g}%) because of this."
            return f"NETHER's topic scoring weighs \"{hit}\" at {now:g}% — still the default; not enough results to move it yet."
        return "Written down as a lesson, but nothing in NETHER's scoring reacts to it yet."
    if theme == "topics" and n["kind"] == "hypothesis":
        return "Not used yet — NETHER doesn't route topic choices by this on its own; needs more evidence first."
    return "Not used yet — only written down."


def _proof_text(n, views):
    vids = n.get("videos") or []
    if not vids:
        m = re.search(r"(\d+)\s+of\s+(\d+)\s+(?:videos|scorecards|topics)", n["text"], re.I)
        if m:
            return f"{m[1]} of {m[2]} — from real decisions, no video evidence yet."
        m = re.search(r"across (\d+) made videos", n["text"], re.I)
        if m:
            return f"{m[1]} posted video(s) checked."
        return "No proof yet."
    seen = {v: views.get(v) for v in vids}
    if all(v is None for v in seen.values()):
        return f"{len(vids)} video{'s' if len(vids) != 1 else ''} named ({', '.join(vids)}) — no view counts yet."
    parts = [f"{v}: {seen[v]:,} views" if seen[v] is not None else f"{v}: no views yet" for v in vids]
    return f"{len(vids)} video{'s' if len(vids) != 1 else ''} · " + " vs ".join(parts)


def _tier(n):
    if n["kind"] == "rule":
        return {"tier": "rule", "label": "Your rule", "brightness": 1.0}
    vids = n.get("videos") or []
    n_ev = len(vids)
    if n_ev == 0:
        m = re.search(r"(\d+)\s+of\s+(\d+)\s+(?:videos|scorecards|topics)", n["text"], re.I) or \
            re.search(r"across (\d+) made videos", n["text"], re.I)
        n_ev = int(m.group(m.lastindex)) if m else 0
    if n_ev >= 3:
        return {"tier": "proven", "label": "Proven", "brightness": 1.0}
    if n_ev == 2:
        return {"tier": "building", "label": "Building", "brightness": 0.72}
    if n_ev == 1:
        return {"tier": "hunch", "label": "Hunch", "brightness": 0.46}
    return {"tier": "none", "label": "No proof yet", "brightness": 0.26}


def memory():
    text = LEARN.read_text() if LEARN.is_file() else ""
    vids = {p.stem for p in (HERE / "cfg").glob("*.json")}
    nodes, section, table_head = [], None, None
    kind_of = lambda h: ("hypothesis" if "hypothes" in h else "lesson" if "learn" in h else
                         "evidence" if "evidence" in h else "rule" if re.search(r"rule|feedback|review", h) else "note")
    in_comment = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if in_comment or line.strip().startswith("<!--"):
            in_comment = "-->" not in line and (in_comment or "<!--" in line)
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            section = {"id": f"n{len(nodes)}", "kind": "section", "title": _plain(line[3:]), "text": line[3:].strip(), "section": None}
            nodes.append(section); table_head = None
            continue
        if not line.strip():
            table_head = None
            continue
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if table_head is None:
                table_head = cells
                continue
            body = " · ".join(f"{h}: {c}" for h, c in zip(table_head, cells) if c)
            nodes.append({"id": f"n{len(nodes)}", "kind": "evidence", "title": _plain(cells[0]), "text": body,
                          "section": section and section["id"], "src": " ".join(cells)})
            continue
        m = re.match(r"^\s*[-*] (.+)", line)
        if m and section:
            nodes.append({"id": f"n{len(nodes)}", "kind": kind_of(section["title"].lower()), "title": _title(m[1]), "text": m[1].strip(),
                          "section": section["id"]})
        elif raw.startswith(("  ", "\t")) and nodes and nodes[-1]["kind"] != "section":
            nodes[-1]["text"] += " " + line.strip()                 # a bullet carried onto the next line
        elif section:
            section["text"] += "\n" + line.strip()
        else:                                                      # the preamble under the title
            nodes.append({"id": f"n{len(nodes)}", "kind": "note", "title": _title(line), "text": line.strip(), "section": None})
    # what each node mentions
    for n in nodes:
        low = n["text"].lower()
        n["dates"] = sorted({a or b for a, b in DATE_RE.findall(n["text"])})
        n["videos"] = sorted(v for v in vids if re.search(rf"(?<![a-z0-9_]){re.escape(v)}(?![a-z0-9_])", low))
        n["words"] = {w for w in re.findall(r"[a-z][a-z'’-]{3,}", _plain(n.pop("src", low).lower())) if w not in STOP}
    links, seen = [], set()

    def link(a, b, why, w):
        k = tuple(sorted((a, b)))
        if a != b and k not in seen:
            seen.add(k); links.append({"a": a, "b": b, "why": why, "w": w})
    for n in nodes:                                                # sections hold their notes
        if n["section"]:
            link(n["id"], n["section"], "same section", 1)
    for d in sorted({d for n in nodes for d in n["dates"]}):       # a date is a node of its own
        did = "d:" + d
        nodes.append({"id": did, "kind": "date", "title": d, "text": f"Mentioned on {d}.", "section": None, "dates": [d], "videos": [], "words": set()})
        for n in nodes:
            if n["id"] != did and d in n["dates"]:
                link(n["id"], did, f"mentions {d}", 2)
    body = [n for n in nodes if n["kind"] not in ("section", "date")]
    df = {}
    for n in body:
        for w in n["words"]:
            df[w] = df.get(w, 0) + 1
    for i, a in enumerate(body):
        for b in body[i + 1:]:
            same = sorted(set(a["videos"]) & set(b["videos"]))
            if same:
                link(a["id"], b["id"], "same video: " + ", ".join(same), 3)
                continue
            shared = sorted((w for w in a["words"] & b["words"] if df[w] <= max(2, len(body) // 3)), key=lambda w: df[w])
            if len(shared) >= 2:
                link(a["id"], b["id"], "shared words: " + ", ".join(shared[:4]), 1.5)
    for n in nodes:
        n.pop("words", None)

    # ---- theme, confidence and use, for every learning (not sections/dates) ----
    weights, views, decisions = _weights(), _views(), _decisions()
    themes_out = {tid: {"id": tid, "label": label, "ax": ax, "ay": ay, "learnings": []}
                  for tid, label, ax, ay, _kws in THEMES}
    themes_out[OTHER[0]] = {"id": OTHER[0], "label": OTHER[1], "ax": OTHER[2], "ay": OTHER[3], "learnings": []}
    for n in body:
        theme = classify(n["title"] + " " + n["text"])
        n["theme"] = theme
        n.update(_tier(n))
        n["proof"] = _proof_text(n, views)
        n["used"] = _used_text(n, theme, weights)
        dec = decisions.get(n["id"])
        if dec:
            n["decision"] = dec["decision"]
        themes_out[theme]["learnings"].append(n["id"])
    proven = sum(1 for n in body if n.get("tier") in ("proven", "rule"))
    hunches = sum(1 for n in body if n.get("tier") == "hunch")
    mtime = datetime.fromtimestamp(LEARN.stat().st_mtime).isoformat(timespec="minutes") if LEARN.is_file() else None
    return {"file": "LEARNINGS.md", "updated": mtime, "nodes": nodes, "links": links,
            "themes": list(themes_out.values()),
            "summary": {"total": len(body), "proven": proven, "hunches": hunches}}


GET = {"/api/organ": organ, "/api/brain/actions": actions, "/api/memory": memory}
GET_PREFIX = {"/api/organ/": lambda rest: _organ(rest)}
POST = {"/api/organ": set_organ, "/api/memory/decide": decide_memory}
