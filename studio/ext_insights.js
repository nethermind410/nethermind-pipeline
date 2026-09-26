"use strict";
/* Insights (#insights) — Best times from your own numbers · Watchlist of channels you follow.
   Also: "From your comments" on the Ideas page, and an Insights link in the Performance header.
   Uses app.js helpers ($, esc, get, post, fmt, toast, go, route, tick, main). Read-only: nothing is posted. */
(() => {
  let tab = "times", poll = null;
  const asOf = iso => { const d = new Date(iso); return isNaN(d) ? "never" : d.toLocaleString(undefined, {weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit"}); };
  const day = iso => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric"}); };
  const dur = s => s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const PCOL = {youtube: "sw-youtube", tiktok: "sw-tiktok", instagram: "sw-instagram"};

  /* ---------- Best times ---------- */
  function grid(p, t) {
    const max = Math.max(1, ...p.dots.map(d => d.views));
    const cell = (di, bi) => p.dots.filter(d => d.day === di && d.band === bi).map(d => {
      const r = 6 + Math.sqrt(d.views / max) * 12;
      return `<a class="in-dot ${d.comparable ? "" : "off"}" href="${esc(d.url || "#")}" target="_blank" rel="noopener" style="width:${r}px;height:${r}px"
        title="${esc(`${d.title}\nPosted ${d.local}\n${fmt(d.views)} views at ${d.age_days} days old (${d.source}, ${asOf(d.measured)})${d.comparable ? "" : "\nNot comparable: measured outside 2–7 days"}`)}"></a>`;
    }).join("");
    return `<div class="in-grid" role="table" aria-label="${esc(p.name)} posts by day and time">
      <span></span>${t.days.map(d => `<span class="in-dh">${d}</span>`).join("")}
      ${t.bands.map((b, bi) => `<span class="in-bh"><b>${b.name}</b><em>${b.hours}</em></span>${t.days.map((_, di) => `<span class="in-cell">${cell(di, bi)}</span>`).join("")}`).join("")}
    </div>`;
  }
  function platCard(p, t) {
    const rows = [...p.dots].sort((a, b) => b.views - a.views);
    return `<section class="card in-plat">
      <div class="in-ph"><i class="sw ${PCOL[p.key]}"></i><b>${esc(p.name)}</b>
        <span class="pill">${p.videos} posted · ${p.comparable} at a comparable age</span><span class="in-asof">as of ${esc(asOf(p.as_of))}</span></div>
      <p class="in-verdict ${p.verdict.call ? "call" : ""}">${esc(p.verdict.text)}</p>
      ${p.dots.length ? grid(p, t) : `<div class="caught"><b>Nothing posted to ${esc(p.name)} yet</b></div>`}
      <p class="fine">${esc(p.source)}. Filled dot = measured at 2–7 days old; hollow = measured outside that window, so not compared. Dot size = views.</p>
      ${rows.length ? `<details><summary>Every video (${rows.length})</summary><div class="table-wrap"><table class="in-tbl"><thead><tr><th>Video</th><th>Posted (${esc(t.tz)})</th><th>Views</th><th>Measured at</th></tr></thead><tbody>
        ${rows.map(d => `<tr class="${d.comparable ? "" : "off"}"><td><a href="${esc(d.url || "#")}" target="_blank" rel="noopener">${esc(d.title)}</a></td><td>${esc(d.local)}</td>
          <td><b>${fmt(d.views)}</b></td><td>${d.age_days} days old${d.comparable ? "" : " · not comparable"}</td></tr>`).join("")}</tbody></table></div></details>` : ""}
    </section>`;
  }
  async function timesBody() {
    const t = await get("/api/insights/times");
    return `<p class="in-lead">Each dot is one video: the day and time it went out (${esc(t.tz)}), sized by its real views when it was 2–7 days old.
        A pattern is only called once a platform has ${t.min_videos} videos measured that way.</p>
      <div class="in-plats">${t.platforms.map(p => platCard(p, t)).join("")}</div>
      <div class="card in-general"><span class="k">General guidance — not from your channel</span><p>${esc(t.general)}</p></div>`;
  }

  /* ---------- Watchlist ---------- */
  function chCard(c) {
    const head = `<div class="in-ch-top">${c.avatar ? `<img src="${esc(c.avatar)}" alt="" loading="lazy">` : `<span class="in-av"></span>`}
      <div><b>${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title || c.handle)}</a>` : esc(c.title || c.handle)}</b>
        <div class="in-sub">${esc(c.handle)}${c.note ? ` · ${esc(c.note)}` : ""}${c.subscribers != null ? ` · ${fmt(c.subscribers)} subscribers` : ""}</div></div>
      <button class="btn small in-rm" data-in-rm="${esc(c.handle)}" title="Stop following">Remove</button></div>`;
    if (c.status !== "ok") return `<section class="card in-ch">${head}<p class="in-miss">${
      c.status === "not found" ? "Not found on YouTube — this handle doesn't resolve. Check the spelling; nothing was guessed." :
      c.status === "error" ? `Couldn't check: ${esc(c.error || "unknown error")}` : "Not checked yet — press Check now."}</p></section>`;
    const med = c.median_by_kind || {};
    const meds = [`<span><b>${fmt(Math.round(c.median))}</b> median views, latest ${c.videos.length}</span>`,
      ...Object.entries(med).map(([k, v]) => `<span>${k === "short" ? "Shorts" : "Long"}: <b>${fmt(Math.round(v))}</b></span>`)].join("");
    const brk = c.breakouts.length ? `<div class="in-brk"><span class="k">Breakouts — idea fuel</span>${c.breakouts.map(v => `<a href="${esc(v.url)}" target="_blank" rel="noopener">
        <b>${v.x}×</b><span>${esc(v.title)}</span><em>${fmt(v.views)} views · ${esc(day(v.published))}</em></a>`).join("")}</div>`
      : `<p class="in-sub">No breakouts in the latest ${c.videos.length} — nothing at 3× its usual views.</p>`;
    return `<section class="card in-ch">${head}<div class="in-meds">${meds}</div>${brk}
      <details><summary>Latest uploads</summary><div class="table-wrap"><table class="in-tbl"><thead><tr><th>Title</th><th>Posted</th><th>Views</th><th>Length</th><th>vs usual</th></tr></thead><tbody>
      ${c.videos.map(v => `<tr><td><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a></td><td>${esc(day(v.published))}</td><td><b>${fmt(v.views)}</b></td>
        <td>${dur(v.seconds)} <span class="pill">${v.kind === "short" ? "Short" : "Long"}</span></td><td>${v.x == null ? "–" : `<span class="${v.x >= 3 ? "in-hot" : ""}">${v.x}×</span>`}</td></tr>`).join("")}
      </tbody></table></div></details></section>`;
  }
  async function watchBody() {
    const w = await get("/api/insights/watchlist");
    const ok = w.channels.filter(c => c.status === "ok"), found = ok.length, missing = w.channels.filter(c => c.status === "not found").length;
    const allBrk = ok.flatMap(c => c.breakouts.map(v => ({...v, ch: c.title || c.handle}))).sort((a, b) => b.x - a.x);
    if (w.run.running) startPoll(); else stopPoll();
    return `<div class="in-wbar"><div><b>${w.channels.length} channels</b><span class="in-sub"> · ${w.checked ? `as of ${esc(asOf(w.checked))}` : "never checked"}${
        missing ? ` · ${missing} not found` : ""}${w.run.error ? ` · last check failed: ${esc(w.run.error)}` : ""}</span></div>
      <form class="in-add" data-in-add><input name="h" placeholder="@handle" aria-label="YouTube handle to follow" autocomplete="off"><button class="btn small">Add</button></form>
      <button class="btn primary" data-in-check ${w.run.running ? "disabled" : ""}>${w.run.running ? "Checking…" : "Check now"}</button></div>
      <p class="fine">${esc(w.rule || "")}. Length ≤ 3 min is counted as a Short — YouTube's API has no Shorts flag. Read-only: this never posts anything.</p>
      ${allBrk.length ? `<h2>Breakouts across the watchlist</h2><div class="card in-brk in-brk-all">${allBrk.slice(0, 8).map(v => `<a href="${esc(v.url)}" target="_blank" rel="noopener">
        <b>${v.x}×</b><span>${esc(v.title)}</span><em>${esc(v.ch)} · ${fmt(v.views)} views · ${esc(day(v.published))}</em></a>`).join("")}</div>` : ""}
      <h2>Channels</h2><div class="in-chs">${w.channels.map(chCard).join("") || `<div class="caught"><b>No channels yet</b>Add a handle above.</div>`}</div>`;
  }
  function startPoll() { if (!poll) poll = setInterval(async () => {
    if (!location.hash.startsWith("#insights")) return stopPoll();
    const w = await get("/api/insights/watchlist").catch(() => null);
    if (w && !w.run.running) { stopPoll(); toast(w.run.error ? "Watchlist check failed." : "Watchlist checked."); page(); }
  }, 2000); }
  function stopPoll() { clearInterval(poll); poll = null; }

  /* ---------- page ---------- */
  async function page() {
    const [, sub] = location.hash.slice(1).split("/"); if (sub === "watchlist" || sub === "times") tab = sub;
    const body = tab === "watchlist" ? await watchBody() : await timesBody();
    main.innerHTML = `<div class="page in-page">
      <div class="head-row"><div class="head"><h1>Insights</h1><p>When your posts do best, and what the channels you watch are breaking out with. Every number is real and dated.</p></div>
        <button class="btn" data-go="performance">Performance</button></div>
      <div class="seg big" role="tablist">${[["times", "Best times"], ["watchlist", "Watchlist"]].map(([k, l]) =>
        `<button role="tab" aria-selected="${tab === k}" class="${tab === k ? "on" : ""}" data-in-tab="${k}">${l}</button>`).join("")}</div>
      ${body}</div>`;
    document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.go === "analytics"));
  }
  window.PAGES.insights = page;

  /* ---------- Performance header: a way in ---------- */
  const perf = window.PAGES.performance;
  window.PAGES.performance = async (...a) => { await perf(...a);
    const hr = main.querySelector(".head-row"); if (hr && !hr.querySelector("[data-go='insights']"))
      hr.insertAdjacentHTML("beforeend", `<button class="btn" data-go="insights" title="Best posting times and your channel watchlist">Insights</button>`); };

  /* ---------- Ideas: From your comments ---------- */
  let ci = null;
  function ciSection() {
    const ideas = ci.ideas.filter(i => !i.dismissed);
    const card = i => `<article class="idea card in-ci" data-key="${esc(i.key)}"><div class="idea-top"><span class="cat">From a comment</span>
        <button class="check" data-in-nope="${esc(i.key)}" title="Not useful — clear it" aria-label="Not useful — clear it"></button></div>
      <h3>${esc(i.hook)}</h3>
      <blockquote>“${esc(i.quote)}”</blockquote><span class="in-why">This comment ${esc(i.why.join(" · "))}</span>
      <p class="src">${esc(i.author)} on <a href="${esc(i.video_url)}" target="_blank" rel="noopener">${esc(i.video_title)}</a> · <a href="${esc(i.link)}" target="_blank" rel="noopener">see comment</a></p>
      <div class="idea-actions">${i.added ? `<span class="pill scheduled">In your ideas</span>` : `<button class="btn small primary" data-in-addidea="${esc(i.key)}">Add to ideas</button>`}
        <span class="in-sub">→ ${esc(i.section)}</span></div></article>`;
    return `<section class="in-ci-sec"><h2>From your comments</h2>
      ${ideas.length ? `<p class="fine">${ideas.length} of ${ci.checked} comments ${esc(ci.rule)}. Comments as of ${esc(asOf(ci.fetched))}.</p><div class="igrid">${ideas.map(card).join("")}</div>`
        : `<p class="fine">No idea-worthy comments yet — ${ci.checked} checked${ci.fetched ? ` (as of ${esc(asOf(ci.fetched))})` : ""}.</p>`}</section>`;
  }
  function injectCi() {
    if (!ci || !location.hash.startsWith("#ideas")) return;
    const pg = main.querySelector(".page"), grid = pg && pg.querySelector(":scope > .igrid");
    if (!grid || pg.querySelector(".in-ci-sec")) return;
    grid.insertAdjacentHTML("beforebegin", ciSection());
  }
  const ideasPage = window.PAGES.ideas;
  window.PAGES.ideas = async (...a) => { const p = get("/api/insights/comment_ideas").catch(() => null); await ideasPage(...a); ci = await p; injectCi(); };
  new MutationObserver(injectCi).observe(main, {childList: true});      // the search box re-renders Ideas without the router

  /* ---------- clicks ---------- */
  document.addEventListener("click", async e => {
    const t = e.target;
    const tb = t.closest("[data-in-tab]"); if (tb) { tab = tb.dataset.inTab; return go("insights/" + tab); }
    if (t.closest("[data-in-check]")) {
      try { const r = await post("/api/insights/watchlist/check", {}); toast(r.already ? "Already checking." : "Checking the watchlist — about a minute."); page(); } catch (err) { toast(err.message); }
      return;
    }
    const rm = t.closest("[data-in-rm]");
    if (rm) { if (!confirm(`Stop following ${rm.dataset.inRm}?`)) return;
      try { toast((await post("/api/insights/watchlist/remove", {handle: rm.dataset.inRm})).reply); page(); } catch (err) { toast(err.message); } return; }
    const add = t.closest("[data-in-addidea]");
    if (add) { const i = ci && ci.ideas.find(x => x.key === add.dataset.inAddidea); if (!i) return;
      try { await post("/api/idea", {section: i.section, hook: i.hook, format: i.format, source: i.link}); toast(`Added to ${i.section}.`); route(); } catch (err) { toast(err.message); } return; }
    const no = t.closest("[data-in-nope]");
    if (no) { try { await tick(no.dataset.inNope, no.closest(".in-ci"), "Cleared"); } catch (err) { toast(err.message); } }
  });
  document.addEventListener("submit", async e => {
    const f = e.target.closest("[data-in-add]"); if (!f) return; e.preventDefault();
    const h = f.h.value.trim(); if (!h) return f.h.focus();
    try { toast((await post("/api/insights/watchlist/add", {handle: h})).reply); page(); } catch (err) { toast(err.message); }
  });
})();
