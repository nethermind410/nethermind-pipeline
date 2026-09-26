# Nether — a studio of agents for one faceless YouTube channel

Nether runs a fact-checked Shorts channel on your Mac. Seven agents — Intelligence, Content, Production, Publishing,
Analytics, Business and Control — scout ideas, research and write scripts, render the video with free narration,
check it, schedule it through Buffer and learn from the numbers. **Nothing is ever posted without you pressing Post.**

> The original install (the Nethermind channel) keeps working exactly as before: its notes are in
> [docs/NETHERMIND.md](docs/NETHERMIND.md), and with no `channel.json` it reads `channel_nethermind.json`.

## Quick start

1. **Try the demo** (no keys, nothing leaves your Mac): open Nether and choose *Explore the demo first*, or
   `python3 app.py --demo`. A band across the top and a "Demo data" mark on every page say it's a sample channel.
2. **Set up your channel**: the first launch walks you through it — name, lanes (the topics you cover), narration voice,
   then your own keys one at a time, each tested as you go. You land on the brain.
3. **Make a video**: Intelligence → scout an idea, or Content → Make. Read the draft, approve it, review the render,
   press Post.

## What you need

| | Why | Cost |
|---|---|---|
| A Mac (macOS 12+), Python 3.12+, ffmpeg | the app and the renderer | free |
| Claude Code (your Claude subscription) **or** an Anthropic API key | research and scripts | your plan / pay per use |
| YouTube Data API key (optional) | true views, subscribers, comments | free quota |
| Buffer account + API key (optional) | scheduling to YouTube, TikTok, Instagram | Buffer's plans |
| Cloudflare R2 (optional) | a public link Buffer fetches each video from | small |
| Cloudflare Workers AI (optional) | original art where no public-domain photo exists | free tier |

You bring every key. They're saved only in `.env` inside your data folder (readable by you alone) and sent only to
the service they belong to. Nether has no server of its own and collects nothing.

## Where things live

| | |
|---|---|
| The app's code | `Nether.app/Contents/Resources/app` (read-only) |
| Your channel | `~/Library/Application Support/Nether/Channel` — `channel.json`, `.env`, `cfg/`, `packaging/`, `out/` |
| The demo | `~/Library/Application Support/Nether/Demo` |

Running from source: every module reads its folders through `channel.py`. `NETHER_DATA=<folder>` points the whole
app (server, build.sh, post.sh, daily run) at another data folder; without it, data lives next to the code.
`channel.example.json` shows every setting.

## Everyday commands (from source)

```bash
NETHER_DATA=~/MyChannel .venv/bin/python studio.py      # the app in a browser (127.0.0.1:8766, STUDIO_PORT to change)
.venv/bin/python demo_data.py ~/NetherDemo               # build the sample channel
NETHER_DATA=~/MyChannel ./build.sh <id>                  # render one video
NETHER_DATA=~/MyChannel ./post.sh <id>                   # dry run of what would post (add --live to queue it)
.venv/bin/python selftest.py                             # is everything working? plain-English fixes
./package.sh                                             # dist/Nether.app + .dmg (see docs/PRODUCT.md first)
```

See [SETUP.md](SETUP.md) for installing, and [LICENSE](LICENSE) for the terms.
