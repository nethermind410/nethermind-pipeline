"use strict";
/* Shared loading / empty / error states — one small helper every page and widget can lean on
   instead of going blank or showing a raw error. Respects prefers-reduced-motion (see ext_states.css).

     window.nxState.loading(el, label, kind)      // kind: "rows" (default) or "cards"
     window.nxState.empty(el, {title, hint, action:{label, run}})
     window.nxState.error(el, {message, retry})    // message must already be plain words — never JSON/a stack

   Nothing here calls fetch itself; app.js's `get()` throws a friendly Error on any failure, and callers
   pass e.message straight into error(). This file only draws the state. */
(() => {
  const plain = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

  function loading(el, label = "Loading", kind = "rows") {
    if (!el) return;
    el.innerHTML = kind === "cards"
      ? `<div class="nx-skel" role="status" aria-live="polite" aria-label="${plain(label)}…"><div class="nx-skel-grid">${
          Array.from({length: 4}, () => `<div class="nx-sk-card"></div>`).join("")}</div></div>`
      : `<div class="nx-skel" role="status" aria-live="polite" aria-label="${plain(label)}…">${
          ["w1", "w2", "w3", "w2"].map(w => `<div class="nx-sk-row ${w}"></div>`).join("")}</div>`;
  }

  function empty(el, {title = "Nothing here yet", hint = "", action = null} = {}) {
    if (!el) return;
    el.innerHTML = `<div class="nx-state nx-empty"><b>${plain(title)}</b>${hint ? `<p>${plain(hint)}</p>` : ""}${
      action ? `<button class="btn primary" type="button">${plain(action.label)}</button>` : ""}</div>`;
    if (action) el.querySelector(".nx-state button").onclick = action.run;
  }

  // message is shown as-is (plain words expected) — never pass e.stack, JSON, or a raw server body here.
  function error(el, {message = "Something went wrong. Try again.", retry = null} = {}) {
    if (!el) return;
    el.innerHTML = `<div class="nx-state nx-error"><b>Couldn't load this</b><p>${plain(message)}</p>${
      retry ? `<button class="btn" type="button">Retry</button>` : ""}</div>`;
    if (retry) el.querySelector(".nx-state button").onclick = retry;
  }

  window.nxState = {loading, empty, error};
})();
