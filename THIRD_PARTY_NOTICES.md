# Third-party notices

Nether is built on the open-source and freely-licensed components below. This file lists them and their
licences so a buyer can see what they're agreeing to when they install and run the app. It does not replace
reading each project's own licence text (linked below); when in doubt, that text governs.

None of these components are modified beyond ordinary use through their documented APIs, unless noted.

## Bundled with, or downloaded by, the app

| Component | Licence | Notes |
|---|---|---|
| [Kokoro](https://github.com/hexgrad/kokoro) (`kokoro-onnx`, model weights) | Apache License 2.0 | Narration voice. Model files (~200MB) are downloaded once by the buyer, not shipped in the app bundle — see `tts_kokoro.py` and `SETUP.md`. |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) | **GNU GPL v3** | A runtime dependency of Kokoro's phonemizer, installed as a **system package** (`apt install espeak-ng` / `brew install espeak-ng`) — **never bundled** with the app or copied into the `.app`/`.dmg`. `package.sh` explicitly excludes any espeak-ng binaries or the `espeakng-loader` cache from what it packages, so the GPL's copyleft terms never attach to Nether's own (non-GPL) code. See `docs/PRODUCT.md` → "Platform policy" for the buyer-install step. |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD 3-Clause | The native window around Studio (`app.py`). |
| [PyObjC](https://github.com/ronaldoussoren/pyobjc) (`pyobjc-core`, `Cocoa`, `Quartz`, `Security`, `UniformTypeIdentifiers`, `WebKit`) | MIT | macOS bindings pywebview uses on this platform. |
| Anton, Bebas Neue (Google Fonts, fetched by `fetch_assets.sh`) | SIL Open Font License 1.1 | Caption/title fonts. Downloaded on first run, not shipped in the repo. |
| [Pillow](https://python-pillow.org/) | MIT-CMU (the "Pillow" / historical "PIL" licence) | Image compositing (`make_short.py`, `qa_render.py`). |
| [NumPy](https://numpy.org/) | BSD 3-Clause | Numeric helpers for the renderer. |
| [soundfile](https://github.com/bastibe/python-soundfile) | BSD 3-Clause | Reads/writes the narration `.wav`. |
| [requests](https://requests.readthedocs.io/) | Apache License 2.0 | HTTP client (Buffer, Wikimedia, YouTube Data API, etc.). |
| [boto3](https://github.com/boto/boto3) | Apache License 2.0 | Cloudflare R2 upload (S3-compatible API) for video hosting before a Buffer post. |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD 3-Clause | Reads `.env` for API keys. |
| [ffmpeg](https://ffmpeg.org/) | **LGPL v2.1+, or GPL v2+/v3+ depending on build configuration** | Required on the buyer's Mac (`brew install ffmpeg`), **not bundled**. A stock Homebrew build is typically LGPL; a build with extra encoders enabled can be GPL — buyers who build ffmpeg themselves should check `ffmpeg -version`'s configuration line if this matters to them. Nether only calls the `ffmpeg`/`ffprobe` binaries as external processes; it does not link against ffmpeg's libraries. |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) (`anthropic`, optional) | MIT | Only used if the buyer opts into the "Anthropic API key" engine in Control → AI engines. |

## Used via their own hosted service, not bundled

- **Claude Code** / the buyer's Claude subscription — used headless (`claude -p`) for drafting; governed by Anthropic's own Consumer/Commercial Terms, not by this notice.
- **Wikimedia Commons** — real-photo search/fetch (`fetch_real.py`); images are filtered to Public Domain / CC0 / plain CC BY (never CC BY-SA or CC BY-NC), and every CC BY image gets an automatic attribution line in the video's YouTube description (see `apply_credits` in `fetch_real.py`).
- **YouTube Data API**, **Buffer API**, **Cloudflare R2**, **vidIQ** — each buyer connects their own account/key under that provider's own terms; Nether stores no shared credentials.

## What this means in practice for a buyer

- Installing Nether does **not** install espeak-ng or ffmpeg for you — that's a deliberate, separate step
  (`SETUP.md`) so their GPL/LGPL terms never become part of what you receive when you buy Nether.
- Keep this file, and each component's own licence notice where required (Apache-2.0 and the SIL OFL both ask
  for the notice to travel with redistributed copies), if you resell or redistribute the app.
- This file is informational, not legal advice — have a lawyer check it once before selling, per `docs/PRODUCT.md`.
