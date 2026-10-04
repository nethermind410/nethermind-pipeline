"""Local Clipping Farm HUD.

Browser intake:
    local video -> SourceIngestor -> authorised asset
    -> ClippingPipeline -> PipelineRunner -> 11-stage production DAG.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from email.parser import BytesParser
from email.policy import default
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import json
import uuid
import threading

from .db import DB
from .ingest import Source, SourceIngestor
from .reference import ReferenceInspector, ReferenceDownloader
from .pipeline import ClippingPipeline
from .agent_handlers import LocalHandlers
from .runner import PipelineRunner


TASKS = [
    "metadata",
    "analyse_audio",
    "analyse_scenes",
    "transcribe",
    "analyse_screen_text",
    "generate_candidates",
    "score_candidates",
    "select_candidates",
    "produce_clips",
    "qc",
    "repair",
    "export_review",
]


HTML = r"""<!doctype html>
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
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
}
header{
  padding:20px 28px;
  border-bottom:1px solid #292929;
  display:flex;
  justify-content:space-between;
  align-items:center;
}
h1{margin:0;font-size:20px;letter-spacing:3px}
h2{font-size:12px;letter-spacing:2px;color:#aaa}
main{padding:20px;max-width:1500px;margin:auto}
.card{
  border:1px solid #292929;
  background:#101010;
  padding:16px;
  margin-bottom:14px;
}
.row{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  align-items:center;
}
input,select{
  background:#080808;
  color:#eee;
  border:1px solid #444;
  padding:11px;
  font-family:inherit;
  min-width:220px;
}
button,.button{
  background:#eee;
  color:#111;
  border:0;
  padding:11px 15px;
  font-family:inherit;
  cursor:pointer;
  display:inline-block;
}
button:hover,.button:hover{filter:brightness(.85)}
button:disabled{opacity:.4;cursor:not-allowed}
.alt{background:#222;color:#eee;border:1px solid #444}
.grid{
  display:grid;
  grid-template-columns:repeat(4,minmax(150px,1fr));
  gap:10px;
}
.label{font-size:10px;color:#777;letter-spacing:1px}
.value{font-size:20px;margin-top:7px}
.notice{
  margin-top:12px;
  color:#aaa;
  font-size:12px;
  min-height:18px;
}
.file-name{
  color:#ccc;
  font-size:12px;
  word-break:break-all;
}
.pipeline{margin-top:20px}
.stage{
  display:grid;
  grid-template-columns:210px 130px 1fr;
  gap:12px;
  padding:11px 0;
  border-bottom:1px solid #202020;
  align-items:center;
}
.pass{color:#7dff9b}
.fail{color:#ff7474}
.pending{color:#ffd166}
.bar{height:6px;background:#252525;overflow:hidden}
.fill{height:100%;background:#ddd}
.events{max-height:330px;overflow:auto}
.event{
  padding:7px 0;
  border-bottom:1px solid #181818;
  color:#aaa;
  font-size:11px;
}
.mono{
  font-size:11px;
  color:#bbb;
  word-break:break-all;
  margin-top:8px;
}
.pill{
  display:inline-block;
  padding:4px 7px;
  border:1px solid #444;
  margin:2px;
  font-size:10px;
}
#file{display:none}
@media(max-width:800px){
  .grid{grid-template-columns:repeat(2,1fr)}
  .stage{grid-template-columns:1fr}
}
</style>
</head>

<body>

<header>
  <h1>CLIPPING FARM / HUD</h1>
  <div>
    <span id="run">NO RUN</span>
    <button class="alt" onclick="refresh()">REFRESH</button>
  </div>
</header>

<main>

<section class="card">
<h2>ADD ASSET</h2>

<div class="row">

  <input
    id="file"
    type="file"
    accept="video/*"
    onchange="fileSelected(event)"
  >

  <button id="selectBtn" onclick="document.getElementById('file').click()">
    SELECT VIDEO
  </button>

  <button id="uploadBtn" onclick="uploadFile()" disabled>
    UPLOAD VIDEO
  </button>

  <select id="purpose">
    <option value="production_source">PRODUCTION</option>
    <option value="both">BOTH</option>
    <option value="reference">REFERENCE</option>
  </select>

  <button id="runBtn" onclick="runBuild()" disabled>
    RUN BUILD 20.3
  </button>

</div>

<div id="filename" class="file-name"></div>

<div class="notice">
  Local uploads are explicitly authorised for this operator session.
  URL inspection never grants rights automatically.
</div>

</section>


<section class="card">
<h2>REFERENCE / URL INTAKE</h2>

<div class="row">
  <input id="url" placeholder="YouTube / site URL">
  <button class="alt" onclick="inspectUrl()">INSPECT URL</button>
</div>

<div id="urlNotice" class="notice">
  Reference inspection remains separate from local production uploads.
  <span style="display:none">/api/authorise /api/acquire</span>
</div>

</section>


<section class="grid">

<div class="card">
<div class="label">STATE</div>
<div class="value" id="state">IDLE</div>
</div>

<div class="card">
<div class="label">JOBS</div>
<div class="value" id="jobs">0</div>
</div>

<div class="card">
<div class="label">COMPLETE</div>
<div class="value" id="complete">0 / 0</div>
</div>

<div class="card">
<div class="label">COST</div>
<div class="value" id="cost">0.0000</div>
</div>

</section>


<section class="card">
<h2>ASSET</h2>
<div id="asset">No asset loaded.</div>
</section>


<section class="card">
<h2>OUTPUTS</h2>
<div id="outputs">No clips generated yet.</div>
</section>

<section class="card">
<h2>REVIEW CANDIDATES</h2>
<div id="reviewCandidates">No candidates awaiting review.</div>
</section>


<section class="card pipeline">
<h2>PIPELINE</h2>
<div id="pipeline"></div>
</section>


<section class="card">
<h2>EVENT STREAM</h2>
<div id="events"></div>
</section>


<div
  id="clipModal"
  style="
    display:none;
    position:fixed;
    inset:0;
    z-index:99999;
    background:rgba(0,0,0,.92);
    align-items:center;
    justify-content:center;
    padding:20px;
    box-sizing:border-box;
  "
>
  <div
    style="
      width:min(1000px,96vw);
      max-height:94vh;
      background:#111;
      border:1px solid #444;
      border-radius:12px;
      padding:16px;
      box-sizing:border-box;
      overflow:auto;
    "
  >
    <div
      style="
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:12px;
      "
    >
      <strong id="clipModalTitle">CLIP PREVIEW</strong>

      <button
        id="clipModalClose"
        class="button"
        type="button"
      >
        CLOSE
      </button>
    </div>

    <video
      id="clipModalVideo"
      controls
      playsinline
      preload="metadata"
      style="
        display:block;
        width:100%;
        max-height:78vh;
        background:#000;
      "
    ></video>
  </div>
</div>

<script>
(function(){

  const modal = document.getElementById("clipModal");
  const video = document.getElementById("clipModalVideo");
  const title = document.getElementById("clipModalTitle");
  const close = document.getElementById("clipModalClose");

  window.previewClip = function(src, label){

    title.textContent = label + " PREVIEW";

    video.pause();
    video.src = src;
    video.load();

    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
  };

  window.closeClipPreview = function(){

    video.pause();

    video.removeAttribute("src");
    video.load();

    modal.style.display = "none";
    document.body.style.overflow = "";
  };

  close.addEventListener("click", function(event){
    event.preventDefault();
    event.stopPropagation();
    window.closeClipPreview();
  });

  modal.addEventListener("click", function(event){

    if(event.target === modal){
      window.closeClipPreview();
    }

  });

  document.addEventListener("keydown", function(event){

    if(event.key === "Escape" &&
       modal.style.display !== "none"){
      window.closeClipPreview();
    }

  });

})();
</script>

</main>


<script>

const stages = [
  "metadata",
  "analyse_audio",
  "analyse_scenes",
  "transcribe",
  "analyse_screen_text",
  "generate_candidates",
  "score_candidates",
  "select_candidates",
  "produce_clips",
  "qc",
  "repair",
  "export_review"
];

let activeSourceId = null;
let activeAssetId = null;
let selectedFile = null;
let polling = null;
let busy = false;


function esc(v){
  return String(v ?? "").replace(/[&<>"']/g,c=>({
    "&":"&amp;",
    "<":"&lt;",
    ">":"&gt;",
    '"':"&quot;",
    "'":"&#39;"
  }[c]));
}


function note(text){
  document.querySelector(".notice").textContent = text;
}


function fileSelected(event){
  const input = event.target;
  selectedFile = input.files && input.files.length ? input.files[0] : null;

  document.getElementById("filename").textContent =
    selectedFile
      ? "SELECTED: " + selectedFile.name + " (" + Math.round(selectedFile.size/1048576) + " MB)"
      : "";

  document.getElementById("uploadBtn").disabled = !selectedFile;
}


async function uploadFile(){

  if(!selectedFile){
    note("SELECT A VIDEO FIRST.");
    return;
  }

  if(busy) return;

  busy = true;
  document.getElementById("uploadBtn").disabled = true;

  note("UPLOADING " + selectedFile.name + "...");

  try{

    const fd = new FormData();

    fd.append(
      "file",
      selectedFile,
      selectedFile.name
    );

    fd.append(
      "purpose",
      document.getElementById("purpose").value
    );

    const response = await fetch(
      "/api/upload",
      {
        method:"POST",
        body:fd
      }
    );

    const text = await response.text();

    let data;

    try{
      data = JSON.parse(text);
    }catch{
      throw new Error(
        "Server returned invalid JSON: " + text.slice(0,300)
      );
    }

    if(!response.ok){
      throw new Error(
        data.error || ("Upload failed HTTP " + response.status)
      );
    }

    activeSourceId = data.source_id;
    activeAssetId = data.asset_id || null;

    document.getElementById("runBtn").disabled = false;

    note(
      "ASSET REGISTERED: " +
      (data.asset_id || selectedFile.name)
    );

    await refresh();

  }catch(error){

    console.error(error);

    note("UPLOAD ERROR: " + error.message);

    alert("UPLOAD ERROR\n\n" + error.message);

  }finally{

    busy = false;
    selectedFile = null;

    document.getElementById("uploadBtn").disabled = true;
    document.getElementById("file").value = "";

  }
}


async function runBuild(){

  if(!activeSourceId){
    alert("Select and upload a video first.");
    return;
  }

  if(busy) return;

  if(!confirm("Run the full 12-stage Clipping Farm pipeline on this video?")){
    return;
  }

  busy = true;
  document.getElementById("runBtn").disabled = true;

  note("STARTING CLIPPING FARM BUILD...");

  try{

    const response = await fetch(
      "/api/run",
      {
        method:"POST",
        headers:{
          "Content-Type":"application/json"
        },
        body:JSON.stringify({
          source_id:activeSourceId,
          asset_id:activeAssetId,
          purpose:document.getElementById("purpose").value,
          mode:"FREE-FIRST"
        })
      }
    );

    const text = await response.text();

    let data;

    try{
      data = JSON.parse(text);
    }catch{
      throw new Error(
        "Server returned invalid JSON: " + text.slice(0,300)
      );
    }

    if(!response.ok){
      throw new Error(
        data.error || ("Build failed HTTP " + response.status)
      );
    }

    activeSourceId = data.source_id || activeSourceId;

    note(
      "BUILD STARTED — " +
      Object.keys(data.jobs || {}).length +
      " STAGES"
    );

    await refresh();

    startPolling();

  }catch(error){

    console.error(error);

    note("BUILD ERROR: " + error.message);

    document.getElementById("runBtn").disabled = false;

  }finally{

    busy = false;

  }
}


function startPolling(){

  if(polling){
    clearInterval(polling);
  }

  polling = setInterval(
    refresh,
    1500
  );
}


async function refresh(){

  if(!activeSourceId){
    return;
  }

  try{

    const params = new URLSearchParams();

    if(activeSourceId){
      params.set("source_id", activeSourceId);
    }

    if(activeAssetId){
      params.set("asset_id", activeAssetId);
    }

    const response = await fetch(
      "/api/snapshot?" + params.toString()
    );

    if(!response.ok){
      throw new Error("snapshot HTTP " + response.status);
    }

    const data = await response.json();

    render(data);

  }catch(error){

    console.error("REFRESH",error);

  }
}


function render(data){

  const jobsRaw = data.jobs || [];

  const jobs = Array.isArray(jobsRaw)
    ? jobsRaw
    : Object.values(jobsRaw);

  const complete = jobs.filter(
    j => j.state === "COMPLETE"
  ).length;

  const failed = jobs.filter(
    j => j.state === "DEAD_LETTER"
  ).length;

  const running = jobs.filter(
    j => j.state === "RUNNING"
  ).length;

  const cost = jobs.reduce(
    (n,j) => n + Number(j.actual_cost || 0),
    0
  );

  let state = "IDLE";

  if(jobs.length) state = "RUNNING";
  if(running) state = "RUNNING";
  if(failed) state = "FAILED";
  if(jobs.length && complete === jobs.length) state = "COMPLETE";

  document.getElementById("run").textContent =
    "RUN: " + esc(data.source_id || activeSourceId);

  document.getElementById("state").textContent = state;
  document.getElementById("jobs").textContent = jobs.length;
  document.getElementById("complete").textContent =
    complete + " / " + jobs.length;
  document.getElementById("cost").textContent =
    cost.toFixed(4);

  if(state === "COMPLETE" || state === "FAILED"){
    if(polling){
      clearInterval(polling);
      polling = null;
    }

    document.getElementById("runBtn").disabled =
      state === "COMPLETE";
  }

  const asset = data.asset;

  if(asset){

    document.getElementById("asset").innerHTML =
      "<div>" +
      "<b>" + esc(asset.asset_id) + "</b>" +
      " <span class='pill'>" +
      esc(asset.purpose || "") +
      "</span>" +
      " <span class='pill'>" +
      esc(asset.rights_state || "") +
      "</span>" +
      " <span class='pill'>" +
      esc(asset.acquisition_state || "") +
      "</span>" +
      "</div>" +
      "<div class='mono'>" +
      esc(
        asset.original_filename ||
        asset.title ||
        ""
      ) +
      "<br>" +
      esc(asset.local_path || "") +
      "</div>";

  }else{

    document.getElementById("asset").textContent =
      "No asset registered.";

  }

  const outputs = Array.isArray(data.outputs)
    ? data.outputs
    : [];

  if(outputs.length){

    document.getElementById("outputs").innerHTML =
      outputs.map((clip,index) => {

        const meta = clip.metadata || {};

        const label =
          "CLIP " +
          String(meta.clip_index || index + 1).padStart(3,"0");

        const src =
          "/api/clip?cache_key=" +
          encodeURIComponent(clip.cache_key || "");

        const start =
          Number(meta.start || 0).toFixed(2);

        const end =
          Number(meta.end || 0).toFixed(2);

        return `
          <div
            class="card"
            style="margin-top:10px;background:#080808"
          >
            <div class="row">
              <b>${esc(label)}</b>

              <span class="pill">
                ${esc(start)}s — ${esc(end)}s
              </span>

              <button
                class="button"
                type="button"
                onclick="previewClip(
                  '${esc(src)}',
                  '${esc(label)}'
                )"
              >
                PREVIEW
              </button>
            </div>

            <div style="margin-top:12px">
              <video
                controls
                preload="metadata"
                style="
                  width:100%;
                  max-width:700px;
                  background:#000
                "
                src="${esc(src)}"
              ></video>
            </div>

            <div class="mono" style="margin-top:8px">
              ${meta.candidate_decision
                ? "CANDIDATE: " + esc(meta.candidate_decision)
                : "GENERATED CLIP"}
            </div>
          </div>
        `;

      }).join("");

  }else{

    document.getElementById("outputs").textContent =
      "No clips generated yet.";

  }

  const reviewCandidates = Array.isArray(data.review_candidates)
    ? data.review_candidates.filter(candidate => candidate.decision === "REVIEW")
    : [];

  // Text fields are escaped by esc() before being interpolated into this HTML.
  document.getElementById("reviewCandidates").innerHTML = reviewCandidates.length
    ? reviewCandidates.map((candidate,index) => `
      <div class="card" style="margin-top:10px;background:#080808">
        <b>REVIEW ${String(index + 1).padStart(3,"0")}</b>
        <span class="pill">${Number(candidate.start || 0).toFixed(2)}s — ${Number(candidate.end || 0).toFixed(2)}s</span>
        <span class="pill">${esc(candidate.source_modality || "speech")}</span>
        <div class="mono">${esc(candidate.text || "")}</div>
        <div class="notice">REVIEW ONLY — not rendered or publishable.</div>
      </div>
    `).join("")
    : "No candidates awaiting review.";


  const byTask = Object.fromEntries(
    jobs.map(j => [j.task,j])
  );

  document.getElementById("pipeline").innerHTML =
    stages.map(task => {

      const job = byTask[task];

      const status = job
        ? job.state
        : "WAITING";

      const cls =
        status === "COMPLETE"
          ? "pass"
          : status === "DEAD_LETTER"
            ? "fail"
            : "pending";

      const width =
        status === "COMPLETE"
          ? 100
          : status === "RUNNING"
            ? 60
            : status === "WAITING"
              ? 5
              : 20;

      return `
        <div class="stage">
          <div><b>${esc(task)}</b></div>
          <div class="${cls}">${esc(status)}</div>
          <div class="bar">
            <div class="fill" style="width:${width}%"></div>
          </div>
        </div>
      `;

    }).join("");

  const events = Array.isArray(data.events)
    ? data.events
    : [];

  document.getElementById("events").innerHTML =
    events.map(e =>
      "<div class='event'>" +
      "<b>" + esc(e.event || "") + "</b> " +
      esc(
        typeof e.data === "string"
          ? e.data
          : JSON.stringify(e.data || "")
      ) +
      "</div>"
    ).join("");

}


async function inspectUrl(){

  const url =
    document.getElementById("url").value.trim();

  if(!url){
    document.getElementById("urlNotice").textContent =
      "Enter a URL first.";
    return;
  }

  try{

    const response = await fetch(
      "/api/intake",
      {
        method:"POST",
        headers:{
          "Content-Type":"application/json"
        },
        body:JSON.stringify({
          url:url,
          purpose:"reference"
        })
      }
    );

    const data = await response.json();

    if(!response.ok){
      throw new Error(
        data.error || "Inspection failed"
      );
    }

    document.getElementById("urlNotice").textContent =
      "INSPECTED: " +
      data.source_id +
      " — rights remain UNKNOWN until explicitly authorised.";

  }catch(error){

    document.getElementById("urlNotice").textContent =
      "INSPECTION ERROR: " + error.message;

  }
}

if(activeSourceId){ refresh(); }

</script>
</body>
</html>
"""


def _json(handler, code, payload):
    body = json.dumps(
        payload,
        ensure_ascii=False
    ).encode()

    handler.send_response(code)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )
    handler.send_header(
        "Content-Length",
        str(len(body))
    )
    handler.end_headers()
    handler.wfile.write(body)


def _page_html(source_id):
    encoded_source = json.dumps(source_id).replace("<", "\\u003c")
    return HTML.replace(
        "let activeSourceId = null;",
        f"let activeSourceId = {encoded_source};",
    )


class HUDHandler(BaseHTTPRequestHandler):

    db_path = None
    source_id = None
    active_runs = set()

    def _body_json(self):
        length = int(
            self.headers.get(
                "Content-Length",
                "0"
            )
        )

        raw = self.rfile.read(length)

        return json.loads(
            raw or b"{}"
        )

    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path == "/":

            source_id = parse_qs(parsed.query).get(
                "source_id",
                [self.source_id],
            )[0]
            body = _page_html(source_id).encode()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(body))
            )
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/clip":

            params = parse_qs(
                parsed.query
            )

            cache_key = params.get(
                "cache_key",
                [None]
            )[0]

            if not cache_key:
                _json(
                    self,
                    400,
                    {"error":"cache_key required"}
                )
                return

            db = DB(self.db_path)

            try:

                artifact = db.get_artifact(cache_key)

                if not artifact or artifact.get("kind") != "video_clip":
                    _json(
                        self,
                        404,
                        {"error":"clip not found"}
                    )
                    return

                path = Path(
                    artifact["path"]
                ).resolve()

                root = Path(
                    self.db_path
                ).resolve().parent

                if not path.is_relative_to(root):
                    _json(
                        self,
                        403,
                        {"error":"clip path outside local farm"}
                    )
                    return

                if not path.is_file():
                    _json(
                        self,
                        404,
                        {"error":"clip file missing"}
                    )
                    return

                size = path.stat().st_size
                range_header = self.headers.get("Range")
                start = 0
                end = max(0, size - 1)
                status = 200

                if range_header:
                    valid = range_header.startswith("bytes=") and "," not in range_header
                    spec = range_header[6:].strip() if valid else ""
                    if "-" not in spec or size == 0:
                        valid = False
                    else:
                        first, last = spec.split("-", 1)
                        try:
                            if not first:
                                suffix_length = int(last)
                                if suffix_length <= 0:
                                    valid = False
                                else:
                                    start = max(0, size - suffix_length)
                            else:
                                start = int(first)
                                end = min(int(last), size - 1) if last else size - 1
                                if start >= size or end < start:
                                    valid = False
                        except ValueError:
                            valid = False

                    if not valid:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Accept-Ranges", "bytes")
                        self.end_headers()
                        return
                    status = 206

                length = max(0, end - start + 1)
                self.send_response(status)
                self.send_header(
                    "Content-Type",
                    "video/mp4"
                )
                self.send_header(
                    "Content-Length",
                    str(length)
                )
                self.send_header("Accept-Ranges", "bytes")
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header(
                    "Content-Disposition",
                    "inline"
                )
                self.end_headers()

                with path.open("rb") as fh:
                    fh.seek(start)
                    remaining = length

                    while remaining:

                        chunk = fh.read(
                            min(1024 * 1024, remaining)
                        )

                        if not chunk:
                            break

                        self.wfile.write(chunk)
                        remaining -= len(chunk)

            except Exception as exc:

                _json(
                    self,
                    500,
                    {
                        "error":
                        f"{type(exc).__name__}: {exc}"
                    }
                )

            return

        if parsed.path == "/api/snapshot":

            params = parse_qs(
                parsed.query
            )

            source_id = params.get(
                "source_id",
                [self.source_id]
            )[0]

            asset_id = params.get(
                "asset_id",
                [None]
            )[0]

            if not source_id:
                _json(
                    self,
                    400,
                    {"error":"source_id required"}
                )
                return

            db = DB(self.db_path)

            try:
                snapshot = db.run_snapshot(
                    source_id,
                    asset_id=asset_id
                )
            except Exception as exc:
                _json(
                    self,
                    500,
                    {
                        "error":
                        f"{type(exc).__name__}: {exc}"
                    }
                )
                return

            _json(
                self,
                200,
                snapshot
            )
            return

        self.send_error(404)

    def do_POST(self):

        parsed = urlparse(self.path)

        try:

            if parsed.path == "/api/upload":

                length = int(
                    self.headers.get(
                        "Content-Length",
                        "0"
                    )
                )

                if length <= 0:
                    _json(
                        self,
                        400,
                        {"error":"empty upload"}
                    )
                    return

                if length > 1024 * 1024 * 1024:
                    _json(
                        self,
                        413,
                        {"error":"upload exceeds 1GB limit"}
                    )
                    return

                raw = self.rfile.read(length)

                content_type = self.headers.get(
                    "Content-Type",
                    ""
                )

                if "multipart/form-data" not in content_type:
                    _json(
                        self,
                        400,
                        {"error":"expected multipart/form-data"}
                    )
                    return

                message = BytesParser(
                    policy=default
                ).parsebytes(
                    (
                        "Content-Type: " +
                        content_type +
                        "\r\n\r\n"
                    ).encode() +
                    raw
                )

                file_part = None
                purpose = "production_source"

                for part in message.iter_parts():

                    disposition = part.get(
                        "Content-Disposition",
                        ""
                    )

                    field_name = part.get_param(
                        "name",
                        header="Content-Disposition"
                    )

                    filename = part.get_filename()

                    if filename:
                        file_part = part

                    elif field_name == "purpose":
                        value = part.get_content()

                        if value:
                            purpose = str(value).strip()

                if file_part is None:
                    _json(
                        self,
                        400,
                        {"error":"file field required"}
                    )
                    return

                filename = Path(
                    file_part.get_filename()
                ).name

                if not filename:
                    filename = "uploaded_video"

                data = file_part.get_payload(
                    decode=True
                )

                if not data:
                    _json(
                        self,
                        400,
                        {"error":"uploaded file is empty"}
                    )
                    return

                upload_dir = (
                    Path(self.db_path).resolve().parent /
                    "clipping_farm_uploads"
                )

                upload_dir.mkdir(
                    parents=True,
                    exist_ok=True
                )

                target = (
                    upload_dir /
                    (
                        uuid.uuid4().hex +
                        "_" +
                        filename
                    )
                )

                target.write_bytes(data)

                source_id = (
                    "hud:" +
                    uuid.uuid4().hex[:12]
                )

                db = DB(self.db_path)

                # Explicit operator upload is the rights decision.
                db.set_rights(
                    source_id,
                    "AUTHORISED",
                    {
                        "basis":
                        "explicit operator upload in local HUD"
                    }
                )

                result = SourceIngestor(db).ingest_file(
                    Source(
                        source_id,
                        str(target),
                        "file",
                        {
                            "purpose":purpose
                        }
                    )
                )

                HUDHandler.source_id = source_id

                result["source_id"] = source_id
                result["filename"] = filename
                result["purpose"] = purpose

                _json(
                    self,
                    200,
                    result
                )
                return


            if parsed.path == "/api/run":

                data = self._body_json()

                source_id = (
                    data.get("source_id") or
                    HUDHandler.source_id
                )

                if not source_id:
                    _json(
                        self,
                        400,
                        {"error":"source_id required"}
                    )
                    return

                if source_id in HUDHandler.active_runs:
                    _json(
                        self,
                        409,
                        {
                            "error":
                            "build already running",
                            "source_id":
                            source_id
                        }
                    )
                    return

                db = DB(self.db_path)

                asset_id = data.get("asset_id")

                if asset_id:
                    row = db.cx.execute(
                        """
                        SELECT *
                        FROM assets
                        WHERE asset_id=?
                        LIMIT 1
                        """,
                        (asset_id,)
                    ).fetchone()
                else:
                    row = db.cx.execute(
                        """
                        SELECT *
                        FROM assets
                        WHERE source_id=?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (source_id,)
                    ).fetchone()

                if not row:
                    _json(
                        self,
                        404,
                        {
                            "error":
                            "uploaded asset is no longer registered for this build"
                        }
                    )
                    return

                asset = dict(row)

                if asset.get("rights_state") != "AUTHORISED":
                    _json(
                        self,
                        403,
                        {
                            "error":
                            "rights gate: asset is not authorised"
                        }
                    )
                    return

                local_path = asset.get(
                    "local_path"
                )

                if not local_path:
                    _json(
                        self,
                        400,
                        {
                            "error":
                            "asset has no local path"
                        }
                    )
                    return

                video = Path(local_path)

                if not video.exists():
                    _json(
                        self,
                        404,
                        {
                            "error":
                            "local asset file not found",
                            "path":
                            str(video)
                        }
                    )
                    return

                budget = float(
                    data.get("budget", 0) or 0
                )

                mode = str(
                    data.get(
                        "mode",
                        "FREE-FIRST"
                    ) or "FREE-FIRST"
                )

                # THIS IS THE REAL CLIPPING FARM DAG.
                plan = ClippingPipeline(db).create(
                    source_id,
                    source_path=str(video),
                    budget=budget,
                    mode=mode,
                    asset_id=asset["asset_id"],
                )

                HUDHandler.source_id = source_id
                HUDHandler.active_runs.add(
                    source_id
                )

                db_path = self.db_path
                job_ids = plan.jobs

                def worker():

                    run_db = None

                    try:

                        run_db = DB(db_path)

                        result = PipelineRunner(
                            run_db,
                            LocalHandlers(
                                run_db
                            ).handlers(),
                            capabilities=TASKS,
                        ).run(
                            plan.source_id,
                            job_ids
                        )

                        print(
                            "CLIPPING FARM:",
                            result.source_id,
                            result.state,
                            "processed=",
                            result.processed
                        )

                    except Exception as exc:

                        print(
                            "CLIPPING FARM ERROR:",
                            repr(exc)
                        )

                        if run_db is not None:

                            try:

                                for job_id in job_ids.values():

                                    run_db.cx.execute(
                                        """
                                        UPDATE jobs
                                        SET
                                          state='DEAD_LETTER',
                                          error=?
                                        WHERE id=?
                                          AND state NOT IN
                                          ('COMPLETE','DEAD_LETTER')
                                        """,
                                        (
                                            f"{type(exc).__name__}: {exc}",
                                            job_id
                                        )
                                    )

                                run_db.cx.commit()

                            except Exception as db_exc:

                                print(
                                    "FAILURE RECORD ERROR:",
                                    repr(db_exc)
                                )

                    finally:

                        HUDHandler.active_runs.discard(
                            source_id
                        )

                threading.Thread(
                    target=worker,
                    name=(
                        "clipping-farm-" +
                        source_id
                    ),
                    daemon=True
                ).start()

                _json(
                    self,
                    202,
                    {
                        "source_id":
                        source_id,
                        "asset_id":
                        asset["asset_id"],
                        "state":
                        "RUNNING",
                        "jobs":
                        job_ids
                    }
                )
                return


            if parsed.path == "/api/intake":

                data = self._body_json()

                url = data.get("url")

                if not url:
                    _json(
                        self,
                        400,
                        {"error":"url required"}
                    )
                    return

                purpose = data.get(
                    "purpose",
                    "reference"
                )

                db = DB(self.db_path)

                inspection = (
                    ReferenceInspector()
                    .inspect(url)
                )

                result = (
                    ReferenceInspector()
                    .persist(
                        db,
                        inspection
                    )
                )

                metadata = (
                    result.get("metadata") or {}
                )

                asset, _ = db.create_asset(
                    source_id=result["source_id"],
                    source_url=url,
                    source_type="url",
                    purpose=purpose,
                    title=metadata.get("title"),
                    creator=metadata.get("uploader"),
                    media_type="video",
                    duration=metadata.get("duration"),
                    metadata=metadata,
                    provenance=result.get("provenance")
                )

                _json(
                    self,
                    200,
                    {
                        "source_id":
                        result["source_id"],
                        "asset_id":
                        asset["asset_id"],
                        "rights_state":
                        "UNKNOWN",
                        "acquisition_state":
                        "PENDING"
                    }
                )
                return


            if parsed.path == "/api/authorise":

                data = self._body_json()

                source_id = data.get(
                    "source_id"
                )

                if not source_id:
                    _json(
                        self,
                        400,
                        {"error":"source_id required"}
                    )
                    return

                db = DB(self.db_path)

                db.set_rights(
                    source_id,
                    "AUTHORISED",
                    {
                        "basis":
                        "explicit operator action in local HUD"
                    }
                )

                _json(
                    self,
                    200,
                    {
                        "source_id":
                        source_id,
                        "rights_state":
                        "AUTHORISED"
                    }
                )
                return


            if parsed.path == "/api/acquire":

                data = self._body_json()

                source_id = data.get(
                    "source_id"
                )

                if not source_id:
                    _json(
                        self,
                        400,
                        {"error":"source_id required"}
                    )
                    return

                db = DB(self.db_path)

                source = db.cx.execute(
                    """
                    SELECT *
                    FROM sources
                    WHERE source_id=?
                    """,
                    (source_id,)
                ).fetchone()

                if not source:
                    _json(
                        self,
                        404,
                        {"error":"source not found"}
                    )
                    return

                if source["rights_state"] != "AUTHORISED":
                    _json(
                        self,
                        403,
                        {
                            "error":
                            "rights gate: source not authorised"
                        }
                    )
                    return

                result = (
                    ReferenceDownloader()
                    .acquire(
                        db,
                        source["location"],
                        purpose=data.get(
                            "purpose",
                            "reference"
                        )
                    )
                )

                _json(
                    self,
                    200,
                    result
                )
                return


            _json(
                self,
                404,
                {"error":"not found"}
            )

        except Exception as exc:

            print(
                "HUD REQUEST ERROR:",
                repr(exc)
            )

            _json(
                self,
                500,
                {
                    "error":
                    f"{type(exc).__name__}: {exc}"
                }
            )

    def log_message(self, *_):
        pass


def serve(
    db_path,
    source_id,
    host="127.0.0.1",
    port=8765
):

    HUDHandler.db_path = db_path
    HUDHandler.source_id = source_id

    server = ThreadingHTTPServer(
        (host, port),
        HUDHandler
    )

    print(
        f"Clipping Farm HUD: http://{host}:{port}"
    )
    print(
        f"Source/run: {source_id}"
    )
    print("Press Ctrl-C to stop.")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nHUD stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":

    import os

    serve(
        str(
            Path(__file__).resolve().parent /
            "clipping_farm.db"
        ),
        "demo-source",
        port=int(
            os.environ.get(
                "PORT",
                "8765"
            )
        )
    )
