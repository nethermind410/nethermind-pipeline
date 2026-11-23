/* 1,000 BRICKS engine. An episode is a JSON file; this turns it into frames. 12 frames a second, no motion blur,
 * poses stepped from frame to frame: the way a real brickfilm is shot. Nothing is generated: the same episode
 * file draws the same frames on any machine.
 *   loadEpisode(ep, durations) -> { frames, seconds }      draw(f) draws frame f onto OUT (1080x1920)
 * Timeline, the same as the pixel series: 1.0 s sting -> each beat for its seconds -> 2.5 s choice card. */
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { KIT, clamp, ease, lerp, rnd } from './kit/base.js';
import './kit/figure.js';
import './kit/world.js';
import * as HUD from './hud.js';

const W = 1080, H = 1920, FPS = 12, STING = 1.0, END = 2.5;
const Q = Number((location.hash.match(/q=([\d.]+)/) || [])[1] || 1);   // drawing quality: 1 = full size, 0.5 = quick look
const ERRS = window.ERRS = [], WARN = window.WARN = [];
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(W * Q, H * Q, false); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
const scene = new THREE.Scene(); scene.background = new THREE.Color('#07040c'); scene.fog = new THREE.Fog('#0a0512', 18, 48);
scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.25;
const cam = new THREE.PerspectiveCamera(27, W / H, 0.1, 140);
const comp = new EffectComposer(renderer); comp.setSize(W * Q, H * Q); comp.addPass(new RenderPass(scene, cam));
const bokeh = new BokehPass(scene, cam, { focus: 14, aperture: 0.0004, maxblur: 0.008 }); comp.addPass(bokeh); comp.addPass(new OutputPass());
const OUT = window.OUT = document.createElement('canvas'); OUT.width = W; OUT.height = H; document.body.appendChild(OUT);
const c2 = OUT.getContext('2d');

let EP = null, beats = [], starts = [], total = 0;
const V = a => new THREE.Vector3(a[0], a[1], a[2]);
const win = (a, t) => clamp((t - (a.from || 0)) / Math.max(1e-6, (a.until == null ? 1 : a.until) - (a.from || 0)));

function build(beat, i, ep) {
  const g = new THREE.Group(), st = { g, beat, things: [] };
  const sn = (beat.set && beat.set.name) || 'corridor', S = KIT.set[sn];
  if (!S) WARN.push(`beat ${i + 1}: no set called "${sn}"`); else st.set = S.build(g, (beat.set && beat.set.opts) || {});
  for (const [kind, list] of [['actor', beat.actors], ['prop', beat.props], ['fx', beat.fx]]) for (const a of list || []) {
    const K = KIT[kind][a.name];
    if (!K) { WARN.push(`beat ${i + 1}: no ${kind} called "${a.name}"`); continue; }
    try { const o = K.build(a, ep); g.add(o); st.things.push({ K, o, a, kind }); } catch (e) { ERRS.push(`${kind} ${a.name}: ${e.message}`); }
  }
  g.visible = false; scene.add(g); return st;
}

window.loadEpisode = (ep, durs) => {
  for (const s of beats) scene.remove(s.g);
  EP = ep; let t = STING, n = ep.count == null ? 1000 : ep.count; starts = [];
  beats = (ep.beats || []).map((b, i) => {
    const s = build(b, i, ep); s.seconds = (durs && durs[i]) || b.seconds || 3.5; starts.push(Math.round(t * FPS)); t += s.seconds;
    s.countFrom = n; if (b.count) n = b.count.to; s.countTo = n;
    for (const line of b.words || []) { if (HUD.textW(line, 6) > 940) WARN.push(`beat ${i + 1}: line too wide: "${line}"`); for (const ch of line) if (!HUD.known(ch)) WARN.push(`beat ${i + 1}: no letter for "${ch}"`); }
    return s;
  });
  starts.push(Math.round(t * FPS)); total = Math.round((t + END) * FPS);
  return { frames: total, seconds: +(total / FPS).toFixed(2), beats: beats.length, kit: Object.fromEntries(Object.entries(KIT).map(([k, v]) => [k, Object.keys(v)])) };
};

window.draw = f => {
  let i = beats.length - 1, t = 1, mode = 'end';
  if (f < starts[0]) { i = 0; t = 0; mode = 'sting'; }
  else if (f < starts[beats.length]) { i = starts.findIndex((s, k) => f >= s && f < starts[k + 1]); t = (f - starts[i]) / Math.max(1, starts[i + 1] - starts[i]); mode = 'beat'; }
  const st = beats[i], b = st.beat; beats.forEach(s => { s.g.visible = s === st; });
  if (st.set && st.set.tick) st.set.tick(f);
  for (const x of st.things) {
    try {
      if (x.kind === 'prop') {
        const a = x.a, p = ease(win(a, t)), to = a.to || {}; x.o.visible = t >= (a.from || 0) && t <= (a.until == null ? 1 : a.until) + 1e-6;
        x.o.position.set(lerp(a.x || 0, to.x == null ? a.x || 0 : to.x, p), lerp(a.y || 0, to.y == null ? a.y || 0 : to.y, p) + 0.4, lerp(a.z || 0, to.z == null ? a.z || 0 : to.z, p));
        x.o.rotation.set(a.rx || 0, a.ry || 0, a.rz || 0); x.o.scale.setScalar(a.scale || 1);
      }
      if (x.K.update) x.K.update(x.o, x.a, t, f, st.seconds);
    } catch (e) { if (!ERRS.includes(`${x.a.name}: ${e.message}`)) ERRS.push(`${x.a.name}: ${e.message}`); }
  }
  const C = b.cam || {}, p = ease(t), to = C.to || {};
  const pos = V(C.pos || [-1.5, 3.6, 19]).lerp(V(to.pos || C.pos || [-1.5, 3.6, 19]), p), look = V(C.look || [0.4, 4.7, -3]).lerp(V(to.look || C.look || [0.4, 4.7, -3]), p);
  pos.x += (rnd(f * 2.3) - 0.5) * 0.012; pos.y += (rnd(f * 4.1) - 0.5) * 0.012;      // a hand-nudged camera never sits perfectly still
  cam.position.copy(pos); cam.fov = lerp(C.fov || 40, to.fov || C.fov || 40, p); cam.updateProjectionMatrix(); cam.lookAt(look);
  const hero = st.things.find(x => x.a.name === 'hero'), fp = C.focus ? V(C.focus) : hero ? hero.o.position.clone().setY(3.5) : look;
  bokeh.uniforms.focus.value = pos.distanceTo(fp);
  comp.render();
  c2.drawImage(renderer.domElement, 0, 0, W, H);
  // what is written on screen
  if (mode === 'sting') {
    c2.fillStyle = 'rgba(5,3,10,0.62)'; c2.fillRect(0, 0, W, H);
    HUD.text(c2, String(EP.series || '1,000 bricks').toLowerCase(), W / 2, 760, 13); HUD.text(c2, 'part ' + (EP.part || 1), W / 2, 900, 9, '#19e0c8');
    return;
  }
  const cn = b.count, cp = cn ? clamp((t - (cn.at == null ? 0.5 : cn.at)) / (cn.over || 0.25)) : 1;
  const steps = Math.round(cp * 8) / 8, val = mode === 'end' ? st.countTo : lerp(st.countFrom, st.countTo, steps);
  HUD.counter(c2, val, W, cn && cp > 0 && cp < 1 ? Math.sign(st.countTo - st.countFrom) : 0);
  if (mode === 'beat') {
    (b.words || []).forEach((line, k) => HUD.text(c2, line, W / 2, 330 + k * 64, 6));
    for (const L of b.labels || []) if (t >= (L.from || 0) && t <= (L.until == null ? 1 : L.until)) HUD.text(c2, L.text, L.x || W / 2, L.y || 520, L.px || 20, L.col || '#ffffff');
  } else {
    const v = EP.vote || {}; c2.fillStyle = 'rgba(5,3,10,0.72)'; c2.fillRect(0, 560, W, 760);
    HUD.text(c2, v.q || 'what do you do?', W / 2, 640, 9);
    HUD.text(c2, 'a: ' + (v.a || ''), W / 2, 800, 8, '#19e0c8'); HUD.text(c2, 'b: ' + (v.b || ''), W / 2, 930, 8, '#ff6b5e');
    if (f % 8 < 6) HUD.text(c2, 'comment a or b', W / 2, 1120, 7, '#ffe08a');
    HUD.text(c2, 'part ' + ((EP.part || 1) + 1) + ' follows the vote', W / 2, 1220, 5, '#cfc6e8');
  }
};
// a contact sheet: the frames in fs, cols across, each drawn at k times full size
window.sheet = (fs, cols, k) => {
  const w = Math.round(W * k), h = Math.round(H * k), cv = document.createElement('canvas'); cv.width = w * cols; cv.height = h * Math.ceil(fs.length / cols);
  const x = cv.getContext('2d'); fs.forEach((f, n) => { window.draw(f); x.drawImage(OUT, (n % cols) * w, Math.floor(n / cols) * h, w, h); });
  return cv.toDataURL('image/png');
};
window.timeline = () => ({ starts, total, fps: FPS });
window.READY = true;
