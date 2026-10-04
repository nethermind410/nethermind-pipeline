# Nethermind App — Brain Floor (Built)

## What's Delivered

The brain floor dashboard is live at `http://127.0.0.1:8765`.

### Visual
- Synaptic brain metaphor — regions fire when work passes through
- Neon green active, amber processing, blue waiting, dim idle, red error
- Apple-like: near-black background, clean typography, spacious cards
- Pulse animation on active synapses
- Auto-refresh every 3 seconds

### Functionality
- **Brain Stats** — assets, jobs, pipelines, brain events, patterns, pending approvals
- **7 Brain Regions** — Trending, Script, Referator, Approval, Production, QC, Brain
- **Synapse Nodes** — visual firing state per region
- **Run Pipeline** — source + title → full cycle
- **Research Creator** — paste transcript → extract patterns
- **Refresh** — manual brain refresh

### What the System Delivers (Mr Beast Test)

Mr Beast's pipeline: idea → script → produce → QC → publish → analytics

Our system covers 1-5. Missing: analytics (needs real data), publishing (human decides), thumbnails.

**Would Mr Beast use this?**
- Ideation: yes — trending videos → script ideas
- Scripting: yes — fast drafts to refine
- Production: partially — clips/moments, not full edit
- QC: yes — automated checks before approval
- Brain: yes — learning what works over time

### System State (verified)
- 9 assets, 172 jobs, 77 artifacts
- 59 workers registered, 5 with full capabilities
- 3454 events recorded
- 0 creator patterns (needs research)
- 0 approvals pending
- 379 tests passing

### How to Run
```bash
cd /Users/courtneyblyde/nethermind-pipeline/clipping-farm
.venv/bin/python -m clipping_farm.nethermind_app --port 8765
```

Then open `http://127.0.0.1:8765`

### Files
- `clipping_farm/nethermind_app.py` — dashboard server (280 lines)
- `NETHERMIND_APP_BRAIN_FLOOR.md` — design doc
- `NETHERMIND_APP_DESIGN.md` — earlier design
- `NETHERMIND_APP_PLAN.md` — original plan