"""
Where beat sheets come from.

  load(path)                   a hand-written or previously saved beat sheet
  from_llm(brief, provider)    an LLM writes one; the compiler checks it and
                               sends any errors back for it to fix (up to max_repairs)
  heuristic(brief)             offline draft with no creative judgement: splits
                               at clause boundaries and marks every shot for review.
                               Use it only to get a plan's structure going.

All three produce the same format (schemas/beatsheet-0.2.schema.json).
"""
import json
import re

from .compiler import PlanError, compile_plan
from .text import sentences, tokens, word_count
from .validate import load_schema

PLANNING_RULES = """You are the shot planner for NETHERMIND, which makes short vertical science videos.
You decide what each shot SHOWS. Code handles timing, prompts and QC afterwards, so
spend your effort on getting the picture right.

THE ONE RULE: every shot shows what the narration is saying at that moment. A viewer
watching with the sound off should still follow the story. Footage that only matches
the general topic ("jellyfish swimming") is a failure.

METHOD
1. Split each sentence into its separate pieces of visual information: the things a
   viewer must SEE to understand it. "When it's injured, starving, or under extreme
   stress, it can transform its adult body back into an earlier stage of its life
   cycle" contains: the adult animal / visible injury or stress / the transformation
   happening / the earlier life stage it becomes. Write each piece as one
   visual_information item tied to its sentence id.
2. Group those pieces into shots. One shot can show one or two closely related
   pieces. A piece that involves a change (A becomes B) gets its own shot with an
   end_state. A shot's narration may start or end mid-sentence.
3. A shot needs about 1.5-4 seconds of narration (about 4-10 words). Merge anything
   shorter with a neighbouring shot; split anything longer. Aim for a new picture
   about every 2 seconds.
4. Use ONLY the references in the brief (refs = CHR_/PROP_ ids with a named state,
   environment_ref = an ENV_ id). If a state changes during the shot, set end_state.
   When one shot picks up exactly where the previous one ended, use
   transition_in "continuous" and start from the state the previous shot ended in.
5. action: what physically happens, in concrete terms of motion and shape.
   Not "it transforms" but "the bell shrinks and folds inward while the tentacles
   shorten and are drawn into the body".
6. must_show: specific visible features that prove the shot is correct. In a shot
   without an end_state, the first frame must already show all of them.
   must_happen: events during the clip (the bite, the detachment); these are
   checked on the video only.
   must_avoid: specific mistakes a model is likely to make (a similar-looking species,
   the wrong size, glow the animal doesn't have, generated text).
7. Scientific accuracy comes before looks. If a shot compresses time or scale, say so
   in accuracy_notes. Names, numbers and labels go in edit_notes as text overlays.
   Never ask the image model to draw text.
8. Write plain physical descriptions. Leave out filler words (cinematic, stunning,
   epic, beautiful, 8k, masterpiece).

Allowed values:
 framing: extreme_close_up close_up medium_close_up medium medium_wide wide extreme_wide macro insert
 angle: eye_level high low top_down bottom_up profile dutch
 movement: static slow_push_in slow_pull_out pan_left pan_right tilt_up tilt_down track_follow orbit rack_focus handheld_drift crane_down crane_up
 transition_in: cut match_cut continuous time_jump location_change
 mode (optional): i2v_single_keyframe i2v_first_last t2v still_kenburns stock_footage
 motion_intensity: low medium high

Return ONLY a JSON object that follows the beat sheet schema you are given."""


def load(path):
    with open(path) as f:
        return json.load(f)


def _brief_for_llm(brief):
    script = " ".join(brief["script"].split())
    toks = tokens(script)
    sents = [{"id": f"N{i:02d}", "text": " ".join(toks[a:b])}
             for i, (a, b) in enumerate(sentences(toks), 1)]
    return {"project": brief["project"], "style": brief["style"], "references": brief["references"],
            "sentences": sents, "notes": brief.get("planner_notes", "")}


def from_llm(brief, provider, max_repairs=2, log=print):
    schema = load_schema("beatsheet-0.2.schema.json")
    prompt = ("BRIEF:\n" + json.dumps(_brief_for_llm(brief), indent=1) +
              "\n\nBEAT SHEET SCHEMA:\n" + json.dumps(schema) +
              "\n\nWrite the beat sheet. The shots' narration must join to make the sentences exactly, in order.")
    history = prompt
    for attempt in range(max_repairs + 1):
        raw = provider.generate_json(PLANNING_RULES, history)
        try:
            beats = json.loads(re.sub(r"^```(json)?|```$", "", raw.strip()))
            compile_plan(brief, beats, backend=provider.label)
            return beats
        except (json.JSONDecodeError, PlanError) as e:
            errs = e.errors if isinstance(e, PlanError) else [f"not valid JSON: {e}"]
            log(f"  attempt {attempt + 1}: {len(errs)} problem(s); " + ("asking for a fix" if attempt < max_repairs else "giving up"))
            history = (prompt + "\n\nYOUR PREVIOUS BEAT SHEET:\n" + raw +
                       "\n\nIT HAS THESE PROBLEMS. Return a corrected, complete beat sheet:\n- " + "\n- ".join(errs))
    raise PlanError(errs)


def heuristic(brief, target_words=(4, 11)):
    """Offline draft: splits into clauses, then merges or splits them to 4-11 words per shot."""
    lo, hi = target_words
    script = " ".join(brief["script"].split())
    toks = tokens(script)
    chars = brief["references"].get("characters", [])
    envs = brief["references"].get("environments", [])
    ref = [{"id": chars[0]["id"], "start_state": next(iter(chars[0]["states"]))}] if chars else []
    info, shots = [], []
    for si, (a, b) in enumerate(sentences(toks), 1):
        # clause chunks inside the sentence
        chunks, cur = [], []
        for t in toks[a:b]:
            cur.append(t)
            if re.search(r"[,;:—–]$", t) or t in ("—", "–"):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        merged = []
        for c in chunks:
            if merged and (word_count(merged[-1]) < lo or word_count(c) < lo) and word_count(merged[-1]) + word_count(c) <= hi:
                merged[-1] = merged[-1] + c
            else:
                merged.append(c)
        for c in merged:
            vid = f"V{len(info) + 1:02d}"
            text = " ".join(c)
            info.append({"id": vid, "sentence_id": f"N{si:02d}", "fact": f"REVIEW: what must be seen for {text!r}"})
            shots.append({
                "narration": text, "communicates": [vid],
                "goal": f"REVIEW: show literally what is said in {text!r}",
                "refs": ref, "environment_ref": envs[0]["id"] if envs else None,
                **({} if envs else {"environment": "REVIEW: environment"}),
                "action": "REVIEW: describe the physical action that matches the narration",
                "framing": "medium", "angle": "eye_level", "movement": "slow_push_in",
                "composition": "subject centred in the upper two-thirds",
                "must_show": [f"REVIEW: visible evidence of {text!r}"],
            })
    return {"visual_information": info, "shots": shots}
