/* Shared brick parts. Units: 1 = one stud across. A brick is 1.2 tall, a plate 0.4.
 * Everything here depends only on its arguments and rnd(n): the same call draws the same thing, every time. */
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export const KIT = { set: {}, actor: {}, prop: {}, fx: {} };
export const rnd = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
export const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
export const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
export const lerp = (a, b, t) => a + (b - a) * t;

const MATS = {};
// shiny moulded plastic
export function abs(color, o = {}) {
  const k = color + JSON.stringify(Object.keys(o).length ? Object.entries(o).filter(([, v]) => typeof v !== 'object') : '');
  if (!o.map && !o.bumpMap && MATS[k]) return MATS[k];
  const m = new THREE.MeshPhysicalMaterial({ color, roughness: 0.3, clearcoat: 0.55, clearcoatRoughness: 0.3, ...o });
  if (!o.map && !o.bumpMap) MATS[k] = m; return m;
}
// dead grey stone: what a hero turns into at zero
export function stone(color = '#8b8e96') { return MATS['s' + color] || (MATS['s' + color] = new THREE.MeshStandardMaterial({ color, roughness: 0.9 })); }

export const studG = new THREE.CylinderGeometry(0.3, 0.3, 0.2, 18);
const BOX = {};
export function boxG(w, h, d, r = 0.035) { const k = [w, h, d, r].join(); return BOX[k] || (BOX[k] = new RoundedBoxGeometry(w, h, d, 2, r)); }
export function mesh(g, mat, x, y, z, parent, shadow = true) {
  const o = new THREE.Mesh(g, mat); o.position.set(x, y, z); o.castShadow = shadow; o.receiveShadow = true; if (parent) parent.add(o); return o;
}
// one brick, w studs wide (x), d deep (z), h tall, sitting on y = 0, studs on top
export function brick(w, d, h, mat, studs = true) {
  const g = new THREE.Group(); mesh(boxG(w - 0.02, h - 0.02, d - 0.02), mat, 0, h / 2, 0, g);
  if (studs) for (let i = 0; i < w; i++) for (let j = 0; j < d; j++) mesh(studG, mat, i - (w - 1) / 2, h + 0.09, j - (d - 1) / 2, g);
  return g;
}
