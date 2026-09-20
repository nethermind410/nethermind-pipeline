# Setup

The pipeline now narrates with **ElevenLabs** and generates its visuals for
character-adjacent topics with **Gemini** (`gemini-3.1-flash-image`, aka Nano
Banana 2), instead of the earlier free edge-tts + public-domain-only setup.
That means two API keys and a small cost per video — no more free rendering.

## Install

```bash
brew install ffmpeg
python3 -m pip install --break-system-packages numpy pillow elevenlabs google-genai python-dotenv
```

## API keys

Fill in `.env` (already scaffolded in this folder) with:

```
ELEVENLABS_API_KEY=...   # elevenlabs.io -> Settings -> API Keys
ELEVENLABS_VOICE_ID=...  # elevenlabs.io -> Voices -> pick one -> copy its ID
GEMINI_API_KEY=...       # aistudio.google.com/apikey
```

## Make a video

```bash
python3 new_video.py hero my_topic        # or: fact / ice / creature
#   ... edit cfg/my_topic.json: text, hook, image prompts ...
python3 gen_visuals.py cfg/my_topic.json  # generates any "kb" images that have a "prompt" and don't exist yet
python3 make_short.py cfg/my_topic.json
```

`fact`/`creature` configs can still point "kb" images at real public-domain
photos fetched by `./fetch_assets.sh` (space/ocean topics) — `prompt` on a
segment is only used if you actually run `gen_visuals.py` on it. `hero`
configs (superhero trivia) have no public-domain path, so every image needs
a `prompt` and a `gen_visuals.py` run.

## What's installed

```
~/Movies/Content-Pipeline/
  make_short.py      the factory — TTS, captions, visuals, score, mix, subtitles
  tts_elevenlabs.py  ElevenLabs narration backend (audio + word timings)
  gen_visuals.py      Gemini image generation for "kb" segments with a "prompt"
  new_video.py        scaffolds a new config (fact / iceberg / creature / hero)
  fetch_assets.sh     re-downloads public-domain NASA/NOAA assets, safe to re-run
  runall.sh           renders every config in cfg/
  .env                your API keys (not committed anywhere — this folder isn't a git repo)
  README.md           how it works, the format rules, what's licence-safe
  TOPICS.md           the backlog — topics with sources to verify against
  cfg/                video configs
```
