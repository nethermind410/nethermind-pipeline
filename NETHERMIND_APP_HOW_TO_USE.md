# Nethermind App — What You Asked

## "How am I supposed to work the system?"

You don't need an idea or creator upfront. The system runs itself — it just needs a video source to process.

### Start it:
```bash
cd /Users/courtneyblyde/nethermind-pipeline/clipping-farm
.venv/bin/python -m clipping_farm.nethermind_app --port 8765
```

Then open `http://127.0.0.1:8765`

### What you see:
- Brain regions: Trending → Script → Referator → Approval → Production → QC → Brain
- Synapse nodes pulse when work is happening
- Stats: assets, jobs, pipelines, brain events, patterns, approvals
- Run Pipeline: paste a source_id and title → full cycle runs
- Research Creator: paste a transcript → brain extracts patterns

### The system is delivering:
- Content pipeline: source → transcript → analysis → script → approval → production → QC
- Learning brain: records what works, improves over time
- Creator research: studies creators, extracts patterns
- Quality control: automated checks before you approve

### Mr Beast would use it for:
- Ideation — trending topics → script ideas
- Scripting — fast drafts to refine
- QC — automated checks before approval
- Learning — brain improves what works

Not for: full video production, publishing (human decides), analytics (needs real data)

## Live Dashboard

The dashboard is at `http://127.0.0.1:8765` — synaptic brain view, dark, Apple-like. Auto-refreshes every 3 seconds.

### Current state:
- 9 assets in the system
- 172 jobs processed (all complete)
- 77 artifacts built
- 59 workers registered
- 3454 events recorded
- 0 approvals pending
- 379 tests passing

The brain floor is working. Want me to wire up a real video source and run a full pipeline?