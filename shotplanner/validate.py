"""
Plan validation: structure first, then the cross-field rules.

  errors, warnings = validate_plan(plan)

Structure is checked against schemas/shotplan-0.2.schema.json using the
`jsonschema` package if it's installed, or otherwise the small built-in
checker below. The built-in one handles only the keywords our schemas use.
The cross-field rules cover what JSON Schema can't express: the narration
covers the whole script, IDs and references resolve, each generation mode has
the keyframes it needs, and so on.
"""
import json
import os
import re

from . import SCHEMA_ID
from .prompts import fluff_in
from .text import tokens
from .timing import HARD_MIN_SHOT_S, MAX_SHOT_S, MIN_SHOT_S, SOFT_MAX_SHOT_S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(ROOT, "schemas")


def load_schema(name):
    with open(os.path.join(SCHEMAS, name)) as f:
        return json.load(f)


# ------------------------------------------------------------------ structure
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _TYPES[t])


def _mini(v, s, root, path, errs):
    if "$ref" in s:
        s = root["$defs"][s["$ref"].split("/")[-1]]
    if "type" in s:
        types = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_is(v, t) for t in types):
            errs.append(f"{path}: expected {'/'.join(types)}, got {type(v).__name__}")
            return
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: must be {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not one of {s['enum']}")
    if isinstance(v, str):
        if len(v) < s.get("minLength", 0):
            errs.append(f"{path}: empty")
        if "pattern" in s and not re.search(s["pattern"], v):
            errs.append(f"{path}: {v!r} does not match {s['pattern']}")
    if _is(v, "number"):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: {v} < {s['minimum']}")
        if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
            errs.append(f"{path}: {v} <= {s['exclusiveMinimum']}")
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: needs at least {s['minItems']} item(s)")
        if "items" in s:
            for i, x in enumerate(v):
                _mini(x, s["items"], root, f"{path}[{i}]", errs)
    if isinstance(v, dict):
        if len(v) < s.get("minProperties", 0):
            errs.append(f"{path}: needs at least {s['minProperties']} entr(ies)")
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing '{k}'")
        props = s.get("properties", {})
        extra = s.get("additionalProperties", True)
        for k, x in v.items():
            if k in props:
                _mini(x, props[k], root, f"{path}.{k}", errs)
            elif extra is False:
                errs.append(f"{path}: unexpected field '{k}'")
            elif isinstance(extra, dict):
                _mini(x, extra, root, f"{path}.{k}", errs)


def check_structure(obj, schema):
    try:
        import jsonschema
    except ImportError:
        errs = []
        _mini(obj, schema, schema, "$", errs)
        return errs
    v = jsonschema.Draft202012Validator(schema)
    return [f"$.{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in v.iter_errors(obj)]


# ------------------------------------------------------------------ semantics
REQUIRED_KEYFRAMES = {
    "i2v_single_keyframe": ["start"], "i2v_first_last": ["start", "end"],
    "still_kenburns": ["start"], "t2v": [], "stock_footage": [],
}


def check_semantics(plan):
    errs, warns = [], []
    if plan.get("schema") != SCHEMA_ID:
        errs.append(f"schema is {plan.get('schema')!r}, this validator reads {SCHEMA_ID!r}")
    shots = plan["shots"]
    refs = {r["id"]: r for grp in plan["references"].values() for r in grp}
    info = {v["id"]: v for v in plan["visual_information"]}
    sentence_ids = {s["id"] for s in plan["script"]["sentences"]}
    script_toks = tokens(plan["script"]["text"])

    # IDs and order
    ids = [s["id"] for s in shots]
    if len(set(ids)) != len(ids):
        errs.append("duplicate shot ids")
    for i, s in enumerate(shots, 1):
        if s["order"] != i:
            errs.append(f"{s['id']}: order {s['order']} but it is shot #{i}")

    # narration covers the script, in order, with no gaps
    pos = 0
    for s in shots:
        n = s["narration"]
        if n["word_start"] != pos:
            errs.append(f"{s['id']}: narration starts at word {n['word_start']}, expected {pos} (gap or overlap)")
        if " ".join(script_toks[n["word_start"]:n["word_end"]]) != n["text"]:
            errs.append(f"{s['id']}: narration text differs from script words {n['word_start']}-{n['word_end']}")
        for sid in n["sentence_ids"]:
            if sid not in sentence_ids:
                errs.append(f"{s['id']}: unknown sentence {sid}")
        pos = n["word_end"]
    if pos != len(script_toks):
        errs.append(f"narration covers {pos} of {len(script_toks)} script words")

    # every visual-information item is shown in some shot
    for v in plan["visual_information"]:
        if v["sentence_id"] not in sentence_ids:
            errs.append(f"{v['id']}: unknown sentence {v['sentence_id']}")
        if not v["shown_in"]:
            errs.append(f"{v['id']} ({v['fact']!r}) is not shown in any shot")
        for sid in v["shown_in"]:
            if sid not in ids:
                errs.append(f"{v['id']}: shown_in names missing shot {sid}")

    t = 0.0
    for i, s in enumerate(shots):
        sid, g, c = s["id"], s["generation"], s["continuity"]
        for vid in s["visual"]["communicates"]:
            if vid not in info:
                errs.append(f"{sid}: communicates unknown {vid}")
            elif sid not in info[vid]["shown_in"]:
                errs.append(f"{sid}: communicates {vid} but {vid}.shown_in does not list it")
        # references and states
        for r in c["refs"]:
            ref = refs.get(r["id"])
            if not ref:
                errs.append(f"{sid}: unknown reference {r['id']}")
                continue
            for k in ("start_state", "end_state"):
                if r[k] not in ref["states"]:
                    errs.append(f"{sid}: {r['id']} has no state {r[k]!r}")
        if c["environment_ref"] and c["environment_ref"] not in refs:
            errs.append(f"{sid}: unknown environment {c['environment_ref']}")
        # neighbour links
        exp_prev = shots[i - 1]["id"] if i else None
        exp_next = shots[i + 1]["id"] if i + 1 < len(shots) else None
        if c["previous_shot"] != exp_prev or c["next_shot"] != exp_next:
            errs.append(f"{sid}: previous/next shot links are wrong (expected {exp_prev}/{exp_next})")
        if c["transition_in"] == "continuous" and i:
            prev_end = {r["id"]: r["end_state"] for r in shots[i - 1]["continuity"]["refs"]}
            for r in c["refs"]:
                if r["id"] in prev_end and prev_end[r["id"]] != r["start_state"]:
                    errs.append(f"{sid}: continuous from {exp_prev} but {r['id']} starts "
                                f"{r['start_state']!r}, previous ended {prev_end[r['id']]!r}")
        # generation mode needs its keyframes
        roles = [k["role"] for k in g["keyframes"]]
        need = REQUIRED_KEYFRAMES[g["mode"]]
        if roles != need:
            errs.append(f"{sid}: mode {g['mode']} needs keyframes {need}, has {roles}")
        changes = any(r["start_state"] != r["end_state"] for r in c["refs"])
        if changes and g["mode"] not in ("i2v_first_last", "t2v", "stock_footage"):
            errs.append(f"{sid}: a reference changes state but mode is {g['mode']}; use i2v_first_last")
        if g["mode"] in ("i2v_single_keyframe", "i2v_first_last", "t2v") and not g["video"]:
            errs.append(f"{sid}: mode {g['mode']} needs a video block")
        if g["mode"] == "stock_footage" and not g.get("stock_query"):
            errs.append(f"{sid}: stock_footage needs a stock_query")
        # timing
        d = s["timing"]["estimated_duration_s"]
        if abs(s["timing"]["start_s"] - t) > 0.02:
            errs.append(f"{sid}: start_s {s['timing']['start_s']} should be {round(t, 2)}")
        t += d
        if d < HARD_MIN_SHOT_S:
            errs.append(f"{sid}: {d}s is too short to read; merge it with a neighbour" if len(shots) > 1 else
                        f"the whole script is only {d}s of narration; too short to plan")
        elif d < MIN_SHOT_S:
            warns.append(f"{sid}: {d}s is short (< {MIN_SHOT_S}s); check it reads on screen")
        if d > MAX_SHOT_S and g["mode"] not in ("still_kenburns", "stock_footage"):
            errs.append(f"{sid}: {d}s is longer than any common video-model clip ({MAX_SHOT_S}s); split the shot")
        elif d > SOFT_MAX_SHOT_S:
            warns.append(f"{sid}: {d}s holds one picture for a long time (> {SOFT_MAX_SHOT_S}s); consider splitting")
        if g["video"] and g["video"]["duration_s"] < d:
            errs.append(f"{sid}: requested clip {g['video']['duration_s']}s is shorter than narration {d}s")
        # prompt hygiene
        texts = [k["prompt"] for k in g["keyframes"]] + ([g["video"]["prompt"]] if g["video"] else [])
        for w in sorted({w for x in texts for w in fluff_in(x)}):
            warns.append(f"{sid}: prompt uses filler word {w!r}; describe what is in the image instead")
        # QC covers every must_show / must_avoid
        qtext = " ".join(q["description"] for q in s["qc"]["checks"])
        for m in s["must_show"]:
            if m not in qtext:
                errs.append(f"{sid}: must_show {m!r} has no QC check")
        for m in s["must_happen"]:
            if m not in qtext:
                errs.append(f"{sid}: must_happen {m!r} has no QC check")
        if s["must_happen"] and not g["video"]:
            errs.append(f"{sid}: must_happen needs a video, but mode {g['mode']} makes none")
        if not any(q["type"] == "comprehension" for q in s["qc"]["checks"]):
            errs.append(f"{sid}: no comprehension check (can a viewer with the sound off tell what's happening?)")

    mx = plan["format"].get("max_duration_s")
    if mx and t > mx:
        warns.append(f"estimated total {t:.1f}s is over max_duration_s {mx}s")
    for r in refs.values():
        if r["status"] == "NEEDS_REFERENCE":
            warns.append(f"{r['id']}: reference image not made yet; generate and approve it before any keyframe")
    return errs, warns


def validate_plan(plan):
    errs = check_structure(plan, load_schema("shotplan-0.2.schema.json"))
    if errs:
        return errs, []
    return check_semantics(plan)
