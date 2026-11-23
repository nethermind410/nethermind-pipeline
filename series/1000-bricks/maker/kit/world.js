/* Rooms, props and effects. A room is KIT.set.<name>.build(group, opts): it adds its bricks and its lights to the group. */
import * as THREE from 'three';
import { KIT, abs, stone, brick, boxG, mesh, studG, rnd, clamp, ease, lerp } from './base.js';
import { figure, STONE } from './figure.js';

KIT.set.corridor = {
  desc: 'The statue corridor: dark purple brick walls, studded floor, wall torches, fallen heroes on plinths down both sides.',
  opts: { statues: 'how many background statues (default 6)', torch: 'torch strength 0..1 (default 1)' },
  build(g, o = {}) {
    const floorM = abs('#231a31', { roughness: 0.42 });
    mesh(new THREE.BoxGeometry(16, 0.4, 64), floorM, 0, 0.2, -18, g, false);
    const fs = new THREE.InstancedMesh(studG, floorM, 16 * 64), mx = new THREE.Matrix4(); let n = 0;
    for (let i = 0; i < 16; i++) for (let k = 0; k < 64; k++) { mx.setPosition(i - 7.5, 0.5, k - 49.5); fs.setMatrixAt(n++, mx); }
    fs.receiveShadow = true; g.add(fs);
    const cols = ['#33224a', '#2b1c40', '#241736', '#3c2957', '#1d132b'].map(c => abs(c, { roughness: 0.5 }));
    let q = 0;
    for (const sx of [-1, 1]) for (let row = 0; row < 17; row++) for (let z = -48 + (row % 2) * 2; z < 14; z += 4) {
      q++; const b = brick(1, 4, 1.2, cols[Math.floor(rnd(q) * cols.length)], row === 16 || rnd(q + 0.5) > 0.94);
      b.position.set(sx * (7.0 - (rnd(q + 0.2) > 0.9 ? 0.14 : 0)), 0.4 + row * 1.2, z); g.add(b);
    }
    const count = o.statues == null ? 6 : o.statues, pm = stone('#3d3549');
    for (let i = 0; i < count; i++) {
      const sx = i % 2 ? 1 : -1, z = -9 - i * 4.5, x = sx * 4.6;
      const p = brick(4, 4, 1.2, pm); p.position.set(x, 0.4, z); g.add(p);
      const st = figure(STONE(), { armR: i % 3 ? 0 : -0.9, armL: i % 2 ? -0.5 : 0, head: (rnd(i + 7) - 0.5) * 0.7 }); st.position.set(x, 1.6, z); st.rotation.y = -sx * 0.85; g.add(st);
    }
    const k = o.torch == null ? 1 : o.torch, lights = [];
    [[-6.3, 7.5, -4], [6.3, 7.5, -8], [-6.3, 7.5, -24], [6.3, 7.5, -28]].forEach(([x, y, z], i) => {
      const t = brick(1, 1, 1.2, abs('#3b2a1a'), false); t.position.set(x, y, z); g.add(t);
      const fl = mesh(new THREE.ConeGeometry(0.42, 1.3, 8), new THREE.MeshBasicMaterial({ color: '#ffb347' }), x, y + 1.85, z, g, false);
      const l = new THREE.PointLight('#ff9a3c', (i < 2 ? 150 : 90) * k, 48, 1.9); l.position.set(x - Math.sign(x) * 1.2, y + 1.6, z); g.add(l);
      lights.push({ l, base: l.intensity, fl });
    });
    g.add(new THREE.HemisphereLight('#7a5cc4', '#1a0d24', 0.55));
    const rim = new THREE.SpotLight('#8f7dff', 150, 44, 0.6, 0.7, 1.6); rim.position.set(-5, 10, -9); rim.target.position.set(0, 3, 2); g.add(rim, rim.target);
    const key = new THREE.SpotLight('#ffc98a', 120, 44, 0.6, 0.8, 1.6); key.position.set(5, 8, 12); key.target.position.set(0, 3, 0);
    key.castShadow = true; key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0012; g.add(key, key.target);
    // real brickfilms flicker a touch from frame to frame: the torches breathe, stepped, never smooth
    return { tick(f) { lights.forEach((t, i) => { const w = 0.9 + rnd(f * 3.1 + i) * 0.2; t.l.intensity = t.base * w; t.fl.scale.y = 0.85 + rnd(f * 1.7 + i) * 0.35; }); } };
  },
};

KIT.prop.plinth = { desc: 'A 4x4 stone plinth, one brick tall.', build() { return brick(4, 4, 1.2, stone('#3d3549')); } };
KIT.prop.armPlate = {
  desc: 'The loose stone arm plate. opts.glow 0..1 lights it up; opts.wobble makes it rock.',
  build(a) { const g = new THREE.Group(), p = brick(1, 2, 0.4, stone('#b4b8c2')); g.add(p);
    const l = new THREE.PointLight('#cfe0ff', 0, 7, 2); l.position.y = 0.8; g.add(l); g.userData.l = l; return g; },
  update(g, a, t, f) { const o = a.opts || {}; g.userData.l.intensity = (o.glow || 0) * 30 * (0.8 + rnd(f) * 0.4); if (o.wobble) g.rotation.z = (a.rz || 0) + (f % 4 < 2 ? 0.08 : -0.08); },
};

// bricks coming off him (sign -1) or flying onto him (sign +1). Each brick is a real 1x1 plate with its own arc.
KIT.fx.bricks = {
  desc: 'n 1x1 plates burst off the hero (sign -1) or fly onto him (sign 1) between from and until. at: [x, y, z].',
  build(a) {
    const g = new THREE.Group(), n = a.n || 12, cols = ['#30323c', '#2b2d36', '#f0c8a2', '#19e0c8', '#8b8e96'];
    for (let i = 0; i < n; i++) { const b = brick(1, 1, 0.4, a.sign > 0 ? stone('#b4b8c2') : abs(cols[i % 3 === 0 ? 2 : i % 2])); b.scale.setScalar(0.42); g.add(b); }
    return g;
  },
  update(g, a, t, f, beatSeconds) {
    const from = a.from || 0, until = a.until == null ? 1 : a.until, at = a.at || [0, 3, 0];
    g.children.forEach((b, i) => {
      const delay = i / g.children.length * 0.5, span = (until - from) * beatSeconds;
      let s = (t - from) * beatSeconds - delay * span; const life = span * 0.5;
      if (a.sign > 0) s = life - s;
      b.visible = s >= 0 && (a.sign > 0 ? s <= life : true);
      if (!b.visible) return;
      const ang = rnd(i + 1) * Math.PI * 2, sp = 2.5 + rnd(i + 9) * 3.5, vy = 5 + rnd(i + 5) * 4;
      const y = at[1] + vy * s - 11 * s * s, floor = 0.55;
      b.position.set(at[0] + Math.cos(ang) * sp * Math.min(s, 1.2), Math.max(floor, y), at[2] + Math.sin(ang) * sp * 0.6 * Math.min(s, 1.2) + 0.8);
      const spin = y > floor ? s * 9 : 0; b.rotation.set(spin * rnd(i + 3), spin * 0.5, spin * rnd(i + 4));
    });
  },
};
