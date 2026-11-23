/* The brick figure. ONE function builds every figure in the series: the hero, the statues, anyone he meets.
 * The hero is figure(HERO colours + loadout). He is never drawn any other way, so he cannot drift between shots.
 * Joints (userData.j): legL, legR, armL, armR, head. A pose is just angles, like posing a real figure. */
import * as THREE from 'three';
import { KIT, abs, stone, boxG, mesh, lerp, ease, clamp } from './base.js';

const TEAL = '#19e0c8';
let FACE, HAIR;
function faceTex() {   // the printed face, drawn once: pale blue-grey eyes, light brown stubble and moustache, nothing else
  if (FACE) return FACE;
  const cv = document.createElement('canvas'); cv.width = 1024; cv.height = 512; const x = cv.getContext('2d');
  x.fillStyle = '#f0c8a2'; x.fillRect(0, 0, 1024, 512); const cx = 512;
  let s = 3; const r = () => (s = (s * 48271) % 2147483647) / 2147483647;
  x.fillStyle = 'rgba(140,98,64,0.6)';
  for (let i = 0; i < 3200; i++) {
    const a = (r() - 0.5) * 300, y = 285 + r() * 190, jaw = Math.abs(a) > 100 ? 255 : 322, mouth = Math.abs(a) < 62 && y > 340 && y < 378;
    if (y > jaw + Math.abs(a) * 0.08 && !mouth) x.fillRect(cx + a, y, 4, 4);
  }
  for (let i = 0; i < 700; i++) { const a = (r() - 0.5) * 150, y = 308 + r() * 26 + Math.abs(a) * 0.14; x.fillRect(cx + a, y, 4, 4); }
  x.strokeStyle = '#4a2f20'; x.lineWidth = 8; x.lineCap = 'round'; x.beginPath(); x.moveTo(cx - 40, 358); x.quadraticCurveTo(cx, 366, cx + 40, 356); x.stroke();
  for (const sx of [-1, 1]) {
    x.fillStyle = '#15171b'; x.beginPath(); x.ellipse(cx + sx * 60, 232, 20, 25, 0, 0, 7); x.fill();
    x.fillStyle = '#a9c0d4'; x.beginPath(); x.ellipse(cx + sx * 60, 234, 13, 17, 0, 0, 7); x.fill();
    x.fillStyle = '#15171b'; x.beginPath(); x.arc(cx + sx * 60, 235, 6, 0, 7); x.fill();
    x.fillStyle = '#fff'; x.beginPath(); x.arc(cx + sx * 60 + 7, 225, 5, 0, 7); x.fill();
    x.strokeStyle = '#8a6a48'; x.lineWidth = 10; x.beginPath(); x.moveTo(cx + sx * 34, 192); x.lineTo(cx + sx * 88, 184); x.stroke();
  }
  FACE = new THREE.CanvasTexture(cv); FACE.colorSpace = THREE.SRGBColorSpace; FACE.anisotropy = 8; return FACE;
}
function hairTex() {   // comb lines, front to back
  if (HAIR) return HAIR;
  const cv = document.createElement('canvas'); cv.width = 256; cv.height = 64; const x = cv.getContext('2d'); x.fillStyle = '#909090'; x.fillRect(0, 0, 256, 64);
  for (let i = 0; i < 256; i += 10) { x.fillStyle = '#3c3c3c'; x.fillRect(i, 0, 3, 64); }
  HAIR = new THREE.CanvasTexture(cv); HAIR.wrapS = THREE.RepeatWrapping; HAIR.repeat.set(3, 1); return HAIR;
}

export const HERO = () => {
  const dark = abs('#2b2d36'), flesh = abs('#f0c8a2');
  return { legL: dark, legR: dark, hip: abs('#22242b'), torso: abs('#30323c'), armL: abs('#30323c'), armR: abs('#30323c'), hand: flesh, head: flesh,
    face: abs('#ffffff', { map: faceTex() }), hair: abs('#ecd583', { bumpMap: hairTex(), bumpScale: 3, roughness: 0.42 }),
    heart: abs(TEAL, { emissive: '#12c9b4', emissiveIntensity: 1.5 }) };
};
export const STONE = () => { const g = stone('#6c6f78'), d = stone('#575a62'); return { legL: g, legR: g, hip: d, torso: g, armL: g, armR: g, hand: d, head: g }; };

// loadout pieces: each one changes the hero's parts, once, in one place
const LOADOUT = {
  stoneArm(c) { c.armR = stone('#9a9da6'); c.handR = stone('#7d8089'); c.bigR = true; },
  gauntlet(c) { c.handL = abs('#0c0c10'); c.bigL = true; },
  redLeg(c) { c.legL = abs('#c8281e'); },
  stonePlate(c) { c.plateR = stone('#a9adb6'); },
};

export function figure(c, pose = {}) {
  const g = new THREE.Group(), j = {};
  for (const sx of [-1, 1]) {
    const L = new THREE.Group(); L.position.set(sx * 0.5, 1.55, 0); const mat = sx < 0 ? c.legL : c.legR;
    mesh(boxG(0.94, 1.5, 0.95, 0.06), mat, 0, -0.8, 0, L); mesh(boxG(0.94, 0.42, 1.3, 0.06), mat, 0, -1.34, 0.18, L);
    g.add(L); j[sx < 0 ? 'legL' : 'legR'] = L;
  }
  mesh(boxG(2.0, 0.45, 1.0, 0.06), c.hip, 0, 1.75, 0, g);
  const s = new THREE.Shape(); s.moveTo(-1, 0); s.lineTo(1, 0); s.lineTo(0.74, 1.6); s.lineTo(-0.74, 1.6); s.closePath();
  const tg = new THREE.ExtrudeGeometry(s, { depth: 0.9, bevelEnabled: true, bevelSize: 0.05, bevelThickness: 0.05, bevelSegments: 3 }); tg.translate(0, 0, -0.45);
  mesh(tg, c.torso, 0, 1.98, 0, g);
  if (c.heart) {   // the teal 1x1 brick in the centre of his chest: the life counter
    mesh(boxG(0.5, 0.5, 0.2, 0.04), c.heart, 0, 2.86, 0.56, g, false);
    mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.1, 16), c.heart, 0, 2.86, 0.7, g, false).rotation.x = Math.PI / 2;
    const gl = new THREE.PointLight(TEAL, 4, 6, 2); gl.position.set(0, 2.86, 1.2); g.add(gl);
  }
  for (const sx of [-1, 1]) {
    const R = sx > 0, mat = R ? c.armR : c.armL, hand = (R ? c.handR : c.handL) || c.hand, big = R ? c.bigR : c.bigL, k = big ? 1.35 : 1;
    const A = new THREE.Group(); A.position.set(sx * 0.98, 3.38, 0); A.rotation.z = sx * 0.2;
    const sw = new THREE.Group(); A.add(sw);   // the shoulder swings forward and back, like the real joint
    mesh(new THREE.SphereGeometry(0.3 * k, 20, 14), mat, 0, 0, 0, sw);
    mesh(new THREE.CapsuleGeometry(0.27 * k, 0.55, 6, 16), mat, sx * 0.06, -0.42, 0, sw);
    mesh(new THREE.CapsuleGeometry(0.25 * k, 0.45, 6, 16), mat, sx * 0.08, -0.95, 0.22, sw).rotation.x = -0.75;
    mesh(new THREE.CylinderGeometry(0.13 * k, 0.13 * k, 0.26, 14), hand, sx * 0.08, -1.18, 0.45, sw).rotation.x = -0.75;
    mesh(new THREE.TorusGeometry(0.21 * k, 0.085 * k, 12, 24, Math.PI * 1.45), hand, sx * 0.08, -1.3, 0.6, sw).rotation.set(Math.PI / 2, 0, 2.3);
    if (R && c.plateR) mesh(boxG(0.5, 0.8, 0.16, 0.03), c.plateR, sx * 0.32, -0.45, 0, sw).rotation.z = 0.05;
    g.add(A); j[R ? 'armR' : 'armL'] = sw;
  }
  const hg = new THREE.Group(); hg.position.set(0, 3.66, 0); g.add(hg); j.head = hg;
  mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.2, 20), c.head, 0, 0, 0, hg);
  const pts = [[0, 0.08], [0.5, 0.08], [0.62, 0.16], [0.66, 0.3], [0.66, 0.98], [0.62, 1.12], [0.5, 1.2], [0, 1.2]].map(p => new THREE.Vector2(p[0], p[1]));
  mesh(new THREE.LatheGeometry(pts, 40, Math.PI), c.face || c.head, 0, 0, 0, hg);
  if (c.hair) {   // hair on top only, slicked straight back; the sides of the head are bare
    const hr = new THREE.SphereGeometry(0.7, 40, 20, 0, Math.PI * 2, 0, Math.PI * 0.5); hr.scale(0.8, 0.62, 1.04); hr.rotateX(-0.12);
    mesh(hr, c.hair, 0, 1.06, -0.05, hg);
  } else mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.16, 20), c.head, 0, 1.28, 0, hg);
  if (c.eyes) for (const sx of [-1, 1]) { const e = mesh(new THREE.SphereGeometry(0.09, 12, 10), c.eyes, sx * 0.24, 0.7, 0.63, hg, false); e.userData.eye = true; }
  g.userData.j = j; setPose(g, pose); return g;
}
export function setPose(g, p = {}) {
  const j = g.userData.j;
  j.legL.rotation.x = p.legL || 0; j.legR.rotation.x = p.legR || 0; j.armL.rotation.x = p.armL || 0; j.armR.rotation.x = p.armR || 0; j.head.rotation.y = p.head || 0;
}
export const POSES = {
  stand: {}, reach: { armR: -1.25, head: 0.25 }, look: { head: 0.6 }, lookL: { head: -0.6 }, shock: { armL: -2.4, armR: -2.4 }, think: { armR: -2.0, head: -0.2 },
  hold: { armR: -0.9, armL: -0.9 }, lie: {},
};
const poseOf = p => typeof p === 'string' ? (POSES[p] || {}) : (p || {});

// an actor: built once per beat, then moved by the beat's clock. a = the placement from the episode.
function actor(colours) {
  return {
    build(a, ep) {
      const c = colours(); for (const l of (a.loadout || (a.name === 'hero' ? ep.loadout : null) || [])) LOADOUT[l] && LOADOUT[l](c);
      if (a.opts && a.opts.eyes) c.eyes = new THREE.MeshBasicMaterial({ color: a.opts.eyes.color || '#ff3b2f' });
      const g = figure(c, poseOf(a.pose)); g.scale.setScalar(a.scale || 1); return g;
    },
    update(g, a, t, f) {
      const from = a.from || 0, until = a.until == null ? 1 : a.until, arrive = a.arrive || until;
      g.visible = t >= from && t <= until + 1e-6;
      const p = ease(clamp((t - from) / Math.max(1e-6, arrive - from))), to = a.to || {};
      const X = lerp(a.x || 0, to.x == null ? a.x || 0 : to.x, p), Z = lerp(a.z || 0, to.z == null ? a.z || 0 : to.z, p);
      g.position.set(X, (a.y || 0) + 0.4, Z); g.rotation.set(0, lerp(a.ry || 0, to.ry == null ? a.ry || 0 : to.ry, p), 0);
      const A = poseOf(a.pose), B = a.poseTo ? poseOf(a.poseTo) : A, w = a.poseAt || [from, arrive];
      const q = ease(clamp((t - w[0]) / Math.max(1e-6, w[1] - w[0]))), P = {};
      for (const k of ['legL', 'legR', 'armL', 'armR', 'head']) P[k] = lerp(A[k] || 0, B[k] || 0, q);
      if (a.anim === 'walk' && p > 0 && p < 1) { const s = Math.sin(f * Math.PI / 3) * 0.6; P.legL = s; P.legR = -s; P.armL = -s * 0.7; P.armR = s * 0.7; }   // six frames a stride
      if (a.anim === 'lie') { g.rotation.x = -Math.PI / 2 * (1 - q); g.position.y += 0.5 * (1 - q); }                                  // gets up off his back
      if (a.anim === 'shake') g.position.x += (f % 2 ? 0.05 : -0.05);
      setPose(g, P);
      const e = a.opts && a.opts.eyes; if (e) g.traverse(o => { if (o.userData.eye) o.visible = t >= (e.from || 0) && (!e.blink || f % 4 < 3); });
    },
  };
}
KIT.actor.hero = { desc: 'The hero: dark tee, dark legs, blonde hair on top only, teal brick in his chest. Wears the episode loadout.', ...actor(HERO) };
KIT.actor.statue = { desc: 'A fallen hero: the same figure in dead grey stone. opts.eyes {from, color, blink} opens its eyes.', ...actor(STONE) };
