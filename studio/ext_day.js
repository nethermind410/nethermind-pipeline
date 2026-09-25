"use strict";
/* Today's run: one tap walks you through today, posting first.
   A dock sits bottom-right on every page. Closed, it says what today still needs ("Post today's Short · 3 jobs")
   and glows until today's Short is out. Tap it and it takes you job by job: Go opens the right page, Done ticks it
   off and moves to the next. It never posts for you — it takes you to the Post button.
   Also here: when a video goes out (scheduled or live), a celebration — a burst across the screen, a chime if
   interface sounds are on, and an impulse from Publishing to Analytics on the brain. */
(() => {
  const LS = (k, v) => { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } };
  let day = null, i = 0, running = false;
  const dock = document.createElement("div");
  dock.className = "dayrun";
  dock.setAttribute("role", "region"); dock.setAttribute("aria-label", "Today's run");
  const ticked = () => (LS("nx-day") || {})[day?.date] || [];
  const isDone = s => s.done || ticked().includes(s.key);
  const tick = key => { const all = LS("nx-day") || {}; const d = day.date; all[d] = [...new Set([...(all[d] || []), key])];
    Object.keys(all).forEach(k => { if (k !== d) delete all[k]; }); LS("nx-day", all); };
  const kindWord = {post: "Post", approve: "Approve", finish: "Finish", decide: "Decide", make: "Make", nice: "Community", fix: "Fix"};

  function render() {
    if (!day) { dock.innerHTML = ""; return; }
    const steps = day.steps, left = steps.filter(s => !isDone(s)), postOut = isDone(day.post);
    dock.classList.toggle("urgent", !postOut); dock.classList.toggle("open", running);
    if (!running) {
      const label = !left.length ? `Day done${day.streak ? ` · ${day.streak}-day streak` : ""}` : !postOut ? day.post.title : `${left.length} job${left.length > 1 ? "s" : ""} left today`;
      dock.innerHTML = `<button class="dr-pill ${left.length ? "" : "clear"}" data-dr="start" title="${left.length ? "Walk me through today" : "Everything's done — nice"}">
        <span class="dr-play">${left.length ? "▶" : "✓"}</span><span><b>${esc(label)}</b>${left.length ? `<em>${left.length} job${left.length > 1 ? "s" : ""} · tap to start</em>` : `<em>${day.out} of 7 out this week</em>`}</span></button>`;
      return;
    }
    i = Math.max(0, Math.min(i, steps.length - 1));
    const s = steps[i], done = isDone(s);
    dock.innerHTML = `<div class="dr-card">
      <div class="dr-top"><span class="k">Today · ${i + 1} of ${steps.length}</span>
        <span class="dr-beads">${steps.map((x, n) => `<i class="${isDone(x) ? "done" : ""} ${n === i ? "on" : ""} ${x.kind === "post" ? "post" : ""}" title="${esc(x.title)}" data-dr-jump="${n}"></i>`).join("")}</span>
        <button class="dr-x" data-dr="close" aria-label="Close">×</button></div>
      <span class="dr-kind ${s.kind}">${esc(kindWord[s.kind] || s.kind)}</span>
      <h3>${done ? "✓ " : ""}${esc(s.title)}</h3><p>${esc(s.why)}</p>
      <div class="dr-acts">${done ? `<button class="btn primary" data-dr="next">${i < steps.length - 1 ? "Next job ›" : "Finish"}</button>`
        : `<button class="btn primary" data-dr="go">Go</button><button class="btn" data-dr="done">Done ✓</button><button class="btn ghost" data-dr="skip">Skip</button>`}</div></div>`;
  }
  function nextOpen(from) { const n = day.steps.findIndex((s, k) => k > from && !isDone(s)); return n < 0 ? day.steps.findIndex(s => !isDone(s)) : n; }
  function finish() {
    running = false; render();
    if (!day.steps.some(s => !isDone(s))) { celebrate("Day done", `${day.out} of 7 out this week${day.streak ? ` · ${day.streak}-day streak` : ""}`); }
  }
  dock.addEventListener("click", e => {
    const b = e.target.closest("[data-dr],[data-dr-jump]"); if (!b) return;
    const a = b.dataset.dr;
    if (b.dataset.drJump) { i = +b.dataset.drJump; return render(); }
    if (a === "start") { running = true; i = Math.max(0, nextOpen(-1)); window.nxSound?.play("tick"); return render(); }
    if (a === "close") { running = false; return render(); }
    const s = day.steps[i];
    if (a === "go") { window.nxSound?.play("tick"); go(s.go); return; }
    if (a === "done") { tick(s.key); window.nxSound?.play("done"); }
    if (a === "done" || a === "skip" || a === "next") {
      const n = nextOpen(i);
      if (n < 0 || (a === "next" && i === day.steps.length - 1 && n <= i)) return finish();
      i = n; render();
    }
  });
  async function load() {
    try { day = await get("/api/day"); } catch (e) { return; }
    render();
    const nav = document.querySelector('.nav[data-go="today"]');       // a reminder dot on Today until the Short is out
    if (nav) nav.classList.toggle("post-due", !isDone(day.post));
  }

  /* ---------- a video went out: celebrate ---------- */
  function burst() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const c = document.createElement("canvas"); c.className = "dr-burst"; document.body.appendChild(c);
    const W = c.width = innerWidth * devicePixelRatio, H = c.height = innerHeight * devicePixelRatio, x = c.getContext("2d");
    const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#E0294B";
    const P = Array.from({length: 140}, () => { const a = Math.random() * Math.PI * 2, v = (2 + Math.random() * 9) * devicePixelRatio;
      return {x: W / 2, y: H * 0.45, vx: Math.cos(a) * v, vy: Math.sin(a) * v, r: (1 + Math.random() * 2.4) * devicePixelRatio, w: Math.random() < 0.3}; });
    const t0 = performance.now();
    (function f(t) {
      const k = (t - t0) / 1600; x.clearRect(0, 0, W, H);
      if (k >= 1) return c.remove();
      P.forEach(p => { p.x += p.vx; p.y += p.vy; p.vx *= 0.975; p.vy = p.vy * 0.975 + 0.05;
        x.globalAlpha = 1 - k; x.fillStyle = p.w ? "#fff" : accent; x.shadowColor = accent; x.shadowBlur = 12;
        x.beginPath(); x.arc(p.x, p.y, p.r, 0, Math.PI * 2); x.fill(); });
      requestAnimationFrame(f);
    })(t0);
  }
  function celebrate(title, sub) {
    burst(); window.nxSound?.play("celebrate");
    window.nxFire?.("publishing", "analytics");
    toast(`${title}${sub ? " — " + sub : ""}`);
  }
  async function watchOut() {
    let w; try { w = await get("/api/week"); } catch (e) { return; }
    const key = w.days[0].date, out = w.days.filter(d => ["live", "scheduled"].includes(d.stage)).map(d => `${d.id}:${d.stage}`);
    if (w.long && ["live", "scheduled"].includes(w.long.stage)) out.push(`${w.long.id}:${w.long.stage}`);
    const seen = LS("nx-out");
    if (seen && seen.week === key) {
      const fresh = out.filter(x => !seen.ids.includes(x));
      fresh.forEach((x, n) => { const [id, st] = x.split(":"), d = w.days.find(y => y.id === id) || w.long;
        setTimeout(() => { celebrate(`“${d.title}” is ${st === "live" ? "live" : "queued"}`, `${w.out} of 7 this week`); load(); }, n * 2200); });
    }
    LS("nx-out", {week: key, ids: out});
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(dock);
    load(); watchOut();
    setInterval(() => { if (!document.hidden) { load(); watchOut(); } }, 45000);
    let t; window.addEventListener("hashchange", () => { clearTimeout(t); t = setTimeout(load, 1200); });
  });
  window.nxDay = {celebrate, reload: load};
})();
