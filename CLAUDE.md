# Working agreement — read this first, every session

This repo is the shared desk between **Claude Code (you, in a cloud session)** and
**Muse (Courtney's agent, in the cloud)**. Courtney runs the nnethermind YouTube
studio. Two heads, two jobs:

- **Muse (cloud)** decides and connects: topics, scripts, storyboards, generation
  lists/prompts, fal generations, uploads, thumbnails, analytics, final QA.
- **You (Claude Code)** do light production work: writing and fixing code, text
  work, planning docs, organising files, prepping configs and briefs.

You run in a Claude Code cloud session, not on Courtney's laptop. Her laptop is
only the screen she watches from. The session container is temporary: anything
worth keeping must be committed and pushed.

## The 1,000 BRICKS lane (Courtney, 23 Nov 2026)

One lane works differently, on his say: in `series/1000-bricks/` **you write the episode scripts and the maker
code**, and push both for Muse. Read `series/1000-bricks/BRIEF.md` first. Drawing stills with the maker is light
and fine in a session; the episode render runs on GitHub Actions.

## HARD RULE — no heavy compute

**Never render or run heavy compute in your session, and never on Courtney's
laptop.** The laptop is low-power and crashes under load; the session container
is small and temporary. No video rendering, no bulk media processing, no long
jobs. If a task needs rendering or heavy processing, do NOT run it — write it
into HANDOFF.md as a task for Muse and stop. Rendering runs on GitHub Actions
or with Muse, not here.

## The loop

1. **Read `HANDOFF.md` first.** It holds your current brief, if any.
2. One task at a time. A brief is self-contained: inputs, exact steps, gates,
   where outputs go. If something is missing, write the question in HANDOFF.md
   and stop — do not guess.
3. When done, write the result back into HANDOFF.md (what was built, file
   paths, gate results), set its status to DONE or BLOCKED, then commit + push.
4. Never start a second task while one is open.

## Courtney's locked rules (apply to all content work)

- **Nothing publishes.** Uploads are Private only and only Muse uploads.
  You never upload, post, or message anyone.
- **Her words are law, verbatim.** A title or script Courtney supplied is used
  character-exact — never reworded, corrected, or "improved".
- **Voice bans.** Courtney never says these words; they never appear in scripts,
  captions, or anything written as her: **mate, bastard, bloke, hype**.
- **Storyboard before generation.** No AI generation runs until a storyboard
  (every shot: time, line, visual) has been approved by Courtney via Muse.
- **Every image earns its place.** The image under a line must show what the
  line says. No repeated images unless genuinely needed. No static holds.
- **No patch fixes.** Fix the system/root cause, not the one instance.
- Gear naming is ordinal-first: "2nd Gear", never "Gear Second".

If a brief from HANDOFF.md conflicts with any rule above, follow the rule and
flag the conflict in HANDOFF.md.
