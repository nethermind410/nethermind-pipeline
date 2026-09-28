#!/usr/bin/env python3
"""Offline, one-time preprocessing: turn a downloaded NIH 3D brain glTF (real anatomy) into the
small organs/brain_mesh.json asset that studio/neural.js builds its node network from directly,
instead of puffing organs/brain.json's 2D side-silhouette into two synthetic shells. This is why,
turned around, the home-page brain now reads as one whole shape from every angle.

Source (download this yourself before running — the ~13MB glTF is not committed to the repo):
  "Detailed Human Brain Model (3D)", NIH 3D (3d.nih.gov), entry 3DPX-021161, by Johnson J.
  Page:     https://3d.nih.gov/entries/3DPX-021161
  Licence:  CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/
  Attribution required: "Detailed Human Brain Model (3D)" by Johnson J, NIH 3D, CC BY 4.0.
  (Recorded again in THIRD_PARTY_NOTICES.md and in this file's own "source" block below.)
  Downloaded via NIH 3D's own file-download API (the entry's Download page -> select the "glb"
  input mesh -> Download), not scraped or mirrored from anywhere else.

Usage:
  python3 scripts/build_brain_mesh.py /path/to/brain_human.glb
  (requires: numpy, scipy, trimesh — dev-only, not a runtime dependency of the app)

Coordinate convention this targets (the same box organs/brain.json's side-profile silhouette
used, so existing region/label/anchor mapping in studio/neural.js still lands on sensible lobes):
  image_x in ~[0.16, 0.89]  (small = anterior/frontal, large = posterior/occipital+cerebellum)
  image_y in ~[0.18, 0.76]  (small = superior/top,      large = inferior/bottom)
  z        the depth the renderer turns around (real measured left-right anatomy, rescaled to
                                                 roughly the old synthetic shells' +/-0.15..0.3)
  side     sign(z)
  g        region id from organs/brain.json's own region() (0 cerebrum, 1 temporal lobe, 2 cerebellum)
  rim      1 for points on the silhouette (top/bottom/front/back outline), else 0

The source mesh's own axes (inspected empirically from its vertex bounds / point-cloud plots):
  mesh X  ~[-66, 67]   left <-> right                        -> our z (depth)
  mesh Y  ~[-107, 74]  posterior(-) <-> anterior(+)           -> our image_x (inverted + scaled)
  mesh Z  ~[-47, 94]   inferior(-) <-> superior(+)            -> our image_y (inverted + scaled)
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent.parent
BRAIN_JSON = HERE / "organs" / "brain.json"
OUT = HERE / "organs" / "brain_mesh.json"

TOTAL_POINTS = 3000
MIDLINE_POINTS = 260          # forced extra samples near the interhemispheric fissure
RNG_SEED = 20260928


def main(src_path):
    rng = np.random.default_rng(RNG_SEED)

    # ---------- 1. load + merge the glTF's sub-meshes into one point set ----------
    scene = trimesh.load(src_path)
    geoms = list(scene.geometry.values()) if hasattr(scene, "geometry") else [scene]
    mesh = trimesh.util.concatenate(geoms)
    mesh.merge_vertices()
    V = mesh.vertices.view(np.ndarray)
    print(f"merged mesh: {len(V)} vertices, {len(mesh.faces)} faces")

    # ---------- 2. curvature-ish weight per vertex (fold detector: a bigger dihedral angle
    #               between adjacent faces means a gyrus crest or sulcus fundus) ----------
    edges = mesh.face_adjacency_edges
    ang = mesh.face_adjacency_angles
    vscore = np.zeros(len(V))
    vcount = np.zeros(len(V))
    np.add.at(vscore, edges[:, 0], ang)
    np.add.at(vscore, edges[:, 1], ang)
    np.add.at(vcount, edges[:, 0], 1)
    np.add.at(vcount, edges[:, 1], 1)
    vcount[vcount == 0] = 1
    curvature = vscore / vcount
    curvature = curvature / (curvature.max() or 1)
    weight = 0.08 + curvature ** 1.6        # a floor so flat areas still get some samples

    # ---------- 3. weighted sample, plus a forced midline band so the longitudinal fissure
    #               between hemispheres reads clearly ----------
    p = weight / weight.sum()
    n_main = TOTAL_POINTS - MIDLINE_POINTS
    idx_main = rng.choice(len(V), size=n_main, replace=False, p=p)

    x_all, z_all = V[:, 0], V[:, 2]
    mid_band = 4.0                                   # +/- mm around the sagittal plane
    mid_candidates = np.where((np.abs(x_all) < mid_band) & (z_all > np.percentile(z_all, 40)))[0]
    idx_mid = rng.choice(mid_candidates, size=MIDLINE_POINTS, replace=len(mid_candidates) < MIDLINE_POINTS)

    idx = np.concatenate([idx_main, idx_mid])
    pts = V[idx]
    print(f"sampled {len(pts)} points ({len(idx_main)} weighted + {len(idx_mid)} midline)")

    # ---------- 4. transform into the organ's 2D box + a rescaled depth ----------
    mesh_x, mesh_y, mesh_z = pts[:, 0], pts[:, 1], pts[:, 2]
    y_lo, y_hi = np.percentile(mesh_y, [0.3, 99.7])
    z_lo, z_hi = np.percentile(mesh_z, [0.3, 99.7])
    _, x_hi = np.percentile(np.abs(mesh_x), [0.3, 99.7])

    IMG_X0, IMG_X1 = 0.175, 0.87     # frontal .. occipital/cerebellum, matches brain.json's polys
    IMG_Y0, IMG_Y1 = 0.19, 0.745     # top (motor cortex) .. bottom (cerebellum/temporal)
    Z_SCALE = 0.30

    image_x = np.clip(IMG_X0 + (y_hi - mesh_y) / (y_hi - y_lo) * (IMG_X1 - IMG_X0), 0.05, 0.97)
    image_y = np.clip(IMG_Y0 + (z_hi - mesh_z) / (z_hi - z_lo) * (IMG_Y1 - IMG_Y0), 0.05, 0.97)
    depth_z = np.clip(mesh_x / x_hi, -1, 1) * Z_SCALE

    # ---------- 5. region id via organs/brain.json's own region() (ported), whole=True so every
    #               point lands on a real part even inside the lateral-fissure gap band ----------
    def smooth(poly, steps=10):
        out, n = [], len(poly)
        for i in range(n):
            p0, p1, p2, p3 = poly[(i - 1) % n], poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
            for k in range(steps):
                t = k / steps
                t2, t3 = t * t, t * t * t
                out.append([0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t
                                    + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)])
        return out

    def in_poly(poly, x, y):
        c, j = False, len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]
            xj, yj = poly[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                c = not c
            j = i
        return c

    brain = json.loads(BRAIN_JSON.read_text())
    parts = [{**part, "poly": smooth(part["poly"])} for part in brain["parts"]]

    def curve(s, v):
        return s["curve"][0] + s["curve"][1] * (v - s["curve"][3]) + s["curve"][2] * (v - s["curve"][3]) ** 2

    def region(x, y):
        for part in parts:
            if not in_poly(part["poly"], x, y):
                continue
            for s in part.get("splits", []):
                u, v = (y, x) if s.get("axis") == "x" else (x, y)
                sv = curve(s, u)
                if s.get("id") is not None and s.get("xmin", -9) < u < s.get("xmax", 9) and (v < sv if s.get("above") else v > sv):
                    return s["id"]
            return part["id"]
        return -1

    def nearest_part(x, y):
        best, bd = parts[0]["id"], 1e9
        for part in parts:
            cx = sum(pp[0] for pp in part["poly"]) / len(part["poly"])
            cy = sum(pp[1] for pp in part["poly"]) / len(part["poly"])
            d = (cx - x) ** 2 + (cy - y) ** 2
            if d < bd:
                bd, best = d, part["id"]
        return best

    g = np.array([region(float(x), float(y)) for x, y in zip(image_x, image_y)])
    g = np.array([gi if gi >= 0 else nearest_part(float(image_x[i]), float(image_y[i])) for i, gi in enumerate(g)])
    side = np.where(depth_z >= 0, 1, -1)

    # ---------- 6. rim (silhouette) flag: per ant/post column, the top-most & bottom-most
    #              points; per sup/inf row, the front-most & back-most. Together they trace the
    #              profile's outline, the way a side photo's silhouette would. ----------
    rim = np.zeros(len(pts), dtype=bool)
    COLS = ROWS = 90
    col_bins = np.floor((image_x - image_x.min()) / (image_x.max() - image_x.min() + 1e-9) * COLS).astype(int)
    row_bins = np.floor((image_y - image_y.min()) / (image_y.max() - image_y.min() + 1e-9) * ROWS).astype(int)
    for bins, coords, other in ((col_bins, image_y, COLS), (row_bins, image_x, ROWS)):
        for b in range(other + 1):
            sel = np.where(bins == b)[0]
            if len(sel) == 0:
                continue
            vals = coords[sel]
            span = vals.max() - vals.min() or 1e-6
            rim[sel[vals <= vals.min() + 0.05 * span]] = True
            rim[sel[vals >= vals.max() - 0.05 * span]] = True

    print(f"rim points: {int(rim.sum())} / {len(pts)}")
    print("region counts:", {int(k): int(v) for k, v in zip(*np.unique(g, return_counts=True))})
    print("side counts:", {int(k): int(v) for k, v in zip(*np.unique(side, return_counts=True))})

    # ---------- 7. write the small asset ----------
    rows = [[round(float(image_x[i]), 4), round(float(image_y[i]), 4), round(float(depth_z[i]), 4),
             int(g[i]), int(side[i]), int(bool(rim[i]))] for i in range(len(pts))]
    out = {
        "source": {
            "title": "Detailed Human Brain Model (3D)", "id": "3DPX-021161", "author": "Johnson J",
            "url": "https://3d.nih.gov/entries/3DPX-021161", "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "note": "Decimated to a ~3000-point weighted surface sample; fields per point are [x, y, z, g, side, rim].",
        },
        "fields": ["x", "y", "z", "g", "side", "rim"],
        "points": rows,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(rows)} points)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_brain_mesh.py /path/to/brain_human.glb")
    main(sys.argv[1])
