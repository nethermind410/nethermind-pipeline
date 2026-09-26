"use strict";
/* Today: a calm "Make your first video" card, shown until the channel has made one.
   Walks: pick an idea → draft it (existing /api/make/draft) → watch it get written (polls itself) →
   review & approve (the existing draft page). Nothing here posts anything on its own. */
(() => {
  const STEPS = ["Pick an idea", "Draft it", "Watch it get written", "Review & approve"];
  let timer = null;

  function dots(step) {
    return STEPS.map((t, i) => `<span class="${i < step ? "done" : i === step ? "on" : ""}" title="${esc(t)}"></span>`).join("");
  }

  function body(s) {
    if (s.draft) return `<p class="nxf-lead">NETHER finished a script for "${esc(s.draft.title)}". Read it, edit any line, then approve — it only moves on once you say so.</p>
      <button class="nxf-btn primary" data-nxf="review" data-id="${esc(s.draft.id)}">Read &amp; approve</button>`;
    if (s.busy) return `<p class="nxf-lead"><span class="nxf-spin" aria-hidden="true"></span>NETHER is researching and writing it now — usually 3–6 minutes. This card updates on its own.</p>`;
    if (s.next) return `<p class="nxf-lead">Next up: "${esc(s.next.hook)}". NETHER will research it and write a full script for you to review.</p>
      <button class="nxf-btn primary" data-nxf="draft" data-topic="${esc(s.next.hook)}">Draft it</button>`;
    if (s.picks && s.picks.length) return `<p class="nxf-lead">Pick one to start with — NETHER researches it and writes the full script.</p>
      <div class="nxf-picks">${s.picks.map(i => `<button class="nxf-pick" data-nxf="draft" data-slug="${esc(i.slug)}" data-topic="${esc(i.hook)}">${esc(i.hook)}</button>`).join("")}</div>`;
    return `<p class="nxf-lead">Add an idea in <button class="nxf-link" data-go="ideas">Ideas</button> to get started.</p>`;
  }

  function card(s) {
    return `<div class="card nxf-card" role="group" aria-label="Make your first video">
      <div class="nxf-head"><span class="nxf-mark" aria-hidden="true"></span>
        <div><b>Make your first video</b><div class="nxf-dots" aria-hidden="true">${dots(s.step)}</div></div></div>
      ${body(s)}
      <p class="nxf-fine">Nothing here posts by itself — every video waits for your review first.</p>
    </div>`;
  }

  function stop() { clearInterval(timer); timer = null; }

  async function paint() {
    if (location.hash !== "#today") return stop();
    let s; try { s = await get("/api/first"); } catch { return; }
    const host = main.querySelector(".page");
    if (!host) return;
    host.querySelector(".nxf-card")?.remove();
    if (!s.show) return stop();
    (host.querySelector(".head") || host.firstElementChild)?.insertAdjacentHTML("afterend", card(s));
    if (s.busy && !timer) timer = setInterval(paint, 3000);
    else if (!s.busy && timer) stop();
  }

  const base = window.PAGES.today;
  window.PAGES.today = async (...a) => { await base(...a); await paint(); };
  window.addEventListener("hashchange", () => { if (location.hash !== "#today") stop(); });

  document.addEventListener("click", async e => {
    const b = e.target.closest("[data-nxf]"); if (!b) return;
    if (b.dataset.nxf === "review") return go("draft/" + b.dataset.id);
    if (b.dataset.nxf === "draft") {
      b.disabled = true;
      try {
        if (b.dataset.slug) await post("/api/next", {slug: b.dataset.slug, hook: b.dataset.topic});
        const r = await post("/api/make/draft", {topic: b.dataset.topic});
        toast(r.reply);
        paint();
      } catch (err) { toast(err.message); b.disabled = false; }
    }
  });
})();
