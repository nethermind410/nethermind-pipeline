"use strict";
/* Memory (#memory): LEARNINGS.md as NETHER's own brain — the same crimson network as home, with each learning a
   small cluster of neurons in the region of its theme. GET /api/memory sorts every rule/hypothesis/lesson/
   evidence row into a theme (server-side, deterministic keywords — see studio_ext_brain.py) and says, for each:
   what NETHER learned, how sure it is (brightness/size), and what NETHER actually does about it. Click a theme
   to zoom in and read the cards; Keep / Test more / Drop is saved via POST /api/memory/decide. Mounts its own
   NeuralBrain instance on this page's own canvas — home's brain (window.brainNet) is untouched.
   Uses app.js helpers: $, esc, get, post, main. */
(() => {
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  const TIER_WORD = {rule: "Your rule", proven: "Proven", building: "Building", hunch: "Hunch", none: "No proof yet"};
  let M = null, mnet = null, openTheme = null, names = {};

  const gist = n => {                                   // the card's line beyond its title
    let t = n.text.replace(/\*\*|`/g, "").replace(/\s+/g, " ").trim(); const base = n.title.replace(/…$/, "").trim();
    if (t.toLowerCase().startsWith(base.toLowerCase())) t = t.slice(base.length).replace(/^[\s.:;—–-]+/, "");
    return t;
  };

  async function pageMemory() {
    document.body.classList.remove("on-brain");
    main.innerHTML = `<div class="mem-page"><header class="mem-head"><button class="mem-back" data-go="home">← The brain</button>
        <div><h1>Memory</h1><p class="mem-sub" id="mem-sub">Reading LEARNINGS.md…</p></div></header>
      <div class="mem-brain-wrap" id="mem-brain-wrap"><div class="mem-brain-stage" id="mem-stage">
        <canvas class="mem-net" id="mem-net" role="img" aria-label="NETHER's memory: a brain of everything it has learned"></canvas>
        <svg class="mem-clusters" id="mem-clusters" aria-hidden="true"></svg>
        <div class="mem-labels" id="mem-labels"></div>
        <p class="mem-hint2">Drag to turn · scroll to zoom · click a theme</p></div>
        <aside class="mem-panel" id="mem-panel" aria-live="polite" hidden></aside></div></div>`;
    const [d, vids] = await Promise.all([get("/api/memory"), get("/api/videos").catch(() => [])]);
    names = Object.fromEntries((vids || []).map(v => [v.id, v.title]));
    M = d; openTheme = null;
    const body = d.nodes.filter(n => !["section", "date"].includes(n.kind));
    $("#mem-sub").textContent = body.length
      ? `NETHER has learned ${d.summary.total} thing${d.summary.total === 1 ? "" : "s"} · ${d.summary.proven} proven · ${d.summary.hunches} hunch${d.summary.hunches === 1 ? "" : "es"}${d.updated ? ` · last changed ${new Date(d.updated).toLocaleString(undefined, {day: "numeric", month: "short", hour: "numeric", minute: "2-digit"})}` : ""}.`
      : `Nothing learned yet — ${d.file} is empty. Once the daily run has evidence, it'll show up here.`;
    if (!body.length) { $("#mem-brain-wrap").innerHTML = `<p class="mem-empty">This channel is new. Come back once a few videos have real numbers — NETHER will start sorting what it learns into the regions below.</p>`; return; }
    await NeuralBrain.ready.catch(() => null);
    window.memNet && window.memNet.destroy();
    mnet = window.memNet = NeuralBrain.mount($("#mem-net"));
    mnet.onView(draw);
    layoutLabels();
    draw();
    window.addEventListener("resize", onResize);
  }

  function onResize() { if ($(".mem-page") && mnet) layoutLabels(); }

  /* ---------- theme labels around the brain, in the home style ---------- */
  function layoutLabels() {
    const stage = $("#mem-stage"); if (!stage || !M) return;
    const S = stage.getBoundingClientRect(), narrow = matchMedia("(max-width:820px)").matches;
    const box = NeuralBrain.box(S.width, S.height);
    const cxu = 0.53, cyu = 0.48;
    const wrap = $("#mem-labels"); wrap.innerHTML = "";
    wrap.style.cssText = "position:absolute;inset:0;pointer-events:none";
    const themes = M.themes.filter(t => t.learnings.length);
    themes.forEach((t, i) => {
      const el = document.createElement("button");
      el.className = "mem-label"; el.dataset.theme = t.id;
      el.style.cssText = "position:absolute;pointer-events:auto";
      const n = t.learnings.length, proven = t.learnings.map(id => byId(id)).filter(x => x && (x.tier === "proven" || x.tier === "rule")).length;
      el.innerHTML = narrow ? `<b>${esc(t.label)}</b>` : `<b>${esc(t.label)}</b><span>${n} learning${n === 1 ? "" : "s"}${proven ? ` · ${proven} proven` : ""}</span>`;
      if (narrow) {                                  // small chips, wrapped along the bottom of the stage
        const perRow = Math.max(2, Math.floor((S.width - 16) / 96)), row = Math.floor(i / perRow), col = i % perRow;
        el.style.left = (8 + col * 96) + "px"; el.style.bottom = (8 + row * 36) + "px"; el.style.width = "88px";
        wrap.appendChild(el); return;
      }
      const dx = t.ax - cxu, dy = t.ay - cyu, L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L;
      let d = L; while (d < 0.9 && NeuralBrain.inside(cxu + ux * d, cyu + uy * d)) d += 0.004;
      d += 0.06;
      let fx = box.ox + (cxu + ux * d) * box.size, fy = box.oy + (cyu + uy * d) * box.size;
      el.style.left = Math.max(12, Math.min(S.width - 190, fx - (ux < -0.25 ? 190 : 0))) + "px";
      el.style.top = Math.max(64, Math.min(S.height - 60, fy)) + "px";
      wrap.appendChild(el);
    });
  }
  function byId(id) { return M.nodes.find(n => n.id === id); }

  /* ---------- clusters: a few bright neurons per theme, sized/lit by confidence ---------- */
  function draw() {
    const svg = $("#mem-clusters"); if (!svg || !M || !mnet) return;
    const stage = $("#mem-stage"), S = stage.getBoundingClientRect();
    svg.setAttribute("viewBox", `0 0 ${S.width} ${S.height}`);
    let out = ""; const pos = {}, themeOf = {};
    M.themes.filter(t => t.learnings.length).forEach(t => {
      const items = t.learnings.map(byId).filter(Boolean);
      items.forEach((n, i) => {
        const k = i + 1, ang = k * 2.399963, rad = 0.012 + 0.006 * Math.sqrt(k);
        const ax = t.ax + Math.cos(ang) * rad, ay = t.ay + Math.sin(ang) * rad;
        const [x, y] = mnet.anchor(ax, ay);
        pos[n.id] = [x, y]; themeOf[n.id] = t.id;
        const r = 2.4 + n.brightness * 4.2, dropped = n.decision === "drop";
        out += `<circle class="ml-node ${t.id === openTheme ? "on" : ""} ${dropped ? "dropped" : ""}" data-theme="${esc(t.id)}"
          cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}" opacity="${dropped ? 0.18 : Math.max(0.22, n.brightness)}"></circle>`;
      });
    });
    // the lines: learnings that name the same video, date or ideas are wired together through the brain
    const seen = new Set(), pairs = [];
    const add = (a, b, why) => { if (a === b || !pos[a] || !pos[b]) return; const k = a < b ? a + "|" + b : b + "|" + a; if (!seen.has(k)) { seen.add(k); pairs.push([a, b, why]); } };
    (M.links || []).forEach(l => add(l.a, l.b, l.why));
    const byVid = {}; M.nodes.forEach(n => (n.videos || []).forEach(v => (byVid[v] = byVid[v] || []).push(n.id)));
    Object.entries(byVid).forEach(([v, ids]) => ids.forEach((a, i) => ids.slice(i + 1).forEach(b => add(a, b, "same video: " + v))));
    const byDate = {}; M.nodes.forEach(n => (n.dates || []).forEach(d => (byDate[d] = byDate[d] || []).push(n.id)));
    Object.entries(byDate).forEach(([d, ids]) => ids.forEach((a, i) => ids.slice(i + 1).forEach(b => add(a, b, "same date: " + d))));
    M.themes.forEach(t => t.learnings.forEach((a, i) => i && add(t.learnings[i - 1], a, "same theme: " + t.label)));   // each theme's own thread
    const lines = pairs.map(([a, b, why]) => {
      const [x1, y1] = pos[a], [x2, y2] = pos[b], mx = (x1 + x2) / 2 + (y2 - y1) * 0.18, my = (y1 + y2) / 2 - (x2 - x1) * 0.18;
      const lit = openTheme && (themeOf[a] === openTheme || themeOf[b] === openTheme);
      return `<path class="ml-link ${lit ? "on" : ""}" data-a="${esc(a)}" data-b="${esc(b)}" d="M${x1.toFixed(1)},${y1.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}"><title>${esc(why || "")}</title></path>`;
    }).join("");
    svg.innerHTML = `<g class="ml-links">${lines}</g>${out}`;
  }

  /* ---------- open a theme: zoom the brain, list its cards ---------- */
  function openThemePanel(tid) {
    const t = M.themes.find(x => x.id === tid); if (!t || !t.learnings.length) return;
    openTheme = tid;
    document.querySelectorAll(".mem-label").forEach(e => e.classList.toggle("on", e.dataset.theme === tid));
    if (mnet && !reduced()) mnet.focus(t.ax, t.ay, 2.1, [0.5, 0.46]);
    const items = t.learnings.map(byId).filter(Boolean).sort((a, b) => b.brightness - a.brightness);
    const panel = $("#mem-panel");
    panel.hidden = false;
    panel.innerHTML = `<button class="mem-panel-x" aria-label="Close">×</button>
      <span class="k">${esc(t.label)}</span><h2>${items.length} learning${items.length === 1 ? "" : "s"} here</h2>
      ${items.map(cardHTML).join("")}`;
    draw();
    if (matchMedia("(max-width: 820px)").matches) panel.scrollIntoView({block: "start", behavior: reduced() ? "auto" : "smooth"});
  }
  function closeThemePanel() {
    openTheme = null;
    document.querySelectorAll(".mem-label").forEach(e => e.classList.remove("on"));
    const panel = $("#mem-panel"); if (panel) { panel.hidden = true; panel.innerHTML = ""; }
    draw();
  }
  function cardHTML(n) {
    const learned = n.kind === "evidence" ? `${esc(n.title)} — ${md(gist(n) || n.text)}` : md(n.text);
    const dec = n.decision;
    return `<div class="mem-card3 ${dec === "drop" ? "dropped" : ""}" data-mem-id="${esc(n.id)}">
      <span class="mem-tier ${esc(n.tier)}">${esc(TIER_WORD[n.tier] || n.tier)}</span>
      <p class="mc-learned"><span class="k">What we learned</span>${learned}</p>
      <p class="mc-proof"><span class="k">Proof</span>${esc(n.proof)}</p>
      <p class="mc-used"><span class="k">What NETHER does</span>${esc(n.used)}</p>
      <div class="mem-decide" role="group" aria-label="Your call on this learning">
        <button data-decide="keep" class="${dec === "keep" ? "on" : ""}">Keep</button>
        <button data-decide="test" class="${dec === "test" ? "on" : ""}">Test more</button>
        <button data-decide="drop" class="${dec === "drop" ? "on" : ""}">Drop</button>
      </div></div>`;
  }

  document.addEventListener("click", async e => {
    if (!$(".mem-page")) return;
    const dot = e.target.closest?.("circle[data-theme]");
    if (dot) return openThemePanel(dot.dataset.theme);
    const lbl = e.target.closest?.(".mem-label");
    if (lbl) return openThemePanel(lbl.dataset.theme);
    if (e.target.closest?.(".mem-panel-x")) return closeThemePanel();
    const dec = e.target.closest?.("[data-decide]");
    if (dec) {
      const card = dec.closest(".mem-card3"), id = card?.dataset.memId, choice = dec.dataset.decide;
      if (!id) return;
      try {
        await post("/api/memory/decide", {id, decision: choice});
        const n = byId(id); if (n) n.decision = choice;
        card.querySelectorAll("[data-decide]").forEach(b => b.classList.toggle("on", b.dataset.decide === choice));
        card.classList.toggle("dropped", choice === "drop");
        draw();
      } catch (err) { toast(err.message || "Couldn't save that."); }
    }
  });
  document.addEventListener("keydown", e => {
    if (!$(".mem-page")) return;
    if (e.key === "Escape" && openTheme) { e.preventDefault(); closeThemePanel(); }
  });
  let rt = 0; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if ($(".mem-page") && mnet) layoutLabels(); }, 200); });

  const _onRoute = window.onRoute;
  window.onRoute = name => {
    if (name !== "memory") { window.removeEventListener("resize", onResize); window.memNet && (memNet.destroy(), window.memNet = null); M = null; }
    _onRoute && _onRoute(name);
  };
  window.PAGES.memory = pageMemory;
})();
