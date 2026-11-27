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
bricks or take them off. At zero he is a statue. **The counts live in `LEDGER.md`** (reworked 24 Nov for bigger swings
and real risk: he can turn to stone early from Part 6). The counts in `ARC.md` are retired; its story beats stand.

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

## Prompt rules, so credits are not spent twice (his rule, 26 Nov)

"I need you to make sure you're prompts don't allow for those changes, as it's wasting credits I can't afford." Part 2
spent 30 extra credits because the stone arm was described in words (three different arms came back) and a clip was
left free to invent a walk (the statue grew a second arm and nearly merged with him).

1. **Anything seen in more than one shot is a saved Element before the first still.** The hero, the hero wearing a
   new piece of kit, a statue in a changed state, the room. One reference picture, his approval, then save it. Never
   describe a recurring thing in words.
2. **A change to a saved thing is a new Element**, made once. The statue without its arm is not "the statue Element
   minus the arm" in a prompt: the model puts the arm back.
3. **A fix is an edit of the still**, with "keep everything identical" and the one change named. Never a regeneration.
4. **A still is checked against the last part's stills, side by side, before he sees it**: same arm, same legs, same
   room. A miss is named, not passed.
5. **A clip prompt allows one thing to move and says where it stops.** Nothing walks toward the camera or toward
   another figure. Name what must not change (arm count, the stone arm's size, the face, the lettering) and what must
   not move. If a shot needs two things moving, it is two shots.
6. **A clip is checked frame by frame at one frame a second before he sees it**, and a miss is named with the frame.
7. **Words the Higgsfield filter blocks** (no charge, but a wasted turn): stump, gone, bare, waist up, shock.

## Two versions of every part, one part ahead (his rule, 24 Nov)

"We need to have a/b episodes for each as depends on what's chosen" and "Let's just work one episode ahead at a time."
Every part is written in two versions: one that opens on A winning the last vote, one on B. The rest is shared. Only
the next part is written ahead. The opening count is filled in from the real votes (`LEDGER.md`) before voicing, and
nothing is generated until the vote is in.

## Part 1 (24 Nov)

Built with his voice and approved: "Yes good we will test and learn from this". Music is being added, then Muse uploads
it Private.

## Music (his pick, 24 Nov)

"I think some quieter hardcore metal like speed the band. Australian hardcore band". An original instrumental in that
style, never the band's own recording and never ElevenLabs. Muse makes it; `assemble.py` lays `<episode>/music.mp3`
quietly under the voice.

## Episode 2

Script and shot list: `episodes/ep02/SCRIPT.md`, approved by him in full on 24 Nov. On 26 Nov he called the Part 1
vote as A ("let's just say that the comments picked an"), so Version A is made: opens at 104, the statue takes 12, 92.
Next: the price quoted, his yes, the set picture, then the stills.

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
