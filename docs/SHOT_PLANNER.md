# Shot Planner v0.2

Turns a narration script into a machine-readable production plan: one entry per
shot, each saying what the viewer must **see**, how to generate it, what must stay
consistent with the other shots, and how to check the result.

```
SCRIPT → [SHOT PLANNER] → REFERENCES → KEYFRAMES → IMAGE-TO-VIDEO → VIDEO QC → EDIT → AUDIO → OUTPUT
```

**The rule it enforces:** every shot shows what the narration is saying at that
moment. A viewer with the sound off should still follow the story. Footage that
only matches the general topic doesn't count.

## Quick start

```bash
python3 plan_shots.py plan briefs/immortal_jellyfish.json --beats beats/immortal_jellyfish.beats.json
python3 plan_shots.py show plans/immortal_jellyfish.shotplan.json        # summary
python3 plan_shots.py show plans/immortal_jellyfish.shotplan.json S05    # one shot in full
python3 plan_shots.py validate plans/immortal_jellyfish.shotplan.json    # after hand edits
python3 -m unittest discover -s tests -v
```

For a new video:

1. Write `briefs/<id>.json`: the fact-checked script, the style, and the
   references (cast and locations). Copy the jellyfish brief as a starting point.
2. Get a beat sheet, in one of three ways:
   - `--llm gemini`: an LLM writes it. The compiler checks the result and sends any
     errors back for the LLM to fix (up to 2 rounds). Needs `GEMINI_API_KEY`;
     set `GEMINI_TEXT_MODEL` to choose the model.
   - `--beats beats/<id>.beats.json`: write it yourself, or edit what the LLM saved.
   - `--heuristic`: an offline draft that only splits at clause boundaries. Every
     shot comes out `NEEDS_REVIEW` with `REVIEW:` placeholders. It gives you the
     structure; it doesn't make any creative decisions.
3. Read the warnings, edit the beat sheet, re-run with `--beats`. Each run raises
   `plan_version`.

The planner needs only the Python standard library. `jsonschema`, if installed,
is used for the structure check; otherwise a built-in checker handles it.

## Why two stages

| Stage | Where | Decides |
|---|---|---|
| **Beats** (creative) | `shotplanner/beats.py`, LLM or person | What separate things each sentence asks the viewer to see, how they group into shots, subject state, action, framing, must-show / must-happen / must-avoid |
| **Compile** (deterministic) | `shotplanner/compiler.py` | Matching narration to the script, timing, generation mode, prompts, negative prompts, continuity links, QC checks, status |

The LLM only makes the creative decisions. Everything that has to be exactly
right structurally comes from code, so the same beat sheet always gives the
same plan. That means you can compare two versions of a plan line by line, and
a bad LLM answer fails loudly instead of slipping through.

## Visual beats, not sentences

Each sentence is split into **visual_information** items: the separate things
a viewer must see to understand it. The shots then cover those items. Every
item must appear in at least one shot, or the plan is rejected.

Your example sentence, *"When it's injured, starving, or under extreme stress, it
can transform its adult body back into an earlier stage of its life cycle"*,
becomes:

| Item | Must be seen | Shot |
|---|---|---|
| V04 | the adult body | S04 |
| V05 | visible injury / stress (torn bell, lost tentacles, weak pulsing) | S04 |
| V06 | the transformation happening (bell folding in, tentacles shortening) | S05, first + last frame |
| V07 | the earlier stage it's heading back to (the polyp colony) | S06 |

The next sentence (*"It sinks, absorbs its own tentacles, and collapses into a
tiny blob"*) then shows the physical steps in S07–S08, using a continuous run of
states (`reverting → settled → cyst`).

Shot narration can start or end mid-sentence. The shots' narration joins to
make the script exactly, word for word (case, curly quotes and edge punctuation
are ignored when matching).

## Files

```
plan_shots.py                     CLI
shotplanner/compiler.py           beats + brief → plan
shotplanner/prompts.py            keyframe / video / negative prompt assembly, filler-word list
shotplanner/validate.py           structure + cross-field rules
shotplanner/beats.py              beat sources: file, LLM (with repair loop), heuristic; planning rules for the LLM
shotplanner/llm.py                provider interface (Gemini wired in)
shotplanner/text.py, timing.py    tokens/sentences/alignment; duration estimates
schemas/brief-0.2.schema.json     input
schemas/beatsheet-0.2.schema.json creative layer
schemas/shotplan-0.2.schema.json  output (every field documented in "description")
briefs/ beats/ plans/             worked example: immortal_jellyfish
tests/test_shotplanner.py         19 tests, offline
```

## Plan structure (summary; the schema is the full reference)

```jsonc
{
  "schema": "nethermind.shotplan/0.2",
  "project": {"id", "title", "fact_sources"},
  "plan_version": 2, "created_at": "...",
  "planner": {"version", "backend", "script_sha256", "words_per_second"},
  "format": {"aspect_ratio": "9:16", "width": 1080, "height": 1920, "fps": 30, "target_duration_s", "max_duration_s"},
  "style": {"visual_style", "lighting", "color_palette", "lens_language", "global_must_avoid", "global_negative"},
  "references": {"characters": [...], "environments": [...]},   // named states, locked_attributes, must_avoid, status
  "script": {"text", "sentences": [{"id": "N03", "text", "word_start", "word_end"}]},
  "visual_information": [{"id": "V05", "sentence_id": "N03", "fact", "shown_in": ["S04"]}],
  "shots": [{
    "id": "S05", "order": 5,
    "narration": {"text", "sentence_ids", "word_start", "word_end"},
    "timing": {"words", "estimated_duration_s", "start_s", "generate_duration_s"},
    "visual": {"goal", "communicates", "subject", "subject_state", "action", "environment",
               "camera": {"framing", "angle", "lens", "movement", "movement_note"}, "lighting", "composition"},
    "continuity": {"refs": [{"id", "start_state", "end_state"}], "environment_ref",
                   "previous_shot", "previous_shot_state", "next_shot", "next_shot_state",
                   "transition_in", "locked_attributes"},
    "generation": {"mode", "mode_reason",
                   "keyframes": [{"role": "start|end", "prompt", "prompt_parts", "reference_ids", "image"}],
                   "video": {"prompt", "duration_s", "motion_intensity", "output"},
                   "negative_prompt", "reference_requirements", "stock_query"},
    "must_show": [], "must_happen": [], "must_avoid": [],
    "qc": {"checks": [{"id", "type", "stage", "description", "severity", "method"}], "pass_required", "max_attempts"},
    "accuracy_notes": [], "edit_notes": [],
    "status": "PLANNED"
  }],
  "totals": {"shots", "estimated_duration_s", "by_mode"},
  "warnings": []
}
```

Changes from the draft schema in the brief:

- **visual_information + communicates.** Makes the "visual beats" rule
  checkable: every item must be shown in some shot.
- **Named reference states.** `adult_healthy`, `adult_injured`, `reverting`, `cyst`...
  Each is described once in the brief and referred to by name in every shot.
  Shots can't drift into describing the same state differently.
- **start_state / end_state per reference.** If they differ, the shot is a
  change of state and automatically gets first + last keyframes.
- **must_happen**, separate from **must_show**. Events (the bite, the
  detachment) can only be checked on video. A still keyframe is never asked to
  show them.
- **prompt_parts** stored next to each assembled prompt, so a provider adapter
  can rebuild the prompt for its own model.
- **QC checks as yes/no questions**, each with a type, stage, severity and method
  (`vlm` / `auto` / `human`), ready for an automated VLM judge.
- **generate_duration_s**: the estimate plus 0.5 s for trimming, rounded up to a
  clip length models usually offer (3/4/5/6/8/10 s).
- **accuracy_notes / edit_notes.** Time compression is written down, not hidden.
  Names and numbers go in as edit overlays, never generated text.

## Generation modes

| Mode | When | Keyframes | Video prompt |
|---|---|---|---|
| `i2v_single_keyframe` | default: no change of state | start | motion only |
| `i2v_first_last` | automatic when any reference changes state | start + end | motion only; ends on the last frame |
| `t2v` | only if set explicitly | — | the full description plus motion |
| `still_kenburns` | fits the existing `make_short.py` "kb" path | start | — |
| `stock_footage` | real public-domain footage fits better (needs `stock_query`) | — | — |

## Prompt method

The method below comes from the published image-to-video guides for Runway
and Kling.

- **Keyframe prompt** = SUBJECT → PHYSICAL STATE → MOMENT → ENVIRONMENT → CAMERA →
  LIGHTING → COMPOSITION → CONTINUITY → STYLE → MUST SHOW, each part one plain
  sentence built from the brief and beat. The subject and state text is
  copied word for word from the reference, so every shot describes the animal the same way.
- For **first + last** shots, each keyframe shows only its own frozen state. The
  action and must_show describe the change, so they go to the video prompt and QC.
- **Video prompt** = camera move + action + (for changes) "gradual, continuous, ends
  on the last keyframe" + locked attributes + "one take, no cuts, no morphing".
  It never describes the keyframe again: the image already sets the look.
- **Negative prompt** = technical negatives + style `global_must_avoid` + each
  reference's `must_avoid` (e.g. moon jellyfish, bioluminescent glow) + the shot's
  own. Written as a plain list without "no". Providers that don't take negatives
  should have their adapter fold these into the main prompt.
- **Filler-word check**: `cinematic`, `stunning`, `epic`, `8k`, `masterpiece`… raise a
  warning. Describe what's in the image instead.

## Continuity

- Each reference has a fixed `description`, named `states` and
  `locked_attributes` (e.g. "the bright red-orange digestive core"). Locked
  attributes go into keyframe prompts, video prompts and continuity QC.
- Each shot stores `previous_shot_state` / `next_shot_state`, so a generator
  (or a person) can see what the neighbouring frames must match.
- `transition_in: "continuous"` is enforced: the shot must start in the state
  the previous shot ended in, otherwise the plan is rejected.
- `reference_requirements` lists the approved reference images a shot needs
  before any keyframe is made. References start as `NEEDS_REFERENCE`.

## QC

Every shot gets generated checks. YES means pass.

- `comprehension`: "With the sound off, would a viewer understand: <goal>". A blocker in every shot.
- `presence` / `absence`: one per must_show / must_avoid.
- `action`: one per must_happen, plus the main action.
- `state_change`, `continuity`, `scale`, and `technical` (aspect ratio and length
  checked in code; no generated text; no flicker or changing anatomy).

`pass_required: true` + `max_attempts: 3`. After three failed generations the shot goes to `NEEDS_REVIEW`.

## Status lifecycle

```
PLANNED → REFS_READY → KEYFRAME_GENERATED → KEYFRAME_APPROVED → VIDEO_GENERATED → QC_PASSED → APPROVED
                              ↑____________________ QC_FAILED ←__________________|
NEEDS_REVIEW (heuristic draft, or max_attempts reached) → PLANNED after a human edit
REJECTED (shot dropped/replaced in a new plan_version)
```

## Timing

`seconds = words / words_per_second + 0.18 s per clause break + 0.35 s per sentence end`.
The default of 2.6 words/s has **not** been measured against Kokoro am_liam. After the
first real render, set `"words_per_second"` in the brief to the measured value
(words ÷ seconds from `tts/<id>/*.json`). `make_short.py` always uses real TTS timing;
these estimates only size the clips to request and plan the edit.

## Adding an LLM provider

Write a class with `label` and `generate_json(system, prompt) -> str`, then register
it in `shotplanner/llm.PROVIDERS`. The repair loop, schema check and compiler work the
same for every provider.

## Known limits (v0.2)

- The Gemini provider is written but hasn't been run against the live API
  here: no key in this environment. The repair loop is tested with a fake
  provider.
- The heuristic backend only drafts structure; it makes no creative decisions.
- The planner doesn't generate anything yet. The next components read
  `generation.*` and fill in `keyframes[].image`, `video.output` and `status`.
