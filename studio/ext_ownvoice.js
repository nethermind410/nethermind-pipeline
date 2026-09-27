"use strict";
/* Her own voiceover for the weekly long-form episode (Make page). Flow: approve the script → record
   the whole episode in one take → upload it here → NETHER splits it into per-line clips (word-count
   proportional; see studio_ext_ownvoice.py) → Render plays her voice back instead of Kokoro on every
   line that has one. Only decorates episode cards flagged "own_voice" by /api/drafts; everything else
   on the Make page (studio/ext_nether.js) is untouched. */
(() => {
  function panel(st) {
    const pct = st.lines ? Math.round(100 * st.recorded / st.lines) : 0;
    const state = st.complete ? "Ready to render" : st.recorded ? `${st.recorded}/${st.lines} lines (${pct}%)` : "Not recorded yet";
    return `<div class="card ov-panel">
      <div class="nx-head"><b>Your voiceover</b><span class="pill ${st.complete ? "live" : ""}">${esc(state)}</span></div>
      <p class="nx-meta">${st.complete
        ? "Every line has your voice. Render below to build the episode with it."
        : st.recorded
          ? "Word-count timing, not speech alignment — if a line's window sounds off, trim episodes/&lt;id&gt;.json's beat or re-upload."
          : "Record the whole script in order, start to finish (intro, chapters, outro), with no long pauses or retakes left in, then upload the file — m4a, wav or mp3."}</p>
      <div class="row-end">
        <label class="btn small">${st.uploaded ? "Replace recording" : "Upload recording"}<input type="file" accept="audio/*" class="ov-file" hidden></label>
        ${st.uploaded ? `<button class="btn small ov-clear">Remove</button>` : ""}
        <button class="btn primary small ov-render" ${st.recorded ? "" : "disabled"}>Render with my voice</button>
      </div>
      <p class="nx-meta ov-status" hidden></p>
    </div>`;
  }

  function readAsDataURL(file) {
    return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
  }

  async function decorate() {
    if (!["make", "content"].includes(location.hash.slice(1))) return;
    const host = main.querySelector(".page");
    if (!host) return;
    let d; try { d = await get("/api/drafts"); } catch { return; }
    const own = (d.episodes || []).filter(e => e.own_voice);
    host.querySelectorAll(".ov-panel").forEach(n => n.remove());
    for (const e of own) {
      const card = host.querySelector(`.nx-ep[data-nx-ep="${e.id}"]`);
      if (!card) continue;
      let st; try { st = await get(`/api/ownvoice/status/${e.id}`); } catch { continue; }
      card.insertAdjacentHTML("beforeend", panel(st));
      const p = card.querySelector(".ov-panel");
      const status = p.querySelector(".ov-status");
      const say = msg => { status.hidden = false; status.textContent = msg; };
      p.querySelector(".ov-file").onchange = async ev => {
        const file = ev.target.files[0];
        if (!file) return;
        say("Uploading and splitting into lines — this can take a minute for a long recording…");
        try {
          const data = await readAsDataURL(file);
          const r = await post("/api/ownvoice/upload", {episode: e.id, data, mime: file.type});
          say(r.reply);
          decorate();
        } catch (err) { say(err.message); }
      };
      const clearBtn = p.querySelector(".ov-clear");
      if (clearBtn) clearBtn.onclick = async () => {
        try { toast((await post("/api/ownvoice/clear", {episode: e.id})).reply); decorate(); } catch (err) { toast(err.message); }
      };
      p.querySelector(".ov-render").onclick = async () => {
        try { toast((await post("/api/ownvoice/render", {episode: e.id})).reply); decorate(); }
        catch (err) {
          if (/render anyway/i.test(err.message) && confirm(err.message)) {
            try { toast((await post("/api/ownvoice/render", {episode: e.id, confirm: true})).reply); decorate(); }
            catch (err2) { toast(err2.message); }
          } else toast(err.message);
        }
      };
    }
  }

  // window.PAGES.content is aliased to this same (wrapped) function once every extension has
  // registered its pages (see ext_nether.js's DOMContentLoaded handler) — wrapping PAGES.make here
  // is enough for both hashes; decorate() itself accepts either.
  const base = window.PAGES.make;
  if (base) window.PAGES.make = async (...a) => { await base(...a); await decorate(); };
  window.addEventListener("hashchange", () => { if (["make", "content"].includes(location.hash.slice(1))) setTimeout(decorate, 50); });
})();
