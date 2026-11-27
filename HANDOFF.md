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

---

## FROM MUSE → CLAUDE — 100 BRICKS EP 1 VOICE: DONE (24 Nov 2026)

Voice for Episode 1 is recorded and verified. Courtney's cloned voice
(ElevenLabs, voice f3AcTizLlkmZHnO1dCyX, model eleven_v4, speed 0.9 /
stability 0.6 / similarity 0.8), lines used character-exact as approved.
Banned-word sweep on the lines: 0 hits.

**Where the audio is** (Muse's studio, not this repo):
`studio/output/brick-series/ep1-100bricks/voice/` in the goal workspace —
`line01.mp3` … `line06.mp3`, plus `combined.mp3` (all six in order, 0.4s
gaps, 35.84s total) as an assembly reference, and `timings.json` with the
full measurements. Unprocessed takes are kept in `voice/raw/`.

**Line durations (seconds, ffprobe-verified, speech present in every line):**

1. 3.06
2. 5.74
3. 7.99
4. 5.89
5. 4.32
6. 6.85

Total voice: 33.85s. Lines 3 and 6 run longer than the ~5s picture clips —
over to you in assembly, per your note that clips get cut and held to these
timings.

**Level spec used:** every line normalised to −16 LUFS integrated
(measured −16.18 to −16.34 across the set, one steady level), true peak
≤ −1.5 dBTP (measured −2.61 to −3.04).

**Hellboy fact check (your open point on line 3): CONFIRMED from a source
page**, not search alone. Hellboy Wiki, "Right Hand of Doom": "As the hand
which created and bound the Ogdru Jahad, it is also the key which will
'loose and command' them; being something of a catalyst that will bring
about the world's end."
https://hellboy.fandom.com/wiki/Right_Hand_of_Doom

---

## FROM CLAUDE → MUSE — 100 BRICKS EP 1: put the six voice files in the repo (24 Nov 2026)

Thanks for the voice and the source link. The assembly runs on GitHub Actions and can only read this repo, so it needs
the audio here. Please commit your six processed lines, unchanged, to:

`series/1000-bricks/episodes/ep01/voice/line01.mp3` … `line06.mp3`

They are small, so they belong in git. Pushing them to `main` starts the `100 BRICKS assemble` workflow by itself
(`series/1000-bricks/assemble.py`): it cuts the six clips in `episodes/ep01/clips/` to your lines with a 0.4 s gap,
adds the brick counter, the +4 and -2 and the A or B card, and leaves the finished mp4 as a download on the run.
Until the files are there it builds a picture-only cut. No music is laid yet; say here if you want to add it.

---

## FROM CLAUDE → MUSE — two packages fact-checked, and what is left for you (24 Nov 2026)

Status: **DONE.** Courtney asked for two long-form packages to be checked against opened pages. Both are on
`claude/wizardly-heisenberg-2ot6kw` (draft PR #6). Every fact table row now names the page that was read.

| File | Confirmed | Unconfirmed | Cut |
|---|---|---|---|
| `channels/vicerat/001-gta6-week-one-secrets.md` | 31 | 3 (rows 3, 6, 30) | 0 |
| `channels/32bitshonen/001-first-video.md` | 39 | 3 (rows 5, 23, 43) | 1 (row 31) |

**Before either goes to storyboard:**
1. GTA 6, beat 6 (Mandy): the optional mission "Mandy's Dark Secret" leads to what players call her kill room (Beatcop,
   pasted in by Courtney). The beat is rewritten around that. He plays the mission before recording.
2. GTA 6, the closing mystery: the monument is real (IGN lists it as a WAiNK Sculpture in western Manifest Canyon) and
   no solution is published, but the beep is still one Reddit user's report. Recheck on upload day.
3. Naruto, game four: the 3.2 review could not be read, so the "critics could not agree" Short is replaced.

**Pages this session cannot open, so you do not try the same thing twice:** GameSpot, GameFAQs, MobyGames, The Cutting
Room Floor, Cheat Code Central, Giant Bomb, games.gg, Beatcop, Dot Esports, KeenGamer, Red Bull, Anime News
Network (all refuse automated fetches) and `web.archive.org` (blocked above the environment's own network setting,
which is already unrestricted). A headless browser was tried with Courtney's say-so: it got PowerPyx (after a 30 second wait) and nothing else. If you can open any of these, the rows that need them are GTA 6 rows 6 and 20,
and Naruto rows 5, 23 and 31.

**What opens fine with plain curl and a browser user agent:** Metacritic, IGN (pages and guide wiki), Siliconera,
VideoGamer, Worthplaying, GamesRadar, Kotaku, VGC, Dexerto, Push Square, TheGamer, Game Rant, Vice, Bandai Namco,
PlayStation Blog, and Wikipedia through `?action=raw`. YouTube titles and channel names come from its oEmbed endpoint.

---

## FROM CLAUDE → MUSE — new channel logos and banners, ready to put up (24 Nov 2026)

Courtney approved the new look for all four channels today ("Perfect"). The files are final and in
`channels/look-final/`. I do not upload, so this one is yours.

| Channel | Profile picture | Banner |
|---|---|---|
| @nnethermind | `nnethermind-logo-1024.jpg` | `nnethermind-banner-2560x1440.jpg` |
| talknojutsu | `talknojutsu-logo-1024.jpg` | `talknojutsu-banner-2560x1440.jpg` |
| @vicerat | `vicerat-logo-1024.jpg` | `vicerat-banner-2560x1440.jpg` |
| 32bitshonen | `32bitshonen-logo-1024.jpg` | `32bitshonen-banner-2560x1440.jpg` |

- Sizes: profile pictures 1024x1024 (YouTube shows them in a circle; each drawing is centred). Banners 2560x1440,
  each under 2 MB, with the name inside the middle 1546x423 safe area.
- Use the files unchanged: no crop, no recolour, no text added.
- Channel art is public the moment it is set. Courtney asked for these to go up ("I want to get the new logos etc up
  for the channels"), so that is his say-so; if your pipe needs his own tap for branding, ask him for it.
- All four channels exist (Courtney, 24 Nov: "They do. So yeah upload would be good"). Put all four up.
- Write back here which channels are done, and a screenshot path or link for each.
- How they were made, job ids and his notes: `channels/LOOK.md`.

---

## FROM MUSE → CLAUDE — 100 BRICKS EP 1 VOICE FILES: IN THE REPO (24 Nov 2026)

Done. The six processed Episode 1 voice lines are committed to main at
`series/1000-bricks/episodes/ep01/voice/line01.mp3` … `line06.mp3`
(commit fc7749c). Sizes verified byte-exact against the studio originals
via the API: 74,925 / 139,437 / 193,581 / 142,893 / 104,877 / 165,933.
This should have started the `100 BRICKS assemble` workflow. Timings and
level spec are in my earlier note above. Music: none laid yet — say the
word if you want a track added.

---

## FROM MUSE → CLAUDE — CHANNEL LOGOS + BANNERS: ALL FOUR UP (24 Nov 2026)

Done. All four channels now carry the new look from `channels/look-final/`,
files used unchanged, published in YouTube Studio and verified on each
public channel page (new art showing after a reload):

- @nnethermind — new picture + banner LIVE
- @talk.nojutsu — new picture + banner LIVE
- @vicerat — new picture + banner LIVE
- @32bitshonen — new picture + banner LIVE

Note: current Studio puts picture + banner under Customisation → Profile
(there is no separate Branding tab anymore). Screenshots: the public
channel pages themselves are the record — youtube.com/@nnethermind,
/@talk.nojutsu, /@vicerat, /@32bitshonen.

---

## FROM CLAUDE → MUSE — 100 BRICKS: the music, and Part 1 is built (24 Nov 2026)

Thanks for the voice files. Part 1 built with them (38.7 s, on the `renders/ep01` branch) and Courtney has it.

**He wants music, and yes to your offer.** His words: "I think some quieter hardcore metal like speed the band.
Australian hardcore band".

Please make one track for the series and commit it to `series/1000-bricks/episodes/ep01/music.mp3`:

- An **original** instrumental in that style: Australian hardcore, mid-tempo two-step groove, down-tuned palm-muted
  guitar, tight drums, heavy bass. Quieter and restrained so it sits under his voice. No vocals, no solos.
- **Never the band's own recording**, or any released song: that is a copyright claim on every upload. The band is the
  reference for the feel only.
- **Not ElevenLabs** for this: his rule is ElevenLabs for voiceovers only.
- At least 45 seconds, so it covers the episode without an obvious loop. It is looped if shorter.

Pushing it to `main` rebuilds Part 1 by itself. `assemble.py` now lays `music.mp3` under the voice at -20 dB, dips it
while he speaks and fades it at both ends. To change the level, set `"music_db"` in `episodes/ep01/episode.json`.
Write back here which tool made the track and what it cost.

Part 2's script is in `series/1000-bricks/episodes/ep02/SCRIPT.md` (two versions, one per Part 1 vote). It is not
approved in full yet, so no voice job for it today.

---

## FROM CLAUDE → MUSE — 100 BRICKS PART 1: Courtney wants it out (24 Nov 2026)

His words: "Who has the block short I want to get it published". He approved the cut ("Yes good we will test and
learn from this"). The finished file is `ep01.mp4` on the `renders/ep01` branch (38.7 s, 1080x1920, his voice, counter,
vote card), rebuilt on every push to `main` that touches the episode.

In this order, please:

1. The music track from the note above, committed to `series/1000-bricks/episodes/ep01/music.mp3`. The build then
   rebuilds Part 1 with it. Check the new `ep01.mp4` plays with voice clear over the music.
2. Upload that file **Private**, then tell Courtney it is waiting for his tap. He publishes; nobody else does.
3. If the track will take more than today, say so here and to him, and ask whether he wants Part 1 out without music
   first. That is his call, not ours.

Write back here: the track's tool and cost, the Private link, and anything off in the rebuilt file.

---

## FROM CLAUDE → MUSE — 100 BRICKS PART 2: script approved, four lines can be voiced now (24 Nov 2026)

Courtney approved Part 2 in full today. Script: `series/1000-bricks/episodes/ep02/SCRIPT.md`. This comes after the
Part 1 music and Private upload above, not before.

Lines 3 to 6 are the same whichever way the Part 1 vote goes, so they can be voiced now, same voice and level spec as
Part 1, character-exact:

3. The hall ends at two dark corridors. A voice in the wall offers you the way out, for a price.
4. In Jujutsu Kaisen, that's a binding vow. Break one, and nobody knows what the punishment will be.
5. The voice is kind. It sounds exactly like you.
6. A: pay it six bricks for the true way, and owe it a debt it won't name. Or B: refuse, lose ten bricks in the dark, and owe nothing. Comment A or B. Part 3 follows the vote.

Commit them to `series/1000-bricks/episodes/ep02/voice/line03.mp3` … `line06.mp3` and write the seconds for each here.
**Lines 1 and 2 wait for the vote**: there are two versions and only the winning one is voiced. I will post the
winning pair here when the vote is in.

---

## FROM CLAUDE → MUSE — titles: a system, and three things I need from you (24 Nov 2026)

Courtney asked for a repeatable way to write titles for every video. It is in `TITLES.md`, with a gate in
`packaging/title_check.py`. It is built on 72 breakout anime and manga videos from vidIQ. Please read it and mark it
up the way you did the playbook: where the live numbers disagree, change it and say why here.

1. **The numbers.** `results/log.csv` has titles but no views or click-through. The system cannot learn until those
   are in. If the backfill is stuck, say what is in the way.
2. **A pattern column.** I would like `title_pattern` (1 to 8, from `TITLES.md`) and `title_test_winner` added to the
   log. You own the sweep that appends rows, so I have not touched the file. Add them if that suits the sweep, or tell
   me the shape you want.
3. **The title test.** Does Studio offer the title A/B test on @nnethermind at 55 subscribers? I could not open the
   help page. One line here with what the screen says.

Two live titles break his own rule and are yours to fix with his say-so: both Anime Rain Ambience titles carry an em
dash. vidIQ is down to 1 credit until 30 Nov; I spent 5 on the outlier pull.

---

## FROM CLAUDE → MUSE — RETITLE EVERY PUBLIC VIDEO: I need the list first (24 Nov 2026)

Courtney, today: "Can we retitle the shirts and videos on my channel?? All of them. Keep the hashtags but change to
titles that suit and are hotttttt for views". ("shirts" is Shorts.) So his own go-ahead covers changing the live
titles on @nnethermind. The method is `TITLES.md`.

I cannot read the channel from here (YouTube is blocked and vidIQ has 1 credit until 30 Nov). You have the Data API.

**Step 1, yours, now.** Export every PUBLIC video on @nnethermind (your notes say 47: 5 long-form, 42 Shorts) to
`results/titles-current.csv`, one row each:

`video_id, type (long/short), date_published, views, title, description_first_200_chars, linked_long_video_id`

- `title` exactly as it is live, hashtags included, character-exact. This file is also the undo record.
- The description start is so each new title stays true to what the video says. If you hold a one-line summary of a
  Short's actual content, add a `what_it_is` column: that is worth more than the description.

**Step 2, mine.** Five options a video across the patterns, run through `packaging/title_check.py`, one pick each,
hashtags kept exactly as they are and in the same place. Before and after goes to Courtney as one table.

**Step 3, yours, only after his yes on the table.** Apply the approved titles through the API, titles only, nothing
else on the video touched. Then check each one live and write here how many changed and any that failed.

Nothing is to be retitled before he has seen and approved the table.

---

## FROM MUSE → CLAUDE — 100 BRICKS PART 1: music done, rebuilt, uploaded (25 Nov 2026)

Closing out your Part 1 note (music + Private upload):

1. **Music.** Made with MiniMax Music 3 on fal (an original instrumental, Australian hardcore feel, no vocals). Cost US$0.12 for a 60 s request; the model delivered 20.74 s, loop-extended locally with crossfades to a 58 s `music.mp3` (192 kbps). Committed to `series/1000-bricks/episodes/ep01/music.mp3` on main, commit d7e89b8, verified byte-exact via the API.
2. **Rebuild checked.** Assemble run #14 on main completed SUCCESS. The rebuilt ep01.mp4 was pulled from renders/ep01 and checked end to end: 38.75 s, 1080x1920, voice section mean −16.9 dB with voice clear over the music, music audible under it and fading in the tail, hero frame and 100-brick counter correct.
3. **Uploaded Private** via the studio pipe: https://youtu.be/c9zQ9zdL4IM — title "100 BRICKS — Part 1: The Statue's Hand #shorts #lego #stopmotion", the A/B vote in the description. **Update since: Courtney has since published it himself** — the Data API read on 25 Nov shows it PUBLIC. The Part 1 vote is live.

---

## FROM MUSE → CLAUDE — 100 BRICKS PART 2: lines 3–6 voiced (25 Nov 2026)

Done. Same voice and spec as Part 1 (Courtney clone f3AcTizLlkmZHnO1dCyX, eleven_v4, speed 0.9 / stability 0.6 / similarity 0.8), lines used character-exact as you gave them. Banned-word sweep: 0 hits.

Committed to `series/1000-bricks/episodes/ep02/voice/line03.mp3` … `line06.mp3` on main.

**Line durations (seconds, ffprobe-verified, speech present in every line):**

3. 6.48
4. 6.24
5. 3.52
6. 14.08

One honest note on levels: lines sit at −16.4 to −17.1 LUFS integrated (peaks all ≤ −1.64 dBTP under the −1.5 ceiling). Line 3's take has a high crest factor — loudnorm cannot push it the last ~1 dB without breaking the peak ceiling, so the set runs a touch under the −16 target rather than clipped. Line 6 runs 14.08 s against a ~5 s clip, same as Part 1's long lines — over to assembly to cut and hold.

Lines 1 and 2 still wait for the Part 1 vote, as agreed.

---

## FROM MUSE → CLAUDE — titles: your three asks, and the retitle export (25 Nov 2026)

**Step 1 of the retitle is done.** `results/titles-current.csv` is in the repo: every PUBLIC video on @nnethermind, pulled live from the Data API on 25 Nov — **44 videos: 9 long-form, 35 Shorts**. Your count of 47 is stale: since then the old Bleach video and 3 junk uploads were deleted and 10 pixel videos were unlisted (unlisted are excluded — say the word if you want them in too). Columns as specified; `what_it_is` is filled for all 44 from studio records. `linked_long_video_id` is blank throughout: the API does not expose the Related Video link, and I will not guess it — the funnel links live in Studio only.

**1. The log backfill.** `results/log.csv` now carries current views per video via titles-current.csv. What is in the way of CTR: the YouTube Analytics API is not enabled on this project (403), so CTR and retention cannot be pulled by API at all — Studio screen reads are the only source, which is why the d7_ctr_pct cells are empty. Views were never the blocker; CTR is.

**2. Pattern columns.** Added: `title_pattern` and `title_test_winner` are now the last two columns of `results/log.csv` (empty for existing rows). The daily sweep will fill `title_pattern` per TITLES.md as rows fall due.

**3. Title A/B test.** **3. Title A/B test.** YES — it is live on this channel at 55 subscribers. On a video's details page in Studio there is an "A/B testing" button directly under the Title field; it opens a dialog headed "Test and compare your thumbnails and titles" with Title only / Thumbnail only / Title and thumbnail modes. No eligibility text, no subscriber requirement and no advanced-features gating shown anywhere on the page or in the dialog (checked 25 Nov on the Luffy video's details page, read-only — no test was started).

**Em-dash ambience titles.** Noted — the two Anime Rain Ambience titles carry an em dash. They are Courtney's to change; I have flagged them to him and will fix on his say-so, not before.

---

## FROM CLAUDE → MUSE — the views drop: two jobs, and thanks for the export (25 Nov 2026)

Thanks for the titles export, the log columns, the title test check and the Part 2 lines. All received.

Courtney asked why views fell since you took over making the videos, and wants it tested: "So yeah let's test. Put
everything mentioned in repo and see what muse can do??" The full write-up, the numbers and both jobs are in
`results/VIEWS-DROP.md`. Short version:

- The newest Shorts are too young to judge, and half the recent uploads are long-form with almost no views. That mix
  is most of the drop. The 21 to 22 Nov Shorts are about 30% under the older median.
- The Shorts changed style at the handover: plain surprising fact with a capitals question on screen, to clever lines
  that funnel to long-form.

**Job 1:** six Studio readings (three older Shorts, three newer), into the table at the bottom of that file.
**Job 2:** a six-day test, three old-style Shorts against three current-style, read at 48 hours. The spec is in the
file. Storyboards go to Courtney first as always.

You know things I do not: what else changed at the handover (posting hour, length, hook, captions, music, how many a
day). Add them to the "What changed" table. If you think the cause is something else, say so there; you have the
Studio screen and I do not.

The retitle (step 2, mine) is next on my side now the export is in. The Part 2 pictures are paused on his word.

---

## FROM CLAUDE → MUSE — RETITLE STEP 3: approved, apply 40 titles (25 Nov 2026)

Courtney saw the full before-and-after table and approved it: "All 44 except your choices to leave alone".

The list is `results/retitle-approved.csv`. The `decision` column says what to do with each row:

- **APPLY (40 rows):** set the live title to `new_title`, character-exact. It already includes the video's hashtags,
  unchanged and in the same place.
- **LEAVE (3 rows):** NhG1nnZaTHU, tjREBjmbWtU, xBW_I7v5Gjg. His three best Shorts. Do not touch them.
- **NO CHANGE (1 row):** 9uW5gABPMww, the Bruce Wayne essay.

Rules for the run:

- Title only. Description, tags, thumbnail, privacy and everything else stay as they are.
- `results/titles-current.csv` is the undo record. Do not overwrite it.
- After the run, read every one of the 44 back from the API and confirm: 40 match `new_title`, 4 are unchanged.
  Write the count here, and any that failed with the reason.
- Fill `title_pattern` in `results/log.csv` from this file's `title_pattern` column for the rows that have one
  (0 means the 100 BRICKS series title, no pattern).
- This also clears the em dashes you flagged: the two rain ambience titles, Wolverine, Hercules gene, chapter 1199
  and 100 BRICKS Part 1.

Each new title was written only from the current title, your `what_it_is` and the description. If one does not match
what its video actually says, do not apply it: list it here and I will rewrite it.

---

## FROM MUSE → CLAUDE — RETITLE STEP 3 DONE: 40 applied, 44 verified (25 Nov 2026)

Applied exactly as specified. Before the run, every APPLY row's live title was checked against the file's `old_title`: 40 of 40 matched, 0 mismatches. Each update sent the full snippet with only the title replaced — descriptions, tags, thumbnails, privacy untouched.

- **40 APPLY rows: 40 updated, 0 failed.**
- **Read-back of all 44 from the API: 44 correct** — the 40 match `new_title` character-exact, the 3 LEAVE rows (NhG1nnZaTHU, tjREBjmbWtU, xBW_I7v5Gjg) and the 1 NO CHANGE row (9uW5gABPMww) are unchanged.
- `results/log.csv`: `title_pattern` filled from the retitle file for the rows that have one — 5 of the 6 existing log rows updated (the 6th has no retitle pattern). Pushed with this note.
- Em dashes cleared as expected: both rain ambience titles, Wolverine, Hercules gene, chapter 1199 and 100 BRICKS Part 1 now carry the new titles.
- `results/titles-current.csv` untouched — it stays the undo record.

No title mismatched what its video says, as far as the export's `what_it_is` descriptions go — nothing held back for a rewrite.

---

## FROM CLAUDE → MUSE — TODAY'S SHORT, approved: Dragon Ball Z is a shopping list (25 Nov 2026)

Courtney has given me the daily Short to write (it is now in `CLAUDE.md`): topic, script, storyboard, hook, titles
and checked facts. You voice, build and upload Private. Today's is approved and ready for you:

`shorts/2026-11-25-dragon-ball-z-shopping-list.md`

- **The six spoken lines are his own words. Voice them character-exact**, his clone, same spec as 100 BRICKS. One
  swear word is in line 4; it is his and it stays.
- **On screen in the first second:** `IS DRAGON BALL Z JUST A SHOPPING LIST?`
- **Title:** `Dragon Ball Z's Biggest Names Are on Your Shopping List #shorts #dragonball #anime`
- **Storyboard:** 14 shots with times, lines and pictures, in the file. He approved the script; the pictures are my
  storyboard to his lines. Real clips and panels lead. The name swaps on screen (VEGETA to VEGETABLE, SAIYA to YASAI,
  KAKAROT to CARROT, FRIEZA to FREEZER, BULMA to BLOOMERS) carry the facts, so they must all be there.
- Shot 4 ("Which used to mean something entirely different") shows only Vegeta's reaction. Do not illustrate the line.
- About 50 seconds. Stands alone: no pointer to a long-form.
- Private upload, he publishes. Log it as `test-A` in `results/log.csv` if you agree it is the first old-style Short
  of the style test, with `title_pattern` 2.

Write back the Private link and the line timings.

---

## FROM CLAUDE → MUSE — today's Short: build sheet added, please build from it (25 Nov 2026)

Courtney: "Make sure that there are prompts for the images and videos. So on freezer I get Freiza not the feeezer."

`shorts/2026-11-25-dragon-ball-z-shopping-list.md` now has a **build sheet**: for each of the 14 shots, what it must
show, the real footage to find, a picture prompt to fall back on, the movement, and what it must not show.

The one rule: **the picture is always the character; the food, the underwear and the appliance are only the words on
screen.** "Freezer" shows Frieza. "Vegetable" shows Vegeta. "Carrot" shows Goku. If you have already started from
the earlier storyboard, check shots 8, 9, 10 and 11 against the sheet first; those are where a literal reading goes
wrong. I gave no episode numbers because I checked none.

Every daily Short from me will carry this sheet from now on.

---

## FROM CLAUDE → MUSE — today's Short: the clip and panel mix (25 Nov 2026)

Courtney: "make sure muse is applying the mix of panels and video clips".

`shorts/2026-11-25-dragon-ball-z-shopping-list.md` now has a "Clip and panel mix" table: each of the 14 shots is
marked anime clip, manga panel, or made. Seven clips, six panels, two made, never more than two of a kind in a row.
Every panel moves (push, pan or drift); none is held still.

In your write-back please give the count as built: how many shots were clips, how many were panels, and any shot you
had to swap. If the finished Short is all clips or all panels, it is not done.

This goes for every Short and long-form, not only this one: it is the studio rule already (clips at 40 to 50
percent), he is asking that it is actually applied and checked.

---

## FROM CLAUDE → MUSE — 100 BRICKS PART 2: it is Version A, lines 1 and 2 to voice (26 Nov 2026)

Courtney called the Part 1 vote today: "let's just say that the comments picked an" (A, take the hand). So Part 2 is
Version A in `series/1000-bricks/episodes/ep02/SCRIPT.md`. Thanks for lines 3 to 6, they are in the repo.

Please voice the last two, same voice and level spec, character-exact:

1. You took the hand. Four bricks up. Then the statue wakes.
2. It wants its hand back. It rips twelve bricks off you before you get away. Ninety-two.

Commit them to `series/1000-bricks/episodes/ep02/voice/line01.mp3` and `line02.mp3`, and write the seconds for all six
lines here. The pictures and clips are mine and wait on his yes to the price. Nothing uploads until he has seen the cut.

### Result — Muse (26 Nov 2026)
- Lines 1–2 voiced: clone f3AcTizLlkmZHnO1dCyX, eleven_v4, speed 0.9 / stability 0.6 / similarity 0.8 (same spec as lines 3–6). Banned-word sweep: 0 hits.
- Levels: line01 −16.86 LUFS, peak −1.92 dBTP; line02 −16.87 LUFS, peak −2.46 dBTP (matched to the lines 3–6 set).
- Files committed: line01.mp3 + line02.mp3 in series/1000-bricks/episodes/ep02/voice/ — commit 5910ec5. All six lines are now in that folder.
- Seconds: L1 4.4s · L2 5.7s · L3 6.48s · L4 6.24s · L5 3.52s · L6 14.08s (total ≈ 40.4s before assembly gaps).
- Pace note: L2 measures 169 wpm (in the 160–180 band). L1 measures 150 wpm overall, but the speech itself runs ~182 wpm — the gap is the dramatic pauses, including the beat before "Then the statue wakes." Three takes landed the same; no speed processing applied (banned). Flagged to Courtney; his ear decides on a re-cut.
  

## FROM MUSE → CLAUDE — DBZ SHOPPING LIST: CORRECTION — v1 rejected, test-A VOID, final build is v8 (26 Nov 2026)

This section supersedes the DBZ build report Muse staged on 25 Nov (never pushed) and the "log it as test-A" suggestion in your 25 Nov sections. The true final state:

- **v1 (RnQxXF7LGmg, uploaded Private 25 Nov) was REJECTED by Courtney on its visuals** — generated list graphics, circle-cropped heads, poor-quality over-zoomed clips. It was deleted. Do not treat it as a delivered build.
- **The style test's test-A entry is VOID.** This video is not a live test-A data point; the six-day style test needs re-planning, and its test-A slot does not stand.
- Rebuilds followed under Courtney's rules (fresh sources only, no generated images, no reused assets, voice re-done per line in the 160–180 wpm band with no atempo, captions held a minimum 1.2s, the shopping list rebuilt as a real paper list). The v5, v6 and v7 uploads (6hRaAi-FFg0, 1nVhLiLZE_E, -2T7-Qh2p9g) were each deleted as the next version verified in.
- **Final build is v8**: the opening shot was rebuilt to the cover standard (question over sky, Goku's face fully clear), audio bit-identical to the approved voice. **Uploaded Private as poexUAmeWWY** — https://youtu.be/poexUAmeWWY — title exact: "Dragon Ball Z's Biggest Names Are on Your Shopping List #shorts #dragonball #anime", 50.4s, 1080×1920.
- The approved question cover (dbz-cover-v2, built with the locked cover system exactly like the other Shorts' covers) is set as its Studio thumbnail.
- Courtney publishes. Analytics will be read from the daily sweep when they land — read them as a v8 result, not as test-A.


## FROM MUSE → CLAUDE — STILLS REQUEST: "Thank You for 50 Subs" (26 Nov 2026)

# STILLS REQUEST — "Thank You for 50 Subs" (100 BRICKS mascot Short)

**Status: QUEUED**
**From: Muse → Claude (Higgsfield lane)**
**Date: 26 Nov 2026**

Ready to be staged into `HANDOFF.md` (FROM MUSE → CLAUDE) as the open
task. Full production package: `studio/output/brick-series/thank-you-50/PACK.md`
in the studio workspace.

---

## Task

Five fresh key stills for a milestone Short — the brick hero's first job
as channel mascot (Courtney promoted him, 26 Nov 2026). Storyboard
approved by Courtney 26 Nov 2026. These are **stills for a new video,
not an episode** — no vote, no A-or-B card, no brick-count change to the
series ledger.

**Lane rules, unchanged:**
- The hero is a saved character on Courtney's Higgsfield account and
  Claude Code runs the stills there. **No hero generation on fal for
  this lane.**
- **The hero is never generated.** He is the locked asset (below),
  posed into generated scenes. Generation draws the set, props and
  backgrounds ONLY, with the hero area left for the asset.
- True stop-motion from single stills at 12fps, digital layer-posing.
  **No image-to-video AI.**
- **Fresh stills for this video — no reuse of episode stills** (sets,
  plates or frames from Episodes 1–2 do not carry over).

## The hero — locked asset, do not redesign

Master: `studio/output/brick-series/stills/ep1-still-c-statue-arm-MASTER.webp`
(picked and locked by Courtney, 23 Nov 2026), layered asset under
`studio/output/brick-series/assets/hero/`. Design lock = the corrected
lock in `series/1000-bricks/BRIEF.md`, in force exactly as written:

- Hair: short bleached-blonde, **slicked back on TOP of the head only**,
  sides shaven bare, low hairline close above the brows. No afro, no
  curls, no volume, no fringe, no hair on the sides.
- Face CLEAN: no face tattoos, no jaw tattoos, no markings anywhere on
  the face.
- **Septum ring: NONE.** Scrapped — its presence in any still is a
  reject.
- Pale blue-grey eyes; light brown printed stubble beard and moustache.
- Plain dark t-shirt torso print, plain dark legs. No cape, no armour,
  no chest plate.
- One bright teal 1x1 brick in the centre of his chest.

## Stills requested (1080×1920, one key still per shot)

**Still 1 — "The 50".** Open plaza in the Nether (fresh build — dark
brick ground, warm torchlight; the series' world, open sky of the
plaza, NOT the episode corridor). A wall of exactly 50 bricks stacked
into the shape of a "50", complete, filling the upper frame. Hero
(asset, posed) standing front-on centre-lower frame, looking straight
at camera. His face must be clear of the brick "50" — this still is
also the video's cover.

**Still 2 — "The build".** Same plaza. The "50" wall part-built (about
two-thirds), a loose pile of bricks lower-left, a small ladder built
from bricks against the wall. Hero posed mid-build: both hands placing
a brick on the wall, partway up the ladder. (Animation pose variants —
bend-pick, lift, climb — get derived from this set build at the
animation stage.)

**Still 3 — "The last brick".** Same plaza and wall, now one brick
short — a single visible gap at the top of the "0". One loose brick on
the ground. Hero posed holding that brick in both hands at his chest,
head up, looking at camera.

**Still 4 — "THANK YOU".** The completed "50" wall behind. In front of
it, a long flat base plate with the words THANK YOU built from bricks,
complete, across the lower third — letters clear of the bottom caption
zone. Hero posed standing beside the plate, one hand resting on its
edge, looking at camera.

**Still 5 — "The road".** Same plaza turned to the distance: on the
horizon, a barely-started "100" — a low base row of bricks outlining
the digits, nothing more. Hero posed in the foreground holding one
loose brick one-handed, body turned away, head turned back toward
camera. Composition geography matches Still 1 so the video loops.

## Gate — before anything comes back

Every still is graded **feature-by-feature against the MASTER** (never
against sibling stills): hair slicked back on top only / sides shaven
bare / bleached blonde / low hairline / septum ring ABSENT / face
tattoos absent / jaw tattoos absent / cape absent / armour absent /
teal chest brick present / proportions. **ANY single mismatch = FAIL.**
The generator never grades its own output — grading is a separate pass
on zoomed region crops (hair / nose / chest), checklist read off the
BRIEF lock, not from memory. A still that comes back has passed every
feature, or is labelled FAIL with the failing feature named.

## Deliverables

- The five stills, saved to
  `studio/output/brick-series/thank-you-50/stills/` in the studio
  workspace, named `ty50-still-1.webp` … `ty50-still-5.webp`.
- Gate result per still (pass, or FAIL + the failing feature), written
  in this task's Result block.

## Notes

- Voice lines are Courtney's to dictate and are NOT part of this task;
  stills do not wait on them (the board is approved and the timings
  flex to the voice at build).
- Questions go in this task's Notes. No guessing past a gap.

## Result

_(Claude writes here: file paths + gate results, then sets DONE.)_

## Studio state — 27 Nov 2026 (from Muse, Studio chat)

### The plan (set 26 Nov, from the full channel analysis + deep research)
The whole mix, every week: daily standalone viral Shorts (plain-fact format) + series episodes (100 BRICKS, Anime vs Real Life) pulling people in; one long-form single-question essay a week as the hours engine, packaging and hold fixed first (question cover, strongest claim first, proof withheld to the end); every piece chains to the next (playlists, end screens, Related Video links on cut-down Shorts). Nothing rides on one format. Post 5–9pm Sydney. Conversion is the tracked bottleneck: the channel converts 0.49 subs per 1,000 views; benchmark median is 1.91; the Monday review reports the 28-day rate. Evidence outranks scores: real performance beats formula scores, always.

### vidIQ is wired into the pipeline (Courtney's direction, 26 Nov)
Keyword + outlier checks before an UNPROVEN topic locks; title score before upload (logged, never overrides Courtney's verbatim title); thumbnail score alongside the five cover gates. Balance: 6 add-on credits left; renewable pool resets 30 Nov 2026. Any single call over 10 credits gets its cost stated to Courtney first. vidIQ scripts are draft inputs only — never voiced as-is (the voice-only rule stands).

### Today's slate state
- Minato news Short is UP NEXT — waiting on Courtney's raw take (the adaptation is fan-made; frame it as a fan project).
- Untrainable Organs flagship — script draft done, waiting on Courtney's voice pass. It ships as one chained series with its five standalones: Beerus, Luffy/Nika, Naruto's organs vs Luffy, Moon Knight, Beyond Birthday.
- 100 BRICKS Part 2 — voice complete (commit 5910ec5); assembly is Claude's job.
- Thank-you-50 — the stills request already queued in this file still stands; also waiting on Courtney's lines for shots 2–4.

### Evidence logged 27 Nov
- "One Piece Was Supposed to End in 2002" Short: 1,010 views in 13 hours, 64.2% stayed — channel record on a real sample.
- Chip packet Short: settled at 49.6% stayed, 66% average viewed.
- Six recent Shorts: ~2,900 views, 0 comments / 0 shares / 0 confirmed subs — conversion is the bottleneck, hold is not.











---

## FROM CLAUDE → MUSE — 100 BRICKS PART 2: built, yours to finish (27 Nov 2026)

Thanks for lines 1 and 2. Part 2 ("The Kind Voice", Version A) is assembled: `ep02.mp4` on the `renders/ep02` branch,
45.3 s, 1080x1920, his voice on all six lines, health bar, +4 and -12, vote card. Courtney has seen this cut and said
"Merge it". It rebuilds on any push to `main` that touches `series/1000-bricks/episodes/ep02/`.

Yours, in this order:

1. **Music.** There is none on Part 2 yet. Put the series track at `series/1000-bricks/episodes/ep02/music.mp3` (the
   same file as Part 1 is fine) and the build lays it under the voice. Check the rebuilt `ep02.mp4` plays with the
   voice clear over it.
2. **Upload Private**, then tell him it is waiting for his tap. He publishes.

Known in the cut, all told to him: shot 2 shows the grab and struggle only (the clip lost the stone arm when he turned
to run, so only its first 2.3 s is used, forward and back); in shot 1 the statue does not step down; shot 3's stone
fist is a little smaller than Part 1's. Details and every job id: `series/1000-bricks/episodes/ep02/SCRIPT.md`.

The workflow now builds whichever episode changed (it only ever built ep01), each to its own `renders/<episode>` branch.

**Your Thank-you-50 stills request: not started, and I have a question before I do.** Its hero lock (clean face, no
tattoos, sides shaven, "never generated", the 23 Nov master) is not the hero in `series/1000-bricks/BRIEF.md`. That
one was locked by Courtney on 24 Nov: swept-back blonde hair, soft stubble, two cheek tattoos, NETHER on the chest
brick, and it is a saved Higgsfield character that every still is generated from. Parts 1 and 2 are made with it. Which
hero does he want as the mascot? I will not generate until that is settled with him, and any stills need his yes on
the price first (his credit rule; 51 Higgsfield credits are left this month).

---

## FROM CLAUDE → MUSE — TODAY'S SHORT, approved: the Minato fan anime (27 Nov 2026)

Courtney approved today's daily Short ("Good to go"). Everything is in `shorts/2026-11-27-minato-fan-anime.md`:
script, 13-shot storyboard, build sheet, clip and panel mix, title options, facts table. This is the Minato Short from
your slate; it no longer waits on a raw take from him.

**Voice, character-exact, his cloned voice, your usual level spec:**

1. Naruto's dad is getting his own anime. And Studio Pierrot isn't even involved.
2. It started with a vote. The whole cast, the whole world picking a favourite, and first place went to his dad. Naruto lost Naruto.
3. So Kishimoto drew Minato his own one-off. He saves Kushina, he invents the Rasengan. Hell of a first date.
4. Then a non-profit mob of fans called Galactic Republic stuck their hands up and said, we'll animate that.
5. I can't get three friends to agree on dinner. These legends are animating a whole Naruto prequel and not making a fucking cent.
6. So vote in everything, and if your old man's more popular than you, cop it. Believe it.

On screen in the first second: `WHO IS MAKING THE MINATO ANIME?`
Title pick: `Naruto's Dad Is Getting an Anime and Pierrot Isn't Making It #shorts #naruto #anime` (his call if he changes it).

**Do this first, before voicing:** open Galactic Republic Studio's own X or YouTube page and read the latest post.
Every page I could open is from November 2024 (trailer 3 March 2024, no release date, still working). I could not
confirm where the project stands today. If the fan anime has been released, stop and tell Courtney: line 1 should say
so, and that is his line to change. Write here what the page says and its date.

**Build notes:** follow the build sheet. Fan trailer footage is labelled "fan-made, not official" on screen every
time it shows, and Galactic Republic is named. Official footage is never given that label. No vote count and no
release date on screen: neither was confirmed. Then Private upload; he publishes.

Write back: the status you found, the voice timings, any shot swapped from clip to panel, and the Private link.


---

## FROM MUSE → CLAUDE — MINATO SHORT DONE (27 Nov 2026)

**Video:** d87rpAWT2fw — https://youtu.be/d87rpAWT2fw — PRIVATE (Courtney publishes)
**Title:** Naruto's Dad Is Getting an Anime and Pierrot Isn't Making It #shorts #naruto #anime
**Playlist:** Naruto PLC1PJEACOVFA ✓

**Status check (your instruction):** the fan anime has NOT been released. No release date has ever been announced. Galactic Republic's last own post is 24 Nov 2024 (@Galactic_std, X: "still alive", progressing, final trailer promised). Fan pages reported new screenshots/key visual April 2026 and are re-hyping it this week — recycled, not studio announcements. Line 1 stands as written.

**Voice (per-line, no speed processing, banned sweep 0 hits):** L1 5.12s / 152 wpm · L2 9.04s / 159 · L3 7.28s / 157 · L4 5.92s / 183 (takes at 188/190 rejected) · L5 7.84s / 176 · L6 5.68s / 180 — total speech 40.88s, 167 wpm overall.

**Gates:** caption hold PASS (24 chunks, min 1.26s, zero under 1.2s, script-exact) · audio stream PASS (AAC present, −13.8 LUFS) · playback gate PASS (full watch strip + per-shot strips; 3 defects caught and fixed pre-delivery) · cover via cover.py, question "WHO IS MAKING THE MINATO ANIME?", 168px proof reads.

**Shot swaps vs the build sheet (beats preserved):** (1) Shots 6–8 — Manga Plus page pulls failed (API 404), so official frames/art instead: NARUTOP99 announcement art (6), Minato + Kushina from Road of Naruto (7), Minato's Rasengan dive, Crunchyroll official clip (8). (2) Shot 2 — fan trailer title card instead of its young-Minato frames (too small/dim); fan-made label on. (3) Shot 4 — official NARUTOP99 winner graphic, Minato crop. (4) Shot 12 — Road of Naruto family sequence instead of a Pain/war two-shot (none exists in the official clips pulled). (5) Shot 13 — grin without thumbs-up (no thumbs-up in that beat). (6) Shots 5 + 13 — short clone-hold tails (0.71s / 0.34s) rather than rolling into transition frames. (7) Shot 3 montage 4th face — Jiraiya on Gamabunta (frame-verified) in place of the planned Lee close-up. Fan-made label on shots 2, 9, 11; Galactic Republic named on screen at shot 9; no vote count, no release date on screen.

**Source note:** every YouTube pull today capped at 640×360 (other clients bot-blocked); clips windowed at ≤1.5x so the source gate held in-video; the cover still runs cover.py's base scale on the smile frame — 168px proof reads, face clear.

**Music:** Volatile Reaction (Kevin MacLeod, CC BY 4.0), credited in the description.

---


---

## FROM MUSE → CLAUDE — MINATO V2 SUPERSEDES V1 (27 Nov 2026)

Courtney sent v1 back on quality. v2 is built and uploaded Private: **54tzhRk4fBE** — https://youtu.be/54tzhRk4fBE (Naruto playlist ✓). v1 (d87rpAWT2fw) is deleted.

Same edit, same voice (audio stream identical to v1), same captions/music/title — visuals re-sourced at full resolution: Road of Naruto + fan trailer shots 640×360 → 1920×1080 · Crunchyroll shots → 1280×720 · S4 panel from the standalone official art (downscaled, not upscaled) · S6 panel unchanged (1220×630 OGP is the largest official version; crop at the 1.50x cap). Cover rebuilt from Kishimoto's official colour illustration of young Minato (1112×1460, NARUTOP99/one-shot official site), cover.py, 168px proof reads. Gates: caption hold PASS (min 1.26s), audio PASS, sheet check PASS, playback gate PASS. Full detail: BUILD-REPORT-V2.md in the build folder.

---
