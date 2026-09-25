"use strict";
/* NETHER in Studio — the app as a multi-agent system.
   The brain: each section is an agent; its sub-agents hang off it on dendrites; tracts carry impulses between
   agents the way work flows (Intelligence → Content → Production → Publishing → Analytics → back). Working
   agents fire, finished work fires a hand-off to the next agent, broken ones glow amber. Every node is clickable.
   Pages: each agent is a hub whose tabs are its sub-agents' pages (Ideas, Videos, Calendar… live inside them),
   plus Investigate, Make (Content drafts → you approve → build), the draft review, and the Task log.
   Uses app.js helpers: $, esc, get, post, toast, sheet, main, go, route, runJob, fmt, media. */
(() => {
  const STATE = {working: "Working", failed: "Needs you", ready: "Ready"};
  const ago = iso => { if (!iso) return ""; const s = (Date.now() - new Date(iso)) / 1000;
    return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`; };
  /* ---------- small visuals ---------- */
  const RUN = {complete: "done", failed: "failed", cancelled: "cancelled"};
  // run history: one dot per recent task, oldest → newest; status is also in the tooltip and the text beside it
  const pips = (recent = [], label = "Recent runs") => recent.length ? `<span class="nx-pips" role="img" aria-label="${label}: ${recent.map(r => RUN[r.status] || r.status).join(", ")}">${
    recent.map(r => `<i class="${esc(r.status)}" title="${esc(r.title)} — ${RUN[r.status] || esc(r.status)} ${ago(r.finished)}"></i>`).join("")}</span>` : "";
  // an agent as a tiny neuron: its core + one dot per sub-agent, coloured by state (hl = the sub-agent in focus)
  function glyph(a, hl, size = 40) {
    const c = size / 2, n = a.subs.length, r = size * 0.36;
    const subs = a.subs.map((s, i) => { const t = -Math.PI / 2 + (i / n) * Math.PI * 2, x = c + Math.cos(t) * r, y = c + Math.sin(t) * r;
      return `<line x1="${c}" y1="${c}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" class="${s.state}"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${s.key === hl ? 3.6 : 2.3}" class="${s.state}${s.key === hl ? " hl" : ""}"/>`; }).join("");
    return `<svg class="nx-glyph ${a.state}" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">${subs}<circle cx="${c}" cy="${c}" r="${size * 0.12}" class="core"/></svg>`;
  }
  // a multi-step task as a connected pipeline; the step that broke is amber and named
  function pipeline(steps) {
    if (!steps.length) return "";
    return `<ol class="nx-pipe">${steps.map(s => `<li class="${esc(s.status)}" title="${esc(s.title)} — ${esc(s.status)}"><i></i><span>${esc(s.title)}</span></li>`).join("")}</ol>`;
  }
  // the score inside a ring (0–100)
  function ring(score, cls) {
    const R = 26, C = 2 * Math.PI * R, f = Math.max(0, Math.min(1, score / 100));
    return `<span class="nx-ring ${cls}" role="img" aria-label="Score ${score} out of 100"><svg viewBox="0 0 64 64" width="64" height="64">
      <circle cx="32" cy="32" r="${R}" class="track"/><circle cx="32" cy="32" r="${R}" class="val" stroke-dasharray="${(C * f).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 32 32)"/></svg><b>${score}</b></span>`;
  }
  // pacing: one bar per spoken line, width = its time on screen; the 3s hook window and long holds marked
  function pacing(lines) {
    const secs = lines.map(l => l.text.split(/\s+/).filter(Boolean).length / 2.8 + 0.15), total = secs.reduce((a, b) => a + b, 0) || 1;
    const long = secs.filter(s => s > 6).length;
    return `<div class="nx-pace"><div class="nx-pace-bar">${lines.map((l, i) => `<button class="nx-seg ${i === 0 ? "hook" : ""} ${secs[i] > 6 ? "long" : ""}" style="flex:${secs[i].toFixed(2)}" data-scroll-line="${i}"
        title="Line ${i + 1} · ${secs[i].toFixed(1)}s${secs[i] > 6 ? " — one picture held over 6s" : ""}: ${esc(l.text)}">${l.hero ? `<em>${esc(l.hero.join(" "))}</em>` : ""}</button>`).join("")}
        <span class="nx-pace-mark" style="left:${Math.min(100, 3 / total * 100).toFixed(1)}%"><span>3s</span></span></div>
      <div class="nx-pace-axis"><span>0s</span><span class="nx-meta">${lines.length} lines · hook in <b>crimson</b>${long ? ` · <span class="bad">${long} held over 6s</span>` : " · no long holds"} · on-screen numbers above their line</span><span>${total.toFixed(0)}s</span></div></div>`;
  }

  const HUBS = {intelligence: [["brief", "Brief"], ["investigate", "Investigate"], ["ideas", "Ideas"]], content: [["make", "Make"]],
    production: [["videos", "Videos"]], publishing: [["calendar", "Calendar"]],
    analytics: [["performance", "Performance"], ["retention", "Retention"]],
    business: [["money", "Money"], ["comments", "Comments"], ["channel", "Channel"]], control: [["agents", "Task log"], ["settings", "Settings"]]};
  const OWNER = Object.fromEntries(Object.entries(HUBS).flatMap(([a, tabs]) => tabs.map(([r]) => [r, a])));
  Object.assign(OWNER, {draft: "content", video: "production"});
  const FLOW = {intelligence: "content", content: "production", production: "publishing", publishing: "analytics",
    analytics: "intelligence", business: "analytics", control: "production"};
  const TRACTS = [...Object.entries(FLOW), ["control", "content"], ["business", "publishing"]];
  let sys = null, prevLast = {};

  /* ---------- live state ---------- */
  async function refresh() {
    let s; try { s = await get("/api/system"); } catch (e) { return; }
    handoffs(s); sys = s;
    const failed = s.agents.filter(a => a.state === "failed").length;
    const bc = $("#count-control"); if (bc) { bc.hidden = !failed; bc.textContent = failed; }
    get("/api/drafts").then(d => { const b = $("#count-content"); if (b) { b.hidden = !d.drafts.length; b.textContent = d.drafts.length; } }).catch(() => {});
    status(); draw();
  }
  function status() {
    const el = $("#nx-status"); if (!el || !sys) return;
    const c = sys.counts, busy = sys.agents.filter(a => a.state === "working").map(a => a.name);
    el.classList.toggle("bad", sys.agents.some(a => a.state === "failed"));
    el.innerHTML = `<span class="nx-dot"></span><b>NETHER</b><span>${busy.length ? esc(busy.join(" · ")) + " working" : "all agents ready"}</span>
      <span>${fmt(c.complete)} done</span>${c.failed ? `<span class="bad">${c.failed} failed</span>` : ""}`;
  }

  /* ---------- the brain overlay ---------- */
  let layer = null, geo = {};
  function mount() {
    const stage = $("#stage");
    if (!stage || !window.brainNet || $(".nx-layer", stage)) return;
    layer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    layer.setAttribute("class", "nx-layer"); layer.setAttribute("aria-label", "NETHER agents and sub-agents");
    stage.append(layer);
    brainNet.onView(draw);
    drawn = ""; status(); draw();
  }
  let drawn = "";
  function draw(force) {
    const stage = $("#stage");
    if (!layer || !stage || !stage.contains(layer) || !window.brainNet || !sys) return;
    const S = stage.getBoundingClientRect();
    const key = JSON.stringify([sys.agents.map(a => [a.state, a.subs.map(s => s.state)]), brainNet.anchor(0.53, 0.48), S.width, S.height]);
    if (key === drawn && force !== true) return;      // only redraw when a state or the view changed (keeps hover alive)
    drawn = key;
    layer.setAttribute("viewBox", `0 0 ${S.width} ${S.height}`);
    const [cx, cy] = brainNet.anchor(0.53, 0.48), k = Math.min(1.25, Math.max(0.75, S.width / 1400));
    geo = {};
    let tracts = "", dend = "", nodes = "";
    sys.agents.forEach(a => {
      const [x, y] = brainNet.anchor(a.ax, a.ay), n = a.subs.length;
      const toward = Math.atan2(cy - y, cx - x), spread = Math.PI * 1.25;
      geo[a.key] = {x, y, subs: {}};
      a.subs.forEach((s, i) => {                     // dendrites fan inward, away from the label, alternating reach
        const t = toward - spread / 2 + spread * (n > 1 ? i / (n - 1) : 0.5), R = (34 + (i % 2) * 16) * k;
        const sx = x + Math.cos(t) * R, sy = y + Math.sin(t) * R, bend = (i % 2 ? 9 : -9) * k;
        const mx = (x + sx) / 2 - Math.sin(t) * bend, my = (y + sy) / 2 + Math.cos(t) * bend;
        const d = `M${x.toFixed(1)},${y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${sx.toFixed(1)},${sy.toFixed(1)}`;
        geo[a.key].subs[s.key] = d;
        dend += `<path class="nx-dend ${s.state}" d="${d}"/>`;
        const lx = Math.cos(t) >= 0 ? 8 : -8;
        nodes += `<g class="nx-sub ${s.state}" data-sub="${a.key}:${s.key}" tabindex="0" role="button" aria-label="${esc(a.name)} → ${esc(s.name)}: ${STATE[s.state]}">
          <circle class="nx-hit" cx="${sx}" cy="${sy}" r="9"/><circle class="nx-soma" cx="${sx}" cy="${sy}" r="${(s.page ? 4.2 : 3.2) * k}"/>
          <text x="${sx + lx}" y="${sy + 3.5}" text-anchor="${lx > 0 ? "start" : "end"}">${esc(s.name)}</text></g>`;
      });
      nodes += `<g class="nx-agent ${a.state}" data-agent="${a.key}" tabindex="0" role="button" aria-label="${esc(a.name)} agent: ${STATE[a.state]}">
          <circle class="nx-glow" cx="${x}" cy="${y}" r="${20 * k}"/><circle class="nx-core" cx="${x}" cy="${y}" r="${8 * k}"/>
          <circle class="nx-ring" cx="${x}" cy="${y}" r="${13 * k}"/></g>`;
    });
    TRACTS.forEach(([f, t]) => {                    // tracts arc through the brain's interior
      const A = geo[f], B = geo[t]; if (!A || !B) return;
      const mx = (A.x + B.x) / 2 * 0.55 + cx * 0.45, my = (A.y + B.y) / 2 * 0.55 + cy * 0.45;
      const d = `M${A.x.toFixed(1)},${A.y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${B.x.toFixed(1)},${B.y.toFixed(1)}`;
      geo[`${f}>${t}`] = d; tracts += `<path class="nx-tract" d="${d}"/>`;
    });
    layer.innerHTML = `<g>${tracts}</g><g>${dend}</g><g>${nodes}</g>`;
  }
  /* impulses: resting traffic along tracts, rapid firing inside working agents */
  const onBrain = () => document.body.classList.contains("on-brain") && !document.hidden && layer && window.pulse;
  setInterval(() => {
    if (!onBrain() || !sys) return;
    const keys = Object.keys(geo).filter(k => k.includes(">"));
    if (keys.length) pulse(geo[keys[Math.floor(Math.random() * keys.length)]], 1600, "faint");
  }, 1900);
  setInterval(() => {
    if (!onBrain() || !sys) return;
    sys.agents.filter(a => a.state === "working").forEach(a => {
      const subs = a.subs.filter(s => s.state === "working"), pick = (subs.length ? subs : a.subs)[Math.floor(Math.random() * (subs.length || a.subs.length))];
      const d = geo[a.key]?.subs[pick.key]; if (d) pulse(d, 520, "work");
    });
  }, 650);
  function handoffs(s) {                            // finished work travels to the next agent
    s.agents.forEach(a => {
      const was = prevLast[a.key], now = a.last;
      if (was && now && (now.id !== was.id || now.status !== was.status) && now.status === "complete" && onBrain()) {
        const nx = FLOW[a.key], d = geo[`${a.key}>${nx}`], to = s.agents.find(x => x.key === nx);
        if (d) pulse(d, 900).then(() => to && brainNet.fire(to.ax, to.ay));
      }
      prevLast[a.key] = now ? {id: now.id, status: now.status} : null;
    });
  }
  setInterval(() => { if (document.body.classList.contains("on-brain")) mount(); }, 600);
  setInterval(() => { if (!document.hidden) refresh(); }, 4000);
  refresh();

  /* ---------- a sub-agent, up close ---------- */
  async function retry(t) {
    const r = t.retry || {};
    try {
      if (r.kind === "intel") toast((await post("/api/intel/run", {topic: r.topic})).reply);
      else if (r.kind === "draft") toast((await post("/api/make/draft", {topic: r.topic})).reply);
      else if (r.kind === "redraft" || r.kind === "redraft_long") toast((await post("/api/make/redraft", {id: r.id, notes: r.notes})).reply);
      else if (r.kind === "draft_long") toast((await post("/api/make/draft", {topic: r.topic, kind: "long"})).reply);
      else if (r.kind === "daily") toast((await post("/api/daily/run", {})).reply);
      else if (r.kind === "long") { toast((await post("/api/long/render", {id: r.id})).reply); watchLong(); }
      else if (r.action) runJob(r.action, r.id || "");
      setTimeout(refresh, 600);
    } catch (e) { toast(e.message); }
  }
  async function subSheet(akey, skey) {
    if (!sys) await refresh();
    const a = sys.agents.find(x => x.key === akey), s = a?.subs.find(x => x.key === skey); if (!s) return;
    const tasks = await get("/api/tasks").catch(() => []);
    const owner = s.last && tasks.find(t => t.id === s.last.id || t.steps.some(x => x.id === s.last.id));
    sheet(`<div class="nx-sheet"><div class="nx-head">${glyph(a, s.key, 34)}<span class="nx-meta">${esc(a.name)} agent · ${esc(a.lobe)} · <span class="st-${s.state}">${STATE[s.state]}</span></span></div>
      <h2>${esc(s.name)}</h2><p>${esc(s.what)}</p>
      ${s.recent.length ? `<div class="nx-hist"><span class="k">Last ${s.recent.length} runs</span>${pips(s.recent, s.name + " runs")}</div>` : ""}
      <div class="nx-last">${s.last ? `<span class="k">Last task</span><b>${esc(s.last.title)}</b> <span class="nx-meta">${esc(s.last.status)} ${ago(s.last.finished)}</span>
        ${s.last.error ? `<pre class="nx-err">${esc(s.last.error.split("\n").slice(-10).join("\n"))}</pre>` : ""}` : `<span class="nx-meta">Hasn't run yet.</span>`}</div>
      <div class="row-end">${owner && owner.status === "failed" && owner.retry ? `<button class="btn primary" id="nx-sr">Retry</button>` : ""}
        ${s.page ? `<button class="btn ${owner && owner.status === "failed" ? "" : "primary"}" data-go="${esc(s.page)}" data-close>Open ${esc(s.name)}</button>` : ""}
        <button class="btn" data-go="${esc(akey)}" data-close>${esc(a.name)} hub</button><button class="btn" data-close>Close</button></div></div>`,
      (el, close) => { el.classList.add("nx-wide"); const b = $("#nx-sr", el); if (b) b.onclick = () => { close(); retry(owner); }; });
  }

  /* ---------- hubs: every page lives inside the agent that owns it ---------- */
  function hub(routeName) {
    const akey = OWNER[routeName]; if (!akey) return;
    document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.go === akey));
    const page = main.firstElementChild; if (!page || !sys || page.querySelector(".hub")) return;
    const a = sys.agents.find(x => x.key === akey); if (!a) return;
    const tabs = HUBS[akey] || [];
    page.classList.add("in-hub");
    page.insertAdjacentHTML("afterbegin", `<div class="hub">
      <div class="hub-top">${glyph(a)}<div><b>${esc(a.name.toUpperCase())}</b><div class="nx-meta">${esc(a.lobe)} · ${esc(a.role)} · <span class="st-${a.state}">${STATE[a.state]}</span></div></div>${pips(a.recent)}</div>
      ${tabs.length > 1 ? `<div class="hub-tabs">${tabs.map(([r, l]) => `<button class="${r === routeName ? "on" : ""}" data-go="${r}">${l}</button>`).join("")}</div>` : ""}
      <div class="hub-subs">${a.subs.map(s => `<button class="nx-chip ${s.state}" data-sub="${akey}:${s.key}" title="${esc(s.what)}">${esc(s.name)}</button>`).join("")}</div></div>`);
  }
  const ORIG = {};
  function wrap(name) {
    const f = window.PAGES[name]; if (!f || ORIG[name]) return;
    ORIG[name] = f;
    window.PAGES[name] = async () => { if (!sys) await refresh(); await ORIG[name](); hub(name); if (name === "ideas") ideasExtras(); };
  }
  const _onRoute = window.onRoute;
  window.onRoute = name => { _onRoute && _onRoute(name);
    document.querySelectorAll(".scrim").forEach(s => s.remove());   // a sheet never outlives the page it was opened on
    if (name === "video") setTimeout(() => document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.go === "production")), 0); };
  function ideasExtras() {                       // every idea can go straight to the Content agent
    main.querySelectorAll("[data-next]").forEach(b => { if (b.nextElementSibling?.dataset?.nxMake) return;
      b.insertAdjacentHTML("afterend", `<button class="btn small" data-nx-make="${esc(b.dataset.hook)}" title="Content researches and writes it now; you approve before it's built">Draft now</button>`); });
  }

  /* ---------- Business → Money ---------- */
  async function pageMoney() {
    const m = await get("/api/money"), s = m.settings;
    const meter = (label, value, goal, note, eta) => { const pct = Math.min(100, value / goal * 100);
      return `<div class="nx-meter"><div class="nx-head"><b>${esc(label)}</b><span class="nx-meta">${fmt(value)} of ${fmt(goal)} · ${pct.toFixed(pct < 1 ? 2 : 0)}%</span></div>
        <span class="nx-mbar" role="img" aria-label="${esc(label)}: ${pct.toFixed(1)}%"><i style="width:${Math.max(pct, 0.6)}%"></i></span>
        <span class="nx-meta">${esc(note || "")}${eta ? ` · at this pace: ${esc(eta)}` : ""}</span></div>`; };
    const g = Object.fromEntries((m.goals || []).map(x => [x.key, x]));
    const routes = g.subs ? `
      <div class="nx-two nx-routes"><div class="card nx-route"><span class="k">Route 1 · Shorts</span>
          ${meter("Subscribers", g.subs.value, g.subs.goal, g.subs.note, g.subs.eta)}${g.views ? meter("Shorts views, 90 days", g.views.value, g.views.goal, g.views.note, g.views.eta) : ""}</div>
        <div class="card nx-route"><span class="k">Route 2 · Long-form</span>
          ${meter("Subscribers", g.subs.value, g.subs.goal, "Same 1,000.", g.subs.eta)}
          ${meter("Watch hours, 12 months", m.watch_hours_est, m.watch_goal, `Rough estimate from ${m.long_videos} long-form video${m.long_videos === 1 ? "" : "s"} at a typical 35% view duration — Studio → Earn has the real number.`)}</div></div>
      <p class="nx-meta">Shorts pay ~$0.01–0.10 per 1,000 views; long-form pays far more per view. That's why the weekly episode matters.</p>`
      : `<div class="card caught"><b>No channel numbers yet</b>Refresh numbers in Analytics.</div>`;
    const streams = m.streams.map(x => `<li><span class="pill ${x.on ? "live" : ""}">${x.on ? "On" : "Not set up"}</span> <b>${esc(x.name)}</b> <span class="nx-meta">— ${esc(x.how)}</span></li>`).join("");
    const setup = m.setup.map(x => `<li class="${x.done ? "on" : ""}"><button class="check ${x.done ? "on" : ""}" data-step="setup:${esc(x.key)}" aria-pressed="${x.done}" aria-label="Done: ${esc(x.title)}"></button>
        <div><b>${esc(x.title)}</b><div class="nx-meta">${esc(x.how)}</div></div></li>`).join("");
    const linkLines = (s.links || []).map(l => `${l.label} | ${l.url}${l.lanes?.length ? " | " + l.lanes.join(",") : ""}`).join("\n");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Money</h1><p>Two ways YouTube starts paying, and the income that doesn't wait for it — ads are only 30–50% of a successful faceless channel's money.</p></div>
        <button class="btn" id="nx-kit">Build media kit</button></div>
      <h2>Getting paid by YouTube</h2>${routes}
      <h2>Income streams</h2><div class="card nx-streams"><ul>${streams}</ul></div>
      <div class="nx-two"><div>
        <h2>Links in every description</h2>
        <form class="card nx-bform" id="nx-bform">
          <label><span class="k">Amazon Associates tag</span><input name="amazon_tag" value="${esc(s.amazon_tag)}" placeholder="e.g. nethermind-20"></label>
          <label><span class="k">Newsletter signup link</span><input name="newsletter_url" value="${esc(s.newsletter_url)}" placeholder="https://…"></label>
          <label><span class="k">Sponsor contact email (media kit)</span><input name="sponsor_email" value="${esc(s.sponsor_email)}" placeholder="you@…"></label>
          <label><span class="k">Other links — one per line: Label | https://… | lanes (optional, e.g. marvel,anime)</span><textarea name="links" rows="3">${esc(linkLines)}</textarea></label>
          <label><span class="k">Affiliate disclosure (Amazon and the FTC require it)</span><input name="disclosure" value="${esc(s.disclosure)}"></label>
          <div class="row-end"><button class="btn primary">Save &amp; update unposted videos</button></div>
          <p class="nx-meta">Each video gets a search link for its own source material (e.g. the collected editions it talks about). Posted videos keep what went out.</p></form>
      </div><div>
        <h2>One-time setup</h2><div class="card nx-setup"><ul>${setup}</ul></div>
      </div></div></div>`;
    $("#nx-bform").onsubmit = async e => { e.preventDefault(); const f = new FormData(e.target);
      const links = String(f.get("links") || "").split("\n").map(l => l.split("|").map(x => x.trim())).filter(p => p[1])
        .map(([label, url, lanes]) => ({label, url, lanes: (lanes || "").split(",").map(x => x.trim().toLowerCase()).filter(Boolean)}));
      try { toast((await post("/api/business/settings", {amazon_tag: f.get("amazon_tag"), newsletter_url: f.get("newsletter_url"),
          sponsor_email: f.get("sponsor_email"), disclosure: f.get("disclosure"), links})).reply); route(); } catch (err) { toast(err.message); } };
    $("#nx-kit").onclick = async () => { try { const r = await post("/api/business/kit", {}); toast(r.reply);
      const w = window.open(URL.createObjectURL(new Blob([r.html], {type: "text/html"})), "_blank"); if (!w) toast("Saved to out/media_kit.html"); } catch (err) { toast(err.message); } };
  }

  /* ---------- Intelligence → Brief: what to make next, and why ---------- */
  const LANE = {marvel: "Marvel & comics", anime: "Anime", gaming: "Gaming", space: "Space", ocean: "Ocean", creature: "Creatures", other: "Other"};
  async function pageBrief() {
    const b = await get("/api/intel/brief");
    const max = Math.max(1, ...b.lanes.map(l => l.avg), b.channel_avg);
    const lanes = b.lanes.length ? `<div class="nx-lanes" role="list">${b.lanes.map(l => `<div class="nx-lane" role="listitem" title="${esc(LANE[l.lane] || l.lane)}: ${fmt(l.avg)} avg views over ${l.videos} video${l.videos > 1 ? "s" : ""} (${l.ratio}× your channel average)">
          <span class="nx-ln">${esc(LANE[l.lane] || l.lane)}</span>
          <span class="nx-lbar"><i style="width:${(l.avg / max * 100).toFixed(1)}%"></i><em style="left:${(b.channel_avg / max * 100).toFixed(1)}%"></em></span>
          <span class="nx-lv"><b>${fmt(l.avg)}</b> · ${l.ratio}× · ${l.videos} vid${l.videos > 1 ? "s" : ""}</span></div>`).join("")}
        <div class="nx-meta nx-lnote"><em class="nx-avgkey"></em> your channel average: ${fmt(b.channel_avg)} views per video · lanes need 2+ videos to count</div></div>`
      : `<p class="nx-meta">No numbers yet — Refresh numbers in Analytics, then this fills in.</p>`;
    const mix = Object.keys(b.mix).length ? `<div class="nx-mix">${Object.entries(b.mix).sort((a, c) => c[1] - a[1]).map(([k, n]) => `<span class="nx-chip">${esc(LANE[k] || k)} × ${n}</span>`).join("")}</div>
        <p class="nx-meta">7 Shorts a week, weighted by how each lane really performs — every proven lane keeps at least one slot so it can keep proving itself.</p>` : "";
    const recs = b.recommendations.map((r, i) => `<div class="card nx-rec">
        <div class="nx-head">${ring(r.score, r.score >= 70 ? "good" : r.score >= 50 ? "ok" : "low")}<div><span class="k">#${i + 1} · ${esc(LANE[r.lane] || r.lane)} · ${esc(r.verdict)}</span><b class="nx-rt">${esc(r.topic)}</b></div></div>
        <ul class="nx-reasons">${r.why.map(w => `<li>${esc(w)}</li>`).join("")}${r.failed.length ? `<li class="bad">${esc(r.failed.join(", "))} scout failed — score is partial</li>` : ""}</ul>
        <div class="nx-call"><input class="nx-reason" placeholder="Why? (optional — it learns from this)" maxlength="300">
          <button class="btn small primary" data-nx-go="short" data-slug="${esc(r.slug)}" data-topic="${esc(r.topic)}">Make a Short</button>
          <button class="btn small" data-nx-go="long" data-slug="${esc(r.slug)}" data-topic="${esc(r.topic)}">Long-form</button>
          <button class="btn small" data-nx-decide="skip" data-slug="${esc(r.slug)}">Not for us</button></div></div>`).join("");
    const outl = b.breakouts.map(o => `<li><a href="${esc(o.url)}" target="_blank" rel="noopener">${esc(o.title)}</a>
        <span class="nx-meta">${esc(o.channel)} · ${fmt(o.views)} views on ${o.subs != null ? fmt(o.subs) + " subs" : "a small channel"} · found investigating “${esc(o.topic)}”</span></li>`).join("");
    const wdiff = Object.entries(b.weights).filter(([k, v]) => Math.abs(v - (b.default[k] || 0)) >= 0.5).map(([k, v]) => `${COMP[k] || k} ${v > b.default[k] ? "↑" : "↓"} ${Math.round(v)}`);
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Brief</h1><p>What to make next and why — from your real numbers, YouTube demand, what small channels are winning with, and your own calls.</p></div>
        <div class="nx-counts"><span>${b.backlog.scored} of ${b.backlog.open} ideas scored</span><span>${b.decided} calls made</span><span>${b.linked} checked against results</span></div></div>
      <h2>Make next</h2>
      ${recs || `<div class="card caught"><b>Nothing scored and waiting</b>The daily run scouts 3 backlog ideas every morning — or <button class="link" data-go="investigate">investigate one now</button>.</div>`}
      <div class="nx-two"><div>
        <h2>Your lanes</h2><div class="card nx-lanecard">${lanes}${mix ? `<span class="k">Suggested weekly mix</span>${mix}` : ""}</div>
      </div><div>
        <h2>Working elsewhere</h2><div class="card nx-out">${outl ? `<p class="nx-meta">Small channels (under 100k subs) that broke 100k views on topics you investigated — proof the topic can win without a big audience.</p><ul class="nx-top">${outl}</ul>` : `<p class="nx-meta">Breakouts show up here as the scouts find them.</p>`}</div>
        <h2>What it's learned</h2><div class="card nx-learned">
          <ul class="nx-reasons">${b.lessons.map(l => `<li>${esc(l)}</li>`).join("") || "<li>Nothing yet — every Make it / Not for us call and every posted result teaches it.</li>"}</ul>
          <p class="nx-meta">${wdiff.length ? "Scoring has shifted from real results: " + esc(wdiff.join(" · ")) : "Scoring still at its starting weights — it moves once scorecards are checked against real views."}</p>
          <button class="link" data-go="investigate">Scorecards &amp; weights ›</button></div>
      </div></div></div>`;
  }

  /* ---------- Intelligence → Investigate ---------- */
  const COMP = {demand: "Demand", competition: "Competition", fit: "Channel fit", taste: "Your taste", visuals: "Visuals", sources: "Sources"};
  const bar = v => v == null ? `<span class="nx-meta">failed</span>` : `<span class="nx-bar"><i style="width:${Math.round(v * 100)}%"></i></span>`;
  function scorecard(c) {
    const comps = Object.entries(c.components).map(([k, v]) => `<div class="nx-comp"><span>${COMP[k] || k}</span>${bar(v.score)}<span class="nx-meta">${Math.round(v.weight)} pts</span></div>`).join("");
    const d = c.decision;
    const call = d ? `<div class="nx-decided ${d.choice}">${d.choice === "make" ? "You said: make it" : "You said: not for us"}${d.reason ? ` — “${esc(d.reason)}”` : ""}
        ${c.made_as ? `<br>Made as <button class="link" data-open="${esc(c.made_as)}">${esc(c.made_as)}</button>${c.views != null ? ` · ${fmt(c.views)} views so far` : ""}`
          : d.choice === "make" ? ` <button class="btn small primary" data-nx-make="${esc(c.topic)}">Draft it now</button>` : ""}</div>`
      : `<div class="nx-call"><input class="nx-reason" placeholder="Why? (optional — NETHER learns from this)" maxlength="300">
         <button class="btn small primary" data-nx-decide="make" data-slug="${esc(c.slug)}">Make it</button>
         <button class="btn small" data-nx-decide="skip" data-slug="${esc(c.slug)}">Not for us</button></div>`;
    const top = (c.evidence?.demand?.top || []).slice(0, 3).map(v => `<li><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a> <span class="nx-meta">${esc(v.channel)} · ${fmt(v.views)}</span></li>`).join("");
    return `<div class="card nx-score">
      <div class="nx-head">${ring(c.score, c.score >= 70 ? "good" : c.score >= 50 ? "ok" : "low")}
        <div><b>${esc(c.topic)}</b><div class="nx-meta">${esc(c.verdict)} · ${esc(c.lane)} · ${ago(c.at)}</div></div></div>
      <div class="nx-comps">${comps}</div>
      <ul class="nx-reasons">${c.reasons.map(r => `<li>${esc(r)}</li>`).join("")}${Object.entries(c.failed || {}).map(([k, e]) => `<li class="bad">${esc(k)} scout failed: ${esc(e)}</li>`).join("")}</ul>
      ${top ? `<details><summary>Top similar Shorts</summary><ul class="nx-top">${top}</ul></details>` : ""}
      ${call}</div>`;
  }
  async function pageInvestigate() {
    const [L, s] = await Promise.all([get("/api/learning"), get("/api/system")]);
    const wrows = Object.entries(L.weights).map(([k, v]) => { const d = v - (L.default[k] || 0);
      return `<div class="nx-comp"><span>${COMP[k] || k}</span><span class="nx-bar"><i style="width:${Math.min(100, v * 2.5)}%"></i></span><span class="nx-meta">${Math.round(v)} pts${Math.abs(d) >= 0.5 ? ` (${d > 0 ? "+" : ""}${d.toFixed(1)})` : ""}</span></div>`; }).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Investigate</h1><p>Give Intelligence a topic. Five scouts check real demand, competition, how the lane does on your channel, usable visuals and sources — then you make the call.</p></div></div>
      <form class="card nx-run" id="nx-run"><input id="nx-topic" placeholder="e.g. Wolverine's healing factor vs the axolotl" maxlength="120" ${s.investigating ? "disabled" : ""}>
        <button class="btn primary" ${s.investigating ? "disabled" : ""}>${s.investigating ? "Investigating…" : "Investigate"}</button></form>
      ${s.investigating ? `<p class="nx-meta nx-live">Scouts are working on “${esc(s.investigating)}” — watch them fire on the brain.</p>` : ""}
      <div class="nx-two"><div><h2>Scorecards</h2>${L.cards.map(scorecard).join("") || `<div class="card caught"><b>No investigations yet</b>Try a topic from your backlog.</div>`}</div>
      <div><h2>What NETHER has learned</h2><div class="card nx-learned">
        <span class="k">How the score is weighted now</span>${wrows}
        <ul class="nx-reasons">${L.lessons.map(l => `<li>${esc(l)}</li>`).join("") || "<li>Nothing yet — investigate topics and give each one your call.</li>"}</ul>
        <p class="nx-meta">Weights start even-handed and move (max ±25% a run) only when real views back it. Lessons also go to LEARNINGS.md for the daily run.</p>
        <button class="btn small" id="nx-relearn">Re-check against latest numbers</button></div></div></div></div>`;
    $("#nx-run").onsubmit = async e => { e.preventDefault(); const t = $("#nx-topic").value.trim(); if (!t) return;
      try { toast((await post("/api/intel/run", {topic: t})).reply); watchIntel(); go("investigate"); route(); } catch (err) { toast(err.message); } };
    $("#nx-relearn").onclick = async () => { try { toast((await post("/api/learning/run", {})).reply); route(); } catch (err) { toast(err.message); } };
    if (s.investigating) watchIntel();
  }
  let wI = null;
  function watchIntel() { clearInterval(wI); wI = setInterval(async () => { const s = await get("/api/system"); if (s.investigating) return;
    clearInterval(wI); toast("Scorecard ready."); if (location.hash === "#investigate" || location.hash === "#intelligence") route(); }, 2500); }

  /* ---------- Content → Make: draft, approve, build ---------- */
  let makeKind = "short";
  const KINDS = {short: ["Short", "45–70s vertical · 3–6 min to draft"], long: ["Long-form", "10–12 min 16:9 episode in chapters · 8–15 min to draft"],
                 iceberg: ["Iceberg", "long-form essay, 5 tiers of obscurity (e.g. The Marvel Iceberg)"]};
  async function pageMake() {
    const [d, ideas, L] = await Promise.all([get("/api/drafts"), get("/api/ideas").catch(() => ({sections: []})), get("/api/learning").catch(() => ({cards: []}))]);
    const picks = [];
    if (ideas.next) picks.push([ideas.next.hook, "pinned: make this next"]);
    L.cards.filter(c => c.decision?.choice === "make" && !c.made_as).slice(0, 3).forEach(c => picks.push([c.topic, `scorecard ${c.score}/100`]));
    (ideas.sections.find(s => s.name.startsWith("Intelligence picks"))?.items || []).filter(i => !i.dismissed).slice(0, 2).forEach(i => picks.push([i.hook, "Intelligence pick"]));
    if (makeKind !== "short") ideas.sections.flatMap(s => s.items).filter(i => !i.made && !i.dismissed && /iceberg/i.test(i.hook)).slice(0, 3).forEach(i => picks.push([i.hook, "iceberg idea"]));
    const seen = new Set(), uniq = picks.filter(([h]) => !seen.has(h) && seen.add(h)).slice(0, 6);
    const drafts = d.drafts.map(x => `<button class="card nx-draft" data-go="draft/${esc(x.id)}">
        <div><b>${esc(x.title || x.topic)}</b> <span class="pill ${x.kind === "long" ? "scheduled" : ""}">${x.kind === "long" ? `Long-form · ${x.minutes} min` : "Short"}</span>
          <div class="nx-meta">${x.kind === "long" ? `${x.chapters.length} chapters` : `${x.lines.length} lines · retention check ${x.check ? x.check.score + "/10" : "–"}`} · ${ago(x.at)}</div></div>
        <span class="btn small primary">Read &amp; approve</span></button>`).join("");
    const longs = d.episodes.filter(e => e.kind === "long"), recaps = d.episodes.filter(e => e.kind !== "long");
    const epCard = e => `<div class="card nx-ep">
          <div class="nx-head"><b>${esc(e.title)}</b><span class="pill ${e.rendered ? "live" : ""}">${e.rendering ? "Rendering…" : e.rendered ? "Rendered" : e.kind === "long" ? "Approved" : "Planned"}</span>${e.style === "iceberg" ? `<span class="pill">Iceberg</span>` : ""}</div>
          <ol class="nx-chaps">${e.chapters.map(c => `<li>${esc(c)}</li>`).join("")}</ol>
          ${e.timestamps ? `<pre class="rt-pre nx-ts">${esc(e.timestamps)}</pre>` : ""}
          <div class="row-end">${e.rendered ? `<button class="btn primary small" data-open="${esc(e.video)}">Review the video</button>` : ""}
            <button class="btn small" data-nx-long="${esc(e.id)}" ${d.rendering ? "disabled" : ""}>${e.rendering ? "Rendering…" : e.rendered ? "Re-render" : "Render"}</button>
            ${e.kind === "long" ? (e.shorts.length ? `<span class="nx-meta">${e.shorts.length} Shorts cut</span>` : `<button class="btn small" data-nx-cut="${esc(e.id)}">Cut Shorts from chapters</button>`) : ""}
            ${e.plan ? `<details class="nx-plan"><summary>Script</summary><pre class="rt-pre">${esc(e.plan)}</pre></details>` : ""}</div></div>`;
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Make</h1><p>Content researches the facts, writes the script and packaging, then stops for you. Edit any line, approve it, and Production builds it. Nothing posts without you.</p></div></div>
      <div class="nx-kind" role="radiogroup">${Object.entries(KINDS).map(([k, [l, sub]]) => `<button role="radio" aria-checked="${makeKind === k}" class="${makeKind === k ? "on" : ""}" data-nx-kind="${k}"><b>${l}</b><span>${sub}</span></button>`).join("")}</div>
      <form class="card nx-run" id="nx-make"><input id="nx-mtopic" placeholder="${makeKind === "short" ? "What's the Short about? e.g. The Kamehameha is named after a Hawaiian king" : makeKind === "iceberg" ? "The iceberg: e.g. The Lost Marvel Games Iceberg" : "The episode: e.g. How Marvel almost went bankrupt — and the movie deal that saved it"}" maxlength="160" ${d.busy ? "disabled" : ""}>
        <button class="btn primary" ${d.busy ? "disabled" : ""}>${d.busy ? "Writing…" : "Draft it"}</button></form>
      ${d.busy ? `<p class="nx-meta nx-live">Content is ${esc(d.busy)} — watch it fire on the brain.</p>` : ""}
      ${makeKind === "short" && !d.busy ? `<div class="row-end nx-batch"><span class="nx-meta">Batching is how faceless channels stay consistent — review them in one sitting.</span><button class="btn small" id="nx-batch">Draft a week (5 Shorts)</button></div>` : ""}
      ${uniq.length ? `<div class="nx-picks"><span class="k">Suggested</span>${uniq.map(([h, why]) => `<button class="nx-chip" data-nx-make="${esc(h)}" ${d.busy ? "disabled" : ""} title="${esc(why)}">${esc(h)}</button>`).join("")}</div>` : ""}
      <h2>Scripts waiting for you</h2>${drafts || `<div class="card caught"><b>Nothing waiting</b>Draft one above — the daily run drafts a Short every morning and a long-form on Sundays.</div>`}
      <h2>Long-form episodes</h2>${longs.map(epCard).join("") || `<div class="card caught"><b>No long-form yet</b>Pick Long-form or Iceberg above. Sundays, the daily run drafts one for you to approve.</div>`}
      <details class="nx-recap"><summary>Recap: stitch this week's Shorts together (not a real long-form)</summary>
        <div class="card nx-week"><p>Joins the week's finished Shorts with chapter cards. Useful as a compilation, not as the weekly episode.</p>
        <div class="row-end"><button class="btn small" id="nx-week">Plan a recap</button></div></div>${recaps.map(epCard).join("")}</details></div>`;
    $("#nx-make").onsubmit = async e => { e.preventDefault(); make($("#nx-mtopic").value.trim()); };
    const bt = $("#nx-batch"); if (bt) bt.onclick = async () => { try { toast((await post("/api/make/batch", {n: 5})).reply); watchDraft(); route(); } catch (err) { toast(err.message); } };
    $("#nx-week").onclick = async () => { try { toast((await post("/api/episode/week", {})).reply); route(); } catch (err) { toast(err.message); } };
    if (d.busy) watchDraft();
    if (d.rendering) watchLong();
  }
  let wL = null;
  function watchLong() { clearInterval(wL); wL = setInterval(async () => { const d = await get("/api/drafts"); if (d.rendering) return;
    clearInterval(wL); refresh(); toast("Long-form finished — review it.", {label: "Open", run: () => go("make")}); if (["#make", "#content"].includes(location.hash)) route(); }, 5000); }
  async function make(topic) {
    if (!topic) return;
    const kind = makeKind === "short" ? "short" : "long", style = makeKind === "iceberg" ? "iceberg" : "";
    try { toast((await post("/api/make/draft", {topic, kind, style})).reply); watchDraft(); if (location.hash !== "#make") go("make"); else route(); }
    catch (err) { toast(err.message); }
  }
  let wD = null;
  function watchDraft() { clearInterval(wD); wD = setInterval(async () => { const d = await get("/api/drafts"); if (d.busy) return;
    clearInterval(wD); refresh(); toast(d.drafts.length ? "Script ready — read it and approve." : "Drafting stopped — see Control → Task log.", {label: "Open", run: () => go(d.drafts.length ? "draft/" + d.drafts[0].id : "agents")});
    if (["#make", "#content"].includes(location.hash)) route(); }, 3000); }

  async function pageDraft() {
    const id = location.hash.split("/")[1];
    const d = (await get("/api/drafts")).drafts.find(x => x.id === id);
    if (!d) { main.innerHTML = `<div class="page"><div class="caught"><b>That draft isn't waiting any more</b><button class="link" data-go="make">Back to Make</button></div></div>`; return; }
    const long = d.kind === "long", r = d.research || {};
    const words = d.lines.reduce((a, l) => a + l.text.split(/\s+/).length, 0);
    const facts = (r.facts || []).map(f => `<li>${esc(f.claim)} <a href="${esc(f.source_url)}" target="_blank" rel="noopener">${esc(f.source_title || "source")}</a></li>`).join("");
    let lastChap = null;
    const lineRows = d.lines.map((l, i) => {
      const head = long && l.chapter !== lastChap ? `<h3 class="nx-chap">${esc(l.chapter)}</h3>` : ""; lastChap = l.chapter;
      return `${head}<label class="nx-line ${l.long_only ? "long-only" : ""}" id="nx-line-${i}"><span class="nx-meta">${i + 1}${!long && i === 0 ? " · hook" : ""}${l.long_only && long ? " · long-form only" : ""}${l.hero ? ` · on screen: <b>${esc(l.hero.join(" "))}</b>` : ""}</span>
            <textarea data-line="${esc(l.id)}" rows="2">${esc(l.text)}</textarea>
            <span class="nx-lfoot"><span class="nx-vis">${esc(l.kind)}${l.visual ? ": " + esc(l.visual) : ""}</span>
              <span class="nx-voice" data-vline="${esc(l.id)}"><span class="nx-vstat"></span><button type="button" class="btn small" data-rec="${esc(l.id)}">● Record</button></span></span></label>`; }).join("");
    main.innerHTML = `<div class="page wide nx-review">
      <button class="back" data-go="make">‹ Make</button>
      <div class="head"><h1>${esc(d.title || d.topic)}</h1><p>${long ? `Long-form · ${d.chapters.length} chapters · about ${d.minutes} minutes. ` : ""}Drafted ${ago(d.at)} from “${esc(d.topic)}”. Read it, edit any line, then approve — or send it back with notes.</p></div>
      <div class="nx-two"><div>
        <div class="card nx-script"><div class="nx-head"><b>Script</b><span class="nx-meta">${words} words ≈ ${long ? (words / 168).toFixed(1) + " min" : Math.round(words / 2.8) + "s"}</span></div>
          ${long ? `<ol class="nx-chaps">${d.chapters.map(c => `<li>${esc(c)}</li>`).join("")}</ol><p class="nx-meta">Lines marked “long-form only” are left out when a chapter is cut into its own Short.</p>` : pacing(d.lines)}
          <div class="nx-voicebar"><b>🎙 Your voice (optional)</b> <span class="nx-meta" id="nx-vcount"></span>
            <span class="nx-meta">Record any line in your own voice — it replaces the AI voice for that line. YouTube treats a real voice as the clearest sign of original work.</span></div>
          ${lineRows}
          <div class="nx-meta">End card: ${esc(d.end.join(" · "))}</div>
          <div class="row-end"><button class="btn" id="nx-save">Save line edits</button></div></div>
        ${d.title_options.length ? `<div class="card nx-titles"><span class="k">Title</span>${[d.title, ...d.title_options].filter(Boolean).map((t, i) => `<label><input type="radio" name="nx-title" value="${esc(t)}" ${i === 0 ? "checked" : ""}> ${esc(t)}</label>`).join("")}</div>` : ""}
        ${long && d.thumbnails?.length ? `<div class="card nx-titles"><span class="k">Thumbnail words · 3 options, rendered for YouTube's Test &amp; Compare</span>${d.thumbnails.map(th => `<div class="nx-thumbw">${(th.lines || []).map((w, i) => `<b class="${i === (th.accent ?? -1) ? "acc" : ""}">${esc(w)}</b>`).join(" ")}</div>`).join("")}</div>` : ""}
      </div><div>
        <div class="card nx-approve"><button class="btn primary big" id="nx-approve">${long ? "Approve &amp; render" : "Approve &amp; build"}</button>
          <p class="nx-meta">${long ? "Production fetches the real photos and art, renders the 16:9 episode with chapter cards, runs QA, fills in the real YouTube chapter timestamps and renders 3 thumbnails. 20–45 minutes. You review it before anything posts." : "Production fetches the photos, generates the art, renders the Short and its TikTok cut, runs QA and makes the thumbnail. You review the finished video before anything posts."}</p>
          <textarea id="nx-notes" rows="3" placeholder="Or: what should change? e.g. 'open on the 1 cell number', 'less about the comic, more about the worm'"></textarea>
          <div class="row-end"><button class="btn" id="nx-redraft">Redraft with notes</button><button class="btn danger" id="nx-discard">Discard</button></div></div>
        ${d.check ? `<div class="card nx-checkc"><span class="k">Hook &amp; retention check · ${d.check.score}/10</span><ul class="rt-list">${d.check.rows.map(([ok, m]) => `<li class="${ok ? "ok" : "no"}">${ok ? "✓" : "✗"} ${esc(m)}</li>`).join("")}</ul></div>` : ""}
        <div class="card nx-research"><span class="k">Research · every line comes from these</span>
          ${r.angle ? `<p><b>${esc(r.angle)}</b></p>` : ""}
          ${r.promise ? `<p class="nx-meta">Promise: ${esc(r.promise)}</p>` : ""}
          ${r.popular_version ? `<p class="nx-meta">Popular version: ${esc(r.popular_version)}<br>True version: ${esc(r.true_version || "")}</p>` : ""}
          ${r.caveat ? `<p class="nx-meta">Caveat: ${esc(r.caveat)}</p>` : ""}${(r.caveats || []).map(c => `<p class="nx-meta">Caveat: ${esc(c)}</p>`).join("")}
          <ol class="nx-facts">${facts}</ol></div></div></div></div>`;
    const collect = () => { const lines = {}; main.querySelectorAll("[data-line]").forEach(t => lines[t.dataset.line] = t.value); return lines; };
    voiceStatus(id, collect);
    const saveLines = lines => post(long ? "/api/make/lines" : "/api/script", {id, lines});
    $("#nx-save").onclick = async () => { try { const x = await saveLines(collect()); toast(x.changed.length ? `Saved ${x.changed.length} line${x.changed.length > 1 ? "s" : ""}.` : "No changes."); } catch (e) { toast(e.message); } };
    $("#nx-approve").onclick = async () => {
      try {
        await saveLines(collect());
        const t = main.querySelector("input[name=nx-title]:checked"); if (t && t.value !== d.title) await post("/api/choose_title", {id: d.title_pkg || id, title: t.value});
        toast((await post("/api/make/approve", {id})).reply);
        if (long) { watchLong(); go("make"); } else { runJob("build", id); go("production"); }
      } catch (e) { toast(e.message); } };
    $("#nx-redraft").onclick = async () => { try { toast((await post("/api/make/redraft", {id, notes: $("#nx-notes").value})).reply); watchDraft(); go("make"); } catch (e) { toast(e.message); } };
    $("#nx-discard").onclick = () => sheet(`<h3>Discard this draft?</h3><p>The script, packaging and research are deleted.</p><div class="row-end"><button class="btn" data-close>Keep it</button><button class="btn danger" id="nx-dd">Discard</button></div>`,
      (el, close) => { $("#nx-dd", el).onclick = async () => { close(); try { toast((await post("/api/make/discard", {id})).reply); go("make"); } catch (e) { toast(e.message); } }; });
  }

  /* ---------- your voice: record a line in the browser ---------- */
  let rec = null;
  async function voiceStatus(owner, collect) {
    const lines = collect(), st = await post("/api/voice/status", {owner, lines}).catch(() => ({}));
    const ids = Object.keys(lines), n = ids.filter(i => st[i] === "ok").length, c = $("#nx-vcount");
    if (c) c.textContent = `${n} of ${ids.length} lines recorded`;
    ids.forEach(i => { const box = main.querySelector(`[data-vline="${CSS.escape(i)}"]`); if (!box) return;
      const s = st[i], el = $(".nx-vstat", box);
      el.innerHTML = s === "ok" ? `<span class="nx-mine">✓ your voice</span><button type="button" class="link" data-vplay="${esc(i)}">play</button> <button type="button" class="link" data-vdel="${esc(i)}">remove</button>`
        : s === "stale" ? `<span class="bad">line changed — record again</span>` : "";
      $("[data-rec]", box).textContent = s ? "● Re-record" : "● Record"; });
    main.dataset.vowner = owner;
  }
  document.addEventListener("click", async e => {
    const owner = main.dataset.vowner;
    const r = e.target.closest("[data-rec]");
    if (r && owner) {
      e.preventDefault();
      if (rec && rec.line === r.dataset.rec) { rec.mr.stop(); return; }
      if (rec) return toast("Finish the recording that's running first.");
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
        return toast(`This window can't use the microphone. Open ${location.origin}/${location.hash} in Safari or Chrome to record.`);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
        const mr = new MediaRecorder(stream), chunks = [], line = r.dataset.rec;
        mr.ondataavailable = ev => ev.data.size && chunks.push(ev.data);
        mr.onstop = async () => {
          stream.getTracks().forEach(t => t.stop()); r.classList.remove("recording"); rec = null;
          const blob = new Blob(chunks, {type: mr.mimeType || "audio/webm"});
          const data = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob); });
          const text = main.querySelector(`[data-line="${CSS.escape(line)}"]`)?.value || "";
          try { const x = await post("/api/voice/save", {owner, line, text, data, mime: blob.type}); toast(`Saved — ${x.seconds}s in your voice.`); }
          catch (err) { toast(err.message); }
          voiceStatus(owner, () => { const l = {}; main.querySelectorAll("[data-line]").forEach(t => l[t.dataset.line] = t.value); return l; });
        };
        mr.start(); rec = {mr, line}; r.classList.add("recording"); r.textContent = "■ Stop";
        toast("Recording — read the line, then press Stop.");
      } catch (err) { toast("Microphone blocked: allow it for this page, or open it in Safari/Chrome."); }
      return;
    }
    const pl = e.target.closest("[data-vplay]");
    if (pl && owner) { e.preventDefault(); try { new Audio((await post("/api/voice/play", {owner, line: pl.dataset.vplay})).data).play(); } catch (err) { toast(err.message); } return; }
    const dl = e.target.closest("[data-vdel]");
    if (dl && owner) { e.preventDefault(); await post("/api/voice/delete", {owner, line: dl.dataset.vdel}); toast("Removed — the AI voice reads this line.");
      voiceStatus(owner, () => { const l = {}; main.querySelectorAll("[data-line]").forEach(t => l[t.dataset.line] = t.value); return l; }); }
  }, true);

  /* ---------- Control → Task log ---------- */
  async function pageAgents() {
    const [s, tasks] = await Promise.all([get("/api/system"), get("/api/tasks")]);
    sys = s;
    const daily = tasks.find(t => t.agent === "control" && t.sub === "daily");
    const agents = s.agents.map(a => `<div class="card nx-card ${a.state}">
        <div class="nx-head">${glyph(a)}<div><button class="link" data-go="${a.key}"><b>${esc(a.name)}</b></button><div class="nx-meta st-${a.state}">${STATE[a.state]}${a.active ? ` · ${a.active} active` : ""}</div></div>${pips(a.recent)}</div>
        <p class="nx-role">${esc(a.lobe)} · ${esc(a.role)}</p>
        <div class="nx-subs">${a.subs.map(x => `<button class="nx-chip ${x.state}" data-sub="${a.key}:${x.key}">${esc(x.name)}</button>`).join("")}</div></div>`).join("");
    const rows = tasks.map(t => `<div class="card nx-task ${t.status}">
        <div class="nx-head"><span class="nx-state ${t.status === "working" ? "working" : t.status === "failed" ? "failed" : "ready"}"></span>
          <b>${esc(t.title)}</b><span class="pill">${esc(t.agent)}</span><span class="nx-meta">${esc(t.status)} · ${ago(t.finished || t.started)}</span>
          <span class="nx-actions">${t.retry && ["failed", "cancelled"].includes(t.status) ? `<button class="btn small primary" data-nx-retry="${t.id}">Retry</button>` : ""}${t.status === "working" ? `<button class="btn small" data-nx-cancel="${t.id}">Cancel</button>` : ""}</span></div>
        ${pipeline(t.steps)}
        ${(() => { const bad = t.steps.find(x => x.status === "failed"); const e = (bad && bad.error) || (t.status === "failed" && t.error);
           return e ? `<pre class="nx-err">${bad ? `<b>${esc(bad.title)}</b>\n` : ""}${esc(e.split("\n").slice(-8).join("\n"))}</pre>` : ""; })()}
      </div>`).join("");
    window._nxTasks = tasks;
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Task log</h1><p>Every job is a task owned by an agent. When something breaks, the amber step shows where and why — retry it from here.</p></div>
        <div class="nx-counts"><span>${s.counts.working} working</span><span>${fmt(s.counts.complete)} done</span><span class="${s.counts.failed ? "bad" : ""}">${s.counts.failed} failed</span></div></div>
      <div class="card nx-dailyc"><div><b>Daily run</b> <span class="nx-meta">7:00 (+20:30 catch-up) · refresh → learn → scout 3 ideas → draft the next video · Sundays: plan + render the long-form</span>
        <div class="nx-meta">${daily ? `Last: ${esc(daily.status)} ${ago(daily.finished || daily.started)}` : "Hasn't run yet — install it once with ./install_daily.sh"}</div></div>
        <button class="btn small" id="nx-daily">Run now</button></div>
      <div class="nx-grid">${agents}</div>
      <h2>Recent tasks</h2>${rows || `<div class="card caught"><b>No tasks yet</b>Builds, posts, refreshes, drafts and investigations show up here as they run.</div>`}</div>`;
    $("#nx-daily").onclick = async () => { try { toast((await post("/api/daily/run", {})).reply); } catch (e) { toast(e.message); } };
  }

  /* ---------- clicks ---------- */
  document.addEventListener("click", async e => {
    const t = e.target;
    const sub = t.closest("[data-sub]"); if (sub) { e.stopPropagation(); const [a, s] = sub.dataset.sub.split(":"); return subSheet(a, s); }
    const ag = t.closest(".nx-agent");
    if (ag) { e.stopPropagation(); const a = sys?.agents.find(x => x.key === ag.dataset.agent);
      if (a && window.brainNet && !matchMedia("(prefers-reduced-motion: reduce)").matches) await brainNet.fire(a.ax, a.ay);
      return go(ag.dataset.agent); }
    const sl = t.closest("[data-scroll-line]"); if (sl) { const l = $("#nx-line-" + sl.dataset.scrollLine); if (l) { l.scrollIntoView({behavior: "smooth", block: "center"}); l.querySelector("textarea")?.focus(); } return; }
    const gg = t.closest("[data-nx-go]");
    if (gg) { e.stopPropagation(); const reason = gg.closest(".nx-call")?.querySelector(".nx-reason")?.value || "";
      try { await post("/api/intel/decide", {slug: gg.dataset.slug, choice: "make", reason});
            toast((await post("/api/make/draft", {topic: gg.dataset.topic, kind: gg.dataset.nxGo})).reply); watchDraft(); go("make"); }
      catch (err) { toast(err.message); } return; }
    const kd = t.closest("[data-nx-kind]"); if (kd) { makeKind = kd.dataset.nxKind; return route(); }
    const cut = t.closest("[data-nx-cut]");
    if (cut) { e.stopPropagation(); try { toast((await post("/api/episode/shorts", {id: cut.dataset.nxCut})).reply); route(); } catch (err) { toast(err.message); } return; }
    const lg = t.closest("[data-nx-long]");
    if (lg) { e.stopPropagation(); try { toast((await post("/api/long/render", {id: lg.dataset.nxLong})).reply); watchLong(); route(); } catch (err) { toast(err.message); } return; }
    const mk = t.closest("[data-nx-make]"); if (mk) { e.stopPropagation(); return make(mk.dataset.nxMake); }
    const r = t.closest("[data-nx-retry]");
    if (r) { const task = (window._nxTasks || []).find(x => x.id === +r.dataset.nxRetry); if (task) { await retry(task); setTimeout(route, 900); } return; }
    const cx = t.closest("[data-nx-cancel]");
    if (cx) { await post("/api/tasks/cancel", {id: +cx.dataset.nxCancel}); toast("Cancelled — anything already mid-way finishes quietly in the background."); return route(); }
    const dc = t.closest("[data-nx-decide]");
    if (dc) { const reason = dc.closest(".nx-call").querySelector(".nx-reason").value;
      try { toast((await post("/api/intel/decide", {slug: dc.dataset.slug, choice: dc.dataset.nxDecide, reason})).reply); route(); } catch (err) { toast(err.message); } }
  }, true);
  document.addEventListener("keydown", e => { if (e.key !== "Enter" && e.key !== " ") return;
    const n = e.target.closest && e.target.closest(".nx-sub,.nx-agent"); if (n) { e.preventDefault(); n.dispatchEvent(new MouseEvent("click", {bubbles: true})); } });

  /* ---------- register pages ---------- */
  Object.assign(window.PAGES, {money: pageMoney, brief: pageBrief, investigate: pageInvestigate, make: pageMake, draft: pageDraft, agents: pageAgents});
  document.addEventListener("DOMContentLoaded", () => {      // after every extension has registered its pages,
    Object.keys(OWNER).forEach(wrap);                        // before the app's first route (window load)
    Object.entries(HUBS).forEach(([akey, tabs]) => { window.PAGES[akey] = window.PAGES[tabs[0][0]]; });
  });
})();
