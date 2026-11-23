#!/usr/bin/env node
/* Look at an episode without rendering it: one frame, or a contact sheet.
 *   node still.cjs <episode.json> <out.png> [--durations 3.2,4.1] [--at 2.5 | --sheet] [--scale 0.25] [--quality 0.5]
 * --sheet = the sting, two frames a beat (30% and 80%) and the choice card. --at = one frame at that many seconds. */
const fs = require('fs');
const L = require('./lib.cjs');
(async () => {
  const A = L.parseArgs(process.argv.slice(2)), [epFile, out] = A.pos; let browser;
  if (!epFile || !out) { L.say({ ok: false, errors: ['usage: node still.cjs <episode.json> <out.png> [--at s | --sheet]'] }); process.exit(2); }
  try {
    const ep = JSON.parse(fs.readFileSync(epFile, 'utf8')), o = await L.openPage({ quality: Number(A.flags.quality || 1) }); browser = o.browser;
    const info = await o.page.evaluate(([e, d]) => loadEpisode(e, d), [ep, L.durations(A.flags.durations)]);
    let url;
    if (A.flags.sheet) {
      url = await o.page.evaluate(k => { const { starts, total } = timeline(), fs = [6]; for (let i = 0; i + 1 < starts.length; i++) for (const p of [0.3, 0.8]) fs.push(Math.round(starts[i] + (starts[i + 1] - starts[i]) * p)); fs.push(total - 6); return sheet(fs, 4, k); }, Number(A.flags.scale || 0.25));
    } else url = await o.page.evaluate(f => { draw(f); return OUT.toDataURL('image/png'); }, Math.round(Number(A.flags.at || 2) * 12));
    fs.writeFileSync(out, L.png(url));
    const r = await L.collect(o.page, o.errors, o.blocked); await browser.close();
    L.say({ ok: r.errors.length === 0, ...info, ...r, out }); process.exit(r.errors.length ? 1 : 0);
  } catch (e) { if (browser) await browser.close().catch(() => {}); L.say({ ok: false, errors: [String(e && e.message || e)] }); process.exit(1); }
})();
