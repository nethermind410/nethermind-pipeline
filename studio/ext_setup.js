"use strict";
/* First run, your channel's name on every screen, and the demo.
   - A fresh install (no channel settings yet) opens a calm, step-by-step setup over the app: name the channel, pick its
     lanes, choose a voice, connect the services one at a time (each key is saved to .env on this Mac and never shown
     again, then tested), and land on the brain.
   - Any channel that isn't the original one gets its own name where the app would say "Nethermind".
   - In the demo, a band across the top and a "Demo data" mark on every page and big number say so; Leave returns you. */
(() => {
  let S = null, step = 0, draft = {};
  const api = p => fetch(p).then(r => r.json());
  const say = (m, ok = true) => { const el = document.querySelector(".nx-note"); if (el) { el.textContent = m; el.className = "nx-note " + (ok ? "ok" : "bad"); } };

  /* ---------- your channel's name (not the original install's) ---------- */
  function brand() {
    if (!S || S.source === "legacy") return;
    const name = S.name, app = S.app_name;
    document.title = document.title.replace(/Nethermind/g, app);
    const b = document.querySelector("#brandcard .bc-text b"); if (b && b.textContent !== name) b.textContent = name;
    const h = document.querySelector(".home-link"); if (h && /NETHERMIND/.test(h.firstChild?.textContent || "")) h.firstChild.textContent = `← ${app.toUpperCase()} `;
    document.querySelectorAll('a[href*="claude.ai/artifact/"], a[href$="#nx-dashboard"]').forEach(a => {
      if (S.dashboard_url) a.href = S.dashboard_url; else a.closest(".row")?.remove(); });
    if (!S.jarvis) document.querySelectorAll(".row .t").forEach(t => { if (t.textContent === "Talk to Jarvis") t.closest(".row")?.remove(); });
    const main = document.getElementById("main");               // pages that still say the original name (the brain's title…)
    if (main && /nethermind/i.test(main.textContent)) {
      const w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
      for (let n; (n = w.nextNode());) if (/nethermind/i.test(n.nodeValue))
        n.nodeValue = n.nodeValue.replace(/NETHERMIND/g, app.toUpperCase()).replace(/Nethermind/gi, app);
    }
  }

  /* ---------- the demo ---------- */
  function demoBand() {
    document.body.classList.add("nx-demo");
    if (document.querySelector(".nx-band")) return;
    const band = document.createElement("div");
    band.className = "nx-band"; band.setAttribute("role", "status");
    band.innerHTML = `<b>Demo data</b><span>A sample channel. Every number, video and comment here is invented, and nothing can be posted.</span>
      <button class="nx-btn ghost" data-nx="leave">Leave the demo</button>`;
    document.body.prepend(band);
  }
  function markHeads() {
    if (!S?.demo) return;
    const heads = [...document.querySelectorAll(".page > .head, .page .head-row .head, .chan-head")];
    const h1 = document.querySelector("#main h1");                         // pages without a .head (the brain, a video)
    if (h1 && !heads.some(h => h.contains(h1))) heads.push(h1.parentElement);
    heads.forEach(h => { if (h && !h.querySelector(".nx-tag")) h.insertAdjacentHTML("beforeend", `<span class="nx-tag">Demo data</span>`); });
  }

  /* ---------- the setup wizard ---------- */
  const STEPS = ["Welcome", "Name", "Lanes", "Voice", "Connect", "Extras", "Done"];
  function shell(body, foot) {
    const dots = STEPS.slice(1, -1).map((s, i) => `<i class="${i + 1 < step ? "done" : i + 1 === step ? "on" : ""}" title="${s}"></i>`).join("");
    return `<div class="nx-card" role="dialog" aria-modal="true" aria-labelledby="nx-h">
      ${step && step < STEPS.length - 1 ? `<div class="nx-dots" aria-label="Step ${step} of ${STEPS.length - 2}">${dots}</div>` : ""}
      ${body}<p class="nx-note" aria-live="polite"></p><div class="nx-foot">${foot}</div></div>`;
  }
  const back = `<button class="nx-btn ghost" data-nx="back">Back</button>`;
  const field = (label, name, value = "", attrs = "") => `<label class="nx-f"><span>${label}</span><input name="${name}" value="${esc(value)}" ${attrs}></label>`;

  function view() {
    const c = S;
    if (step === 0) return shell(`<div class="nx-mark"></div><h1 id="nx-h">Welcome to ${esc(c.app_name)}</h1>
      <p class="nx-lead">Seven agents that find ideas, write, render, schedule and learn — for one faceless channel. Let's set yours up.
      It takes about five minutes, and you can change everything later.</p>`,
      `<button class="nx-btn ghost" data-nx="demo">Explore the demo first</button><button class="nx-btn primary" data-nx="next">Set up my channel</button>`);
    if (step === 1) return shell(`<h1 id="nx-h">Name your channel</h1><p class="nx-lead">This is how the agents refer to it in every script, caption and report.</p>
      ${field("Channel name", "name", draft.name ?? (c.source === "defaults" ? "" : c.name), 'maxlength="60" autofocus placeholder="e.g. Deep Current"')}
      ${field("Your first name (optional)", "owner", draft.owner ?? (c.owner === "you" ? "" : c.owner), 'maxlength="40" placeholder="So drafts can say whose notes they are"')}
      ${field("In one line, what it makes (optional)", "about", draft.about ?? "", 'maxlength="300" placeholder="Faceless, fact-checked Shorts on…"')}`,
      back + `<button class="nx-btn primary" data-nx="next">Continue</button>`);
    if (step === 2) {
      const on = new Set(draft.lanes ?? c.lanes);
      return shell(`<h1 id="nx-h">Pick your lanes</h1><p class="nx-lead">The topics your channel covers. Idea scouts score everything against these, and ideas outside them get flagged.</p>
        <div class="nx-chips">${c.lane_library.map(l => `<button class="nx-chip ${on.has(l.id) ? "on" : ""}" data-lane="${esc(l.id)}" aria-pressed="${on.has(l.id)}">${esc(l.label)}</button>`).join("")}</div>
        <details class="nx-more"${draft.custom?.label ? " open" : ""}><summary>Add a lane of your own</summary>
          ${field("Lane name", "cl_label", draft.custom?.label || "", 'maxlength="40" placeholder="e.g. Extreme weather"')}
          ${field("Words that mean it's this lane", "cl_words", draft.custom?.words || "", 'placeholder="storm hurricane tornado lightning"')}
          <label class="nx-check"><input type="checkbox" name="cl_copy" ${draft.custom?.copyright ? "checked" : ""}> Its characters or brands belong to someone (art must be original)</label>
        </details>`, back + `<button class="nx-btn primary" data-nx="next">Continue</button>`);
    }
    if (step === 3) return shell(`<h1 id="nx-h">Voice and identity</h1><p class="nx-lead">Narration is made on this Mac, free. Pick the voice your videos use.</p>
      <label class="nx-f"><span>Narration voice</span><select name="voice">${c.voices.map(v => `<option value="${v.id}" ${(draft.voice ?? c.narration_voice) === v.id ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></label>
      ${field("Channel hashtag", "hashtag", draft.hashtag ?? c.hashtag_raw, 'maxlength="30" placeholder="added to every description, e.g. deepcurrent"')}
      ${field("YouTube channel id (optional)", "yt", draft.yt ?? c.youtube_channel_id, 'maxlength="24" placeholder="UC… — YouTube Studio → Settings → Channel → Advanced"')}`,
      back + `<button class="nx-btn primary" data-nx="save-channel">Save and continue</button>`);
    if (step === 4) return shell(`<h1 id="nx-h">Connect your services</h1>
      <p class="nx-lead">Bring your own keys. Each one is saved only in a private file on this Mac, never shown again, and never sent anywhere
      but the service it belongs to. Everything is optional — skip what you don't use yet.</p>
      <div class="nx-svcs">${c.services.map(s => {
        const n = Object.values(s.set).filter(Boolean).length, all = n === s.keys.length;
        const claude = s.id === "writing" && c.tools.claude;
        return `<details class="nx-svc" data-svc="${s.id}"><summary><span class="nx-dot ${all || claude ? "ok" : n ? "part" : ""}"></span><b>${esc(s.label)}</b>
          <em>${claude && !all ? "Claude Code found" : all ? "Saved" : n ? `${n} of ${s.keys.length} saved` : "Not connected"}</em></summary>
          <p class="nx-why">${esc(s.why)}</p>
          ${s.keys.map(k => `<label class="nx-f"><span>${k}${s.set[k] ? " · saved" : ""}</span><input type="password" name="${k}" autocomplete="off" spellcheck="false"
            placeholder="${s.set[k] ? "Saved — paste a new one to replace it" : "Paste it here"}"></label>`).join("")}
          <div class="nx-row"><button class="nx-btn" data-nx="save-keys" data-svc="${s.id}">Save</button><button class="nx-btn ghost" data-nx="test" data-svc="${s.id}">Test connection</button></div>
        </details>`; }).join("")}</div>
      <p class="nx-fine">Rendering needs ffmpeg${c.tools.ffmpeg ? " — found." : " — not found yet: install it with Homebrew (brew install ffmpeg)."}</p>`,
      back + `<button class="nx-btn primary" data-nx="next">Continue</button>`);
    if (step === 5) return shell(`<h1 id="nx-h">Extras</h1><p class="nx-lead">Optional. Leave this off unless you already run a Jarvis voice assistant on this Mac.</p>
      <label class="nx-check"><input type="checkbox" name="jarvis" ${(draft.jarvis ?? c.jarvis) ? "checked" : ""}> Connect Jarvis (answers ⌘K questions)</label>
      ${field("Jarvis folder", "jarvis_dir", draft.jarvis_dir ?? c.jarvis_dir, 'placeholder="e.g. ~/Developer/jarvis"')}`,
      back + `<button class="nx-btn primary" data-nx="save-extras">Continue</button>`);
    return shell(`<div class="nx-mark"></div><h1 id="nx-h">${esc(S.name)} is ready</h1>
      <p class="nx-lead">This is your brain: seven agents, each glowing while it works. Start in Intelligence to scout your first idea, or Content → Make to draft one.
      Settings shows every connection, and fixes, in plain English.</p>`, `<button class="nx-btn primary" data-nx="finish">Open the brain</button>`);
  }

  let root = null;
  function paint() {
    if (!root) { root = document.createElement("div"); root.className = "nx-setup"; document.body.append(root); }
    root.innerHTML = view();
    (root.querySelector("[autofocus]") || root.querySelector(".nx-btn.primary"))?.focus();
  }
  const val = n => root.querySelector(`[name="${n}"]`);
  function collect() {
    if (step === 1) Object.assign(draft, {name: val("name").value.trim(), owner: val("owner").value.trim(), about: val("about").value.trim()});
    if (step === 2) { draft.lanes = [...root.querySelectorAll(".nx-chip.on")].map(b => b.dataset.lane);
      draft.custom = {label: val("cl_label").value.trim(), words: val("cl_words").value.trim(), copyright: val("cl_copy").checked}; }
    if (step === 3) Object.assign(draft, {voice: val("voice").value, hashtag: val("hashtag").value.trim(), yt: val("yt").value.trim()});
    if (step === 5) Object.assign(draft, {jarvis: val("jarvis").checked, jarvis_dir: val("jarvis_dir").value.trim()});
  }
  const channelBody = () => ({name: draft.name, owner: draft.owner, about: draft.about, lanes: draft.lanes ?? S.lanes,
    custom_lane: draft.custom, hashtag: draft.hashtag, youtube_channel_id: draft.yt, narration_voice: draft.voice,
    jarvis: {enabled: !!draft.jarvis, dir: draft.jarvis_dir || ""}});
  async function refresh() { S = await api("/api/setup"); }

  async function act(what, btn) {
    try {
      if (what === "next") {
        collect();
        if (step === 1 && !draft.name) return say("Give your channel a name first.", false);
        if (step === 2 && !draft.lanes.length && !draft.custom.label) return say("Pick at least one lane.", false);
        step++; return paint();
      }
      if (what === "back") { collect(); step = Math.max(0, step - 1); return paint(); }
      if (what === "save-channel" || what === "save-extras") {
        collect(); const r = await post("/api/setup/channel", channelBody()); await refresh(); draft.custom = {};
        step++; paint(); return say(r.reply);
      }
      if (what === "save-keys") {
        const box = btn.closest(".nx-svc"), inputs = [...box.querySelectorAll("input[type=password]")].filter(i => i.value.trim());
        if (!inputs.length) return say("Paste a key first.", false);
        for (const i of inputs) { await post("/api/setup/key", {name: i.name, value: i.value.trim()}); i.value = ""; }
        await refresh(); const open = btn.dataset.svc; paint();
        root.querySelector(`[data-svc="${open}"]`)?.setAttribute("open", "");
        return say(`Saved ${inputs.length} value${inputs.length > 1 ? "s" : ""}. Test the connection when you're ready.`);
      }
      if (what === "test") { say("Testing…"); const r = await post("/api/setup/test", {service: btn.dataset.svc}); return say(r.reply); }
      if (what === "finish") { say("Starting your agents…"); await post("/api/setup/finish", {}); return waitRestart(s => !s.needs_setup); }
      if (what === "demo" || what === "leave") {
        const r = await post(what === "demo" ? "/api/setup/demo" : "/api/setup/leave_demo", {});
        say(r.reply); toast?.(r.reply); return waitRestart(s => !!s.demo === (what === "demo"));
      }
    } catch (e) { say(e.message, false); }
  }
  async function waitRestart(ready) {       // the server restarts (fresh agents, or another data folder); reload once it's back
    await new Promise(r => setTimeout(r, 1200));
    for (let i = 0; i < 40; i++) {
      try { const s = await api("/api/setup"); if (ready(s)) { location.hash = "home"; return location.reload(); } } catch (e) { /* restarting */ }
      await new Promise(r => setTimeout(r, 500));
    }
    say("It's taking a while. Quit and reopen the app.", false);
  }

  document.addEventListener("click", e => {
    const chip = e.target.closest(".nx-chip");
    if (chip) { chip.classList.toggle("on"); chip.setAttribute("aria-pressed", chip.classList.contains("on")); return; }
    const b = e.target.closest("[data-nx]"); if (!b) return;
    e.preventDefault(); e.stopPropagation(); act(b.dataset.nx, b);
  }, true);
  document.addEventListener("keydown", e => {
    if (e.key === "Enter" && root && e.target.matches?.(".nx-setup input:not([type=checkbox])")) {
      e.preventDefault(); root.querySelector(".nx-foot .nx-btn.primary")?.click(); }
  });

  async function start() {
    try { await refresh(); } catch (e) { return; }
    brand();
    if (S.demo) { demoBand(); markHeads(); }
    if (S.needs_setup) paint();
    new MutationObserver(() => { brand(); markHeads(); }).observe(document.getElementById("main") || document.body, {childList: true, subtree: true});
    const bc = document.getElementById("brandcard"); if (bc) new MutationObserver(brand).observe(bc, {childList: true, subtree: true, characterData: true});
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
