"use strict";
/* ext_gate.js — "Ready to post?" quality checklist (quality_gate.py via studio_ext_gate.py's
   GET /api/gate/<id>). Two places it shows up:

     1. The video page — a read-only card so nothing is a surprise before you even open Schedule.
        pageVideo() (app.js) replaces main.innerHTML wholesale on every render, so there's no
        single call site to patch in cleanly — a MutationObserver on #main notices the render
        and appends the card after .cta, same trick ext_verdict-style pages use.

     2. The Schedule sheet (ext_post.js) — the actual gate. We wrap window.scheduleSheet (a
        plain global function, same pattern as the window.onRoute chaining already used all
        over this app) to inject the card and disable #go while a block-level check fails,
        and we wrap window.runJob so a confirmed "Post anyway" reason rides along on the next
        post_live/post_now/post_at call without ext_post.js needing to know this file exists.
*/

const gateCache = new Map();
const pendingOverride = new Map();   // video id -> reason, cleared once that post actually runs

async function gateFor(id, fresh) {
  if (!fresh && gateCache.has(id)) return gateCache.get(id);
  const g = await get("/api/gate/" + encodeURIComponent(id)).catch(() => null);
  if (g) gateCache.set(id, g); else gateCache.delete(id);
  return g;
}

function gateRow(c) {
  const cls = c.ok ? "ok" : c.level === "block" ? "block" : "warn";
  const icon = c.ok ? "✓" : c.level === "block" ? "✕" : "!";
  return `<div class="gate-row ${cls}"><span class="gate-icon">${icon}</span>
    <div class="gate-body"><div class="gate-name">${esc(c.name)}</div><div class="gate-detail">${esc(c.detail)}</div>
    ${!c.ok && c.fix ? `<div class="gate-fix">${esc(c.fix)}</div>` : ""}</div></div>`;
}

function gateStatus(g) {
  const blocked = g.checks.some(c => !c.ok && c.level === "block");
  return blocked ? "block" : g.pass ? "pass" : "warn";
}

function gateCardHtml(g, id, withOverride) {
  const status = gateStatus(g);
  const headline = status === "block" ? "Not ready — fix these first" : status === "warn" ? "Ready, with warnings" : "Ready to post";
  return `<div class="card gate gate-${status}" data-gate-card data-id="${esc(id)}">
    <div class="gate-head"><b>Ready to post?</b><span class="pill gate-pill-${status}">${esc(headline)} · ${g.score}/100</span></div>
    <div class="gate-rows">${g.checks.map(gateRow).join("")}</div>
    ${withOverride && status === "block" ? gateOverrideHtml() : ""}
  </div>`;
}

function gateOverrideHtml() {
  return `<div class="gate-override">
    <button type="button" class="btn small danger" data-gate-toggle>Post anyway…</button>
    <div class="gate-reason" hidden>
      <textarea placeholder="Why are you posting this even though the gate is blocking it? (recorded)" rows="2"></textarea>
      <button type="button" class="btn small" data-gate-confirm>Confirm override</button>
    </div>
  </div>`;
}

function wireOverride(root, id, go) {
  const toggle = root.querySelector("[data-gate-toggle]");
  const box = root.querySelector(".gate-reason");
  const confirmBtn = root.querySelector("[data-gate-confirm]");
  if (!toggle) return;
  toggle.onclick = () => { box.hidden = !box.hidden; if (!box.hidden) box.querySelector("textarea").focus(); };
  confirmBtn.onclick = () => {
    const reason = box.querySelector("textarea").value.trim();
    if (!reason) { toast("Say why, first."); return; }
    pendingOverride.set(id, reason);
    toggle.textContent = "Overriding — " + reason.slice(0, 40) + (reason.length > 40 ? "…" : "");
    toggle.disabled = true;
    box.hidden = true;
    if (go) { go.disabled = false; go.title = ""; }
    toast("Reason recorded. You can post now.");
  };
}

/* ---------- video page card ---------- */
async function paintVideoGate() {
  const m = /^video\/([a-z0-9_]+)/.exec((location.hash || "").slice(1));
  if (!m) return;
  const id = m[1];
  const cta = main.querySelector(".cta");
  if (!cta || main.querySelector(".gate[data-gate-card]")) return;
  const g = await gateFor(id);
  if (!g || !main.querySelector(".cta") || main.querySelector(".gate[data-gate-card]")) return;
  cta.insertAdjacentHTML("afterend", gateCardHtml(g, id, false));
}
new MutationObserver(() => paintVideoGate()).observe(main, {childList: true});
window.addEventListener("hashchange", () => setTimeout(paintVideoGate, 0));

/* ---------- Schedule sheet ---------- */
const _scheduleSheet = window.scheduleSheet;
if (typeof _scheduleSheet === "function") {
  window.scheduleSheet = async function (v) {
    const gPromise = gateFor(v.id, true);   // fresh — don't show a stale pass from before a re-render
    await _scheduleSheet(v);
    const g = await gPromise;
    if (!g) return;
    const sheetEl = [...document.querySelectorAll(".scrim")].pop()?.querySelector(".sheet");
    const choices = sheetEl && sheetEl.querySelector(".post-choices");
    if (!sheetEl || !choices) return;
    choices.insertAdjacentHTML("beforebegin", gateCardHtml(g, v.id, true));
    const go = sheetEl.querySelector("#go");
    const card = sheetEl.querySelector(".gate[data-gate-card]");
    const blocked = gateStatus(g) === "block";
    if (go && blocked && !pendingOverride.has(v.id)) {
      go.disabled = true;
      go.title = "The quality gate is blocking this post — fix the issues above or post anyway with a reason.";
    }
    if (card) wireOverride(card, v.id, go);
  };
}

/* ---------- runJob: ride the override reason along, once ---------- */
const _runJob = window.runJob;
if (typeof _runJob === "function") {
  window.runJob = function (action, id, extra = {}) {
    if (["post_live", "post_now", "post_at"].includes(action)) {
      const vid = String(id).split("|")[0];
      if (pendingOverride.has(vid)) {
        extra = {...extra, gate_override: pendingOverride.get(vid)};
        pendingOverride.delete(vid);
        gateCache.delete(vid);
      }
    }
    return _runJob(action, id, extra);
  };
}
