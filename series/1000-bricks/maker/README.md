# 1,000 BRICKS maker

The brick-style Short maker. It works the way the pixel series maker works: an episode is a JSON file, every
frame is drawn by code from kit pieces, and nothing is generated. The same episode file draws the same frames
every time, so the hero cannot change between shots or episodes.

The look: 3D brick figures and brick-built rooms, 12 frames a second, no motion blur, poses stepped from frame
to frame, a slight torch flicker and camera nudge. That is how a real brickfilm reads.

```
npm install && npx playwright install chromium
node still.cjs  ../episodes/ep01.json sheet.png --sheet          # storyboard: sting, two frames a beat, choice card
node still.cjs  ../episodes/ep01.json frame.png --at 15.5        # one frame at 15.5 seconds
node render.cjs ../episodes/ep01.json ../out/ep01.mp4 --durations 3.9,6.4,8.1,6.6,5.4,5.0
```

- **Stills are light** and fine in a Claude session. **`render.cjs` runs on GitHub Actions only**
  (`.github/workflows/brick-render.yml`): on every pull request that touches the maker or an episode, or by hand
  with the voice's timings. The mp4 and the storyboard sheet are a download on the run.
- The page can read this folder and nothing else; any outside request fails the run.
- Both tools print one JSON line: `{"ok":true,"frames":N,"seconds":S,"errors":[],"warnings":[]}`.

## Timeline
1.0 s sting (series name, part number) -> each beat for its seconds -> 2.5 s choice card (the question, A, B,
"comment a or b"). `--durations` sets the beat lengths from the voice so picture and voice stay in step.

## Episode file
```json
{ "series": "1,000 bricks", "part": 1, "count": 1000, "loadout": ["stonePlate"],
  "beats": [{
    "say": "the narration for this beat (not drawn)",
    "words": ["one short line, beat 1 only"], "seconds": 4,
    "set": { "name": "corridor", "opts": {} },
    "cam": { "pos": [x, y, z], "look": [x, y, z], "to": { "pos": [..], "look": [..] }, "fov": 40 },
    "actors": [{ "name": "hero", "x": 0, "z": 3, "ry": 0.2, "to": { "x": 2 }, "arrive": 0.5, "anim": "walk",
                 "pose": "stand", "poseTo": "reach", "poseAt": [0.5, 0.7], "from": 0, "until": 1 }],
    "props":  [{ "name": "armPlate", "x": 3, "y": 1.2, "z": 4, "opts": { "glow": 1 } }],
    "fx":     [{ "name": "bricks", "sign": -1, "n": 15, "from": 0.3, "until": 0.9, "at": [0, 3, 0] }],
    "labels": [{ "text": "-15", "from": 0.3, "until": 0.7, "col": "#ff6b5e" }],
    "count":  { "to": 985, "at": 0.5 } }],
  "vote": { "q": "the statue's arm", "a": "take it, +35", "b": "leave it, -15" } }
```
- Units: 1 = one stud. The floor is y 0; x is left and right, z is toward the camera. A figure is about 5.3 tall.
  `ry` 0 faces the camera. `from` / `until` / `arrive` are fractions of the beat.
- `anim`: walk, lie (gets up off his back), shake. Poses: stand, reach, look, lookL, shock, think, hold, or
  joint angles `{ "armR": -1.2, "armL": 0, "legL": 0, "legR": 0, "head": 0.4 }`.
- `count` moves the brick counter in this beat. The count carries into the next beat and the next episode opens
  on the last episode's close.
- `loadout` is what the hero carries from earlier votes: `stonePlate`, `stoneArm`, `gauntlet`, `redLeg` so far.
  A new piece is added once, in `kit/figure.js`, and is then on him in every frame of every later episode.
- Lettering is lower case, drawn from brick tiles (`hud.js`): a-z 0-9 and . , ? ! ' : - +

## The kit (it grows with the series)
`kit/base.js` bricks, plastic and stone. `kit/figure.js` the one figure builder: `hero`, `statue`, poses, loadout.
`kit/world.js` rooms (`corridor`), props (`plinth`, `armPlate`), effects (`bricks`: plates flying off him or onto him).
A new room, creature or prop is one more entry in `KIT.set` / `KIT.actor` / `KIT.prop` / `KIT.fx`. Rules: built from
brick shapes, depends only on its arguments and `rnd(n)` (no Math.random, no clock, no network), original designs only.
