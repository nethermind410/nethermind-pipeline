"use strict";
/* Settings: daily backups (what, where, when) and health alerts you tick off. */
(() => {
  const base = window.PAGES.settings;
  window.PAGES.settings = async (...a) => {
    await base(...a);
    let o; try { o = await get("/api/ops"); } catch { return; }
    const b = o.backup;
    const html = `<h2>Backups</h2><div class="card list">
      <div class="row"><div class="body"><div class="t">${b ? `Last backup ${esc(when(b.last))}` : "No backup yet"}</div>
        <div class="s">${b ? `${fmt(b.files)} files · ${(b.bytes / 1e6).toFixed(1)} MB · keeps the newest 14 in ${esc(o.folder.replace(/^\/Users\/[^/]+/, "~"))}` : "Nethermind backs up your scripts, packaging, ideas, learnings and numbers once a day while it's open. Videos aren't included — they can be re-made."}</div></div>
        <button class="btn small" id="op-back">Back up now</button>${b ? `<button class="btn small" id="op-show">Show in Finder</button>` : ""}</div></div>
      <h2>Alerts</h2><div class="card list">${o.alerts.length ? o.alerts.map(x => `<div class="row"><span class="dot ${x.kind === "fixed" ? "ok" : ""}"></span>
        <div class="body"><div class="t">${esc(x.name)} ${x.kind === "fixed" ? "is working again" : "stopped working"}</div><div class="s">${esc(when(x.at))}${x.detail ? " · " + esc(x.detail) : ""}</div></div>
        <label class="tick"><input type="checkbox" data-op-clear="${esc(x.id)}"> Done</label></div>`).join("")
        : `<div class="row"><div class="body"><div class="t">No alerts</div><div class="s">You'll get a Mac notification if a connection breaks, and again when it's fixed.</div></div></div>`}</div>`;
    main.querySelector(".page")?.insertAdjacentHTML("beforeend", html);
    $("#op-back").onclick = async e => { e.target.disabled = true; e.target.textContent = "Backing up…";
      try { toast((await post("/api/backup/run", {})).reply); route(); } catch (err) { toast(err.message); e.target.disabled = false; } };
    $("#op-show") && ($("#op-show").onclick = () => post("/api/backup/show", {}));
  };
  document.addEventListener("change", async e => {
    const c = e.target.closest("[data-op-clear]"); if (!c || !c.checked) return;
    try { await post("/api/alerts/clear", {id: c.dataset.opClear}); c.closest(".row").remove(); } catch (err) { toast(err.message); c.checked = false; }
  });
})();
