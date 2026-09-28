"use strict";
/* Settings → Connections: a "YouTube — let NETHER finish videos for you" card (Connect / Connected as
   <channel> / Disconnect, plus an off-by-default "do this automatically" switch), and on Today's
   finish-a-video rows, a "Do these for me" button that runs the automations right there. Everything
   here only ever calls /api/ytfinish/*; it never touches app.js's own DOM structure directly beyond
   appending to it, the same way ext_connect.js layers its cards on. */
(() => {
  const baseSettings = window.PAGES.settings;
  window.PAGES.settings = async (...a) => { await baseSettings(...a); await paintSettingsCard(); };

  const baseToday = window.PAGES.today;
  window.PAGES.today = async (...a) => { await baseToday(...a); await paintTodayButtons(); };

  function card(html) { return `<div class="yf-card card">${html}</div>`; }

  function setupSteps() {
    return `<ol class="yf-steps">
      <li>Google Cloud Console → create a project (or use one you have) → enable the <b>YouTube Data API v3</b>.</li>
      <li>OAuth consent screen → type <b>External</b> → add yourself as a <b>test user</b>.</li>
      <li>Credentials → Create credentials → OAuth client ID → application type <b>Desktop app</b>.</li>
      <li>Download the JSON it gives you, and drop it at the path shown below.</li>
    </ol>`;
  }

  async function paintSettingsCard() {
    const page = $(".page");
    if (!page) return;
    page.querySelector(".yf-card")?.remove();
    let s;
    try { s = await get("/api/ytfinish/status"); }
    catch { return; }
    const body = s.connected
      ? `<p class="cx-detail">Connected as <b>${esc(s.channel || "your channel")}</b>.</p>
         <label class="cx-check"><input type="checkbox" id="yf-autorun" ${s.autorun ? "checked" : ""}>
           Do these automatically when a video goes live</label>
         <div class="cx-row"><button class="cx-btn ghost" id="yf-disconnect">Disconnect</button></div>`
      : s.needs_setup
      ? `<p class="cx-why">${esc(s.hint || "")}</p>${setupSteps()}
         <div class="cx-row"><button class="cx-btn" id="yf-retry">I've added it — check again</button></div>`
      : `<p class="cx-why">Sets tags, marks synthetic-media disclosure, posts (not pins) the pinned comment,
           and adds each video to its series playlist — automatically, once you sign in.</p>
         <div class="cx-row"><button class="cx-btn" id="yf-connect">Connect</button></div>`;
    const note = s.connecting ? `<p class="cx-note">Waiting on Google in your browser tab…</p>`
               : s.error ? `<p class="cx-note bad">${esc(s.error)}</p>` : "";
    const html = card(`<h2>YouTube — let NETHER finish videos for you</h2>${body}${note}`);
    const anchor = page.querySelector(".cx-sched") || page.querySelector(".cx-wrap") || page.firstElementChild;
    (anchor || page).insertAdjacentHTML(anchor ? "afterend" : "beforeend", html);

    page.querySelector("#yf-connect")?.addEventListener("click", async e => {
      try { const r = await post("/api/ytfinish/connect", {}); window.open(r.auth_url, "_blank", "noopener"); pollUntilConnected(); }
      catch (err) { toast(err.message); }
    });
    page.querySelector("#yf-retry")?.addEventListener("click", () => window.PAGES.settings());
    page.querySelector("#yf-disconnect")?.addEventListener("click", async () => {
      try { await post("/api/ytfinish/disconnect", {}); toast("Disconnected."); window.PAGES.settings(); }
      catch (err) { toast(err.message); }
    });
    page.querySelector("#yf-autorun")?.addEventListener("change", async e => {
      try { await post("/api/ytfinish/autorun", {on: e.target.checked}); toast(e.target.checked ? "Will finish videos automatically." : "Turned off."); }
      catch (err) { toast(err.message); e.target.checked = !e.target.checked; }
    });
  }

  function pollUntilConnected(tries = 0) {
    if (tries > 40) return;  // ~2 minutes
    setTimeout(async () => {
      let s; try { s = await get("/api/ytfinish/status"); } catch { return; }
      if (s.connected || s.error) return window.PAGES.settings();
      pollUntilConnected(tries + 1);
    }, 3000);
  }

  /* ---------- Today: "Do these for me" on each finish-a-video row ---------- */
  async function paintTodayButtons() {
    const rows = [...document.querySelectorAll('.row[data-key^="finish:"]')];
    if (!rows.length) return;
    let connected = false;
    try { connected = (await get("/api/ytfinish/status")).connected; } catch { /* leave button off */ }
    if (!connected) return;
    rows.forEach(row => {
      if (row.querySelector(".yf-run")) return;
      const vid = row.dataset.key.slice("finish:".length);
      const actions = row.querySelector(".actions");
      if (!actions) return;
      const btn = document.createElement("button");
      btn.className = "btn small yf-run"; btn.textContent = "Do these for me";
      btn.addEventListener("click", async () => {
        btn.classList.add("busy"); btn.disabled = true;
        try {
          const r = await post("/api/ytfinish/run", {video: vid});
          showRunResult(row, r);
        } catch (err) { toast(err.message); }
        finally { btn.classList.remove("busy"); btn.disabled = false; }
      });
      actions.prepend(btn);
    });
  }

  const STEP_LABEL = {tags: "Tags", disclosure: "Synthetic-media disclosure", comment: "Pinned comment", playlist: "Series playlist"};

  function showRunResult(row, r) {
    row.querySelector(".yf-result")?.remove();
    const lines = Object.entries(r.results || {}).map(([step, res]) => {
      const bad = res.action === "error";
      const extra = step === "comment" && r.comment_text ? ` <button class="btn small" data-copy="${esc(r.comment_text)}">Copy comment</button>` : "";
      return `<li class="${bad ? "yf-bad" : ""}">${esc(STEP_LABEL[step] || step)}: ${esc(res.action)}${res.detail ? " — " + esc(res.detail) : ""}${extra}</li>`;
    });
    row.insertAdjacentHTML("beforeend", `<ul class="yf-result">${lines.join("")}</ul>`);
    toast("Ran the YouTube automations — pinning the comment and the end screen are still yours to do.");
    setTimeout(() => route(), 400);   // pick up the tags/disclosure ticks the server just made
  }
})();
