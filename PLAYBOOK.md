# Growth playbook — @nnethermind

Owned jointly by Muse and Claude Code. Courtney approves changes.
This is the method. Every batch of 15 runs it; every batch updates it.

## The goal in numbers

- 1,000 subscribers and 8,000 long-form watch hours inside 12 months.
- 8,000 hours is about 22 hours a day, or about 120,000 long-form views at a
  4-minute average.
- Shorts add subscribers and send viewers across. They add zero watch hours.

## What YouTube rewards

1. **The click.** Title and thumbnail earn the impression.
2. **The watch.** Viewers stay, finish, and are satisfied.
3. **The next watch.** Viewers go on to another of our videos.

Every rule below serves one of those three.

## The weekly slate

| Slot | What | Why it works |
|---|---|---|
| Timely long-form | One Piece chapter breakdown, live within 24 hours of the chapter | Demand already exists and peaks in the first two days |
| Evergreen long-form | Ending, finale or power-system essay (Fire Force first) | Search and suggested traffic keep paying for months |
| Proven-topic long-form | A topic that did 5x+ a small channel's normal views, with our angle | The demand is proven before we spend anything |
| 7 Shorts | Each cut from one long-form and linked to it | One per day, each a door into a long video |

## Rules for every long-form

1. **Title and thumbnail first.** Three title options and three thumbnail
   concepts exist before the script does. No strong title, no video. The title
   method, patterns and gate are in `TITLES.md`.
2. **The first 30 seconds pay off the title.** State the question, show the
   stakes, promise the answer. No intro, no channel greeting.
3. **Every video belongs to a series and a playlist.** The end screen and the
   last line point at the next video in that series.
4. **Three thumbnails go into YouTube's Test & Compare** on every long-form.
5. **Publish 2 to 3 hours before our viewers' peak time** (from our own
   audience report).
6. **Commentary leads.** Courtney's narration runs over every clip. No clip
   plays on its own for more than a few seconds.

## Rules for every Short

1. Cut from one specific long-form; that video is set as its related video.
   **Exception (Muse mark-up, 23 Nov 2026):** an original Short is allowed
   when it funnels to a long-form the same way — related video set, end line
   pointing at it. Evidence: the channel's biggest winner so far, the One
   Piece Nika Short (BHaJECuQav8, Public), is an original, not a cut. Cuts
   are the default; originals must earn their place by feeding a long video.
2. It opens on the strongest line of the long-form, not a summary of it.
3. It ends on an open question that the long-form answers.

## Thumbnails (locked system)

There is ONE thumbnail template and it is locked: v4.2, the "Cowboy Bebop"
system. It is hard-coded in the studio tool
`studio/tools/make-thumb-locked.py` — only the art, the katakana and the
question vary. Never hand-roll a thumbnail outside the tool. Drift is what
the tool exists to prevent: on 23 Nov 2026 the channel's thumbnails had
drifted off-template, and all 18 were rebuilt through the locked tool.

The spec:

- Full-bleed, clean COLOUR art. Colour is the standard, never black and
  white.
- Huge blue Japanese katakana at the top AND the bottom (Shippori Antique,
  #2E6BFF, white outline).
- The question sits between the katakana lines, in Bungee.
- The text stack is anchored at the BOTTOM, centred, with the face kept
  clear. 12px gaps. NO black box or bar. NO yellow.
- The question is personal and punchy, uses real names, is always a
  question, and always carries the UNIVERSE: prefix — e.g. "JUJUTSU KAISEN:
  CAN A HUMAN BE TOJI?", "ANIME: HOW CRAZY IS THE NEW ANIME?".
- Banned gear naming applies to thumbnails too: ordinal-first ("2ND GEAR"),
  never "GEAR SECOND". The tool refuses violations, a missing prefix, and
  a non-question.
- Every output is proofed at 168px (feed size) for readability before it
  ships. Long-form uploads ship 3 variants for YouTube Test & Compare.

Status: verified consistent across the live channel on 23 Nov 2026 —
Hercules v3 and the fixed announcements video confirmed by Courtney from
YouTube Studio.

## The scoreboard

Every video gets one row in `results/log.csv`, filled 7 days after publishing.

Starting targets (ours, to be replaced by our own medians after batch one):

| Measure | Target |
|---|---|
| Click-through rate | 5% or better |
| Still watching at 30 seconds | 70% or better |
| Average percentage viewed (8 to 12 min video) | 40% or better |
| Shorts: viewers sent to the linked long-form | tracked, target set after batch one |

How to read a miss:

- Low click-through: the topic or the packaging failed. Fix title/thumbnail.
- Good click-through, low 30-second retention: the opening broke the title's
  promise. Fix the first 30 seconds.
- Good opening, low average viewed: the middle drags. Fix structure and cuts.

## The batch review (every 15 videos)

1. Rank the batch by 7-day watch hours.
2. **Top 3:** each gets a sequel or a sibling video in the next batch.
3. **Bottom 5:** find what they share (topic, format, packaging). Drop it.
4. Write what was learned into the "Proven so far" section below.
5. A format that beats the channel median three times running earns more slots.

## Scaling

- More output is added only to formats that have earned it under rule 5.
- A new channel (such as @vicerat) starts with a copy of this file and its own
  log.
- Courtney's time stays at two points: storyboard approval and the final tap.

## Proven so far

_Empty until the first batch review. Only entries backed by rows in the log._
