"use strict";
/* The brain: Nethermind's home. Each section is a neuron wired to a region of the brain with
   Da Vinci construction lines; hovering draws the line, clicking fires a signal along it and
   zooms into that region before opening the section. Every caption is live data. */
const NEURONS = [
  // each section sits on the part of the brain that does that job (side profile: front is left).
  // Placed by hand, deliberately uneven: gap = distance outside the brain, nudge = px offset,
  // scale = type size, tilt = degrees.
  {key: "today", label: "Today", lobe: "Motor cortex · action", ax: 0.5, ay: 0.215, gap: 0, nudge: [0, 0], scale: 1.3, tilt: -3, at: [0.035, 0.37]},
  {key: "ideas", label: "Ideas", lobe: "Frontal lobe · planning", ax: 0.24, ay: 0.36, gap: 0.2, nudge: [-10, -80], scale: 0.95, tilt: 2.5},
  {key: "comments", label: "Comments", lobe: "Temporal lobe · language", ax: 0.36, ay: 0.64, gap: 0.015, nudge: [-110, 36], scale: 1.12, tilt: -1.5},
  {key: "calendar", label: "Calendar", lobe: "Hippocampus · memory", ax: 0.53, ay: 0.6, gap: 0, nudge: [0, 0], scale: 0.82, tilt: 1.5, at: [0.025, 0.6]},
  {key: "performance", label: "Performance", lobe: "Parietal lobe · numbers", ax: 0.7, ay: 0.29, gap: 0.15, nudge: [70, -40], scale: 1.0, tilt: 3.5},
  {key: "videos", label: "Videos", lobe: "Occipital lobe · vision", ax: 0.85, ay: 0.46, gap: 0.05, nudge: [-6, 110], scale: 1.4, tilt: -2},
  {key: "settings", label: "Settings", lobe: "Cerebellum · coordination", ax: 0.74, ay: 0.72, gap: 0.24, nudge: [110, -30], scale: 0.74, tilt: 2},
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
      <span class="hint">Drag to turn · scroll to zoom · shift-drag to move · double-click to reset</span>
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
    return `<button class="neuron ${hot ? "hot" : ""}" data-neuron="${n.key}" style="--s:${n.scale};--tilt:${n.tilt}deg">
      <span class="nw">${n.label}</span><span class="nc">${esc(cap)}</span><span class="lobe">${esc(n.lobe)}</span></button>`;
  }).join("");
  const c = data.ch;
  $("#core").innerHTML = c?.ready ? `<button class="core-btn" data-neuron="home-core" title="Open your channel numbers">
      <span class="big">${(c.goals[0].value / c.goals[0].goal * 100).toFixed(1)}%</span>
      <span class="nc">of the way to monetisation · ${fmt(c.goals[0].value)} of 1,000 subscribers · ${fmt(c.goals[1].value)} of 10M Shorts views (estimate)</span></button>` : "";
  window.brainNet && window.brainNet.destroy();
  window.brainNet = NeuralBrain.mount($("#bnet"));
  brainNet.onView(lines);
  wire(data);
  window.onresize = () => document.body.classList.contains("on-brain") && wire(data);
}

const CORE = {key: "home-core", ax: 0.47, ay: 0.64};
const findN = key => key === CORE.key ? CORE : NEURONS.find(x => x.key === key);

/* lay out neurons around the brain and draw the construction lines */
function wire() {
  const stage = $("#stage"), svg = $("#syn"); if (!stage || !$("#bnet")) return;
  const S = stage.getBoundingClientRect(), bx = NeuralBrain.box(S.width, S.height);   // same box neural.js draws in
  const side = bx.size, I = {left: S.left + bx.ox, top: S.top + bx.oy, width: side, height: side};
  I.right = I.left + side;
  svg.setAttribute("viewBox", `0 0 ${S.width} ${S.height}`);
  const pt = n => [I.left - S.left + n.ax * I.width, I.top - S.top + n.ay * I.height];
  const els = Object.fromEntries([...document.querySelectorAll(".neuron")].map(e => [e.dataset.neuron, e]));
  const narrow = S.width < 820;
  let paths = ""; const ends = {};
  NEURONS.forEach(n => {
    const el = els[n.key], [ax, ay] = pt(n);
    if (narrow) { el.style.cssText = ""; return; }
    const cxu = 0.53, cyu = 0.48, dx = n.ax - cxu, dy = n.ay - cyu, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
    let t = L; while (t < 0.9 && NeuralBrain.inside(cxu + ux * t, cyu + uy * t)) t += 0.004;   // reach the edge
    t += n.gap;
    let fx = I.left - S.left + (cxu + ux * t) * I.width + n.nudge[0], fy = I.top - S.top + (cyu + uy * t) * I.height + n.nudge[1];
    let right = ux > 0.25, left = ux < -0.25;                                                     // which way the text hangs
    if (n.at) { fx = S.width * n.at[0]; fy = S.height * n.at[1]; right = true; left = false; }   // hand-placed where the brain leaves no room
    el.classList.toggle("hang-left", left); el.classList.toggle("hang-right", right);
    let lx = left ? fx - el.offsetWidth : right ? fx : fx - el.offsetWidth / 2;
    let ly = n.at ? fy - el.offsetHeight / 2 : uy < -0.5 ? fy - el.offsetHeight : uy > 0.5 ? fy : fy - el.offsetHeight / 2;
    lx = Math.max(24, Math.min(S.width - el.offsetWidth - 24, lx)); ly = Math.max(96, Math.min(S.height - el.offsetHeight - (n.at ? 24 : 120), ly));
    el.style.left = lx + "px"; el.style.top = ly + "px";
    const ex = left ? lx + el.offsetWidth + 10 : right ? lx - 10 : lx + el.offsetWidth / 2;
    const ey = n.at ? ly + el.querySelector(".nw").offsetHeight / 2 : uy < -0.5 ? ly + el.offsetHeight + 6 : uy > 0.5 ? ly - 6 : ly + el.querySelector(".nw").offsetHeight / 2;
    ends[n.key] = {ex, ey, n, bow: 0.15};
  });
  const core = $("#core .core-btn");                                        // the monetisation number is wired in like the rest
  if (core && !narrow) {
    const r = core.getBoundingClientRect();
    ends[CORE.key] = {ex: r.left - S.left + r.width / 2, ey: r.top - S.top - 6, n: CORE, bow: 0};
  }
  Object.keys(ends).forEach(k => paths += `<path class="guide" id="g-${k}"/><path class="line" id="l-${k}"/>
      <circle class="node" id="n-${k}" r="3.5"/><circle class="halo" id="h-${k}" r="4"/>`);
  // faint construction axes, Da Vinci-style: through the brain's centre and across the page
  const cx = I.left - S.left + I.width * 0.5, cy = I.top - S.top + I.height * 0.5;
  svg.innerHTML = `${paths}<g id="sparks"></g>`;
  wireEnds = ends; lines();
}

/* the construction lines follow the brain as it's turned, zoomed or moved */
let wireEnds = {};
function lines() {
  if (!window.brainNet) return;
  Object.entries(wireEnds).forEach(([k, {ex, ey, n, bow}]) => {
    const [ax, ay] = brainNet.anchor(n.ax, n.ay), l = $("#l-" + k); if (!l) return;
    const d = bow ? `M${ex},${ey} Q${(ex + ax) / 2 + (ay - ey) * bow},${(ey + ay) / 2 - (ax - ex) * 0.1} ${ax},${ay}`
                  : `M${ex},${ey} Q${ex + (ax - ex) * 0.3},${(ey + ay) / 2} ${ax},${ay}`;
    $("#g-" + k).setAttribute("d", d); l.setAttribute("d", d);
    ["n-", "h-"].forEach(p => { const c = $("#" + p + k); c.setAttribute("cx", ax); c.setAttribute("cy", ay); });
    const L = l.getTotalLength(), on = l.dataset.on === "1";
    l.style.transition = "none"; l.style.strokeDasharray = L; l.style.strokeDashoffset = on ? 0 : L;
    l.getBoundingClientRect(); l.style.transition = "";
  });

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
  const n = e.target.closest && e.target.closest(".neuron,.core-btn"); if (!n) return;
  const l = $("#l-" + n.dataset.neuron); if (l) { l.dataset.on = "1"; l.style.strokeDashoffset = 0; }
  $("#h-" + n.dataset.neuron)?.classList.add("lit");
  const nn = findN(n.dataset.neuron); if (nn && window.brainNet) brainNet.glow(nn.ax, nn.ay, true);
});
document.addEventListener("pointerout", e => {
  const n = e.target.closest && e.target.closest(".neuron,.core-btn"); if (!n || n.contains(e.relatedTarget)) return;
  const l = $("#l-" + n.dataset.neuron); if (l) { l.dataset.on = ""; l.style.strokeDashoffset = l.getTotalLength(); }
  $("#h-" + n.dataset.neuron)?.classList.remove("lit");
  const nn = findN(n.dataset.neuron); if (nn && window.brainNet) brainNet.glow(nn.ax, nn.ay, false);
});
document.addEventListener("click", async e => {
  const n = e.target.closest && e.target.closest("[data-neuron]"); if (!n) return;
  e.stopPropagation();
  const key = n.dataset.neuron, target = key === "home-core" ? "channel" : key;
  if (REDUCED) return go(target);
  const l = $("#l-" + key);
  if (l) { l.style.strokeDashoffset = 0; await spark(l.getAttribute("d"), 480); }
  const nn = findN(key);
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
