"""
make_short.py — config-driven YouTube Shorts factory.

    python3 make_short.py config.json [--preview] [--no-tts]

One JSON config in, one finished MP4 + SRT out. Handles narration (Kokoro
TTS, free/self-hosted, see tts_kokoro.py), Ken Burns stills, video
clips, procedural iceberg charts, kinetic captions, hero number overlays, a
synthesized score, loudness normalisation and subtitles.

Visual types (segment "vis"):
  {"t":"kb",  "src":"x.jpg", "z0":1.3,"z1":1.1,"cx":.5,"cy":.45}   Ken Burns still
  {"t":"vid", "src":"x.mp4", "ss":0, "fit":"square"|"cover"}        video clip
  {"t":"ice", "tier":2}                                            iceberg descent
"""
import json, os, sys, math, re, subprocess, time, tempfile, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 48000
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "assets")
CFG = json.load(open(sys.argv[1]))
PREVIEW = "--preview" in sys.argv
VID = CFG["id"]
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
TTS_DIR = os.path.join(HERE, "tts", VID); os.makedirs(TTS_DIR, exist_ok=True)

PAL = CFG.get("palette", {})
ACCENT = tuple(PAL.get("accent", [200, 120, 255]))
ACCENT2 = tuple(PAL.get("accent2", [255, 140, 40]))
WHITE = (245, 245, 245)
COL = {"a": ACCENT, "a2": ACCENT2, "w": WHITE}
F_CAP = os.path.join(A, "Anton-Regular.ttf")
F_SM = os.path.join(A, "BebasNeue-Regular.ttf")

# ---------------------------------------------------------------- TTS
def tts_all():
    import tts_kokoro as tts_elevenlabs  # switched from ElevenLabs -> free, self-hosted Kokoro (am_liam), 2026-09-21
    timing = {}
    for s in CFG["segments"]:
        if not s.get("text"):
            timing[s["id"]] = []
            continue
        mp3 = os.path.join(TTS_DIR, s["id"] + ".mp3")
        jsn = os.path.join(TTS_DIR, s["id"] + ".json")
        if os.path.exists(mp3) and os.path.exists(jsn) and "--no-tts" not in sys.argv:
            timing[s["id"]] = json.load(open(jsn))
        else:
            timing[s["id"]] = tts_elevenlabs.synthesize(s["text"], mp3, CFG.get("voice_id"))
            json.dump(timing[s["id"]], open(jsn, "w"))
    return timing

TIMING = tts_all()

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                          "format=duration", "-of", "csv=p=0", p]).decode().strip())

# ---------------------------------------------------------------- timeline
segs, t = [], 0.0
for s in CFG["segments"]:
    d = (dur(os.path.join(TTS_DIR, s["id"] + ".mp3")) + 0.05) if s.get("text") else s["dur"]
    segs.append({**s, "start": t, "end": t + d, "dur": d, "words": TIMING[s["id"]]})
    t += d + s.get("gap", 0.15)
TOTAL = t + 0.25
NF = int(round(TOTAL * FPS))
print(f"[{VID}] {TOTAL:.2f}s / {NF}f")
for s in segs:
    print(f"   {s['id']:6s} {s['start']:6.2f}-{s['end']:6.2f} {s['vis']['t']}")

# ---------------------------------------------------------------- assets
_im, _vf = {}, {}
def img(name):
    if name not in _im:
        im = Image.open(os.path.join(A, name)).convert("RGB")
        if im.height < 1700:
            sc = 1700 / im.height
            im = im.resize((int(im.width * sc), 1700), Image.LANCZOS)
        _im[name] = im
    return _im[name]

def vframes(src, ss=0.0, length=8.0):
    key = (src, ss)
    if key not in _vf:
        d = os.path.join(A, f".fr_{os.path.splitext(src)[0]}_{int(ss*10)}")
        if not os.path.isdir(d):
            os.makedirs(d)
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(ss), "-i", os.path.join(A, src),
                                   "-t", str(length), "-r", str(FPS), "-vf", f"scale={W}:-2",
                                   os.path.join(d, "f%04d.jpg")])
        _vf[key] = (d, sorted(os.listdir(d)))
    return _vf[key]

def fit_cover(im, zoom=1.0, cx=.5, cy=.5):
    iw, ih = im.size
    base = min(iw / W, ih / H)
    cw, chh = W * base / zoom, H * base / zoom
    x0 = min(max(cx * iw - cw / 2, 0), iw - cw)
    y0 = min(max(cy * ih - chh / 2, 0), ih - chh)
    return im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + chh))).resize((W, H), Image.BILINEAR)

def ease(p): return p * p * (3 - 2 * p)

Y, X = np.mgrid[0:H, 0:W]
_r = np.sqrt(((X - W / 2) / (W / 2)) ** 2 + ((Y - H / 2) / (H / 2)) ** 2)
VIG = np.clip(1 - .55 * np.clip(_r - .45, 0, 1.2), .3, 1)[..., None].astype(np.float32)

# ---------------------------------------------------------------- iceberg canvas
ICE_H = 0
ICE = None
def build_iceberg():
    """Tall procedural iceberg: sky, waterline, tapering berg, depth bands, marine snow."""
    global ICE, ICE_H
    tiers = CFG["iceberg"]["tiers"]
    band = 1250
    ICE_H = 700 + band * len(tiers) + 300
    im = Image.new("RGB", (W, ICE_H), (4, 8, 18))
    d = ImageDraw.Draw(im)
    water_y = 620
    for y in range(water_y):
        k = y / water_y
        d.line([(0, y), (W, y)], fill=(int(6 + 12 * k), int(10 + 18 * k), int(24 + 30 * k)))
    for y in range(water_y, ICE_H):
        k = (y - water_y) / (ICE_H - water_y)
        kk = k ** 0.42                      # darken fast
        d.line([(0, y), (W, y)], fill=(int(12 * (1 - kk)), int(58 * (1 - kk) + 2), int(104 * (1 - kk) + 4)))
    rng = np.random.default_rng(abs(hash(CFG["id"])) % 9999)
    top_w, max_w = 120, W * 0.29            # keep water visible either side
    pts_l, pts_r, n = [], [], 46
    for i in range(n + 1):
        k = i / n
        y = water_y - 165 + k * (ICE_H - water_y + 100)
        base = top_w + (max_w - top_w) * math.sin(min(k * 1.7, 1) * math.pi / 2)
        base *= 1 - 0.62 * max(0, (k - 0.5) / 0.5) ** 1.5
        j = rng.normal(0, 20) if i not in (0, n) else 0
        pts_l.append((W / 2 - base + j, y))
        pts_r.append((W / 2 + base + (rng.normal(0, 20) if i not in (0, n) else 0), y))
    poly = pts_l + pts_r[::-1]
    bergcol = tuple(int(206 * .78 + ACCENT[k] * .22) for k in range(3))
    d.polygon(poly, fill=bergcol)
    berg = Image.new("L", (W, ICE_H), 0)
    ImageDraw.Draw(berg).polygon(poly, fill=255)
    arr = np.asarray(im).astype(np.float32)
    m = (np.asarray(berg).astype(np.float32) / 255)[..., None]
    depth = np.clip((np.arange(ICE_H) - water_y) / (ICE_H - water_y), 0, 1)[:, None, None]
    dd = depth ** 0.55
    tint = np.array([ACCENT[0] / 900 + .10, ACCENT[1] / 620 + .12, ACCENT[2] / 430 + .12])
    shaded = arr * (1 - m) + m * (arr * (1 - dd * 0.97) + 255 * tint * dd * 0.26)
    im = Image.fromarray(np.clip(shaded, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    # marine snow
    for _ in range(1400):
        y = rng.uniform(water_y, ICE_H)
        k = 1 - ((y - water_y) / (ICE_H - water_y)) ** 0.5
        r = rng.uniform(1, 2.6)
        g = int(190 * max(k, 0.18))
        x = rng.uniform(0, W)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(g, g, int(g * 1.1)))
    d.line([(0, water_y), (W, water_y)], fill=(160, 210, 240), width=4)
    fs = ImageFont.truetype(F_SM, 44)
    for i, tr in enumerate(tiers):
        y = 700 + band * i
        for x in range(0, W, 34):
            d.line([(x, y), (x + 16, y)], fill=(120, 150, 180), width=2)
        d.text((34, y + 12), tr["depth"], font=fs, fill=(140, 168, 196))
    return im

def ice_window(tier_i, p):
    """Camera window over the iceberg canvas for a tier (slow continuous descent)."""
    if ICE is None: build_iceberg()
    band = 1250
    y0 = 700 + band * tier_i - 560
    y0 += 210 * ease(p)
    y0 = max(0, min(y0, ICE_H - H))
    return ICE.crop((0, int(y0), W, int(y0) + H))

if any(s["vis"]["t"] == "ice" for s in CFG["segments"]):
    ICE = build_iceberg()

# ---------------------------------------------------------------- background
_blur = {}
def blur_bg(fr, key):
    if key not in _blur:
        sm = fr.resize((96, 96)).resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(6))
        _blur[key] = Image.eval(sm.resize((W, H), Image.BILINEAR), lambda c: int(c * .5))
    return _blur[key].copy()

def background(seg, p, tl):
    v = seg["vis"]
    if v["t"] == "kb":
        z = v.get("z0", 1.1) + (v.get("z1", 1.25) - v.get("z0", 1.1)) * ease(p)
        return fit_cover(img(v["src"]), z, v.get("cx", .5), v.get("cy", .5))
    if v["t"] == "vid":
        d, files = vframes(v["src"], v.get("ss", 0), seg["dur"] + .4)
        fr = Image.open(os.path.join(d, files[min(int(tl * FPS), len(files) - 1)])).convert("RGB")
        if v.get("fit") == "square" or fr.width >= fr.height:
            bg = blur_bg(fr, v["src"])
            side = W if v.get("fit") == "square" else W
            fr2 = fr.resize((side, int(side * fr.height / fr.width)))
            bg.paste(fr2, (0, (H - fr2.height) // 2 - 70))
            return bg
        return fit_cover(fr, 1.05)
    if v["t"] == "ice":
        return ice_window(v["tier"], p)
    return Image.new("RGB", (W, H), (0, 0, 0))

# ---------------------------------------------------------------- text
_f = {}
def font(p, s):
    if (p, s) not in _f: _f[(p, s)] = ImageFont.truetype(p, s)
    return _f[(p, s)]

def outline(d, xy, txt, f, fill, ow=7):
    d.text(xy, txt, font=f, fill=fill, stroke_width=ow, stroke_fill=(0, 0, 0))

def centre(d, txt, f, y, fill, ow=7):
    bb = d.textbbox((0, 0), txt, font=f)
    outline(d, ((W - (bb[2] - bb[0])) / 2 - bb[0], y), txt, f, fill, ow)
    return bb[3] - bb[1]

def align_words(seg):
    toks, out, i = seg["text"].split(), [], 0
    for w in seg["words"]:
        n = len(w["word"].split())
        out.append({"word": " ".join(toks[i:i + n]).upper(), "start": w["start"], "end": w["end"]})
        i += n
    return out

def chunks(ws, maxn=3):
    out, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= maxn or re.search(r"[.?!,]$", w["word"]):
            out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def draw_hook(d):
    f = font(F_CAP, CFG["hook"].get("size", 150))
    y = CFG["hook"].get("y", 620)
    for txt, c in CFG["hook"]["lines"]:
        h = centre(d, txt, f, y, COL[c], 8)
        y += CFG["hook"].get("size", 150) * 1.17

def draw_hero(d, hero, sc):
    lines = hero["lines"]
    size = int(hero.get("size", 150 if len(lines) > 1 else 170) * sc)
    f = font(F_CAP, size)
    y = hero.get("y", 380)
    for ln in lines:
        h = centre(d, ln, f, y, COL[hero.get("col", "a")], 8)
        y += size * 1.12

def draw_tier(d, seg, tl):
    """Iceberg tier label above, fact caption below."""
    tr = CFG["iceberg"]["tiers"][seg["vis"]["tier"]]
    p = min(tl / .22, 1)
    f = font(F_CAP, int(96 * (.86 + .14 * ease(p))))
    centre(d, tr["label"].upper(), f, 300, COL[tr.get("col", "a")], 8)
    fs = font(F_SM, 62)
    centre(d, tr["depth"], fs, 300 + 118, (190, 210, 230), 5)

def draw_caps(d, seg, tl):
    if seg["vis"]["t"] == "ice":
        draw_tier(d, seg, tl)
    if seg.get("hook"):
        draw_hook(d); return
    if not seg.get("text"):
        if seg.get("hero"):
            draw_hero(d, seg["hero"], .75 + .25 * ease(min(tl / .25, 1)))
            if seg.get("sub"):
                centre(d, seg["sub"], font(F_SM, 66), 1400, WHITE, 5)
        return
    ws = align_words(seg)
    if not ws: return
    cur = None
    for c in chunks(ws):
        if c[0]["start"] - .05 <= tl: cur = c
    if seg.get("hero") and tl >= ws[min(seg["hero"]["at"], len(ws) - 1)]["start"] - .05:
        a = min((tl - ws[min(seg["hero"]["at"], len(ws) - 1)]["start"] + .05) / .2, 1)
        draw_hero(d, seg["hero"], .82 + .18 * ease(a))
    if cur is None: return
    shown = [w for w in cur if w["start"] - .05 <= tl]
    if not shown: return
    f = font(F_CAP, 116)
    parts = [w["word"] for w in shown]
    wds = [d.textbbox((0, 0), p_, font=f)[2] for p_ in parts]
    sp, lines, cl, cw = 32, [], [], 0
    if sum(wds) + sp * (len(wds) - 1) > W - 110:
        for p_, wd in zip(parts, wds):
            if cl and cw + sp + wd > W - 110:
                lines.append(cl); cl, cw = [], 0
            cl.append((p_, wd)); cw += wd + (sp if len(cl) > 1 else 0)
        lines.append(cl)
    else:
        lines = [list(zip(parts, wds))]
    y = CFG.get("cap_y", 1120) - 70 * (len(lines) - 1)
    last = shown[-1]["word"]
    for line in lines:
        lw = sum(w for _, w in line) + sp * (len(line) - 1)
        x = (W - lw) / 2
        for p_, wd in line:
            if p_ == last:
                age = tl - shown[-1]["start"] + .05
                s = 1 + .12 * (1 - min(age / .12, 1))
                fb = font(F_CAP, int(116 * s))
                bb = d.textbbox((0, 0), p_, font=fb)
                outline(d, (x - (bb[2] - wd) / 2, y - (bb[3] - 116) / 2), p_, fb, ACCENT)
            else:
                outline(d, (x, y), p_, f, WHITE)
            x += wd + sp
        y += 138

def draw_end(d, seg, tl):
    e = CFG.get("end")
    if not e or seg["id"] != segs[-1]["id"] or tl < e.get("at", 1.6): return
    f = font(F_SM, 62)
    for i, txt in enumerate(e["lines"]):
        centre(d, txt, f, 1370 + i * 70, COL["a2"] if i else WHITE, 5)

def draw_credit(d):
    f = font(F_SM, 34)
    bb = d.textbbox((0, 0), CFG["credit"], font=f)
    d.text(((W - bb[2]) / 2, 215), CFG["credit"], font=f, fill=(150, 150, 150))

# ---------------------------------------------------------------- video
TMP = os.path.join(tempfile.gettempdir(), "shortfactory_" + VID)
os.makedirs(TMP, exist_ok=True)
vpath = os.path.join(TMP, VID + "_v.mp4")
FR = os.path.join(TMP, "frames")

# Invalidate the frame cache if the config or any referenced image changed
# since the last run — otherwise a --deadline resume (see below) would also
# silently resume with stale frames after an edit, reusing old art under new
# narration/captions.
def _cache_key():
    import hashlib
    h = hashlib.sha256(open(sys.argv[1], "rb").read())
    for s in CFG["segments"]:
        src = s["vis"].get("src")
        if src:
            p = os.path.join(A, src)
            if os.path.exists(p):
                st = os.stat(p)
                h.update(f"{src}:{st.st_mtime_ns}:{st.st_size}".encode())
    return h.hexdigest()

_key_path = os.path.join(TMP, ".cachekey")
_key = _cache_key()
if os.path.exists(_key_path) and open(_key_path).read().strip() != _key:
    shutil.rmtree(FR, ignore_errors=True)
    if os.path.exists(vpath):
        os.remove(vpath)
open(_key_path, "w").write(_key)

# --deadline N: render as many frames as fit in N seconds, then exit 2 (incomplete).
# Frames are cached as JPEGs, so re-running resumes where it stopped. Lets slow
# machines build a video across several bounded runs.
DEADLINE = None
for _i, _a in enumerate(sys.argv):
    if _a == "--deadline" and _i + 1 < len(sys.argv):
        DEADLINE = time.time() + float(sys.argv[_i + 1])
if not PREVIEW:
    os.makedirs(FR, exist_ok=True)

def render_frame(fi):
    tt = fi / FPS
    seg = None
    for s_ in segs:
        if s_["start"] <= tt < s_["end"] + s_.get("gap", .15): seg = s_
    if seg is None:
        frame = Image.new("RGB", (W, H), (0, 0, 0))
    else:
        tl = tt - seg["start"]
        frame = Image.fromarray(np.clip(np.asarray(background(seg, min(tl / seg["dur"], 1), tl))
                                        .astype(np.float32) * VIG, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(frame)
        draw_caps(d, seg, tl); draw_end(d, seg, tl); draw_credit(d)
        if tl < 2 / FPS and seg is not segs[0]:
            frame = Image.eval(frame, lambda c: min(255, int(c * 1.3)))
    if tt > TOTAL - .15:
        k = max(0, (TOTAL - tt) / .15)
        frame = Image.eval(frame, lambda c: int(c * k))
    return frame

if PREVIEW:
    for fi in range(0, NF, 15):
        render_frame(fi).save(os.path.join(OUT, f"pv_{VID}_{fi:05d}.jpg"), quality=85)
    print("  preview frames written")
    sys.exit(0)

done = 0
for fi in range(NF):
    p = os.path.join(FR, f"{fi:05d}.jpg")
    if os.path.exists(p):
        done += 1
        continue
    render_frame(fi).save(p, quality=93)
    done += 1
    if DEADLINE and time.time() > DEADLINE:
        print(f"  paused at {done}/{NF} frames — run again to resume")
        sys.exit(2)

subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
                       "-i", os.path.join(FR, "%05d.jpg"), "-c:v", "libx264", "-preset", "medium",
                       "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", vpath])
print("  video ok")

# ---------------------------------------------------------------- srt
def build_srt():
    def fmt(x):
        return f"{int(x//3600):02d}:{int(x%3600//60):02d}:{x%60:06.3f}".replace(".", ",")
    cards = []
    for s in segs:
        if not s.get("text"):
            if s.get("srt"): cards.append((s["start"], s["end"], s["srt"]))
            continue
        al = align_words(s)
        toks = s["text"].split()
        # re-derive original casing
        i, groups, cur = 0, [], []
        for k, w in enumerate(s["words"]):
            n = len(w["word"].split())
            txt = " ".join(toks[i:i + n]); i += n
            cur.append((txt, al[k]["start"], al[k]["end"]))
            if re.search(r"[.?!]$", txt) or len(cur) >= 9:
                groups.append(cur); cur = []
        if cur: groups.append(cur)
        for g in groups:
            cards.append((s["start"] + g[0][1], s["start"] + g[-1][2] + .15, " ".join(x[0] for x in g)))
    out = []
    for k, (a, b, tx) in enumerate(cards):
        if k + 1 < len(cards): b = min(b, cards[k + 1][0] - .02)
        out.append(f"{k+1}\n{fmt(a)} --> {fmt(b)}\n{tx}\n")
    p = os.path.join(OUT, VID + ".srt")
    open(p, "w").write("\n".join(out))
    return p

if not PREVIEW:
    import score
    mix = score.build_audio(segs, TOTAL, TMP, VID, A, TTS_DIR, CFG.get("score", "space") == "deep", SR)
    final = os.path.join(OUT, CFG.get("file", VID) + ".mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", vpath, "-i", mix, "-c:v", "copy",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", final])
    srt = build_srt()
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"  DONE {final}  ({dur(final):.2f}s)  + {os.path.basename(srt)}")
else:
    print("  preview frames written")
