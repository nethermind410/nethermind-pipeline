"use strict";
/* Every page opens with its answer: one question, the answer from real data, and the next action.
   (studio_ext_verdict.py works the answers out; this puts them at the top of each page.) */
(() => {
  const PAGES = ["comments", "today", "videos", "calendar", "performance", "retention", "channel", "agents", "settings", "ideas"];
  async function show(name) {
    let v; try { v = await get("/api/verdict/" + name); } catch (e) { return; }
    const page = main.firstElementChild; if (!page || !v.answer || page.querySelector(".vd")) return;
    const el = document.createElement("section");
    el.className = `vd ${v.tone}`;
    el.innerHTML = `<span class="vd-q">${esc(v.q)}</span><div class="vd-a">${esc(v.answer)}</div>
      ${v.detail ? `<p>${esc(v.detail)}</p>` : ""}
      ${v.actions.length ? `<div class="vd-acts">${v.actions.map((a, i) => `<button class="btn ${a.primary ? "primary" : ""}" data-vd="${i}">${esc(a.label)}</button>`).join("")}</div>` : ""}`;
    const after = page.querySelector(".head-row") || page.querySelector(".head") || page.querySelector(".hub");
    after ? after.after(el) : page.prepend(el);
    el.querySelectorAll("[data-vd]").forEach(b => b.onclick = async () => {
      const a = v.actions[+b.dataset.vd];
      if (a.go) return go(a.go);
      if (a.run) return window.nxDay?.start();
      if (a.job) return runJob(a.job, "");
      if (a.confirm && !confirm(a.confirm)) return;
      try { const r = await post(a.post, a.body || {}); toast(r.reply || "Done."); window.nxSound?.play("done"); setTimeout(route, 500); } catch (e) { toast(e.message); }
    });
  }
  document.addEventListener("DOMContentLoaded", () => {      // runs after ext_nether has wrapped the hub pages
    PAGES.forEach(name => {
      const f = window.PAGES[name]; if (!f) return;
      const g = async (...a) => { await f(...a); await show(name); };
      Object.keys(window.PAGES).forEach(k => { if (window.PAGES[k] === f) window.PAGES[k] = g; });   // hub aliases too (control → agents)
    });
  });
})();
