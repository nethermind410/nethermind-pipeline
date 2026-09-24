"use strict";
/* The brain: Nethermind's home. Each section is a neuron wired to a region of the brain with
   Da Vinci construction lines; hovering draws the line, clicking fires a signal along it and
   zooms into that region before opening the section. Every caption is live data. */
const NEURONS = [
  // anchor on the brain (unit square), where the label floats (angle in degrees, distance as a share of
  // the stage), and which way its text aligns. Deliberately uneven, so it feels placed by hand.
  {key: "today", label: "Today", ax: 0.52, ay: 0.21, ang: -84, dist: 0.44, side: "top"},
  {key: "ideas", label: "Ideas", ax: 0.34, ay: 0.3, ang: -148, dist: 0.43, side: "left"},
  {key: "videos", label: "Videos", ax: 0.235, ay: 0.52, ang: 176, dist: 0.5, side: "left"},
  {key: "comments", label: "Comments", ax: 0.36, ay: 0.72, ang: 134, dist: 0.4, side: "left"},
  {key: "calendar", label: "Calendar", ax: 0.66, ay: 0.29, ang: -38, dist: 0.47, side: "right"},
  {key: "performance", label: "Performance", ax: 0.77, ay: 0.47, ang: 4, dist: 0.53, side: "right"},
  {key: "settings", label: "Settings", ax: 0.64, ay: 0.75, ang: 52, dist: 0.41, side: "right"},
];
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

async function brainData() {
  const safe = p => get(p).catch(() => null);
  const [ch, today, vids, cal, ideas, com, health] = await Promise.all(["/api/channel", "/api/today", "/api/videos",
    "/api/calendar", "/api/ideas", "/api/comments", "/api/health"].map(safe));
  const count = s => (vids || []).filter(v => v.stage === s).length;
  const next = (cal?.items || []).find(i => i.state === "scheduled");
  const openIdeas = (ideas?.sections || []).flatMap(s => s.items).filter(i => !i.made && !i.dismissed).length;
  const waitingC = (com?.comments || []).filter(c => !c.done).length;
  const bad = (health || []).filter(h => !h.ok);
  const nToday = today?.cards?.length || 0;
  return {
    ch,
    cap: {
      today: [nToday ? `${nToday} thing${nToday > 1 ? "s" : ""} to tick off` : "All caught up", nToday > 0],
      ideas: [ideas?.next ? `Up next: ${ideas.next.hook}` : `${openIdeas} ideas, ranked by real demand`, false],
      videos: [`${count("live")} live · ${count("scheduled")} scheduled · ${count("ready")} ready`, count("ready") > 0],
      comments: [waitingC ? `${waitingC} waiting for a reply` : "Nobody waiting", waitingC > 0],
      calendar: [next ? `Next: ${PLAT[next.platform]} ${new Date(next.at).toLocaleString(undefined, {weekday: "short", hour: "numeric", minute: "2-digit"})}` : "Nothing queued", false],
      performance: [ch?.ready ? `${fmt(ch.channel.views)} YouTube views` : "No numbers yet", false],
      settings: [bad.length ? `${bad.map(b => b.name.split(" (")[0]).join(", ")} need${bad.length > 1 ? "" : "s"} a look` : "Every connection working", bad.length > 0],
    },
  };
}

async function pageBrain() {
  document.body.classList.add("on-brain");
  main.innerHTML = `<div class="brain-stage" id="stage">
    <header class="brain-top"><span class="wm">NETHERMIND</span><span class="ed">The brain · ${esc(new Date().toLocaleDateString(undefined, {weekday: "long", day: "numeric", month: "long"}))}</span>
      <button class="ask" id="brain-ask">Ask the brain <kbd>⌘K</kbd></button></header>
    <canvas class="brain-net" id="bnet" role="img" aria-label="Nethermind's brain: a living network of glowing neurons"></canvas>
    <svg class="synapses" id="syn" aria-hidden="true"></svg>
    <nav class="neurons" id="neurons" aria-label="Sections"></nav>
    <div class="core" id="core"></div>
  </div>`;
  $("#brain-ask").onclick = () => palette();
  const data = await brainData();
  $("#neurons").innerHTML = NEURONS.map(n => {
    const [cap, hot] = data.cap[n.key];
    return `<button class="neuron ${n.side} ${hot ? "hot" : ""}" data-neuron="${n.key}">
      <span class="nw">${n.label}</span><span class="nc">${esc(cap)}</span></button>`;
  }).join("");
  const c = data.ch;
  $("#core").innerHTML = c?.ready ? `<button class="core-btn" data-neuron="home-core" title="Open your channel numbers">
      <span class="big">${(c.goals[0].value / c.goals[0].goal * 100).toFixed(1)}%</span>
      <span class="nc">of the way to monetisation · ${fmt(c.goals[0].value)} of 1,000 subscribers · ${fmt(c.goals[1].value)} of 10M Shorts views (estimate)</span></button>` : "";
  window.brainNet && window.brainNet.destroy();
  window.brainNet = NeuralBrain.mount($("#bnet"));
  wire(data);
  window.onresize = () => document.body.classList.contains("on-brain") && wire(data);
}

/* lay out neurons around the brain and draw the construction lines */
function wire() {
  const stage = $("#stage"), svg = $("#syn"); if (!stage || !$("#bnet")) return;
  const S = stage.getBoundingClientRect(), side = Math.min(S.width, S.height);
  const I = {left: S.left + (S.width - side) / 2, top: S.top + (S.height - side) / 2, width: side, height: side};
  I.right = I.left + side;
  svg.setAttribute("viewBox", `0 0 ${S.width} ${S.height}`);
  const pt = n => [I.left - S.left + n.ax * I.width, I.top - S.top + n.ay * I.height];
  const rows = {left: [], right: [], top: []};
  NEURONS.forEach(n => rows[n.side].push(n));
  const els = Object.fromEntries([...document.querySelectorAll(".neuron")].map(e => [e.dataset.neuron, e]));
  const narrow = S.width < 820;
  let paths = "";
  NEURONS.forEach(n => {
    const el = els[n.key], [ax, ay] = pt(n);
    if (narrow) { el.style.cssText = ""; return; }
    const cx0 = S.width / 2, cy0 = S.height / 2, rad = n.ang * Math.PI / 180, R = Math.min(S.width * 0.5, S.height * 0.95) * n.dist;
    const fx = cx0 + Math.cos(rad) * R * (S.width / S.height > 1.3 ? 1.35 : 1), fy = cy0 + Math.sin(rad) * R;
    let lx = n.side === "left" ? fx - el.offsetWidth : n.side === "right" ? fx : fx - el.offsetWidth / 2;
    let ly = fy - el.offsetHeight / 2;
    lx = Math.max(28, Math.min(S.width - el.offsetWidth - 28, lx)); ly = Math.max(64, Math.min(S.height - el.offsetHeight - 110, ly));
    el.style.left = lx + "px"; el.style.top = ly + "px";
    const ex = n.side === "left" ? lx + el.offsetWidth + 12 : n.side === "right" ? lx - 12 : lx + el.offsetWidth / 2;
    const ey = n.side === "top" ? ly + el.offsetHeight + 10 : ly + el.querySelector(".nw").offsetHeight / 2;
    const qx = (ex + ax) / 2 + (ay - ey) * 0.18, qy = (ey + ay) / 2 - (ax - ex) * 0.12;   // a soft, hand-drawn curve
    const d = `M${ex},${ey} Q${qx},${qy} ${ax},${ay}`;
    paths += `<path class="guide" id="g-${n.key}" d="${d}"/><path class="line" id="l-${n.key}" d="${d}"/>
      <circle class="node" id="n-${n.key}" cx="${ax}" cy="${ay}" r="3.5"/><circle class="halo" id="h-${n.key}" cx="${ax}" cy="${ay}" r="4"/>`;
  });
  // faint construction axes, Da Vinci-style: through the brain's centre and across the page
  const cx = I.left - S.left + I.width * 0.5, cy = I.top - S.top + I.height * 0.5;
  svg.innerHTML = `${paths}<g id="sparks"></g>`;
  svg.querySelectorAll(".line").forEach(p => { const L = p.getTotalLength(); p.style.strokeDasharray = L; p.style.strokeDashoffset = L; });

}

/* resting activity: now and then a faint signal crosses the brain between two regions */
let ambientTimer = null;
function ambient() {
  clearInterval(ambientTimer);
  ambientTimer = setInterval(() => {
    if (!document.body.classList.contains("on-brain") || document.hidden) return;
    const a = NEURONS[Math.floor(Math.random() * NEURONS.length)], b = NEURONS[Math.floor(Math.random() * NEURONS.length)];
    if (a === b) return;
    const na = $("#n-" + a.key), nb = $("#n-" + b.key); if (!na || !nb) return;
    const x1 = +na.getAttribute("cx"), y1 = +na.getAttribute("cy"), x2 = +nb.getAttribute("cx"), y2 = +nb.getAttribute("cy");
    const mx = (x1 + x2) / 2 + (y2 - y1) * 0.25, my = (y1 + y2) / 2 - (x2 - x1) * 0.25;
    spark(`M${x1},${y1} Q${mx},${my} ${x2},${y2}`, 1400, "faint");
  }, 1700);
}

/* a travelling pulse along a path */
function spark(d, ms, cls = "") {
  const g = $("#sparks"); if (!g) return Promise.resolve();
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", d); p.setAttribute("class", "trail " + cls);
  const c = document.createElementNS("http://www.w3.org/2000/svg", "circle"); c.setAttribute("r", cls ? 2.2 : 4); c.setAttribute("class", "spark " + cls);
  g.append(p, c);
  const L = p.getTotalLength(); p.style.strokeDasharray = `${Math.min(60, L / 3)} ${L}`;
  return new Promise(res => {
    const done = () => { p.remove(); c.remove(); res(); };
    const guard = setTimeout(done, ms + 250);   // never let an animation block navigation (hidden windows pause rAF)
    const t0 = performance.now();
    const step = t => {
      const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2, at = p.getPointAtLength(e * L);
      c.setAttribute("cx", at.x); c.setAttribute("cy", at.y); p.style.strokeDashoffset = -(e * L - Math.min(60, L / 3));
      if (k < 1) requestAnimationFrame(step); else { clearTimeout(guard); setTimeout(done, 120); }
    };
    requestAnimationFrame(step);
  });
}

/* hover: draw the construction line; click: fire the synapse, flash the region, zoom in, open */
document.addEventListener("pointerover", e => {
  const n = e.target.closest && e.target.closest(".neuron"); if (!n) return;
  const l = $("#l-" + n.dataset.neuron); if (l) l.style.strokeDashoffset = 0;
  $("#h-" + n.dataset.neuron)?.classList.add("lit");
  const nn = NEURONS.find(x => x.key === n.dataset.neuron); if (nn && window.brainNet) brainNet.glow(nn.ax, nn.ay, true);
});
document.addEventListener("pointerout", e => {
  const n = e.target.closest && e.target.closest(".neuron"); if (!n || n.contains(e.relatedTarget)) return;
  const l = $("#l-" + n.dataset.neuron); if (l) l.style.strokeDashoffset = l.getTotalLength();
  $("#h-" + n.dataset.neuron)?.classList.remove("lit");
  const nn = NEURONS.find(x => x.key === n.dataset.neuron); if (nn && window.brainNet) brainNet.glow(nn.ax, nn.ay, false);
});
document.addEventListener("click", async e => {
  const n = e.target.closest && e.target.closest("[data-neuron]"); if (!n) return;
  e.stopPropagation();
  const key = n.dataset.neuron, target = key === "home-core" ? "channel" : key;
  if (REDUCED) return go(target);
  const l = $("#l-" + key);
  if (l) { l.style.strokeDashoffset = 0; await spark(l.getAttribute("d"), 480); }
  const nn = NEURONS.find(x => x.key === key);
  if (nn && window.brainNet) await brainNet.fire(nn.ax, nn.ay);      // the wave spreads through the network
  const node = $("#n-" + key), stage = $("#stage");
  if (node) {
    $("#h-" + key).classList.add("fire");
    const S = stage.getBoundingClientRect(), x = +node.getAttribute("cx"), y = +node.getAttribute("cy");
    stage.style.transformOrigin = `${x}px ${y}px`; stage.classList.add("zoom");
  } else stage.classList.add("fade");
  setTimeout(() => go(target), 420);
}, true);

/* the brain replaces Home; the old channel page lives on at #channel */
window.PAGES.channel = window.PAGES.home;
window.PAGES.home = pageBrain;
const _onRoute = window.onRoute;
window.onRoute = name => {
  if (name !== "home" && name !== "") { document.body.classList.remove("on-brain"); window.brainNet && (brainNet.destroy(), window.brainNet = null); }
  clearInterval(ambientTimer); _onRoute && _onRoute(name);
};
