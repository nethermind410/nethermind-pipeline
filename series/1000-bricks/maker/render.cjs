#!/usr/bin/env node
/* Render an episode to a silent 1080x1920 mp4. Drawn at 12 frames a second and saved at 24 (each frame twice:
 * TikTok and Reels refuse under 23). RUNS ON GITHUB ACTIONS (.github/workflows/brick-render.yml), never in a
 * Claude session and never on Courtney's laptop.
 *   node render.cjs <episode.json> <out.mp4> [--durations 3.2,4.1,3.8]
 * --durations = seconds a beat, from the voice. Prints one JSON line: {"ok":true,"frames":N,"seconds":S,...} */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const L = require('./lib.cjs');
(async () => {
  const A = L.parseArgs(process.argv.slice(2)), [epFile, out] = A.pos, t0 = Date.now(); let browser, ff;
  if (!epFile || !out) { L.say({ ok: false, errors: ['usage: node render.cjs <episode.json> <out.mp4> [--durations a,b,c]'] }); process.exit(2); }
  try {
    const ep = JSON.parse(fs.readFileSync(epFile, 'utf8')), o = await L.openPage({ quality: Number(A.flags.quality || 1) }); browser = o.browser;
    const info = await o.page.evaluate(([e, d]) => loadEpisode(e, d), [ep, L.durations(A.flags.durations)]);
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    const tmp = out + '.part.mp4';
    ff = spawn(process.env.FFMPEG || 'ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', '12', '-c:v', 'png', '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
      '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '24', '-an', '-movflags', '+faststart', tmp], { stdio: ['pipe', 'ignore', 'pipe'] });
    let ffErr = ''; ff.stderr.on('data', d => { ffErr += d; }); const done = new Promise(res => ff.on('close', res));
    const write = buf => new Promise(res => (ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res)));
    for (let f = 0; f < info.frames; f++) {
      await write(L.png(await o.page.evaluate(n => { draw(n); return OUT.toDataURL('image/png'); }, f)));
      if (f % 24 === 0) process.stderr.write(`frame ${f}/${info.frames}\n`);
    }
    ff.stdin.end(); const code = await done, r = await L.collect(o.page, o.errors, o.blocked); await browser.close(); browser = null;
    if (code !== 0) r.errors.push(`ffmpeg failed (${code}): ${ffErr.trim().slice(0, 400)}`);
    const ok = r.errors.length === 0; if (ok) fs.renameSync(tmp, out); else if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
    L.say({ ok, frames: info.frames, seconds: info.seconds, ...r, out: ok ? path.resolve(out) : null, render_s: +((Date.now() - t0) / 1000).toFixed(1) }); process.exit(ok ? 0 : 1);
  } catch (e) { if (ff && ff.stdin && !ff.stdin.destroyed) ff.stdin.destroy(); if (browser) await browser.close().catch(() => {}); L.say({ ok: false, errors: [String(e && e.message || e)] }); process.exit(1); }
})();
