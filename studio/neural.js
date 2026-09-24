"use strict";
/* The brain: a fine crimson neural network in side profile (frontal lobe left, cerebellum back-right,
   no brain stem), tuned to be subtle.
   Nodes cluster along fold contours; hairline fibres join near neighbours. At rest small sparks run
   along fibres; hovering a section glows its region; clicking fires a bright wave through the graph.
   API: NeuralBrain.mount(canvas) -> {glow(ax,ay,on), fire(ax,ay) -> Promise, destroy()} */
window.NeuralBrain = (() => {
  const VIOLET = [235, 45, 75], WHITE = [255, 232, 236];   // crimson fibres, pink-white light

  // side profile. Regions: cerebrum (0), temporal lobe (1), cerebellum (2); -1 = outside or in a fissure
  const sylvian = x => 0.585 - 0.19 * (x - 0.3) + 0.22 * (x - 0.3) ** 2;       // lateral sulcus curve
  function region(x, y) {
    const cb = ((x - 0.73) / 0.13) ** 2 + ((y - 0.705) / 0.075) ** 2;             // cerebellum
    if (cb < 1 && y > 0.64) return 2;
    const top = ((x - 0.52) / 0.355) ** 2 + ((y - 0.47) / 0.285) ** 2;            // main cerebral dome
    const front = ((x - 0.3) / 0.19) ** 2 + ((y - 0.46) / 0.21) ** 2;             // fuller frontal pole
    const temp = ((x - 0.47) / 0.21) ** 2 + ((y - 0.61) / 0.1) ** 2;              // temporal lobe
    const inCere = (top < 1 || front < 1) && y < 0.66;
    if (!inCere && !(temp < 1)) return -1;
    if (y > 0.62 && x > 0.66 && cb >= 1) return -1;                              // notch above the cerebellum
    const sy = sylvian(x);
    if (x > 0.24 && x < 0.66 && Math.abs(y - sy) < 0.011) return -1;             // the fissure itself
    if (temp < 1 && y > sy && x < 0.68) return 1;
    return inCere ? 0 : -1;
  }
  const inside = (x, y) => region(x, y) >= 0;
  function fold(x, y) {
    if (region(x, y) === 2) return Math.sin(y * 150 + Math.sin(x * 30) * 1.4);    // cerebellum: fine ridges
    return Math.sin(x * 38 + Math.sin(y * 17) * 2.6) * 0.55 + Math.sin(y * 31 + Math.cos(x * 19) * 2.3) * 0.45;
  }
  function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

  function build() {
    const r = rng(42), nodes = [];
    while (nodes.length < 1900) {
      const x = 0.1 + r() * 0.8, y = 0.16 + r() * 0.66;
      const band = Math.exp(-((fold(x, y) / 0.16) ** 2));   // near a contour = on a fold
      if (inside(x, y) && r() < 0.08 + 0.92 * band) nodes.push({x, y, g: region(x, y), n: []});
    }
    const edges = [];
    nodes.forEach((a, i) => {
      nodes.map((b, j) => [j, (a.x - b.x) ** 2 + (a.y - b.y) ** 2])
        .filter(([j, d]) => j !== i && d < 0.0008 && a.g === nodes[j].g)
        .sort((p, q) => p[1] - q[1]).slice(0, 3)
        .forEach(([j]) => { if (j > i) { edges.push([i, j]); a.n.push(j); nodes[j].n.push(i); } });
    });
    return {nodes, edges};
  }
  const NET = build();

  function mount(canvas) {
    const ctx = canvas.getContext("2d"), dpr = Math.min(2, devicePixelRatio || 1);
    let W = 0, H = 0, size = 0, ox = 0, oy = 0, fibres = null, raf = 0, alive = true;
    const pulses = [], glows = new Map(), waves = [];
    const P = n => [ox + n.x * size, oy + n.y * size];

    function layout() {
      const rect = canvas.getBoundingClientRect();
      W = rect.width; H = rect.height; canvas.width = W * dpr; canvas.height = H * dpr;
      size = Math.min(W * 0.88, H * 1.22); ox = W / 2 - size * 0.5; oy = H * 0.47 - size * 0.46;
      fibres = document.createElement("canvas"); fibres.width = canvas.width; fibres.height = canvas.height;
      const f = fibres.getContext("2d"); f.scale(dpr, dpr); f.lineCap = "round";
      const aura = f.createRadialGradient(ox + size * 0.5, oy + size * 0.47, size * 0.05, ox + size * 0.5, oy + size * 0.47, size * 0.42);
      aura.addColorStop(0, "rgba(210,30,60,.10)"); aura.addColorStop(.6, "rgba(210,30,60,.04)"); aura.addColorStop(1, "rgba(0,0,0,0)");
      f.fillStyle = aura; f.fillRect(0, 0, W, H);
      NET.edges.forEach(([i, j]) => {                        // hairline fibres
        const [x1, y1] = P(NET.nodes[i]), [x2, y2] = P(NET.nodes[j]);
        f.strokeStyle = `rgba(${VIOLET},.26)`; f.lineWidth = 0.5; f.beginPath(); f.moveTo(x1, y1); f.lineTo(x2, y2); f.stroke();
      });
      f.globalCompositeOperation = "lighter";
      NET.nodes.forEach(n => {                               // small, soft nodes
        const [x, y] = P(n), s = 0.35 + n.n.length * 0.16;
        const g = f.createRadialGradient(x, y, 0, x, y, s * 2.8);
        g.addColorStop(0, `rgba(${WHITE},.6)`); g.addColorStop(.35, `rgba(${VIOLET},.3)`); g.addColorStop(1, "rgba(0,0,0,0)");
        f.fillStyle = g; f.beginPath(); f.arc(x, y, s * 2.8, 0, 7); f.fill();
      });
    }
    const nearest = (ax, ay) => NET.nodes.reduce((best, n, i) => {
      const d = (n.x - ax) ** 2 + (n.y - ay) ** 2; return d < best[1] ? [i, d] : best; }, [0, 9])[0];

    function frame(t) {
      if (!alive) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = 0.9 + 0.1 * Math.sin(t / 2000); ctx.drawImage(fibres, 0, 0, W, H); ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "lighter";
      glows.forEach((k, key) => {                            // hover: the region warms up
        const [ax, ay] = key.split(",").map(Number), x = ox + ax * size, y = oy + ay * size, R = size * 0.075;
        const g = ctx.createRadialGradient(x, y, 0, x, y, R); g.addColorStop(0, `rgba(${VIOLET},.4)`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, R, 0, 7); ctx.fill();
      });
      for (let w = waves.length - 1; w >= 0; w--) {          // the fire: nodes flash as the wave passes
        const wv = waves[w], front = (t - wv.t0) / 34; let any = false;
        wv.dist.forEach((d, i) => {
          const k = 1 - Math.abs(front - d) / 3; if (k <= 0) return; any = true;
          const [x, y] = P(NET.nodes[i]); ctx.fillStyle = `rgba(${WHITE},${Math.min(1, k)})`;
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
        const [x1, y1] = P(NET.nodes[pu.a]), [x2, y2] = P(NET.nodes[pu.b]), x = x1 + (x2 - x1) * k, y = y1 + (y2 - y1) * k;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 4.5); g.addColorStop(0, `rgba(${WHITE},.85)`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 4.5, 0, 7); ctx.fill();
      }
      if (pulses.length > 40) pulses.splice(0, pulses.length - 40);
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(frame);
    }

    layout();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.drawImage(fibres, 0, 0, W, H); }
    else raf = requestAnimationFrame(frame);
    const onResize = () => layout(); addEventListener("resize", onResize);

    return {
      glow(ax, ay, on) { on ? glows.set(`${ax},${ay}`, 1) : glows.delete(`${ax},${ay}`); },
      fire(ax, ay) {                                         // breadth-first distance from the region's nearest node
        const start = nearest(ax, ay), dist = new Array(NET.nodes.length).fill(Infinity); dist[start] = 0;
        const q = [start];
        while (q.length) { const i = q.shift(); NET.nodes[i].n.forEach(j => { if (dist[j] === Infinity) { dist[j] = dist[i] + 1; q.push(j); } }); }
        return new Promise(res => { waves.push({t0: performance.now(), dist: dist.map(d => d === Infinity ? 99 : d), done: res}); setTimeout(res, 900); });
      },
      destroy() { alive = false; cancelAnimationFrame(raf); removeEventListener("resize", onResize); },
    };
  }
  return {mount, geometry: size => size};
})();
