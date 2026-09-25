"use strict";
/* Retention & Episodes — hook/pacing checklist beside real watch time, TikTok cuts, episode builds.
   Uses the shared helpers from app.js ($, esc, get, post, toast, sheet, main). */
(() => {
  const nav = document.createElement("button");
  nav.className = "nav"; nav.dataset.go = "retention";
  nav.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 7v5l3 2"/><circle cx="12" cy="12" r="9"/></svg>Retention`;
  const settings = document.querySelector('.nav[data-go="settings"]');
  settings ? settings.before(nav) : document.querySelector(".side").append(nav);

  const bar = (score) => `<span class="rt-score"><i style="width:${score * 10}%"></i></span><b>${score}/10</b>`;
  const real = (r) => !r ? `<span class="rt-none">not posted</span>`
    : `${Number(r.views).toLocaleString()} views${r.avg_watch != null ? ` · <b>${r.avg_watch}s</b> avg watch` : ""}`;
  const list = (c) => c.rows.map(x => `<li class="${x.ok ? "ok" : "no"}">${x.ok ? "✓" : "✗"} ${esc(x.msg)}</li>`).join("");

  async function pageRetention() {
    const d = await get("/api/retention");
    const vids = d.videos.map(v => `<div class="card rt-card">
        <div class="rt-top"><button class="link rt-title" data-open="${esc(v.id)}">${esc(v.hook || v.id)}</button>
          <span class="pill">${v.main.length}s</span></div>
        <div class="rt-cols">
          <div><span class="k">Short checklist</span><div class="rt-line">${bar(v.main.score)}</div></div>
          <div><span class="k">TikTok cut</span><div class="rt-line">${v.tiktok ? bar(v.tiktok.score) : `<span class="rt-none">none yet</span>`}</div></div>
          <div><span class="k">TikTok, real</span><div class="rt-line">${real(v.real.tiktok)}</div></div>
          <div><span class="k">Instagram, real</span><div class="rt-line">${real(v.real.instagram)}</div></div>
        </div>
        <details><summary>What the checklist sees</summary><ul class="rt-list">${list(v.main)}</ul>
          ${v.tiktok ? `<span class="k">TikTok cut</span><ul class="rt-list">${list(v.tiktok)}</ul>` : ""}</details>
        <div class="rt-actions"><button class="btn small" data-rt-cut="${esc(v.id)}">${v.tiktok ? "Remake TikTok cut" : "Make TikTok cut"}</button></div>
      </div>`).join("");
    const eps = d.episodes.map(e => `<div class="card rt-card"><div class="rt-top"><b>${esc(e.title)}</b>
        <span class="pill ${e.planned ? "live" : ""}">${e.planned ? "Planned" : "Not built"}</span></div>
        <ol class="rt-ch">${e.chapters.map(c => `<li>${esc(c)}</li>`).join("")}</ol>
        <div class="rt-actions"><button class="btn small primary" data-rt-ep="${esc(e.id)}">Build Shorts + plan</button></div></div>`).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>Retention</h1>
        <p>Hook and pacing checklist beside what viewers actually did${d.stats_updated ? ` (numbers from ${esc(d.stats_updated)})` : ""}.
        The checklist is a guide, not a forecast — trust the real watch time.</p></div></div>
      <h2>Episodes</h2>
      ${eps || `<div class="card caught"><b>No episodes yet</b>Copy episodes/_example.json to start one: one research pass, one long-form, a Short per chapter.</div>`}
      <h2>Videos</h2><div class="rt-grid">${vids}</div></div>`;
  }

  document.addEventListener("click", async e => {
    const cut = e.target.closest("[data-rt-cut]");
    if (cut) {
      cut.disabled = true;
      try { const r = await post("/api/retention/tiktok", {id: cut.dataset.rtCut}); toast(`${r.reply} Checklist ${r.score}/10.`); pageRetention(); }
      catch (err) { toast(err.message); cut.disabled = false; }
    }
    const ep = e.target.closest("[data-rt-ep]");
    if (ep) {
      ep.disabled = true;
      try {
        const r = await post("/api/episode/build", {id: ep.dataset.rtEp});
        sheet(`<h2>Episode built</h2><pre class="rt-pre">${esc(r.log)}</pre><h3>Plan</h3><pre class="rt-pre">${esc(r.plan)}</pre>
          <div class="rt-actions"><button class="btn" data-close>Close</button></div>`);
        pageRetention();
      } catch (err) { toast(err.message); ep.disabled = false; }
    }
  });

  window.PAGES.retention = pageRetention;
  if (location.hash.slice(1) === "retention") route();
})();
