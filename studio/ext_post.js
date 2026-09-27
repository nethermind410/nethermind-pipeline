"use strict";
/* ext_post.js — the "Schedule" sheet: pick Best time / Post now / Pick a time, with a
   preview so you can double-check the video before it goes anywhere. Talks to
   /api/post/plan/<id> (studio_ext_post.py) for the per-platform best-time plan, and to
   /api/run for post_live (best), post_now, and post_at (a chosen ISO time) — all three
   need {confirm:true}, same as the old post_live did. Replaces the old scheduleSheet in
   app.js, which said the send time was "Buffer's next open slot" — no longer true. */

function nowLocalInputValue() {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}
function isoWithOffset(localValue) {
  const d = new Date(localValue);
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const abs = Math.abs(off);
  const pad = n => String(n).padStart(2, "0");
  return `${localValue}${localValue.length === 16 ? ":00" : ""}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}
function fmtChosen(localValue) {
  const d = new Date(localValue);
  return isNaN(d) ? "" : d.toLocaleString(undefined, {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"});
}

async function scheduleSheet(v) {
  const plan = await get("/api/post/plan/" + encodeURIComponent(v.id)).catch(() => null);
  const rows = plan ? plan.platforms : [];
  const preview = v.video
    ? `<video class="post-preview" src="${media(v.video)}" controls playsinline preload="metadata"></video>`
    : v.picture ? `<img class="post-preview" src="${media(v.picture)}" alt="">` : "";
  const bestRows = rows.map(p => `<div class="post-plat"><b>${esc(p.name)}</b> — ${esc(p.local)}
      <details class="why"><summary>Why?</summary><p class="fine">${esc(p.why)} <i>(${esc(p.confidence)})</i></p></details></div>`).join("")
    || `<p class="fine">This video isn't set up to post anywhere yet.</p>`;

  sheet(`<h3>Schedule "${esc(v.title)}"?</h3>
    ${preview}
    <div class="post-choices">
      <label class="opt on"><input type="radio" name="when" value="best" checked>
        <div><div class="t">Best time <b>(recommended)</b></div><div class="s">${bestRows}</div></div></label>
      <label class="opt"><input type="radio" name="when" value="now">
        <div><div class="t">Post now</div><div class="s">Goes live right away, on every platform above — nothing to double-check after.</div></div></label>
      <label class="opt"><input type="radio" name="when" value="pick">
        <div><div class="t">Pick a time</div><div class="s"><input type="datetime-local" id="pick-time" min="${nowLocalInputValue()}"></div></div></label>
    </div>
    <div class="row-end"><button class="btn" data-close>Cancel</button><button class="btn primary" id="go" ${rows.length ? "" : "disabled"}>Schedule for best times</button></div>`,
    (el, close) => {
      const go = $("#go", el), pick = $("#pick-time", el);
      const radios = () => [...el.querySelectorAll('input[name="when"]')];
      const selected = () => radios().find(r => r.checked)?.value || "best";
      const syncOn = () => el.querySelectorAll(".opt").forEach(o => o.classList.toggle("on", o.querySelector("input").checked));
      const refresh = () => {
        const s = selected();
        go.textContent = s === "now" ? "Post now" : s === "pick"
          ? (pick.value ? `Schedule for ${fmtChosen(pick.value)}` : "Pick a time")
          : "Schedule for best times";
        go.disabled = !rows.length || (s === "pick" && !pick.value);
      };
      radios().forEach(r => r.onchange = () => { syncOn(); refresh(); });
      pick.onfocus = () => { el.querySelector('input[name="when"][value="pick"]').checked = true; syncOn(); refresh(); };
      pick.oninput = refresh;
      refresh();
      go.focus();
      go.onclick = () => {
        const s = selected();
        close();
        if (s === "now") runJob("post_now", v.id, {confirm: true});
        else if (s === "pick") runJob("post_at", `${v.id}|${isoWithOffset(pick.value)}`, {confirm: true});
        else runJob("post_live", v.id, {confirm: true});
      };
    });
}
