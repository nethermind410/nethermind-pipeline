# Nethermind App — Brain Floor View (Build)

## Visual Concept: Synaptic Brain, Not Office Floor

You said: "nether mind is a brain that has synapses firing when works going on, different areas of the brain for different departments"

That's the right metaphor. Not an office — a living brain.

### Layout

```
┌─────────────────────────────────────────────────────────┐
│                    🧠 NETHERMIND                         │
│         [trending]  [script]  [refer]  [approve]         │
│         [produce]   [qc]      [export]  [brain]          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─ TRENDING ──────────────────────────────────┐       │
│   │  ⚡ ACTIVE                                   │       │
│   │  ┌──┐ ┌──┐ ┌──┐  ← synapse nodes firing     │       │
│   │  │██│ │██│ │██│  hot items being processed   │       │
│   │  └──┘ └──┘ └──┘                             │       │
│   │  3 candidates queued                          │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ SCRIPT ───────────────────────────────────┐       │
│   │  🔄 PROCESSING                              │       │
│   │  ┌──┐ ┌──┐                                   │       │
│   │  │██│ │░░│  ← partial fire, waiting          │       │
│   │  └──┘ └──┘                                   │       │
│   │  1 writing, 1 pending review                  │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ REFERATOR ────────────────────────────────┐       │
│   │  ⚡ ACTIVE                                   │       │
│   │  ┌──┐ ┌──┐ ┌──┐ ┌──┐                        │       │
│   │  │██│ │██│ │██│ │██│  ← all firing          │       │
│   │  └──┘ └──┘ └──┘ └──┘                        │       │
│   │  4 packs built                               │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ APPROVAL ─────────────────────────────────┐       │
│   │  🟡 WAITING                                 │       │
│   │  ┌──┐                                       │       │
│   │  │██│  ← awaiting your click                │       │
│   │  └──┘                                       │       │
│   │  1 script to approve                         │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ PRODUCTION ───────────────────────────────┐       │
│   │  ✅ IDLE                                     │       │
│   │  ┌──┐ ┌──┐                                   │       │
│   │  │░░│ │░░│  ← resting, ready                 │       │
│   │  └──┘ └──┘                                   │       │
│   │  0 clips rendering                            │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ QC ───────────────────────────────────────┐       │
│   │  ✅ IDLE                                     │       │
│   │  ┌──┐                                       │       │
│   │  │░░│  ← ready to check                      │       │
│   │  └──┘                                       │       │
│   │  0 checks done                               │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
│   ┌─ BRAIN ────────────────────────────────────┐       │
│   │  💡 LEARNING                                │       │
│   │  ┌──┐ ┌──┐ ┌──┐                             │       │
│   │  │██│ │██│ │░░│  ← 2 patterns, 1 pending    │       │
│   │  └──┘ └──┘ └──┘                             │       │
│   │  5 events today, 3 recommendations           │       │
│   └──────────────────────────────────────────────┘       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [▶ Run Pipeline]  [🔍 Research Creator]  [✅ Approve]  │
└─────────────────────────────────────────────────────────┘
```

### Synapse Nodes
- Each agent = a brain region
- Active regions glow (pulse animation)
- Connections between regions show work passing
- Firing = work happening, synapse lights up
- Resting = region idle, dim but ready
- Dead = region error, red flash

### Colour Palette (Apple-like)
- Background: #0a0a0a (near black)
- Active synapse: #00ff88 (neon green — firing)
- Processing: #ffaa00 (amber — working)
- Waiting: #00aaff (blue — awaiting you)
- Idle: #333333 (dim — resting)
- Error: #ff3355 (red — something wrong)
- Text: #f5f5f7 (Apple light)
- Muted: #86868b (Apple grey)

### Typography
- Sans: SF Pro / Inter / system sans-serif
- Mono: SF Mono for IDs, hashes, data

### Interactions
- Click a synapse → see details (job, agent, status)
- Click "Run Pipeline" → starts full cycle
- Click "Approve" → approve/reject script inline
- Click "Research" → paste transcript → extract patterns
- Synapses fire when work passes between agents
- Brain regions light up as stages complete

### Auto-Refresh
- Every 3 seconds (faster than 5s — brain-like responsiveness)
- Smooth transitions between states
- No page reload — DOM updates only

## What the System Delivers (Mr Beast Analysis)

Mr Beast's content pipeline:
1. **Idea generation** — trending topics, hooks, formats
2. **Script writing** — strong hooks, pacing, payoffs
3. **Production** — filming, editing, graphics
4. **QC** — quality check before publish
5. **Publishing** — upload, SEO, thumbnails
6. **Analytics** — learn what works, iterate

Our system covers 1-5 (content creation pipeline). What's missing for Mr Beast:
- **Analytics learning** — we have the brain but need to feed it real data
- **Publishing** — no YouTube upload capability (and shouldn't — human decides)
- **Thumbnail generation** — visual content creation

**Would Mr Beast use this?**
- For ideation: yes — he'd feed it trending videos and get script ideas
- For scripting: yes — fast draft scripts to refine
- For production: partially — clips, moments, but not full edit
- For QC: yes — automated checks before he approves
- The brain: yes — learning what works over time

**The system is good for:**
- Fast content iteration
- Learning from patterns
- Quality control before publish
- Researching creators and trends

**The system is NOT for:**
- Full video production (filming, editing)
- Publishing (human decision)
- Analytics (needs real data)

## Next Steps

1. Build the brain floor UI (synapse nodes, regions, connections)
2. Wire up real data from the Clipping Farm
3. Add inline approve/reject
4. Add pipeline run button
5. Test with a real video source

## Open Questions

1. Colour — neon green for active or different?
2. Synapse animation — pulse or glow?
3. Layout — brain regions top-to-bottom or spatial?
4. Creator research — paste transcript or URL?
5. Approval — inline or separate?
6. Refresh — 3s or manual?