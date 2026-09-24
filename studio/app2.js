"use strict";
/* Home (channel), Calendar, Comments and the live sidebar card. Uses helpers from app.js. */
const ago = iso => {
  const d = new Date(iso); if (isNaN(d)) return "never";
  const m = Math.round((Date.now() - d) / 60000);
  return m < 1 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
};
function goalRing(value, goal, size = 150) {
  const r = size / 2 - 10, C = 2 * Math.PI * r, frac = Math.min(1, value / goal), shown = Math.max(frac * C, value ? 3 : 0);
  return `<div class="ring" style="width:${size}px;height:${size}px"><svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${fmt(value)} of ${fmt(goal)}">
    <circle class="track" r="${r}" cx="${size / 2}" cy="${size / 2}"/>
    <circle class="goal-arc" r="${r}" cx="${size / 2}" cy="${size / 2}" stroke-dasharray="${shown} ${C - shown}" stroke-linecap="round"/></svg>
    <div class="ring-mid"><b>${frac < 0.001 && value ? "<0.1" : (frac * 100).toFixed(frac < 0.1 ? 1 : 0)}%</b><span>of ${fmt(goal)}</span></div></div>`;
}

/* ---------- sidebar channel card: live, useful, clickable ---------- */
async function brandCard() {
  const el = $("#brandcard"); if (!el) return;
  const [c, t] = await Promise.all([get("/api/channel").catch(() => ({})), get("/api/today").catch(() => ({cards: []}))]);
  if (!c.ready) { el.innerHTML = `<img src="/icon.png" alt=""><div><b>Nethermind</b><span>Tap to load your channel</span></div>`; return; }
  const subs = c.goals[0], n = t.cards.length;
  el.innerHTML = `<div class="bc-av"><img src="${esc(c.channel.avatar)}" alt="" onerror="this.src='/icon.png'">${n ? `<i class="pulse" title="${n} thing${n > 1 ? "s" : ""} need you"></i>` : ""}</div>
    <div class="bc-text"><b>${esc(c.channel.title)}</b><span>${fmt(subs.value)} subscribers · ${fmt(c.channel.views)} views</span>
    <div class="bc-bar" title="${fmt(subs.value)} of ${fmt(subs.goal)} subscribers for monetisation"><i style="width:${Math.max(1.5, subs.value / subs.goal * 100)}%"></i></div>
    <span class="bc-note">${(subs.value / subs.goal * 100).toFixed(1)}% to 1,000 · updated ${ago(c.fetched)}</span></div>`;
}
setInterval(brandCard, 5 * 60 * 1000);

/* ---------- Home: the channel at a glance (landing page) ---------- */
async function pageHome() {
  const [c, t, cal, ideas] = await Promise.all([get("/api/channel"), get("/api/today"), get("/api/calendar"), get("/api/ideas")]);
  if (!c.ready) {
    main.innerHTML = `<div class="page"><div class="caught"><b>No channel numbers yet</b>Pull them from YouTube once and they'll stay fresh.<br><br><button class="btn primary" data-act-global="stats">Get my numbers</button></div></div>`;
    return;
  }
  const next = cal.items.find(i => i.state === "scheduled");
  const goals = c.goals.map(g => `<div class="card goal">${goalRing(g.value, g.goal)}<div>
      <div class="k">${esc(g.label)}</div><div class="gv">${fmt(g.value)} <span>/ ${fmt(g.goal)}</span></div>
      <p>${g.per_day != null ? `${g.per_day >= 0 ? "+" : ""}${g.per_day.toFixed(1)} a day lately${g.eta ? ` · at this pace: ${g.eta === "10+ years" ? "10+ years" : new Date(g.eta).toLocaleDateString(undefined, {month: "short", year: "numeric"})}` : ""}` : "Pace shows once there are a few days of history."}</p>
      <p class="fine">${esc(g.note)}</p></div></div>`).join("");
  const w = c.weekly;
  main.innerHTML = `<div class="page">
    <div class="chan-head"><img src="${esc(c.channel.avatar)}" alt="" onerror="this.src='/icon.png'">
      <div><h1>${esc(c.channel.title)}</h1><p>${esc(c.channel.handle)} · numbers from YouTube, ${ago(c.fetched)}</p></div>
      <button class="btn" data-act-global="stats">Refresh</button></div>
    <div class="glance">
      <button class="card gl" data-go="today"><span class="k">Needs you</span><b>${t.cards.length || "Nothing"}</b><span>${t.cards.length ? "Open Today" : "You're all caught up"}</span></button>
      <button class="card gl" data-go="calendar"><span class="k">Next post</span><b>${next ? esc(new Date(next.at).toLocaleString(undefined, {weekday: "short", hour: "numeric", minute: "2-digit"})) : "—"}</b><span>${next ? `${PLAT[next.platform]} · ${esc(next.title)}` : "Nothing queued"}</span></button>
      <button class="card gl" data-go="ideas"><span class="k">Up next to make</span><b>${ideas.next ? "Picked" : "Auto"}</b><span>${ideas.next ? esc(ideas.next.hook) : "The 7:00 build chooses"}</span></button>
    </div>
    <h2>Monetisation goals</h2><div class="goals">${goals}</div>
    <div class="stats">
      <div class="card stat"><span class="k">Views on your videos</span><span class="v">${fmt(c.channel.views)}</span><span class="k">${c.channel.videos} videos on YouTube</span></div>
      <div class="card stat"><span class="k">Average per video</span><span class="v">${fmt(c.avg_views)}</span><span class="k">YouTube views</span></div>
      <div class="card stat"><span class="k">This week</span><span class="v">${w ? `${w.views >= 0 ? "+" : ""}${fmt(w.views)}` : "—"}</span><span class="k">${w ? `views · ${w.subscribers >= 0 ? "+" : ""}${w.subscribers} subscribers since ${esc(new Date(w.since).toLocaleDateString())}` : "Appears after a week of history"}</span></div>
    </div>
    <h2>Most watched on YouTube</h2>
    <div class="card list">${c.top.map(v => `<a class="row plain" href="${esc(v.url)}" target="_blank" rel="noopener">
      <img class="thumb" src="${esc(v.thumb)}" alt=""><div class="body"><div class="t">${esc(v.title)}</div>
      <div class="s">${fmt(v.likes)} likes · ${fmt(v.comments)} comments · ${esc(new Date(v.published).toLocaleDateString())}</div></div>
      <b class="num">${fmt(v.views)}</b></a>`).join("")}</div>
    <h2>Weekly digest</h2>
    <div class="card digest">${c.digest ? `<div class="k">${esc(c.digest.date)}</div><div class="md">${esc(c.digest.text)}</div>` : `<p class="s">Your first digest arrives Sunday at 6 pm: growth, the best video and why, and next week's plan.</p>`}</div>
  </div>`;
}

/* ---------- Calendar: sent + scheduled, drag a scheduled post to another day ---------- */
async function pageCalendar() {
  const cal = await get("/api/calendar");
  const start = new Date(); start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7) - 7);          // Monday of last week
  const days = [...Array(28)].map((_, i) => { const d = new Date(start); d.setDate(d.getDate() + i); return d; });
  const key = d => d.toLocaleDateString("en-CA");
  const today = key(new Date());
  const byDay = {}; cal.items.forEach(i => (byDay[key(new Date(i.at))] ||= []).push(i));
  const cell = d => {
    const k = key(d), past = k < today;
    return `<div class="day ${k === today ? "today" : ""} ${past ? "past" : ""}" data-day="${k}">
      <div class="dn">${d.toLocaleDateString(undefined, {weekday: "short"})} <b>${d.getDate()}</b></div>
      ${(byDay[k] || []).map(i => `<div class="post ${i.state}" ${i.state === "scheduled" ? `draggable="true" data-pid="${esc(i.post_id)}" data-at="${esc(i.at)}"` : ""}
        data-open="${esc(i.video)}" title="${esc(`${PLAT[i.platform]} · ${i.title} · ${new Date(i.at).toLocaleString()}${i.state === "scheduled" ? " · drag to move" : ""}`)}">
        <i class="sw sw-${esc(i.platform)}"></i><span>${esc(new Date(i.at).toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit"}))}</span>
        <em>${esc(i.title)}</em></div>`).join("")}</div>`;
  };
  main.innerHTML = `<div class="page wide">
    <div class="head-row"><div class="head"><h1>Calendar</h1><p>Posted and scheduled, from Buffer (${cal.updated ? "updated " + ago(cal.updated) : "not refreshed"}). Drag a scheduled post to another day to move it.</p></div>
      <div class="legend-inline">${["youtube", "tiktok", "instagram"].map(k => `<span><i class="sw sw-${k}"></i>${PLAT[k]}</span>`).join("")}<span><i class="sw ghost"></i>Scheduled</span></div></div>
    <div class="cal-head">${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => `<span>${d}</span>`).join("")}</div>
    <div class="cal">${days.map(cell).join("")}</div></div>`;
  main.querySelectorAll(".post[draggable]").forEach(p => p.addEventListener("dragstart", e => {
    e.dataTransfer.setData("text/plain", JSON.stringify({pid: p.dataset.pid, at: p.dataset.at})); p.classList.add("dragging");
  }));
  main.querySelectorAll(".day").forEach(d => {
    d.addEventListener("dragover", e => { if (!d.classList.contains("past") || d.dataset.day === today) { e.preventDefault(); d.classList.add("drop"); } });
    d.addEventListener("dragleave", () => d.classList.remove("drop"));
    d.addEventListener("drop", e => {
      e.preventDefault(); d.classList.remove("drop");
      const {pid, at} = JSON.parse(e.dataTransfer.getData("text/plain")); const old = new Date(at);
      const [y, m, dd] = d.dataset.day.split("-").map(Number); const nu = new Date(old); nu.setFullYear(y, m - 1, dd);
      if (nu <= new Date()) return toast("Pick a time in the future.");
      if (nu.getTime() === old.getTime()) return;
      sheet(`<h3>Move this post?</h3><p>From ${esc(old.toLocaleString())}<br>to <b>${esc(nu.toLocaleString())}</b> (same time of day).</p>
        <div class="row-end"><button class="btn" data-close>Cancel</button><button class="btn primary" id="mv">Move</button></div>`,
        (el, close) => $("#mv", el).onclick = () => { close(); lastMove = {pid, back: old.toISOString()}; runJob("reschedule", `${pid}|${nu.toISOString()}`); });
    });
  });
}
let lastMove = null;

/* ---------- Comments: real YouTube comments, drafts you copy ---------- */
async function pageComments() {
  const d = await get("/api/comments");
  const open = d.comments.filter(c => !c.done), done = d.comments.filter(c => c.done);
  const row = c => `<div class="row cm ${c.done ? "dim" : ""}" data-key="comment:${esc(slugify(c.id))}">
    <button class="check ${c.done ? "on" : ""}" data-cdone="${esc(slugify(c.id))}" aria-label="${c.done ? "Mark as not handled" : "Handled"}"></button>
    <div class="body"><div class="s">${esc(c.author)} · ${ago(c.at)} · on <b>${esc(c.video_title)}</b>${c.likes ? ` · ${c.likes} likes` : ""}${c.replies ? ` · ${c.replies} replies` : ""}</div>
      <div class="t cm-text">${esc(c.text)}</div>
      ${c.drafts.length ? `<div class="drafts">${c.drafts.map(r => `<div class="draft"><span>${esc(r)}</span><button class="btn small" data-copy="${esc(r)}">Copy</button></div>`).join("")}</div>` : ""}
      <div class="actions" style="margin-top:8px"><button class="btn small" data-draft="${esc(c.id)}">${c.drafts.length ? "New drafts" : "Draft replies"}</button>
        <a class="btn small" href="${esc(c.link)}" target="_blank" rel="noopener">Reply on YouTube</a></div></div></div>`;
  main.innerHTML = `<div class="page">
    <div class="head-row"><div class="head"><h1>Comments</h1><p>Public YouTube comments (${d.fetched ? "fetched " + ago(d.fetched) : "not fetched yet"}). Drafts are suggestions; you post the reply on YouTube.</p></div>
      <button class="btn" data-act-global="stats">Refresh</button></div>
    <div class="card list">${open.map(row).join("") || `<div class="caught"><b>No comments waiting</b>Tick a comment once you've replied, and it clears from here.</div>`}</div>
    ${done.length ? `<details class="more"><summary>Handled (${done.length})</summary><div class="card list" style="margin-top:8px">${done.map(row).join("")}</div></details>` : ""}
  </div>`;
}
const slugify = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 60);

Object.assign(window.PAGES, {home: pageHome, calendar: pageCalendar, comments: pageComments});
window.onRoute = () => { brandCard(); get("/api/comments").then(d => { const n = d.comments.filter(c => !c.done).length, b = $("#count-comments"); if (b) { b.hidden = !n; b.textContent = n; } }).catch(() => {}); };

document.addEventListener("click", async e => {
  const cd = e.target.closest("[data-cdone]");
  if (cd) {
    const key = "comment:" + cd.dataset.cdone, on = !cd.classList.contains("on");
    await post("/api/done", {key, done: on});
    if (on) toast("Marked handled", {label: "Undo", run: async () => { await post("/api/done", {key, done: false}); route(); }});
    return route();
  }
  const dr = e.target.closest("[data-draft]"); if (dr) return runJob("replies", dr.dataset.draft);
});
