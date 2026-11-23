# 1,000 BRICKS — live brief

The current brief for the brick-style series lane. Courtney's instruction
(23 Nov 2026): "Make sure it's in the repo what we're doing." This file is
the truth for this lane; if anything elsewhere disagrees, this file wins
and the disagreement gets flagged in HANDOFF.md.

## The series

**"1,000 BRICKS"** — a fresh brick-style (LEGO-style) animated series,
starting from Episode 1. It is a **separate series** from the pixel series
("The Nether"). The pixel series is **PARKED as of 23 Nov 2026 — do not
continue it, do not build for it, do not revive it** unless Courtney says
otherwise.

Production rules for this lane:

- **True stop-motion from single stills at 12fps** — digital layer-posing,
  the way real brickfilms are made. **No image-to-video AI. Ever.**
- **Stills before animation.** The look is proven and approved in stills
  before a single frame moves.
- **Storyboard agreed by Courtney before any build.** No generation runs
  ahead of his agreement.
- **Nothing public without Courtney's tap.** Drafts and uploads are
  Private by default; only Courtney publishes.

## Story engine

Adapted from @saveo.house's interactive format ("You stole $10M"), rebuilt
for this niche — not copied:

- **ONE continuing story.** Not standalone clips. Stakes and consequences
  persist across episodes.
- **One hero in every shot.**
- **Every episode ends on an A-or-B choice that the audience votes on in
  the comments.** The winning vote becomes canon, and the next episode
  opens with its consequence — and shows the vote split.
- **The brick economy runs both ways.** Choices cost bricks OR give bricks
  back:
  - **Bad pays fast** — loot, deals, cruelty: bricks now, plus hidden
    debts (watchers, enemies, prices that come due later).
  - **Good pays slow** — mercy, sacrifice, sharing: bricks cost today,
    allies and payoffs episodes later.
- The crowd splits into **saviours vs destroyers**, fighting over the hero
  in the comments. Both camps are the engine.

Episode shape (~25s): last vote's consequence → the new room/creature →
the price lands → A-or-B end card (vote in the comments).

## The hero — Courtney himself

The hero is **Courtney as a minifigure**. The audience is not voting on a
character; they are voting on what happens **to him**.

**CORRECTED DESIGN LOCK (Courtney, 23 Nov 2026 — supersedes all earlier
hero text anywhere, including the studio's series bible until it is
updated to match):**

- **Hair: short blonde hair** — short cropped, short at the sides and the
  back. Never long, never wavy.
- **No cape. No armour, no chest plate.** He is not a knight — he is a
  regular dude trapped in this world: **plain dark t-shirt torso print,
  plain dark legs.**
- **Face prints are his real tattoos:** "TAMA" with a small x under
  **his right cheek**; "MHATHAIR" with three small dots under **his left
  cheek** — **never mirrored**; ornate black blackwork swirls printed
  across both sides of his jaw.
- Pale blue-grey eyes; light brown printed stubble beard and moustache;
  a tiny silver septum ring on his nose.
- **One bright teal 1x1 brick set into the centre of his chest** — the
  life counter. It is part of him, not clothing.

The premise: he wakes in the Nether built from exactly **1,000 bricks**,
and the count shows on screen. Every voted choice adds bricks to him or
takes them off him — visibly, piece by piece. **At zero he becomes a
statue** in the corridor, like the fallen heroes already standing there.
**Reach the Door with bricks left and he gets out.** The story has a real
ending either way, and the audience decides which one.

Reference photos of Courtney (front + both profiles) live in the studio
workspace at `studio/output/brick-series/reference/`.

## Consistency gate (Courtney's rules, 23 Nov 2026 — in force from now)

Why this exists, in Courtney's words: he picked up the v2 hair failure
with his own eyes after it was reported as passed. He is not doing QA
anymore. His watch is the publish decision, not QA.

1. **ONE CANONICAL PROMPT.** The hero description lives in exactly one
   place — the design lock in the studio's SERIES-BIBLE.md — and is
   pasted character-for-character into every generation prompt. Never
   reworded, shortened, or adapted per still. A lock change happens in
   the bible first, in Courtney's words, and only then in prompts.
2. **BINARY PER-FEATURE GATE.** A still is judged feature-by-feature
   against the single MASTER image (currently Episode 1 still C v2, for
   hair and figure), one feature at a time: hair length; hair colour;
   tattoo sides (TAMA on his right cheek — frame-left when he faces
   camera; MHATHAIR on his left cheek — frame-right); cape absent;
   armour absent; outfit items; teal chest brick present; proportions.
   ANY single mismatch = FAIL. No holistic "looks consistent", no
   set-level passes, no "family / close enough" grading.
3. **MASTER-ANCHORED.** Every still is compared to the master, never to
   sibling stills from the same batch.
4. **CHECKLIST FROM THE BIBLE.** The gate checklist is Courtney's exact
   phrases from the lock, read off the bible at gate time — not from
   memory or interpretation.
5. **COURTNEY'S WATCH IS THE PUBLISH DECISION, NOT QA.** A still that
   reaches him has already passed every feature, or is labelled FAIL
   with the failing feature named.

## State at push time (23 Nov 2026)

- Series bible + Episode 1 storyboard exist in the studio workspace
  (`studio/output/brick-series/SERIES-BIBLE.md`,
  `studio/output/brick-series/EP1-STORYBOARD.md`). The bible's hero lock
  is being updated to the corrected design above.
- **Episode 1 stills v2** (corrected design, generated from the master
  look + Courtney's photos) are **in production on Muse's side**.
- A **stop-motion technique proof** (the Hellboy door scene, layer-posed
  from the approved brick still) is also **in production on Muse's
  side**. It is a technique test only, not an episode.
- **Episode 1 beat:** he wakes in the corridor among the statues of
  fallen heroes; the 1,000-brick counter appears. First choice — a fallen
  statue has a loose arm plate:
  - **A: take it** (+ bricks — but the statue's eyes open)
  - **B: leave it** (the road costs bricks — and nothing follows him… yet)

## Platform jobs

- **Instagram = premiere home** for this series.
- **YouTube = lore / long-form** (the bank; the funnel points there).
- **TikTok = mirror.**
- **NO browser automation on Courtney's Instagram. Ever.** Official
  connector API only. Standing rule set 23 Nov 2026 after Muse's web
  automation triggered Meta's "Automated account activity" warning and an
  advertising restriction on his account. If the official route cannot do
  something, the answer is "can't be done safely" — unsanctioned routes
  are not a fallback.
