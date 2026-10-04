"""Nethermind App — live visual dashboard for the Clipping Farm.

Shows departments/agents/processes in a factory-floor view.
ADHD-friendly: visual, colour-coded, live-updating.

Backend: existing Clipping Farm API (Hermes adapter + DB).
Frontend: simple web UI with cards, progress bars, status indicators.
"""
import json, time, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from clipping_farm.db import DB
from clipping_farm.hermes_adapter import HermesAdapter
from clipping_farm.system_manifest import SystemManifest
from clipping_farm.capability_registry import CapabilityRegistry
from clipping_farm.preflight import PreflightGate
from clipping_farm.creator_researcher import CreatorResearcherAgent
from clipping_farm.learning_brain import LearningBrain
from clipping_farm.automation import AutomationEngine


# ─── HTML Dashboard ───────────────────────────────────────────────

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nethermind — Live Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
h1 { color: #58a6ff; margin-bottom: 10px; }
h2 { color: #f0f6fc; margin: 20px 0 10px; font-size: 1.2em; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.card h3 { color: #58a6ff; font-size: 1em; margin-bottom: 8px; }
.status { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
.status.ok { background: #238636; color: #fff; }
.status.warn { background: #d29922; color: #000; }
.status.error { background: #da3633; color: #fff; }
.status.idle { background: #30363d; color: #c9d1d9; }
.bar { height: 8px; background: #21262d; border-radius: 4px; margin: 8px 0; overflow: hidden; }
.bar > div { height: 100%; border-radius: 4px; transition: width 0.3s; }
.bar-green > div { background: #238636; }
.bar-yellow > div { background: #d29922; }
.bar-red > div { background: #da3633; }
.small { font-size: 0.8em; color: #8b949e; }
button { background: #238636; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9em; }
button:hover { background: #2ea043; }
button.danger { background: #da3633; }
button.danger:hover { background: #f85149; }
input, select { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 6px 10px; border-radius: 6px; font-size: 0.9em; }
.mono { font-family: monospace; font-size: 0.85em; }
</style>
</head>
<body>
<h1>🌌 Nethermind — Live Dashboard</h1>
<p class="small">Factory floor view — all agents, pipelines, and processes</p>

<div id="refresh-note" class="small" style="margin-bottom:16px;">Auto-refresh: ON (every 5s)</div>

<h2>System Health</h2>
<div id="system-health" class="grid"></div>

<h2>Capabilities</h2>
<div id="capabilities" class="grid"></div>

<h2>Pipelines</h2>
<div id="pipelines" class="grid"></div>

<h2>Agents</h2>
<div id="agents" class="grid"></div>

<h2>Creator Patterns</h2>
<div id="patterns" class="grid"></div>

<h2>Learning Brain</h2>
<div id="brain" class="grid"></div>

<h2>Run Pipeline</h2>
<div class="card" style="max-width:600px;">
  <input id="source-input" placeholder="source_id" style="width:200px;">
  <input id="title-input" placeholder="title" style="width:200px;">
  <button onclick="runPipeline()">▶ Run</button>
  <div id="run-result" class="small" style="margin-top:8px;"></div>
</div>

<h2>Research Creator</h2>
<div class="card" style="max-width:600px;">
  <input id="creator-input" placeholder="creator name" style="width:200px;">
  <textarea id="transcript-input" placeholder="Paste transcript here..." style="width:100%;height:60px;background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:6px;font-size:0.9em;"></textarea>
  <button onclick="researchCreator()">🔍 Research</button>
  <div id="research-result" class="small" style="margin-top:8px;"></div>
</div>

<script>
async function load() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    renderSystem(d);
    renderCapabilities(d.capabilities);
    renderPipelines(d.pipelines);
    renderAgents(d.agents);
    renderPatterns(d.patterns);
    renderBrain(d.brain);
  } catch(e) { console.error(e); }
  setTimeout(load, 5000);
}

function renderSystem(d) {
  document.getElementById('system-health').innerHTML = `
    <div class="card"><h3>Manifest</h3><span class="status ok">${d.manifest_version}</span><p class="small">Generated: ${new Date(d.generated_at*1000).toLocaleTimeString()}</p></div>
    <div class="card"><h3>Registry</h3><span class="status ok">${d.registry_version}</span><p class="small">${d.cap_summary.total} capabilities, ${d.cap_summary.available} available</p></div>
    <div class="card"><h3>Approvals</h3><span class="status ${d.approval_stats.PENDING > 0 ? 'warn' : 'ok'}">${d.approval_stats.PENDING || 0} pending</span><p class="small">${d.approval_stats.APPROVED || 0} approved</p></div>
    <div class="card"><h3>DB</h3><span class="status ok">connected</span><p class="small">${d.db_stats.total_assets} assets, ${d.db_stats.total_jobs} jobs</p></div>
  `;
}

function renderCapabilities(caps) {
  const html = Object.entries(caps).map(([k,v]) => `
    <div class="card">
      <h3>${k}</h3>
      <span class="status ${v.status==='AVAILABLE'?'ok':v.status==='DEGRADED'?'warn':'idle'}">${v.status}</span>
      <p class="small">quality: ${v.quality} | cost: ${v.cost_class} | local: ${v.local}</p>
    </div>
  `).join('');
  document.getElementById('capabilities').innerHTML = html;
}

function renderPipelines(pips) {
  const html = (pips || []).map(p => `
    <div class="card">
      <h3>${p.pipeline_id}</h3>
      <span class="status ${p.status==='COMPLETE'?'ok':p.status==='APPROVING_SCRIPT'?'warn':p.status==='CANCELLED'?'error':'idle'}">${p.status}</span>
      <p class="small">agent: ${p.current_agent || '-'}</p>
      <p class="small">jevs: ${p.jev_chain ? p.jev_chain.length : 0}</p>
    </div>
  `).join('');
  document.getElementById('pipelines').innerHTML = html || '<p class="small">No pipelines</p>';
}

function renderAgents(agents) {
  const html = Object.entries(agents).map(([k,v]) => `
    <div class="card">
      <h3>${k}</h3>
      <span class="status ${v.status==='ACTIVE'?'ok':v.status==='ERROR'?'error':v.status==='OFFLINE'?'idle':'warn'}">${v.status}</span>
      <p class="small">health: ${v.health} | uptime: ${Math.round(v.uptime||0)}s</p>
    </div>
  `).join('');
  document.getElementById('agents').innerHTML = html || '<p class="small">No agents</p>';
}

function renderPatterns(patterns) {
  const html = (patterns || []).map(p => `
    <div class="card">
      <h3>${p.pattern_type}</h3>
      <span class="status ok">${p.creator}</span>
      <p class="small">conf: ${p.confidence} | ${p.description.substring(0,60)}...</p>
    </div>
  `).join('');
  document.getElementById('patterns').innerHTML = html || '<p class="small">No patterns yet — research a creator</p>';
}

function renderBrain(brain) {
  const html = `
    <div class="card"><h3>Events</h3><p class="mono">${brain.total_events || 0} recorded</p></div>
    <div class="card"><h3>Threshold Rec</h3><p class="mono">${brain.recommendation || 'pending'}</p></div>
    <div class="card"><h3>Provider Rec</h3><p class="mono">${brain.provider || 'pending'}</p></div>
  `;
  document.getElementById('brain').innerHTML = html;
}

async function runPipeline() {
  const source = document.getElementById('source-input').value;
  const title = document.getElementById('title-input').value;
  const r = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({source_id:source, title:title})});
  const d = await r.json();
  document.getElementById('run-result').textContent = JSON.stringify(d, null, 2);
}

async function researchCreator() {
  const creator = document.getElementById('creator-input').value;
  const transcript = document.getElementById('transcript-input').value;
  const r = await fetch('/api/research', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({creator, transcript})});
  const d = await r.json();
  document.getElementById('research-result').textContent = JSON.stringify(d, null, 2);
}

load();
</script>
</body>
</html>"""


# ─── HTTP Handler ─────────────────────────────────────────────────

class NethermindHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Nethermind dashboard."""

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
        """Aggregate system status for the dashboard."""
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
        jobs = db.cx.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        return {"total_assets": assets, "total_jobs": jobs}

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
    """Start the Nethermind dashboard."""
    server = ThreadingHTTPServer((host, port), NethermindHandler)
    print(f"Nethermind App: http://{host}:{port}")
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