# 100 BRICKS — live brief

The truth for this lane, rewritten 24 Nov 2026 on Courtney's direction. The earlier briefs (the generated hero master
with candidate rounds, then a code-drawn maker) are retired and live only in git history. The series was called
"1,000 BRICKS"; the folder keeps that name.

## His direction, verbatim

- "Ignore anything muse has said hair the episodes are important" (23 Nov)
- On the reference pictures he supplied: "This is what the character should look like okay" (23 Nov)
- On the three test shots made from his saved character: "Okay!!! Great. Now can we work with that??" (23 Nov)
- "thousands of bricks is way too much compared to the character??" then "100 bricks is good" (24 Nov)
- "i dont want it to be a stale video that is just wasting credits. can we iron out all before generating" (24 Nov)
- "muse will do voice yes" (24 Nov)

## What it is

One ongoing story in twelve episodes (`ARC.md`). Every episode ends on an A or B choice the comments vote on, and the
next opens on what the vote cost. The hero wakes built from **100 bricks**; the count is on screen; choices add a few
bricks or take a few off. At zero he is a statue. **Every count in `ARC.md` is divided by ten**: 100, 104, 100, 102,
99, 94, 87, 80, 75, 84, 70, 64, then 3 or 0.

## How it is made

1. **Two saved characters on Courtney's Higgsfield account** (Elements). Every still is generated from them; never
   describe either from scratch.
   - `nether-hero` (id `ab3e1734-649d-4c93-81f3-4eed6940362c`): the hero, LOCKED 24 Nov. Swept-back blonde hair, soft
     light stubble, two cheek tattoos (a small x and TAMA under one eye; three dots and MHATHAIR under the other), black
     tee with bare arms, teal chest brick with NETHER on its stud.
   - `stone-hand-statue` (id `3f4cc39a-be32-434d-b09c-b26a69d91625`): the statue with the giant stone right hand (the
     Hellboy hand), cracked at the shoulder. Courtney's pick ("a"); he wants it only slightly taller than the hero.
2. **Shot list first.** Each line and the picture under it, approved by Courtney before any credit is spent.
3. **Stills**: a start picture for every shot, and an end picture made as an edit of the start so room and camera
   match. No LEGO lettering anywhere, no stray pieces on the floor.
4. **Movement, by shot** (his picks, 24 Nov):
   - A shot where he turns, reaches or steps: Higgsfield's `grok_video_v15_lite`, 5 seconds from the start picture,
     5 credits ("heaps better"). Strip its sound.
   - A shot where nothing rotates (eyes open, a glow, dust, a crack): the free open-source RIFE tool between the start
     and end pictures, 0 credits.
   - Not used: Kling (10 credits, blurred the tattoos), RIFE on turns ("twisting and weird"), and snapping between
     stills with a camera wobble ("shaky").
5. **Episode 1 teases both choices; the next episode opens on the one the comments pick**, shown in full.
6. **Voice**: Muse, in his cloned voice. **Assembly in code**: clips cut to the voice, the brick counter, the plus and
   minus numbers, the A or B card, music. Private upload by Muse. Courtney publishes.

**Credits (his rule, 24 Nov):** quote the price before any generation and wait for his yes; one attempt, then stop and
ask; aim for about 40 credits an episode (12 stills, three moving shots). He will spend more if the series picks up.

Every still is checked against the saved hero before he sees it. A miss is named, not passed.

## On-screen look (his picks, 24 Nov)

- Font: Pixelify Sans 700 (`fonts/`). Colours: torch gold and amber with white text. No teal, no red.
- The brick count is a game health bar across the top: twenty segments that empty as bricks are lost, the number beside it.
- The vote card is see-through, so the picture stays visible behind it.

## Carry into Episode 2 (his notes on Episode 1)

- **Lock the room.** In Episode 1 the wall sits behind the hero and statue in the side-on shots but the open corridor
  is behind them when they face the camera, so the room seems to move. Before any shot: save one picture of the set as
  an Element (statue, wall and corridor in fixed places) and film every shot from the same side of it.
- Keep the statue only slightly taller than the hero.

## Music (his pick, 24 Nov)

"I think some quieter hardcore metal like speed the band. Australian hardcore band". An original instrumental in that
style, never the band's own recording and never ElevenLabs. Muse makes it; `assemble.py` lays `<episode>/music.mp3`
quietly under the voice.

## Episode 2

Script and shot list, two versions (one for each way the Part 1 vote can go): `episodes/ep02/SCRIPT.md`. Draft, waiting
on his approval. Nothing is generated until he approves it and the vote is in.

## Episode rules

- 5 or 6 shots, 85 to 115 words, second person, present tense, Australian spelling, no em dashes.
- Shot 1 is the hook, 12 words or fewer. From Part 2 it opens on the vote landing and what it cost.
- Say once, plainly, which world the room's rule comes from. The lore fact comes from a source that was opened.
- The picture shows what the words say. Something always moves. No two shots that look the same.
- The last shot is the choice, and each option says what it costs in bricks.
- Voice bans: mate, bastard, bloke, hype.

## Platform jobs

Instagram is the premiere home, YouTube the lore and long-form bank, TikTok the mirror. No browser automation on
Courtney's Instagram, ever: the official connector only.
