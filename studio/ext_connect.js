"use strict";
/* Settings: Connections, as cards instead of a plain list, plus the Daily schedule switch.
   Keys save through /api/setup/key (never echoed back); Test uses /api/setup/test. Wraps
   window.PAGES.settings so the original page renders first, then this replaces the plain list. */
(() => {
  const base = window.PAGES.settings;
  window.PAGES.settings = async (...a) => {
    await base(...a);
    const page = main.querySelector(".page");
    if (!page) return;
    const openIds = [...page.querySelectorAll(".cx-card[open]")].map(d => d.dataset.cx);
    hidePlainList(page);
    await paintConnections(page, openIds);
    await paintSchedule(page);
  };

  function hidePlainList(page) {
    const h2 = [...page.querySelectorAll("h2")].find(h => h.textContent.trim() === "Connections");
    if (!h2) return;
    h2.classList.add("cx-hide");
    const list = h2.nextElementSibling;
    if (list && list.classList.contains("list")) list.classList.add("cx-hide");
  }

  function dot(ok) { return `<span class="cx-dot ${ok ? "ok" : ""}" aria-hidden="true"></span>`; }

  function svcCard(s) {
    if (s.id === "vidiq") return `<details class="cx-card" data-cx="vidiq"><summary>${dot(s.ok)}<b>${esc(s.label)}</b><em>optional</em></summary>
      <p class="cx-why">${esc(s.why)}</p><p class="cx-detail">${esc(s.detail)}</p>
      <a class="cx-link" href="${esc(s.link)}" target="_blank" rel="noopener">Get vidIQ ↗</a></details>`;
    if (s.id === "jarvis") return `<details class="cx-card" data-cx="jarvis"><summary>${dot(s.ok)}<b>${esc(s.label)}</b><em>optional · ${s.enabled ? "on" : "off"}</em></summary>
      <p class="cx-why">${esc(s.why)}</p>
      <label class="cx-check"><input type="checkbox" id="cx-jarvis-on" ${s.enabled ? "checked" : ""}> Connect Jarvis</label>
      <label class="cx-f"><span>Jarvis folder</span><input id="cx-jarvis-dir" value="${esc(s.dir)}" placeholder="e.g. ~/Developer/jarvis"></label>
      <div class="cx-row"><button class="cx-btn" data-cx-act="jarvis-save">Save</button></div>
      <p class="cx-note" data-cx-note></p></details>`;
    return `<details class="cx-card" data-cx="${s.id}"><summary>${dot(s.ok)}<b>${esc(s.label)}</b>${s.optional ? `<em>optional</em>` : ""}</summary>
      <p class="cx-why">${esc(s.why)}</p>
      ${s.link ? `<a class="cx-link" href="${esc(s.link)}" target="_blank" rel="noopener">Get a key ↗</a>` : ""}
      ${s.keys.map(k => `<label class="cx-f"><span>${esc(k)}${s.set[k] ? " · saved" : ""}</span>
        <input type="password" autocomplete="off" spellcheck="false" data-cx-key="${esc(k)}"
          placeholder="${s.set[k] ? "Saved — paste a new one to replace it" : "Paste it here"}"></label>`).join("")}
      <div class="cx-row"><button class="cx-btn" data-cx-act="save" data-svc="${s.id}">Save</button>
        <button class="cx-btn ghost" data-cx-act="test" data-svc="${s.id}">Test connection</button></div>
      <p class="cx-note" data-cx-note></p></details>`;
  }

  async function paintConnections(page, openIds) {
    let c; try { c = await get("/api/connect"); } catch { return; }
    page.querySelector(".cx-wrap")?.remove();
    const h2 = [...page.querySelectorAll("h2")].find(h => h.textContent.trim() === "Connections");
    const html = `<div class="cx-wrap"><h2>Connections</h2><div class="cx-grid">${c.services.map(svcCard).join("")}</div></div>`;
    (h2 || page.firstElementChild).insertAdjacentHTML("afterend", html);
    (openIds || []).forEach(id => page.querySelector(`.cx-card[data-cx="${id}"]`)?.setAttribute("open", ""));
  }

  async function paintSchedule(page) {
    let s; try { s = await get("/api/schedule"); } catch { return; }
    page.querySelector(".cx-sched")?.remove();
    const last = s.last ? ` · last ran ${esc(when(s.last.at))} · ${esc(s.last.status)}` : "";
    const html = `<div class="cx-sched"><h2>Daily schedule</h2><div class="card list">
      <div class="row"><div class="body"><div class="t">Make a video every day</div>
        <div class="s">${s.installed ? `Runs at ${esc(s.time)}, with a catch-up if it's missed${last}` : "Off — turn it on to have NETHER pick a topic and draft it every morning."}</div></div>
        <label class="cx-switch"><input type="checkbox" id="cx-sched-on" ${s.installed ? "checked" : ""} aria-label="Daily run"><span></span></label></div>
      <div class="row"><div class="body"><div class="t">Time</div><div class="s">A 90-minute catch-up runs automatically if the Mac was asleep, or the morning run failed.</div></div>
        <input type="time" id="cx-sched-time" value="${esc(s.time)}"><button class="cx-btn small" id="cx-sched-save">Save</button></div>
      <p class="cx-note" id="cx-sched-note"></p></div></div>`;
    const wrap = page.querySelector(".cx-wrap");
    if (wrap) wrap.insertAdjacentHTML("afterend", html); else page.insertAdjacentHTML("beforeend", html);
  }

  document.addEventListener("click", async e => {
    const sb = e.target.closest("#cx-sched-save");
    if (sb) {
      const on = $("#cx-sched-on").checked, time = $("#cx-sched-time").value || "07:00";
      const note = $("#cx-sched-note");
      try { await post("/api/schedule", {on, time}); note.textContent = on ? `Saved — runs at ${time}.` : "Turned off."; note.className = "cx-note ok"; toast(note.textContent); }
      catch (err) { note.textContent = err.message; note.className = "cx-note bad"; }
      return;
    }
    const b = e.target.closest("[data-cx-act]"); if (!b) return;
    const box = b.closest(".cx-card"), note = box.querySelector("[data-cx-note]");
    const say = (m, bad) => { if (note) { note.textContent = m; note.className = "cx-note " + (bad ? "bad" : "ok"); } };
    try {
      if (b.dataset.cxAct === "save") {
        const inputs = [...box.querySelectorAll("[data-cx-key]")].filter(i => i.value.trim());
        if (!inputs.length) return say("Paste a key first.", true);
        for (const i of inputs) { await post("/api/setup/key", {name: i.dataset.cxKey, value: i.value.trim()}); i.value = ""; }
        say(`Saved ${inputs.length} value${inputs.length > 1 ? "s" : ""}. Test the connection when you're ready.`);
        const page = main.querySelector(".page");
        if (page) await paintConnections(page, [...page.querySelectorAll(".cx-card[open]")].map(d => d.dataset.cx));
      } else if (b.dataset.cxAct === "test") {
        say("Testing…"); const r = await post("/api/setup/test", {service: b.dataset.svc}); say(r.reply);
      } else if (b.dataset.cxAct === "jarvis-save") {
        const enabled = box.querySelector("#cx-jarvis-on").checked, dir = box.querySelector("#cx-jarvis-dir").value.trim();
        await post("/api/connect/jarvis", {jarvis: {enabled, dir}});
        say("Saved.");
      }
    } catch (err) { say(err.message, true); }
  });
})();
