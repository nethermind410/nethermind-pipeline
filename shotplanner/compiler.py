"""
Beat sheet + brief -> shot plan. Deterministic; no model calls.

    plan = compile_plan(brief, beats, backend="manual:beats/x.json")

Raises PlanError(errors) if the beat sheet can't become a valid plan: the
narration doesn't match the script, a reference or state is unknown, a
visual-information item isn't shown in any shot, and so on. The error
messages are written so an LLM can read them and fix its own beat sheet
(beats.py sends them back to it).
"""
import datetime
import hashlib
import re

from . import SCHEMA_ID, VERSION
from . import prompts as P
from .text import align_spans, sentences, tokens, word_count
from .timing import DEFAULT_LPS, estimate, generate_length
from .validate import check_structure, load_schema, validate_plan

FRAMINGS = {"extreme_close_up", "close_up", "medium_close_up", "medium", "medium_wide", "wide",
            "extreme_wide", "macro", "insert"}
ANGLES = {"eye_level", "high", "low", "top_down", "bottom_up", "profile", "dutch"}
MOVES = {"static", "slow_push_in", "slow_pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down",
         "track_follow", "orbit", "rack_focus", "handheld_drift", "crane_down", "crane_up"}
TRANSITIONS = {"cut", "match_cut", "continuous", "time_jump", "location_change", "open"}
MODES = {"i2v_single_keyframe", "i2v_first_last", "t2v", "still_kenburns", "stock_footage"}
INTENSITY = {"low", "medium", "high"}
DEFAULT_FORMAT = {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 30,
                  "target_duration_s": 35, "max_duration_s": 60}
TECH_NEGATIVE = ["text", "captions", "subtitles", "watermark", "logo", "signature", "frame border",
                 "split screen", "collage", "blurry subject", "motion smearing", "duplicated subject"]


class PlanError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


# What LLMs and people actually write -> the allowed value. Anything not listed
# here and not already valid is still reported as an error.
ALIASES = {
    "framing": {"ecu": "extreme_close_up", "extreme_closeup": "extreme_close_up", "cu": "close_up",
                "closeup": "close_up", "mcu": "medium_close_up", "medium_closeup": "medium_close_up",
                "ms": "medium", "mid": "medium", "full": "medium_wide", "mws": "medium_wide",
                "ws": "wide", "long": "wide", "establishing": "wide", "ews": "extreme_wide",
                "els": "extreme_wide", "extreme_long": "extreme_wide", "detail": "insert"},
    "angle": {"overhead": "top_down", "birds_eye": "top_down", "bird_eye": "top_down", "aerial": "top_down",
              "worms_eye": "bottom_up", "worm_eye": "bottom_up", "side": "profile", "side_view": "profile",
              "straight_on": "eye_level", "eye": "eye_level", "canted": "dutch", "tilted": "dutch",
              "high_down": "high", "looking_down": "high", "looking_up": "low"},
    "movement": {"push_in": "slow_push_in", "dolly_in": "slow_push_in", "zoom_in": "slow_push_in",
                 "slow_zoom_in": "slow_push_in", "slow_dolly_in": "slow_push_in", "creep_in": "slow_push_in",
                 "pull_out": "slow_pull_out", "pull_back": "slow_pull_out", "dolly_out": "slow_pull_out",
                 "zoom_out": "slow_pull_out", "slow_zoom_out": "slow_pull_out", "slow_pull_back": "slow_pull_out",
                 "tracking": "track_follow", "track": "track_follow", "follow": "track_follow",
                 "locked_off": "static", "locked": "static", "still": "static", "fixed": "static",
                 "none": "static", "arc": "orbit", "orbit_left": "orbit", "orbit_right": "orbit",
                 "focus_pull": "rack_focus", "pull_focus": "rack_focus", "rack": "rack_focus",
                 "handheld": "handheld_drift", "drift": "handheld_drift", "boom_down": "crane_down",
                 "pedestal_down": "crane_down", "boom_up": "crane_up", "pedestal_up": "crane_up"},
    "transition_in": {"hard_cut": "cut", "straight_cut": "cut", "match": "match_cut",
                      "continuation": "continuous", "continues": "continuous", "time_skip": "time_jump",
                      "time_cut": "time_jump", "new_location": "location_change", "location": "location_change"},
    "motion_intensity": {"subtle": "low", "gentle": "low", "minimal": "low", "slow": "low",
                         "moderate": "medium", "fast": "high", "intense": "high", "dynamic": "high"},
    "mode": {"i2v": "i2v_single_keyframe", "image_to_video": "i2v_single_keyframe",
             "first_last": "i2v_first_last", "first_last_frame": "i2v_first_last",
             "text_to_video": "t2v", "ken_burns": "still_kenburns", "kenburns": "still_kenburns",
             "stock": "stock_footage"},
}


def _norm(v, key=None):
    """Lowercase, spaces/hyphens/apostrophes -> underscores, drop a trailing
    '_shot'/'_angle', then map known aliases. 'Close-Up shot' -> 'close_up'."""
    v = re.sub(r"[\s\-]+", "_", str(v).strip().lower().replace("'", "").replace("\u2019", ""))
    table = ALIASES.get(key, {})
    for cand in (v, re.sub(r"_(shot|angle|camera|cam|move|movement)$", "", v)):
        if cand in table:
            return table[cand]
    return re.sub(r"_(shot|angle)$", "", v) if v.endswith(("_shot", "_angle")) else v


def _qc(sid):
    n = [0]

    def add(type_, stage, desc, severity="blocker", method="vlm"):
        n[0] += 1
        return {"id": f"{sid}.Q{n[0]:02d}", "type": type_, "stage": stage, "description": desc,
                "severity": severity, "method": method}
    return add


def _state_line(ref, state):
    return f"{ref['id']} {state!r}: {ref['states'][state]}"


def compile_plan(brief, beats, backend="manual", plan_version=1, now=None):
    errs = check_structure(beats, load_schema("beatsheet-0.2.schema.json"))
    if errs:
        raise PlanError(["beat sheet: " + e for e in errs])

    fmt = {**DEFAULT_FORMAT, **brief.get("format", {})}
    style = dict(brief["style"])
    style.setdefault("global_must_avoid", [])
    style["global_negative"] = list(dict.fromkeys(TECH_NEGATIVE + style.get("global_negative", [])))
    refs_in = brief["references"]
    refs_by_id = {r["id"]: r for grp in ("characters", "environments") for r in refs_in.get(grp, [])}
    lps = brief.get("letters_per_second", DEFAULT_LPS)

    script = " ".join(brief["script"].split())
    toks = tokens(script)
    sent_ranges = sentences(toks)
    sents = [{"id": f"N{i:02d}", "text": " ".join(toks[a:b]), "word_start": a, "word_end": b}
             for i, (a, b) in enumerate(sent_ranges, 1)]

    src = beats["shots"]
    ranges, errs = align_spans(toks, [b["narration"] for b in src])
    info_ids = {v["id"] for v in beats["visual_information"]}
    sent_ids = {s["id"] for s in sents}
    for v in beats["visual_information"]:
        if v["sentence_id"] not in sent_ids:
            errs.append(f"{v['id']}: unknown sentence {v['sentence_id']} (script has N01-N{len(sents):02d})")

    # normalise + check each beat before building anything
    norm = []
    for n, b in enumerate(src, 1):
        b = dict(b)
        tag = f"shot {n}"
        for key, allowed in (("framing", FRAMINGS), ("angle", ANGLES), ("movement", MOVES)):
            b[key] = _norm(b[key], key)
            if b[key] not in allowed:
                errs.append(f"{tag}: {key} {b[key]!r} not one of {sorted(allowed)}")
        for key, allowed, default in (("transition_in", TRANSITIONS, None), ("mode", MODES, None),
                                      ("motion_intensity", INTENSITY, "low")):
            if b.get(key):
                b[key] = _norm(b[key], key)
                if b[key] not in allowed:
                    errs.append(f"{tag}: {key} {b[key]!r} not one of {sorted(allowed)}")
            elif default:
                b[key] = default
        refs = []
        for r in b["refs"]:
            ref = refs_by_id.get(r["id"])
            if not ref or ref["id"].startswith("ENV_"):
                errs.append(f"{tag}: refs entry {r['id']!r} is not a CHR_/PROP_ reference in the brief "
                            f"(have {sorted(k for k in refs_by_id if not k.startswith('ENV_'))})")
                continue
            r = {"id": r["id"], "start_state": r["start_state"], "end_state": r.get("end_state") or r["start_state"]}
            for k in ("start_state", "end_state"):
                if r[k] not in ref["states"]:
                    errs.append(f"{tag}: {r['id']} has no state {r[k]!r} (has {sorted(ref['states'])})")
            refs.append(r)
        b["refs"] = refs
        env = b.get("environment_ref")
        if env and (env not in refs_by_id or not env.startswith("ENV_")):
            errs.append(f"{tag}: environment_ref {env!r} is not an ENV_ reference in the brief")
        if not env and not b.get("environment"):
            errs.append(f"{tag}: needs environment_ref or environment")
        for vid in b["communicates"]:
            if vid not in info_ids:
                errs.append(f"{tag}: communicates unknown {vid}")
        if b.get("mode") == "stock_footage" and not b.get("stock_query"):
            errs.append(f"{tag}: stock_footage needs stock_query")
        norm.append(b)
    shown = {v for b in norm for v in b["communicates"]}
    for v in beats["visual_information"]:
        if v["id"] not in shown:
            errs.append(f"{v['id']} ({v['fact']!r}) is not shown in any shot")
    if errs:
        raise PlanError(errs)

    ids = [f"S{i:02d}" for i in range(1, len(norm) + 1)]
    warnings, shots, t = [], [], 0.0
    if backend == "heuristic":
        warnings.append("beats came from the offline heuristic: every shot is a draft marked NEEDS_REVIEW")

    for i, (b, (ws, we)) in enumerate(zip(norm, ranges)):
        sid = ids[i]
        span = toks[ws:we]
        est = estimate(span, lps)
        changes = any(r["start_state"] != r["end_state"] for r in b["refs"])
        mode = b.get("mode") or ("i2v_first_last" if changes else "i2v_single_keyframe")
        reason = ("set in the beat sheet" if b.get("mode") else
                  "a subject changes state during the shot, so both the first and last frames are fixed"
                  if changes else "no change of state; one keyframe fixes the look and the video model adds the motion")
        env_ref = refs_by_id.get(b.get("environment_ref") or "")
        chars = [refs_by_id[r["id"]] for r in b["refs"]]
        locked = [a for c in chars for a in c.get("locked_attributes", [])]
        subject = b.get("subject") or (" + ".join(c["name"] for c in chars) if chars else "environment")
        subj_state = "; ".join(
            f"{refs_by_id[r['id']]['name']}: {r['start_state']}"
            + (f" -> {r['end_state']}" if r["end_state"] != r["start_state"] else "") for r in b["refs"]) or "n/a"
        environment = " ".join(x for x in ((env_ref or {}).get("description", ""), b.get("environment", "")) if x)

        keyframes = []
        roles = {"i2v_single_keyframe": ["start"], "still_kenburns": ["start"],
                 "i2v_first_last": ["start", "end"]}.get(mode, [])
        for role in roles:
            parts = P.keyframe_parts(b, refs_by_id, style, fmt, role, first_last=len(roles) == 2)
            keyframes.append({"role": role, "prompt": P.join_parts(parts), "prompt_parts": parts,
                              "reference_ids": [r["id"] for r in b["refs"]] + ([env_ref["id"]] if env_ref else []),
                              "image": None})
        video = None
        if mode in ("i2v_single_keyframe", "i2v_first_last", "t2v"):
            vp = P.video_prompt(b, locked)
            if mode == "t2v":  # no keyframe to carry the look, so the video prompt must describe it
                vp = P.join_parts(P.keyframe_parts(b, refs_by_id, style, fmt, "start")) + " " + vp
            video = {"prompt": vp, "duration_s": generate_length(est),
                     "motion_intensity": b["motion_intensity"], "output": None}
        negative = P.negative_prompt(style["global_negative"], style["global_must_avoid"],
                                     [x for c in chars for x in c.get("must_avoid", [])],
                                     (env_ref or {}).get("must_avoid", []), b.get("must_avoid", []))

        # QC — every check is a yes/no question where YES = pass
        q = _qc(sid)
        checks = [q("comprehension", "video" if video else "keyframe",
                    f"With the sound off, would a viewer understand this: {b['goal']}")]
        # with first+last frames, must_show describes the change, so it can only be judged on the video
        show_stage = "video" if mode == "i2v_first_last" else "both"
        checks += [q("presence", show_stage, f"Is this clearly visible: {m}?") for m in b["must_show"]]
        checks += [q("action", "video", f"Does this happen on screen: {m}?") for m in b.get("must_happen", [])]
        checks += [q("absence", "both", f"Is this absent: {m}?", "blocker")
                   for m in b.get("must_avoid", [])]
        if video:
            checks.append(q("action", "video", f"Does this action actually happen on screen: {b['action']}"))
        for r in b["refs"]:
            ref = refs_by_id[r["id"]]
            checks.append(q("continuity", "both",
                            f"Does the {ref['name']} match its approved reference and, where visible in frame, keep: "
                            + ("; ".join(ref.get("locked_attributes", [])) or ref["description"]) + "?"))
            if r["start_state"] != r["end_state"]:
                checks.append(q("state_change", "video",
                                f"Does the {ref['name']} begin {r['start_state']!r} ({ref['states'][r['start_state']]}) "
                                f"and end {r['end_state']!r} ({ref['states'][r['end_state']]})?"))
            if ref.get("scale") and len(b["refs"]) > 1:  # needs a second subject in frame to compare against
                checks.append(q("scale", "both", f"Compared with the other subjects in frame, is the {ref['name']} shown at a believable size ({ref['scale']})?",
                                "major"))
        if env_ref:
            checks.append(q("continuity", "both", f"Does the setting match {env_ref['id']}: {env_ref['description']}?",
                            "major"))
        checks.append(q("technical", "both", f"Is the frame {fmt['aspect_ratio']} vertical at "
                        f"{fmt['width']}x{fmt['height']} or larger?", "blocker", "auto"))
        checks.append(q("technical", "both", "Is the frame free of generated text, watermarks and logos?"))
        if video:
            checks.append(q("technical", "video", f"Is the clip at least {est}s long?", "blocker", "auto"))
            checks.append(q("technical", "video",
                            "Is the subject free of flicker, melting or anatomy that changes between frames?"))

        sent_of = [s["id"] for s in sents if s["word_start"] < we and s["word_end"] > ws]
        shot = {
            "id": sid, "order": i + 1,
            "narration": {"text": " ".join(span), "sentence_ids": sent_of, "word_start": ws, "word_end": we},
            "timing": {"words": word_count(span), "estimated_duration_s": est, "start_s": round(t, 2),
                       "generate_duration_s": generate_length(est)},
            "visual": {"goal": b["goal"], "communicates": b["communicates"], "subject": subject,
                       "subject_state": subj_state, "action": b["action"], "environment": environment,
                       "camera": {k: v for k, v in (("framing", b["framing"]), ("angle", b["angle"]),
                                                    ("lens", b.get("lens")), ("movement", b["movement"]),
                                                    ("movement_note", b.get("movement_note"))) if v},
                       "lighting": b.get("lighting") or (env_ref or {}).get("lighting") or style["lighting"],
                       "composition": b["composition"]},
            "continuity": {"refs": b["refs"], "environment_ref": env_ref["id"] if env_ref else None,
                           "previous_shot": None, "previous_shot_state": None,
                           "next_shot": None, "next_shot_state": None,
                           "transition_in": b.get("transition_in") or ("open" if i == 0 else "cut"),
                           "locked_attributes": locked},
            "generation": {"mode": mode, "mode_reason": reason, "keyframes": keyframes, "video": video,
                           "negative_prompt": negative,
                           "reference_requirements": [f"{r['id']} ({r['start_state']}"
                                                      + (f" and {r['end_state']}" if r["end_state"] != r["start_state"] else "")
                                                      + ") reference image approved" for r in b["refs"]]
                           + ([f"{env_ref['id']} reference image approved"] if env_ref else [])},
            "must_show": b["must_show"], "must_happen": b.get("must_happen", []),
            "must_avoid": b.get("must_avoid", []),
            "qc": {"checks": checks, "pass_required": True, "max_attempts": 3},
            "status": "NEEDS_REVIEW" if backend == "heuristic" else "PLANNED",
        }
        if b.get("stock_query"):
            shot["generation"]["stock_query"] = b["stock_query"]
        for k in ("accuracy_notes", "edit_notes"):
            if b.get(k):
                shot[k] = b[k]
        shots.append(shot)
        t += est

    # continuity links: each shot knows how its neighbours end/start
    def ends(s):
        return "; ".join(_state_line(refs_by_id[r["id"]], r["end_state"]) for r in s["continuity"]["refs"]) \
            or f"environment only ({s['continuity']['environment_ref']})"

    def starts(s):
        return "; ".join(_state_line(refs_by_id[r["id"]], r["start_state"]) for r in s["continuity"]["refs"]) \
            or f"environment only ({s['continuity']['environment_ref']})"

    for i, s in enumerate(shots):
        c = s["continuity"]
        if i:
            c["previous_shot"], c["previous_shot_state"] = shots[i - 1]["id"], ends(shots[i - 1])
        if i + 1 < len(shots):
            c["next_shot"], c["next_shot_state"] = shots[i + 1]["id"], starts(shots[i + 1])

    by_mode = {}
    for s in shots:
        by_mode[s["generation"]["mode"]] = by_mode.get(s["generation"]["mode"], 0) + 1
    refs_out = {grp: [{"reference_images": [], "status": "NEEDS_REFERENCE", **r} for r in refs_in.get(grp, [])]
                for grp in ("characters", "environments")}
    plan = {
        "schema": SCHEMA_ID,
        "project": {k: v for k, v in brief["project"].items() if k in ("id", "title", "fact_sources")},
        "plan_version": plan_version,
        "created_at": (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "planner": {"version": VERSION, "backend": backend,
                    "script_sha256": hashlib.sha256(script.encode()).hexdigest(), "letters_per_second": lps},
        "format": fmt, "style": style, "references": refs_out,
        "script": {"text": script, "sentences": sents},
        "visual_information": [{**v, "shown_in": [ids[i] for i, b in enumerate(norm) if v["id"] in b["communicates"]]}
                               for v in beats["visual_information"]],
        "shots": shots,
        "totals": {"shots": len(shots), "estimated_duration_s": round(t, 2), "by_mode": by_mode},
        "warnings": [],
    }
    errs, warns = validate_plan(plan)
    if errs:
        raise PlanError(errs)
    plan["warnings"] = warnings + warns
    return plan
