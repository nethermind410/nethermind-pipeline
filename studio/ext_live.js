"use strict";
/* ext_live.js — one shared EventSource for the whole app.
   Push, not poll: studio.py streams job/queue/task/done events over SSE (/api/events).
   Anything that used to poll (watchJob, the queue sheet, Task log, ext_nether's nx-system)
   listens for these window events instead:
     nx-job    {type:"started"|"progress"|"finished", ...}   — the running job
     nx-queue  {queue:[...]}                                 — the waiting line
     nx-task   {id, status, agent?, sub?}                    — orchestrator's task log
     nx-done   {key, done}                                   — a Today card ticked
   If the stream drops, a slow 15s fallback poll keeps things from going stale, and the
   stream itself reconnects with backoff. */
(() => {
  let es = null, retryMs = 1000, fallback = null;

  function dispatch(kind, detail) {
    window.dispatchEvent(new CustomEvent(kind, {detail}));
  }

  function startFallback() {
    clearInterval(fallback);
    fallback = setInterval(async () => {
      if (document.hidden) return;
      try {
        const j = await get("/api/job");
        dispatch("nx-job", {type: j.done ? "finished" : "progress", ...j});
        dispatch("nx-queue", {queue: j.queue});
      } catch (e) { /* server not up yet — next tick tries again */ }
    }, 15000);
  }

  function connect() {
    try { es && es.close(); } catch (e) {}
    es = new EventSource("/api/events");
    es.onmessage = e => {
      retryMs = 1000;
      let msg;
      try { msg = JSON.parse(e.data); } catch (e) { return; }
      if (msg.event === "job") dispatch("nx-job", msg.data);
      else if (msg.event === "queue") dispatch("nx-queue", msg.data);
      else if (msg.event === "task") dispatch("nx-task", msg.data);
      else if (msg.event === "done") dispatch("nx-done", msg.data);
    };
    es.onerror = () => {
      try { es.close(); } catch (e) {}
      setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, 15000);
    };
  }

  connect();
  startFallback();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && es && es.readyState === EventSource.CLOSED) connect();
  });
  window.nxLive = {reconnect: connect};

  /* ---------- truth badge ----------
     truth(value, {source, at, staleAfterHours, fmt}) → an HTML string for a headline number:
     a small source dot; hover/tap shows "YouTube API · 2h ago". A value older than
     staleAfterHours (default 24) renders dimmed with "stale" in the tooltip. A missing value
     (null/undefined) renders "—" — never 0, so "no data yet" never looks like "zero". */
  function agoStr(ms) {
    if (ms == null) return "unknown time";
    if (ms < 0) ms = 0;
    const m = Math.round(ms / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  }
  window.truth = function (value, opts) {
    const {source = "source unknown", at = null, staleAfterHours = 24, fmt} = opts || {};
    if (value === null || value === undefined) return `<span class="truth unknown" title="No data yet">—</span>`;
    const text = fmt ? fmt(value) : String(value);
    const ageMs = at ? Date.now() - new Date(at).getTime() : null;
    const stale = ageMs !== null && !Number.isNaN(ageMs) && ageMs > staleAfterHours * 3600 * 1000;
    const label = `${source} · ${agoStr(ageMs)}${stale ? " · stale" : ""}`;
    return `<span class="truth${stale ? " stale" : ""}" title="${label.replace(/"/g, "&quot;")}">${text}<i class="truth-dot" aria-hidden="true"></i></span>`;
  };
})();
