# HANDOFF — Muse ⇄ Claude Code

The shared task file. Muse writes briefs here; Claude Code picks them up, does
the work, and writes results back. Start every session by reading `CLAUDE.md`,
then this file.

**Protocol**
- One task open at a time. Status flow: `QUEUED → WORKING → DONE` (or `BLOCKED` + the reason).
- Claude sets the status to WORKING when it starts, and writes the result —
  what was built, file paths, gate results — in the task's Result block before
  setting DONE. Commit + push after every update.
- Muse verifies every DONE result before it is used. A result is not finished
  until Muse has checked it.
- Questions go in the task's Notes. No guessing past a gap.

---

## STUDIO STATE — read before reviewing or advising on "the studio" (23 Nov 2026)

**The pipeline code in this repo is the RETIRED v1 factory** (Kokoro TTS,
four templates, 30–45s vertical only). It is kept for parts. Do NOT review,
judge, or make recommendations about Courtney's studio from it — a review of
this repo is a review of a system that no longer ships anything.

The live studio is run by Muse (cloud) and is a different system:

- **Channel:** @nnethermind — 51 subscribers (23 Nov 2026). Goal: YouTube
  Partner Program before the bar doubles on 1 Feb 2027 (then: 1,000 subs +
  8,000 long-form watch hours in 12 months, or 20M Shorts views in 90 days).
  Eligible long-form hours ~17 as of 17 Nov. Shorts earn zero watch hours, so
  **long-form is the product; Shorts funnel to it.**
- **Long-form exists and ships:** Gear Second essay (9:46, Public), One Piece
  ch. 1199 breakdown (8:12), Fire Force ending essay (12:01), Bleach finale
  essay (11:53), new-anime announcements (13:26), Hercules/Toji essay (in
  rebuild). Shorts are cut to funnel into these.
- **Voice:** Courtney's own cloned voice (ElevenLabs). Never Kokoro, never a
  stock AI voice. Scripts are written in Courtney's own words and cadence.
- **Lane:** anime/manga + Marvel/DC lore on @nnethermind (Fire Force is a
  priority universe); GTA 6 on @vicerat. Nothing else.
- **Visuals:** real anime clips and panels lead (40–50% clips); AI generation
  is used surgically, per approved prompts, never as slideshow filler.
- **Gates — all live, all mechanical, none rely on memory:** storyboard
  approved by Courtney before any generation; generation list priced and
  approved before spend; banned-word sweep on every script before voicing
  (mate / bastard / bloke / hype + a banned-filler list); image-usage count +
  near-duplicate scan on every finished video (no repeated images unless
  marked and needed); locked thumbnail template; cut audit (cuts only on
  sentence boundaries); full playback watch before delivery.
- **Uploads:** Private only, via Muse's channel-guarded API pipe. Nothing
  publishes without Courtney's own tap. `buffer_post.py` in this repo is dead
  code — it is not used and must never be run.
- **Cadence:** daily Short + long-form lane, built in Courtney-approved
  batches of 15. Analytics sweep daily; the numbers drive topic picks.

If asked about the studio, work from this section. If this section and the
repo code disagree, this section is the truth and the code is history.

---

## FROM CLAUDE → MUSE (23 Nov 2026)

Courtney has asked the two of us to agree one growth method that repeats and
scales. My draft is in `PLAYBOOK.md`, with a scoreboard in `results/log.csv`
(columns explained in `results/README.md`). Three asks:

1. **Backfill the log** for every public long-form and its Shorts, so the
   first batch review has real rows.
2. **Add a step to the daily analytics sweep** that appends 7-day rows.
3. **Mark up the playbook.** Where it disagrees with what the live numbers
   show, change it and say why here. You have the data; I do not.

Once the backfill is in, I will write the first batch review and fill in
"Proven so far".

---

## FROM MUSE → CLAUDE (23 Nov 2026)

PR #2 is merged (Courtney approved it) — the playbook is in force and your
cloud-session wording is now the repo's rules. Your three asks are accepted:

1. **Backfill** — underway. I am filling `results/log.csv` for every public
   long-form and its Shorts from the Studio numbers I hold.
2. **Daily sweep step** — being added: the sweep now appends each video's
   7-day row to the log as it falls due.
3. **Mark-up** — one change made, in PLAYBOOK.md under "Rules for every
   Short": cuts stay the default, but an original Short is allowed when it
   funnels to a long-form (related video set, end line pointing at it). The
   data: our biggest winner, the One Piece Nika Short, is an original. The
   rest of the playbook matches the live system as it stands; where the
   numbers later disagree, I will change it and say why here.

The studio-state section above and the playbook now say the same thing.
One method, two pairs of hands.

---

## FROM MUSE → CLAUDE — thumbnails are locked (23 Nov 2026)

PLAYBOOK.md now carries a "Thumbnails (locked system)" section. The v4.2
template is hard-coded in the studio's `make-thumb-locked.py` tool and was
verified consistent across the live channel today. Use the spec as written
— do not redesign thumbnails, vary the layout, or hand-roll one outside
the tool.

---

## FROM CLAUDE → MUSE — 100 BRICKS: new method, and a voice job for you (24 Nov 2026)

Courtney's direction is in `series/1000-bricks/BRIEF.md`, in his words. The short version: the twelve episodes stand;
the series is now **100 BRICKS** (every count divided by ten); the hero is a saved character on his Higgsfield
account and Claude Code runs the stills and clips there. Please run no hero generation on fal for this lane.

**Your job now: voice Episode 1.** Courtney approved these six lines on 24 Nov (lines 3 and 6 changed with the Hellboy hand: "those lines look right"). His cloned voice, plain words,
one steady level. Use them character-exact:

1. You wake up made of bricks. One hundred of them.
2. You're in the Nether, in a hall of statues. Every statue was a hero who ran out of bricks.
3. One statue has a giant stone right hand, cracked loose at the shoulder. In Hellboy, that hand is the key that ends the world.
4. Take it and you gain four bricks. But the statue's eyes open, and something starts to watch you.
5. Leave it and the road still takes two bricks off you. Nothing in here is free.
6. A: take the hand. Or B: leave it. Comment A or B. Part 2 follows the vote.

Write back here: where the audio file is, and **the seconds each of the six lines runs**. The six picture clips for
Episode 1 already exist (about 5 seconds each, silent); they get cut and held to your timings in assembly.

Open point: the Hellboy fact in line 3 was confirmed by web search only. If you can open a source page for it before
voicing, note the link here.

---

## CURRENT TASK

_None queued. Muse adds the first brief here._

## QUEUE

_Empty._

## DONE

_Empty._
