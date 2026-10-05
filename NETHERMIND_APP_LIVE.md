# Nethermind App — Brain Floor (Live)

## Status

Dashboard running at `http://127.0.0.1:8765`

### What's working
- Brain floor view: 7 regions (Trending, Script, Referator, Approval, Production, QC, Brain)
- Synapse nodes pulse when active
- Auto-refresh every 3s
- Run Pipeline button (source + title)
- Research Creator button (paste transcript)
- Stats: assets, jobs, pipelines, events, patterns, approvals

### Current state
- 0 assets, 1 job, 0 approvals
- Fresh start — ready for a real video source

### How to run
```bash
cd /Users/courtneyblyde/nethermind-pipeline/clipping-farm
.venv/bin/python -m clipping_farm.nethermind_app --port 8765
```

Then open `http://127.0.0.1:8765`

### Next step
Wire up a real video source and run a full pipeline through the brain.