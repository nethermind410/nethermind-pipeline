/* Shared by render.cjs and still.cjs. Opens the engine in headless Chromium with every outside request blocked:
 * the page can only read this folder (served to it as http://brick.local/). Needs playwright and three (npm ci). */
const fs = require('fs');
const path = require('path');
const ROOT = __dirname;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };

function parseArgs(argv) {
  const out = { pos: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]; if (!a.startsWith('--')) { out.pos.push(a); continue; }
    const next = argv[i + 1], has = next != null && !next.startsWith('--'); out.flags[a.slice(2)] = has ? next : true; if (has) i++;
  }
  return out;
}
async function openPage({ quality = 1 } = {}) {
  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  const errors = [], blocked = [];
  page.on('pageerror', e => errors.push(`page error: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  await page.route('**/*', r => {
    const u = new URL(r.request().url());
    if (u.hostname !== 'brick.local') { blocked.push(u.href); return r.abort(); }
    const file = path.join(ROOT, path.normalize(decodeURIComponent(u.pathname)));
    if (!file.startsWith(ROOT) || !fs.existsSync(file)) return r.fulfill({ status: 404, body: 'not found' });
    r.fulfill({ status: 200, contentType: TYPES[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file) });
  });
  await page.goto(`http://brick.local/play.html#q=${quality}`);
  await page.waitForFunction('window.READY', null, { timeout: 120000 });
  return { browser, page, errors, blocked };
}
async function collect(page, errors, blocked) {
  const e = await page.evaluate(() => ({ ERRS: window.ERRS.slice(), WARN: window.WARN.slice() })).catch(x => ({ ERRS: [x.message], WARN: [] }));
  return { errors: [...new Set([...errors, ...e.ERRS, ...blocked.map(u => `blocked network request: ${u}`)])], warnings: [...new Set(e.WARN)] };
}
const durations = s => (typeof s === 'string' && s.trim()) ? s.split(',').map(Number) : undefined;
const say = o => process.stdout.write(JSON.stringify(o) + '\n');
const png = u => Buffer.from(u.slice(u.indexOf(',') + 1), 'base64');
module.exports = { ROOT, parseArgs, openPage, collect, durations, say, png };
