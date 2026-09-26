"use strict";
/* Control's repair desk: every failure explains itself (which department, what happened, what fixes it) and can be
   sent back to be fixed. Code repairs happen on their own branch; nothing changes until you tap Apply. */
(() => {
  const KIND = {retry: "Try again", wait: "Wait, or switch engine", login: "Sign in", settings: "Fix a setting", code: "Needs a code fix"};
  const STATE = {open: "Filed", working: "Claude is repairing…", ready: "Repair ready — review it", nofix: "Nothing to change in the code", applied: "Applied"};

  window.showFailure = async params => {
    let d;
    try { d = await post("/api/fix/diagnose", params); } catch (e) { return toast(e.message); }
    sheet(`<div class="fx-sheet"><div class="fx-dept"><span class="fx-dot"></span>Error · ${esc(d.department)}${d.desk ? ` → ${esc(d.desk)}` : ""}${d.where ? ` · step: ${esc(d.where)}` : ""}</div>
      <h3>${esc(d.title)} didn't finish</h3>
      <p class="fx-what">${esc(d.what)}</p>
      <div class="fx-fix"><span class="fx-kind">${esc(KIND[d.kind] || "")}</span>${esc(d.fix)}</div>
      ${d.error ? `<p class="fx-err">${esc(d.error)}</p>` : ""}
      <details class="more"><summary>Full log</summary><pre>${esc(d.log || "…")}</pre></details>
      <div class="row-end">
        ${d.kind === "wait" || d.kind === "settings" ? `<button class="btn" data-fx-go="${d.kind === "wait" ? "engines" : "settings"}">${d.kind === "wait" ? "AI engines" : "Settings"}</button>` : ""}
        ${d.can_retry ? `<button class="btn" data-fx-retry>Retry</button>` : ""}
        ${d.task ? `<button class="btn primary" data-fx-send>Send to fix</button>` : ""}
        <button class="btn" data-close>Close</button></div></div>`, (el, close) => {
      el.querySelector("[data-fx-go]")?.addEventListener("click", e => { close(); go(e.target.dataset.fxGo); });
      el.querySelector("[data-fx-retry]")?.addEventListener("click", () => { close(); window.nxRetry ? nxRetry({retry: d.retry}) : runJob(d.retry.action, d.retry.id || ""); });
      el.querySelector("[data-fx-send]")?.addEventListener("click", async () => {
        try {
          const r = await post("/api/fix/send", {task: d.task}); close();
          if (r.retry && window.nxRetry) { toast("Control says: " + r.reply, {label: "Retry now", run: () => nxRetry({retry: d.retry})}); }
          else toast(r.reply, r.ticket ? {label: "Open ticket", run: () => go("fixes")} : null);
        } catch (e) { toast(e.message); }
      });
    });
  };

  /* ---------- Fix tickets ---------- */
  let poll = null;
  async function pageFixes() {
    const list = await get("/api/fixes");
    main.innerHTML = `<div class="page">
      <div class="head"><h1>Fix tickets</h1><p>Failures you sent back to Control. Claude repairs code on a separate branch — you see exactly what changed and nothing is applied until you say so.</p></div>
      ${list.length ? list.map(t => `<div class="card fx-ticket ${t.state}">
        <div class="fx-row"><b>#${t.n} · ${esc(t.title)}</b><span class="pill">${esc(t.department)}</span><span class="fx-state">${esc(STATE[t.state] || t.state)}</span></div>
        <p class="fx-err">${esc(t.error || "")}</p>
        ${t.summary ? `<p class="fx-what">${esc(t.summary)}</p>` : ""}
        <div class="row-end">
          ${t.state === "open" ? `<button class="btn primary" data-fx-start="${t.n}">Let Claude fix it</button>` : ""}
          ${t.state === "ready" ? `<button class="btn" data-fx-diff="${t.n}">See the change</button><button class="btn primary" data-fx-apply="${t.n}">Apply</button>` : ""}
          ${t.state === "working" ? `<span class="spin"></span>` : ""}
          ${t.state !== "working" ? `<label class="tick"><input type="checkbox" data-fx-clear="${t.n}"> ${t.state === "applied" ? "Done" : "Clear"}</label>` : ""}</div></div>`).join("")
        : `<div class="card caught"><b>No open tickets</b>When a task fails, tap Why? · Fix in the Task log and choose Send to fix.</div>`}
      <div class="row-end"><button class="btn" data-go="agents">Task log</button></div></div>`;
    window._fx = list;
    clearInterval(poll);
    if (list.some(t => t.state === "working")) poll = setInterval(() => location.hash === "#fixes" ? route() : clearInterval(poll), 5000);
  }
  window.PAGES.fixes = pageFixes;

  document.addEventListener("click", async e => {
    const t = e.target;
    const why = t.closest("[data-fx-why]"); if (why) { e.stopPropagation(); return showFailure({task: +why.dataset.fxWhy}); }
    const st = t.closest("[data-fx-start]");
    if (st) { e.stopPropagation();
      if (!confirm("Let Claude repair this on a separate branch? It reads the code and the error, makes the smallest fix it can, and waits for you to Apply. It never posts anything.")) return;
      try { toast((await post("/api/fix/start", {n: +st.dataset.fxStart})).reply); route(); } catch (err) { toast(err.message); } return; }
    const df = t.closest("[data-fx-diff]");
    if (df) { const x = (window._fx || []).find(y => y.n === +df.dataset.fxDiff); if (x) sheet(`<h3>Repair #${x.n}</h3><p>${esc(x.summary || "")}</p><pre class="fx-diff">${esc(x.diff || "")}</pre><div class="row-end"><button class="btn" data-close>Close</button></div>`); return; }
    const ap = t.closest("[data-fx-apply]");
    if (ap) { e.stopPropagation();
      try { const r = await post("/api/fix/apply", {n: +ap.dataset.fxApply}); toast(r.reply, r.retry && window.nxRetry ? {label: "Retry", run: () => nxRetry({retry: r.retry})} : null); route(); }
      catch (err) { toast(err.message); } return; }
  }, true);
  document.addEventListener("change", async e => {
    const c = e.target.closest("[data-fx-clear]"); if (!c || !c.checked) return;
    try { await post("/api/fix/discard", {n: +c.dataset.fxClear}); c.closest(".fx-ticket").remove(); } catch (err) { toast(err.message); c.checked = false; }
  });
})();
