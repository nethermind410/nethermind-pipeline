"use strict";
/* Control → AI engines: which engine writes each job, the fallbacks, keys and what it costs.
   Claude stays on research and scripts (accuracy is the channel); everything else can run on whatever is cheapest,
   and any answer that isn't good enough goes to the next engine in the chain. */
(() => {
  const QUICK = {openai: ["https://api.openai.com/v1", "OPENAI_API_KEY", "OpenAI"],
                 openrouter: ["https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OpenRouter"],
                 gemini: ["https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "Gemini"]};
  const MODELS = [["claude-opus-5", "Opus 5 — best for research (recommended)"], ["claude-sonnet-5", "Sonnet 5 — cheaper, strong"],
                  ["claude-haiku-4-5", "Haiku 4.5 — cheapest, fine for packaging"]];

  async function pageEngines() {
    const s = await get("/api/llm"), E = s.engines, u = s.usage;
    const opt = (job, sel, i) => {
      const web = s.jobs[job].web;
      return `<select data-job="${job}" data-slot="${i}" aria-label="${esc(s.jobs[job].what)} — engine ${i + 1}">
        ${i ? `<option value="">— none —</option>` : ""}
        ${Object.entries(E).filter(([k, e]) => !web || e.web).map(([k, e]) => `<option value="${k}" ${sel === k ? "selected" : ""}>${esc(e.short || e.name)}${e.available ? "" : " · off"}</option>`).join("")}</select>`;
    };
    const jobs = Object.entries(s.jobs).map(([j, v]) => `<div class="en-job"><div><b>${esc(v.what)}</b>${v.web ? `<span class="pill">needs web search</span>` : ""}</div>
      <div class="en-chain">${[0, 1, 2, 3].map(i => opt(j, v.chain[i] || "", i)).join('<span class="en-arrow">then</span>')}</div></div>`).join("");
    const presets = Object.entries(s.presets).map(([k, p]) => `<button class="en-preset ${s.preset === k ? "on" : ""}" data-preset="${k}">
      <b>${esc(p.name)}</b><span>${esc(p.what)}</span>${s.preset === k ? `<em>In use</em>` : ""}</button>`).join("");
    const dot = e => `<span class="en-dot ${e.available ? "ok" : ""}"></span>`;
    const keyRow = (name, placeholder) => `<div class="en-key"><input type="password" data-key="${name}" placeholder="${esc(placeholder)}" autocomplete="off">
      <button class="btn small" data-savekey="${name}">Save key</button></div>`;
    const a = E.anthropic.config, o = E.openai.config, l = E.local.config;
    const engines = `
      <div class="card en-eng">${dot(E.claude)}<div><b>${esc(E.claude.name)}</b><p class="nx-meta">${esc(E.claude.detail)} · no per-use cost, but a weekly limit.</p></div>
        <button class="btn small" data-test="claude">Test</button></div>
      <div class="card en-eng">${dot(E.anthropic)}<div><b>${esc(E.anthropic.name)}</b><p class="nx-meta">${esc(E.anthropic.detail)} · pay per use · has web search, so it can research.</p>
        <label class="en-f"><span class="k">Model</span><select data-cfg="anthropic.model">${MODELS.map(([m, t]) => `<option value="${m}" ${a.model === m ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
        ${keyRow("ANTHROPIC_API_KEY", "Paste an Anthropic API key (console.anthropic.com)")}</div>
        <button class="btn small" data-test="anthropic">Test</button></div>
      <div class="card en-eng">${dot(E.openai)}<div><b>${esc(E.openai.name)}</b><p class="nx-meta">${esc(E.openai.detail)} · pay per use · no web search (packaging, replies).</p>
        <div class="en-quick">${Object.entries(QUICK).map(([k, [, , n]]) => `<button class="nx-chip ${o.base_url === QUICK[k][0] ? "on" : ""}" data-quick="${k}">${n}</button>`).join("")}</div>
        <label class="en-f"><span class="k">Model</span><input data-cfg="openai.model" value="${esc(o.model)}" placeholder="the model name from your provider"></label>
        <label class="en-f"><span class="k">Address</span><input data-cfg="openai.base_url" value="${esc(o.base_url)}"></label>
        <input type="hidden" data-cfg="openai.key_env" value="${esc(o.key_env)}">
        ${keyRow(o.key_env || "OPENAI_API_KEY", `Paste your ${o.key_env || "OPENAI_API_KEY"}`)}</div>
        <button class="btn small" data-test="openai">Test</button></div>
      <div class="card en-eng">${dot(E.local)}<div><b>${esc(E.local.name)}</b><p class="nx-meta">${esc(E.local.detail)} · free, runs on this Mac · no web search.
          Install Ollama (ollama.com), then in Terminal: <code>ollama pull</code> a model and put its name here.</p>
        <label class="en-f"><span class="k">Model</span><input data-cfg="local.model" value="${esc(l.model)}" placeholder="the model you pulled in Ollama"></label>
        <label class="en-f"><span class="k">Address</span><input data-cfg="local.base_url" value="${esc(l.base_url)}"></label></div>
        <button class="btn small" data-test="local">Test</button></div>`;
    const ur = Object.entries(u.engines).map(([k, b]) => `<tr><td>${esc(E[k]?.name || k)}</td><td>${b.calls}</td><td>${b.ok}</td><td class="${b.failed ? "bad" : ""}">${b.failed}</td><td>$${b.cost.toFixed(2)}</td></tr>`).join("");
    main.innerHTML = `<div class="page wide">
      <div class="head-row"><div class="head"><h1>AI engines</h1><p>Claude stays on research and scripts — accuracy is the channel. Everything else can run on whatever's cheapest.
        Every answer is checked; one that isn't good enough goes to the next engine, so a cheaper engine can cost a retry, never a broken video.</p></div></div>
      <section class="vd ${u.claude_share === null ? "info" : "good"}"><span class="vd-q">Is Claude only doing the jobs that need it?</span>
        <div class="vd-a">${u.claude_share === null ? "Nothing written through the engines yet this week" : `Claude wrote ${Math.round(u.claude_share * 100)}% of this week's answers · $${u.cost.toFixed(2)} spent on APIs`}</div>
        <p>${s.preset ? `Preset: ${esc(s.presets[s.preset].name)}.` : "Custom setup."} Change it below — nothing changes until you save.</p></section>
      <h2>Presets</h2><div class="en-presets">${presets}</div>
      <h2>Who writes what</h2><div class="card en-jobs">
        <div class="en-legend"><div>Job</div><div><span>First choice</span><span>If that fails</span><span>Then</span><span>Last resort</span></div></div>${jobs}<div class="row-end"><button class="btn primary" id="en-save">Save</button></div></div>
      <h2>Engines</h2><div class="en-engines">${engines}</div>
      <h2>Last 7 days</h2>${ur ? `<div class="card"><table class="en-use"><thead><tr><th>Engine</th><th>Calls</th><th>Answered</th><th>Failed</th><th>Cost</th></tr></thead><tbody>${ur}</tbody></table></div>`
        : `<div class="card caught">Nothing yet — usage shows here after the next draft.</div>`}</div>`;

    const collect = () => {
      const routes = {};
      main.querySelectorAll("select[data-job]").forEach(sel => { (routes[sel.dataset.job] ||= [])[+sel.dataset.slot] = sel.value; });
      Object.keys(routes).forEach(j => routes[j] = [...new Set(routes[j].filter(Boolean))]);
      const engines = {};
      main.querySelectorAll("[data-cfg]").forEach(el => { const [e, k] = el.dataset.cfg.split("."); (engines[e] ||= {})[k] = el.value; });
      return {routes, engines};
    };
    $("#en-save").onclick = async () => { try { toast((await post("/api/llm/save", collect())).reply); window.nxSound?.play("done"); route(); } catch (e) { toast(e.message); } };
    main.querySelectorAll("[data-cfg]").forEach(el => el.onchange = async () => { try { await post("/api/llm/save", {engines: collect().engines}); } catch (e) { toast(e.message); } });
    main.querySelectorAll("[data-preset]").forEach(b => b.onclick = async () => { try { toast((await post("/api/llm/preset", {id: b.dataset.preset})).reply); route(); } catch (e) { toast(e.message); } });
    main.querySelectorAll("[data-quick]").forEach(b => b.onclick = async () => { const [url, keyEnv] = QUICK[b.dataset.quick];
      try { await post("/api/llm/save", {engines: {openai: {base_url: url, key_env: keyEnv}}}); route(); } catch (e) { toast(e.message); } });
    main.querySelectorAll("[data-savekey]").forEach(b => b.onclick = async () => { const inp = main.querySelector(`[data-key="${b.dataset.savekey}"]`);
      try { toast((await post("/api/llm/key", {name: b.dataset.savekey, value: inp.value})).reply); inp.value = ""; route(); } catch (e) { toast(e.message); } });
    main.querySelectorAll("[data-test]").forEach(b => b.onclick = async () => { b.disabled = true; b.textContent = "Testing…";
      try { toast((await post("/api/llm/test", {engine: b.dataset.test})).reply); } catch (e) { toast(e.message); } finally { b.disabled = false; b.textContent = "Test"; } });
  }
  window.PAGES.engines = pageEngines;
})();
