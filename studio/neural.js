"use strict";
/* The brain, suggested rather than drawn: hairline bone-white strokes that follow the folds of a
   brain seen from above (no outline, no dots, no colour). A wave of light runs along the folds when
   a section fires; a faint glint now and then travels one fold at rest.
   API: NeuralBrain.mount(canvas) -> {glow(ax,ay,on), fire(ax,ay) -> Promise, destroy()} */
window.NeuralBrain = (() => {
  const BONE = "247,247,238", BLUSH = "255,214,204", PINKWHITE = "255,236,230";
  // look 1 = glowing folds · 2 = synapses on folds · 3 = light sweep (chosen in Settings; ?look=N to preview)
  const LOOK = +(new URLSearchParams(location.search).get("look") || (() => { try { return localStorage.getItem("brainLook"); } catch (e) { return null; } })() || 1);

  function inside(x, y) {                                  // top-view silhouette with a midline fissure
    const dx = x - 0.5, dy = y - 0.5;
    if (Math.abs(dx) < 0.016 + 0.012 * Math.abs(dy) * 4) return false;
    const rx = 0.28 * (1 - 0.13 * Math.max(0, -dy) * 3) * (1 + 0.02 * Math.sin(y * 40)), ry = 0.32;
    return (dx / rx) ** 2 + (dy / ry) ** 2 < 1;
  }
  function field(x, y) {                                   // fold field, mirrored across the midline
    const m = Math.abs(x - 0.5);
    return Math.sin(m * 44 + Math.sin(y * 17) * 2.3) * 0.55 + Math.sin(y * 30 + Math.cos(m * 19) * 2.2) * 0.45;
  }
  function rng(seed) { return () => (seed = (seed * 16807) % 2147483647) / 2147483647; }

  /* trace contour lines of the fold field: step along the direction perpendicular to its gradient */
  function trace() {
    const r = rng(7), strokes = [], occ = new Set(), cell = 0.012, h = 0.0045, e = 1e-4;
    const key = (x, y) => `${Math.round(x / cell)},${Math.round(y / cell)}`;
    for (let tries = 0; tries < 900 && strokes.length < 150; tries++) {
      const x = 0.2 + r() * 0.6, y = 0.16 + r() * 0.68;
      if (!inside(x, y) || occ.has(key(x, y))) continue;
      const pts = [[x, y]], own = new Set([key(x, y)]);
      for (const dir of [1, -1]) {
        let px = x, py = y;
        for (let s = 0; s < 160; s++) {
          const gx = (field(px + e, py) - field(px - e, py)) / (2 * e), gy = (field(px, py + e) - field(px, py - e)) / (2 * e);
          const len = Math.hypot(gx, gy) || 1, nx = px + dir * (-gy / len) * h, ny = py + dir * (gx / len) * h;
          const k = key(nx, ny);
          if (!inside(nx, ny) || (occ.has(k) && !own.has(k))) break;
          own.add(k); px = nx; py = ny; dir > 0 ? pts.push([px, py]) : pts.unshift([px, py]);
        }
      }
      if (pts.length > 14) { strokes.push(pts); own.forEach(k => occ.add(k)); }
    }
    return strokes;
  }
  const STROKES = trace();

  function mount(canvas) {
    const ctx = canvas.getContext("2d"), dpr = Math.min(2, devicePixelRatio || 1);
    let W = 0, H = 0, size = 0, ox = 0, oy = 0, base = null, raf = 0, alive = true;
    const glows = new Map(), waves = [], glints = [];
    const P = ([x, y]) => [ox + x * size, oy + y * size];
    const path = (c, pts) => { c.beginPath(); pts.forEach((p, i) => { const [x, y] = P(p); i ? c.lineTo(x, y) : c.moveTo(x, y); }); };

    function layout() {
      const rect = canvas.getBoundingClientRect();
      W = rect.width; H = rect.height; canvas.width = W * dpr; canvas.height = H * dpr;
      size = Math.min(W, H); ox = (W - size) / 2; oy = (H - size) / 2;
      base = document.createElement("canvas"); base.width = canvas.width; base.height = canvas.height;
      const b = base.getContext("2d"); b.scale(dpr, dpr); b.lineCap = b.lineJoin = "round";
      if (LOOK === 1) {                                   // soft blush glow on every fold
        b.shadowColor = `rgba(${BLUSH},.55)`; b.shadowBlur = 9;
        STROKES.forEach((s, i) => { b.strokeStyle = `rgba(${BLUSH},${0.22 + (i % 5) * 0.04})`; b.lineWidth = 0.9; path(b, s); b.stroke(); });
        b.shadowBlur = 0;
      } else if (LOOK === 2) {                            // faint folds with glowing nodes along them
        STROKES.forEach(s => { b.strokeStyle = `rgba(${BONE},.07)`; b.lineWidth = 0.7; path(b, s); b.stroke(); });
        b.globalCompositeOperation = "lighter";
        STROKES.forEach(s => s.forEach((p, j) => { if (j % 7) return; const [x, y] = P(p), r = 2.6 + (j % 3);
          const g = b.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, `rgba(${PINKWHITE},.75)`); g.addColorStop(1, "rgba(0,0,0,0)");
          b.fillStyle = g; b.beginPath(); b.arc(x, y, r, 0, 7); b.fill(); }));
        b.globalCompositeOperation = "source-over";
      } else {                                            // dark folds; the sweep lights them each frame
        STROKES.forEach(s => { b.strokeStyle = `rgba(${BONE},.06)`; b.lineWidth = 0.8; path(b, s); b.stroke(); });
        const core = b.createRadialGradient(ox + size / 2, oy + size / 2, 0, ox + size / 2, oy + size / 2, size * 0.34);
        core.addColorStop(0, `rgba(${BLUSH},.10)`); core.addColorStop(1, "rgba(0,0,0,0)"); b.fillStyle = core; b.fillRect(0, 0, W, H);
      }
    }
    const distTo = (s, ax, ay) => Math.min(...s.map(([x, y]) => Math.hypot(x - ax, y - ay)));

    function frame(t) {
      if (!alive) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = LOOK === 1 ? 0.78 + 0.22 * Math.sin(t / 1900) : 1;
      ctx.drawImage(base, 0, 0, W, H); ctx.globalAlpha = 1;
      ctx.lineCap = ctx.lineJoin = "round";
      if (LOOK === 3) {                                   // a slow diagonal band of warm light
        const k = ((t / 6500) % 1.6) - 0.3, x0 = ox + size * k, g = ctx.createLinearGradient(x0 - size * 0.18, oy, x0 + size * 0.18, oy + size * 0.4);
        g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(.5, `rgba(${PINKWHITE},.75)`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.strokeStyle = g; ctx.lineWidth = 1; ctx.shadowColor = `rgba(${BLUSH},.8)`; ctx.shadowBlur = 8;
        STROKES.forEach(s => { path(ctx, s); ctx.stroke(); }); ctx.shadowBlur = 0;
      }
      glows.forEach(near => { ctx.strokeStyle = `rgba(${PINKWHITE},.6)`; ctx.lineWidth = 1; ctx.shadowColor = `rgba(${BLUSH},.8)`; ctx.shadowBlur = 6; near.forEach(s => { path(ctx, s); ctx.stroke(); }); ctx.shadowBlur = 0; });
      for (let w = waves.length - 1; w >= 0; w--) {          // the fire: light races outward along the folds
        const wv = waves[w], front = (t - wv.t0) / 1100 * 0.75; let any = false;
        wv.d.forEach((d, i) => {
          const k = 1 - Math.abs(front - d) / 0.07; if (k <= 0) return; any = true;
          ctx.strokeStyle = `rgba(${PINKWHITE},${Math.min(1, k)})`; ctx.lineWidth = 0.8 + 1.4 * k;
          ctx.shadowColor = `rgba(${BLUSH},.95)`; ctx.shadowBlur = 10 * k; path(ctx, STROKES[i]); ctx.stroke(); ctx.shadowBlur = 0;
        });
        if (!any && front > 0.12) { waves.splice(w, 1); wv.done(); }
      }
      if (Math.random() < (LOOK === 2 ? 0.09 : 0.012) && glints.length < (LOOK === 2 ? 9 : 3)) glints.push({s: STROKES[Math.floor(Math.random() * STROKES.length)], t0: t, ms: 2600});
      for (let g = glints.length - 1; g >= 0; g--) {          // idle glint along one fold
        const gl = glints[g], k = (t - gl.t0) / gl.ms; if (k >= 1) { glints.splice(g, 1); continue; }
        const n = gl.s.length, i = Math.floor(k * (n - 1)), seg = gl.s.slice(Math.max(0, i - 8), i + 1);
        ctx.strokeStyle = `rgba(${PINKWHITE},${(LOOK === 2 ? 0.85 : 0.6) * Math.sin(k * Math.PI)})`; ctx.lineWidth = 1.2;
        ctx.shadowColor = `rgba(${BLUSH},.9)`; ctx.shadowBlur = 8; path(ctx, seg); ctx.stroke(); ctx.shadowBlur = 0;
      }
      raf = requestAnimationFrame(frame);
    }

    layout();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.drawImage(base, 0, 0, W, H); }
    else raf = requestAnimationFrame(frame);
    const onResize = () => layout(); addEventListener("resize", onResize);

    return {
      glow(ax, ay, on) {
        const k = `${ax},${ay}`;
        on ? glows.set(k, STROKES.filter(s => distTo(s, ax, ay) < 0.06)) : glows.delete(k);
      },
      fire(ax, ay) {
        return new Promise(res => { waves.push({t0: performance.now(), d: STROKES.map(s => distTo(s, ax, ay)), done: res}); setTimeout(res, 1000); });
      },
      destroy() { alive = false; cancelAnimationFrame(raf); removeEventListener("resize", onResize); },
    };
  }
  return {mount};
})();
