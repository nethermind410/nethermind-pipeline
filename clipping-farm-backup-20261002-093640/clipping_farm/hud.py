"""Local Clipping Farm HUD."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .db import DB


HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clipping Farm HUD</title>
<style>
*{box-sizing:border-box}
body{
  margin:0;
  background:#090909;
  color:#eee;
  font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,monospace;
}
header{
  padding:22px 28px;
  border-bottom:1px solid #252525;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
h1{margin:0;font-size:20px;letter-spacing:3px}
#run{color:#888;font-size:12px}
main{padding:24px;max-width:1400px;margin:auto}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  gap:10px;
}
.card{
  border:1px solid #292929;
  background:#101010;
  padding:16px;
}
.label{font-size:11px;color:#777;letter-spacing:1px}
.value{font-size:22px;margin-top:7px}
.pipeline{margin-top:22px}
.stage{
  display:grid;
  grid-template-columns:180px 120px 1fr;
  gap:12px;
  padding:12px 0;
  border-bottom:1px solid #202020;
  align-items:center;
}
.stage-name{font-weight:bold}
.pass{color:#7dff9b}
.fail{color:#ff7474}
.pending{color:#ffd166}
.bar{
  height:6px;
  background:#252525;
  overflow:hidden;
}
.fill{
  height:100%;
  background:#ddd;
}
.events{
  margin-top:22px;
  max-height:360px;
  overflow:auto;
}
.event{
  padding:8px 0;
  border-bottom:1px solid #181818;
  color:#aaa;
  font-size:11px;
}
button{
  background:#eee;
  color:#111;
  border:0;
  padding:8px 12px;
  font-family:inherit;
  cursor:pointer;
}
@media(max-width:700px){
  .stage{grid-template-columns:1fr}
  main{padding:14px}
}
</style>
</head>
<body>
<header>
  <h1>CLIPPING FARM / HUD</h1>
  <div>
    <span id="run">NO RUN</span>
    <button onclick="load()">REFRESH</button>
  </div>
</header>
<main>
  <section class="grid">
    <div class="card"><div class="label">STATE</div><div class="value" id="state">—</div></div>
    <div class="card"><div class="label">JOBS</div><div class="value" id="jobs">—</div></div>
    <div class="card"><div class="label">COMPLETE</div><div class="value" id="complete">—</div></div>
    <div class="card"><div class="label">COST</div><div class="value" id="cost">—</div></div>
  </section>

  <section class="pipeline">
    <h2>PIPELINE</h2>
    <div id="pipeline"></div>
  </section>

  <section class="events">
    <h2>EVENT STREAM</h2>
    <div id="events"></div>
  </section>
</main>

<script>
const stages = [
  "metadata","analyse_audio","analyse_scenes","transcribe",
  "generate_candidates","score_candidates","select_candidates",
  "produce_clips","qc","repair","export_review"
];

function esc(value){
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",
    '"':"&quot;","'":"&#39;"
  }[c]));
}

async function load(){
  const response = await fetch("/api/snapshot");
  const data = await response.json();

  document.getElementById("run").textContent =
    "RUN: " + data.source_id;

  const jobs = data.jobs || [];
  const complete = jobs.filter(j => j.state === "COMPLETE").length;
  const failed = jobs.filter(j => j.state === "DEAD_LETTER").length;
  const cost = jobs.reduce((n,j) => n + Number(j.actual_cost || 0), 0);

  let state = "RUNNING";
  if(jobs.length && complete === jobs.length) state = "COMPLETE";
  if(failed) state = "FAILED";

  document.getElementById("state").textContent = state;
  document.getElementById("jobs").textContent = jobs.length;
  document.getElementById("complete").textContent =
    complete + " / " + jobs.length;
  document.getElementById("cost").textContent =
    cost.toFixed(4);

  const byTask = Object.fromEntries(jobs.map(j => [j.task,j]));
  document.getElementById("pipeline").innerHTML =
    stages.map(task => {
      const job = byTask[task];
      const status = job ? job.state : "WAITING";
      const cls =
        status === "COMPLETE" ? "pass" :
        status === "DEAD_LETTER" ? "fail" :
        "pending";

      return `
        <div class="stage">
          <div class="stage-name">${esc(task)}</div>
          <div class="${cls}">${esc(status)}</div>
          <div class="bar">
            <div class="fill" style="width:${status === "COMPLETE" ? 100 : status === "RUNNING" ? 60 : 15}%"></div>
          </div>
        </div>`;
    }).join("");

  document.getElementById("events").innerHTML =
    (data.events || []).map(e => `
      <div class="event">
        <b>${esc(e.event)}</b>
        ${esc(e.data)}
      </div>
    `).join("");
}

load();
setInterval(load, 3000);
</script>
</body>
</html>
"""


class HUDHandler(BaseHTTPRequestHandler):
    db_path = None
    source_id = None

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/snapshot":
            db = DB(self.db_path)
            payload = db.run_snapshot(self.source_id)
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404)

    def log_message(self, *_):
        pass


def serve(db_path, source_id, host="127.0.0.1", port=8765):
    HUDHandler.db_path = db_path
    HUDHandler.source_id = source_id

    server = ThreadingHTTPServer((host, port), HUDHandler)

    print(f"Clipping Farm HUD: http://{host}:{port}")
    print(f"Source: {source_id}")
    print("Press Ctrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHUD stopped.")
    finally:
        server.server_close()
