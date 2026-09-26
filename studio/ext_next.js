"use strict";
/* "What's next?" — the one card the home brain answers at a glance.
   Server-derived (studio_ext_next.py /api/next_step) from the exact same priority order as
   Today's run: post today's Short → approve a waiting script → fix a failing connection →
   reply to comments → make the next video... One recommendation, one line of why, one button.
   Everything else waiting today sits behind "N more today", which opens Today. */
(() => {
  function html(ns) {
    if (!ns) return "";
    if (ns.done) return `<div class="ns-card calm"><b>All caught up</b><span>${ns.streak ? `${ns.streak}-day streak · ` : ""}${ns.out} of 7 out this week</span></div>`;
    const more = ns.more > 0 ? `<button class="ns-more" data-go="today">${ns.more} more today</button>` : "";
    return `<div class="ns-card">
      <span class="ns-label">Next best step</span>
      <b class="ns-title">${esc(ns.action.title)}</b>
      <span class="ns-why">${esc(ns.action.why)}</span>
      <div class="ns-row"><button class="btn primary small" data-go="${esc(ns.action.go)}">Go →</button>${more}</div>
    </div>`;
  }
  async function paint() {
    const host = document.getElementById("next-step");
    if (!host) return;
    let ns; try { ns = await get("/api/next_step"); } catch (e) { return; }
    host.innerHTML = html(ns);
  }
  window.nxNext = {reload: paint};
  window.addEventListener("nx-done", () => document.body.classList.contains("on-brain") && paint());
  window.addEventListener("nx-job", e => { if (document.body.classList.contains("on-brain") && (!e.detail || e.detail.type !== "progress")) paint(); });
})();
