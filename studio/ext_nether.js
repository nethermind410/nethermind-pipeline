"use strict";
/* NETHER in Studio: agents on the brain, an Agents page (every task, its steps, errors, retry)
   and an Intelligence page (investigate a topic, give your call, see what NETHER has learned).
   Uses app.js helpers: $, esc, get, post, toast, sheet, main, go, route, runJob, fmt. */
(() => {
  const STATE = {working: "Working", failed: "Needs you", ready: "Ready"};
  const ago = iso => { if (!iso) return ""; const s = (Date.now() - new Date(iso)) / 1000;
    return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`; };

  /* ---------- nav ---------- */
  const icon = {agents: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="18" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 7l3 3M17 7l-3 3M7 17l3-3M17 17l-3-3"/></svg>`,
    intelligence: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5M11 8v6M8 11h6"/></svg>`};
  const settings = document.querySelector('.nav[data-go="settings"]');
  [["intelligence", "Intelligence"], ["agents", "Agents"]].forEach(([k, label]) => {
    const b = document.createElement("button"); b.className = "nav"; b.dataset.go = k;
    b.innerHTML = `${icon[k]}${label}<span class="count" id="count-${k}" hidden></span>`;
    settings ? settings.before(b) : document.querySelector(".side").append(b);
  });

  /* ---------- the brain: agents as glowing nodes, sub-agents orbiting them ---------- */
  let sys = null, layer = null, timer = null;
  async function refresh() {
    try { sys = await get("/api/system"); } catch (e) { return; }
    const failed = sys.agents.reduce((a, g) => a + g.subs.filter(s => s.state === "failed").length + (g.state === "failed" && !g.subs.some(s => s.state === "failed") ? 1 : 0), 0);
    const b = $("#count-agents"); if (b) { b.hidden = !failed; b.textContent = failed; }
    draw();
  }
  function mount() {
    const stage = $("#stage");
    if (!stage || !window.brainNet || $(".nx-layer", stage)) return;
    layer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    layer.setAttribute("class", "nx-layer"); layer.setAttribute("aria-label", "NETHER agents");
    stage.append(layer);
    const panel = document.createElement("button"); panel.className = "nx-panel"; panel.dataset.go = "agents";
    stage.append(panel);
    brainNet.onView(draw);
    draw();
  }
  function draw() {
    const stage = $("#stage");
    if (!layer || !stage || !stage.contains(layer) || !window.brainNet || !sys) return;
    const S = stage.getBoundingClientRect();
    layer.setAttribute("viewBox", `0 0 ${S.width} ${S.height}`);
    let out = "";
    sys.agents.forEach((a, ai) => {
      const [x, y] = brainNet.anchor(a.ax, a.ay), n = a.subs.length, R = 30;
      a.subs.forEach((s, i) => {
        const t = (i / n) * Math.PI * 2 + ai * 0.7, sx = x + Math.cos(t) * R, sy = y + Math.sin(t) * R;
        out += `<line class="nx-link ${s.state}" x1="${x}" y1="${y}" x2="${sx}" y2="${sy}"/>
          <circle class="nx-sub ${s.state}" cx="${sx}" cy="${sy}" r="3.4"><title>${esc(a.name)} → ${esc(s.name)}: ${STATE[s.state]}${s.last?.error ? " — " + esc(s.last.error.split("\n").pop()) : ""}</title></circle>`;
      });
      out += `<g class="nx-agent ${a.state}" data-go="agents" tabindex="0" role="button" aria-label="${esc(a.name)} agent: ${STATE[a.state]}">
          <circle class="nx-glow" cx="${x}" cy="${y}" r="16"/><circle class="nx-core" cx="${x}" cy="${y}" r="7"/>
          <text x="${x}" y="${y + R + 18}">${esc(a.name.toUpperCase())}</text>
          <title>${esc(a.name)} — ${esc(a.role)}. ${STATE[a.state]}${a.active ? ` (${a.active} active)` : ""}</title></g>`;
    });
    layer.innerHTML = out;
    const c = sys.counts, p = $(".nx-panel", stage);
    if (p) p.innerHTML = `<span class="nx-dot"></span><b>NETHER</b><span>online</span><span>${c.working} working</span>
      <span>${fmt(c.complete)} done</span><span class="${c.failed ? "bad" : ""}">${c.failed} failed</span><span>${sys.agents.length} agents</span>
      ${sys.investigating ? `<span class="nx-busy">investigating “${esc(sys.investigating)}”</span>` : ""}`;
  }
  setInterval(() => { if (document.body.classList.contains("on-brain")) mount(); }, 700);
  timer = setInterval(() => { if (!document.hidden) refresh(); }, 5000);
  refresh();

  /* ---------- Agents page ---------- */
  const stepRow = s => `<li class="nx-step ${s.status}"><span class="nx-sd"></span><span>${esc(s.title)}</span>
      <span class="nx-meta">${s.status === "working" ? "working…" : esc(s.status)}</span>
      ${s.error ? `<pre class="nx-err">${esc(s.error.split("\n").slice(-8).join("\n"))}</pre>` : ""}</li>`;
  function retryBtn(t) {
    if (!t.retry || !["failed", "cancelled"].includes(t.status)) return "";
    return t.retry.kind === "intel" ? `<button class="btn small primary" data-nx-intel="${esc(t.retry.topic)}">Retry</button>`
      : `<button class="btn small primary" data-nx-retry="${esc(t.retry.action)}" data-id="${esc(t.retry.id || "")}">Retry</button>`;
  }
  async function pageAgents() {
    const [s, tasks] = await Promise.all([get("/api/system"), get("/api/tasks")]);
    sys = s;
    const agents = s.agents.map(a => `<div class="card nx-card ${a.state}">
        <div class="nx-head"><span class="nx-state ${a.state}"></span><b>${esc(a.name)}</b><span class="nx-meta">${STATE[a.state]}${a.active ? ` · ${a.active} active` : ""}</span></div>
        <p class="nx-role">${esc(a.role)}</p>
        <div class="nx-subs">${a.subs.map(x => `<span class="nx-chip ${x.state}" title="${esc(x.last ? `${x.last.title} — ${x.last.status}${x.last.finished ? " " + ago(x.last.finished) : ""}` : "Not run yet")}">${esc(x.name)}</span>`).join("")}</div>
        ${a.last ? `<p class="nx-meta">Last: ${esc(a.last.title)} · ${esc(a.last.status)} ${ago(a.last.finished)}</p>` : `<p class="nx-meta">No tasks yet</p>`}</div>`).join("");
    const rows = tasks.map(t => `<div class="card nx-task ${t.status}">
        <div class="nx-head"><span class="nx-state ${t.status === "complete" ? "ready" : t.status === "working" ? "working" : t.status === "failed" ? "failed" : "ready"}"></span>
          <b>${esc(t.title)}</b><span class="pill">${esc(t.agent)}</span><span class="nx-meta">${esc(t.status)} · ${ago(t.finished || t.started)}</span>
          <span class="nx-actions">${retryBtn(t)}${t.status === "working" ? `<button class="btn small" data-nx-cancel="${t.id}">Cancel</button>` : ""}</span></div>
        ${t.steps.length ? `<ol class="nx-steps">${t.steps.map(stepRow).join("")}</ol>` : t.error ? `<pre class="nx-err">${esc(t.error.split("\n").slice(-8).join("\n"))}</pre>` : ""}
      </div>`).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Agents</h1><p>Every job is a task owned by an agent. When something breaks, the red step shows where and why — retry it from here.</p></div>
        <div class="nx-counts"><span>${s.counts.working} working</span><span>${fmt(s.counts.complete)} done</span><span class="${s.counts.failed ? "bad" : ""}">${s.counts.failed} failed</span></div></div>
      <div class="nx-grid">${agents}</div>
      <h2>Recent tasks</h2>${rows || `<div class="card caught"><b>No tasks yet</b>Builds, posts, refreshes and investigations will show up here as they run.</div>`}</div>`;
  }

  /* ---------- Intelligence page ---------- */
  const COMP = {demand: "Demand", competition: "Competition", fit: "Channel fit", taste: "Your taste", visuals: "Visuals", sources: "Sources"};
  const bar = v => v == null ? `<span class="nx-meta">failed</span>` : `<span class="nx-bar"><i style="width:${Math.round(v * 100)}%"></i></span>`;
  function scorecard(c) {
    const comps = Object.entries(c.components).map(([k, v]) => `<div class="nx-comp"><span>${COMP[k] || k}</span>${bar(v.score)}<span class="nx-meta">${Math.round(v.weight)} pts</span></div>`).join("");
    const d = c.decision;
    const call = d ? `<div class="nx-decided ${d.choice}">${d.choice === "make" ? "You said: make it" : "You said: not for us"}${d.reason ? ` — “${esc(d.reason)}”` : ""}
        ${c.made_as ? `<br>Made as <button class="link" data-open="${esc(c.made_as)}">${esc(c.made_as)}</button>${c.views != null ? ` · ${fmt(c.views)} views so far` : ""}` : ""}</div>`
      : `<div class="nx-call"><input class="nx-reason" placeholder="Why? (optional — NETHER learns from this)" maxlength="300">
         <button class="btn small primary" data-nx-decide="make" data-slug="${esc(c.slug)}">Make it</button>
         <button class="btn small" data-nx-decide="skip" data-slug="${esc(c.slug)}">Not for us</button></div>`;
    const top = (c.evidence?.demand?.top || []).slice(0, 3).map(v => `<li><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a> <span class="nx-meta">${esc(v.channel)} · ${fmt(v.views)}</span></li>`).join("");
    return `<div class="card nx-score">
      <div class="nx-head"><span class="nx-big ${c.score >= 70 ? "good" : c.score >= 50 ? "ok" : "low"}">${c.score}</span>
        <div><b>${esc(c.topic)}</b><div class="nx-meta">${esc(c.verdict)} · ${esc(c.lane)} · ${ago(c.at)}</div></div></div>
      <div class="nx-comps">${comps}</div>
      <ul class="nx-reasons">${c.reasons.map(r => `<li>${esc(r)}</li>`).join("")}${Object.entries(c.failed || {}).map(([k, e]) => `<li class="bad">${esc(k)} scout failed: ${esc(e)}</li>`).join("")}</ul>
      ${top ? `<details><summary>Top similar Shorts</summary><ul class="nx-top">${top}</ul></details>` : ""}
      ${call}</div>`;
  }
  async function pageIntelligence() {
    const [L, s] = await Promise.all([get("/api/learning"), get("/api/system")]);
    const wrows = Object.entries(L.weights).map(([k, v]) => { const d = v - (L.default[k] || 0);
      return `<div class="nx-comp"><span>${COMP[k] || k}</span><span class="nx-bar"><i style="width:${Math.min(100, v * 2.5)}%"></i></span><span class="nx-meta">${Math.round(v)} pts${Math.abs(d) >= 0.5 ? ` (${d > 0 ? "+" : ""}${d.toFixed(1)})` : ""}</span></div>`; }).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Intelligence</h1><p>Give NETHER a topic. Five scouts check real demand, competition, how the lane does on your channel, usable visuals and sources — then you make the call.</p></div></div>
      <form class="card nx-run" id="nx-run"><input id="nx-topic" placeholder="e.g. Wolverine's healing factor vs the axolotl" maxlength="120" ${s.investigating ? "disabled" : ""}>
        <button class="btn primary" ${s.investigating ? "disabled" : ""}>${s.investigating ? "Investigating…" : "Investigate"}</button></form>
      ${s.investigating ? `<p class="nx-meta nx-live">Scouts are working on “${esc(s.investigating)}” — this page updates when they're done.</p>` : ""}
      <div class="nx-two"><div><h2>Scorecards</h2>${L.cards.map(scorecard).join("") || `<div class="card caught"><b>No investigations yet</b>Try a topic from your backlog.</div>`}</div>
      <div><h2>What NETHER has learned</h2><div class="card nx-learned">
        <span class="k">How the score is weighted now</span>${wrows}
        <ul class="nx-reasons">${L.lessons.map(l => `<li>${esc(l)}</li>`).join("") || "<li>Nothing yet — investigate topics and give each one your call.</li>"}</ul>
        <p class="nx-meta">Weights start even-handed and move (max ±25% a run) only when real views back it. Lessons are also written to LEARNINGS.md for the daily build.</p>
        <button class="btn small" id="nx-relearn">Re-check against latest numbers</button></div></div></div></div>`;
    $("#nx-run").onsubmit = async e => { e.preventDefault(); const t = $("#nx-topic").value.trim(); if (!t) return;
      try { toast((await post("/api/intel/run", {topic: t})).reply); watch(); pageIntelligence(); } catch (err) { toast(err.message); } };
    $("#nx-relearn").onclick = async () => { try { toast((await post("/api/learning/run", {})).reply); pageIntelligence(); } catch (err) { toast(err.message); } };
    if (s.investigating) watch();
  }
  let watching = null;
  function watch() {
    clearInterval(watching);
    watching = setInterval(async () => { const s = await get("/api/system"); if (s.investigating) return;
      clearInterval(watching); toast("Scorecard ready."); if (location.hash === "#intelligence") pageIntelligence(); }, 2500);
  }

  /* ---------- actions ---------- */
  document.addEventListener("click", async e => {
    const t = e.target;
    const ag = t.closest(".nx-agent"); if (ag) { e.stopPropagation(); return go("agents"); }
    const r = t.closest("[data-nx-retry]");
    if (r) { runJob(r.dataset.nxRetry, r.dataset.id); return setTimeout(pageAgents, 800); }
    const ri = t.closest("[data-nx-intel]");
    if (ri) { try { toast((await post("/api/intel/run", {topic: ri.dataset.nxIntel})).reply); go("intelligence"); } catch (err) { toast(err.message); } return; }
    const cx = t.closest("[data-nx-cancel]");
    if (cx) { await post("/api/tasks/cancel", {id: +cx.dataset.nxCancel}); toast("Cancelled."); return pageAgents(); }
    const dc = t.closest("[data-nx-decide]");
    if (dc) { const reason = dc.closest(".nx-call").querySelector(".nx-reason").value;
      try { toast((await post("/api/intel/decide", {slug: dc.dataset.slug, choice: dc.dataset.nxDecide, reason})).reply); pageIntelligence(); } catch (err) { toast(err.message); } }
  }, true);

  window.PAGES.agents = pageAgents;
  window.PAGES.intelligence = pageIntelligence;
  if (["agents", "intelligence"].includes(location.hash.slice(1))) route();
})();
