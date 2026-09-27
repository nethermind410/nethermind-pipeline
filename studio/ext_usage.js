"use strict";
/* Control → AI engines: a plain-language "how much did this cost me" strip — today's and this week's
   Claude/paid-API usage by job — above the existing per-engine weekly spending table. Wraps
   window.PAGES.engines so the richer per-engine page renders first, then this adds its summary on top. */
(() => {
  const base = window.PAGES.engines;
  if (!base) return;   // ext_engines.js didn't load; nothing to attach to
  window.PAGES.engines = async (...a) => {
    await base(...a);
    const page = main.querySelector(".page");
    if (page) await paintUsage(page);
  };

  const JOB_NAME = {research: "researching", script: "drafting", episode: "drafting", packaging: "packaging",
                     replies: "replies", titles: "title scoring", other: "other jobs"};
  const name = j => JOB_NAME[j] || j;

  function fmtTokens(n) {
    if (!n) return "0";
    return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);
  }

  function line(bucket, label) {
    const t = bucket.total;
    if (!t.calls) return `${label} nothing yet — usage shows here after the next draft.`;
    const tok = t.in + t.out;
    const share = bucket.top_job && bucket.top_pct ? ` — ${name(bucket.top_job)} ${bucket.top_pct}%` : "";
    const cost = t.cost > 0 ? `, about $${t.cost.toFixed(2)} in paid API cost` : "";
    return `${label} used about <b>${esc(fmtTokens(tok))} tokens</b> across <b>${t.calls} call${t.calls === 1 ? "" : "s"}</b>${cost}${esc(share)}.`;
  }

  function bars(bucket) {
    const entries = Object.entries(bucket.jobs).sort((a, b) => b[1].calls - a[1].calls);
    if (!entries.length) return `<p class="us-empty">Nothing logged for this period yet.</p>`;
    const max = Math.max(...entries.map(([, b]) => b.calls));
    return `<div class="us-bars">${entries.map(([j, b]) => `<div class="us-bar-row">
        <b>${esc(name(j))}</b>
        <div class="us-bar-track"><div class="us-bar-fill" style="width:${Math.max(6, Math.round(100 * b.calls / max))}%"></div></div>
        <span>${b.calls} call${b.calls === 1 ? "" : "s"}${b.cost ? ` · $${b.cost.toFixed(2)}` : ""}</span></div>`).join("")}</div>`;
  }

  async function paintUsage(page) {
    let u;
    try { u = await get("/api/usage"); }
    catch { return; }   // quiet — the rest of the AI engines page still works without this strip
    page.querySelector(".us-wrap")?.remove();
    const html = `<div class="us-wrap"><div class="us-card">
      <div class="us-line">Today NETHER ${line(u.today, "")}</div>
      <button class="us-toggle" id="us-more">This week ▾</button>
      <div class="us-detail" id="us-week" hidden>
        <p class="us-line">This week ${line(u.week, "")}</p>
        ${bars(u.week)}
      </div></div></div>`;
    const anchor = page.querySelector(".vd") || page.querySelector(".head-row");
    if (anchor) anchor.insertAdjacentHTML("afterend", html);
    else page.insertAdjacentHTML("afterbegin", html);
    const btn = page.querySelector("#us-more"), detail = page.querySelector("#us-week");
    btn.onclick = () => { const open = !detail.hidden; detail.hidden = open; btn.textContent = open ? "This week ▾" : "This week ▴"; };
  }
})();
