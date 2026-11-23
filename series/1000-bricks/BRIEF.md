# 1,000 BRICKS — live brief

The truth for this lane. Rewritten 23 Nov 2026 on Courtney's direction; the earlier brief (generated hero master,
layered cut-outs, candidate and grading rounds, PRODUCTION-SPEC) is retired and lives only in git history.

## His direction, verbatim (23 Nov 2026)

- "I want the pixel series but Lego style applied to these new episodes"
- "Ignore anything muse has said hair the episodes are important"
- "I want it to be made with code, so change that in the repo with you and Muse. So you're doing the script
  writing and yada yada, but then you're also writing this code and pushing it to Muse."
- "I want the Lego brick style applied to exactly how you made the pixel series."
- "Before anything I want to get the pipeline and video working."

## What it is

The pixel series method with a brick look. One ongoing story, twelve episodes (`ARC.md`), every episode ends on
an A or B choice the comments vote on, and the next episode opens on what the vote cost. The hero wakes built
from 1,000 bricks; the count is on screen; choices add bricks or take them off him. At zero he is a statue.

## How it is made: by code, never generated

- **The maker is `maker/`** (read `maker/README.md`). An episode is a JSON file in `episodes/`. Every frame is
  drawn by code from kit pieces: brick figures, brick-built rooms, 12 frames a second, stepped poses.
- **No AI picture or video generation in this lane.** Not for the hero, not for rooms, not for props. That is
  what failed: a picture model cannot hold one character. Here the hero is one function, so he is the same in
  every frame of every episode, and a loadout piece (stone arm, red leg) is added once and stays on.
- **The hero's look** lives in `maker/kit/figure.js`: dark tee, dark legs, clean printed face with stubble,
  blonde hair on top only, a teal 1x1 brick in his chest. Courtney changes it by saying so; it changes there, once.
- **Brick-style, original.** No LEGO logo, no official sets or characters, never described as an official LEGO product.

## Who does what

| Step | Who |
|---|---|
| Episode script (the `say` lines) and beats, from `ARC.md` | Claude Code |
| Maker code and new kit pieces the episode needs | Claude Code |
| Storyboard sheet (`still.cjs --sheet`) for Courtney's yes | Claude Code draws it, Muse takes it to him |
| Voice: Courtney's cloned voice, then the seconds each beat runs | Muse |
| Render: the `1,000 BRICKS render` workflow, run with those seconds | GitHub Actions (Muse or Claude starts it) |
| Voice + music onto the mp4, gates, Private upload | Muse |
| Publish | Courtney only |

## Episode rules (the pixel series rules, carried over)

- 5 or 6 beats, 85 to 115 words of narration, second person, present tense, Australian spelling, no em dashes.
- Beat 1 is the hook, 12 words or fewer. From Part 2 on it opens on the vote landing and what it cost.
- A stranger can follow it: by the end of beat 2 they know where you are and what you want.
- Say once, plainly, which world the room's rule comes from ("In Hellboy, ..."). The lore fact comes from a
  source that was opened. The world, the hero and everyone he meets are ours: no studio characters on screen.
- The picture shows what the words say, when the voice says it. Whole bodies. Something always moves.
- The last beat is the choice, and each option says what it costs in bricks.
- The count is exact and chains between episodes (`ARC.md` has the numbers for the expected votes).
- Storyboard before render: Courtney's yes on the sheet and the script comes first.
- Voice bans, as everywhere: mate, bastard, bloke, hype.

## State (23 Nov 2026)

- Maker built and drawing. Kit so far: the statue corridor, hero, statue, plinth, arm plate, bricks flying on or off.
- `episodes/ep01.json` is a DRAFT (script and storyboard) waiting on Courtney's yes.
- The lore line in Episode 1 (the stone right hand as the key that ends the world) was checked by web search
  only; the source page still has to be opened before it is voiced.

## Platform jobs

Instagram is the premiere home, YouTube the lore and long-form bank, TikTok the mirror. No browser automation
on Courtney's Instagram, ever: the official connector only.
