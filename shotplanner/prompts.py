"""
Prompt assembly. Deterministic: the same shot always gives the same prompt.

Keyframe (image) prompt, in this fixed order:
    SUBJECT, PHYSICAL STATE, ACTION MOMENT, ENVIRONMENT, CAMERA, LIGHTING,
    COMPOSITION, CONTINUITY, VISUAL STYLE, MUST SHOW
Each part is also stored separately in prompt_parts, so a provider adapter
can reorder or reword the prompt for its own model.

Video (image-to-video) prompt: motion only. The keyframe already sets the
subject, lighting and style, so the video prompt gives just the camera move,
what the subject does, and how its state changes (the method in Runway's and
Kling's image-to-video guides). It does not describe the keyframe again.

Negative prompt: a plain list of things to leave out, without the word "no".
"""
import re

# Words that make an image look impressive but say nothing about what should be in it.
# They get flagged in any prompt part.
FLUFF = ("cinematic", "stunning", "beautiful", "epic", "masterpiece", "breathtaking",
         "award-winning", "award winning", "8k", "4k", "ultra-detailed", "hyperrealistic",
         "hyper-realistic", "trending on artstation", "gorgeous", "amazing", "dramatic")

HUMAN = {
    "extreme_close_up": "extreme close-up", "close_up": "close-up", "medium_close_up": "medium close-up",
    "medium_wide": "medium-wide", "extreme_wide": "extreme wide", "eye_level": "eye-level",
    "top_down": "top-down", "bottom_up": "bottom-up, looking up", "slow_push_in": "slow push-in toward the subject",
    "slow_pull_out": "slow pull-out away from the subject", "pan_left": "slow pan left",
    "pan_right": "slow pan right", "tilt_up": "slow tilt up", "tilt_down": "slow tilt down",
    "track_follow": "tracking to follow the subject", "orbit": "slow orbit around the subject",
    "rack_focus": "rack focus", "handheld_drift": "subtle handheld drift", "crane_down": "crane down",
    "crane_up": "crane up", "static": "locked-off static camera",
}


def human(s):
    return HUMAN.get(s, s.replace("_", " "))


def _sentence(s):
    s = s.strip()
    return s if not s or s[-1] in ".!?" else s + "."


def fluff_in(text):
    low = text.lower()
    return [w for w in FLUFF if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", low)]


def keyframe_parts(shot_src, refs_by_id, style, fmt, role, first_last=False):
    """role: 'start' or 'end'. Uses each ref's start_state or end_state.

    first_last: the shot has both a start and an end keyframe. Each image then
    shows only its own frozen state. The action and the must_show items describe
    the change between them, so they go in the video prompt and QC instead;
    putting them here would ask the start image to show the end.
    """
    chars = [r for r in shot_src["refs"] if refs_by_id[r["id"]]["id"].startswith(("CHR_", "PROP_"))]
    env = refs_by_id.get(shot_src.get("environment_ref") or "")
    state_key = "start_state" if role == "start" else "end_state"

    subject = " ".join(
        _sentence(f"{refs_by_id[r['id']]['name']}: {refs_by_id[r['id']]['description']}")
        + (" " + _sentence(f"Real size: {refs_by_id[r['id']]['scale']}") if refs_by_id[r['id']].get("scale") else "")
        for r in chars)
    state = " ".join(
        _sentence(f"{refs_by_id[r['id']]['name']} state: {refs_by_id[r['id']]['states'][r[state_key]]}")
        for r in chars)
    if first_last:
        action = ("Frozen moment at the start of the shot, before any change begins." if role == "start"
                  else "Frozen moment at the end of the shot, after the change is complete.")
    else:
        action = _sentence(f"Frame shows the first moment of this action: {shot_src['action']}")
    environment = _sentence("Environment: " + " ".join(
        x for x in ((env or {}).get("description", ""), shot_src.get("environment", "")) if x))
    lens = f", {shot_src['lens']}" if shot_src.get("lens") else ""
    camera = _sentence(f"Camera: {human(shot_src['framing'])}, {human(shot_src['angle'])} angle{lens}")
    # most specific wins: the shot, then its environment, then the film-wide style
    lighting = _sentence("Lighting: " + (shot_src.get("lighting") or (env or {}).get("lighting") or style["lighting"]))
    composition = _sentence(f"Composition: vertical {fmt['aspect_ratio']} frame; {shot_src['composition']}; "
                            "keep the lower third free of key detail for captions")
    locked = [a for r in shot_src["refs"] for a in refs_by_id[r["id"]].get("locked_attributes", [])]
    continuity = _sentence("Continuity: must match the approved reference images"
                           + (" and keep " + "; ".join(locked) if locked else ""))
    palette = (env or {}).get("color_palette") or style["color_palette"]
    vis_style = _sentence(f"Style: {(env or {}).get('visual_style') or style['visual_style']}; palette: {palette}"
                          + (f"; {style['lens_language']}" if style.get("lens_language") else ""))
    must = "" if first_last else _sentence("Clearly visible: " + "; ".join(shot_src["must_show"]))
    parts = {"subject": subject, "state": state, "action": action, "environment": environment,
             "camera": camera, "lighting": lighting, "composition": composition,
             "continuity": continuity, "style": vis_style, "must_show": must}
    return {k: v for k, v in parts.items() if v and v != "."}


def join_parts(parts):
    return " ".join(parts.values())


def video_prompt(shot_src, locked):
    move = human(shot_src["movement"])
    note = f" ({shot_src['movement_note']})" if shot_src.get("movement_note") else ""
    out = [_sentence(f"Camera: {move}{note}"), _sentence(shot_src["action"])]
    if any(r["start_state"] != r["end_state"] for r in shot_src["refs"]):
        out.append("The change is gradual and continuous from the first keyframe to the last keyframe, "
                   "with no jump, and the shot ends exactly on the last keyframe.")
    intensity = shot_src.get("motion_intensity", "low")
    out.append({"low": "Motion is slow, smooth and physically plausible.",
                "medium": "Motion is steady and physically plausible.",
                "high": "Motion is fast but physically plausible."}[intensity])
    if locked:
        out.append(_sentence("Keep unchanged throughout: " + "; ".join(locked)))
    out.append("One continuous take, no cuts, no morphing of anatomy between frames.")
    return " ".join(out)


def negative_prompt(*lists):
    seen, out = set(), []
    for lst in lists:
        for item in lst:
            item = re.sub(r"^(no|avoid|without)\s+", "", item.strip(), flags=re.I).rstrip(".")
            if item and item.lower() not in seen:
                seen.add(item.lower())
                out.append(item)
    return ", ".join(out)
