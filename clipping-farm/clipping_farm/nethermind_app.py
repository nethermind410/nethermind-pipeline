"""Nethermind App — Brain Floor Dashboard.

Synaptic brain view: regions fire when work passes through.
Dark, spacious, Apple-like aesthetic.

Backend: existing Clipping Farm API (Hermes adapter + DB).
Frontend: HTML/JS with synapse-node visualisation.
"""
import json, time, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from clipping_farm.db import DB
from clipping_farm.system_manifest import SystemManifest
from clipping_farm.capability_registry import CapabilityRegistry
from clipping_farm.preflight import PreflightGate
from clipping_farm.creator_researcher import CreatorResearcherAgent
from clipping_farm.learning_brain import LearningBrain
from clipping_farm.automation import AutomationEngine
from clipping_farm.hermes_adapter import HermesAdapter


# ─── HTML Dashboard ──────────────────────────────────

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nethermind — Brain Floor</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'SF Pro', 'Inter', sans-serif; background: #0a0a0a; color: #f5f5f7; padding: 20px; min-height: 100vh; }
h1 { color: #00ff88; margin-bottom: 4px; font-weight: 700; font-size: 1.8em; letter-spacing: -0.5px; }
.subtitle { color: #86868b; font-size: 0.9em; margin-bottom: 20px; }
.brain-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.region { background: #141414; border: 1px solid #222; border-radius: 12px; padding: 16px; position: relative; overflow: hidden; transition: border-color 0.3s, box-shadow 0.3s; }
.region.active { border-color: #00ff88; box-shadow: 0 0 20px rgba(0,255,136,0.15); }
.region.processing { border-color: #ffaa00; box-shadow: 0 0 20px rgba(255,170,0,0.15); }
.region.waiting { border-color: #00aaff; box-shadow: 0 0 20px rgba(0,170,255,0.15); }
.region.idle { border-color: #222; }
.region.error { border-color: #ff3355; box-shadow: 0 0 20px rgba(255,51,85,0.15); }
.region-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.region-name { font-size: 0.85em; color: #86868b; text-transform: uppercase; letter-spacing: 1px; }
.region-status { font-size: 0.75em; padding: 3px 10px; border-radius: 10px; font-weight: 600; }
.status-active { background: #00ff8822; color: #00ff88; }
.status-processing { background: #ffaa0022; color: #ffaa00; }
.status-waiting { background: #00aaff22; color: #00aaff; }
.status-idle { background: #33333322; color: #666; }
.status-error { background: #ff335522; color: #ff3355; }
.synapses { display: flex; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
.synapse { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.7em; font-weight: 700; transition: all 0.3s; cursor: pointer; position: relative; }
.synapse.active { background: #00ff8833; color: #00ff88; border: 2px solid #00ff88; animation: pulse 1.5s infinite; }
.synapse.processing { background: #ffaa0033; color: #ffaa00; border: 2px solid #ffaa00; animation: pulse 0.8s infinite; }
.synapse.waiting { background: #00aaff33; color: #00aaff; border: 2px solid #00aaff; }
.synapse.idle { background: #222; color: #555; border: 2px solid #333; }
.synapse.error { background: #ff335533; color: #ff3355; border: 2px solid #ff3355; }
@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.1); opacity: 0.7; } }
.synapse-label { font-size: 0.65em; color: #86868b; text-align: center; margin-top: 4px; }
.region-detail { font-size: 0.8em; color: #86868b; margin-top: 8px; }
.region-detail p { margin: 2px 0; }
.conn { position: absolute; top: 50%; left: 0; right: 0; height: 2px; background: #222; z-index: 0; }
.conn.firing { background: #00ff88; animation: flash 0.5s; }
@keyframes flash { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
.brain-stats { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { background: #141414; border: 1px solid #222; border-radius: 10px; padding: 14px 20px; min-width: 140px; }
.stat-value { font-size: 1.8em; font-weight: 700; color: #00ff88; }
.stat-label { font-size: 0.75em; color: #86868b; text-transform: uppercase; letter-spacing: 0.5px; }
.actions { display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }
.btn { background: #00ff88; color: #0a0a0a; border: none; padding: 10px 20px; border-radius: 8px; font-size: 0.9em; font-weight: 600; cursor: pointer; transition: background 0.2s; }
.btn:hover { background: #00cc6a; }
.btn.secondary { background: #222; color: #f5f5f7; border: 1px solid #333; }
.btn.secondary:hover { background: #333; }
.btn.danger { background: #ff3355; color: #fff; }
.btn.danger:hover { background: #cc2944; }
.btn.small { padding: 6px 12px; font-size: 0.8em; }
.approval-item { background: #1a1a1a; border: 1px solid #00aaff33; border-radius: 8px; padding: 12px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center; }
.approval-actions { display: flex; gap: 8px; }
.pattern-tag { display: inline-block; background: #00ff8822; color: #00ff88; padding: 2px 8px; border-radius: 6px; font-size: 0.75em; margin: 2px; }
.input-field { background: #1a1a1a; color: #f5f5f7; border: 1px solid #333; padding: 8px 12px; border-radius: 8px; font-size: 0.9em; width: 100%; margin-bottom: 8px; }
.input-field:focus { border-color: #00ff88; outline: none; }
.result-box { background: #1a1a1a; border: 1px solid #222; border-radius: 8px; padding: 12px; margin-top: 8px; font-size: 0.85em; color: #86868b; max-height: 200px; overflow-y: auto; }
</style>
</head>
<body>
<h1>🧠 Nethermind</h1>
<p class="subtitle">Brain Floor — synaptic view of all departments and processes</p>

<div id="brain-stats" class="brain-stats"></div>
<div id="brain-regions" class="brain-grid"></div>

<div class="actions">
  <button class="btn" onclick="runPipeline()">▶ Run Pipeline</button>
  <button class="btn secondary" onclick="researchCreator()">🔍 Research Creator</button>
  <button class="btn secondary" onclick="refreshBrain()">🔄 Refresh</button>
</div>

<div id="pipeline-form" style="display:none; margin-top:16px; background:#141414; border:1px solid #222; border-radius:12px; padding:16px; max-width:500px;">
  <h3 style="color:#00ff88; margin-bottom:12px;">Run Pipeline</h3>
  <input class="input-field" id="source-input" placeholder="source_id (e.g. VIDEO_001)">
  <input class="input-field" id="title-input" placeholder="title">
  <div style="display:flex; gap:8px;">
    <button class="btn small" onclick="submitPipeline()">▶ Start</button>
    <button class="btn secondary small" onclick="hidePipelineForm()">Cancel</button>
  </div>
  <div id="pipeline-result" class="result-box" style="display:none; margin-top:8px;"></div>
</div>

<div id="research-form" style="display:none; margin-top:16px; background:#141414; border:1px solid #222; border-radius:12px; padding:16px; max-width:500px;">
  <h3 style="color:#00aaff; margin-bottom:12px;">Research Creator</h3>
  <input class="input-field" id="creator-input" placeholder="creator name">
  <textarea class="input-field" id="transcript-input" placeholder="Paste transcript here..." style="height:80px; resize:vertical;"></textarea>
  <div style="display:flex; gap:8px;">
    <button class="btn small" onclick="submitResearch()">🔍 Research</button>
    <button class="btn secondary small" onclick="hideResearchForm()">Cancel</button>
  </div>
  <div id="research-result" class="result-box" style="display:none; margin-top:8px;"></div>
</div>

<script>
const STATUS_MAP = {
  'IDLE': 'idle', 'ACTIVE': 'active', 'PROCESSING': 'processing',
  'WAITING': 'waiting', 'ERROR': 'error', 'COMPLETE': 'active',
  'PENDING': 'waiting', 'APPROVED': 'active', 'REJECTED': 'error',
  'RUNNING': 'processing', 'CLAIMED': 'processing', 'FINISHED': 'active'
};

function statusClass(status) {
  return STATUS_MAP[status] || 'idle';
}

function statusLabel(status) {
  const labels = {
    'IDLE': 'Idle', 'ACTIVE': 'Firing', 'PROCESSING': 'Processing',
    'WAITING': 'Waiting', 'ERROR': 'Error', 'COMPLETE': 'Complete',
    'PENDING': 'Pending', 'APPROVED': 'Approved', 'REJECTED': 'Rejected',
    'RUNNING': 'Running', 'CLAIMED': 'Claimed', 'FINISHED': 'Finished'
  };
  return labels[status] || status;
}

async function load() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    renderStats(d);
    renderRegions(d);
  } catch(e) { console.error(e); }
  setTimeout(load, 3000);
}

function renderStats(d) {
  const assets = d.db_stats?.total_assets || 0;
  const jobs = d.db_stats?.total_jobs || 0;
  const pipelines = d.pipelines?.length || 0;
  const events = d.brain?.total_events || 0;
  const patterns = d.patterns?.length || 0;
  const approvals = d.approval_stats?.PENDING || 0;

  document.getElementById('brain-stats').innerHTML = `
    <div class="stat-card"><div class="stat-value">${assets}</div><div class="stat-label">Assets</div></div>
    <div class="stat-card"><div class="stat-value">${jobs}</div><div class="stat-label">Jobs</div></div>
    <div class="stat-card"><div class="stat-value">${pipelines}</div><div class="stat-label">Pipelines</div></div>
    <div class="stat-card"><div class="stat-value">${events}</div><div class="stat-label">Brain Events</div></div>
    <div class="stat-card"><div class="stat-value">${patterns}</div><div class="stat-label">Patterns</div></div>
    <div class="stat-card"><div class="stat-value" style="color:${approvals > 0 ? '#ffaa00' : '#00ff88'}">${approvals}</div><div class="stat-label">Pending Approval</div></div>
  `;
}

function renderRegions(d) {
  const regions = [
    { name: 'TRENDING', icon: '⚡', jobs: d.agents?.trending_agent || null, pipelines: d.pipelines?.filter(p => p.current_agent === 'trending_agent') || [] },
    { name: 'SCRIPT', icon: '✍️', jobs: d.agents?.script_agent || null, pipelines: d.pipelines?.filter(p => p.current_agent === 'script_agent') || [] },
    { name: 'REFERATOR', icon: '🔍', jobs: d.agents?.referencer_agent || null, pipelines: d.pipelines?.filter(p => p.current_agent === 'referencer_agent') || [] },
    { name: 'APPROVAL', icon: '✅', jobs: null, approvals: d.approval_stats || {} },
    { name: 'PRODUCTION', icon: '🎬', jobs: d.agents?.production_agent || null, pipelines: d.pipelines?.filter(p => p.current_agent === 'production_agent') || [] },
    { name: 'QC', icon: '🔬', jobs: d.agents?.qc_agent || null, pipelines: d.pipelines?.filter(p => p.current_agent === 'qc_agent') || [] },
    { name: 'BRAIN', icon: '💡', jobs: null, patterns: d.patterns || [], brain: d.brain || {} },
  ];

  const html = regions.map(region => {
    const job = region.jobs;
    const status = job ? statusClass(job.status) : 'idle';
    const label = job ? statusLabel(job.status) : 'Idle';
    const synapseCount = job ? 3 : 2;
    const firingCount = status === 'active' || status === 'processing' ? synapseCount : status === 'waiting' ? 1 : 0;

    let detail = '';
    if (region.pipelines && region.pipelines.length > 0) {
      detail = region.pipelines.map(p => `<p>${p.pipeline_id}: ${p.status}</p>`).join('');
    }
    if (region.approvals && Object.keys(region.approvals).length > 0) {
      detail = Object.entries(region.approvals).map(([k,v]) => `<p>${k}: ${v}</p>`).join('');
    }
    if (region.patterns && region.patterns.length > 0) {
      detail = region.patterns.map(p => `<p>${p.pattern_type}: ${p.creator} (${p.confidence})</p>`).join('');
    }
    if (region.brain && region.brain.total_events) {
      detail = `<p>Events: ${region.brain.total_events}</p><p>Rec: ${region.brain.recommendation || 'pending'}</p>`;
    }

    const synapses = Array.from({length: synapseCount}, (_, i) => {
      const s = i < firingCount ? status : 'idle';
      return `<div style="text-align:center;"><div class="synapse ${s}">${i < firingCount ? '⚡' : '·'}</div><div class="synapse-label">node ${i+1}</div></div>`;
    }).join('');

    return `
      <div class="region ${status}">
        <div class="region-header">
          <span class="region-name">${region.icon} ${region.name}</span>
          <span class="region-status status-${status}">${label}</span>
        </div>
        <div class="synapses">${synapses}</div>
        <div class="region-detail">${detail || '<p>Ready</p>'}</div>
      </div>
    `;
  }).join('');

  document.getElementById('brain-regions').innerHTML = html;
}

async function runPipeline() {
  document.getElementById('pipeline-form').style.display = 'block';
  document.getElementById('research-form').style.display = 'none';
}

function hidePipelineForm() {
  document.getElementById('pipeline-form').style.display = 'none';
}

async function researchCreator() {
  document.getElementById('research-form').style.display = 'block';
  document.getElementById('pipeline-form').style.display = 'none';
}

function hideResearchForm() {
  document.getElementById('research-form').style.display = 'none';
}

async function submitPipeline() {
  const source = document.getElementById('source-input').value;
  const title = document.getElementById('title-input').value;
  const resultDiv = document.getElementById('pipeline-result');
  resultDiv.style.display = 'block';
  resultDiv.textContent = 'Running...';
  try {
    const r = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({source_id:source, title:title})});
    const d = await r.json();
    resultDiv.textContent = JSON.stringify(d, null, 2);
  } catch(e) {
    resultDiv.textContent = 'Error: ' + e.message;
  }
}

async function submitResearch() {
  const creator = document.getElementById('creator-input').value;
  const transcript = document.getElementById('transcript-input').value;
  const resultDiv = document.getElementById('research-result');
  resultDiv.style.display = 'block';
  resultDiv.textContent = 'Researching...';
  try {
    const r = await fetch('/api/research', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({creator, transcript})});
    const d = await r.json();
    resultDiv.textContent = JSON.stringify(d, null, 2);
  } catch(e) {
    resultDiv.textContent = 'Error: ' + e.message;
  }
}

async function refreshBrain() {
  await load();
}

load();
</script>
</body>
</html>"""


# ─── HTTP Handler ────────────────────────────────────────

class NethermindHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Nethermind brain floor dashboard."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/dashboard":
            self._serve_html()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/pipelines":
            self._serve_pipelines()
        elif path == "/api/agents":
            self._serve_agents()
        elif path == "/api/patterns":
            self._serve_patterns()
        elif path == "/api/brain":
            self._serve_brain()
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/run":
            self._handle_run()
        elif path == "/api/research":
            self._handle_research()
        else:
            self._json(404, {"error": "not found"})

    def _serve_html(self):
        self._send(200, DASHBOARD_HTML, "text/html")

    def _serve_status(self):
        """Aggregate system status for the brain floor dashboard."""
        db = self._get_db()
        manifest = SystemManifest(db=db)
        registry = CapabilityRegistry(db=db)
        brain = LearningBrain(db=db)
        researcher = CreatorResearcherAgent(db=db)

        status = {
            "manifest_version": manifest.VERSION,
            "generated_at": time.time(),
            "manifest": manifest.inspect(),
            "registry": registry.inspect(),
            "cap_summary": registry.inspect().get("summary", {}),
            "pipelines": self._get_pipelines(db),
            "agents": self._get_agents(db),
            "patterns": self._get_patterns(researcher),
            "brain": {
                "total_events": len(brain.get_events(limit=1000)),
                "stats": brain.get_stats(),
            },
            "approval_stats": self._get_approval_stats(db),
            "db_stats": self._get_db_stats(db),
        }
        self._json(200, status)

    def _handle_run(self):
        """Run a pipeline."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode())

        db = self._get_db()
        adapter = HermesAdapter(db)
        result = adapter.run_full_cycle(
            data.get("source_id", "test-source"),
            title=data.get("title", ""),
        )
        self._json(200, result)

    def _handle_research(self):
        """Research a creator."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode())

        db = self._get_db()
        agent = CreatorResearcherAgent(db)
        patterns = agent.research_creator(
            data.get("creator", "Unknown"),
            source_url=data.get("source_url", ""),
            transcript=data.get("transcript", ""),
        )
        self._json(200, {
            "creator": data.get("creator"),
            "patterns_found": len(patterns),
            "patterns": [p.__dict__ if hasattr(p, '__dict__') else str(p) for p in patterns],
        })

    def _get_db(self):
        """Get a DB instance."""
        db_path = Path(__file__).parent / "clipping_farm.db"
        return DB(str(db_path))

    def _get_pipelines(self, db):
        """Get recent pipelines."""
        try:
            rows = db.cx.execute(
                "SELECT pipeline_id, status, current_agent, jev_chain, created_at FROM pipelines ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        except Exception:
            return []
        return [
            {
                "pipeline_id": r["pipeline_id"],
                "status": r["status"],
                "current_agent": r["current_agent"],
                "jev_chain": json.loads(r["jev_chain"]) if r["jev_chain"] else [],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def _get_agents(self, db):
        """Get agent statuses."""
        try:
            from clipping_farm.agents.agent_registry import AgentRegistry
            registry = AgentRegistry(db)
            available = registry.available()
            result = {}
            for a in available:
                name = a.name
                status = a.status
                health = a.health
                last_seen = getattr(a, 'last_seen', None)
                uptime = time.time() - last_seen if last_seen else 0
                result[name] = {"status": status, "health": health, "uptime": uptime}
            return result
        except Exception:
            return {}

    def _get_patterns(self, researcher):
        """Get recent creator patterns."""
        patterns = researcher.get_patterns(limit=10)
        return [p.__dict__ if hasattr(p, '__dict__') else str(p) for p in patterns]

    def _get_approval_stats(self, db):
        """Get approval statistics."""
        rows = db.cx.execute("SELECT state, COUNT(*) c FROM approvals GROUP BY state").fetchall()
        return {r["state"]: r["c"] for r in rows}

    def _get_db_stats(self, db):
        """Get database statistics."""
        assets = db.cx.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
        jobs = db.cx.execute("SELECT COUNT(*) c FROM jobs").fetchall()
        return {"total_assets": assets, "total_jobs": len(jobs)}

    def _json(self, status, data):
        self._send(status, json.dumps(data, indent=2), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_):
        pass


def serve(host="127.0.0.1", port=8765):
    """Start the Nethermind brain floor dashboard."""
    server = ThreadingHTTPServer((host, port), NethermindHandler)
    print(f"Nethermind Brain Floor: http://{host}:{port}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    import os
    serve(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8765")),
    )