# Selling Nether — a proposal for Courtney to decide on

Nothing here is decided or built in (no payments, no licence checks). It's the shape of the offer, the options, and
what has to be true before the first sale.

## Who it's for

Solo creators running (or starting) a **faceless, fact-driven Shorts channel** — science, history, nature, "the true
story behind…" — who are comfortable installing a Mac app with a few tools, and want a system that does the grind
(ideas, research, scripts, render, QA, scheduling, numbers) while they stay the editor who approves every video.
Not for: people who want fully automatic posting, Windows users, or channels built on film/TV footage.

## What's in the box

- **The app** — the brain, seven agents, Today, Videos, Calendar, Performance, Ideas, Comments, Money, Settings.
- **The pipeline** — research with sources → script → free on-device narration (Kokoro) → render → TikTok cut → QA
  contact sheet → thumbnail → Buffer scheduling → true numbers → a learning loop that re-weights the idea scouts.
- **First-run setup** — name, lanes, voice, keys (each tested), then the brain. **A demo channel** to explore first.
- **Docs** — README quick start, SETUP buyer install, the house retention rules.
- Buyers bring their own keys and accounts. Nether ships with no keys and no server.

## Pricing options (pick one, or one + an add-on)

| | How it works | For | Against |
|---|---|---|---|
| **A. One-off licence** (e.g. £149–£249) | Pay once, own that version; paid major upgrades | Simplest to sell and explain; no billing system; fits "local app, your keys" | Revenue stops after launch; support cost continues; updates are harder to fund |
| **B. Subscription** (e.g. £15–£25/month or £150/year) | Updates + support while subscribed | Recurring revenue funds fixes as YouTube/Buffer APIs change (they do) | Needs licence checks + a billing provider (Paddle/Lemon Squeezy handle VAT); buyers resent subscriptions for local apps; churn |
| **C. Done-for-you setup** (e.g. £400–£900 once) | You install it on their Mac, set lanes/voice/keys, first 3 videos together | Highest value per sale; no packaging polish needed to start; you learn what buyers need | Your time doesn't scale; screen-share access to their Mac and accounts needs care (they type their own keys) |

A sensible path: **start with C for 3–5 people** (validates demand, finds install pain), then launch **A** with a year
of updates, and add **B-style "update plan"** renewals later if updates keep coming.

## Before selling — must change (legal)

- **Licence text**: `LICENSE` is a placeholder (all rights reserved). Choose the real EULA — number of Macs/channels,
  refunds, no warranty, liability cap. Get it checked once by a lawyer, especially the liability cap.
- **Business**: sole-trader/company registration, VAT/sales tax on digital goods (a merchant-of-record like Paddle or
  Lemon Squeezy collects EU/UK VAT for you).
- **API terms — the buyer is the developer of record for their own keys**:
  - *YouTube Data API*: each buyer creates their own Google Cloud project and key; the app must show YouTube data
    in line with the YouTube API Services Terms and Developer Policies (no storing beyond what's allowed, attribution,
    refresh/delete rules). Nether stores snapshots in `out/youtube.json` — review the 30-day data-refresh rule and add a
    purge if needed. Don't market it as "YouTube-approved".
  - *Buffer*: buyers use their own Buffer account and API key under Buffer's terms; check Buffer allows third-party
    tools built on personal API keys to be resold (their public API has been in flux).
  - *Anthropic*: buyers use their own Claude subscription (Claude Code) or their own API key under Anthropic's
    Consumer/Commercial Terms and Usage Policy. Don't resell or share access; don't ship a key. Confirm running
    Claude Code headless (`claude -p`) from a sold product is within the subscription's terms for the buyer's plan.
  - *Cloudflare, Kokoro, fonts*: Kokoro model is Apache-2.0 (keep its notice); fonts are OFL; third-party
    licences are listed in `THIRD_PARTY_NOTICES.md`.
  - *espeak-ng*: Kokoro's phonemizer needs it, and it's **GPLv3** — a licence Nether itself doesn't ship under.
    It must stay a separate system install the buyer does themselves (`apt install espeak-ng` / `brew install
    espeak-ng`, see `SETUP.md`), never bundled inside the `.app`/`.dmg`; `package.sh` now refuses to package
    if an espeak-ng binary or its data slips in. Don't bundle it without redoing the licence math first.
- **Content rights**: the app's guidance (public-domain media only, original AI art for characters, cite sources) is
  guidance, not a guarantee — say so plainly in the EULA and README. vidIQ scoring uses Courtney's vidIQ connector:
  remove or make it bring-your-own before selling.
- **Privacy**: Nether collects nothing and has no server; say that in a short privacy notice. If you add analytics,
  crash reports or licence checks later, that notice must change (UK GDPR).

## Platform policy

Plain rules, not legalese — what the app actually does to stay inside YouTube's, TikTok's and Instagram's own
policies, and what stays the buyer's job:

- **Reused/inauthentic content**: every video is written from its own sourced research (each fact carries a
  source), the narration and beats are original to that script, and repeated images are reframed rather than
  looped verbatim. A buyer who instead points the drafter at someone else's script or footage is outside what
  this checklist covers — YouTube's reused-content policy is about the buyer's judgement, not a box the app
  can tick for them.
- **AI disclosure**: narration is always text-to-speech and some visuals are AI-generated art, so every video
  carries a `synthetic_disclosure` flag (on by default) that (a) tells Buffer to mark the post as AI-generated
  on every platform that accepts the flag, and (b) is a step in the finish checklist reminding the buyer to
  tick "Altered or synthetic content" in YouTube Studio — because YouTube's own toggle isn't exposed by any
  public API, so it can't be set from here automatically.
- **Human approval before every post**: nothing renders without an approved script, and nothing posts without
  the buyer opening the review page and pressing Schedule/Post themselves — there is no unattended posting
  path, by design, however the app is configured.
- **No mass accounts**: the app manages exactly one channel's three platform accounts (YouTube, TikTok,
  Instagram) through the buyer's own Buffer login. It has no feature for operating multiple channels, sock
  puppets, or bulk-created accounts, and buyers should not use it that way.
- **Trademarked characters**: AI art and thumbnail text are checked against a block list of trademarked
  character names and studio marks (`channel.py` → `BLOCKED_NAMES`, extendable per channel) — AI art may only
  depict an archetype (pose/palette), never a named character, costume or logo. Narration may still mention a
  real character by name; that's commentary, not the depiction the block list targets.

## Before selling — must change (technical)

- [x] Channel settings are config (`channel.json`), not code; the original install falls back to `channel_nethermind.json`.
- [x] No bundled secrets; keys are written only to the buyer's `.env` (0600), never echoed back.
- [x] `package.sh` builds from tracked code only and refuses if personal files/ids slip in.
- [ ] **Self-contained Python**: the .app currently needs the buyer to create a venv (SETUP.md). Bundle a relocatable
      Python (python-build-standalone) + wheels so it opens with no Terminal step.
- [ ] **Voice files and fonts** download into the data folder on first run (today: manual steps in SETUP.md).
- [ ] **Code signing + notarisation** (needs Courtney's Apple Developer account, $99/year):
  1. Create a *Developer ID Application* certificate in Xcode → Settings → Accounts.
  2. `SIGN_ID="Developer ID Application: … (TEAMID)" ./package.sh` (signs app with hardened runtime, then the dmg).
     A bundled Python needs every `.so`/`.dylib` signed too, plus entitlements for `allow-unsigned-executable-memory`
     if a dependency needs it.
  3. `xcrun notarytool store-credentials nether --apple-id … --team-id …` (app-specific password).
  4. `xcrun notarytool submit dist/Nether-1.0.dmg --keychain-profile nether --wait`
  5. `xcrun stapler staple dist/Nether-1.0.dmg`, then test on a clean Mac/user account with Gatekeeper on.
- [ ] Icon/name: the bundle uses the Nethermind icon file; commission a Nether icon.
- [ ] Remove Courtney-specific leftovers still in UI files owned by other work (brain title text, Jarvis ⌘K wording,
      the dashboard link in `app.js` is scrubbed by package.sh) — `ext_setup.js` renames them at runtime for now.
- [ ] Update path: a version check (read-only, no tracking) or "download the new .dmg" emails.
- [ ] Support: an email, a known-issues page, and a way for buyers to send `selftest.py` output.
