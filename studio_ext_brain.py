"""Studio extension: NETHER's body and memory.

GET  /api/organ             the organ NETHER takes the form of now (organs/<name>.json), plus every choice
GET  /api/organ/<name>      one organ's shape file (to preview it in Settings)
POST /api/organ             {"name"} → sets the form; stored in out/brain_state.json
GET  /api/brain/actions     Studio job action → the agent that does it (so a running job pulses its region)
GET  /api/memory            LEARNINGS.md as a web: nodes (sections, hypotheses, evidence rows, notes, lessons,
                            dates) and links (same video, same date, shared keywords, section). Only what the
                            file says — nothing is summarised or invented.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import orchestrator as nether

HERE = Path(__file__).resolve().parent
ORGANS = HERE / "organs"
STATE = HERE / "out" / "brain_state.json"
LEARN = HERE / "LEARNINGS.md"
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


def _plain(s):
    return re.sub(r"\*\*|`", "", s).strip()


def _title(s):
    b = re.search(r"\*\*(.+?)\*\*", s)
    t = _plain(b[1] if b else s)
    return t if len(t) <= 72 else t[:70].rsplit(" ", 1)[0] + "…"


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
    mtime = datetime.fromtimestamp(LEARN.stat().st_mtime).isoformat(timespec="minutes") if LEARN.is_file() else None
    return {"file": "LEARNINGS.md", "updated": mtime, "nodes": nodes, "links": links}


GET = {"/api/organ": organ, "/api/brain/actions": actions, "/api/memory": memory}
GET_PREFIX = {"/api/organ/": lambda rest: _organ(rest)}
POST = {"/api/organ": set_organ}
