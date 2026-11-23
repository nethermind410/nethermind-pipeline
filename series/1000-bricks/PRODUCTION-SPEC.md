# 1,000 BRICKS — PRODUCTION SPEC (LOCKED)

**Spec version: v4 — 23 Nov 2026.**

**Change note (v4, 23 Nov 2026):** the hair shape changes — the slicked-back hair now sits on TOP of the head only and the sides of the head are shaven bare, in the canonical hero prompt (A1) and grading list (B3), per Courtney — his words: "Just have it shaven in the sides and only hair on top — this character doesn't have ears, no need to have the hairs going around ears that don't exist." A1 re-synced character-exact to the current SERIES-BIBLE.md hero lock; B3 feature 1 is now "hair SLICKED BACK ON TOP ONLY, short + straight, sides shaven bare", judged on the hair crop.

**Change note (v3, 23 Nov 2026):** the hair spec changes from a buzz-short crop to short slicked-back hair in the canonical hero prompt (A1) and grading list (B3), per Courtney — his words: "short blonde slicked back hair", "I don't want an Afro". A1 re-synced character-exact to the current SERIES-BIBLE.md hero lock; B3 feature 1 is now "hair SLICKED BACK, short + straight", judged on the hair crop.

**Change note (v2, 23 Nov 2026):** the septum ring is scrapped and the hair is tightened to a buzz-short straight crop in the canonical hero prompt (A1) and grading list (B3), per Courtney — A1 re-synced character-exact to the current SERIES-BIBLE.md hero lock.

Courtney's instruction (23 Nov 2026): fixed parameters so the work does the same job every time. Every generation run and every grading run for this series runs under this spec. **No per-run improvisation:** no reworded prompts, no substituted references, no relaxed grading, no exceptions invented mid-run. If a run cannot be done under these parameters, it stops and the blocker is reported — it is not worked around.

This spec lives in two places, and the two copies must stay identical: the studio workspace (`studio/output/brick-series/PRODUCTION-SPEC.md`) and the repo (`series/1000-bricks/PRODUCTION-SPEC.md`).

---

## A. GENERATION PARAMETERS

### A1. The canonical hero prompt — character-exact, never varies

Every generation prompt contains the hero block below, copied **character-for-character** from the hero design lock in SERIES-BIBLE.md. It is never reworded, shortened, extended, or adapted per shot, per episode, or per run:

> a single LEGO-style minifigure of Courtney: fair light-flesh minifigure head with a clean printed face — pale blue-grey eyes, light brown printed stubble beard and moustache, no septum ring, no nose jewellery or marking of any kind, no tattoos or markings on the face at all — short bleached-blonde hair slicked back on TOP of the head only — strands swept straight back flat, smooth moulded top piece, low hairline close above the brows; the sides of the head are shaven bare — no hair on the sides at all (a minifigure head has no ears; nothing wraps around the sides), back short — a plain dark t-shirt torso print, plain dark legs, one bright teal 1x1 brick set into the centre of his chest, no cape, no armour, no chest plate, no hat, no weapons. He is a regular dude trapped in the Nether, not a knight.

### A2. Fixed reference inputs — the same two, every call

Every generation call passes exactly these two reference inputs, and no others:

1. **Courtney's front photo** — `brick-series/reference/courtney-front.jpg` (identity reference).
2. **The accepted master still** — `brick-series/stills/ep1-still-c-statue-arm-v6-master.webp` (the master named in the bible's consistency gate; hair, figure and face anchor).

No other reference image may be added, swapped, or dropped per run. A change to the reference inputs is a spec change (see D).

### A3. Output format — fixed

- Vertical **9:16** stills, delivered at **1080×1920**.
- Photoreal brick style: visible studs, seams and brick texture on every surface; dark purple and black cavern brickwork, warm torchlight, shallow depth of field, cinematic — per the bible's visual lock.
- Stills only. Animation is true stop-motion from graded stills at 12 fps; **no image-to-video AI, ever.**

### A4. The scene-template rule

A generation prompt is assembled from exactly two parts, in this order:

1. **The scene description for this shot** — the only part that varies: the room, the pose, the camera, the story beat, taken from the episode's approved storyboard.
2. **The hero block (A1)** — pasted verbatim, in full, every time.

The hero block NEVER varies. If a shot does not contain the hero, it contains no hero block and no hero reference inputs — and it is still graded for world consistency against the master set.

### A5. Candidates — the generator stops at candidates

- **Up to 3 candidates per shot.** The generator produces candidates and stops.
- The generator does **not** select a winner, does **not** grade, does **not** pass or fail anything, and does **not** describe any candidate as consistent, correct, or approved.
- Candidates go to the grading pass (B) exactly as generated — unedited, uncomposited, unretouched.

---

## B. GRADING PARAMETERS

### B1. A separate grader — never the generator

Grading is done by a **different agent** from the one that generated the candidates. The generator never grades its own output (bible consistency gate, rule 7). This separation is structural, not a courtesy: the same run that made an image does not get to judge it.

### B2. What the grader receives — ONLY these four things

1. Courtney's front photo — `brick-series/reference/courtney-front.jpg`.
2. The accepted master still — `brick-series/stills/ep1-still-c-statue-arm-v6-master.webp`.
3. The candidate still(s) for the shot.
4. The feature list (B3), copied verbatim from the bible's consistency gate.

The grader **never sees the generation prompt**, the scene description, the generator's notes, or any claim about what the image was meant to be. It grades what the image **is**, against the photo and the master.

### B3. The feature list — verbatim from the bible gate

Each candidate is judged on exactly these features, in this wording:

- hair SLICKED BACK ON TOP ONLY, short + straight, sides shaven bare (strands swept straight back flat, smooth moulded top piece; no hair on the sides at all — nothing wraps around the sides; no afro, no curls, no waves standing up, no volume, no fringe) — judged on the hair crop
- hair colour
- hairline low (sitting close above the brows, not high or receded)
- septum ring ABSENT (no ring, no nose jewellery, no marking of any kind on the nose — the piercing is scrapped, its presence = FAIL)
- face tattoos absent (no tattoos, text or markings anywhere on the face)
- jaw tattoos absent
- cape absent
- armour absent
- outfit items
- teal chest brick present
- proportions

### B4. How grading is done — region crops, binary, no averaging

- Grading is judged on **zoomed region crops**: a **hair crop**, a **nose crop**, and a **chest crop**, each compared against the same region of the front photo and the master. **Full-frame** is used for outfit items, proportions, cape absent and armour absent.
- **Binary per feature:** every feature is PASS or FAIL. There is no partial credit, no weighting, no "close enough", no holistic "looks consistent", and no set-level pass — each candidate is graded alone, against the master, never against sibling candidates.
- **ANY single FAIL = the image is rejected outright.** A rejected image is not shipped, not composited over, not patched, and not shown to Courtney as anything other than a named failure.
- If all 3 candidates for a shot fail, the shot goes back for a new generation run under these same parameters — the parameters do not loosen because a shot is hard.

### B5. The verdict format

The grader reports a **per-feature table** for each candidate: every feature from B3 listed, each marked PASS or FAIL, and **the failing feature named in words** for any rejection. A verdict with no table is not a verdict. Only a candidate that passes every feature may be called passed, and only passed stills reach Courtney — his watch is the publish decision, not QA.

---

## C. UNRENDERABLE-FEATURE RULE

A feature that **fails across all 3 candidates in 2 separate generation runs** is declared unrenderable by generation. It leaves generation permanently:

- It is then either **composited from one locked graphic asset at one fixed anchor**, or **removed from the design entirely**.
- **Courtney decides which**, and the decision is recorded **in the bible first** — the lock text changes there, in his words, before any prompt, asset, or practice changes.
- Until that bible change exists, the feature stays in the lock and keeps failing honestly; it is never quietly dropped, faked, or graded around.

**Precedent:** the face tattoos — generation and compositing could not lock them in properly every time, so on Courtney's instruction (23 Nov 2026) they were **removed from the design**. The bible records the removal; the old face-print overlay asset is retired and unused.

---

## D. CHANGE CONTROL

- These parameters change **only** by editing this spec, and **only** on Courtney's instruction, recorded in the bible first. No run, agent, or deadline changes a parameter on its own authority.
- Every change increments the spec version and is dated at the top of this file. Superseded versions are not silently overwritten in substance: the change and Courtney's words behind it are noted in the bible.
- **Every build report names the spec version and date it ran under** (e.g. "Ran under PRODUCTION-SPEC v1 — 23 Nov 2026"). A build report that does not name its spec version is incomplete.
- If this spec and the bible disagree, the run **stops** and the disagreement is flagged. Nobody resolves it by improvising.
