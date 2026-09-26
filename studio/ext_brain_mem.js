"use strict";
/* Memory (#memory): LEARNINGS.md as a web, in the brain's crimson. GET /api/memory parses the file into nodes —
   sections, working hypotheses, evidence rows, production rules, NETHER's lessons, and the dates they mention — and
   links them where they share a video, a date, a section or distinctive words. A small force layout places them;
   click a node to read exactly what the file says. Uses app.js helpers: $, esc, get, main. */
(() => {
  const KIND = {section: "Section", hypothesis: "Hypothesis", evidence: "Evidence", rule: "Rule", lesson: "Lesson", note: "Note", date: "Date"};
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const md = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  let M = null, sel = null;
  const gist = n => {                                   // the card's line: what the note says beyond its title
    let t = n.text.replace(/\*\*|`/g, "").replace(/\s+/g, " ").trim(); const base = n.title.replace(/…$/, "").trim();
    if (t.toLowerCase().startsWith(base.toLowerCase())) t = t.slice(base.length).replace(/^[\s.:;—–-]+/, "");
    else t = t.replace(/^[^:]{0,60}:\s*/, "");
    return t.length > 150 ? t.slice(0, 149).trimEnd() + "…" : t;
  };

  async function pageMemory() {
    document.body.classList.remove("on-brain");
    main.innerHTML = `<div class="mem-page"><header class="mem-head"><button class="mem-back" data-go="home">← The brain</button>
        <div><h1>Memory</h1><p class="mem-sub" id="mem-sub">Reading LEARNINGS.md…</p></div></header>
      <div class="mem-digest" id="mem-digest"></div>
      <h2 class="mem-h2">How it all connects</h2>
      <div class="mem-wrap"><div class="mem-stage" id="mem-stage"><svg class="mem-web" id="mem-web" aria-label="LEARNINGS.md as a web of linked notes"></svg>
        <div class="mem-legend" id="mem-legend"></div></div>
        <aside class="mem-read" id="mem-read" aria-live="polite"></aside></div></div>`;
    const [d, vids] = await Promise.all([get("/api/memory"), get("/api/videos").catch(() => [])]);
    const names = Object.fromEntries((vids || []).map(v => [v.id, v.title]));
    d.nodes.forEach(n => {                               // plain names: video titles for ids, sections without their fine print
      if (n.kind === "evidence" && names[n.title]) n.title = names[n.title];
      if (n.kind === "section") n.title = n.title.replace(/\s*\(.*\)\s*$/, "");
    });
    M = d; sel = null;
    const G = [["rule", "lesson"], "Always true", "Rules this channel follows — from your feedback and from results."],
          T = [["hypothesis"], "Being tested", "Hunches the numbers haven't proven yet."],
          E = [["evidence"], "The evidence", "What each video actually did."],
          U = [["note"], "How NETHER uses this", "The ground rules for the notes themselves."];
    $("#mem-digest").innerHTML = [G, T, E, U].map(([ks, h, sub]) => { const items = d.nodes.filter(n => ks.includes(n.kind)); if (!items.length) return "";
      return `<section class="mem-col"><h2>${h} <span>${items.length}</span></h2><p>${sub}</p>${items.map(n => `<button class="mem-card ${n.kind}" data-mem="${esc(n.id)}">
        <b>${esc(n.title)}</b><span>${esc(gist(n))}</span></button>`).join("")}</section>`; }).join("");
    const count = k => d.nodes.filter(n => n.kind === k).length, body = d.nodes.filter(n => !["section", "date"].includes(n.kind)).length;
    $("#mem-sub").textContent = d.nodes.length
      ? `Everything NETHER has written down in ${d.file}: ${body} note${body === 1 ? "" : "s"} in ${count("section")} section${count("section") === 1 ? "" : "s"}, ${count("date")} date${count("date") === 1 ? "" : "s"}, ${d.links.length} link${d.links.length === 1 ? "" : "s"}.${d.updated ? ` Last changed ${new Date(d.updated).toLocaleString(undefined, {day: "numeric", month: "short", hour: "numeric", minute: "2-digit"})}.` : ""}`
      : `${d.file} is empty — nothing learned yet.`;
    const kinds = [...new Set(d.nodes.map(n => n.kind))];
    $("#mem-legend").innerHTML = kinds.map(k => `<span><i class="mk ${k}"></i>${KIND[k] || k}</span>`).join("");
    read(null);
    layout(); draw();
  }

  /* ---------- a small force layout (runs to rest up front, so it's calm and cheap) ---------- */
  function layout() {
    const svg = $("#mem-web"); if (!svg || !M) return;
    const R = svg.getBoundingClientRect(), W = Math.max(320, R.width), H = Math.max(320, R.height), narrow = W < 640;
    const byId = Object.fromEntries(M.nodes.map((n, i) => [n.id, i])), deg = M.nodes.map(() => 0);
    M.links.forEach(l => { deg[byId[l.a]]++; deg[byId[l.b]]++; });
    const P = M.nodes.map((n, i) => ({x: W / 2 + Math.cos(i * 2.39996) * (40 + 11 * i), y: H / 2 + Math.sin(i * 2.39996) * (30 + 8 * i), vx: 0, vy: 0}));
    const E = M.links.map(l => [byId[l.a], byId[l.b], l.why === "same section" ? 1.25 : l.w >= 3 ? 0.75 : 1]);
    const rest = (narrow ? 58 : 92), rep = (narrow ? 2400 : 5200);
    for (let it = 0; it < 420; it++) {
      const cool = 1 - it / 420;
      for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) {
        const dx = P[j].x - P[i].x, dy = P[j].y - P[i].y, d2 = Math.max(80, dx * dx + dy * dy), f = rep / d2, d = Math.sqrt(d2);
        P[i].vx -= f * dx / d; P[i].vy -= f * dy / d; P[j].vx += f * dx / d; P[j].vy += f * dy / d;
      }
      E.forEach(([a, b, k]) => { const dx = P[b].x - P[a].x, dy = P[b].y - P[a].y, d = Math.hypot(dx, dy) || 1, f = (d - rest * k) * 0.035;
        P[a].vx += f * dx / d; P[a].vy += f * dy / d; P[b].vx -= f * dx / d; P[b].vy -= f * dy / d; });
      P.forEach(p => { p.vx += (W / 2 - p.x) * 0.012; p.vy += (H / 2 - p.y) * 0.018;
        p.x += Math.max(-24, Math.min(24, p.vx * cool)); p.y += Math.max(-24, Math.min(24, p.vy * cool)); p.vx *= 0.6; p.vy *= 0.6;
        p.x = Math.max(28, Math.min(W - 28, p.x)); p.y = Math.max(28, Math.min(H - 28, p.y)); });
    }
    M.nodes.forEach((n, i) => { n.x = P[i].x; n.y = P[i].y; n.deg = deg[i];
      n.r = n.kind === "section" ? 8 : n.kind === "date" ? 4.5 : Math.min(10, 4 + deg[i] * 1.1); });
    const xs = M.nodes.map(n => n.x), ys = M.nodes.map(n => n.y), pad = 70;   // fit: the web fills the stage, labels included
    M.box = [Math.min(...xs) - pad * 2, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + pad * 4, Math.max(...ys) - Math.min(...ys) + pad * 2];
    M.W = W; M.H = H; M.byId = byId;
  }
  function draw() {
    const svg = $("#mem-web"); if (!svg || !M) return;
    svg.setAttribute("viewBox", M.box.map(v => v.toFixed(0)).join(" "));
    const N = id => M.nodes[M.byId[id]];
    const links = M.links.map((l, i) => { const a = N(l.a), b = N(l.b), mx = (a.x + b.x) / 2 + (b.y - a.y) * 0.08, my = (a.y + b.y) / 2 - (b.x - a.x) * 0.08;
      return `<path class="ml ${l.w >= 3 ? "strong" : l.why === "same section" ? "sec" : ""}" data-l="${i}" d="M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}"><title>${esc(l.why)}</title></path>`; }).join("");
    const nodes = M.nodes.map((n, i) => {
      const right = n.x < M.W * 0.72, lx = right ? n.r + 7 : -n.r - 7, label = n.title.length > 30 ? n.title.slice(0, 29).trimEnd() + "…" : n.title;
      const mark = n.kind === "date" ? `<rect class="mk-s" x="${-n.r}" y="${-n.r}" width="${n.r * 2}" height="${n.r * 2}" transform="rotate(45)"/>` : `<circle class="mk-s" r="${n.r.toFixed(1)}"/>`;
      return `<g class="mn ${n.kind}" data-mem="${esc(n.id)}" transform="translate(${n.x.toFixed(1)},${n.y.toFixed(1)})" tabindex="0" role="button"
        aria-label="${esc(KIND[n.kind] || n.kind)}: ${esc(n.title)}" style="--i:${i}"><circle class="mn-hit" r="16"/>${mark}
        <text x="${lx}" y="4" text-anchor="${right ? "start" : "end"}">${esc(label)}</text></g>`;
    }).join("");
    svg.innerHTML = `<g class="mls">${links}</g><g>${nodes}</g>`;
    svg.classList.toggle("still", reduced());
    requestAnimationFrame(() => svg.classList.add("in"));
    focusOn(sel);
  }
  function near(id) {
    const s = new Set([id]); M.links.forEach(l => { if (l.a === id) s.add(l.b); if (l.b === id) s.add(l.a); }); return s;
  }
  function focusOn(id) {
    const svg = $("#mem-web"); if (!svg) return;
    const s = id ? near(id) : null;
    svg.classList.toggle("dim", !!id);
    svg.querySelectorAll(".mn").forEach(g => { g.classList.toggle("on", !!s && s.has(g.dataset.mem)); g.classList.toggle("sel", g.dataset.mem === sel); });
    svg.querySelectorAll(".ml").forEach(p => { const l = M.links[+p.dataset.l]; p.classList.toggle("on", !!id && (l.a === id || l.b === id)); });
  }
  function read(id) {
    const el = $("#mem-read"); if (!el) return;
    const n = id && M.nodes[M.byId[id]];
    if (!n) { el.innerHTML = `<span class="k">Read</span><p class="mem-hint">Click any point to read exactly what ${esc(M?.file || "the file")} says there.
      Lines join notes that name the same video or date, sit in the same section, or share distinctive words.</p>`; return; }
    const sec = n.section && M.nodes[M.byId[n.section]];
    const linked = M.links.filter(l => l.a === id || l.b === id).map(l => { const o = M.nodes[M.byId[l.a === id ? l.b : l.a]];
      return `<li><button data-mem-go="${esc(o.id)}"><b>${esc(o.title)}</b><span>${esc(KIND[o.kind] || o.kind)} · ${esc(l.why)}</span></button></li>`; }).join("");
    el.innerHTML = `<span class="k">${esc(KIND[n.kind] || n.kind)}${sec ? ` · ${esc(sec.title)}` : ""}</span>
      <h3>${esc(n.title)}</h3><div class="mem-text">${n.text.split("\n").map(p => `<p>${md(p)}</p>`).join("")}</div>
      ${n.videos?.length ? `<p class="mem-meta">Videos: ${n.videos.map(v => `<a href="#video/${esc(v)}">${esc(v)}</a>`).join(", ")}</p>` : ""}
      ${linked ? `<span class="k">Linked to</span><ul class="mem-links">${linked}</ul>` : ""}
      <button class="btn small mem-close">Close <kbd>Esc</kbd></button>`;
  }
  function pick(id) { sel = id; read(id); focusOn(id); document.querySelectorAll(".mem-card").forEach(c => c.classList.toggle("sel", c.dataset.mem === id)); if (id && matchMedia("(max-width: 820px)").matches) $("#mem-read")?.scrollIntoView({block: "nearest", behavior: reduced() ? "auto" : "smooth"}); }

  document.addEventListener("click", e => {
    if (!$(".mem-page")) return;
    const g = e.target.closest?.("[data-mem]");
    if (g) { if (g.classList.contains("mem-card")) $("#mem-stage")?.scrollIntoView({block: "start", behavior: reduced() ? "auto" : "smooth"}); return pick(g.dataset.mem === sel ? null : g.dataset.mem); }
    const l = e.target.closest?.("[data-mem-go]"); if (l) return pick(l.dataset.memGo);
    if (e.target.closest?.(".mem-close")) return pick(null);
  });
  document.addEventListener("keydown", e => {
    if (!$(".mem-page")) return;
    if (e.key === "Escape" && sel) { e.preventDefault(); pick(null); return; }
    const g = e.target.closest?.("[data-mem]"); if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); pick(g.dataset.mem); }
  });
  document.addEventListener("pointerover", e => { const g = e.target.closest?.("[data-mem]"); if (g && M) focusOn(g.dataset.mem); });
  document.addEventListener("pointerout", e => { const g = e.target.closest?.("[data-mem]"); if (g && M && !g.contains(e.relatedTarget)) focusOn(sel); });
  let rt = 0; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if ($(".mem-page") && M) { layout(); draw(); } }, 200); });
  window.PAGES.memory = pageMemory;
})();
