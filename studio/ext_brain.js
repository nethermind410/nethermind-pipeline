"use strict";
/* Sub-brains: click a section (or its agent) on the brain and, after the synapse wave, the view glides into that
   region and a small cluster of neurons grows out of it — one per real item of that section: ideas (sized by the
   views similar Shorts really got), scripts waiting, videos in the works, upcoming posts, live videos (sized by their
   real views), waiting comments, health checks (red when failing), today's to-dos it owns, and the agent's own
   sub-agents. Every neuron opens its page; "Open <section> →" opens the section; Esc or "Whole brain" goes back.
   window.nxSub = {open(key), close()}. Uses app.js helpers: $, esc, get, go, fmt; brain.js: NEURONS, brainNet. */
(() => {
  const RED = "#FF3B30";
  const TODAY_OWNER = {draft: "content", ready: "production", fixing: "production", queued: "publishing", finish: "publishing", intel: "intelligence", missed: "control"};
  const STAGE = {making: "Being made", ready: "Ready to post", scheduled: "Scheduled", draft: "Script waiting", live: "Live"};
  const NEED = {intelligence: ["/api/ideas", "/api/demand"], content: ["/api/drafts"], production: ["/api/videos"], publishing: ["/api/calendar"],
    analytics: ["/api/videos"], business: ["/api/comments"], control: ["/api/health"]};
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cut = (s, n) => { s = String(s || ""); return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s; };
  const when = iso => new Date(iso).toLocaleString(undefined, {weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit"});
  let cur = null, hooked = null;

  /* ---------- what lives in each region: real items only ---------- */
  async function gather(key) {
    const safe = p => get(p).catch(() => null);
    const [sys, today, a, b] = await Promise.all(["/api/system", "/api/today", ...NEED[key]].map(safe));
    const out = [], agent = (sys?.agents || []).find(x => x.key === key);
    const sized = (list, val) => { const max = Math.max(1, ...list.map(val)); list.forEach(x => x.v = Math.sqrt(Math.max(0, val(x)) / max)); return list; };
    let what = "";
    if (key === "intelligence") {
      const med = s => a && b?.[s]?.median || 0;
      const ideas = (a?.sections || []).flatMap(s => s.items.filter(i => !i.made && !i.dismissed).map(i => ({...i, sec: s.name})));
      const list = sized(ideas.map(i => ({label: i.hook, detail: `${i.sec}${med(i.slug) ? ` · similar Shorts: median ${fmt(med(i.slug))} views` : ""}`, go: "ideas", kind: "item", m: med(i.slug)})), x => x.m)
        .sort((p, q) => q.m - p.m);
      out.push(...list.slice(0, 24)); what = `${ideas.length} idea${ideas.length === 1 ? "" : "s"} waiting, sized by real demand`;
    } else if (key === "content") {
      const d = a?.drafts || [];
      if (a?.busy) out.push({label: a.busy, detail: "Writing now", go: "make", kind: "item", tone: "working", v: 0.6});
      d.forEach(x => out.push({label: x.title || x.topic || x.id, detail: "Script waiting for you", go: `draft/${x.id}`, kind: "item", tone: "hot", v: 0.5}));
      what = d.length ? `${d.length} script${d.length === 1 ? "" : "s"} to approve` : a?.busy ? "Writing a script now" : "No scripts waiting";
    } else if (key === "production") {
      const v = (a || []).filter(x => x.stage && x.stage !== "live");
      v.forEach(x => out.push({label: x.title, detail: STAGE[x.stage] || x.stage, go: `video/${x.id}`, kind: "item", tone: x.stage === "ready" ? "hot" : "", v: 0.45}));
      what = v.length ? `${v.length} video${v.length === 1 ? "" : "s"} in the works` : "Nothing in the works";
    } else if (key === "publishing") {
      const up = (a?.items || []).filter(i => i.state === "scheduled" && new Date(i.at) > Date.now()).sort((p, q) => new Date(p.at) - new Date(q.at));
      up.slice(0, 24).forEach(i => out.push({label: i.title, detail: `${(typeof PLAT !== "undefined" && PLAT[i.platform]) || i.platform} · ${when(i.at)}`, go: "calendar", kind: "item", v: 0.4}));
      what = up.length ? `${up.length} upcoming post${up.length === 1 ? "" : "s"}` : "Nothing queued";
    } else if (key === "analytics") {
      const live = sized((a || []).filter(x => x.stage === "live").map(x => ({label: x.title, detail: `${fmt(x.views || 0)} views`, go: `video/${x.id}`, kind: "item", n: x.views || 0})), x => x.n)
        .sort((p, q) => q.n - p.n);
      out.push(...live.slice(0, 24)); what = live.length ? `${live.length} live video${live.length === 1 ? "" : "s"}, sized by real views` : "No live videos yet";
    } else if (key === "business") {
      const w = (a?.comments || []).filter(c => !c.done);
      w.slice(0, 24).forEach(c => out.push({label: c.author, detail: cut(c.text, 90) + (c.video_title ? ` — on “${cut(c.video_title, 40)}”` : ""), go: "comments", kind: "item", tone: "hot", v: 0.35 + Math.min(0.4, (c.likes || 0) / 10)}));
      what = w.length ? `${w.length} comment${w.length === 1 ? "" : "s"} waiting` : "Nobody waiting";
    } else if (key === "control") {
      const h = [...(a || [])].sort((p, q) => p.ok - q.ok);
      h.forEach(x => out.push({label: x.name, detail: x.ok ? x.detail || "Working" : `Not working${x.detail ? " · " + x.detail : ""}`, go: "settings", kind: "item", tone: x.ok ? "ok" : "bad", v: x.ok ? 0.3 : 0.6}));
      const bad = h.filter(x => !x.ok).length;
      what = h.length ? (bad ? `${bad} of ${h.length} connections need a look` : `All ${h.length} connections working`) : "No health checks yet";
    }
    (today?.cards || []).filter(c => (TODAY_OWNER[c.kind] || "control") === key)
      .forEach(c => out.push({label: c.title, detail: `To do today · ${cut(c.text, 80)}`, go: "today", kind: "todo", tone: "hot", v: 0.4}));
    (agent?.subs || []).forEach(s => out.push({label: s.name, detail: `${s.what}${s.state === "failed" ? " · needs you" : s.state === "working" ? " · working now" : ""}`,
      go: `desk/${key}/${s.key}`, kind: "sub", tone: s.state === "failed" ? "bad" : s.state === "working" ? "working" : "", v: 0.2}));
    return {items: out, what, agent};
  }

  /* ---------- the cluster ---------- */
  function layout(items, narrow) {                   // biggest nearest the centre, spiralling out; sub-agents on an outer ring
    const main = items.filter(i => i.kind !== "sub"), subs = items.filter(i => i.kind === "sub");
    const base = narrow ? 32 : 58, step = narrow ? 21 : 34, R = x => (narrow ? 3 : 4) + (narrow ? 8 : 12) * (x.v ?? 0.3);
    main.forEach((it, i) => { const t = i * 2.39996 + 0.6, r = base + step * Math.sqrt(i + 0.5); it.x = Math.cos(t) * r; it.y = Math.sin(t) * r * 0.86; it.r = R(it); });
    const outer = base + step * Math.sqrt(main.length + 1.5) + (narrow ? 22 : 34);
    subs.forEach((it, i) => { const t = -Math.PI / 2 + (i + 0.5) / subs.length * Math.PI * 2; it.x = Math.cos(t) * outer; it.y = Math.sin(t) * outer * 0.86; it.r = narrow ? 4 : 5.5; });
    // labels: biggest first, skipped where they'd collide with another label or neuron (hover still shows everything)
    const boxes = items.map(it => [it.x - it.r - 3, it.y - it.r - 3, it.x + it.r + 3, it.y + it.r + 3]), placed = [];
    const hit = (b, skip) => boxes.some((o, i) => i !== skip && b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]) || placed.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    const order = items.map((it, i) => i).sort((p, q) => (items[p].kind === "sub") - (items[q].kind === "sub") || (items[q].v ?? 0) - (items[p].v ?? 0));
    let shown = 0;
    order.forEach(i => { const it = items[i], w = Math.min(it.label.length, narrow ? 22 : 30) * 6.4 + 18, x0 = it.x >= 0 ? it.x + it.r + 6 : it.x - it.r - 6 - w;
      const b = [x0, it.y - 11, x0 + w, it.y + 11];
      it.showLabel = (!narrow || shown < 4) && !hit(b, i); if (it.showLabel) { placed.push(b); shown++; } });
    return items;
  }
  function render(c) {
    const n = c.items.length, narrow = c.narrow;
    const dend = c.items.map((it, i) => { const bend = (i % 2 ? 1 : -1) * 0.18, mx = it.x / 2 - it.y * bend, my = it.y / 2 + it.x * bend;
      return `<path class="${it.kind === "sub" ? "sub" : ""} ${it.tone || ""}" d="M0,0 Q${mx.toFixed(1)},${my.toFixed(1)} ${it.x.toFixed(1)},${it.y.toFixed(1)}" style="--i:${i}"/>`; }).join("");
    c.cl.innerHTML = `<svg class="bx-dend" aria-hidden="true">${dend}</svg>` + c.items.map((it, i) => {
      const side = it.x >= 0 ? "r" : "l";
      return `<button class="bx-n ${it.kind} ${it.tone || ""} ${side}" data-bx="${i}" style="left:${it.x.toFixed(1)}px;top:${it.y.toFixed(1)}px;--r:${it.r.toFixed(1)}px;--i:${i}"
        aria-label="${esc(it.label)} — ${esc(it.detail)}"><i></i>${it.showLabel ? `<span>${esc(cut(it.label, narrow ? 22 : 30))}</span>` : ""}</button>`;
    }).join("") + `<span class="bx-core"></span>`;
    c.panel.querySelector(".bx-what").textContent = c.what;
    requestAnimationFrame(() => c.cl.classList.add("in"));
  }
  function fit(c) {                                   // the overlay sits exactly over the canvas, whatever the layout
    const stage = $("#stage"), canvas = $("#bnet"); if (!stage || !canvas) return;
    const S = (c.wrap.offsetParent || stage).getBoundingClientRect(), R = canvas.getBoundingClientRect();
    c.wrap.style.cssText = `left:${R.left - S.left}px;top:${R.top - S.top}px;width:${R.width}px;height:${R.height}px`;
  }
  function place() {
    if (!cur || !window.brainNet || !cur.cl.isConnected) return;
    fit(cur);
    const [x, y] = brainNet.anchor(cur.ax, cur.ay);
    cur.cl.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`;
  }

  async function open(key) {
    const nn = (typeof NEURONS !== "undefined" ? NEURONS : []).find(x => x.key === key), stage = $("#stage"), canvas = $("#bnet");
    if (!nn || !stage || !canvas || !window.brainNet) return go(key);
    if (cur) close(true);
    const narrow = stage.getBoundingClientRect().width < 820, name = nn.label;
    const wrap = document.createElement("div"); wrap.className = "bx-sub";
    wrap.innerHTML = `<div class="bx-cluster ${reduced() ? "still" : ""}"></div><div class="bx-cap" hidden></div>`;
    const panel = document.createElement("aside"); panel.className = "bx-panel"; panel.setAttribute("aria-label", `${name}, up close`);
    panel.innerHTML = `<button class="bx-x" aria-label="Back to the whole brain" title="Back to the whole brain (Esc)">×</button><span class="k">${esc(NeuralBrain.lobe(key) || nn.lobe)}</span><b class="t">${esc(name)}</b>
      <p class="bx-what">Looking inside…</p>
      <div class="bx-acts"><button class="btn primary small bx-open">Open ${esc(name)} →</button>
        <button class="btn small bx-back">Whole brain <kbd>Esc</kbd></button></div>`;
    stage.append(wrap, panel); stage.classList.add("bx-on");
    cur = {key, ax: nn.ax, ay: nn.ay, wrap, cl: wrap.firstElementChild, cap: wrap.lastElementChild, panel, narrow, items: [], what: ""};
    const c = cur;
    if (hooked !== brainNet) { brainNet.onView(place); hooked = brainNet; }
    c.zoomIn = () => brainNet.focus(nn.ax, nn.ay, c.narrow ? 1.7 : 2.2, c.narrow ? [0.5, 0.48] : [0.56, 0.47]);
    c.zoomIn();
    if (narrow) canvas.scrollIntoView({block: "start", behavior: reduced() ? "auto" : "smooth"});
    place();
    panel.querySelector(".bx-open").onclick = () => go(key);
    panel.querySelector(".bx-back").onclick = () => close();
    panel.querySelector(".bx-x").onclick = () => close();
    panel.querySelector(".bx-open").focus({preventScroll: true});
    const g = await gather(key);
    if (cur !== c) return;
    Object.assign(c, g, {items: layout(g.items, narrow)});
    render(c); place();
  }
  function close(quick) {
    if (!cur) return;
    const c = cur; cur = null;
    c.wrap.remove(); c.panel.remove();
    const stage = $("#stage"); if (stage) stage.classList.remove("bx-on");
    if (!quick && window.brainNet) brainNet.reset();
    $(`.neuron[data-neuron="${c.key}"]`)?.focus({preventScroll: true});
  }

  /* ---------- hover, click, keys ---------- */
  const showCap = b => {
    if (!cur || !b) return; const it = cur.items[+b.dataset.bx]; if (!it) return;
    const W = cur.wrap.getBoundingClientRect(), r = b.getBoundingClientRect();
    cur.cap.innerHTML = `<b>${esc(it.label)}</b><span>${esc(it.detail)}</span>`; cur.cap.hidden = false;
    const w = cur.cap.offsetWidth, x = r.left - W.left + r.width / 2, left = x + 14 + w > W.width - 12 ? x - 14 - w : x + 14;
    cur.cap.style.left = Math.max(8, left) + "px"; cur.cap.style.top = Math.max(8, r.top - W.top + r.height / 2 - cur.cap.offsetHeight / 2) + "px";
  };
  const hideCap = () => { if (cur) cur.cap.hidden = true; };
  document.addEventListener("pointerover", e => { const b = e.target.closest?.(".bx-n"); if (b) showCap(b); });
  document.addEventListener("pointerout", e => { const b = e.target.closest?.(".bx-n"); if (b && !b.contains(e.relatedTarget)) hideCap(); });
  document.addEventListener("focusin", e => { const b = e.target.closest?.(".bx-n"); b ? showCap(b) : hideCap(); });
  document.addEventListener("click", e => {
    const b = e.target.closest?.(".bx-n"); if (!b || !cur) return;
    e.stopPropagation(); const it = cur.items[+b.dataset.bx]; if (it) go(it.go);
  }, true);
  let down = null;                                      // a plain click on the brain (not a drag to turn it) also goes back
  document.addEventListener("pointerdown", e => { down = e.target.id === "bnet" ? [e.clientX, e.clientY] : null; }, true);
  document.addEventListener("pointerup", e => { if (cur && down && e.target.id === "bnet" && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5) close(); down = null; }, true);
  document.addEventListener("keydown", e => { if (e.key === "Escape" && cur && !document.querySelector(".sheet, .palette:not([hidden])")) { e.preventDefault(); close(); } });
  let rz = 0;
  addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => {       // re-centre and re-grow at the new size
    if (!cur || !window.brainNet) return; const c = cur, narrow = ($("#stage")?.getBoundingClientRect().width || 0) < 820;
    c.zoomIn?.(); if (narrow !== c.narrow && c.items.length) { c.narrow = narrow; layout(c.items, narrow); render(c); } place(); }, 150); });
  const _route = window.onRoute;
  window.onRoute = name => { if (cur) { cur = null; } _route && _route(name); };
  window.nxSub = {open, close, get key() { return cur?.key || null; }};
})();
