#!/usr/bin/env python3
"""Short assembler: builds a 1080x1920 Short from a shot list. RUNS ON GITHUB ACTIONS, never in a Claude session.

  python3 tools/short_assemble.py <folder> <out.mp4>

Reads <folder>/short.json. Every shot has a start and end time on the voice track and either a still ("img") or a
video clip ("clip", with "clip_start" in seconds). Stills always move: each one pans and pushes between two focus
points, so no picture is ever held still. Clips are cut to the shot, cropped to fill the frame and muted.

On top it lays, in one fixed style: the opening question ("hook"), a big stamp for a shot that has one ("stamp"),
and captions made from the shot's spoken words ("say"), three words at a time, timed across the shot's speech window
("speech": [start, end]). The voice is the audio; "music" is mixed quietly under it and dipped while he speaks.

No generation and no network. Prints one JSON line: {"ok":true,"seconds":S,"shots":N,"out":"..."}"""
import json, os, re, subprocess, sys, tempfile

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
YELLOW, WHITE, BLACK = (255, 212, 0), (255, 255, 255), (0, 0, 0)
try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FF = 'ffmpeg'


def ease(p):
    return p * p * (3 - 2 * p)


def label(font, text, px, fill, stroke, max_w=W - 120, box=False):
    """One block of centred text, wrapped to max_w, as an RGBA image."""
    f = ImageFont.truetype(font, px); words = text.split(); lines = []; cur = ''
    probe = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    for w in words:
        t = (cur + ' ' + w).strip()
        if probe.textlength(t, font=f) <= max_w or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    lh = int(px * 1.12); pad = stroke + 28
    tw = int(max(probe.textlength(l, font=f) for l in lines)) + pad * 2; th = lh * len(lines) + pad * 2
    im = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if box: d.rounded_rectangle((0, 0, tw - 1, th - 1), radius=28, fill=(0, 0, 0, 215))
    for i, l in enumerate(lines):
        d.text((tw // 2, pad + i * lh + lh // 2), l, font=f, fill=fill, anchor='mm', stroke_width=stroke, stroke_fill=BLACK)
    return im


def chunks(say, a, b, n=3):
    """Split the spoken line into caption chunks of up to n words, timed by letter count across [a, b]."""
    words = say.split(); groups = [' '.join(words[i:i + n]) for i in range(0, len(words), n)]
    total = sum(len(g) for g in groups) or 1; out = []; t = a
    for g in groups:
        d = (b - a) * len(g) / total; out.append((t, t + d, re.sub(r'["“”]', '', g).upper())); t += d
    return out


def still_frame(im, s, p):
    """The 1080x1920 view of a still at progress p (0..1) through its shot."""
    iw, ih = im.size; e = ease(p)
    fx = s['x'][0] + (s['x'][1] - s['x'][0]) * e; fy = s.get('y', [0.5, 0.5]); fy = fy[0] + (fy[1] - fy[0]) * e
    z = s.get('zoom', [1.0, 1.08]); z = z[0] + (z[1] - z[0]) * e
    k = 1 / (max(W / iw, H / ih) * z); ww, wh = W * k, H * k
    x0 = min(max(fx * iw - ww / 2, 0), iw - ww); y0 = min(max(fy * ih - wh / 2, 0), ih - wh)
    return im.transform((W, H), Image.AFFINE, (k, 0, x0, 0, k, y0), resample=Image.BICUBIC)


def clip_frames(root, s, fps, tmp, i):
    """Cut a clip to its shot, fill the frame around its focus point, and return the frame files in order."""
    d = s['end'] - s['start']; out = os.path.join(tmp, f'clip{i}'); os.makedirs(out)
    fx = s.get('x', [0.5, 0.5])[0]
    vf = f"fps={fps},scale=-2:{H}:flags=lanczos,crop={W}:{H}:(iw-{W})*{fx}:0"
    subprocess.check_call([FF, '-y', '-loglevel', 'error', '-ss', str(s.get('clip_start', 0)), '-t', f'{d + 0.2:.3f}', '-i', os.path.join(root, s['clip']),
                           '-an', '-vf', vf, '-q:v', '2', os.path.join(out, '%05d.jpg')])
    return sorted(os.path.join(out, f) for f in os.listdir(out))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if len(a) != 2: raise SystemExit(__doc__)
    root, out = a; sp = json.load(open(os.path.join(root, 'short.json'))); shots = sp['shots']; fps = sp.get('fps', 30)
    font = os.path.join(root, sp.get('font', '../fonts/Anton-Regular.ttf')); total = shots[-1]['end']
    for i, s in enumerate(shots):
        if i and abs(s['start'] - shots[i - 1]['end']) > 1e-6: raise SystemExit(f'shot {i + 1} does not start where shot {i} ends')
        if not (s.get('img') or s.get('clip')): raise SystemExit(f'shot {i + 1} has no picture')
    seen = [s.get('img') for s in shots if s.get('img')]
    if len(seen) != len(set(seen)): raise SystemExit('a picture is used twice')
    tmp = tempfile.mkdtemp(); caps = []
    for s in shots:
        sa, sb = s.get('speech', [s['start'], s['end']])
        caps += [(t0, t1, label(font, txt, 104, WHITE, 10)) for t0, t1, txt in chunks(s.get('say', ''), sa, sb)] if s.get('say') else []
    hook = label(font, sp['hook']['text'], 92, YELLOW, 6, max_w=W - 200, box=True) if sp.get('hook') else None
    stamps = {i: label(font, s['stamp'], 132, YELLOW, 12) for i, s in enumerate(shots) if s.get('stamp')}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); silent = os.path.join(tmp, 'v.mp4')
    enc = subprocess.Popen([FF, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', silent], stdin=subprocess.PIPE)
    n = round(total * fps); cur = -1; im = None; frames = None
    for f in range(n):
        t = f / fps; i = next(k for k, s in enumerate(shots) if t < s['end'] or k == len(shots) - 1); s = shots[i]
        if i != cur:
            cur = i; im = Image.open(os.path.join(root, s['img'])).convert('RGB') if s.get('img') else None
            frames = clip_frames(root, s, fps, tmp, i) if s.get('clip') else None
        local = t - s['start']; d = s['end'] - s['start']
        fr = still_frame(im, s, min(local / d, 1)) if im else Image.open(frames[min(int(local * fps), len(frames) - 1)]).convert('RGB')
        if hook and t < sp['hook'].get('until', 3): fr.paste(hook, ((W - hook.width) // 2, 110), hook)
        if i in stamps and local > 0.15:
            st = stamps[i]; fr.paste(st, ((W - st.width) // 2, 250 if not (hook and t < sp['hook'].get('until', 3)) else 420), st)
        for t0, t1, c in caps:
            if t0 <= t < t1: fr.paste(c, ((W - c.width) // 2, 1300 - c.height // 2), c); break
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    if enc.wait() != 0: raise SystemExit('the picture encode failed')
    voice = os.path.join(root, sp['voice']); music = os.path.join(root, sp['music']) if sp.get('music') else None
    cmd = [FF, '-y', '-loglevel', 'error', '-i', silent, '-i', voice]
    if music and os.path.exists(music):
        cmd += ['-stream_loop', '-1', '-i', music, '-filter_complex',
                f'[1:a]aresample=48000,apad,atrim=duration={total:.3f},asplit[vo][key];[2:a]aresample=48000,volume={sp.get("music_db", -24)}dB,'
                f'atrim=duration={total:.3f},afade=t=in:d=0.4,afade=t=out:st={total - 1.5:.3f}:d=1.5[m];'
                f'[m][key]sidechaincompress=threshold=0.03:ratio=5:attack=20:release=500[md];[vo][md]amix=inputs=2:normalize=0:duration=first[a]',
                '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-filter_complex', f'[1:a]aresample=48000,apad,atrim=duration={total:.3f}[a]', '-map', '0:v', '-map', '[a]']
    subprocess.check_call(cmd + ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out])
    print(json.dumps({'ok': True, 'seconds': round(total, 2), 'shots': len(shots), 'clips': sum(1 for s in shots if s.get('clip')),
                      'stills': sum(1 for s in shots if s.get('img')), 'out': os.path.abspath(out)}))


if __name__ == '__main__':
    main()
