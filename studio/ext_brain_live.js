"use strict";
/* Real activity on the brain, and NETHER's form.
   · Working agents (from /api/system, which ext_nether.js already polls and shares as an "nx-system" event) and a
     running Studio job (/api/job) make their region breathe and send out small local waves until they finish.
     ext_nether.js keeps its own dendrite sparks; this adds the region itself.
   · New views or comments since you last looked (remembered in localStorage) fire a one-off wave from Analytics
     or Business with a small caption — real numbers only, and nothing at all when nothing changed.
   · Settings → NETHER's form: brain, eye, heart or tongue (organs/*.json), stored server-side via POST /api/organ. */
(() => {
  let ACT = null, sys = null, job = null, net = null;
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const onBrain = () => document.body.classList.contains("on-brain") && window.brainNet && !document.hidden;
  const sections = () => (typeof NEURONS !== "undefined" ? NEURONS : []);
  get("/api/brain/actions").then(a => ACT = a).catch(() => {});

  /* ---------- working agents ---------- */
  function working() {
    const w = new Set((sys?.agents || []).filter(a => a.state === "working").map(a => a.key));
    if (sys?.investigating) w.add("intelligence");
    if (job && !job.done && ACT?.[job.action]) w.add(ACT[job.action]);
    return w;
  }
  function apply() {
    if (!window.brainNet) return;
    const w = working();
    sections().forEach(n => brainNet.busy(n.ax, n.ay, w.has(n.key)));
  }
  window.addEventListener("nx-system", e => { sys = e.detail; apply(); });
  setInterval(async () => {
    if (!onBrain()) return;
    try { job = await get("/api/job"); } catch (e) { job = null; }
    apply();
  }, 4000);
  setInterval(() => {                                  // a freshly mounted brain: re-apply, then look for news
    if (!document.body.classList.contains("on-brain") || !window.brainNet || brainNet === net) return;
    net = brainNet; notes.length = 0; brainNet.onView(placeNotes); apply(); since();
  }, 500);

  /* ---------- since you last looked ---------- */
  async function since() {
    const [vids, com] = await Promise.all([get("/api/videos").catch(() => null), get("/api/comments").catch(() => null)]);
    if (!vids && !com) return;
    const views = Array.isArray(vids) ? vids.reduce((s, v) => s + (+v.views || 0), 0) : null;
    const ids = com?.comments ? com.comments.map(c => c.id) : null;
    let prev = null; try { prev = JSON.parse(localStorage.getItem("nx-seen") || "null"); } catch (e) { prev = null; }
    const keep = {views: views ?? prev?.views ?? null, comments: (ids ?? prev?.comments ?? []).slice(-500), at: new Date().toISOString()};
    try { localStorage.setItem("nx-seen", JSON.stringify(keep)); } catch (e) {}
    if (!prev) return;                                 // first visit: remember, say nothing
    const news = [];
    if (views != null && prev.views != null && views > prev.views) {
      const d = views - prev.views; news.push({key: "analytics", text: `+${fmt(d)} view${d === 1 ? "" : "s"} since you last looked`});
    }
    if (ids && Array.isArray(prev.comments)) {
      const seen = new Set(prev.comments), n = ids.filter(i => !seen.has(i)).length;
      if (n) news.push({key: "business", text: `+${n} new comment${n === 1 ? "" : "s"} since you last looked`});
    }
    news.forEach((o, i) => setTimeout(() => announce(o), 1100 + i * 1500));
  }
  const notes = [];
  function announce(o) {
    const stage = $("#stage"), n = sections().find(x => x.key === o.key);
    if (!stage || !n || !onBrain()) return;
    if (!reduced()) brainNet.fire(n.ax, n.ay);
    const el = document.createElement("div"); el.className = "bx-note"; el.setAttribute("role", "status");
    el.innerHTML = `<span class="k">${esc(n.label)}</span>${esc(o.text)}`;
    stage.append(el); const note = {el, n}; notes.push(note); placeNotes();
    requestAnimationFrame(() => el.classList.add("in"));
    setTimeout(() => { el.classList.remove("in"); setTimeout(() => { el.remove(); notes.splice(notes.indexOf(note), 1); }, 600); }, 8000);
  }
  function placeNotes() {
    const c = $("#bnet"), stage = $("#stage"); if (!c || !stage || !window.brainNet) return;
    const S = stage.getBoundingClientRect(), R = c.getBoundingClientRect();
    notes.forEach(({el, n}, i) => {
      const [x, y] = brainNet.anchor(n.ax, n.ay);
      el.style.left = Math.max(12, Math.min(S.width - el.offsetWidth - 12, R.left - S.left + x + 18)) + "px";
      el.style.top = Math.max(80, R.top - S.top + y - el.offsetHeight - 14 - i * 4) + "px";
    });
  }

  /* ---------- Settings: NETHER's form ---------- */
  const base = window.PAGES.settings;
  window.PAGES.settings = async (...a) => {
    await base(...a);
    let d; try { d = await get("/api/organ"); } catch (e) { return; }
    const page = main.querySelector(".page"); if (!page || $("#bx-form")) return;
    page.insertAdjacentHTML("beforeend", `<h2>NETHER's form</h2><div class="card bx-form" id="bx-form">
      <div class="bx-choices" role="radiogroup" aria-label="NETHER's form">${d.choices.map(c => `<button class="bx-choice" role="radio" data-organ="${esc(c.name)}">
        <b>${esc(c.title)}</b><span>${esc(c.blurb)}</span></button>`).join("")}</div>
      <div class="bx-prev"><canvas id="bx-preview" role="img" aria-label="Preview of NETHER's form — drag to turn it"></canvas><ul class="bx-map" id="bx-map"></ul></div>
      <p class="fine">The home page takes this shape. Each agent lives in one of its regions; labels, lines and close-ups follow.</p></div>`);
    await NeuralBrain.ready.catch(() => null);
    if (NeuralBrain.organ()?.name !== d.name) await NeuralBrain.use(d.name).catch(() => null);
    show();
  };
  function show() {
    const O = NeuralBrain.organ(); if (!O || !$("#bx-form")) return;
    document.querySelectorAll(".bx-choice").forEach(b => { const on = b.dataset.organ === O.name; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
    $("#bx-map").innerHTML = sections().map(n => `<li><b>${esc(n.label)}</b><span>${esc(NeuralBrain.lobe(n.key) || n.lobe)}</span></li>`).join("");
    window._bxPrev?.destroy(); window._bxPrev = NeuralBrain.mount($("#bx-preview"));
  }
  document.addEventListener("click", async e => {
    const b = e.target.closest?.("[data-organ]"); if (!b || b.classList.contains("on") || b.disabled) return;
    document.querySelectorAll(".bx-choice").forEach(x => x.disabled = true);
    try { const r = await post("/api/organ", {name: b.dataset.organ}); await NeuralBrain.use(r.name); show(); toast(r.reply); }
    catch (err) { toast(err.message); }
    document.querySelectorAll(".bx-choice").forEach(x => x.disabled = false);
  });
})();
