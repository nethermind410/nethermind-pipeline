# Nethermind App — Vision & Plan

## What You Want
A visual, live dashboard showing the Clipping Farm system working — departments, agents, processes — sort of like a factory floor view. ADHD-friendly, visual, easy to operate the business.

## What Exists
- HUD (`hud.py`): local web server, shows pipeline status for a source/run
- Kanban board: task tracking
- Agent system: trending → script → pack → approval → production
- Content Lab: production objects with provenance

## What Needs to Be Built
A proper **Nethermind App** — a live visual dashboard showing:

### Departments / Agents
- Trending (discovery)
- Script Writer (scripting)
- Content Referencer (packaging)
- Approval Gate (human review)
- Production (rendering)
- QC (quality check)
- Learning Brain (advisory)
- Creator Research (pattern extraction)

### Live View
- Pipeline status: PENDING → CLAIMED → RUNNING → COMPLETE
- Agent status: IDLE / ACTIVE / ERROR / OFFLINE
- Job queue: what's running, what's waiting
- Rights state: AUTHORISED / PENDING / REJECTED
- Creator patterns: hook/storytelling/narration/visual/educational/humour/retention
- Quality scores: candidate scores, QC results
- Budget tracking: estimated vs actual cost

### Controls
- Start pipeline (source → full run)
- Approve/reject scripts
- Cancel running jobs
- View production objects
- Research creators

## Technical Approach
The HUD is a simple HTTP server. The Nethermind App should be a proper web app:
- Backend: existing Clipping Farm API (Hermes adapter + DB)
- Frontend: simple web UI showing the factory floor
- Live updates: poll or WebSocket for real-time status
- Visual: cards per agent, progress bars, status indicators

## Next Steps
1. Build the Nethermind App frontend (simple HTML/JS)
2. Wire it to the existing API (Hermes adapter + DB)
3. Make it live-updating
4. Test end-to-end

## Priority
High — this is the main way you'll interact with the system day-to-day.

## Estimated Effort
1-2 days for a basic working dashboard.