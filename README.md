# Content Pipeline

## Day-to-day: the Nethermind app

Open **Nethermind** from Applications or the Dock (`./make_app.sh` rebuilds it). It opens on
**Today**: everything that needs you, each with a tick circle. Ticking clears it, with Undo.
It also starts Studio's server (:8766) and Jarvis's brain (:8765) behind the scenes, and sends a
notification when a new video is ready. Screens: Today · Videos (review, Schedule…, Needs changes…)
· Performance · Ideas · Settings. Press ⌘K to ask Jarvis or jump anywhere.
`.venv/bin/python studio.py` still serves the same UI in a browser.

| Command | What it does |
|---|---|
| `./build.sh <id>` | fetch/generate images → render main + TikTok cut → QA both → thumbnail → upload asset bundle |
| `./build.sh <id> --no-fetch` | re-render only, using the images already in assets/ |
| `./post.sh <id>` | dry run: shows exactly what would go to YouTube, Instagram, TikTok |
| `./post.sh <id> --live` | uploads to R2 and queues on Buffer (YouTube tags + pinned comment still manual) |
| `.venv/bin/python stats.py` | pulls views/shares/saves for Buffer-posted videos into out/stats.json |

**Daily at 7:00** (Claude app → Scheduled → "Nethermind daily build"): refreshes stats, updates
LEARNINGS.md from the numbers, builds + packages the next video for your review (never posts), and
publishes the phone-friendly dashboard: https://claude.ai/artifact/H7zHPA7sX1urnaWbt9yR7B
(`dashboard.py` builds it; daily notes land in out/daily/).

The GitHub "Render and post" workflow now takes any video id: it restores the asset bundle
`build.sh` uploaded, runs `build.sh`, and posts only if you tick "publish".


A factory for faceless, fact-checked YouTube Shorts. One JSON config in, one finished MP4 + SRT out. Narration is Kokoro TTS — free, self-hosted, no API key (voice: am_liam); visuals are either public-domain NASA/NOAA/ESA media or, for topics with no public-domain source (e.g. superhero trivia), original AI-generated art from Gemini. Fonts are open-licence, and the score is synthesised from scratch. Only cost is a Gemini API key for hero-config art (see SETUP.md) — otherwise free. `tts_elevenlabs.py` is kept as an optional fallback backend, not used by default.

## Make a video

```bash
cd ~/Movies/Content-Pipeline

source .venv/bin/activate                 # deps live here (Homebrew python3 lacks soundfile/kokoro-onnx as of 2026-09-24)
python3 new_video.py fact my_topic        # scaffold a config
#   ... edit cfg/my_topic.json: the text, the image names/prompts, the hook ...
python3 fetch_real.py cfg/my_topic.json   # real photos first — see "Visuals" below
python3 gen_visuals.py cfg/my_topic.json  # only for "kb" images with a "prompt" (no real photo exists)
python3 make_short.py cfg/my_topic.json
python3 qa_render.py cfg/my_topic.json    # ALWAYS run this before it goes near Buffer — see below
#   ... write packaging/my_topic.json (title, description, tags, captions, pinned comment, "thumbnail" block) ...
python3 make_thumb.py packaging/my_topic.json  # out/my_topic_thumb.jpg (1280×720) + out/my_topic_cover.jpg (1080×1920)
```

Out comes `out/my_topic.mp4` (1080×1920, ~30–45s) and `out/my_topic.srt`. Takes about 2–3 minutes plus generation time. `./runall.sh` rebuilds every config in `cfg/`.

**`qa_render.py` is not optional.** Two silent-failure incidents (2026-09-21) shipped because nothing
actually looked at the output before it was trusted: hook/credit text overflowing both edges of the
frame (caught only by manually screenshotting), and Buffer posts running a crushed ~200kbps remux or
the wrong-length video while Buffer itself reported no error. `qa_render.py` runs the automated checks a
script actually can (dimensions, bitrate floor, duration sanity, srt exists) and builds a contact sheet
of 8 evenly-spaced frames at `out/<id>_qa_contact.jpg` — a 5-second glance that catches what the checks
can't (text overflow, a wrong or ugly image, a caption that doesn't fit). Look at the contact sheet
every time, not just when the exit code is non-zero.

Four scaffolds: `fact` (narrated story, public-domain or generated stills), `ice` (iceberg chart — needs no media at all, the chart is drawn in code), `creature` (animal reveal), `hero` (superhero trivia — Gemini-generated art only, see "Visuals" below).

## Making a video (Draft → you approve → build)

**Content → Make** (or **Draft now** on any idea, or **Draft it now** on a scorecard you said "Make it" to): the Content agent researches the facts with sources, writes the script, visuals plan and packaging, checks the hook, and stops. The draft lands in **Today** — read it, edit any line, pick a title, then **Approve & build** (Production renders the Short + TikTok cut, QA, thumbnail) or **Redraft with notes**. Nothing posts until you press Post. `python3 drafter.py "topic"` does the same from Terminal.

**Daily (7:00, with a 20:30 catch-up if the morning run failed):** `./install_daily.sh` once (re-run it after updating). `daily.py` refreshes the numbers, runs the learning loop, drafts the next video (your pinned idea → your "Make it" scorecards → Intelligence picks → backlog) and on Sundays plans and renders the weekly long-form from that week's Shorts. launchd catches up after sleep; if it still hasn't run for 26h, Today says so. Don't also run the Claude app's old "Nethermind daily build", or you'll get two videos a day.

## Weekly long-form (16:9)

Sundays the daily run plans the week's episode (`episode.py --week`: that week's finished Shorts become chapters) and Production renders it (`make_long.py episodes/<id>.json`): intro, a title card per chapter, the Shorts' own narration reused (no re-recording), 1920x1080 with portrait art centred over a blurred fill, captions in the lower third, then QA, **real YouTube chapter timestamps**, a description listing every chapter's sources, and a thumbnail. It lands in Production → Videos for review; posting it goes to YouTube only (`./post.sh <id>_long`). Content → Make shows each episode with Render / Review buttons. Any config can be rendered wide with `"format": "landscape"` — Shorts are unchanged.

## Is everything working?

`python3 selftest.py` (same checks as Control → Settings): keys, the 7:00 run, the `claude` command for drafting, ffmpeg, the Kokoro voice files, fonts, disk space — each with the fix in plain English.

## NETHER — agents that run the pipeline, and learn

Seven agents own every job, each a region of the brain with sub-agents around it: **Intelligence** (Ideas, the five scouts), **Content** (research, script, packaging, hooks, episodes), **Production** (Videos, visuals, render, TikTok cut, QA, thumbnail), **Publishing** (Calendar, scheduling), **Analytics** (Performance, Retention, learning loop), **Business** (Comments, monetisation), **Control** (Task log, daily run, Settings). Every page lives inside the agent that owns it. Each has sub-agents; every job is a task in `out/nether.db` with its steps, errors and a Retry. They glow on the brain — crimson while working, amber when one needs you — and the **Agents** page shows exactly which step broke.

**Every sub-agent has a desk.** Click any sub-agent (on the brain, or its chip in a hub) and you get its desk: the one question it answers (Demand scout: *do people actually watch Shorts about this?*), what it has found (the most-watched Shorts, small channels breaking out, which lanes beat your average, which scripts fail the 3-second hook rule, days with nothing going out…), what you can do right there (Scout, Draft it, Score, Refresh, Re-learn), and its own last tasks with Retry. Built by `studio_ext_desk.py` from each sub-agent's real work.

**Today's run (bottom-right, every page).** One tap walks you through today, job by job — posting first: until today's Short is live or scheduled, step 1 is whatever gets it there (approve the script, build it, or post it), and the dock glows. Go opens the right page, Done ticks it off. It never posts for you. On a Mac, the 7:00 run and the 20:30 catch-up also send a notification if today's Short isn't out yet (`studio_ext_day.py remind`). When a video goes out, the screen bursts and Publishing fires into Analytics on the brain.

**Music and sound (bottom-left ♪).** *Nether drift* is generative ambient made live in the browser (no files, no rights issues); or drop your own .mp3/.m4a files into `music/` (never committed). Interface sounds — hand-offs, Done, a video going live — are off until you tick them.

**Iceberg is a template, not a topic.** Any subject in the channel's lanes becomes a 5-tier long-form essay ("The Dragon Ball Iceberg", "The Real-Life Superpowers Iceberg"). Make → Iceberg takes any topic; every Brief recommendation has *As an iceberg*; the Sunday run picks an iceberg from TOPICS.md in a different lane from last week's.

```bash
python3 orchestrator.py                          # every agent's state + recent tasks
python3 intelligence.py "wolverine vs axolotl"   # 5 scouts → a scorecard out of 100 (also: Studio → Intelligence)
python3 learning.py                              # link scorecards to posted videos, re-weight, update LEARNINGS.md
```

**Collaboration:** each scorecard waits for your call — *Make it* (adds it to TOPICS.md → Intelligence picks) or *Not for us* — with a reason. Your calls become the "Your taste" part of later scorecards in that lane. **Learning:** once a video made from a scorecard is posted, the scorecard becomes a checked prediction; each part of the score is re-weighted (max ±25% a run, needs 2+ videos each side) by whether it really went with more views. `refresh.sh` runs the learning loop after every stats refresh; lessons land in the auto block of LEARNINGS.md, which the daily build reads.

## Long-form episode → Shorts → TikTok

```bash
cp episodes/_example.json episodes/buried_origins_02.json   # write the episode as chapters
python3 episode.py episodes/buried_origins_02.json          # one Short + one TikTok cut per chapter,
                                                            # plus episodes/<id>.plan.md (script + YouTube chapters)
python3 retention.py check  cfg/<id>.json                   # hook/pacing checklist for any config
python3 retention.py tiktok cfg/<id>.json                   # TikTok cut: number on frame 0, punch-in,
                                                            # tight gaps, no still held over ~6s
```

Tag a segment `"in": ["long"]` for depth only the episode gets, or `["long", "short"]` to keep it out of the TikTok cut. The 16:9 long-form render isn't wired yet; the plan file is the script for it.

## What's in here

```
make_short.py      the factory — TTS, captions, visuals, score, mix, subtitles
tts_kokoro.py      Kokoro narration backend (free, self-hosted; audio + estimated word timings)
tts_elevenlabs.py  ElevenLabs narration backend — optional fallback, not used by default
gen_visuals.py     Gemini image generation for "kb" segments with a "prompt"
fetch_real.py      Wikimedia Commons PD/CC0 photo fetch for "kb" segments with a "real"
new_video.py       scaffolds a new config so you never start blank
make_thumb.py      thumbnail + vertical cover from the packaging file's "thumbnail" block
fetch_assets.sh    re-downloads every public-domain asset (safe to re-run)
runall.sh          renders every config in cfg/
cfg/               one JSON per video — this is the only file you edit
assets/            media + fonts
out/               finished MP4s and SRTs
tts/               cached narration (delete a folder to re-record that video)
```

## How a config works

Each `segments` entry is one spoken beat. The `vis` block says what's on screen:

```json
{"t":"kb",  "src":"casa_lg.jpg", "z0":1.3, "z1":1.1, "cx":0.5, "cy":0.45}
{"t":"vid", "src":"clip.mp4", "ss":1.2, "fit":"square"}
{"t":"ice", "tier":2}
```

`kb` is a Ken Burns move over a still (`z0`→`z1` zoom, `cx`/`cy` pan centre). `vid` plays a clip. `ice` descends the procedural iceberg.

Useful keys:

- `"hook": true` — first segment, shows the big opening text from the top-level `hook` block
- `"hero": {"at": 4, "lines": ["5,400 MPH"], "col": "a2"}` — a big number that slams in on word 4
- `"payoff": true` — use this clip's own audio as the payoff (the score ducks to silence under it)
- `"end"` — the card naming the next video, which is what actually earns subscribers

Captions, word timing, the score, loudness normalisation to −14 LUFS and the SRT are automatic.

## The rules that make these work

Learned from the retention data and from six videos of iteration:

1. **The hook is frame zero.** Big text, already on screen, saying the same thing the voice says. Half of all drop-off happens in the first three seconds.
2. **One hero number per video.** Not three. It's the thing people repeat in the comments.
3. **A real payoff.** A sound, a reveal, an image they haven't seen. Not a summary.
4. **State the caveat.** Where the popular version of a fact is exaggerated, say so — "the range was 272 to 512 years" beats repeating a headline. It's also the only defence against a comment section correcting you.
5. **End by naming the next video.** Not "subscribe". The chain is the subscribe mechanism.
6. **Visual change roughly every two seconds.** Zoom direction, image, or tier.

## Visuals

`"kb"` segments read from `assets/<src>`. Three ways to fill that file in:

1. **Public domain photo** — download it yourself or via `fetch_assets.sh` (fixed NASA/NOAA/ESA list), or add a `"real":{"query":"..."}` to the segment and run `fetch_real.py cfg/<id>.json` to pull a real photo from Wikimedia Commons, filtered to entries Commons' own curators have explicitly marked "Public domain" or "CC0" (not a user-supplied tag — Commons is far more reliable here than open-upload sites like archive.org, which mixes real PD content with actual copyrighted uploads regardless of tags). `fetch_real.py` prints the source page — put it in the config's `"credit"` field.
2. **Gemini-generated art** — add a `"prompt"` to the segment and run `gen_visuals.py cfg/<id>.json`. This is the only option for anything involving copyrighted characters (Marvel/DC and similar) — real footage or official art of those isn't usable at all. `gen_visuals.py` prepends a house style (stylized, non-photorealistic) and prompts should stick to archetype/pose/palette/mood, never a named character or exact costume/logo — that keeps the output clearly original rather than a close copy of someone's trademarked design, and Gemini's own content filter will outright reject a prompt that reads as too close to a specific existing character. Treat prompting discipline as your responsibility, not a guarantee the API enforces.
3. **Real public-domain Golden Age comic scans** — a manual, per-issue job, not scriptable: "pre-1964" is not the same as "public domain," some issues were renewed and are still under copyright. Browse Digital Comic Museum (vets this themselves before hosting) or verify a specific issue yourself against the scanned Catalog of Copyright Entries at onlinebooks.library.upenn.edu/cce/ before using it. Don't trust archive.org's tags on their own — verified in this pipeline's own history: a "public domain"-tagged search there surfaced an actual 1977 Marvel comic and a 2002 DC/Vertigo comic alongside genuinely PD titles.

## Assets — what's safe

Public domain, no permission needed, credit as a courtesy:

- NASA image library — images.nasa.gov
- Chandra X-ray Observatory — chandra.si.edu (also its sonifications)
- Hubble / Webb — hubblesite.org, webbtelescope.org
- NOAA Ocean Exploration — oceanexplorer.noaa.gov
- ESA/Hubble — CC BY 4.0, credit line required
- Fonts — fonts.google.com (Open Font License)

**Wikimedia Commons is mixed.** Check each file's licence and take only public domain / CC0. CC BY-SA files will get the channel a strike.

Never: film or anime footage, band photos, music, or stock you haven't licensed.

## Fact-checking

The one step that shouldn't be automated. Every claim goes back to a primary source — the study, the NOAA page, the NASA release — not a listicle. Popular versions of facts are frequently wrong in a specific way: they quote the ceiling of a range as the estimate, or call a data sonification a recording. Those gaps make better videos than the myths do.

## Publishing

Upload, set the title/description from the pack, attach the `.srt`, pin the first comment, and use YouTube's own scheduler to spread the batch across Mon/Wed/Fri. Cross-post the identical file to TikTok, Reels and Facebook Reels — same video, different hashtags.
