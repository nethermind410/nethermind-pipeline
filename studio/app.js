"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const V = Date.now();
const media = f => !f ? "" : /^(\/|https?:)/.test(f) ? f : `/media/${encodeURIComponent(f)}?v=${V}`;
const main = $("#main");
const get = p => fetch(p).then(r => r.json());
// the button you just pressed shows it's working until the server answers (so nothing ever feels ignored)
let pressed = null, pressedAt = 0;
document.addEventListener("pointerdown", e => { const b = e.target.closest && e.target.closest("button,.btn"); if (b) { pressed = b; pressedAt = Date.now(); } }, true);
async function post(p, body) {
  const b = Date.now() - pressedAt < 1500 ? pressed : null;
  b?.classList.add("busy");
  try {
    const r = await fetch(p, {method: "POST", headers: {"Content-Type": "application/json", "X-Studio": "1"}, body: JSON.stringify(body)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || j.reply || "Something went wrong.");
    return j;
  } finally { b?.classList.remove("busy"); }
}
const fmt = n => Number(n || 0).toLocaleString();
const PLAT = {youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram"};
const STAGES = [["making", "Making"], ["ready", "Ready for you"], ["scheduled", "Scheduled"], ["live", "Live"]];

/* ---------- small pieces ---------- */
function toast(msg, action) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = "toast"; t.setAttribute("role", "status");
  t.innerHTML = `<span>${esc(msg)}</span>`;
  if (action) {
    const b = document.createElement("button"); b.textContent = action.label;
    b.onclick = () => { t.remove(); action.run(); }; t.append(b);
  }
  document.body.append(t);
  setTimeout(() => t.remove(), action ? 8000 : 4000);
}
function sheet(html, onReady) {
  const s = document.createElement("div");
  s.className = "scrim"; s.innerHTML = `<div class="sheet" role="dialog" aria-modal="true">${html}</div>`;
  const close = () => { s.remove(); document.removeEventListener("keydown", key); };
  const key = e => { if (e.key === "Escape") close(); };
  s.addEventListener("click", e => { if (e.target === s || e.target.closest("[data-close]")) close(); });
  document.addEventListener("keydown", key);
  document.body.append(s);
  onReady && onReady($(".sheet", s), close);
  return close;
}
function copy(text, btn) {
  const done = () => { if (btn) { const o = btn.textContent; btn.textContent = "Copied"; setTimeout(() => btn.textContent = o, 1300); } };
  navigator.clipboard.writeText(text).then(done, () => toast("Couldn't copy. Select the text and press ⌘C."));
}
function progress(stage) {
  if (stage === "earlier") return `<span class="pill">Made earlier</span>`;
  const i = STAGES.findIndex(s => s[0] === stage);
  return `<div class="progress" aria-label="Stage: ${esc(stage)}"><span class="past">Idea</span>${
    STAGES.map((s, n) => `<span class="${n < i ? "past" : n === i ? "now" : ""}">${s[1]}</span>`).join("")}</div>`;
}
function pill(stage) {
  const label = {draft: "Script to approve", ready: "Ready for you", scheduled: "Scheduled", live: "Live", making: "Making", earlier: "Made earlier"}[stage];
  return `<span class="pill ${esc(stage)}">${label}</span>`;
}
function spark(series, w = 200, h = 36) {
  const pts = (series && series.length ? series : [0]).slice(-30);
  const max = Math.max(...pts, 1), step = pts.length > 1 ? w / (pts.length - 1) : w;
  const xy = pts.map((v, i) => [pts.length > 1 ? i * step : w, h - 4 - (v / max) * (h - 8)]);
  const line = xy.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const last = xy[xy.length - 1];
  const area = pts.length > 1 ? `<path class="area" d="${line} L${w},${h} L0,${h} Z"/>` : "";
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">${area}<path d="${line}"/><circle cx="${last[0]}" cy="${last[1]}" r="3"/></svg>`;
}
function when(iso) {
  const d = new Date(iso); if (isNaN(d)) return "";
  return d.toLocaleString(undefined, {weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit"});
}

/* ---------- ticking things off ---------- */
async function tick(key, row, label = "Marked done") {
  await post("/api/done", {key, done: true});
  if (row) { row.classList.add("leaving"); await new Promise(r => setTimeout(r, 250)); }
  toast(label, {label: "Undo", run: async () => { await post("/api/done", {key, done: false}); route(); }});
  route();
}

/* ---------- Today ---------- */
async function pageToday() {
  const t = await get("/api/today");
  const row = c => {
    const img = c.thumb ? `<img class="thumb" src="${media(c.thumb)}" alt="" data-open="${esc(c.video)}">` : `<div class="thumb ph"></div>`;
    let body = `<div class="t">${esc(c.title)}</div><div class="s">${esc(c.text)}</div>`;
    let actions = c.kind === "draft" ? `<button class="btn primary small" data-go="draft/${esc(c.video)}">Read &amp; approve</button>` :
                  c.kind === "missed" ? `<button class="btn primary small" data-go="control">Open Control</button>` :
                  c.kind === "intel" ? `<button class="btn primary small" data-go="brief">Give your call</button>` :
                  c.kind === "ready" ? `<button class="btn primary small" data-open="${esc(c.video)}">Review</button>` :
                  `<button class="btn small" data-open="${esc(c.video)}">Open</button>`;
    if (c.steps) {
      const helper = {tags: c.tags ? `<button class="btn small" data-copy="${esc(c.tags)}">Copy tags</button>` : "",
                      comment: c.comment ? `<button class="btn small" data-copy="${esc(c.comment)}">Copy comment</button>` : "",
                      check: c.watch ? `<a class="btn small" href="${esc(c.watch)}" target="_blank" rel="noopener">Watch</a>` : ""};
      body += `<ul class="steps">${c.steps.map(s => `<li class="${s.done ? "on" : ""}">
        <button class="check ${s.done ? "on" : ""}" data-step="${esc(s.key)}" aria-pressed="${s.done}" aria-label="Done: ${esc(s.label)}"></button>
        <span>${esc(s.label)}</span>${helper[s.key.split(":")[2]] || ""}</li>`).join("")}</ul>`;
      if (c.kind === "finish") actions = c.link ? `<a class="btn primary small" href="${esc(c.link)}" target="_blank" rel="noopener">Open YouTube Studio</a>` : "";
    }
    return `<div class="row" data-key="${esc(c.key)}"><button class="check" data-tick="${esc(c.key)}" aria-label="Mark done"></button>${img}
      <div class="body">${body}</div><div class="actions">${actions}</div></div>`;
  };
  const now = t.cards.filter(c => c.kind !== "queued"), wait = t.cards.filter(c => c.kind === "queued");
  const n = t.cards.length; window.nxDay?.reload();
  main.innerHTML = `<div class="page">
    <div class="head"><h1>Today</h1><p>${n ? "Everything waiting on you, in one list — each clears when it's done. Today's run (bottom-right) takes you through it in order." : "Nothing needs you."}</p></div>
    ${now.length ? `<h2>Do now</h2><div class="card list">${now.map(row).join("")}</div>` : ""}
    ${wait.length ? `<h2>Waiting to go out</h2><div class="card list">${wait.map(row).join("")}</div>` : ""}
    ${n ? "" : `<div class="card"><div class="caught"><b>You're all caught up</b>The next video is made at 7:00. Pick what it'll be in <button class="link" data-go="ideas">Ideas</button>.</div></div>`}
    ${t.next ? `<div class="card upnext"><div><span class="k">Up next to make</span><div class="t">${esc(t.next.hook)}</div></div><button class="btn small" data-go="ideas">Change</button></div>` : ""}
  </div>`;
}

/* ---------- Videos ---------- */
async function pageVideos() {
  const vs = await get("/api/videos");
  const tile = v => `<button class="tile" ${v.stage === "draft" ? `data-go="draft/${esc(v.id)}"` : `data-open="${esc(v.id)}"`}>
      ${v.picture ? `<img src="${media(v.picture)}" alt="" loading="lazy">` : `<div class="ph">No picture yet</div>`}
      <div class="t">${esc(v.title)}</div>${pill(v.stage)}</button>`;
  const group = (name, list, open = true) => list.length ? (open
    ? `<h2>${name}</h2><div class="grid">${list.map(tile).join("")}</div>`
    : `<details class="more"><summary>${name} (${list.length})</summary><div class="grid" style="margin-top:12px">${list.map(tile).join("")}</div></details>`) : "";
  const by = s => vs.filter(v => v.stage === s);
  main.innerHTML = `<div class="page"><div class="head"><h1>Videos</h1><p>Everything you've made, newest first.</p></div>
    ${group("Scripts to approve", by("draft"))}${group("Ready for you", by("ready"))}${group("Being made", by("making"))}${group("Scheduled", by("scheduled"))}
    ${group("Live", by("live"))}${group("Made earlier", by("earlier"), false)}</div>`;
}

/* ---------- One video (review) ---------- */
async function pageVideo(id) {
  const v = await get("/api/video/" + encodeURIComponent(id));
  const p = v.packaging || {};
  const field = (lab, val) => val ? `<div class="field"><div class="lab">${lab}<button class="btn small" data-copy="${esc(val)}">Copy</button></div><div class="val">${esc(val)}</div></div>` : "";
  let cta = "";
  if (v.stage === "ready") cta = `<button class="btn primary" data-act="schedule">Schedule…</button><button class="btn" data-act="changes">Needs changes…</button>`;
  else if (v.stage === "making") cta = `<button class="btn primary" data-act="build">Make video</button>`;
  else if (v.stage === "scheduled") cta = `<button class="btn danger" data-act="undo">Take back from queue</button>`;
  else if (v.youtube_url) cta = `<a class="btn primary" href="${esc(v.youtube_url)}" target="_blank" rel="noopener">Watch on YouTube</a>`;
  const sched = v.scheduled.length ? `<div class="card list">${v.scheduled.map(s => `<div class="row"><div class="body"><div class="t">${PLAT[s.platform] || esc(s.platform)}</div><div class="s">Goes out ${esc(when(s.dueAt))}</div></div></div>`).join("")}</div>` : "";
  const live = v.posts.length ? `<div class="card list">${v.posts.map(x => `<div class="row"><div class="body"><div class="t">${PLAT[x.platform] || esc(x.platform)}</div><div class="s">${fmt(x.views)} views · posted ${esc(when(x.sentAt))}</div></div>${x.url ? `<a class="btn small" href="${esc(x.url)}" target="_blank" rel="noopener">Open</a>` : ""}</div>`).join("")}</div>` : "";
  main.innerHTML = `<div class="page"><button class="back" data-go="videos">‹ Videos</button>
    <div class="review ${v.format === "landscape" ? "wide" : ""}">
      <div class="player">
        ${v.video ? `<video id="player" controls playsinline preload="metadata" src="${media(v.video)}"></video>
          ${v.tiktok ? `<div class="seg" role="tablist"><button class="on" data-src="${esc(v.video)}">YouTube · Instagram</button><button data-src="${esc(v.tiktok)}">TikTok</button></div>` : ""}`
          : v.picture ? `<div class="tile poster"><img src="${media(v.picture)}" alt=""><span>${v.stage === "live" || v.stage === "scheduled" ? "The video file isn't on this Mac — the picture is from YouTube or its artwork" : "Not rendered yet — press Make video"}</span></div>`
          : `<div class="tile"><div class="ph">${v.stage === "live" || v.stage === "scheduled" ? "The video file isn't on this Mac" : "Not made yet"}</div></div>`}
      </div>
      <div style="display:grid;gap:18px">
        <div class="head"><h1 style="font-size:24px">${esc(v.title)}</h1></div>
        ${progress(v.stage)}
        ${v.feedback ? `<div class="note"><b>Your change notes</b><div class="val" style="white-space:pre-wrap">${esc(v.feedback)}</div></div>` : ""}
        <div class="cta">${cta}</div>
        ${sched}${live}
        ${v.precheck && v.stage === "ready" ? precheckHtml(v) : ""}
        ${v.thumb ? `<div class="card"><img src="${media(v.thumb)}" alt="Thumbnail" style="width:100%;display:block"></div>` : ""}
        ${p.title ? `<div class="card">${field("Title", p.title)}${field("Description", p.youtube_description)}${field("YouTube tags", p.youtube_tags)}
          ${field("TikTok caption", p.tiktok_caption)}${field("Instagram caption", p.instagram_caption)}${field("Pinned comment", p.pinned_comment)}</div>` : ""}
        <details class="more"><summary>Script</summary><div class="card script" style="padding:14px 16px;margin-top:8px">${v.script.map(s => `<p>${esc(s)}</p>`).join("")}</div></details>
        ${v.qa ? `<details class="more"><summary>Quality check frames</summary><img class="qa" src="${media(v.qa)}" alt="Frames from across the video"></details>` : ""}
        <details class="more"><summary>More actions</summary><div class="cta" style="margin-top:8px">
          <button class="btn" data-act="build">Make again from scratch</button>
          <button class="btn" data-act="build_nofetch">Re-make with the same pictures</button>
          ${p.title ? `<button class="btn" data-act="post_dry">Preview what would post</button>` : ""}</div></details>
      </div></div></div>`;
  main.querySelectorAll(".seg button").forEach(b => b.onclick = () => {
    main.querySelectorAll(".seg button").forEach(x => x.classList.toggle("on", x === b));
    $("#player").src = media(b.dataset.src);
  });
}

function precheckHtml(v) {
  const pc = v.precheck;
  return `<div class="card precheck"><div class="pc-head"><b>Before you schedule: pick the title</b>
      <button class="btn small" data-act="score">Score with vidIQ</button></div>
    ${pc.titles.map(o => `<label class="opt ${o.current ? "on" : ""}"><input type="radio" name="title" ${o.current ? "checked" : ""} data-title="${esc(o.title)}">
      <div><div class="t">${esc(o.title)}</div>
        <div class="s">${o.score != null ? `<b class="score">vidIQ ${o.score}/100</b> ${esc(o.note || "")} · scored ${esc(new Date(o.scored).toLocaleDateString())} · ` : ""}Checklist ${o.passed}/${o.checks.length}:
        ${o.checks.map(c => `<span class="${c.ok ? "ok" : "no"}">${c.ok ? "✓" : "✗"} ${esc(c.label)}</span>`).join(" ")}</div></div></label>`).join("")}
    <p class="fine">${esc(pc.vidiq_note)} The checklist is a rule-based check, not a prediction.</p></div>`;
}
function scheduleSheet(v) {
  sheet(`<h3>Schedule "${esc(v.title)}"?</h3>
    <p>It goes to YouTube, Instagram and TikTok, each at your next open slot in Buffer. While it's still waiting, you can take it back.</p>
    <p>After it's live on YouTube, Today will remind you to add the tags and pinned comment.</p>
    <div class="row-end"><button class="btn" data-close>Cancel</button><button class="btn primary" id="go">Schedule</button></div>`,
    (el, close) => { $("#go", el).onclick = () => { close(); runJob("post_live", v.id, {confirm: true}); }; $("#go", el).focus(); });
}
function changesSheet(v) {
  sheet(`<h3>What should change?</h3><p>Be specific, e.g. "the second picture doesn't show a worm" or "hook is too slow". Tomorrow's 7:00 build will redo it, and the note teaches future builds.</p>
    <textarea id="note" aria-label="What should change"></textarea>
    <div class="row-end"><button class="btn" data-close>Cancel</button><button class="btn primary" id="save">Save note</button></div>`,
    (el, close) => {
      $("#note", el).focus();
      $("#save", el).onclick = async () => {
        const note = $("#note", el).value.trim(); if (!note) return $("#note", el).focus();
        try { await post("/api/feedback", {id: v.id, note}); close(); toast("Saved. It'll be redone at 7:00."); route(); }
        catch (e) { toast(e.message); }
      };
    });
}

/* ---------- Performance ---------- */
const PORDER = ["youtube", "tiktok", "instagram"];            // fixed order = fixed colour, never by rank
const pct = (a, b) => b ? Math.round(a / b * 100) : 0;
function byPlatform(posts) {
  const m = {youtube: 0, tiktok: 0, instagram: 0};
  posts.forEach(p => { if (p.platform in m) m[p.platform] += Number(p.views || 0); });
  return m;
}
/* Donut: one arc per platform, 2px surface gaps between arcs, total in the middle. */
function ring(parts, size = 132, label = "views") {
  const total = PORDER.reduce((a, k) => a + (parts[k] || 0), 0);
  const r = size / 2 - 9, C = 2 * Math.PI * r, gap = total && PORDER.filter(k => parts[k]).length > 1 ? 3 : 0;
  let off = 0;
  const arcs = total ? PORDER.filter(k => parts[k]).map(k => {
    const len = parts[k] / total * C, dash = Math.max(len - gap, 1.5);
    const a = `<circle class="arc arc-${k}" r="${r}" cx="${size / 2}" cy="${size / 2}" stroke-dasharray="${dash} ${C - dash}"
      stroke-dashoffset="${-off}" data-tip="${PLAT[k]}: ${fmt(parts[k])} views (${pct(parts[k], total)}%)"><title>${PLAT[k]} ${pct(parts[k], total)}%</title></circle>`;
    off += len; return a;
  }).join("") : "";
  return `<div class="ring" style="width:${size}px;height:${size}px">
    <svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${fmt(total)} ${label}: ${PORDER.map(k => `${PLAT[k]} ${pct(parts[k] || 0, total)}%`).join(", ")}">
      <circle class="track" r="${r}" cx="${size / 2}" cy="${size / 2}"/>${arcs}</svg>
    <div class="ring-mid"><b>${fmt(total)}</b><span>${total ? label : "no views yet"}</span></div></div>`;
}
function legend(parts) {
  const total = PORDER.reduce((a, k) => a + (parts[k] || 0), 0);
  return `<ul class="legend">${PORDER.map(k => `<li class="${parts[k] ? "" : "zero"}"><i class="sw sw-${k}"></i><span>${PLAT[k]}</span>
    <b>${pct(parts[k] || 0, total)}%</b><em>${fmt(parts[k] || 0)}</em></li>`).join("")}</ul>`;
}
let perfTab = "overview";
async function pagePerformance() {
  const p = await get("/api/performance");
  const all = {youtube: 0, tiktok: 0, instagram: 0};
  p.rows.forEach(r => { const b = byPlatform(r.posts); PORDER.forEach(k => all[k] += b[k]); });
  const tabs = [["overview", "Overview"], ...PORDER.map(k => [k, PLAT[k]])];
  const seg = `<div class="seg big" role="tablist">${tabs.map(([k, l]) => `<button role="tab" aria-selected="${perfTab === k}" class="${perfTab === k ? "on" : ""}" data-ptab="${k}">${k !== "overview" ? `<i class="sw sw-${k}"></i>` : ""}${l}</button>`).join("")}</div>`;
  let body = "";
  if (perfTab === "overview") {
    const cards = p.rows.map(r => { const b = byPlatform(r.posts); return `<button class="vcard card" data-open="${esc(r.id)}">
        ${ring(b, 112)}<div class="vc-text"><div class="t">${esc(r.title)}</div>${legend(b)}
        <div class="trend">${spark(r.series, 160, 26)}<span>${r.series.length > 1 ? "views over time" : "trend builds daily"}</span></div></div></button>`; }).join("");
    body = `<div class="card overall">${ring(all, 176, "total views")}<div><div class="k">Across every video</div>${legend(all)}
        ${p.insight ? `<p class="why"><b>What's working:</b> ${esc(p.insight)}</p>` : ""}</div></div>
      <h2>Each video</h2><div class="vgrid">${cards || `<div class="caught">No numbers yet. Tap Refresh.</div>`}</div>`;
  } else {
    const k = perfTab, rows = [];
    p.rows.forEach(r => r.posts.filter(x => x.platform === k).forEach(x => rows.push({...x, title: r.title, id: r.id})));
    rows.sort((a, b) => (b.views || 0) - (a.views || 0));
    const sum = f => rows.reduce((a, x) => a + Number(x[f] || 0), 0);
    const views = sum("views"), eng = sum("reactions") + sum("comments") + sum("shares") + sum("saves");
    const watch = rows.filter(x => x.averageTimeWatched != null);
    const max = Math.max(1, ...rows.map(x => x.views || 0));
    const tile = (label, val, sub = "") => `<div class="card stat"><span class="k">${label}</span><span class="v">${val}</span>${sub ? `<span class="k">${sub}</span>` : ""}</div>`;
    body = `<div class="stats">
        ${tile("Views", fmt(views), `${pct(views, PORDER.reduce((a, q) => a + all[q], 0))}% of all your views`)}
        ${tile("Videos posted", rows.length)}
        ${tile("Average per video", fmt(rows.length ? Math.round(views / rows.length) : 0))}
        ${tile("Engagement", views ? (eng / views * 100).toFixed(1) + "%" : "–", "likes, comments, shares, saves ÷ views")}
        ${watch.length ? tile("Average watch", (watch.reduce((a, x) => a + x.averageTimeWatched, 0) / watch.length).toFixed(1) + "s") : ""}
        ${tile("Best video", rows[0] ? fmt(rows[0].views) : "–", rows[0] ? esc(rows[0].title) : "")}</div>
      <div class="card table-wrap"><table><thead><tr><th>Video</th><th>Views</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Saves</th><th>Avg watch</th><th>Posted</th></tr></thead><tbody>
      ${rows.map(x => `<tr><td><button class="link" data-open="${esc(x.id)}">${esc(x.title)}</button></td>
        <td class="barcell"><i class="bar sw-${k}" style="width:${Math.max(2, (x.views || 0) / max * 100)}%"></i><b>${fmt(x.views)}</b></td>
        <td>${fmt(x.reactions)}</td><td>${fmt(x.comments)}</td><td>${x.shares == null ? "–" : fmt(x.shares)}</td><td>${x.saves == null ? "–" : fmt(x.saves)}</td>
        <td>${x.averageTimeWatched == null ? "–" : x.averageTimeWatched + "s"}</td><td>${esc(when(x.sentAt))}</td></tr>`).join("") || `<tr><td colspan="8">Nothing posted to ${PLAT[k]} yet.</td></tr>`}
      </tbody></table></div>`;
  }
  main.innerHTML = `<div class="page">
    <div class="head-row"><div class="head"><h1>Performance</h1><p>${esc(p.sources)} · YouTube ${p.youtube_updated ? esc(when(p.youtube_updated)) : "not fetched"} · Buffer ${p.updated ? esc(when(p.updated)) : "not fetched"}</p></div>
      <button class="btn" data-act-global="stats">Refresh</button></div>${seg}${body}</div>`;
}

/* ---------- Ideas ---------- */
let ideaFilter = "All", ideaQuery = "", showDismissed = false, ideaSort = "mixed";
const FORMATS = {fact: "Story", ice: "Iceberg", creature: "Creature", hero: "Marvel"};
async function pageIdeas() {
  const [d, dem] = await Promise.all([get("/api/ideas"), get("/api/demand")]);
  const maxMed = Math.max(1, ...Object.values(dem).map(x => x.median || 0));
  const strength = i => { const x = dem[i.slug]; return !x ? -1 : x.results < 5 ? x.median * 0.01 : x.median; };  // thin evidence sinks
  const cats = ["All", ...d.sections.map(s => s.name).filter(n => n !== "Made")];
  const q = ideaQuery.toLowerCase();
  const items = d.sections.flatMap(s => s.items.map(i => ({...i, cat: s.name, note: s.note})))
    .filter(i => (ideaFilter === "All" || i.cat === ideaFilter) && (!q || (i.hook + i.source).toLowerCase().includes(q)))
    .sort((a, b) => ideaSort === "list" ? 0 : (strength(b) - strength(a)));
  if (ideaSort === "mixed") {                    // strongest first within each category, then alternate categories
    const byCat = {}; items.forEach(i => (byCat[i.cat] ||= []).push(i));
    const queues = Object.values(byCat); items.length = 0;
    while (queues.some(q => q.length)) queues.forEach(q => q.length && items.push(q.shift()));
  }
  const live = items.filter(i => !i.dismissed && !i.made), gone = items.filter(i => i.dismissed && !i.made), made = items.filter(i => i.made);
  const card = i => `<article class="idea card ${i.dismissed ? "dim" : ""} ${d.next && d.next.slug === i.slug ? "pinned" : ""}">
      <div class="idea-top"><span class="cat">${esc(i.cat)}</span><span class="pill">${esc(FORMATS[i.format] || i.format)}</span>
        <button class="check ${i.dismissed ? "on" : ""}" data-dismiss="${esc(i.slug)}" aria-pressed="${i.dismissed}" title="${i.dismissed ? "Bring back" : "Not for us — clear it"}" aria-label="${i.dismissed ? "Bring back" : "Clear this idea"}"></button></div>
      <h3>${esc(i.hook)}</h3>
      <p class="src">Check facts at: ${esc(i.source)}</p>
      ${dem[i.slug] ? `<div class="demand" title="Median views of ${dem[i.slug].results} matching Shorts from the last year (YouTube search for “${esc(dem[i.slug].query)}”), checked ${esc(new Date(dem[i.slug].at).toLocaleDateString())}">
        <div class="dm-top"><span>Demand</span><b>${fmt(dem[i.slug].median)}</b><em>median views · ${dem[i.slug].results} similar Shorts</em>${dem[i.slug].results < 5 ? `<i class="weak" title="Too few matching Shorts to trust this number">weak evidence</i>` : ""}</div>
        <div class="dm-bar"><i style="width:${Math.max(2, Math.sqrt(dem[i.slug].median / maxMed) * 100)}%"></i></div>
        <details><summary>Proof from YouTube</summary>${dem[i.slug].top.map(v => `<a href="${esc(v.url)}" target="_blank" rel="noopener">${fmt(v.views)} · ${esc(v.title)}</a>`).join("")}</details></div>`
        : `<button class="link small" data-demand="${esc(i.slug)}">Check demand on YouTube</button>`}
      <div class="idea-actions">
        ${d.next && d.next.slug === i.slug ? `<span class="pill scheduled">Up next</span>` : `<button class="btn small primary" data-next="${esc(i.slug)}" data-hook="${esc(i.hook)}">Make this next</button>`}
        <button class="btn small" data-toseries="${esc(i.hook)}">+ Series</button>
        <button class="btn small" data-ask="${esc(`Is this a strong next Nethermind video, and what's the surprising true version? "${i.hook}" (${i.source})`)}">Ask Jarvis</button>
      </div></article>`;
  main.innerHTML = `<div class="page">
    <div class="head-row"><div class="head"><h1>Ideas</h1><p>Pick what gets made next. The 7:00 build uses your pick first.</p></div>
      <button class="btn primary" data-addidea>+ Add idea</button></div>
    ${d.next ? `<div class="card upnext"><div><span class="k">Up next</span><div class="t">${esc(d.next.hook)}</div>
        <div class="s">The next 7:00 build will make this.</div></div><button class="btn small" data-next="">Clear</button></div>` : ""}
    ${typeof ideasTabs === "function" ? ideasTabs("ideas") : ""}
    <div class="toolbar"><input id="iq" type="search" placeholder="Search ideas" value="${esc(ideaQuery)}" aria-label="Search ideas">
      <div class="chips">${cats.map(c => `<button class="chip ${c === ideaFilter ? "on" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`).join("")}
        <span class="chip-gap"></span><button class="chip ${ideaSort === "mixed" ? "on" : ""}" data-sort="mixed">Mixed</button>
        <button class="chip ${ideaSort === "demand" ? "on" : ""}" data-sort="demand">Most demand</button>
        <button class="chip ${ideaSort === "list" ? "on" : ""}" data-sort="list">Your order</button>
        <button class="chip" data-demand="">Check all on YouTube</button></div>
      <p class="fine">Demand = median views of similar Shorts from the last year, found by YouTube search. Open "Proof" to judge whether they really match.</p></div>
    <div class="igrid">${live.map(card).join("") || `<div class="caught"><b>No ideas match</b>Try another category, or add one.</div>`}</div>
    ${made.length ? `<details class="more"><summary>Made already (${made.length})</summary><div class="igrid" style="margin-top:10px">${made.map(i => `<article class="idea card done"><div class="idea-top"><span class="cat">Made</span><span class="check on" aria-hidden="true"></span></div><h3>${esc(i.hook)}</h3><p class="src">${esc(i.source)}</p></article>`).join("")}</div></details>` : ""}
    ${gone.length ? `<details class="more" ${showDismissed ? "open" : ""} id="gone"><summary>Cleared ideas (${gone.length})</summary><div class="igrid" style="margin-top:10px">${gone.map(card).join("")}</div></details>` : ""}
  </div>`;
  const iq = $("#iq");
  iq.oninput = () => { ideaQuery = iq.value; const pos = iq.selectionStart; pageIdeas().then(() => { const n = $("#iq"); n.focus(); n.setSelectionRange(pos, pos); }); };
  const g = $("#gone"); if (g) g.ontoggle = () => showDismissed = g.open;
  main.dataset.cats = JSON.stringify(d.sections.map(s => s.name).filter(n => n !== "Made"));
}
function addIdeaSheet() {
  const cats = JSON.parse(main.dataset.cats || "[]");
  sheet(`<h3>Add an idea</h3><p>One line: the surprising claim. The 7:00 build checks it before making anything.</p>
    <textarea id="ih" aria-label="The idea" placeholder="e.g. The octopus that guarded her eggs for 4½ years"></textarea>
    <div class="form-row"><label>Category<select id="ic">${cats.map(c => `<option>${esc(c)}</option>`).join("")}</select></label>
      <label>Format<select id="if">${Object.entries(FORMATS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label></div>
    <input id="is" placeholder="Where to check the facts (optional)" aria-label="Where to check the facts">
    <div class="row-end"><button class="btn" data-close>Cancel</button><button class="btn primary" id="iadd">Add</button></div>`,
    (el, close) => {
      $("#ih", el).focus();
      $("#iadd", el).onclick = async () => {
        try { await post("/api/idea", {hook: $("#ih", el).value, section: $("#ic", el).value, format: $("#if", el).value, source: $("#is", el).value});
          close(); toast("Idea added."); route(); } catch (e) { toast(e.message); }
      };
    });
}

/* ---------- Settings ---------- */
async function pageSettings() {
  const hs = await get("/api/health");
  main.innerHTML = `<div class="page"><div class="head"><h1>Settings</h1><p>Everything Nethermind depends on, at a glance.</p></div>
    <h2>Connections</h2><div class="card list">${hs.map(h => `<div class="row"><span class="dot ${h.ok ? "ok" : ""}" aria-label="${h.ok ? "Working" : "Needs attention"}"></span>
      <div class="body"><div class="t">${esc(h.name)}</div><div class="s">${esc(h.detail)}</div></div></div>`).join("")}</div>
    <h2>Handy</h2><div class="card list">
      <div class="row"><div class="body"><div class="t">Daily dashboard</div><div class="s">The same summary, on your phone or any browser.</div></div>
        <a class="btn small" href="https://claude.ai/artifact/H7zHPA7sX1urnaWbt9yR7B" target="_blank" rel="noopener">Open</a></div>
      <div class="row"><div class="body"><div class="t">Open Nethermind when you log in</div><div class="s">System Settings → General → Login Items → + → choose Nethermind in Applications.</div></div></div>
      <div class="row"><div class="body"><div class="t">Talk to Jarvis</div><div class="s">Press ⌘K here, or ⌘⇧J anywhere once Jarvis's voice client is running.</div></div></div>
    </div></div>`;
}

/* ---------- jobs ---------- */
let seenJob = 0, jobLiveOn = false;
async function runJob(action, id, extra = {}) {
  try { const r = await post("/api/run", {action, id, ...extra}); if (r.queued) toast(r.reply, {label: "See queue", run: showQueue}); }
  catch (e) { return toast(e.message); }
  watchJob();
}
/* the line of jobs: one runs at a time (renders need the whole Mac); the rest wait here and start by themselves */
async function showQueue() {
  const j = await get("/api/job");
  sheet(`<h3>Job queue</h3><div class="q-list">
    ${!j.done ? `<div class="q-row now"><span class="spin"></span><b>${esc(j.label)}</b><span class="s">running now</span><button class="cancel" data-cancel-job aria-label="Cancel">Cancel</button></div>` : ""}
    ${j.queue.map((q, i) => `<div class="q-row"><span class="q-n">${i + 1}</span><b>${esc(q.label)}</b>
      <button class="icon" data-q="up:${q.qid}" aria-label="Move up" ${i ? "" : "disabled"}>↑</button><button class="icon" data-q="down:${q.qid}" aria-label="Move down" ${i < j.queue.length - 1 ? "" : "disabled"}>↓</button>
      <button class="icon" data-q="remove:${q.qid}" aria-label="Remove">×</button></div>`).join("") || `<p class="s">Nothing waiting. Anything you start while a job runs lines up here and starts by itself.</p>`}</div>
    <div class="row-end">${j.queue.length > 1 ? `<button class="btn" data-q="clear:0">Clear queue</button>` : ""}<button class="btn" data-close>Close</button></div>`, (el, close) => {
    el.querySelectorAll("[data-q]").forEach(b => b.onclick = async () => {
      const [op, qid] = b.dataset.q.split(":");
      try { await post("/api/queue", {op, qid: +qid}); close(); if (op !== "clear") showQueue(); } catch (e) { toast(e.message); }
    });
    const cancelBtn = el.querySelector("[data-cancel-job]");
    if (cancelBtn) cancelBtn.onclick = async () => {
      try { await post("/api/cancel", {}); toast("Cancelling…"); } catch (e) { toast(e.message); }
    };
  });
}
function jobDone(j, a) {
  if (j.code !== 0) return toast(`Error: ${j.label} didn't finish.`, {label: "See why", run: () => window.showFailure ? showFailure({job: true}) : a.click()});
  if (j.action === "post_live") {
    const due = [...j.log.matchAll(/Posting to (\w+)[\s\S]*?due (\S+)/g)].map(m => `${PLAT[m[1]] || m[1]} ${when(m[2])}`);
    toast("Scheduled" + (due.length ? ": " + due.join(" · ") : "."), {label: "Undo", run: () => runJob("undo", j.video)});
  } else if (j.action === "undo") toast("Taken back out of the queue.");
  else if (j.action === "reschedule") toast("Moved.", lastMove ? {label: "Undo", run: () => { const m = lastMove; lastMove = null; runJob("reschedule", `${m.pid}|${m.back}`); }} : null);
  else if (j.action === "replies") toast("Drafts ready.");
  else if (j.action === "score") toast("Scored with vidIQ.");
  else if (j.action === "demand") toast("Demand checked on YouTube.");
  else if (j.action === "stats") toast("Numbers refreshed from YouTube and Buffer.");
  else if (j.action === "post_dry") a.click();
  else toast("Done: " + j.label);
}
/* Push, not poll: ext_live.js keeps one shared EventSource and dispatches nx-job/nx-queue
   window events (with a slow 15s fallback poll if the stream drops). We just react to them —
   the only thing polled here is the one-off fetch to render the current state immediately. */
function renderActivity(j) {
  const a = $("#activity"); if (!a) return;
  const n = j.queue ? j.queue.length : 0, more = n ? ` · <span class="q-badge">${n} queued</span>` : "";
  a.hidden = false; a.classList.toggle("busy", !j.done); a.classList.toggle("err", j.done && j.code !== 0);
  a.classList.toggle("interrupted", j.done && j.code === null && /interrupted/i.test(j.friendly || ""));
  const cancel = !j.done ? `<button class="cancel" data-cancel-pill aria-label="Cancel">Cancel</button>` : "";
  a.innerHTML = (j.done ? (j.code === 0 ? "✓ " + esc("Finished: " + j.label) : `<b>Error</b> · ${esc(j.label)} didn't finish — tap to see why`) + more
                        : `<span class="spin"></span>${esc(j.label)}…${more}`) + cancel;
  a.onclick = e => {
    if (e.target.closest("[data-cancel-pill]")) { post("/api/cancel", {}).then(() => toast("Cancelling…")).catch(err => toast(err.message)); return; }
    j.done && j.code !== 0 && window.showFailure ? showFailure({job: true}) : n || !j.done ? showQueue() : sheet(`<h3>${esc(j.label)}</h3>${j.friendly ? `<p>${esc(j.friendly)}</p>` : ""}<details class="more" ${j.friendly ? "" : "open"}><summary>Details</summary><pre>${esc(j.log.slice(-6000) || "…")}</pre></details><div class="row-end"><button class="btn" data-close>Close</button></div>`);
  };
  if (j.done && j.id !== seenJob) { seenJob = j.id; jobDone(j, a); route(); }
  else if (!j.done && seenJob && j.id > seenJob + 1) { seenJob = j.id - 1; route(); }   // a queued job started after one we didn't see finish
}
function watchJob() {
  const refresh = () => get("/api/job").then(renderActivity).catch(() => {});
  if (!jobLiveOn) {
    jobLiveOn = true;
    window.addEventListener("nx-job", e => { if (e.detail && e.detail.type !== "progress") refresh(); });
    window.addEventListener("nx-queue", refresh);
  }
  refresh();
}

/* ---------- ⌘K palette ---------- */
async function palette(prefill = "") {
  const vs = await get("/api/videos").catch(() => []);
  const cmds = [["Today", () => go("today")], ["Videos", () => go("videos")], ["Performance", () => go("performance")],
    ["Ideas", () => go("ideas")], ["Settings", () => go("settings")], ["Refresh numbers", () => runJob("stats", "")],
    ...vs.map(v => [v.title, () => go("video/" + v.id)])];
  sheet(`<input id="pq" placeholder="Ask Jarvis, or type to jump…" aria-label="Ask or jump" value="${esc(prefill)}"><div class="hits" id="hits"></div><div class="answer" id="ans" hidden></div>`,
    (el, close) => {
      el.classList.add("palette"); el.parentElement.style.paddingTop = "14vh";
      const q = $("#pq", el), hits = $("#hits", el), ans = $("#ans", el); let sel = 0, shown = [];
      const draw = () => {
        const t = q.value.trim().toLowerCase();
        shown = t ? cmds.filter(c => c[0].toLowerCase().includes(t)).slice(0, 7) : cmds.slice(0, 6);
        if (t) shown.push(["Ask Jarvis: " + q.value.trim(), () => ask(q.value.trim())]);
        sel = Math.min(sel, shown.length - 1);
        hits.innerHTML = shown.map((c, i) => `<button class="hit ${i === sel ? "on" : ""}" data-i="${i}">${esc(c[0])}</button>`).join("");
      };
      const ask = async text => {
        hits.innerHTML = ""; ans.hidden = false; ans.textContent = "Jarvis is thinking…";
        try { ans.textContent = (await post("/api/jarvis", {text})).reply; } catch (e) { ans.textContent = e.message; }
      };
      const pick = i => { const c = shown[i]; if (!c) return; if (c[0].startsWith("Ask Jarvis")) c[1](); else { close(); c[1](); } };
      q.oninput = () => { sel = 0; ans.hidden = true; draw(); };
      q.onkeydown = e => {
        if (e.key === "ArrowDown") { sel = Math.min(sel + 1, shown.length - 1); draw(); e.preventDefault(); }
        if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
        if (e.key === "Enter") pick(sel);
      };
      hits.onclick = e => { const b = e.target.closest(".hit"); if (b) pick(+b.dataset.i); };
      draw(); q.focus(); if (prefill) { sel = shown.length - 1; draw(); }
    });
}

/* ---------- routing ---------- */
window.PAGES = {today: pageToday, videos: pageVideos, performance: pagePerformance, ideas: pageIdeas, settings: pageSettings};
let current = null;
function go(r) { location.hash = r; }
async function route() {
  const r = location.hash.slice(1) || "home";
  const [name, id] = r.split("/");
  document.querySelectorAll(".nav,.brandcard").forEach(n => n.classList.toggle("on", n.dataset.go === (name === "video" ? "videos" : name)));
  if (name !== "home") document.body.classList.remove("on-brain");
  window.onRoute && window.onRoute(name);
  try {
    if (name === "video" && id) { current = await get("/api/video/" + encodeURIComponent(id)); await pageVideo(id); }
    else await (window.PAGES[name] || window.PAGES.home || pageToday)();
  } catch (e) { main.innerHTML = `<div class="page"><div class="caught"><b>Couldn't load this</b>${esc(e.message)}</div></div>`; }
  window.nxDay?.reload();                          // the Today count comes from Today's run, so it matches everywhere
}
window.addEventListener("hashchange", () => { route(); main.scrollTop = 0; });

document.addEventListener("click", async e => {
  const t = e.target;
  const nav = t.closest("[data-go]"); if (nav) return go(nav.dataset.go);
  const open = t.closest("[data-open]"); if (open) return go("video/" + open.dataset.open);
  const c = t.closest("[data-copy]"); if (c) return copy(c.dataset.copy, c);
  const tk = t.closest("[data-tick]"); if (tk) return tick(tk.dataset.tick, tk.closest(".row"));
  const st = t.closest("[data-step]");
  if (st) { const on = !st.classList.contains("on"); await post("/api/done", {key: st.dataset.step, done: on}); return route(); }
  const ask = t.closest("[data-ask]"); if (ask) return palette(ask.dataset.ask);
  const lk = t.closest("[data-look]");
  if (lk) { try { localStorage.setItem("brainLook", lk.dataset.look); } catch (err) {} toast("Brain look saved.", {label: "See it", run: () => { location.href = "/#home"; location.reload(); }}); return route(); }
  const so = t.closest("[data-sort]"); if (so) { ideaSort = so.dataset.sort; return route(); }
  const dq = t.closest("[data-demand]"); if (dq) return runJob("demand", dq.dataset.demand);
  const tt = t.closest("[data-title]");
  if (tt && current) { await post("/api/choose_title", {id: current.id, title: tt.dataset.title}); toast("Title chosen."); return route(); }
  const pt = t.closest("[data-ptab]"); if (pt) { perfTab = pt.dataset.ptab; return route(); }
  const cat = t.closest("[data-cat]"); if (cat) { ideaFilter = cat.dataset.cat; return route(); }
  if (t.closest("[data-addidea]")) return addIdeaSheet();
  const dm = t.closest("[data-dismiss]");
  if (dm) {
    const key = "idea:" + dm.dataset.dismiss, on = !dm.classList.contains("on");
    await post("/api/done", {key, done: on});
    if (on) { dm.closest(".idea").classList.add("leaving"); await new Promise(r => setTimeout(r, 220));
      toast("Idea cleared", {label: "Undo", run: async () => { await post("/api/done", {key, done: false}); route(); }}); }
    return route();
  }
  const nx = t.closest("[data-next]");
  if (nx) { await post("/api/next", {slug: nx.dataset.next, hook: nx.dataset.hook || ""});
    toast(nx.dataset.next ? "Up next. The 7:00 build will make it." : "Cleared. The 7:00 build will choose."); return route(); }
  const g = t.closest("[data-act-global]"); if (g) return runJob(g.dataset.actGlobal, "");
  const a = t.closest("[data-act]");
  if (a && current) {
    const act = a.dataset.act;
    if (act === "schedule") return scheduleSheet(current);
    if (act === "changes") return changesSheet(current);
    if (act === "undo") return sheet(`<h3>Take it back?</h3><p>Anything still waiting in Buffer is removed. Posts that are already live stay up.</p><div class="row-end"><button class="btn" data-close>Keep it</button><button class="btn primary" id="go">Take back</button></div>`,
      (el, close) => $("#go", el).onclick = () => { close(); runJob("undo", current.id); });
    return runJob(act, current.id);
  }
});
const tip = document.createElement("div"); tip.className = "tip"; tip.hidden = true; document.body.append(tip);
document.addEventListener("mousemove", e => {
  const a = e.target.closest && e.target.closest("[data-tip]");
  if (!a) { tip.hidden = true; return; }
  tip.textContent = a.dataset.tip; tip.hidden = false;
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + "px"; tip.style.top = (e.clientY + 14) + "px";
});
$("#open-palette").onclick = () => palette();
document.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); palette(); } });

window.addEventListener("load", route);
get("/api/job").then(j => { seenJob = j.done ? j.id : j.id - 1; }).finally(watchJob);   // always listen: a job can start elsewhere (cron, retry)
