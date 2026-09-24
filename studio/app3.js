"use strict";
/* Create tools: Inspiration board + Series planner (tabs inside Ideas), script workshop + hook picker (review). */
const ideasTabs = active => `<div class="seg big tabs3" role="tablist">${[["ideas", "Ideas"], ["series", "Series"], ["inspiration", "Inspiration"]]
  .map(([k, l]) => `<button role="tab" aria-selected="${k === active}" class="${k === active ? "on" : ""}" data-go="${k}">${l}</button>`).join("")}</div>`;

/* ---------- Inspiration board ---------- */
async function pageInspiration() {
  const items = await get("/api/inspiration");
  main.innerHTML = `<div class="page">
    <div class="head"><h1>Inspiration</h1><p>Drop in images or links that capture the look you want. The 7:00 build reads this board for art direction.</p></div>
    ${ideasTabs("inspiration")}
    <label class="drop card" id="drop" tabindex="0">
      <input type="file" id="ifile" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden>
      <b>Drop images here, paste, or click to choose</b><span>PNG, JPG, WebP or GIF, up to 12 MB each</span></label>
    <div class="insp-link"><input id="ilink" placeholder="…or paste a link (Pinterest, YouTube, a site you like)" aria-label="Link">
      <input id="inote" placeholder="What do you like about it? (optional)" aria-label="Note"><button class="btn primary" id="iadd">Add link</button></div>
    <div class="masonry">${items.map(i => `<figure class="card insp">
        ${i.file ? `<img src="/insp/${esc(i.file)}" alt="${esc(i.note || "Inspiration")}">` : `<a class="insp-url" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.url.replace(/^https?:\/\//, "").slice(0, 60))}</a>`}
        <figcaption>${i.note ? esc(i.note) : `<span class="s">No note</span>`}<button class="link small" data-irm="${esc(i.id)}">Remove</button></figcaption></figure>`).join("")
      || `<div class="caught"><b>Nothing here yet</b>Add a few images and the next builds will lean into that look.</div>`}</div></div>`;
  const drop = $("#drop"), file = $("#ifile");
  const upload = async files => {
    for (const f of files) {
      if (!f.type.startsWith("image/")) continue;
      const data = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
      try { await post("/api/inspiration", {image: data, note: $("#inote").value}); } catch (e) { toast(e.message); }
    }
    toast("Added to your board."); route();
  };
  drop.onclick = () => file.click(); file.onchange = () => upload(file.files);
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = () => drop.classList.remove("over");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); upload(e.dataTransfer.files); };
  document.onpaste = e => { if (location.hash === "#inspiration") upload([...e.clipboardData.files]); };
  $("#iadd").onclick = async () => { try { await post("/api/inspiration", {url: $("#ilink").value.trim(), note: $("#inote").value}); toast("Link added."); route(); } catch (e) { toast(e.message); } };
}

/* ---------- Series planner ---------- */
let seriesDraft = null;
async function pageSeries() {
  seriesDraft = await get("/api/series");
  drawSeries();
}
function drawSeries() {
  main.innerHTML = `<div class="page">
    <div class="head-row"><div class="head"><h1>Series</h1><p>Plan runs of videos that feed each other. The active series drives the 7:00 build and every end card names the next part.</p></div>
      <button class="btn primary" id="snew">+ New series</button></div>
    ${ideasTabs("series")}
    ${seriesDraft.map((s, si) => `<section class="card series ${s.active ? "active" : ""}">
      <div class="series-head"><input class="sname" data-si="${si}" value="${esc(s.name)}" aria-label="Series name">
        <label class="switch"><input type="checkbox" data-sact="${si}" ${s.active ? "checked" : ""}> Drives the 7:00 build</label>
        <button class="link small" data-sdel="${si}">Delete</button></div>
      <ol class="parts">${s.items.map((it, ii) => `<li class="${it.video ? "made" : ""}"><span class="pn">Part ${ii + 1}</span>
        <input class="phook" data-si="${si}" data-ii="${ii}" value="${esc(it.hook)}" aria-label="Part ${ii + 1}">
        ${it.video ? `<button class="pill live" data-open="${esc(it.video)}">Made</button>` : `<span class="pill">To make</span>`}
        <button class="icon" data-sup="${si}:${ii}" aria-label="Move up" ${ii ? "" : "disabled"}>↑</button>
        <button class="icon" data-sdn="${si}:${ii}" aria-label="Move down" ${ii < s.items.length - 1 ? "" : "disabled"}>↓</button>
        <button class="icon" data-srm="${si}:${ii}" aria-label="Remove part">×</button></li>`).join("")}</ol>
      <button class="link small" data-sadd="${si}">+ Add a part</button></section>`).join("")
      || `<div class="card"><div class="caught"><b>No series yet</b>A series is a run like "Marvel powers that are real, parts 1–5". Add ideas to one from the Ideas tab too.</div></div>`}
    <div class="row-end" ${seriesDraft.length ? "" : "hidden"}><button class="btn primary" id="ssave">Save series</button></div></div>`;
}
async function saveSeries(msg = "Series saved.") {
  const r = await post("/api/series", {series: seriesDraft}); seriesDraft = r.series; toast(msg); drawSeries();
}

/* ---------- Review screen additions: hook picker + script workshop ---------- */
async function enhanceReview(v) {
  const col = main.querySelector(".review > div:last-child"); if (!col || !v.script.length) return;
  const h = await get("/api/hooks/" + encodeURIComponent(v.id));
  const hookCard = h.options.length > 1 ? `<div class="card precheck"><div class="pc-head"><b>Pick the opening line</b></div>
      ${h.options.map(o => `<label class="opt ${o.current ? "on" : ""}"><input type="radio" name="hook" ${o.current ? "checked" : ""} data-hook="${esc(o.text)}"><div class="t">${esc(o.text)}</div></label>`).join("")}
      ${h.past.length ? `<p class="fine">For reference, your posted openings and their real YouTube views: ${h.past.map(p => `“${esc(p.hook.slice(0, 60))}…” ${fmt(p.views)}`).join(" · ")}</p>` : ""}
      <p class="fine">Changing the opening re-records only that line when you tap Re-make.</p></div>` : "";
  const workshop = `<details class="more" id="workshop"><summary>Edit the script</summary><div class="card script-edit">
      ${v.script.map((t, i) => `<label><span>Line ${i + 1}</span><textarea data-line="${i}" rows="2">${esc(t)}</textarea></label>`).join("")}
      <p class="fine">Only change what you've checked — every fact still needs a source. Saving re-records just the lines you changed.</p>
      <div class="cta"><button class="btn primary" id="wsave">Save and re-make</button></div></div></details>`;
  const old = [...col.querySelectorAll("details.more")].find(d => d.querySelector("summary")?.textContent === "Script");
  if (old) old.outerHTML = workshop; else col.insertAdjacentHTML("beforeend", workshop);
  if (hookCard) col.querySelector(".cta").insertAdjacentHTML("afterend", hookCard);
  $("#wsave").onclick = async () => {
    const cfgIds = (await get("/api/video/" + encodeURIComponent(v.id))).script_ids || null;
    const lines = {}; main.querySelectorAll("[data-line]").forEach(t => lines[(cfgIds || [])[+t.dataset.line] || `s${+t.dataset.line + 1}`] = t.value);
    try { const r = await post("/api/script", {id: v.id, lines}); if (!r.changed.length) return toast("No changes to save.");
      toast(`Saved ${r.changed.length} line${r.changed.length > 1 ? "s" : ""}. Re-making…`); runJob("build_nofetch", v.id); } catch (e) { toast(e.message); }
  };
}

/* ---------- wiring ---------- */
Object.assign(window.PAGES, {inspiration: pageInspiration, series: pageSeries});
const _route3 = window.onRoute;
window.onRoute = name => { _route3 && _route3(name); document.querySelectorAll(".nav").forEach(n => { if (["series", "inspiration"].includes(name)) n.classList.toggle("on", n.dataset.go === "ideas"); }); };
const _pageVideo = pageVideo;
pageVideo = async id => { await _pageVideo(id); if (current) enhanceReview(current); };

document.addEventListener("input", e => {
  if (!seriesDraft) return;
  const t = e.target;
  if (t.matches(".sname")) seriesDraft[+t.dataset.si].name = t.value;
  if (t.matches(".phook")) seriesDraft[+t.dataset.si].items[+t.dataset.ii].hook = t.value;
});
document.addEventListener("change", e => {
  const t = e.target;
  if (t.matches("[data-sact]")) { seriesDraft.forEach((s, i) => s.active = i === +t.dataset.sact && t.checked); saveSeries(t.checked ? "This series now drives the 7:00 build." : "Series paused."); }
});
document.addEventListener("click", async e => {
  const t = e.target;
  const hk = t.closest("[data-hook]");
  if (hk && current) { try { await post("/api/hook", {id: current.id, text: hk.dataset.hook}); toast("Opening line chosen. Tap Re-make to hear it.", {label: "Re-make", run: () => runJob("build_nofetch", current.id)}); route(); } catch (err) { toast(err.message); } return; }
  const rm = t.closest("[data-irm]"); if (rm) { await post("/api/inspiration/remove", {id: rm.dataset.irm}); toast("Removed."); return route(); }
  if (t.closest("#snew")) { seriesDraft.push({name: "New series", active: false, items: [{hook: ""}]}); return drawSeries(); }
  if (t.closest("#ssave")) return saveSeries();
  const [op, arg] = ["sadd", "sdel", "sup", "sdn", "srm"].map(k => [k, t.closest(`[data-${k}]`)?.dataset[k]]).find(x => x[1] != null) || [];
  if (op) {
    const [si, ii] = String(arg).split(":").map(Number), items = seriesDraft[si]?.items;
    if (op === "sadd") items.push({hook: ""});
    if (op === "sdel") seriesDraft.splice(si, 1);
    if (op === "srm") items.splice(ii, 1);
    if (op === "sup" && ii > 0) [items[ii - 1], items[ii]] = [items[ii], items[ii - 1]];
    if (op === "sdn" && ii < items.length - 1) [items[ii + 1], items[ii]] = [items[ii], items[ii + 1]];
    return drawSeries();
  }
  const add = t.closest("[data-toseries]");
  if (add) {
    const all = await get("/api/series");
    if (!all.length) { await post("/api/series", {series: [{name: "My first series", items: [{hook: add.dataset.toseries}]}]}); return toast("Started a new series with this idea.", {label: "Open", run: () => go("series")}); }
    sheet(`<h3>Add to which series?</h3>${all.map((s, i) => `<button class="btn" data-pick="${i}" style="justify-content:flex-start">${esc(s.name)} · ${s.items.length} parts</button>`).join("")}
      <div class="row-end"><button class="btn" data-close>Cancel</button></div>`, (el, close) => el.querySelectorAll("[data-pick]").forEach(b => b.onclick = async () => {
        all[+b.dataset.pick].items.push({hook: add.dataset.toseries}); await post("/api/series", {series: all}); close(); toast(`Added to ${all[+b.dataset.pick].name}.`); }));
  }
}, true);
