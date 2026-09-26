"use strict";
/* NETHER's body: a fine crimson neural network in 3D, shaped by an organ file (organs/<name>.json, served by
   /api/organ). The brain is the default: side profile (frontal lobe left, cerebellum back-right), given depth as
   two hemispheres on a rounded surface. An organ file gives the side silhouette polygons, a depth (half-width)
   ellipsoid per part, a fold pattern per part, optional splits (the brain's lateral fissure), interior structures,
   named regions with ax/ay and a map from the seven agents/sections to those regions. Callers keep using the
   brain's own coordinates (orchestrator.AGENTS ax/ay): they're mapped onto the current organ's regions here.
   Drag to turn it, scroll or pinch to zoom, shift-drag (or two fingers) to move it, double-click to reset.
   API: NeuralBrain.mount(canvas) -> {glow, fire, busy, focus, anchor(ax,ay), onView(cb), reset(), destroy()}
        NeuralBrain.ready (promise) · use(name) · organ() · map(ax,ay) · lobe(key) · box(W,H) · inside(x,y) */
window.NeuralBrain = (() => {
  const VIOLET = [235, 45, 75], WHITE = [255, 232, 236];   // crimson fibres, pink-white light
  let O = null, NET = null, C = [0.525, 0.4685], G = null;  // current organ, its network, turning point, geometry
  const cache = {};

  // silhouettes are smoothed with Catmull-Rom
  const smooth = (pts, steps = 10) => {
    const out = [], n = pts.length;
    for (let i = 0; i < n; i++) {
      const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      for (let k = 0; k < steps; k++) {
        const t = k / steps, t2 = t * t, t3 = t2 * t;
        out.push([0, 1].map(c => 0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3)));
      }
    }
    return out;
  };
  const inPoly = (poly, x, y) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  const FOLDS = {                                                  // fold patterns: nodes gather where the value is near 0
    gyri: ([a, b, c, d, e, f, g, h]) => (x, y) => Math.sin(x * a + Math.sin(y * b) * c) * d + Math.sin(y * e + Math.cos(x * f) * g) * h,
    ridges: ([a, b, c]) => (x, y) => Math.sin(y * a + Math.sin(x * b) * c),
    rings: ([cx, cy, f, k, a]) => (x, y) => Math.sin(Math.hypot(x - cx, y - cy) * f + Math.sin(Math.atan2(y - cy, x - cx) * k) * a),
    radial: ([cx, cy, k, f, a]) => (x, y) => Math.sin(Math.atan2(y - cy, x - cx) * k + Math.sin(Math.hypot(x - cx, y - cy) * f) * a),
    bands: ([ang, f, g, a]) => { const c = Math.cos(ang), s = Math.sin(ang); return (x, y) => Math.sin((x * c + y * s) * f + Math.sin((y * c - x * s) * g) * a); },
    papillae: ([f, g, a]) => (x, y) => 1.1 - Math.abs(Math.sin(x * f + Math.sin(y * g) * a) * Math.sin(y * f + Math.cos(x * g) * a)) * 1.1,
  };

  function compile(org) {                                          // organ file -> region / fold / half-width functions
    const parts = org.parts.map(p => ({...p, poly: smooth(p.poly, p.steps || 10), foldFn: FOLDS[p.fold.type](p.fold.k),
      splits: (p.splits || []).map(s => ({...s, foldFn: s.fold ? FOLDS[s.fold.type](s.fold.k) : null}))}));
    const byId = {}; parts.forEach(p => { byId[p.id] = {part: p, fold: p.foldFn}; p.splits.forEach(s => { if (s.id != null) byId[s.id] = {part: p, fold: s.foldFn || p.foldFn}; }); });
    const curve = (s, v) => s.curve[0] + s.curve[1] * (v - s.curve[3]) + s.curve[2] * (v - s.curve[3]) ** 2;
    function region(x, y, whole = false) {
      for (const p of parts) {
        if (!inPoly(p.poly, x, y)) continue;
        for (const s of p.splits) {                                  // axis "x": the curve gives x from y (a vertical split)
          const [u, v] = s.axis === "x" ? [y, x] : [x, y], sv = curve(s, u);
          if (!whole && s.gap && u > s.gap[0] && u < s.gap[1] && Math.abs(v - sv) < s.gap[2]) return -1;   // keep the fissure open
          if (s.id != null && u < (s.xmax ?? 9) && u > (s.xmin ?? -9) && (s.above ? v < sv : v > sv)) return s.id;
        }
        return p.id;
      }
      return -1;
    }
    const fold = (x, y) => { const g = region(x, y); return (g >= 0 ? byId[g].fold : parts[0].foldFn)(x, y); };
    function half(x, y, g) {                                       // half-width at (x,y): an ellipsoid seen from the side
      const [cx, cy, rx, ry, w] = (byId[g] || byId[parts[0].id]).part.body;
      return Math.max(org.minHalf || 0.018, w * Math.sqrt(Math.max(0, 1 - ((x - cx) / rx) ** 2 - ((y - cy) / ry) ** 2)));
    }
    const all = parts.flatMap(p => p.poly);
    const bbox = [Math.min(...all.map(p => p[0])), Math.min(...all.map(p => p[1])), Math.max(...all.map(p => p[0])), Math.max(...all.map(p => p[1]))];
    return {region, fold, half, bbox, inside: (x, y) => region(x, y) >= 0};
  }
  function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

  function build(org, g) {
    const {region, fold, half, inside} = g, r = rng(org.seed || 42), nodes = [], S = org.sample, RIM = org.rim;
    const add = (x, y, rim) => {
      const gg = region(x, y), side = r() < 0.5 ? -1 : 1;                        // -1 faces you at rest
      nodes.push({x, y, z: side * (half(x, y, gg) * (0.86 + 0.14 * r()) + 0.012), g: gg, side, n: [], rim});
    };
    while (nodes.length < S.n) {
      const x = S.x[0] + r() * S.x[1], y = S.y[0] + r() * S.y[1];
      const band = Math.exp(-((fold(x, y) / S.band) ** 2));   // near a contour = on a fold
      if (inside(x, y) && r() < S.keep[0] + S.keep[1] * band) add(x, y, false);
    }
    const rim = p => [[RIM.d, 0], [-RIM.d, 0], [0, RIM.d], [0, -RIM.d]].some(([dx, dy]) => !inside(p[0] + dx, p[1] + dy));
    for (let k = 0; k < RIM.tries && nodes.length < RIM.max; k++) {    // denser band along the edge
      const x = RIM.x[0] + r() * RIM.x[1], y = RIM.y[0] + r() * RIM.y[1];
      if (inside(x, y) && rim([x, y]) && r() < RIM.p) add(x, y, true);
    }
    const cell = 0.03, grid = new Map(), key = (i, j) => i * 1000 + j;           // spatial hash for neighbours
    nodes.forEach((a, i) => { const k = key(Math.floor(a.x / cell), Math.floor(a.y / cell)); (grid.get(k) || grid.set(k, []).get(k)).push(i); });
    const edges = [];
    nodes.forEach((a, i) => {
      const gi = Math.floor(a.x / cell), gj = Math.floor(a.y / cell), near = [];
      for (let di = -1; di <= 1; di++) for (let dj = -1; dj <= 1; dj++) (grid.get(key(gi + di, gj + dj)) || []).forEach(j => {
        const b = nodes[j]; if (j === i || b.g !== a.g || b.side !== a.side) return;
        const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2; if (d < 0.0009) near.push([j, d]);
      });
      near.sort((p, q) => p[1] - q[1]).slice(0, 3).forEach(([j]) => { if (j > i) { edges.push([i, j]); a.n.push(j); nodes[j].n.push(i); } });
    });
    // inside: arcs (the brain's corpus callosum, a heart's septum), blobs (thalamus, lens) and an inner wall, all finely meshed
    const I = org.interior || {}, first = nodes.length;
    const arcAt = (A, t) => [A.x[0] + A.x[1] * t, A.y[0] + A.y[1] * Math.sin(Math.PI * t) + A.y[2] * t];
    (I.arcs || []).forEach(A => { for (let k = 0; k < A.n; k++) {
      const t = r(), [x, y] = arcAt(A, t), thick = A.thick[0] + A.thick[1] * Math.sin(Math.PI * t) + (A.tail && t > A.tail[0] ? A.tail[1] : 0);
      nodes.push({x: x + (r() - 0.5) * A.jitter, y: y + (r() - 0.5) * thick, z: (r() - 0.5) * A.z, g: 3, side: 0, n: [], mid: true});
    } });
    (I.blobs || []).forEach(B => { for (let k = 0; k < B.n; k++) {
      const a = r() * 6.283, d = Math.sqrt(r()), sd = r() < 0.5 ? -1 : 1;
      nodes.push({x: B.c[0] + Math.cos(a) * d * B.r[0], y: B.c[1] + Math.sin(a) * d * B.r[1], z: sd * (B.z[0] + r() * B.z[1]), g: 3, side: 0, n: [], mid: true});
    } });
    const link = (i, j) => { edges.push([i, j]); nodes[i].n.push(j); nodes[j].n.push(i); };
    for (let i = first; i < nodes.length; i++) {                               // the interior's own fine mesh
      const a = nodes[i], near = [];
      for (let j = first; j < nodes.length; j++) { if (j === i) continue;
        const d = (a.x - nodes[j].x) ** 2 + (a.y - nodes[j].y) ** 2 + (a.z - nodes[j].z) ** 2; if (d < (I.mesh || 0.0006)) near.push([j, d]); }
      near.sort((p, q) => p[1] - q[1]).slice(0, 3).forEach(([j]) => { if (j > i) link(i, j); });
    }
    const Wl = I.wall;
    if (Wl) {
      const wall = nodes.length, A = I.arcs[Wl.under];                     // each hemisphere's inner (medial) wall, facing the other
      for (let k = 0; k < Wl.tries && nodes.length < wall + Wl.max; k++) {
        const x = Wl.x[0] + r() * Wl.x[1], y = Wl.y[0] + r() * Wl.y[1], band = Math.exp(-((fold(x * Wl.foldScale[0], y * Wl.foldScale[1]) / Wl.band[0]) ** 2));
        if (region(x, y, true) !== Wl.part || y > arcAt(A, Math.max(0, Math.min(1, (x - A.x[0]) / A.x[1])))[1] + Wl.margin || r() > Wl.band[1] + Wl.band[2] * band) continue;
        const sd = r() < 0.5 ? -1 : 1;
        nodes.push({x, y, z: sd * (Wl.z[0] + r() * Wl.z[1]), g: 4, side: sd, n: [], mid: true, wall: true});
      }
      for (let i = first; i < nodes.length; i++) {                             // short fibres: interior <-> walls, wall <-> wall (same side)
        const a = nodes[i], near = [];
        for (let j = first; j < nodes.length; j++) { const b = nodes[j];
          if (j === i || (a.wall && b.wall && a.side !== b.side)) continue;
          const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2; if (d < 0.0009) near.push([j, d]); }
        near.sort((p, q) => p[1] - q[1]).slice(0, a.wall ? 3 : 2).forEach(([j]) => { if (j > i && !(nodes[j].n.includes(i))) link(i, j); });
      }
      for (let i = wall; i < nodes.length; i++) {                              // where the inner wall folds over into the outer surface
        const a = nodes[i]; let best = -1, bd = 0.0012;
        for (let j = 0; j < first; j++) { const b = nodes[j]; if (b.side !== a.side || b.g !== Wl.part) continue;
          const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2; if (d < bd) { bd = d; best = j; } }
        if (best >= 0) link(i, best);
      }
    }
    return {nodes, edges};
  }

  function load(org) {                                             // make an organ current (built once per session)
    if (!cache[org.name]) { const g = compile(org); cache[org.name] = {org, g, net: build(org, g)}; }
    ({org: O, g: G, net: NET} = cache[org.name]); C = O.center;
    return O;
  }
  const fetchOrgan = name => fetch(name ? "/api/organ/" + encodeURIComponent(name) : "/api/organ").then(r => { if (!r.ok) throw new Error("organ"); return r.json(); });
  const ready = typeof fetch === "function" && typeof document !== "undefined"
    ? fetchOrgan().then(d => load(d.organ)).catch(() => fetchOrgan("brain").then(d => load(d.organ || d))) : Promise.resolve(null);

  // the brain's own coordinates -> the current organ: a section's anchor goes to its region, anything else is scaled box to box
  function map(ax, ay) {
    if (!O || O.name === "brain" || !O.canon) return [ax, ay];
    const hit = Object.entries(O.canon.sections).find(([, p]) => Math.abs(p[0] - ax) < 1e-6 && Math.abs(p[1] - ay) < 1e-6);
    const reg = hit && O.regions[O.sections[hit[0]]];
    if (reg) return [reg.ax, reg.ay];
    const [a, b, c, d] = O.canon.bbox, [e, f, g, h] = G.bbox;
    return [e + (ax - a) / (c - a) * (g - e), f + (ay - b) / (d - b) * (h - f)];
  }

  const box = (W, H) => { const size = Math.min(W * O.fit[0], H * O.fit[1]); return {size, ox: W / 2 - size * C[0], oy: H * 0.47 - size * C[1]}; };
  const HOME = {yaw: 0, pitch: 0, zoom: 1, px: 0, py: 0};

  function mount(canvas) {
    const net = NET;
    // a soft glow doesn't need full Retina resolution: 1.25× looks the same and draws ~60% fewer pixels
    const ctx = canvas.getContext("2d"), dpr = Math.min(1.25, devicePixelRatio || 1);
    let lastDraw = 0, slow = 0, frameGap = 1000 / 30;                           // idle: 30 fps; busier machines drop further
    let W = 0, H = 0, size = 0, ox = 0, oy = 0, fibres = null, raf = 0, alive = true, dirty = true;
    const view = {...HOME}, spin = {yaw: 0, pitch: 0}, listeners = [];
    const pulses = [], glows = new Map(), waves = [], busy = new Map();
    const proj = new Float32Array(net.nodes.length * 3);                          // screen x, y, depth per node

    // unit-space point -> screen, through the current turn, perspective, zoom and pan
    function project(x, y, z) {
      const dx = x - C[0], dy = y - C[1], ca = Math.cos(view.yaw), sa = Math.sin(view.yaw), cb = Math.cos(view.pitch), sb = Math.sin(view.pitch);
      const x1 = dx * ca + z * sa, z1 = -dx * sa + z * ca, y2 = dy * cb - z1 * sb, z2 = dy * sb + z1 * cb, p = 2.6 / (2.6 + z2);
      return [ox + C[0] * size + x1 * p * size * view.zoom + view.px, oy + C[1] * size + y2 * p * size * view.zoom + view.py, z2];
    }
    const P = i => [proj[i * 3], proj[i * 3 + 1]];
    const shade = i => Math.max(0.22, Math.min(1, 0.62 - proj[i * 3 + 2] * 1.6));   // near side bright, far side dim
    const sprite = (() => {                                                        // one soft node, stamped many times
      const s = document.createElement("canvas"); s.width = s.height = 32; const g = s.getContext("2d");
      const r = g.createRadialGradient(16, 16, 0, 16, 16, 16);
      r.addColorStop(0, `rgba(${WHITE},.6)`); r.addColorStop(.35, `rgba(${VIOLET},.3)`); r.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = r; g.fillRect(0, 0, 32, 32); return s;
    })();

    function layout() {
      const rect = canvas.getBoundingClientRect();
      W = rect.width; H = rect.height; canvas.width = W * dpr; canvas.height = H * dpr;
      ({size, ox, oy} = box(W, H));
      fibres = document.createElement("canvas"); fibres.width = canvas.width; fibres.height = canvas.height;
      dirty = true;
    }
    function render() {                                                            // the still network, redrawn only when the view moves
      net.nodes.forEach((n, i) => { const [x, y, z] = project(n.x, n.y, n.z); proj[i * 3] = x; proj[i * 3 + 1] = y; proj[i * 3 + 2] = z; });
      const f = fibres.getContext("2d"); f.setTransform(dpr, 0, 0, dpr, 0, 0); f.clearRect(0, 0, W, H); f.lineCap = "round";
      const [cx, cy] = project(C[0], C[1], 0), R = size * view.zoom;
      const aura = f.createRadialGradient(cx, cy, R * 0.05, cx, cy, R * 0.42);
      aura.addColorStop(0, "rgba(210,30,60,.10)"); aura.addColorStop(.6, "rgba(210,30,60,.04)"); aura.addColorStop(1, "rgba(0,0,0,0)");
      f.fillStyle = aura; f.fillRect(0, 0, W, H);
      const buckets = [[], [], []];                                                // hairline fibres in three depth layers
      net.edges.forEach(e => { const s = (shade(e[0]) + shade(e[1])) / 2; buckets[s > 0.75 ? 2 : s > 0.45 ? 1 : 0].push(e); });
      buckets.forEach((list, b) => {
        f.strokeStyle = `rgba(${VIOLET},${[0.09, 0.18, 0.28][b]})`; f.lineWidth = 0.5; f.beginPath();
        list.forEach(([i, j]) => { f.moveTo(proj[i * 3], proj[i * 3 + 1]); f.lineTo(proj[j * 3], proj[j * 3 + 1]); });
        f.stroke();
      });
      f.globalCompositeOperation = "lighter";
      f.strokeStyle = `rgba(${WHITE},.07)`; f.beginPath();                          // the interior, faint pink-white
      net.edges.forEach(([i, j]) => { if (net.nodes[i].g === 3 && net.nodes[j].g === 3) { f.moveTo(proj[i * 3], proj[i * 3 + 1]); f.lineTo(proj[j * 3], proj[j * 3 + 1]); } });
      f.stroke();
      net.nodes.forEach((n, i) => {
        const k = n.wall ? shade(i) * 0.7 : n.mid ? 0.8 : shade(i), s = (0.35 + n.n.length * 0.16) * 2.8 * Math.sqrt(view.zoom) * (0.7 + 0.4 * k);
        f.globalAlpha = k; f.drawImage(sprite, proj[i * 3] - s, proj[i * 3 + 1] - s, s * 2, s * 2);
      });
      f.globalAlpha = 1; f.globalCompositeOperation = "source-over";
      dirty = false; listeners.forEach(cb => cb());
    }
    const nearest = (ax, ay, side) => net.nodes.reduce((best, n, i) => {
      if (side && n.side !== side) return best;
      const d = (n.x - ax) ** 2 + (n.y - ay) ** 2; return d < best[1] ? [i, d] : best; }, [0, 9])[0];
    const anchors = new Map();                                                     // each section's node on the near side
    const anchorOf = (ax, ay) => { const k = `${ax},${ay}`; if (!anchors.has(k)) anchors.set(k, nearest(...map(ax, ay), -1)); return anchors.get(k); };
    const dists = new Map();                                                       // breadth-first hops from a region's node
    function distFrom(start) {
      if (dists.has(start)) return dists.get(start);
      const dist = new Array(net.nodes.length).fill(Infinity); dist[start] = 0; const q = [start];
      for (let h = 0; h < q.length; h++) { const i = q[h]; net.nodes[i].n.forEach(j => { if (dist[j] === Infinity) { dist[j] = dist[i] + 1; q.push(j); } }); }
      const out = dist.map(d => d === Infinity ? 99 : d); dists.set(start, out); return out;
    }

    function frame(t) {
      if (!alive) return;
      if (!canvas.isConnected) { api.destroy(); return; }                        // its page was replaced
      if (!W || !H) { layout(); if (!W || !H) { raf = requestAnimationFrame(frame); return; } }   // hidden or not laid out yet
      if (!drag && (Math.abs(spin.yaw) > 1e-4 || Math.abs(spin.pitch) > 1e-4)) {   // a little inertia after a flick
        view.yaw += spin.yaw; view.pitch = clampPitch(view.pitch + spin.pitch); spin.yaw *= 0.9; spin.pitch *= 0.9; dirty = true;
      }
      if (tween) { const k = Math.min(1, (t - tween.t0) / tween.ms), e = 1 - (1 - k) ** 3;
        Object.keys(HOME).forEach(p => view[p] = tween.from[p] + (tween.to[p] - tween.from[p]) * e); dirty = true; if (k >= 1) tween = null; }
      const active = dirty || waves.some(w => !w.soft) || drag;                   // moving or firing: full speed
      if (!active && t - lastDraw < frameGap) { raf = requestAnimationFrame(frame); return; }   // idle: skip this frame
      lastDraw = t; const w0 = performance.now();
      if (dirty) render();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = 0.9 + 0.1 * Math.sin(t / 2000); ctx.drawImage(fibres, 0, 0, W, H); ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "lighter";
      const warm = (i, R, a) => { const [x, y] = P(i), g = ctx.createRadialGradient(x, y, 0, x, y, R);
        g.addColorStop(0, `rgba(${VIOLET},${a})`); g.addColorStop(1, "rgba(0,0,0,0)"); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill(); };
      glows.forEach((k, key) => warm(anchorOf(...key.split(",").map(Number)), size * view.zoom * 0.075, 0.4));   // hover: the region warms up
      busy.forEach((b, key) => {                             // working: the region breathes and sends out small local waves
        const i = anchorOf(...key.split(",").map(Number)), s = 0.5 + 0.5 * Math.sin(t / 420 + b.ph);
        warm(i, size * view.zoom * (0.06 + 0.03 * s), 0.18 + 0.22 * s);
        if (t - b.last > 1500) { b.last = t; waves.push({t0: t, dist: distFrom(i), soft: 9, done() {}}); }
      });
      for (let w = waves.length - 1; w >= 0; w--) {          // the fire: nodes flash as the wave passes
        const wv = waves[w], front = (t - wv.t0) / 34; let any = false;
        wv.dist.forEach((d, i) => {
          if (wv.soft && d > wv.soft) return;
          const k = (1 - Math.abs(front - d) / 3) * (wv.soft ? 0.55 * (1 - d / (wv.soft + 1)) : 1); if (k <= 0) return; any = true;
          const [x, y] = P(i); ctx.fillStyle = `rgba(${WHITE},${Math.min(1, k) * shade(i)})`;
          ctx.beginPath(); ctx.arc(x, y, 1.4 + 2.2 * k, 0, 7); ctx.fill();
        });
        if (!any && front > 4) { waves.splice(w, 1); wv.done(); }
      }
      if (Math.random() < 0.16) {                            // small sparks along fibres
        const e = net.edges[Math.floor(Math.random() * net.edges.length)];
        pulses.push({a: e[0], b: e[1], t0: t, ms: 600 + Math.random() * 700});
      }
      for (let p = pulses.length - 1; p >= 0; p--) {
        const pu = pulses[p], k = (t - pu.t0) / pu.ms;
        if (k >= 1) { pulses.splice(p, 1); if (Math.random() < 0.6) { const nb = net.nodes[pu.b].n; if (nb.length) pulses.push({a: pu.b, b: nb[Math.floor(Math.random() * nb.length)], t0: t, ms: pu.ms}); } continue; }
        const [x1, y1] = P(pu.a), [x2, y2] = P(pu.b), x = x1 + (x2 - x1) * k, y = y1 + (y2 - y1) * k;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 4.5); g.addColorStop(0, `rgba(${WHITE},${0.85 * shade(pu.a)})`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 4.5, 0, 7); ctx.fill();
      }
      if (pulses.length > 40) pulses.splice(0, pulses.length - 40);
      ctx.globalCompositeOperation = "source-over";
      const cost = performance.now() - w0;                                         // self-tuning: a slow machine gets fewer idle frames
      slow = slow * 0.95 + (cost > 14 ? 1 : 0) * 0.05;
      frameGap = slow > 0.5 ? 1000 / 15 : slow > 0.2 ? 1000 / 20 : 1000 / 30;
      raf = requestAnimationFrame(frame);
    }

    /* ---- turning, zooming and moving ---- */
    const clampPitch = p => Math.max(-1.1, Math.min(1.1, p));
    const pts = new Map(); let drag = null, tween = null;
    canvas.style.touchAction = "none"; canvas.style.cursor = "grab";
    const onDown = e => {
      canvas.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); tween = null; spin.yaw = spin.pitch = 0;
      drag = {pan: e.shiftKey || e.button === 2 || e.altKey, last: [e.clientX, e.clientY], pinch: null}; canvas.style.cursor = "grabbing";
    };
    const onMove = e => {
      if (!drag || !pts.has(e.pointerId)) return;
      pts.set(e.pointerId, [e.clientX, e.clientY]);
      if (pts.size === 2) {                                   // two fingers: pinch to zoom, move together to pan
        const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]), m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        if (drag.pinch) { view.zoom = Math.max(0.55, Math.min(3, view.zoom * d / drag.pinch.d)); view.px += m[0] - drag.pinch.m[0]; view.py += m[1] - drag.pinch.m[1]; }
        drag.pinch = {d, m}; dirty = true; return;
      }
      const dx = e.clientX - drag.last[0], dy = e.clientY - drag.last[1]; drag.last = [e.clientX, e.clientY];
      if (drag.pan) { view.px += dx; view.py += dy; }
      else { const cap = v => Math.max(-0.06, Math.min(0.06, v));        // a flick coasts, it doesn't whirl
        view.yaw += dx * 0.008; view.pitch = clampPitch(view.pitch - dy * 0.006); spin.yaw = cap(dx * 0.008); spin.pitch = cap(-dy * 0.006); drag.t = performance.now(); }
      dirty = true;
    };
    const onUp = e => { pts.delete(e.pointerId); if (!pts.size) { if (!drag?.t || performance.now() - drag.t > 80) spin.yaw = spin.pitch = 0; drag = null; canvas.style.cursor = "grab"; } };
    const onWheel = e => {
      e.preventDefault();
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015)), z = Math.max(0.55, Math.min(3, view.zoom * k)), r = canvas.getBoundingClientRect();
      const [cx, cy] = project(C[0], C[1], 0), mx = e.clientX - r.left, my = e.clientY - r.top;
      view.px += (mx - cx) * (1 - z / view.zoom); view.py += (my - cy) * (1 - z / view.zoom);   // zoom toward the pointer
      view.zoom = z; dirty = true;
    };
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const still = () => { if (dirty && W) render(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H); ctx.drawImage(fibres, 0, 0, W, H); };
    const glide = to => { spin.yaw = spin.pitch = 0;
      if (reduced) { Object.assign(view, to); dirty = true; still(); } else tween = {t0: performance.now(), from: {...view}, to, ms: 650}; };
    const reset = () => glide({...HOME});
    canvas.addEventListener("pointerdown", onDown); canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp); canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("wheel", onWheel, {passive: false}); canvas.addEventListener("dblclick", reset);
    canvas.addEventListener("contextmenu", e => e.preventDefault());

    layout(); if (W && H) render();
    if (reduced) still();
    else raf = requestAnimationFrame(frame);
    const onResize = () => { layout(); if (W && H) { render(); if (reduced) still(); } }; addEventListener("resize", onResize);

    const api = {
      glow(ax, ay, on) { on ? glows.set(`${ax},${ay}`, 1) : glows.delete(`${ax},${ay}`); },
      fire(ax, ay) {                                         // breadth-first distance from the region's nearest node
        const dist = distFrom(anchorOf(ax, ay));
        return new Promise(res => { waves.push({t0: performance.now(), dist, done: res}); setTimeout(res, 900); });
      },
      busy(ax, ay, on) { const k = `${ax},${ay}`; if (!on) busy.delete(k); else if (!busy.has(k)) busy.set(k, {last: 0, ph: Math.random() * 6}); },
      busyKeys: () => [...busy.keys()],
      focus(ax, ay, zoom = 2.2, at = [0.5, 0.46]) {          // glide so this region sits at `at` (fraction of the canvas), zoomed in
        const n = net.nodes[anchorOf(ax, ay)], p = 2.6 / (2.6 + n.z);
        glide({yaw: 0, pitch: 0, zoom, px: W * at[0] - (ox + C[0] * size + (n.x - C[0]) * p * size * zoom), py: H * at[1] - (oy + C[1] * size + (n.y - C[1]) * p * size * zoom)});
      },
      anchor(ax, ay) { return P(anchorOf(ax, ay)); },       // where a section's region is on screen right now
      scale: () => view.zoom,
      onView(cb) { listeners.push(cb); },
      reset,
      organ: O && O.name,
      destroy() {
        alive = false; cancelAnimationFrame(raf); removeEventListener("resize", onResize);
        canvas.removeEventListener("pointerdown", onDown); canvas.removeEventListener("pointermove", onMove);
        canvas.removeEventListener("pointerup", onUp); canvas.removeEventListener("wheel", onWheel); canvas.removeEventListener("dblclick", reset);
      },
    };
    return api;
  }
  async function use(name) { const d = await fetchOrgan(name); return load(d.organ || d); }
  // a section's region name on the current organ, with the section's own role ("Left ventricle · the pump"); null on the brain
  function lobe(key) {
    if (!O || O.name === "brain") return null;
    const r = O.regions[O.sections[key]];
    return r ? (r.role ? `${r.label} · ${r.role}` : r.label) : null;
  }
  return {mount, box, ready, use, map, lobe, load, organ: () => O, _net: () => NET,
    inside: (x, y) => G ? G.region(x, y, true) >= 0 : false};
})();
