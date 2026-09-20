# Content Pipeline

A factory for faceless, fact-checked YouTube Shorts. One JSON config in, one finished MP4 + SRT out. Narration is ElevenLabs TTS; visuals are either public-domain NASA/NOAA/ESA media or, for topics with no public-domain source (e.g. superhero trivia), original AI-generated art from Gemini. Fonts are open-licence, and the score is synthesised from scratch. Needs an ElevenLabs and a Gemini API key (see SETUP.md) — this is no longer a free pipeline.

## Make a video

```bash
cd ~/Movies/Content-Pipeline

python3 new_video.py fact my_topic        # scaffold a config
#   ... edit cfg/my_topic.json: the text, the image names/prompts, the hook ...
python3 gen_visuals.py cfg/my_topic.json  # only needed for "kb" images with a "prompt"
python3 make_short.py cfg/my_topic.json
```

Out comes `out/my_topic.mp4` (1080×1920, ~30–45s) and `out/my_topic.srt`. Takes about 2–3 minutes plus generation time. `./runall.sh` rebuilds every config in `cfg/`.

Four scaffolds: `fact` (narrated story, public-domain or generated stills), `ice` (iceberg chart — needs no media at all, the chart is drawn in code), `creature` (animal reveal), `hero` (superhero trivia — Gemini-generated art only, see "Visuals" below).

## What's in here

```
make_short.py      the factory — TTS, captions, visuals, score, mix, subtitles
tts_elevenlabs.py  ElevenLabs narration backend (audio + word-level timings)
gen_visuals.py     Gemini image generation for "kb" segments with a "prompt"
fetch_real.py      Wikimedia Commons PD/CC0 photo fetch for "kb" segments with a "real"
new_video.py       scaffolds a new config so you never start blank
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
