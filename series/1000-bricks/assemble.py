#!/usr/bin/env python3
"""100 BRICKS assembly: cut an episode's clips to its voice and lay the brick counter, the plus and minus numbers and
the A or B card on top. RUNS ON GITHUB ACTIONS (.github/workflows/bricks-assemble.yml), never in a Claude session.

  python3 assemble.py episodes/ep01 out/ep01.mp4 [--silent]

Reads <episode>/episode.json. Each shot runs for its voice line plus the gap; the last shot holds for the tail with the
vote card up. A clip shorter than its slot is slowed by up to 20 percent, then its last frame is held; a longer one is
cut. --silent builds the picture with no voice (used until the voice files are in the repo). No generation, no network.
Prints one JSON line: {"ok":true,"seconds":S,"shots":N,"voice":true|false,"out":"..."}"""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 24
FONTS = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf']
TEAL, WHITE, INK = (25, 224, 200), (255, 255, 255), (5, 3, 10)
try:                                   # a self-contained ffmpeg from pip, so the cloud run needs no system packages
    import imageio_ffmpeg; FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FF = 'ffmpeg'


def font(px):
    for f in FONTS:
        if os.path.exists(f): return ImageFont.truetype(f, px)
    return ImageFont.load_default(px)      # Pillow's own built-in face, when the machine has no DejaVu


def text(d, xy, s, px, fill, anchor='mm'):
    f = font(px); x, y = xy
    d.text((x + px // 14 + 1, y + px // 12 + 1), s, font=f, fill=(0, 0, 0, 200), anchor=anchor)     # a hard drop shadow, like a printed tile
    d.text((x, y), s, font=f, fill=fill, anchor=anchor)


def overlay(ep, shot, path):
    """One transparent 1080x1920 picture per shot: counter always, a number when the shot has one, the vote card on the last."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    n = str(shot.get('count', ep['count'])); f = font(96); tw = d.textlength(n, font=f); x0 = (W - (72 + 26 + tw)) / 2
    d.rounded_rectangle([x0 - 34, 118, x0 + 72 + 26 + tw + 34, 300], 22, fill=INK + (150,))
    d.rectangle([x0, 150, x0 + 72, 222], fill=TEAL); d.rectangle([x0, 150, x0 + 72, 160], fill=(127, 245, 230)); d.rectangle([x0, 212, x0 + 72, 222], fill=(10, 154, 138))
    d.ellipse([x0 + 16, 166, x0 + 56, 206], fill=(127, 245, 230)); d.ellipse([x0 + 18, 170, x0 + 54, 206], fill=TEAL)
    text(d, (x0 + 72 + 26, 186), n, 96, WHITE, 'lm'); text(d, (W / 2, 262), 'bricks left', 34, (207, 198, 232))
    if shot.get('label'): text(d, (W / 2, 470), shot['label']['text'], 190, shot['label'].get('colour', '#ffffff'))
    if shot.get('vote'):
        v = ep['vote']; d.rectangle([0, 1130, W, 1640], fill=INK + (185,))
        text(d, (W / 2, 1200), v['q'], 60, WHITE); text(d, (W / 2, 1310), 'a:  ' + v['a'], 64, TEAL); text(d, (W / 2, 1410), 'b:  ' + v['b'], 64, (255, 107, 94))
        text(d, (W / 2, 1520), 'comment a or b', 54, (255, 224, 138)); text(d, (W / 2, 1596), f"part {ep['part'] + 1} follows the vote", 34, (207, 198, 232))
    im.save(path)


def dur(p):
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', subprocess.run([FF, '-hide_banner', '-i', p], capture_output=True, text=True).stderr)
    if not m: raise SystemExit(f'cannot read the length of {p}')
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; silent = '--silent' in sys.argv
    if len(a) != 2: raise SystemExit(__doc__)
    root, out = a; ep = json.load(open(os.path.join(root, 'episode.json'))); shots = ep['shots']
    voices = [os.path.join(root, s['voice']) for s in shots]; have = all(os.path.exists(v) for v in voices)
    if not have and not silent: raise SystemExit('voice files missing: ' + ', '.join(v for v in voices if not os.path.exists(v)) + '  (use --silent for a picture-only cut)')
    tmp = tempfile.mkdtemp(); ins, fc, vs, au = [], [], [], []
    for i, s in enumerate(shots):
        clip = os.path.join(root, s['clip']); slot = (dur(voices[i]) if have else s['seconds']) + ep['gap'] + (ep['tail'] if i == len(shots) - 1 else 0)
        c = dur(clip); k = min(1.2, max(1.0, slot / c)); ov = os.path.join(tmp, f'ov{i}.png'); overlay(ep, s, ov)
        ins += ['-i', clip, '-loop', '1', '-t', f'{slot:.3f}', '-i', ov]
        fc.append(f'[{2 * i}:v]setpts={k:.4f}*PTS,fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},'
                  f'tpad=stop_mode=clone:stop_duration=30,trim=duration={slot:.3f},setpts=PTS-STARTPTS[c{i}];[c{i}][{2 * i + 1}:v]overlay=shortest=1,format=yuv420p[v{i}]')
        vs.append(f'[v{i}]')
    n = len(shots); fc.append(''.join(vs) + f'concat=n={n}:v=1:a=0[v]'); maps = ['-map', '[v]']
    if have:
        for i, v in enumerate(voices):
            slot = dur(v) + ep['gap'] + (ep['tail'] if i == n - 1 else 0); ins += ['-i', v]
            fc.append(f'[{2 * n + i}:a]aresample=48000,apad,atrim=duration={slot:.3f}[a{i}]'); au.append(f'[a{i}]')
        fc.append(''.join(au) + f'concat=n={n}:v=0:a=1[a]'); maps += ['-map', '[a]', '-c:a', 'aac', '-b:a', '192k']
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    subprocess.check_call([FF, '-y', '-loglevel', 'error', *ins, '-filter_complex', ';'.join(fc), *maps, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-r', str(FPS), '-movflags', '+faststart', out])
    print(json.dumps({'ok': True, 'seconds': round(dur(out), 2), 'shots': n, 'voice': have, 'out': os.path.abspath(out)}))


if __name__ == '__main__':
    main()
