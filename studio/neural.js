"use strict";
/* The brain: a fine crimson neural network, now in 3D. The side profile (frontal lobe left, cerebellum
   back-right, no stem) is given depth as two hemispheres on a rounded surface, so it can be turned.
   Drag to turn it, scroll or pinch to zoom, shift-drag (or two fingers) to move it, double-click to reset.
   At rest small sparks run along fibres; hovering a section glows its region; clicking fires a wave.
   API: NeuralBrain.mount(canvas) -> {glow, fire, anchor(ax,ay), onView(cb), reset(), destroy()} */
window.NeuralBrain = (() => {
  const VIOLET = [235, 45, 75], WHITE = [255, 232, 236];   // crimson fibres, pink-white light
  const C = [0.525, 0.4685];                                // the point the brain turns around

  // side profile traced from a lateral view of a real brain (front = left), smoothed with Catmull-Rom.
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
  const CEREBRUM = smooth([[0.21, 0.575], [0.165, 0.49], [0.17, 0.38], [0.23, 0.285], [0.33, 0.215], [0.46, 0.185], [0.59, 0.19],
    [0.705, 0.225], [0.795, 0.295], [0.855, 0.39], [0.875, 0.485], [0.85, 0.565], [0.78, 0.605], [0.69, 0.625], [0.6, 0.66],
    [0.5, 0.69], [0.41, 0.685], [0.345, 0.655], [0.31, 0.61], [0.275, 0.588]]);
  const CEREBELLUM = smooth([[0.655, 0.655], [0.71, 0.615], [0.79, 0.603], [0.855, 0.625], [0.885, 0.672], [0.855, 0.728],
    [0.775, 0.752], [0.7, 0.735]]);
  const sylvian = x => 0.588 - 0.36 * (x - 0.275) + 0.32 * (x - 0.275) ** 2;          // lateral fissure
  const inPoly = (poly, x, y) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  function region(x, y, whole = false) {
    const cere = inPoly(CEREBRUM, x, y);
    if (!cere) return inPoly(CEREBELLUM, x, y) ? 2 : -1;
    const sy = sylvian(x);
    if (!whole && x > 0.28 && x < 0.63 && Math.abs(y - sy) < 0.01) return -1;        // keep the fissure open
    return x < 0.66 && y > sy ? 1 : 0;                                              // temporal lobe below the fissure
  }
  const inside = (x, y) => region(x, y) >= 0;
  function fold(x, y) {
    if (region(x, y) === 2) return Math.sin(y * 150 + Math.sin(x * 30) * 1.4);    // cerebellum: fine ridges
    return Math.sin(x * 38 + Math.sin(y * 17) * 2.6) * 0.55 + Math.sin(y * 31 + Math.cos(x * 19) * 2.3) * 0.45;
  }
  // half-width of the brain at (x,y): an ellipsoid seen from the side, so the silhouette stays the profile
  function half(x, y, g) {
    const [cx, cy, rx, ry, w] = g === 2 ? [0.77, 0.678, 0.13, 0.085, 0.15] : [0.52, 0.44, 0.39, 0.3, 0.29];
    return Math.max(0.018, w * Math.sqrt(Math.max(0, 1 - ((x - cx) / rx) ** 2 - ((y - cy) / ry) ** 2)));
  }
  function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

  function build() {
    const r = rng(42), nodes = [];
    const add = (x, y, rim) => {
      const g = region(x, y), side = r() < 0.5 ? -1 : 1;                           // -1 faces you at rest
      nodes.push({x, y, z: side * (half(x, y, g) * (0.86 + 0.14 * r()) + 0.012), g, side, n: [], rim});
    };
    while (nodes.length < 2900) {
      const x = 0.1 + r() * 0.8, y = 0.16 + r() * 0.66;
      const band = Math.exp(-((fold(x, y) / 0.16) ** 2));   // near a contour = on a fold
      if (inside(x, y) && r() < 0.08 + 0.92 * band) add(x, y, false);
    }
    const rim = p => [[0.012, 0], [-0.012, 0], [0, 0.012], [0, -0.012]].some(([dx, dy]) => !inside(p[0] + dx, p[1] + dy));
    for (let k = 0; k < 14000 && nodes.length < 3500; k++) {           // denser band along the edge
      const x = 0.12 + r() * 0.8, y = 0.15 + r() * 0.65;
      if (inside(x, y) && rim([x, y]) && r() < 0.6) add(x, y, true);
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
    // between the hemispheres: the corpus callosum (an arched bridge), the thalamus, and fibres crossing over
    const first = nodes.length, arc = t => [0.35 + 0.34 * t, 0.47 - 0.13 * Math.sin(Math.PI * t) + 0.03 * t];
    for (let k = 0; k < 420; k++) {
      const t = r(), [x, y] = arc(t), thick = 0.018 + 0.014 * Math.sin(Math.PI * t) + (t > 0.85 ? 0.012 : 0);   // thicker at the back (splenium)
      nodes.push({x: x + (r() - 0.5) * 0.02, y: y + (r() - 0.5) * thick, z: (r() - 0.5) * 0.09, g: 3, side: 0, n: [], mid: true});
    }
    for (let k = 0; k < 140; k++) {                                            // thalamus: two small eggs either side of the midline
      const a = r() * 6.283, d = Math.sqrt(r()), sd = r() < 0.5 ? -1 : 1;
      nodes.push({x: 0.555 + Math.cos(a) * d * 0.045, y: 0.505 + Math.sin(a) * d * 0.028, z: sd * (0.03 + r() * 0.03), g: 3, side: 0, n: [], mid: true});
    }
    const link = (i, j) => { edges.push([i, j]); nodes[i].n.push(j); nodes[j].n.push(i); };
    for (let i = first; i < nodes.length; i++) {                               // the bridge's own fine mesh
      const a = nodes[i], near = [];
      for (let j = first; j < nodes.length; j++) { if (j === i) continue;
        const d = (a.x - nodes[j].x) ** 2 + (a.y - nodes[j].y) ** 2 + (a.z - nodes[j].z) ** 2; if (d < 0.0006) near.push([j, d]); }
      near.sort((p, q) => p[1] - q[1]).slice(0, 3).forEach(([j]) => { if (j > i) link(i, j); });
    }
    const wall = nodes.length;                                                 // each hemisphere's inner (medial) wall, facing the other
    for (let k = 0; k < 9000 && nodes.length < wall + 900; k++) {
      const x = 0.2 + r() * 0.66, y = 0.2 + r() * 0.5, band = Math.exp(-((fold(x * 0.9, y * 1.1) / 0.2) ** 2));
      if (region(x, y, true) !== 0 || y > arc(Math.max(0, Math.min(1, (x - 0.35) / 0.34)))[1] + 0.05 || r() > 0.05 + 0.9 * band) continue;
      const sd = r() < 0.5 ? -1 : 1;
      nodes.push({x, y, z: sd * (0.05 + r() * 0.015), g: 4, side: sd, n: [], mid: true, wall: true});
    }
    for (let i = first; i < nodes.length; i++) {                               // short fibres: bridge <-> walls, wall <-> wall (same side)
      const a = nodes[i], near = [];
      for (let j = first; j < nodes.length; j++) { const b = nodes[j];
        if (j === i || (a.wall && b.wall && a.side !== b.side)) continue;
        const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2; if (d < 0.0009) near.push([j, d]); }
      near.sort((p, q) => p[1] - q[1]).slice(0, a.wall ? 3 : 2).forEach(([j]) => { if (j > i && !(nodes[j].n.includes(i))) link(i, j); });
    }
    for (let i = wall; i < nodes.length; i++) {                                // where the inner wall folds over into the outer surface
      const a = nodes[i]; let best = -1, bd = 0.0012;
      for (let j = 0; j < first; j++) { const b = nodes[j]; if (b.side !== a.side || b.g !== 0) continue;
        const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2; if (d < bd) { bd = d; best = j; } }
      if (best >= 0) link(i, best);
    }
    return {nodes, edges};
  }
  const NET = build();

  const box = (W, H) => { const size = Math.min(W * 0.9, H * 1.42); return {size, ox: W / 2 - size * 0.525, oy: H * 0.47 - size * 0.4685}; };   // brain spans x .165–.885, y .185–.752
  const HOME = {yaw: 0, pitch: 0, zoom: 1, px: 0, py: 0};

  function mount(canvas) {
    // a soft glow doesn't need full Retina resolution: 1.25× looks the same and draws ~60% fewer pixels
    const ctx = canvas.getContext("2d"), dpr = Math.min(1.25, devicePixelRatio || 1);
    let lastDraw = 0, slow = 0, frameGap = 1000 / 30;                           // idle: 30 fps; busier machines drop further
    let W = 0, H = 0, size = 0, ox = 0, oy = 0, fibres = null, raf = 0, alive = true, dirty = true;
    const view = {...HOME}, spin = {yaw: 0, pitch: 0}, listeners = [];
    const pulses = [], glows = new Map(), waves = [];
    const proj = new Float32Array(NET.nodes.length * 3);                          // screen x, y, depth per node

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
      NET.nodes.forEach((n, i) => { const [x, y, z] = project(n.x, n.y, n.z); proj[i * 3] = x; proj[i * 3 + 1] = y; proj[i * 3 + 2] = z; });
      const f = fibres.getContext("2d"); f.setTransform(dpr, 0, 0, dpr, 0, 0); f.clearRect(0, 0, W, H); f.lineCap = "round";
      const [cx, cy] = project(C[0], C[1], 0), R = size * view.zoom;
      const aura = f.createRadialGradient(cx, cy, R * 0.05, cx, cy, R * 0.42);
      aura.addColorStop(0, "rgba(210,30,60,.10)"); aura.addColorStop(.6, "rgba(210,30,60,.04)"); aura.addColorStop(1, "rgba(0,0,0,0)");
      f.fillStyle = aura; f.fillRect(0, 0, W, H);
      const buckets = [[], [], []];                                                // hairline fibres in three depth layers
      NET.edges.forEach(e => { const s = (shade(e[0]) + shade(e[1])) / 2; buckets[s > 0.75 ? 2 : s > 0.45 ? 1 : 0].push(e); });
      buckets.forEach((list, b) => {
        f.strokeStyle = `rgba(${VIOLET},${[0.09, 0.18, 0.28][b]})`; f.lineWidth = 0.5; f.beginPath();
        list.forEach(([i, j]) => { f.moveTo(proj[i * 3], proj[i * 3 + 1]); f.lineTo(proj[j * 3], proj[j * 3 + 1]); });
        f.stroke();
      });
      f.globalCompositeOperation = "lighter";
      f.strokeStyle = `rgba(${WHITE},.07)`; f.beginPath();                          // the bridge, faint pink-white
      NET.edges.forEach(([i, j]) => { if (NET.nodes[i].g === 3 && NET.nodes[j].g === 3) { f.moveTo(proj[i * 3], proj[i * 3 + 1]); f.lineTo(proj[j * 3], proj[j * 3 + 1]); } });
      f.stroke();
      NET.nodes.forEach((n, i) => {
        const k = n.wall ? shade(i) * 0.7 : n.mid ? 0.8 : shade(i), s = (0.35 + n.n.length * 0.16) * 2.8 * Math.sqrt(view.zoom) * (0.7 + 0.4 * k);
        f.globalAlpha = k; f.drawImage(sprite, proj[i * 3] - s, proj[i * 3 + 1] - s, s * 2, s * 2);
      });
      f.globalAlpha = 1; f.globalCompositeOperation = "source-over";
      dirty = false; listeners.forEach(cb => cb());
    }
    const nearest = (ax, ay, side) => NET.nodes.reduce((best, n, i) => {
      if (side && n.side !== side) return best;
      const d = (n.x - ax) ** 2 + (n.y - ay) ** 2; return d < best[1] ? [i, d] : best; }, [0, 9])[0];
    const anchors = new Map();                                                     // each section's node on the near hemisphere
    const anchorOf = (ax, ay) => { const k = `${ax},${ay}`; if (!anchors.has(k)) anchors.set(k, nearest(ax, ay, -1)); return anchors.get(k); };

    function frame(t) {
      if (!alive) return;
      if (!W || !H) { layout(); if (!W || !H) { raf = requestAnimationFrame(frame); return; } }   // hidden or not laid out yet
      if (!drag && (Math.abs(spin.yaw) > 1e-4 || Math.abs(spin.pitch) > 1e-4)) {   // a little inertia after a flick
        view.yaw += spin.yaw; view.pitch = clampPitch(view.pitch + spin.pitch); spin.yaw *= 0.9; spin.pitch *= 0.9; dirty = true;
      }
      if (tween) { const k = Math.min(1, (t - tween.t0) / 650), e = 1 - (1 - k) ** 3;
        Object.keys(HOME).forEach(p => view[p] = tween.from[p] + (HOME[p] - tween.from[p]) * e); dirty = true; if (k >= 1) tween = null; }
      const active = dirty || waves.length || drag;                               // moving or firing: full speed
      if (!active && t - lastDraw < frameGap) { raf = requestAnimationFrame(frame); return; }   // idle: skip this frame
      lastDraw = t; const w0 = performance.now();
      if (dirty) render();
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = 0.9 + 0.1 * Math.sin(t / 2000); ctx.drawImage(fibres, 0, 0, W, H); ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "lighter";
      glows.forEach((k, key) => {                            // hover: the region warms up
        const [x, y] = P(anchorOf(...key.split(",").map(Number))), R = size * view.zoom * 0.075;
        const g = ctx.createRadialGradient(x, y, 0, x, y, R); g.addColorStop(0, `rgba(${VIOLET},.4)`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill();
      });
      for (let w = waves.length - 1; w >= 0; w--) {          // the fire: nodes flash as the wave passes
        const wv = waves[w], front = (t - wv.t0) / 34; let any = false;
        wv.dist.forEach((d, i) => {
          const k = 1 - Math.abs(front - d) / 3; if (k <= 0) return; any = true;
          const [x, y] = P(i); ctx.fillStyle = `rgba(${WHITE},${Math.min(1, k) * shade(i)})`;
          ctx.beginPath(); ctx.arc(x, y, 1.4 + 2.2 * k, 0, 7); ctx.fill();
        });
        if (!any && front > 4) { waves.splice(w, 1); wv.done(); }
      }
      if (Math.random() < 0.16) {                            // small sparks along fibres
        const e = NET.edges[Math.floor(Math.random() * NET.edges.length)];
        pulses.push({a: e[0], b: e[1], t0: t, ms: 600 + Math.random() * 700});
      }
      for (let p = pulses.length - 1; p >= 0; p--) {
        const pu = pulses[p], k = (t - pu.t0) / pu.ms;
        if (k >= 1) { pulses.splice(p, 1); if (Math.random() < 0.6) { const nb = NET.nodes[pu.b].n; if (nb.length) pulses.push({a: pu.b, b: nb[Math.floor(Math.random() * nb.length)], t0: t, ms: pu.ms}); } continue; }
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
        if (drag.pinch) { view.zoom = Math.max(0.55, Math.min(2.4, view.zoom * d / drag.pinch.d)); view.px += m[0] - drag.pinch.m[0]; view.py += m[1] - drag.pinch.m[1]; }
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
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015)), z = Math.max(0.55, Math.min(2.4, view.zoom * k)), r = canvas.getBoundingClientRect();
      const [cx, cy] = project(C[0], C[1], 0), mx = e.clientX - r.left, my = e.clientY - r.top;
      view.px += (mx - cx) * (1 - z / view.zoom); view.py += (my - cy) * (1 - z / view.zoom);   // zoom toward the pointer
      view.zoom = z; dirty = true;
    };
    const reset = () => { tween = {t0: performance.now(), from: {...view}}; spin.yaw = spin.pitch = 0; };
    canvas.addEventListener("pointerdown", onDown); canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp); canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("wheel", onWheel, {passive: false}); canvas.addEventListener("dblclick", reset);
    canvas.addEventListener("contextmenu", e => e.preventDefault());

    layout(); if (W && H) render();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.drawImage(fibres, 0, 0, W, H); }
    else raf = requestAnimationFrame(frame);
    const onResize = () => { layout(); if (W && H) render(); }; addEventListener("resize", onResize);

    return {
      glow(ax, ay, on) { on ? glows.set(`${ax},${ay}`, 1) : glows.delete(`${ax},${ay}`); },
      fire(ax, ay) {                                         // breadth-first distance from the region's nearest node
        const start = anchorOf(ax, ay), dist = new Array(NET.nodes.length).fill(Infinity); dist[start] = 0;
        const q = [start];
        while (q.length) { const i = q.shift(); NET.nodes[i].n.forEach(j => { if (dist[j] === Infinity) { dist[j] = dist[i] + 1; q.push(j); } }); }
        return new Promise(res => { waves.push({t0: performance.now(), dist: dist.map(d => d === Infinity ? 99 : d), done: res}); setTimeout(res, 900); });
      },
      anchor(ax, ay) { return P(anchorOf(ax, ay)); },       // where a section's region is on screen right now
      onView(cb) { listeners.push(cb); },
      reset,
      destroy() {
        alive = false; cancelAnimationFrame(raf); removeEventListener("resize", onResize);
        canvas.removeEventListener("pointerdown", onDown); canvas.removeEventListener("pointermove", onMove);
        canvas.removeEventListener("pointerup", onUp); canvas.removeEventListener("wheel", onWheel); canvas.removeEventListener("dblclick", reset);
      },
    };
  }
  return {mount, box, inside: (x, y) => region(x, y, true) >= 0};
})();
