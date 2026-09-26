# Setup

The pipeline narrates with **Kokoro** — free, self-hosted, no API key, voice
`am_liam` — and generates its visuals for character-adjacent topics with
**Gemini** (`gemini-3.1-flash-image`, aka Nano Banana 2). That means one paid
API key (Gemini, and only for hero-config art) instead of two; narration is
free again. `tts_elevenlabs.py` still exists as an optional fallback backend
if Kokoro ever needs to be swapped out, but nothing calls it by default.

## Install

```bash
brew install ffmpeg espeak-ng
python3 -m pip install --break-system-packages numpy pillow kokoro-onnx soundfile google-genai python-dotenv elevenlabs

# Kokoro model files (~200MB total), one-time download into this folder:
curl -L -o kokoro-v1.0.fp16.onnx \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx
curl -L -o voices-v1.0.bin \
    https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

(`elevenlabs` is only needed if `tts_elevenlabs.py`'s optional fallback path is used.)

## API keys

Fill in `.env` (already scaffolded in this folder) with:

```
GEMINI_API_KEY=...       # aistudio.google.com/apikey

# Optional — only used if tts_elevenlabs.py's fallback path is called instead of Kokoro:
ELEVENLABS_API_KEY=...   # elevenlabs.io -> Settings -> API Keys
ELEVENLABS_VOICE_ID=...  # elevenlabs.io -> Voices -> pick one -> copy its ID
```

Kokoro needs no key — it's set in code (`tts_kokoro.py`, default voice `am_liam`),
overridable with the `KOKORO_VOICE` env var if a different voice is ever wanted.

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
  tts_kokoro.py       Kokoro narration backend (free, self-hosted; default)
  tts_elevenlabs.py   ElevenLabs narration backend — optional fallback, not used by default
  gen_visuals.py      Gemini image generation for "kb" segments with a "prompt"
  new_video.py        scaffolds a new config (fact / iceberg / creature / hero)
  fetch_assets.sh     re-downloads public-domain NASA/NOAA assets, safe to re-run
  runall.sh           renders every config in cfg/
  .env                your API keys — gitignored, never committed (this folder IS a git repo now: github.com/nethermind410/nethermind-pipeline)
  README.md           how it works, the format rules, what's licence-safe
  TOPICS.md           the backlog — topics with sources to verify against
  cfg/                video configs
```

## Buyer install (the packaged Nether.app)

1. Drag **Nether** from the .dmg to Applications.
2. Install the tools once, in Terminal:
   ```bash
   brew install ffmpeg espeak-ng python@3.12
   python3.12 -m venv ~/Library/Application\ Support/Nether/venv
   ~/Library/Application\ Support/Nether/venv/bin/pip install -r /Applications/Nether.app/Contents/Resources/app/requirements.txt pywebview
   cd ~/Library/Application\ Support/Nether/Channel 2>/dev/null || mkdir -p ~/Library/Application\ Support/Nether/Channel && cd "$_"
   curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx
   curl -L -O https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
   ```
3. Open Nether. The setup walks you through your channel and keys (or explore the demo first).
4. Fonts for the renderer: `cd` into the channel folder and run `/Applications/Nether.app/Contents/Resources/app/fetch_assets.sh`.

Your data lives in `~/Library/Application Support/Nether/Channel`; the app never writes inside itself.
