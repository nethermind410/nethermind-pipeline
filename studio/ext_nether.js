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
  const HUBS = {intelligence: [["investigate", "Investigate"], ["ideas", "Ideas"]], content: [["make", "Make"]],
    production: [["videos", "Videos"]], publishing: [["calendar", "Calendar"]],
    analytics: [["performance", "Performance"], ["retention", "Retention"]],
    business: [["comments", "Comments"], ["channel", "Monetisation"]], control: [["agents", "Task log"], ["settings", "Settings"]]};
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
  const onBrain = () => document.body.classList.contains("on-brain") && !document.hidden && layer && window.spark;
  setInterval(() => {
    if (!onBrain() || !sys) return;
    const keys = Object.keys(geo).filter(k => k.includes(">"));
    if (keys.length) spark(geo[keys[Math.floor(Math.random() * keys.length)]], 1600, "faint");
  }, 1900);
  setInterval(() => {
    if (!onBrain() || !sys) return;
    sys.agents.filter(a => a.state === "working").forEach(a => {
      const subs = a.subs.filter(s => s.state === "working"), pick = (subs.length ? subs : a.subs)[Math.floor(Math.random() * (subs.length || a.subs.length))];
      const d = geo[a.key]?.subs[pick.key]; if (d) spark(d, 520, "work");
    });
  }, 650);
  function handoffs(s) {                            // finished work travels to the next agent
    s.agents.forEach(a => {
      const was = prevLast[a.key], now = a.last;
      if (was && now && (now.id !== was.id || now.status !== was.status) && now.status === "complete" && onBrain()) {
        const nx = FLOW[a.key], d = geo[`${a.key}>${nx}`], to = s.agents.find(x => x.key === nx);
        if (d) spark(d, 900).then(() => to && brainNet.fire(to.ax, to.ay));
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
      else if (r.kind === "daily") toast((await post("/api/daily/run", {})).reply);
      else if (r.action) runJob(r.action, r.id || "");
      setTimeout(refresh, 600);
    } catch (e) { toast(e.message); }
  }
  async function subSheet(akey, skey) {
    if (!sys) await refresh();
    const a = sys.agents.find(x => x.key === akey), s = a?.subs.find(x => x.key === skey); if (!s) return;
    const tasks = await get("/api/tasks").catch(() => []);
    const owner = s.last && tasks.find(t => t.id === s.last.id || t.steps.some(x => x.id === s.last.id));
    sheet(`<div class="nx-sheet"><div class="nx-head"><span class="nx-state ${s.state}"></span><span class="nx-meta">${esc(a.name)} agent · ${esc(a.lobe)}</span></div>
      <h2>${esc(s.name)}</h2><p>${esc(s.what)}</p>
      <div class="nx-last">${s.last ? `<span class="k">Last task</span><b>${esc(s.last.title)}</b> <span class="nx-meta">${esc(s.last.status)} ${ago(s.last.finished)}</span>
        ${s.last.error ? `<pre class="nx-err">${esc(s.last.error.split("\n").slice(-10).join("\n"))}</pre>` : ""}` : `<span class="nx-meta">Hasn't run yet.</span>`}</div>
      <div class="row-end">${owner && owner.status === "failed" && owner.retry ? `<button class="btn primary" id="nx-sr">Retry</button>` : ""}
        ${s.page ? `<button class="btn ${owner && owner.status === "failed" ? "" : "primary"}" data-go="${esc(s.page)}" data-close>Open ${esc(s.name)}</button>` : ""}
        <button class="btn" data-go="${esc(akey)}" data-close>${esc(a.name)} hub</button><button class="btn" data-close>Close</button></div></div>`,
      (el, close) => { const b = $("#nx-sr", el); if (b) b.onclick = () => { close(); retry(owner); }; });
  }

  /* ---------- hubs: every page lives inside the agent that owns it ---------- */
  function hub(routeName) {
    const akey = OWNER[routeName]; if (!akey) return;
    document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.go === akey));
    const page = main.firstElementChild; if (!page || !sys || page.querySelector(".hub")) return;
    const a = sys.agents.find(x => x.key === akey); if (!a) return;
    const tabs = HUBS[akey] || [];
    page.insertAdjacentHTML("afterbegin", `<div class="hub">
      <div class="hub-top"><span class="nx-state ${a.state}"></span><b>${esc(a.name.toUpperCase())}</b><span class="nx-meta">${esc(a.lobe)} · ${esc(a.role)} · ${STATE[a.state]}</span></div>
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
      <div class="nx-head"><span class="nx-big ${c.score >= 70 ? "good" : c.score >= 50 ? "ok" : "low"}">${c.score}</span>
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
  async function pageMake() {
    const [d, ideas, L] = await Promise.all([get("/api/drafts"), get("/api/ideas").catch(() => ({sections: []})), get("/api/learning").catch(() => ({cards: []}))]);
    const picks = [];
    if (ideas.next) picks.push([ideas.next.hook, "pinned: make this next"]);
    L.cards.filter(c => c.decision?.choice === "make" && !c.made_as).slice(0, 3).forEach(c => picks.push([c.topic, `scorecard ${c.score}/100`]));
    (ideas.sections.find(s => s.name.startsWith("Intelligence picks"))?.items || []).filter(i => !i.dismissed).slice(0, 2).forEach(i => picks.push([i.hook, "Intelligence pick"]));
    const seen = new Set(), uniq = picks.filter(([h]) => !seen.has(h) && seen.add(h)).slice(0, 5);
    const drafts = d.drafts.map(x => `<button class="card nx-draft" data-go="draft/${esc(x.id)}">
        <div><b>${esc(x.title || x.topic)}</b><div class="nx-meta">${x.lines.length} lines · retention check ${x.check ? x.check.score + "/10" : "–"} · ${ago(x.at)}</div></div>
        <span class="btn small primary">Read &amp; approve</span></button>`).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Make</h1><p>Content researches the facts, writes the script and packaging, then stops for you. Edit any line, approve it, and Production builds it. Nothing posts without you.</p></div></div>
      <form class="card nx-run" id="nx-make"><input id="nx-mtopic" placeholder="What's the video about? e.g. The Kamehameha is named after a Hawaiian king" maxlength="160" ${d.busy ? "disabled" : ""}>
        <button class="btn primary" ${d.busy ? "disabled" : ""}>${d.busy ? "Writing…" : "Draft it"}</button></form>
      ${d.busy ? `<p class="nx-meta nx-live">Content is ${esc(d.busy)} — research, script, packaging, check. Usually 3–6 minutes; watch it fire on the brain.</p>` : ""}
      ${uniq.length ? `<div class="nx-picks"><span class="k">Suggested</span>${uniq.map(([h, why]) => `<button class="nx-chip" data-nx-make="${esc(h)}" ${d.busy ? "disabled" : ""} title="${esc(why)}">${esc(h)}</button>`).join("")}</div>` : ""}
      <h2>Scripts waiting for you</h2>${drafts || `<div class="card caught"><b>Nothing waiting</b>Draft one above — or the daily run drafts the next one at 7:00.</div>`}
      <h2>Weekly long-form</h2><div class="card nx-week"><p>Every Sunday the Episode planner turns the week's Shorts into one long-form episode: chapters, script and YouTube chapter timestamps.</p>
        <div class="row-end"><button class="btn" id="nx-week">Plan this week's episode now</button></div>
        ${d.episodes.map(e => `<details><summary>${esc(e.id)}</summary><pre class="rt-pre">${esc(e.plan)}</pre></details>`).join("")}</div></div>`;
    $("#nx-make").onsubmit = async e => { e.preventDefault(); make($("#nx-mtopic").value.trim()); };
    $("#nx-week").onclick = async () => { try { toast((await post("/api/episode/week", {})).reply); route(); } catch (err) { toast(err.message); } };
    if (d.busy) watchDraft();
  }
  async function make(topic) {
    if (!topic) return;
    try { toast((await post("/api/make/draft", {topic})).reply); watchDraft(); if (location.hash !== "#make") go("make"); else route(); }
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
    const r = d.research || {};
    const facts = (r.facts || []).map(f => `<li>${esc(f.claim)} <a href="${esc(f.source_url)}" target="_blank" rel="noopener">${esc(f.source_title || "source")}</a></li>`).join("");
    main.innerHTML = `<div class="page wide nx-review">
      <button class="back" data-go="make">‹ Make</button>
      <div class="head"><h1>${esc(d.title || d.topic)}</h1><p>Drafted ${ago(d.at)} from “${esc(d.topic)}”. Read it, edit any line, then approve — or send it back with notes.</p></div>
      <div class="nx-two"><div>
        <div class="card nx-script"><div class="nx-head"><b>Script</b><span class="nx-meta">${d.lines.reduce((a, l) => a + l.text.split(/\s+/).length, 0)} words ≈ ${Math.round(d.lines.reduce((a, l) => a + l.text.split(/\s+/).length, 0) / 2.8)}s</span></div>
          ${d.lines.map((l, i) => `<label class="nx-line"><span class="nx-meta">${i + 1}${i === 0 ? " · hook" : ""}${l.hero ? ` · on screen: <b>${esc(l.hero.join(" "))}</b>` : ""}</span>
            <textarea data-line="${esc(l.id)}" rows="2">${esc(l.text)}</textarea>
            <span class="nx-vis">${esc(l.kind)}${l.visual ? ": " + esc(l.visual) : ""}</span></label>`).join("")}
          <div class="nx-meta">End card: ${esc(d.end.join(" · "))}</div>
          <div class="row-end"><button class="btn" id="nx-save">Save line edits</button></div></div>
        ${d.title_options.length ? `<div class="card nx-titles"><span class="k">Title</span>${[d.title, ...d.title_options].filter(Boolean).map((t, i) => `<label><input type="radio" name="nx-title" value="${esc(t)}" ${i === 0 ? "checked" : ""}> ${esc(t)}</label>`).join("")}</div>` : ""}
      </div><div>
        <div class="card nx-approve"><button class="btn primary big" id="nx-approve">Approve &amp; build</button>
          <p class="nx-meta">Production fetches the photos, generates the art, renders the Short and its TikTok cut, runs QA and makes the thumbnail. You review the finished video before anything posts.</p>
          <textarea id="nx-notes" rows="3" placeholder="Or: what should change? e.g. 'open on the 1 cell number', 'less about the comic, more about the worm'"></textarea>
          <div class="row-end"><button class="btn" id="nx-redraft">Redraft with notes</button><button class="btn danger" id="nx-discard">Discard</button></div></div>
        ${d.check ? `<div class="card nx-checkc"><span class="k">Hook &amp; retention check · ${d.check.score}/10</span><ul class="rt-list">${d.check.rows.map(([ok, m]) => `<li class="${ok ? "ok" : "no"}">${ok ? "✓" : "✗"} ${esc(m)}</li>`).join("")}</ul></div>` : ""}
        <div class="card nx-research"><span class="k">Research · every line comes from these</span>
          ${r.angle ? `<p><b>${esc(r.angle)}</b></p>` : ""}
          ${r.popular_version ? `<p class="nx-meta">Popular version: ${esc(r.popular_version)}<br>True version: ${esc(r.true_version || "")}</p>` : ""}
          ${r.caveat ? `<p class="nx-meta">Caveat: ${esc(r.caveat)}</p>` : ""}
          <ol class="nx-facts">${facts}</ol></div></div></div></div>`;
    $("#nx-save").onclick = async () => { const lines = {}; main.querySelectorAll("[data-line]").forEach(t => lines[t.dataset.line] = t.value);
      try { const x = await post("/api/script", {id, lines}); toast(x.changed.length ? `Saved ${x.changed.length} line${x.changed.length > 1 ? "s" : ""}.` : "No changes."); } catch (e) { toast(e.message); } };
    $("#nx-approve").onclick = async () => {
      const lines = {}; main.querySelectorAll("[data-line]").forEach(t => lines[t.dataset.line] = t.value);
      try {
        await post("/api/script", {id, lines});
        const t = main.querySelector("input[name=nx-title]:checked"); if (t && t.value !== d.title) await post("/api/choose_title", {id, title: t.value});
        toast((await post("/api/make/approve", {id})).reply); runJob("build", id); go("production");
      } catch (e) { toast(e.message); } };
    $("#nx-redraft").onclick = async () => { try { toast((await post("/api/make/redraft", {id, notes: $("#nx-notes").value})).reply); watchDraft(); go("make"); } catch (e) { toast(e.message); } };
    $("#nx-discard").onclick = () => sheet(`<h3>Discard this draft?</h3><p>The script, packaging and research are deleted.</p><div class="row-end"><button class="btn" data-close>Keep it</button><button class="btn danger" id="nx-dd">Discard</button></div>`,
      (el, close) => { $("#nx-dd", el).onclick = async () => { close(); try { toast((await post("/api/make/discard", {id})).reply); go("make"); } catch (e) { toast(e.message); } }; });
  }

  /* ---------- Control → Task log ---------- */
  const stepRow = s => `<li class="nx-step ${s.status}"><span class="nx-sd"></span><span>${esc(s.title)}${s.agent ? ` <span class="nx-meta">· ${esc(s.agent)}</span>` : ""}</span>
      <span class="nx-meta">${s.status === "working" ? "working…" : esc(s.status)}</span>
      ${s.error ? `<pre class="nx-err">${esc(s.error.split("\n").slice(-8).join("\n"))}</pre>` : ""}</li>`;
  async function pageAgents() {
    const [s, tasks] = await Promise.all([get("/api/system"), get("/api/tasks")]);
    sys = s;
    const daily = tasks.find(t => t.agent === "control" && t.sub === "daily");
    const agents = s.agents.map(a => `<div class="card nx-card ${a.state}">
        <div class="nx-head"><span class="nx-state ${a.state}"></span><button class="link" data-go="${a.key}"><b>${esc(a.name)}</b></button><span class="nx-meta">${STATE[a.state]}${a.active ? ` · ${a.active} active` : ""}</span></div>
        <p class="nx-role">${esc(a.lobe)} · ${esc(a.role)}</p>
        <div class="nx-subs">${a.subs.map(x => `<button class="nx-chip ${x.state}" data-sub="${a.key}:${x.key}">${esc(x.name)}</button>`).join("")}</div></div>`).join("");
    const rows = tasks.map(t => `<div class="card nx-task ${t.status}">
        <div class="nx-head"><span class="nx-state ${t.status === "working" ? "working" : t.status === "failed" ? "failed" : "ready"}"></span>
          <b>${esc(t.title)}</b><span class="pill">${esc(t.agent)}</span><span class="nx-meta">${esc(t.status)} · ${ago(t.finished || t.started)}</span>
          <span class="nx-actions">${t.retry && ["failed", "cancelled"].includes(t.status) ? `<button class="btn small primary" data-nx-retry="${t.id}">Retry</button>` : ""}${t.status === "working" ? `<button class="btn small" data-nx-cancel="${t.id}">Cancel</button>` : ""}</span></div>
        ${t.steps.length ? `<ol class="nx-steps">${t.steps.map(x => stepRow({...x, agent: x.agent !== t.agent ? x.agent : ""})).join("")}</ol>` : t.error ? `<pre class="nx-err">${esc(t.error.split("\n").slice(-8).join("\n"))}</pre>` : ""}
      </div>`).join("");
    window._nxTasks = tasks;
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Task log</h1><p>Every job is a task owned by an agent. When something breaks, the amber step shows where and why — retry it from here.</p></div>
        <div class="nx-counts"><span>${s.counts.working} working</span><span>${fmt(s.counts.complete)} done</span><span class="${s.counts.failed ? "bad" : ""}">${s.counts.failed} failed</span></div></div>
      <div class="card nx-dailyc"><div><b>Daily run</b> <span class="nx-meta">7:00 · refresh → learn → draft the next video · Sundays: plan the episode</span>
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
    const mk = t.closest("[data-nx-make]"); if (mk) { e.stopPropagation(); return make(mk.dataset.nxMake); }
    const r = t.closest("[data-nx-retry]");
    if (r) { const task = (window._nxTasks || []).find(x => x.id === +r.dataset.nxRetry); if (task) { await retry(task); setTimeout(route, 900); } return; }
    const cx = t.closest("[data-nx-cancel]");
    if (cx) { await post("/api/tasks/cancel", {id: +cx.dataset.nxCancel}); toast("Cancelled."); return route(); }
    const dc = t.closest("[data-nx-decide]");
    if (dc) { const reason = dc.closest(".nx-call").querySelector(".nx-reason").value;
      try { toast((await post("/api/intel/decide", {slug: dc.dataset.slug, choice: dc.dataset.nxDecide, reason})).reply); route(); } catch (err) { toast(err.message); } }
  }, true);
  document.addEventListener("keydown", e => { if (e.key !== "Enter" && e.key !== " ") return;
    const n = e.target.closest && e.target.closest(".nx-sub,.nx-agent"); if (n) { e.preventDefault(); n.dispatchEvent(new MouseEvent("click", {bubbles: true})); } });

  /* ---------- register pages ---------- */
  Object.assign(window.PAGES, {investigate: pageInvestigate, make: pageMake, draft: pageDraft, agents: pageAgents});
  document.addEventListener("DOMContentLoaded", () => {      // after every extension has registered its pages,
    Object.keys(OWNER).forEach(wrap);                        // before the app's first route (window load)
    Object.entries(HUBS).forEach(([akey, tabs]) => { window.PAGES[akey] = window.PAGES[tabs[0][0]]; });
  });
})();
