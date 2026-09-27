"use strict";
/* Her own photos/video per scene — studio_ext_scenes.py. Shows on two pages, both already rendered by
   the app before this file ever runs (see ext_nether.js for the draft page, app.js for the video page):

     #draft/<id>   the script review, before anything is built — a "Scenes" panel goes under the script
                   (works for a Short's draft AND a long-form episode's draft; both use pageDraft()).
     #video/<id>   an already-made Short or long-form episode — the same panel, so she can still swap
                   in her own footage and re-make the video with it (make/build_nofetch keeps her upload).

   Neither page has one call site to hook cleanly (pageDraft() and pageVideo() both replace the page's
   HTML wholesale), so — same trick as ext_gate.js — a MutationObserver on #main notices the render and
   appends the panel afterward. */
(() => {
  function readAsDataURL(file) {
    return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
  }

  const SOURCE_LABEL = {wikimedia: "Wikimedia photo", ai: "AI art", reused: "reused picture", none: "no picture yet"};

  function sceneLabel(s) {
    if (s.source === "own") return s.own_media_rights === "free" ? "your free-to-use upload" : "your own footage/photo";
    if (s.source === "reused" && s.type === "vid") return "video clip";
    return SOURCE_LABEL[s.source] || s.source;
  }

  function sceneRow(s) {
    const isVid = s.type === "vid";
    const thumb = s.thumb ? `<img src="${esc(s.thumb)}" alt="">` : `<div class="sc-ph">${isVid ? "\u{1F3AC}" : "\u{1F5BC}"}</div>`;
    const need = s.hint ? `<div class="sc-hint">Needs: ${esc(s.hint)}</div>` : "";
    const fact = s.fact ? `<div class="sc-fact">Fact: ${esc(s.fact)}</div>` : "";
    const start = s.source === "own" && isVid
      ? `<label class="sc-start">Start at <input type="number" min="0" step="0.5" value="${esc(s.ss || 0)}" class="sc-ss" data-sc-key="${esc(s.key)}"> s</label>` : "";
    return `<div class="sc-row" data-sc-key="${esc(s.key)}" data-sc-own="${s.source === "own" ? 1 : 0}">
      <div class="sc-thumb">${thumb}</div>
      <div class="sc-body">
        <div class="sc-line">${s.chapter ? `<span class="sc-chap">${esc(s.chapter)}</span>` : ""}${esc(s.text || "(no line — a title card or clip only)")}</div>
        <div class="sc-src">${esc(sceneLabel(s))}</div>
        ${need}${fact}${start}
      </div>
      <div class="sc-actions">
        <label class="btn small">${s.source === "own" ? "Replace" : "Use my own"}<input type="file" accept="image/jpeg,image/png,image/webp,image/heic,video/mp4,video/quicktime,video/x-m4v" hidden class="sc-file" data-sc-key="${esc(s.key)}"></label>
        ${s.source === "own" ? `<button type="button" class="btn small danger sc-remove" data-sc-key="${esc(s.key)}">Remove</button>` : ""}
      </div>
    </div>`;
  }

  function panelHtml(data) {
    return `<div class="card sc-panel">
      <div class="nx-head"><b>Scenes</b><span class="nx-meta">${data.scenes.length} scene${data.scenes.length === 1 ? "" : "s"} — drag a photo or video onto any scene, or use its button</span></div>
      <div class="sc-list">${data.scenes.map(sceneRow).join("")}</div>
    </div>`;
  }

  function wire(panel, vid) {
    async function send(file, key, inp) {
      const row = panel.querySelector(`.sc-row[data-sc-key="${CSS.escape(key)}"]`);
      let rights = null;
      if (row && row.dataset.scOwn !== "1") {
        rights = confirm("Is this your own photo/video? OK = yours. Cancel = free to use / stock.") ? "own" : "free";
      }
      try {
        row?.classList.add("sc-busy");
        const dataUrl = await readAsDataURL(file);
        const body = {id: vid, key, data: dataUrl, mime: file.type};
        if (rights) body.rights = rights;
        const r = await post("/api/scenes/upload", body);
        toast(r.reply);
        refreshPanel(panel.parentElement, vid);
      } catch (err) { toast(err.message); if (inp) inp.value = ""; }
      finally { row?.classList.remove("sc-busy"); }
    }
    panel.querySelectorAll(".sc-file").forEach(inp => {
      inp.onchange = ev => { const file = ev.target.files[0]; if (file) send(file, inp.dataset.scKey, inp); };
    });
    panel.querySelectorAll(".sc-row").forEach(row => {          // drag a photo or clip straight onto a scene
      row.addEventListener("dragover", e => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); row.classList.add("sc-drop"); } });
      row.addEventListener("dragleave", e => { if (!row.contains(e.relatedTarget)) row.classList.remove("sc-drop"); });
      row.addEventListener("drop", e => {
        e.preventDefault(); row.classList.remove("sc-drop");
        const file = e.dataTransfer.files[0];
        if (!file) return;
        if (!/^(image|video)\//.test(file.type)) return toast("That's not a photo or video.");
        send(file, row.dataset.scKey);
      });
    });
    panel.querySelectorAll(".sc-remove").forEach(btn => {
      btn.onclick = async () => {
        try { await post("/api/scenes/remove", {id: vid, key: btn.dataset.scKey}); toast("Removed — back to the original."); refreshPanel(panel.parentElement, vid); }
        catch (err) { toast(err.message); }
      };
    });
    panel.querySelectorAll(".sc-ss").forEach(inp => {
      const prev = inp.value;
      inp.onchange = async () => {
        try { await post("/api/scenes/start", {id: vid, key: inp.dataset.scKey, ss: Number(inp.value) || 0}); toast("Start time saved."); }
        catch (err) { toast(err.message); inp.value = prev; }
      };
    });
  }

  async function refreshPanel(host, vid) {
    if (!host) return;
    let data; try { data = await get(`/api/scenes/${encodeURIComponent(vid)}`); } catch { return; }
    const old = host.querySelector(".sc-panel");
    if (old) old.remove();
    host.insertAdjacentHTML("beforeend", panelHtml(data));
    wire(host.querySelector(".sc-panel"), vid);
  }

  async function decorateDraft() {
    const m = /^draft\/([a-z0-9_]+)/.exec((location.hash || "").slice(1));
    if (!m) return;
    const host = main.querySelector(".nx-review .card.nx-script");
    if (!host || host.querySelector(".sc-panel")) return;
    await refreshPanel(host, m[1]);
  }

  async function decorateVideo() {
    const m = /^video\/([a-z0-9_]+)/.exec((location.hash || "").slice(1));
    if (!m) return;
    const host = main.querySelector(".review > div:last-child");
    if (!host || host.querySelector(".sc-panel")) return;
    await refreshPanel(host, m[1]);
  }

  new MutationObserver(() => { decorateDraft(); decorateVideo(); }).observe(main, {childList: true});
  window.addEventListener("hashchange", () => setTimeout(() => { decorateDraft(); decorateVideo(); }, 30));
})();
